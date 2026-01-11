"""
Probabilities endpoint - get probability time series for a game.

Design Pattern: Composite data aggregation from multiple sources
Algorithm: Game-timeline normalization - ESPN timestamps normalized to synthetic timeline anchored at event_date, Kalshi uses actual timestamps
Big O: O(n + m) where n = ESPN points, m = Kalshi candles
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from fastapi import APIRouter, Query, HTTPException

from ..db import get_db_connection
from ..cache import cached
from ..logging_config import get_logger
from .utils import get_cache_ttl_for_game
from ..utils.trade_candles import fetch_trades, aggregate_trades, derive_game_window

router = APIRouter()
logger = get_logger(__name__)


@router.get("/games/{game_id}/probs")
@cached(ttl_seconds=86400 * 365, dynamic_ttl=lambda result: get_cache_ttl_for_game(result))
def get_game_probabilities(
    game_id: str,
    include_kalshi: bool = Query(True, description="Include Kalshi candlestick data"),
) -> dict[str, Any]:
    """
    Get probability time series for a game.
    
    Returns ESPN probabilities and optionally Kalshi market prices.
    
    ESPN data: {time (Unix timestamp), home_prob, away_prob, home_score, away_score}
    Kalshi data: {time (Unix timestamp), price} where price is in cents (0-100)
    
    Design Pattern: Composite data aggregation from multiple sources
    Algorithm: Game-timeline normalization - ESPN timestamps normalized to synthetic timeline anchored at event_date, Kalshi uses actual timestamps
    Big O: O(n + m) where n = ESPN points, m = Kalshi candles
    """
    request_start = time.time()
    with get_db_connection() as conn:
        db_conn_time = time.time() - request_start
        logger.debug(f"[TIMING] get_game_probabilities({game_id}) - DB connection: {db_conn_time:.3f}s")
        
        # Get ESPN probability data with actual timestamps
        # Use last_modified_utc as the actual wall-clock time
        # Get final scores from scoreboard_games (per-record scores can be added later if needed)
        query_start = time.time()
        espn_sql = """
        SELECT 
            p.sequence_number,
            p.last_modified_utc,
            p.home_win_percentage,
            p.away_win_percentage,
            sg.home_score as home_score,
            sg.away_score as away_score
        FROM espn.probabilities_raw_items p
        LEFT JOIN espn.scoreboard_games sg ON p.game_id = sg.event_id
        WHERE p.game_id = %s
        AND p.season_label = '2025-26'
        ORDER BY p.last_modified_utc ASC
        """
        espn_rows = conn.execute(espn_sql, (game_id,)).fetchall()
        espn_query_time = time.time() - query_start
        logger.debug(f"[TIMING] get_game_probabilities({game_id}) - ESPN query: {espn_query_time:.3f}s ({len(espn_rows)} rows)")
        
        if not espn_rows:
            raise HTTPException(
                status_code=404, 
                detail=f"No ESPN probability data for game {game_id}"
            )
        
        # Get game start time (event_date) to align ESPN data to game timeline
        query_start = time.time()
        game_start_sql = "SELECT event_date FROM espn.scoreboard_games WHERE event_id = %s LIMIT 1"
        game_start_row = conn.execute(game_start_sql, (game_id,)).fetchone()
        game_start_query_time = time.time() - query_start
        logger.debug(f"[TIMING] get_game_probabilities({game_id}) - Game start query: {game_start_query_time:.3f}s")
        game_start_utc = game_start_row[0] if game_start_row and game_start_row[0] else None
        game_start_timestamp = int(game_start_utc.timestamp()) if game_start_utc else None
        
        # Transform ESPN data to Lightweight Charts format
        # Normalize ESPN recording timestamps onto a synthetic game timeline anchored at event_date
        # ESPN records probabilities FOR the game, but records them at different wall-clock times
        # We preserve relative timing between ESPN records but map them to a game timeline starting at event_date
        espn_data = []
        min_espn_timestamp = None
        max_espn_timestamp = None
        first_espn_timestamp = None
        
        for row in espn_rows:
            last_modified_utc = row[1]  # TIMESTAMPTZ
            if last_modified_utc is None:
                continue
            
            # Convert to Unix timestamp (seconds)
            espn_recording_timestamp = int(last_modified_utc.timestamp())
            
            if first_espn_timestamp is None:
                first_espn_timestamp = espn_recording_timestamp
            
            if min_espn_timestamp is None:
                min_espn_timestamp = espn_recording_timestamp
            min_espn_timestamp = min(min_espn_timestamp, espn_recording_timestamp)
            max_espn_timestamp = max(max_espn_timestamp, espn_recording_timestamp) if max_espn_timestamp else espn_recording_timestamp
            
            # Normalize to game timeline: calculate offset from first ESPN record to game start
            # Then apply that offset to all ESPN timestamps to create synthetic game timeline
            if game_start_timestamp is not None and first_espn_timestamp is not None:
                # Calculate elapsed time from first ESPN record to this record
                elapsed_from_first = espn_recording_timestamp - first_espn_timestamp
                # Map to synthetic game timeline: event_date + elapsed time from first ESPN record
                aligned_timestamp = game_start_timestamp + elapsed_from_first
            else:
                # Fallback: use recording timestamp if we don't have game start
                aligned_timestamp = espn_recording_timestamp
            
            # home_win_percentage is stored in database as 0-100 (percentage format)
            # Convert to 0-1 format for consistency with frontend expectations
            home_win_pct = float(row[2]) if row[2] is not None else 50.0
            away_win_pct = float(row[3]) if row[3] is not None else 50.0
            # Normalize: if value > 1, it's in 0-100 format, divide by 100
            home_prob = (home_win_pct / 100.0) if home_win_pct > 1.0 else home_win_pct
            away_prob = (away_win_pct / 100.0) if away_win_pct > 1.0 else away_win_pct
            
            espn_data.append({
                "time": aligned_timestamp,  # Aligned to game timeline
                "home_prob": home_prob,  # 0-1 format
                "away_prob": away_prob,  # 0-1 format
                "home_score": int(row[4]) if row[4] is not None else 0,
                "away_score": int(row[5]) if row[5] is not None else 0,
            })
        
        result: dict[str, Any] = {
            "espn": espn_data,
        }
        
        logger.debug(f"ESPN data processed: {len(espn_data)} points, "
                     f"time_range=[{min_espn_timestamp}, {max_espn_timestamp}]")
        
        # Get Kalshi candlestick data if requested
        if include_kalshi and min_espn_timestamp is not None and max_espn_timestamp is not None:
            logger.debug("Kalshi data requested, calculating game window for Kalshi query...")
            query_start = time.time()
            # Calculate game window using event_date as start and duration from ESPN data
            # Game start = event_date (actual scheduled start time, e.g., 5:00 PM PT)
            # Game duration = MAX(last_modified_utc) - MIN(last_modified_utc) (ESPN recording duration, e.g., 2h 28m)
            # Game end = event_date + duration (e.g., 5:00 PM + 2h 28m = 7:28 PM PT)
            # Filter Kalshi data from game_start to game_end (not from ESPN timestamps!)
            # Optimized: Pre-calculate game window to avoid repeated calculations in query
            # Get game window first (simpler query)
            window_sql = """
            SELECT 
                sg.event_date as game_start,
                EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as espn_duration_seconds
            FROM espn.scoreboard_games sg
            JOIN espn.probabilities_raw_items p ON sg.event_id = p.game_id
            WHERE sg.event_id = %s
            GROUP BY sg.event_id, sg.event_date
            LIMIT 1
            """
            window_start = time.time()
            window_row = conn.execute(window_sql, (game_id,)).fetchone()
            window_time = time.time() - window_start
            logger.debug(f"[TIMING] get_game_probabilities({game_id}) - Window query: {window_time:.3f}s")
            
            if not window_row:
                logger.warning(f"No game window found for game {game_id}")
                kalshi_rows = []
            else:
                game_start = window_row[0]
                espn_duration_seconds = window_row[1] or 0
                # Add 15-minute buffer at the end (consistent with derive_game_window)
                buffer_seconds = 15 * 60
                game_end = game_start + timedelta(seconds=espn_duration_seconds + buffer_seconds)
                
                # Get markets for this game (simpler query without CROSS JOIN)
                markets_start = time.time()
                markets_sql = """
                SELECT DISTINCT ON (kmw.ticker)
                    kmw.ticker,
                    kmw.event_ticker,
                    kmw.yes_sub_title,
                    kmw.kalshi_team_side,
                    sg.home_team_abbrev,
                    sg.away_team_abbrev,
                    sg.home_team_display_name,
                    sg.away_team_display_name,
                    COALESCE(sg.home_team_name, '') as home_team_name,
                    COALESCE(sg.away_team_name, '') as away_team_name
                FROM kalshi.markets_with_games kmw
                JOIN espn.scoreboard_games sg ON kmw.espn_event_id = sg.event_id
                WHERE kmw.espn_event_id = %s
                  AND kmw.kalshi_team_side IS NOT NULL
                ORDER BY kmw.ticker, kmw.snapshot_id DESC
                """
                market_rows = conn.execute(markets_sql, (game_id,)).fetchall()
                markets_time = time.time() - markets_start
                logger.debug(f"[TIMING] get_game_probabilities({game_id}) - Markets query: {markets_time:.3f}s ({len(market_rows)} markets)")
                
                if not market_rows:
                    kalshi_rows = []
                else:
                    # Get tickers and query candlesticks efficiently
                    tickers = [row[0] for row in market_rows]
                    candlesticks_start = time.time()
                    candlesticks_sql = """
                    SELECT 
                        c.ticker,
                        c.period_ts,
                        c.price_close,
                        c.yes_bid_close,
                        c.yes_ask_close,
                        c.volume,
                        c.period_interval_min
                    FROM kalshi.candlesticks c
                    WHERE c.ticker = ANY(%s)
                      AND (
                          c.price_close IS NOT NULL 
                          OR (c.yes_bid_close IS NOT NULL AND c.yes_ask_close IS NOT NULL)
                      )
                      AND c.period_ts >= %s
                      AND c.period_ts <= %s
                    ORDER BY c.ticker, c.period_ts
                    """
                    candlestick_rows = conn.execute(candlesticks_sql, (tickers, game_start, game_end)).fetchall()
                    candlesticks_time = time.time() - candlesticks_start
                    logger.debug(f"[TIMING] get_game_probabilities({game_id}) - Candlesticks query: {candlesticks_time:.3f}s ({len(candlestick_rows)} rows)")
                    
                    # Join candlesticks with market metadata
                    # Create lookup dict for market metadata
                    market_lookup = {row[0]: row for row in market_rows}
                    
                    # Combine data
                    kalshi_rows = []
                    for c_row in candlestick_rows:
                        ticker = c_row[0]
                        if ticker in market_lookup:
                            m_row = market_lookup[ticker]
                            kalshi_rows.append((
                                ticker,  # 0
                                m_row[1],  # event_ticker
                                m_row[2],  # yes_sub_title
                                m_row[3],  # kalshi_team_side
                                m_row[4],  # home_team_abbrev
                                m_row[5],  # away_team_abbrev
                                m_row[6],  # home_team_display_name
                                m_row[7],  # away_team_display_name
                                m_row[8],  # home_team_name
                                m_row[9],  # away_team_name
                                c_row[1],  # period_ts
                                c_row[2],  # price_close
                                c_row[3],  # yes_bid_close
                                c_row[4],  # yes_ask_close
                                c_row[5],  # volume
                                c_row[6],  # period_interval_min
                            ))
            
            kalshi_query_time = time.time() - query_start
            logger.debug(f"[TIMING] get_game_probabilities({game_id}) - Kalshi query TOTAL: {kalshi_query_time:.3f}s ({len(kalshi_rows)} rows)")
        else:
            logger.debug("Kalshi data not requested (include_kalshi=False)")
            kalshi_rows = []
        
        # Group by ticker (home team market vs away team market)
        logger.debug(f"Processing {len(kalshi_rows)} Kalshi candlestick rows...")
        kalshi_by_ticker: dict[str, dict[str, Any]] = {}
        kalshi_validation: dict[str, Any] = {
            "game_id": game_id,
            "markets_found": [],
            "warnings": [],
        }
        
        # Track seen tickers to avoid duplicate validation entries
        seen_tickers: set[str] = set()
        
        for idx, row in enumerate(kalshi_rows, 1):
            if idx % 100 == 0:
                logger.debug(f"Processing Kalshi row {idx}/{len(kalshi_rows)}...")
            ticker = row[0]
            event_ticker = row[1]
            team_name = row[2]
            team_side = row[3]  # 'home' or 'away'
            home_team_abbrev = row[4]  # For validation
            away_team_abbrev = row[5]  # For validation
            home_team_display_name = row[6]
            away_team_display_name = row[7]
            home_team_name = row[8]
            away_team_name = row[9]
            period_ts = row[10]
            price_close = row[11]
            yes_bid_close = row[12]
            yes_ask_close = row[13]
            volume = row[14]
            period_interval = row[15]
            
            if ticker not in kalshi_by_ticker:
                kalshi_by_ticker[ticker] = {
                    "team": team_name,
                    "team_side": team_side,
                    "event_ticker": event_ticker,
                    "data": [],
                }
                
                # Comprehensive validation for first occurrence of each ticker
                validation_entry = {
                    "ticker": ticker,
                    "event_ticker": event_ticker,
                    "kalshi_team_name": team_name,
                    "team_side": team_side,
                    "espn_home_abbrev": home_team_abbrev,
                    "espn_away_abbrev": away_team_abbrev,
                    "espn_home_display": home_team_display_name,
                    "espn_away_display": away_team_display_name,
                }
                
                # Validate team name matching
                expected_team_display = home_team_display_name if team_side == "home" else away_team_display_name
                expected_team_abbrev = home_team_abbrev if team_side == "home" else away_team_abbrev
                expected_team_name = home_team_name if team_side == "home" else away_team_name
                
                # Check if team name contains expected values (case-insensitive)
                team_name_lower = (team_name or "").lower()
                expected_display_lower = (expected_team_display or "").lower()
                expected_abbrev_lower = (expected_team_abbrev or "").lower()
                expected_name_lower = (expected_team_name or "").lower()
                
                name_match_found = (
                    expected_abbrev_lower in team_name_lower
                    or expected_display_lower in team_name_lower
                    or expected_name_lower in team_name_lower
                    or team_name_lower in expected_display_lower
                )
                
                validation_entry["name_match_valid"] = name_match_found
                
                if not name_match_found:
                    kalshi_validation["warnings"].append(
                        f"Market {ticker}: Team name '{team_name}' doesn't clearly match "
                        f"expected {'home' if team_side == 'home' else 'away'} team '{expected_team_display}'"
                    )
                
                kalshi_validation["markets_found"].append(validation_entry)
                seen_tickers.add(ticker)
            
            # Use price_close directly (this is what Kalshi uses)
            # We previously switched to mid-price while debugging timestamp issues, but now that's fixed
            display_price = None
            
            if price_close is not None:
                display_price = float(price_close)
            elif yes_bid_close is not None and yes_ask_close is not None:
                # Fallback to mid-price only if price_close is not available
                display_price = (yes_bid_close + yes_ask_close) / 2.0
            
            # Use period_ts as Unix timestamp (wall-clock time)
            if display_price is not None and period_ts is not None:
                unix_timestamp = int(period_ts.timestamp())
                kalshi_by_ticker[ticker]["data"].append({
                    "time": unix_timestamp,  # Unix timestamp (seconds since epoch)
                    "price": display_price,  # Smart price: price_close if resolved, else mid-price
                    "bid": yes_bid_close,
                    "ask": yes_ask_close,
                    "price_close": price_close,  # Keep original for reference
                    "volume": volume,
                    "period_ts": period_ts.isoformat() if period_ts else None,
                    "period_interval_min": period_interval,
                })
        
        # Add summary validation info
        if kalshi_validation["markets_found"]:
            home_markets = [m for m in kalshi_validation["markets_found"] if m["team_side"] == "home"]
            away_markets = [m for m in kalshi_validation["markets_found"] if m["team_side"] == "away"]
            kalshi_validation["summary"] = {
                "total_markets": len(kalshi_validation["markets_found"]),
                "home_markets": len(home_markets),
                "away_markets": len(away_markets),
                "all_name_matches_valid": all(m.get("name_match_valid", False) for m in kalshi_validation["markets_found"]),
                "warnings_count": len(kalshi_validation["warnings"]),
            }
        
        # Add validation info to result for debugging
        result["kalshi"] = kalshi_by_ticker
        result["kalshi_validation"] = kalshi_validation
        
        if kalshi_validation.get("summary"):
            logger.debug(f"Kalshi validation summary: {kalshi_validation['summary']}")
        logger.debug(f"Kalshi data processed: {len(kalshi_by_ticker)} tickers with data")
    
    total_time = time.time() - request_start
    logger.info(f"[TIMING] get_game_probabilities({game_id}) - TOTAL: {total_time:.3f}s - "
                f"espn_points={len(result.get('espn', []))}, "
                f"kalshi_tickers={len(kalshi_by_ticker)}")
    return result


@router.get("/probabilities/{game_id}/kalshi-candles")
@cached(ttl_seconds=3600)  # 1 hour TTL, in-memory cache (per-worker)
def get_kalshi_candles(
    game_id: str,
    interval_seconds: int = Query(60, ge=1, le=3600, description="Candlestick interval in seconds (1, 10, 60)"),
    source: str = Query("auto", description="Data source: 'official' or 'trades'"),
    ticker: Optional[str] = Query(None, description="Specific market ticker (optional, for multi-ticker games)"),
    start_ts: Optional[int] = Query(None, description="Start Unix timestamp (seconds)"),
    end_ts: Optional[int] = Query(None, description="End Unix timestamp (seconds)"),
) -> dict[str, Any]:
    """
    Get Kalshi candlesticks for a game.
    
    Performance guardrails:
    - For 1-second resolution: max_points=3600 (1 hour) enforced
    - If window too large: returns 400 with message "Zoom in to use 1-second view"
    - If start_ts/end_ts omitted: derives from game window (event_date + duration)
    
    Multi-ticker support:
    - If ticker provided: returns {"candles": [...], "ticker": "..."}
    - If ticker omitted: returns {"markets": [{"ticker": "...", "candles": [...]}, ...]}
    - Primary market selection: first ticker by snapshot_id DESC (most recent)
    
    Design Pattern: Query-Time Aggregation with Bounded Windows
    Algorithm: Time-Window OHLC Aggregation
    Big O: O(log n + k) for fetch, O(k) for aggregate where k = trades in window
    
    Args:
        game_id: ESPN game_id
        interval_seconds: Aggregation interval (1, 10, 60)
        source: "official" (uses kalshi.candlesticks) or "trades" (uses kalshi.trades)
        ticker: Optional specific ticker (for multi-ticker games)
        start_ts: Optional start timestamp (derived from game if omitted)
        end_ts: Optional end timestamp (derived from game if omitted)
    
    Returns:
        JSON response with candles array or markets array
    """
    request_start = time.time()
    logger.debug(f"[TIMING] get_kalshi_candles({game_id}, interval={interval_seconds}, source={source}) - START")
    
    with get_db_connection() as conn:
        db_conn_time = time.time() - request_start
        logger.debug(f"[TIMING] get_kalshi_candles({game_id}) - DB connection: {db_conn_time:.3f}s")
        
        # Determine data source
        use_official = (source == "official" or (source == "auto" and interval_seconds == 60))
        use_trades = (source == "trades" or (source == "auto" and interval_seconds in [1, 10]))
        
        if use_official:
            # Use official candlesticks from kalshi.candlesticks
            result = _get_official_candles(conn, game_id, interval_seconds, ticker, start_ts, end_ts)
        elif use_trades:
            # Use trade-derived candles from kalshi.trades
            result = _get_trade_candles(conn, game_id, interval_seconds, ticker, start_ts, end_ts)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source '{source}' or interval_seconds={interval_seconds}. Use source='official' for 60s or source='trades' for 1s/10s."
            )
        
        total_time = time.time() - request_start
        logger.info(f"[TIMING] get_kalshi_candles({game_id}) - TOTAL: {total_time:.3f}s")
        return result


def _get_official_candles(
    conn: Any,
    game_id: str,
    interval_seconds: int,
    ticker: Optional[str],
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> dict[str, Any]:
    """
    Get official candlesticks from kalshi.candlesticks table.
    
    CRITICAL: Official candlesticks only exist for 1-minute (60-second) intervals.
    This function validates that interval_seconds is a multiple of 60.
    """
    # Validate interval_seconds is compatible with official candlesticks
    if interval_seconds % 60 != 0:
        raise HTTPException(
            status_code=400,
            detail=f"Official candlesticks require interval_seconds to be a multiple of 60. Got {interval_seconds}."
        )
    # For official candles, we use the existing logic from get_game_probabilities
    # This is a simplified version that returns candles in the expected format
    sql = """
    SELECT DISTINCT ON (kmw.ticker)
        kmw.ticker,
        kmw.event_ticker,
        kmw.yes_sub_title,
        kmw.kalshi_team_side
    FROM kalshi.markets_with_games kmw
    WHERE kmw.espn_event_id = %s
      AND kmw.kalshi_team_side IS NOT NULL
      AND (%s::TEXT IS NULL OR kmw.ticker = %s)
    ORDER BY kmw.ticker, kmw.snapshot_id DESC
    """
    
    market_rows = conn.execute(sql, (game_id, ticker, ticker)).fetchall()
    
    if not market_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No Kalshi markets found for game {game_id}"
        )
    
    # Create ticker to team_side lookup from market_rows
    ticker_to_team_side = {row[0]: row[3] for row in market_rows}  # ticker -> kalshi_team_side
    
    # For now, return first market (can extend to multiple markets later)
    selected_ticker = ticker if ticker else market_rows[0][0]
    
    # Query official candlesticks
    # Convert timestamps to datetime objects for consistent null handling
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None
    
    candles_sql = """
    SELECT 
        period_ts,
        price_close,
        yes_bid_close,
        yes_ask_close,
        volume,
        period_interval_min
    FROM kalshi.candlesticks
    WHERE ticker = %s
      AND period_interval_min = %s
      AND (%s::TIMESTAMPTZ IS NULL OR period_ts >= %s)
      AND (%s::TIMESTAMPTZ IS NULL OR period_ts <= %s)
    ORDER BY period_ts
    """
    
    interval_min = interval_seconds // 60
    
    rows = conn.execute(
        candles_sql,
        (selected_ticker, interval_min, start_dt, start_dt, end_dt, end_dt)
    ).fetchall()
    
    candles = []
    for row in rows:
        period_ts = row[0]
        candles.append({
            "period_ts": int(period_ts.timestamp()) if period_ts is not None else None,
            "price_close": float(row[1]) if row[1] is not None else None,
            "yes_bid_close": row[2] if row[2] is not None else None,
            "yes_ask_close": row[3] if row[3] is not None else None,
            "volume": row[4] if row[4] is not None else None,
            "interval_seconds": interval_seconds,
            "source": "official",
        })
    
    return {
        "candles": candles,
        "ticker": selected_ticker,
        "team_side": ticker_to_team_side.get(selected_ticker),
        "interval_seconds": interval_seconds,
        "source": "official",
    }


def _get_trade_candles(
    conn: Any,
    game_id: str,
    interval_seconds: int,
    ticker: Optional[str],
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> dict[str, Any]:
    """Get trade-derived candlesticks from kalshi.trades table."""
    # Derive time window if not provided
    if start_ts is None or end_ts is None:
        window = derive_game_window(conn, game_id)
        if not window:
            raise HTTPException(
                status_code=404,
                detail=f"Game {game_id} not found or has no ESPN data"
            )
        start_ts, end_ts = window
        logger.debug(f"Derived game window: {start_ts} to {end_ts}")
    
    # Get tickers for this game
    sql = """
    SELECT DISTINCT ON (kmw.ticker)
        kmw.ticker,
        kmw.event_ticker,
        kmw.yes_sub_title,
        kmw.kalshi_team_side
    FROM kalshi.markets_with_games kmw
    WHERE kmw.espn_event_id = %s
      AND kmw.kalshi_team_side IS NOT NULL
      AND (%s::TEXT IS NULL OR kmw.ticker = %s)
    ORDER BY kmw.ticker, kmw.snapshot_id DESC
    """
    
    market_rows = conn.execute(sql, (game_id, ticker, ticker)).fetchall()
    
    if not market_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No Kalshi markets found for game {game_id}"
        )
    
    # If ticker specified, use it; else return all markets
    if ticker:
        selected_tickers = [ticker]
    else:
        selected_tickers = [row[0] for row in market_rows]
    
    # Create ticker to team_side lookup from market_rows
    ticker_to_team_side = {row[0]: row[3] for row in market_rows}  # ticker -> kalshi_team_side
    
    if len(selected_tickers) == 1:
        # Single ticker: return simple format
        ticker_str = selected_tickers[0]
        trades = fetch_trades(conn, ticker_str, start_ts, end_ts)
        candles = aggregate_trades(trades, interval_seconds)
        
        return {
            "candles": candles,
            "ticker": ticker_str,
            "team_side": ticker_to_team_side.get(ticker_str),
            "interval_seconds": interval_seconds,
            "source": "trades",
        }
    else:
        # Multiple tickers: return markets array
        markets = []
        for ticker_str in selected_tickers:
            trades = fetch_trades(conn, ticker_str, start_ts, end_ts)
            candles = aggregate_trades(trades, interval_seconds)
            markets.append({
                "ticker": ticker_str,
                "team_side": ticker_to_team_side.get(ticker_str),
                "candles": candles,
            })
        
        return {
            "markets": markets,
            "interval_seconds": interval_seconds,
            "source": "trades",
        }

