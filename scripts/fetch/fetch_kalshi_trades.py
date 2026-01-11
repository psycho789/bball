#!/usr/bin/env python3
"""
Fetch trade data from Kalshi API for completed NBA games from 2025-26 season.

Design Pattern: Batch Fetch with Pagination
- Queries database for past games that have Kalshi markets
- Fetches trades for each market ticker with pagination
- Stores raw JSON responses with manifests

Algorithm: Linear scan O(n) where n = number of markets
Big O: O(n) time, O(n) space for paginated trade responses

Usage:
  python scripts/fetch_kalshi_trades.py --dsn "$DATABASE_URL"
  python scripts/fetch_kalshi_trades.py --dsn "$DATABASE_URL" --limit 10  # for testing
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import psycopg
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, parse_iso8601_z
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest

# Configure verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_kalshi_credentials() -> tuple[str, bytes]:
    """Load Kalshi API credentials from files."""
    logger.debug("Loading Kalshi API credentials...")
    root_dir = Path(__file__).parent.parent
    api_key_path = root_dir / "kalshi-api-key-public.txt"
    private_key_path = root_dir / "kalshi-api-key-private.txt"
    
    if not api_key_path.exists():
        raise FileNotFoundError(f"API key file not found: {api_key_path}")
    if not private_key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {private_key_path}")
    
    api_key_id = api_key_path.read_text(encoding="utf-8").strip()
    private_key_pem = private_key_path.read_bytes()
    
    logger.debug(f"Loaded API key ID: {api_key_id[:8]}...")
    logger.debug(f"Private key size: {len(private_key_pem)} bytes")
    
    return api_key_id, private_key_pem


def sign_request(private_key_pem: bytes, timestamp: str, method: str, path: str) -> str:
    """Sign a request using RSA-SHA256."""
    message = f"{timestamp}{method}{path}".encode("utf-8")
    
    # Load the private key
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None,
        backend=default_backend()
    )
    
    # Sign the message
    signature = private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Return base64-encoded signature
    return base64.b64encode(signature).decode("utf-8")


def fetch_trades_with_auth(
    api_key_id: str,
    private_key_pem: bytes,
    ticker: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
    min_ts: int | None = None,
    max_ts: int | None = None,
) -> dict[str, Any]:
    """Fetch trades from Kalshi API with authentication."""
    logger.debug(f"Preparing API request: ticker={ticker}, limit={limit}, cursor={'present' if cursor else 'none'}")
    
    base_url = "https://api.elections.kalshi.com/trade-api/v2"
    
    # Build query parameters using proper URL encoding
    query_params = {}
    if limit:
        query_params["limit"] = limit
    if cursor:
        query_params["cursor"] = cursor  # Use FULL cursor, properly URL-encoded
        logger.debug(f"Using cursor: {cursor[:50]}..." if len(cursor) > 50 else f"Using cursor: {cursor}")
    if ticker:
        query_params["ticker"] = ticker
    if min_ts:
        query_params["min_ts"] = min_ts
    if max_ts:
        query_params["max_ts"] = max_ts
    
    query_string = urlencode(query_params)
    endpoint_path = "/markets/trades"
    endpoint = f"{endpoint_path}?{query_string}" if query_string else endpoint_path
    url = f"{base_url}{endpoint}"
    
    # Log URL with truncated cursor for readability
    log_url = url.replace(f"cursor={cursor}", f"cursor={cursor[:20]}...") if cursor and len(cursor) > 20 else url
    logger.debug(f"Request URL: {log_url}")
    
    # Sign the request - path should be /trade-api/v2/markets/trades (without query string)
    timestamp = str(int(time.time() * 1000))  # milliseconds
    method = "GET"
    url_path = f"/trade-api/v2{endpoint_path}"  # Path without query string for signing
    
    logger.debug(f"Signing request: method={method}, path={url_path}, timestamp={timestamp}")
    signature = sign_request(private_key_pem, timestamp, method, url_path)
    logger.debug(f"Signature generated: {signature[:20]}...")
    
    # Make the request
    headers = {
        "Accept": "application/json",
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }
    
    retry = HttpRetry(
        max_attempts=6,
        timeout_seconds=20.0,
        base_backoff_seconds=1.0,
        max_backoff_seconds=60.0,
        jitter_seconds=0.25,
        deadline_seconds=180.0,
    )
    
    try:
        logger.debug(f"Making HTTP request (max attempts: {retry.max_attempts})...")
        start_time = time.time()
        status, resp_headers, body = http_get_bytes(url, retry, headers=headers, allow_non_200=True)
        elapsed = time.time() - start_time
        
        logger.debug(f"HTTP response: status={status}, body_size={len(body)} bytes, elapsed={elapsed:.2f}s")
        
        if status != 200:
            error_body = body.decode('utf-8', errors='replace')[:1000]
            logger.error(f"HTTP error {status}: {error_body}")
            raise RuntimeError(f"HTTP {status} for {url}: {error_body}")
        
        response_data = parse_json_bytes(body)
        trade_count = len(response_data.get("trades", []))
        logger.debug(f"Parsed response: {trade_count} trades, cursor={'present' if response_data.get('cursor') else 'none'}")
        
        return response_data
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise RuntimeError(f"Failed to fetch trades from {url}: {e}") from e


def fetch_all_trades_for_ticker(
    api_key_id: str,
    private_key_pem: bytes,
    ticker: str,
    limit: int = 1000,
    min_ts: int | None = None,
    max_ts: int | None = None,
    pages_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch trades for a ticker within a time window, handling pagination.
    
    Args:
        min_ts: Minimum Unix timestamp (seconds) - only fetch trades after this time
        max_ts: Maximum Unix timestamp (seconds) - only fetch trades before this time
        pages_dir: Optional directory to save individual page responses for verification
    
    Returns:
        Tuple of (list of trades, stats dict) where stats includes:
        - total_trades: Number of trades after filtering
        - total_trades_received: Total trades received from API
        - total_trades_filtered: Trades filtered out by time window
        - total_volume_dollars: Total volume in dollars
        - total_pages: Number of pages fetched
        - pages_saved: List of page file paths saved
    """
    time_window_str = ""
    if min_ts and max_ts:
        min_dt = datetime.fromtimestamp(min_ts, tz=timezone.utc)
        max_dt = datetime.fromtimestamp(max_ts, tz=timezone.utc)
        time_window_str = f" (window: {min_dt.strftime('%H:%M:%S')} - {max_dt.strftime('%H:%M:%S')} UTC)"
    
    logger.info(f"  📥 Starting paginated fetch for ticker: {ticker}{time_window_str}")
    sys.stdout.flush()
    all_trades: list[dict[str, Any]] = []
    cursor: str | None = None
    page_num = 0
    total_start_time = time.time()
    
    # Stats tracking
    total_volume_dollars = 0.0
    total_trades_received = 0
    total_trades_filtered = 0
    pages_saved = []
    
    # Create pages directory if provided
    if pages_dir:
        pages_dir.mkdir(parents=True, exist_ok=True)
    
    while True:
        page_num += 1
        page_start_time = time.time()
        
        try:
            logger.info(f"    Page {page_num}: Fetching... (cursor: {'present' if cursor else 'none'})")
            sys.stdout.flush()
            
            response = fetch_trades_with_auth(
                api_key_id,
                private_key_pem,
                ticker=ticker,
                limit=limit,
                cursor=cursor,
                min_ts=min_ts,
                max_ts=max_ts,
            )
            
            trades = response.get("trades", [])
            total_trades_received += len(trades)
            logger.info(f"    Page {page_num}: Received {len(trades)} trades")
            sys.stdout.flush()
            
            # Save raw page response if pages_dir provided
            if pages_dir and response:
                page_file = pages_dir / f"page_{page_num:05d}.json"
                page_data = {
                    "page_num": page_num,
                    "ticker": ticker,
                    "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                    "cursor": response.get("cursor"),
                    "trades_count": len(trades),
                    "min_ts": min_ts,
                    "max_ts": max_ts,
                    "raw_response": response,  # Store full response
                }
                page_file.write_text(json.dumps(page_data, indent=2, default=str), encoding="utf-8")
                pages_saved.append(str(page_file))
                logger.debug(f"    Saved page response: {page_file}")
            
            if trades:
                # Client-side filtering as backup (API filter may not work correctly)
                # Filter trades to only include those within the time window
                filtered_trades = []
                page_volume = 0.0
                
                if min_ts is not None or max_ts is not None:
                    for trade in trades:
                        # Calculate volume: price * count (in dollars)
                        trade_count = trade.get("count", 0)
                        trade_price = trade.get("price", 0.0)
                        trade_volume = trade_count * trade_price
                        page_volume += trade_volume
                        
                        trade_ts_str = trade.get("created_time", "")
                        if trade_ts_str:
                            try:
                                trade_dt = datetime.fromisoformat(trade_ts_str.replace("Z", "+00:00"))
                                trade_ts = int(trade_dt.timestamp())
                                
                                # Check if trade is within window
                                in_window = True
                                if min_ts is not None and trade_ts < min_ts:
                                    in_window = False
                                if max_ts is not None and trade_ts > max_ts:
                                    in_window = False
                                
                                if in_window:
                                    filtered_trades.append(trade)
                                else:
                                    total_trades_filtered += 1
                            except (ValueError, TypeError) as e:
                                logger.debug(f"      Could not parse trade timestamp: {trade_ts_str}: {e}")
                                # Include trade if we can't parse timestamp (shouldn't happen)
                                filtered_trades.append(trade)
                        else:
                            # Include trades without timestamp (shouldn't happen)
                            filtered_trades.append(trade)
                    
                    if len(filtered_trades) < len(trades):
                        logger.debug(f"    Filtered {len(trades) - len(filtered_trades)} trades outside time window")
                else:
                    # No time window, include all trades and calculate volume
                    filtered_trades = trades
                    for trade in trades:
                        trade_count = trade.get("count", 0)
                        trade_price = trade.get("price", 0.0)
                        page_volume += trade_count * trade_price
                
                total_volume_dollars += page_volume
                all_trades.extend(filtered_trades)
                logger.info(f"    Total trades so far: {len(all_trades):,} (after filtering) | Page volume: ${page_volume:,.2f}")
                sys.stdout.flush()
            
            new_cursor = response.get("cursor")
            
            # Check if cursor changed (pagination is working)
            if cursor and new_cursor and cursor == new_cursor:
                logger.warning(f"    ⚠️  Cursor unchanged! Previous: {cursor[:30]}... | New: {new_cursor[:30]}...")
                logger.warning(f"    ⚠️  This may indicate pagination issue - API returned same cursor")
                # Continue anyway in case API is working but cursor format is stable
            
            cursor = new_cursor
            if not cursor:
                logger.info(f"    ✓ Pagination complete (no more pages)")
                sys.stdout.flush()
                break
            
            logger.info(f"    → More pages available, continuing... (cursor: {cursor[:30]}...)")
            sys.stdout.flush()
            
            # Rate limiting
            sleep_time = 0.3
            time.sleep(sleep_time)
            
            page_elapsed = time.time() - page_start_time
            logger.info(f"    Page {page_num} completed in {page_elapsed:.2f}s")
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"    ✗ Error fetching page {page_num} for {ticker}: {e}", exc_info=True)
            sys.stdout.flush()
            sys.stderr.flush()
            break
    
    total_elapsed = time.time() - total_start_time
    if total_elapsed > 0:
        rate = len(all_trades) / total_elapsed
    else:
        rate = 0
    
    # Calculate final stats
    stats = {
        "total_trades": len(all_trades),
        "total_trades_received": total_trades_received,
        "total_trades_filtered": total_trades_filtered,
        "total_volume_dollars": total_volume_dollars,
        "total_pages": page_num,
        "fetch_time_seconds": total_elapsed,
        "trades_per_second": rate,
        "pages_saved": pages_saved,
    }
    
    logger.info(f"  ✓ Completed: {len(all_trades):,} total trades in {total_elapsed:.2f}s ({rate:.1f} trades/sec)")
    logger.info(f"  📊 Volume: ${total_volume_dollars:,.2f} | Received: {total_trades_received:,} | Filtered: {total_trades_filtered:,}")
    sys.stdout.flush()
    
    return all_trades, stats


