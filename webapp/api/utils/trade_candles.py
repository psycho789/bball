"""
Trade-derived candlestick aggregation utilities.

Design Pattern: Split Architecture (DB layer + Pure aggregation layer)
Algorithm: Time-Window OHLC Aggregation
Big O: fetch_trades() = O(log n + k) with index, aggregate_trades() = O(n log n) worst case
       (O(n) if trades are pre-sorted by created_time, but we sort per-interval)

This module provides functions to generate trade-derived candlesticks from kalshi.trades.
Trade-derived candles are execution-only (last-trade prices), not bid/ask quotes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
import time
import threading

from ..logging_config import get_logger
from ..cache import CACHE_ENABLED

logger = get_logger(__name__)

# In-memory cache for trade data
# Cache key: (ticker, start_ts, end_ts)
# Cache value: list of trade dicts
# Cache TTL: Indefinite for completed games (end_ts < now - 1 hour), 5 minutes for in-progress
_trade_cache: dict[tuple[str, int, int], tuple[list[dict[str, Any]], float]] = {}
_cache_lock = threading.Lock()
_cache_max_size = 1000  # Maximum number of cached entries (LRU eviction)


def fetch_trades(
    conn: Any,
    ticker: str,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, Any]]:
    """
    Fetch trades from kalshi.trades table for given ticker and time window.
    
    CRITICAL: This function requires bounded time windows (start_ts, end_ts).
    Never fetches "all trades" for a ticker to ensure performance with 7M+ trades.
    
    Caching: Trades for completed games (end_ts < now - 1 hour) are cached indefinitely.
    Trades for in-progress games are cached for 5 minutes.
    
    Args:
        conn: Database connection
        ticker: Market ticker (e.g., "KXNBAGAME-25NOV30OKCPOR-POR")
        start_ts: Start Unix timestamp (seconds) - REQUIRED
        end_ts: End Unix timestamp (seconds) - REQUIRED
    
    Returns:
        List of trade dicts with keys: created_time, yes_price, no_price, count, etc.
    
    Raises:
        ValueError: If start_ts >= end_ts or window is invalid
    """
    if start_ts >= end_ts:
        raise ValueError(f"Invalid time window: start_ts ({start_ts}) >= end_ts ({end_ts})")
    
    # Check cache first (skip if caching is globally disabled)
    cache_key = (ticker, start_ts, end_ts)
    now_ts = int(time.time())
    is_completed_game = end_ts < (now_ts - 3600)  # Game ended more than 1 hour ago
    
    if CACHE_ENABLED:
        with _cache_lock:
            if cache_key in _trade_cache:
                cached_trades, cache_time = _trade_cache[cache_key]
                cache_age = now_ts - cache_time
                
                # For completed games, cache is valid indefinitely
                # For in-progress games, cache is valid for 5 minutes
                if is_completed_game or cache_age < 300:
                    logger.debug(f"[CACHE] fetch_trades({ticker}) - cache HIT - age={cache_age}s, completed={is_completed_game}")
                    return cached_trades
                else:
                    # Cache expired, remove it
                    del _trade_cache[cache_key]
                    logger.debug(f"[CACHE] fetch_trades({ticker}) - cache EXPIRED - age={cache_age}s")
    
    # Cache miss - fetch from database
    # Convert Unix timestamps to TIMESTAMPTZ
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
    
    sql = """
    SELECT 
        created_time,
        yes_price,
        no_price,
        count,
        price,
        taker_side,
        trade_id
    FROM kalshi.trades
    WHERE ticker = %s
      AND created_time >= %s
      AND created_time < %s
    ORDER BY created_time ASC
    """
    
    logger.debug(f"Fetching trades for {ticker} from {start_dt} to {end_dt}")
    query_start = time.time()
    rows = conn.execute(sql, (ticker, start_dt, end_dt)).fetchall()
    query_elapsed = time.time() - query_start
    logger.info(f"[TIMING] fetch_trades({ticker}) - trades_sql: {query_elapsed:.3f}s - rows={len(rows)}")
    
    trades = []
    for row in rows:
        trades.append({
            "created_time": row[0],  # TIMESTAMPTZ
            "yes_price": row[1],     # INTEGER (cents)
            "no_price": row[2],      # INTEGER (cents)
            "count": row[3],         # INTEGER
            "price": row[4],         # NUMERIC (for reference only)
            "taker_side": row[5],    # TEXT
            "trade_id": row[6],      # TEXT
        })
    
    # Store in cache (skip if caching is globally disabled)
    if CACHE_ENABLED:
        with _cache_lock:
            # LRU eviction: if cache is full, remove oldest entry
            if len(_trade_cache) >= _cache_max_size:
                # Remove oldest entry (simple approach: remove first item)
                oldest_key = next(iter(_trade_cache))
                del _trade_cache[oldest_key]
                logger.debug(f"[CACHE] fetch_trades({ticker}) - cache EVICTED oldest entry")
            
            _trade_cache[cache_key] = (trades, now_ts)
            logger.debug(f"[CACHE] fetch_trades({ticker}) - cache SET - completed={is_completed_game}, size={len(_trade_cache)}")
    
    logger.debug(f"Fetched {len(trades)} trades")
    return trades


def aggregate_trades(
    trade_rows: list[dict[str, Any]],
    interval_seconds: int,
) -> list[dict[str, Any]]:
    """
    Aggregate trade rows into candlesticks by time interval.
    
    Pure function (no DB dependency) for testability.
    Returns sparse series (only intervals with trades).
    
    CRITICAL: 
    - Uses integer cents end-to-end (no float math)
    - Sorts trades by created_time within each interval
    - Only returns intervals that contain ≥1 trade with valid price/volume pairs
    - Derives canonical executed price from yes_price (YES market) or 100 - no_price (NO execution)
    
    Args:
        trade_rows: List of trade dicts with created_time, yes_price, no_price, count, taker_side, etc.
        interval_seconds: Aggregation interval in seconds (1, 10, 60, etc.)
    
    Returns:
        List of candlestick dicts with keys:
        - period_ts: End of interval (TIMESTAMPTZ) - matches kalshi.candlesticks.period_ts convention
        - interval_seconds: Interval length
        - price_open_cents: First trade executed price in interval (integer cents)
        - price_high_cents: Highest trade executed price in interval
        - price_low_cents: Lowest trade executed price in interval
        - price_close_cents: Last trade executed price in interval
        - price_mean_cents: VWAP (volume-weighted average price) in cents
        - volume: Total volume (SUM(count))
        - yes_price_close_cents: Yes price from last trade
        - no_price_close_cents: No price from last trade
        - is_filled: False (actual data, not interpolated)
    """
    if not trade_rows:
        return []
    
    # Group trades by interval (truncate to interval boundary)
    trades_by_interval = defaultdict(list)
    
    for trade in trade_rows:
        created_time = trade["created_time"]
        if isinstance(created_time, datetime):
            # Normalize to UTC-aware datetime for consistent bucketing
            if created_time.tzinfo is None:
                # Naive datetime - assume UTC
                created_time = created_time.replace(tzinfo=timezone.utc)
            elif created_time.tzinfo != timezone.utc:
                # Convert to UTC
                created_time = created_time.astimezone(timezone.utc)
            
            # Truncate to interval boundary
            # Example: interval_seconds=1: truncate microseconds
            # Example: interval_seconds=10: truncate to 10-second boundary
            if interval_seconds == 1:
                interval_key = created_time.replace(microsecond=0)
            else:
                # Truncate to interval_seconds boundary
                total_seconds = int(created_time.timestamp())
                truncated_seconds = (total_seconds // interval_seconds) * interval_seconds
                interval_key = datetime.fromtimestamp(truncated_seconds, tz=timezone.utc)
        else:
            # Fallback: assume it's already a datetime-like object
            interval_key = created_time
        
        trades_by_interval[interval_key].append(trade)
    
    candlesticks = []
    
    for interval_ts, interval_trades in sorted(trades_by_interval.items()):
        # CRITICAL: Sort trades by created_time within each interval
        # Do NOT assume list order
        interval_trades_sorted = sorted(
            interval_trades,
            key=lambda t: t["created_time"]
        )
        
        # Build paired (price, volume) tuples to ensure correct VWAP calculation
        # Derive canonical executed price: use yes_price if available, else derive from no_price
        # For YES market: executed price is yes_price (when taker_side='yes') or yes_price (when taker_side='no', still represents YES price)
        # If yes_price is None but no_price exists, derive: 100 - no_price (convert NO market to YES market space)
        pairs = []
        for t in interval_trades_sorted:
            executed_price_cents = None
            volume = t.get("count")
            
            # Determine executed price in YES market space (cents)
            if t.get("yes_price") is not None:
                executed_price_cents = int(t["yes_price"])
            elif t.get("no_price") is not None:
                # Convert NO market price to YES market space: YES = 100 - NO
                executed_price_cents = 100 - int(t["no_price"])
            elif t.get("price") is not None:
                # Fallback: use price field if it exists (convert from 0-1 to cents)
                executed_price_cents = int(float(t["price"]) * 100)
            
            # Only include trades with both valid price and volume
            if executed_price_cents is not None and volume is not None:
                pairs.append((executed_price_cents, volume))
        
        if not pairs:
            continue  # Skip intervals with no valid price/volume pairs
        
        # Extract prices and volumes from paired tuples (guaranteed aligned)
        executed_prices_cents = [p for p, _ in pairs]
        volumes = [v for _, v in pairs]
        
        # Calculate OHLC using integer cents
        price_open_cents = executed_prices_cents[0]  # First trade in interval
        price_close_cents = executed_prices_cents[-1]  # Last trade in interval
        price_high_cents = max(executed_prices_cents)
        price_low_cents = min(executed_prices_cents)
        
        # Calculate VWAP in cents (volume-weighted average)
        # Use paired tuples to ensure correct alignment (fixes VWAP bug)
        # Use integer division for cents VWAP (floors); if you want rounding, add + total_volume/2 before //
        total_price_volume = sum(p * v for p, v in pairs)
        total_volume = sum(volumes)
        price_mean_cents = total_price_volume // total_volume if total_volume > 0 else price_close_cents
        
        # Get yes/no prices from last trade (for reference)
        # Note: These are the raw prices from the trade, not the executed price we calculated
        last_trade = interval_trades_sorted[-1]
        
        # period_ts as Unix timestamp (seconds) for frontend compatibility
        period_end = interval_ts + timedelta(seconds=interval_seconds)
        candlestick = {
            "period_ts": int(period_end.timestamp()),  # Unix timestamp (seconds) - end of period
            "interval_seconds": interval_seconds,
            "price_open_cents": price_open_cents,
            "price_high_cents": price_high_cents,
            "price_low_cents": price_low_cents,
            "price_close_cents": price_close_cents,
            "price_mean_cents": price_mean_cents,
            "volume": total_volume,
            "yes_price_close_cents": last_trade.get("yes_price"),
            "no_price_close_cents": last_trade.get("no_price"),
            "is_filled": False,  # Actual data, not interpolated
        }
        
        candlesticks.append(candlestick)
    
    return candlesticks


def derive_game_window(
    conn: Any,
    game_id: str,
) -> tuple[int, int] | None:
    """
    Derive game time window from ESPN data.
    
    Uses event_date as game start (scheduled time, not guaranteed tipoff) and duration 
    from ESPN probabilities (MAX(last_modified_utc) - MIN(last_modified_utc)) 
    with 15-minute buffer at the end.
    
    Note: Only buffers the end time, not the start. If you need to capture pre-game trades,
    consider adding a start buffer as well.
    
    Args:
        conn: Database connection
        game_id: ESPN game_id
    
    Returns:
        Tuple of (start_ts, end_ts) Unix timestamps, or None if game not found
    """
    sql = """
    SELECT 
        sg.event_date as game_start,
        EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as duration_seconds
    FROM espn.scoreboard_games sg
    JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
    WHERE sg.event_id = %s
    GROUP BY sg.event_id, sg.event_date
    """
    
    row = conn.execute(sql, (game_id,)).fetchone()
    
    if not row or not row[0]:
        return None
    
    game_start = row[0]  # TIMESTAMPTZ (scheduled event_date, may not be actual tipoff)
    duration_seconds = row[1] if row[1] else 0
    
    # Add 15-minute buffer at the end (only)
    buffer_seconds = 15 * 60
    start_ts = int(game_start.timestamp())
    end_ts = start_ts + duration_seconds + buffer_seconds
    
    return (start_ts, end_ts)