def get_completed_games_with_kalshi_markets(dsn: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Query database for completed games from 2025-26 season with Kalshi markets.
    
    Uses ESPN data (espn.scoreboard_games) as the source of truth, matching Kalshi markets
    via espn_event_id. This matches how the webapp queries games.
    """
    logger.info("Querying database for completed games with Kalshi markets...")
    
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Query ESPN scoreboard_games joined with Kalshi markets via espn_event_id
            # This matches how the webapp queries games - ESPN is the source of truth
            logger.debug("Querying ESPN scoreboard_games joined with Kalshi markets...")
            
            query = """
                SELECT DISTINCT
                    sg.event_id as game_id,
                    sg.event_date as game_time_utc,
                    '2025-26' as season,
                    km.ticker,
                    km.event_ticker,
                    km.status as market_status
                FROM espn.scoreboard_games sg
                JOIN kalshi.markets km ON sg.event_id = km.espn_event_id
                WHERE km.event_ticker LIKE 'KXNBAGAME-25%%'
                  AND km.status IN ('finalized', 'closed', 'open', 'active')
                  AND sg.event_date < NOW()
                ORDER BY sg.event_date DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                logger.debug(f"Adding LIMIT {limit} to query")
            
            cur.execute(query)
            rows = cur.fetchall()
            logger.info(f"Found {len(rows)} Kalshi markets matched to ESPN games")
            
            markets = [
                {
                    "game_id": row[0],
                    "game_time_utc": row[1],
                    "season": row[2],
                    "ticker": row[3],
                    "event_ticker": row[4],
                    "market_status": row[5],
                }
                for row in rows
            ]
            
            # Count unique games (events)
            unique_events = set(m["event_ticker"] for m in markets if m["event_ticker"])
            logger.info(f"  → {len(markets)} markets across {len(unique_events)} unique games")
            logger.debug(f"Returning {len(markets)} markets from ESPN + Kalshi join")
            return markets


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch Kalshi trade data for completed NBA games from 2025-26 season.")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--limit", type=int, default=None, help="Limit number of games (for testing). If not set, fetches all.")
    p.add_argument("--out-dir", default="data/raw/kalshi/trades", help="Output directory for trade data.")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
    
    logger.info("=" * 70)
    logger.info("Kalshi Trade Data Fetcher - Completed Games 2025-26 Season")
    logger.info("=" * 70)
    
    dsn = get_dsn(args.dsn)
    logger.debug(f"Database DSN: {dsn[:20]}...")
    
    limit_str = f" (limit: {args.limit})" if args.limit else " (all games)"
    logger.info(f"Fetching trade data for completed games from 2025-26 season{limit_str}...")
    
    # Get completed games with Kalshi markets
    query_start = time.time()
    games = get_completed_games_with_kalshi_markets(dsn, limit=args.limit)
    query_elapsed = time.time() - query_start
    
    logger.info(f"Database query completed in {query_elapsed:.2f}s")
    
    if not games:
        logger.warning("No completed games with Kalshi markets found.")
        return 0
    
    # Note: 'games' variable actually contains MARKETS (one per team per game)
    # Each NBA game has 2 markets (one for each team)
    unique_events = set(g["event_ticker"] for g in games if g["event_ticker"])
    logger.info(f"Found {len(games)} Kalshi markets across {len(unique_events)} unique games")
    logger.debug(f"Event tickers: {sorted(unique_events)[:10]}...")
    
    # Load credentials
    logger.info("Loading API credentials...")
    api_key_id, private_key_pem = load_kalshi_credentials()
    
    # Create output directory
    out_dir = Path(args.out_dir)
    fetch_timestamp = utc_now_iso_compact()
    session_dir = out_dir / f"fetch_{fetch_timestamp}"
    logger.info(f"Creating output directory: {session_dir}")
    session_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Output directory created: {session_dir}")
    
    # Fetch trades for each market
    all_results: list[dict[str, Any]] = []
    total_start_time = time.time()
    successful_count = 0
    skipped_count = 0
    error_count = 0
    
    logger.info("=" * 70)
    logger.info(f"Starting trade fetch for {len(games)} markets ({len(unique_events)} unique games)...")
    logger.info("=" * 70)
    
    for i, game in enumerate(games, 1):
        ticker = game["ticker"]
        game_id = game["game_id"]
        event_ticker = game["event_ticker"]
        market_status = game["market_status"]
        
        # Parse ticker to show readable game info
        import re
        game_info = ""
        match = re.match(r'KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})-([A-Z]{3})', ticker)
        if match:
            yy, mmm, dd, away, home, team = match.groups()
            game_info = f"{away} @ {home} ({mmm} {dd}, 20{yy}) - Betting on {team}"
        
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"📊 MARKET [{i}/{len(games)}]: {ticker}")
        if game_info:
            logger.info(f"   📍 {game_info}")
        logger.info(f"   Event: {event_ticker}")
        logger.info(f"   Game ID: {game_id if game_id else 'N/A (not matched)'}")
        logger.info(f"   Market Status: {market_status}")
        logger.info("=" * 70)
        sys.stdout.flush()  # Force flush for real-time output
        
        # Check if we already have trade data for this ticker in ANY previous fetch session
        # Look in all subdirectories of the trades folder
        existing_file = None
        for prev_session_dir in out_dir.glob("fetch_*"):
            if prev_session_dir.is_dir():
                check_file = prev_session_dir / f"{ticker.replace('/', '_')}.json"
                if check_file.exists():
                    existing_file = check_file
                    break
        
        if existing_file:
            skipped_count += 1
            logger.info(f"  ⏭️  SKIPPING: Trade data already exists at {existing_file}")
            logger.info(f"     File size: {existing_file.stat().st_size:,} bytes")
            logger.info(f"     Session: {existing_file.parent.name}")
            logger.info(f"  📊 Progress: [{i}/{len(games)}] | ✓ Success: {successful_count} | ⏭️  Skipped: {skipped_count} | ✗ Errors: {error_count}")
            sys.stdout.flush()
            
            # Still add to results but mark as skipped
            all_results.append({
                "ticker": ticker,
                "game_id": game_id,
                "event_ticker": event_ticker,
                "trade_count": 0,
                "status": "skipped",
                "reason": "file_already_exists",
                "existing_file": str(existing_file),
                "total_volume_dollars": 0.0,
            })
            continue
        
        ticker_file = session_dir / f"{ticker.replace('/', '_')}.json"
        
        try:
            # Calculate in-game time window using ESPN data (matches webapp logic)
            # Game start = event_date from espn.scoreboard_games
            # Game duration = MAX(last_modified_utc) - MIN(last_modified_utc) from ESPN probabilities
            # Game window = event_date to event_date + duration
            min_ts = None
            max_ts = None
            
            if game["game_time_utc"] and game_id:
                game_start = game["game_time_utc"]
                
                # Handle different types: datetime object, string, or None
                if isinstance(game_start, datetime):
                    # Already a datetime object from psycopg
                    if game_start.tzinfo is None:
                        # Assume UTC if no timezone
                        game_start = game_start.replace(tzinfo=timezone.utc)
                    else:
                        # Convert to UTC
                        game_start = game_start.astimezone(timezone.utc)
                elif isinstance(game_start, str):
                    from scripts.lib._db_lib import parse_iso8601_z
                    game_start = parse_iso8601_z(game_start)
                
                if game_start and isinstance(game_start, datetime):
                    # Calculate actual game duration from ESPN data (matches webapp)
                    # Query ESPN probabilities to get MIN and MAX last_modified_utc
                    with psycopg.connect(dsn) as conn:
                        with conn.cursor() as dur_cur:
                            duration_query = """
                                SELECT 
                                    MIN(p.last_modified_utc) as first_record,
                                    MAX(p.last_modified_utc) as last_record,
                                    EXTRACT(EPOCH FROM (MAX(p.last_modified_utc) - MIN(p.last_modified_utc)))::INTEGER as duration_seconds
                                FROM espn.probabilities_raw_items p
                                WHERE p.game_id = %s
                            """
                            dur_cur.execute(duration_query, (game_id,))
                            dur_row = dur_cur.fetchone()
                            
                            if dur_row and dur_row[2] is not None:
                                duration_seconds = int(dur_row[2])
                                # Add 15 min buffer before and after (like webapp does for safety)
                                buffer_seconds = 15 * 60
                                game_start_ts = int(game_start.timestamp()) - buffer_seconds
                                game_end_ts = int(game_start.timestamp()) + duration_seconds + buffer_seconds
                                
                                min_ts = game_start_ts
                                max_ts = game_end_ts
                                
                                game_start_dt = datetime.fromtimestamp(game_start_ts, tz=timezone.utc)
                                game_end_dt = datetime.fromtimestamp(game_end_ts, tz=timezone.utc)
                                logger.info(f"  🎮 Game window: {game_start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {game_end_dt.strftime('%H:%M:%S')} UTC")
                                logger.info(f"  🎮 Duration: {duration_seconds / 60:.1f} minutes (from ESPN data)")
                                logger.info(f"  🎮 Time window timestamps: {min_ts} to {max_ts}")
                                sys.stdout.flush()
                            else:
                                # Fallback: use fixed 3.5 hour window if no ESPN duration data
                                logger.warning(f"  ⚠️  No ESPN duration data found, using fixed 3.5h window")
                                game_start_ts = int(game_start.timestamp()) - (15 * 60)  # 15 min before
                                game_end_ts = int(game_start.timestamp()) + (3 * 60 * 60) + (15 * 60)  # 3h15m after
                                min_ts = game_start_ts
                                max_ts = game_end_ts
                                sys.stdout.flush()
                else:
                    logger.warning(f"  ⚠️  Could not parse game_time_utc: {game['game_time_utc']} (type: {type(game['game_time_utc'])}), fetching all trades")
                    sys.stdout.flush()
            else:
                logger.warning(f"  ⚠️  No game_time_utc or game_id available, fetching all trades")
                sys.stdout.flush()
            
            # Create ticker-specific directory for pages
            ticker_safe = ticker.replace("/", "_")
            ticker_pages_dir = session_dir / ticker_safe / "pages"
            
            market_start_time = time.time()
            trades, fetch_stats = fetch_all_trades_for_ticker(
                api_key_id, 
                private_key_pem, 
                ticker,
                min_ts=min_ts,
                max_ts=max_ts,
                pages_dir=ticker_pages_dir,
            )
            market_elapsed = time.time() - market_start_time
            
            successful_count += 1
            
            # Log validation info
            volume = fetch_stats.get("total_volume_dollars", 0.0)
            logger.info(f"  ✓ Successfully fetched {len(trades)} in-game trades in {market_elapsed:.2f}s")
            logger.info(f"  💰 Total Volume: ${volume:,.2f} | Pages: {fetch_stats.get('total_pages', 0)}")
            if fetch_stats.get("total_trades_filtered", 0) > 0:
                logger.info(f"  ⚠️  Filtered {fetch_stats['total_trades_filtered']:,} trades outside time window")
            logger.info(f"  📊 Progress: [{i}/{len(games)}] | ✓ Success: {successful_count} | ⏭️  Skipped: {skipped_count} | ✗ Errors: {error_count}")
            
            # Calculate ETA
            if successful_count > 0:
                elapsed_total = time.time() - total_start_time
                avg_time_per_market = elapsed_total / (successful_count + skipped_count + error_count)
                remaining_markets = len(games) - i
                eta_seconds = avg_time_per_market * remaining_markets
                eta_minutes = eta_seconds / 60
                logger.info(f"  ⏱️  ETA: ~{eta_minutes:.1f} minutes remaining ({remaining_markets} markets left)")
            
            sys.stdout.flush()
            
            # Store trades for this ticker (aggregated)
            ticker_data = {
                "fetch_timestamp": fetch_timestamp,
                "ticker": ticker,
                "event_ticker": event_ticker,
                "game_id": game_id,
                "game_time_utc": game["game_time_utc"].isoformat() if game["game_time_utc"] else None,
                "market_status": game["market_status"],
                "filter_type": "in_game_only",
                "time_window_start_ts": min_ts,
                "time_window_end_ts": max_ts,
                "total_trades": len(trades),
                "total_volume_dollars": fetch_stats.get("total_volume_dollars", 0.0),
                "fetch_stats": fetch_stats,
                "trades": trades,
            }
            
            # Save aggregated file
            ticker_file = session_dir / f"{ticker_safe}.json"
            logger.debug(f"  Writing to file: {ticker_file}")
            
            file_start = time.time()
            ticker_file.write_text(json.dumps(ticker_data, indent=2, default=str), encoding="utf-8")
            file_elapsed = time.time() - file_start
            
            file_size = ticker_file.stat().st_size
            logger.info(f"  ✓ File written: {file_size:,} bytes in {file_elapsed:.2f}s")
            sys.stdout.flush()
            
            # Create manifest
            manifest_file = ticker_file.with_suffix(ticker_file.suffix + ".manifest.json")
            body_bytes = json.dumps(ticker_data, indent=2, default=str).encode("utf-8")
            sha256_hex = hashlib.sha256(body_bytes).hexdigest()
            
            manifest = {
                "source_type": "kalshi_trades",
                "source_key": ticker,
                "path": str(ticker_file),
                "fetched_at_utc": fetch_timestamp,
                "http_status": 200,
                "sha256_hex": sha256_hex,
                "byte_size": len(body_bytes),
            }
            manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            logger.debug(f"  Manifest written: {manifest_file}")
            
            all_results.append({
                "ticker": ticker,
                "game_id": game_id,
                "event_ticker": event_ticker,
                "trade_count": len(trades),
                "total_volume_dollars": fetch_stats.get("total_volume_dollars", 0.0),
                "total_pages": fetch_stats.get("total_pages", 0),
                "file_size_bytes": file_size,
                "file": str(ticker_file),
                "pages_dir": str(ticker_pages_dir) if ticker_pages_dir.exists() else None,
                "fetch_time_seconds": market_elapsed,
            })
            
            # Rate limiting between markets
            sleep_time = 0.5
            logger.info(f"  ⏳ Rate limiting: sleeping {sleep_time}s before next market...")
            sys.stdout.flush()
            time.sleep(sleep_time)
            
        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ ERROR: Failed to fetch trades for {ticker}: {e}", exc_info=True)
            logger.info(f"  📊 Progress: [{i}/{len(games)}] | ✓ Success: {successful_count} | ⏭️  Skipped: {skipped_count} | ✗ Errors: {error_count}")
            sys.stdout.flush()
            sys.stderr.flush()
            all_results.append({
                "ticker": ticker,
                "game_id": game_id,
                "event_ticker": event_ticker,
                "trade_count": 0,
                "total_volume_dollars": 0.0,
                "status": "error",
                "error": str(e),
            })
    
    total_elapsed = time.time() - total_start_time
    
    # Save summary with validation stats
    total_volume = sum(r.get("total_volume_dollars", 0.0) for r in all_results)
    total_pages = sum(r.get("total_pages", 0) for r in all_results)
    
    summary_file = session_dir / "summary.json"
    summary = {
        "fetch_timestamp": fetch_timestamp,
        "total_markets": len(games),
        "unique_events": len(unique_events),
        "total_trades": sum(r.get("trade_count", 0) for r in all_results),
        "total_volume_dollars": total_volume,
        "total_pages_fetched": total_pages,
        "successful_fetches": len([r for r in all_results if r.get("trade_count", 0) > 0]),
        "failed_fetches": len([r for r in all_results if "error" in r]),
        "skipped_fetches": len([r for r in all_results if r.get("status") == "skipped"]),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "validation": {
            "avg_trades_per_game": round(sum(r.get("trade_count", 0) for r in all_results) / max(len([r for r in all_results if r.get("trade_count", 0) > 0]), 1), 2),
            "avg_volume_per_game": round(total_volume / max(len([r for r in all_results if r.get("total_volume_dollars", 0) > 0]), 1), 2),
            "avg_pages_per_game": round(total_pages / max(len([r for r in all_results if r.get("total_pages", 0) > 0]), 1), 2),
        },
        "results": all_results,
    }
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("Saving summary...")
    summary_file.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    logger.debug(f"Summary written: {summary_file}")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("=== FETCH COMPLETE ===")
    logger.info("=" * 70)
    logger.info(f"Total markets processed: {len(games)}")
    logger.info(f"Unique games (events): {len(unique_events)}")
    logger.info(f"✓ Successful fetches: {successful_count}")
    logger.info(f"⏭️  Skipped (already exists): {skipped_count}")
    logger.info(f"✗ Failed fetches: {error_count}")
    logger.info(f"Total trades fetched: {summary['total_trades']:,}")
    logger.info(f"Total elapsed time: {total_elapsed:.2f}s ({total_elapsed/60:.1f} minutes)")
    if successful_count + skipped_count + error_count > 0:
        logger.info(f"Average time per market: {total_elapsed/(successful_count + skipped_count + error_count):.2f}s")
    logger.info(f"Output directory: {session_dir}")
    logger.info(f"Summary file: {summary_file}")
    logger.info("=" * 70)
    
    # Print data structure info
    if all_results and any(r.get("trade_count", 0) > 0 for r in all_results):
        logger.info("")
        logger.info("=== TRADE DATA STRUCTURE ===")
        # Find first result with trades
        first_with_trades = next((r for r in all_results if r.get("trade_count", 0) > 0), None)
        if first_with_trades:
            ticker_file = Path(first_with_trades["file"])
            if ticker_file.exists():
                data = json.loads(ticker_file.read_text(encoding="utf-8"))
                if data.get("trades") and len(data["trades"]) > 0:
                    logger.info(f"\nExample trade from {first_with_trades['ticker']}:")
                    logger.info(json.dumps(data["trades"][0], indent=2))
                    logger.info(f"\nTrade fields: {list(data['trades'][0].keys())}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

