#!/usr/bin/env python3
"""
Load Kalshi trade data from JSON files into PostgreSQL.

Design Pattern: Idempotent Upsert with Provenance Tracking
- Uses source_files for provenance tracking (deduplication by sha256)
- Inserts individual trade records with all raw fields preserved
- Links to kalshi.markets via ticker

Algorithm: Single-pass linear scan O(n) where n = number of trades
Big O: O(n) time, O(n) space for the trades batch

Idempotency:
- Upserts source_files by (source_type, source_key, sha256_hex)
- Inserts trades with ON CONFLICT DO NOTHING (trade_id is unique)
- Safe to re-run without duplicating data

Usage:
  python scripts/load_kalshi_trades.py \\
    --trades-dir data/raw/kalshi/trades \\
    --dsn "$DATABASE_URL"

Pros:
- Full historical data preserved for replay/reprocessing
- Matches existing codebase patterns
- Idempotent: safe to re-run without duplicating data
- All raw fields preserved exactly as received

Cons:
- Storage grows with trade volume (acceptable for analytics use case)
- Requires processing all JSON files (can be slow for large datasets)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import (
    connect,
    finish_ingestion_run_failed,
    finish_ingestion_run_success,
    get_dsn,
    now_utc,
    parse_iso8601_z,
    start_ingestion_run,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def sha256_hex_bytes(data: bytes) -> str:
    """Compute SHA256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def load_trades_file(
    conn: Any,
    trades_file: Path,
    source_type: str = "kalshi_trades",
) -> tuple[int, int]:
    """
    Load trades from a single JSON file.
    
    Returns:
        Tuple of (trades_inserted, trades_skipped)
    """
    logger.info(f"Loading trades from: {trades_file}")
    
    # Read file
    body_bytes = trades_file.read_bytes()
    sha256_hex = sha256_hex_bytes(body_bytes)
    
    # Parse JSON
    try:
        trades_data = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return 0, 0
    
    # Extract metadata
    ticker = trades_data.get("ticker", "")
    event_ticker = trades_data.get("event_ticker", "")
    fetch_timestamp_str = trades_data.get("fetch_timestamp", "")
    time_window_start_ts = trades_data.get("time_window_start_ts")
    time_window_end_ts = trades_data.get("time_window_end_ts")
    
    # Parse fetch timestamp
    fetch_timestamp = None
    if fetch_timestamp_str:
        try:
            fetch_timestamp = parse_iso8601_z(fetch_timestamp_str)
        except Exception as e:
            logger.warning(f"Could not parse fetch_timestamp: {e}")
    
    # Get trades array from ticker-level aggregated files (trades at root level)
    # Note: Page files are skipped - they're duplicates stored in raw_response.trades
    trades = trades_data.get("trades", [])
    
    if not trades:
        logger.warning(f"No trades found in file: {trades_file}")
        return 0, 0
    
    logger.info(f"Found {len(trades)} trades in file")
    
    # Upsert source_file (for provenance tracking)
    source_key = f"{ticker}:{fetch_timestamp_str}" if ticker and fetch_timestamp_str else str(trades_file)
    
    source_file_row = conn.execute(
        """
        INSERT INTO source_files (
            source_type, source_key, path, fetched_at, http_status,
            sha256_hex, byte_size
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_type, source_key, sha256_hex) DO UPDATE SET
            path = EXCLUDED.path,
            fetched_at = EXCLUDED.fetched_at
        RETURNING source_file_id
        """,
        (
            source_type,
            source_key,
            str(trades_file),
            fetch_timestamp or datetime.now(timezone.utc),
            200,
            sha256_hex,
            len(body_bytes),
        ),
    ).fetchone()
    
    source_file_id = int(source_file_row[0]) if source_file_row else None
    
    # Insert trades (with ON CONFLICT DO NOTHING for idempotency)
    trades_inserted = 0
    trades_skipped = 0
    
    for trade in trades:
        trade_id = trade.get("trade_id")
        if not trade_id:
            logger.warning(f"Skipping trade without trade_id: {trade}")
            trades_skipped += 1
            continue
        
        # Parse created_time
        created_time_str = trade.get("created_time", "")
        created_time = None
        if created_time_str:
            try:
                created_time = parse_iso8601_z(created_time_str)
            except Exception as e:
                logger.warning(f"Could not parse created_time '{created_time_str}': {e}")
                trades_skipped += 1
                continue
        
        if not created_time:
            logger.warning(f"Skipping trade without valid created_time: {trade_id}")
            trades_skipped += 1
            continue
        
        # Insert trade (all raw fields preserved)
        try:
            result = conn.execute(
                """
                INSERT INTO kalshi.trades (
                    trade_id,
                    source_file_id,
                    ticker,
                    event_ticker,
                    count,
                    created_time,
                    no_price,
                    no_price_dollars,
                    price,
                    taker_side,
                    yes_price,
                    yes_price_dollars,
                    fetch_timestamp,
                    time_window_start_ts,
                    time_window_end_ts
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id) DO NOTHING
                """,
                (
                    trade_id,
                    source_file_id,
                    ticker or trade.get("ticker", ""),
                    event_ticker,
                    trade.get("count"),
                    created_time,
                    trade.get("no_price"),
                    trade.get("no_price_dollars"),
                    trade.get("price"),
                    trade.get("taker_side", ""),
                    trade.get("yes_price"),
                    trade.get("yes_price_dollars"),
                    fetch_timestamp,
                    time_window_start_ts,
                    time_window_end_ts,
                ),
            )
            
            if result.rowcount > 0:
                trades_inserted += 1
            else:
                trades_skipped += 1  # Already exists
                
        except Exception as e:
            logger.error(f"Error inserting trade {trade_id}: {e}")
            trades_skipped += 1
    
    logger.info(f"Inserted {trades_inserted} trades, skipped {trades_skipped} (already exist)")
    return trades_inserted, trades_skipped


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load Kalshi trade data from JSON files into PostgreSQL"
    )
    parser.add_argument(
        "--trades-dir",
        type=str,
        required=True,
        help="Directory containing trade JSON files (will search recursively)",
    )
    parser.add_argument(
        "--dsn",
        type=str,
        required=True,
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of files to process (for testing)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=" * 70)
    logger.info("Kalshi Trade Data Loader")
    logger.info("=" * 70)
    
    dsn = get_dsn(args.dsn)
    logger.debug(f"Database DSN: {dsn[:20]}...")
    
    trades_dir = Path(args.trades_dir)
    if not trades_dir.exists():
        logger.error(f"Trades directory does not exist: {trades_dir}")
        return 1
    
    # Find all trade JSON files (excluding manifests, summaries, and page files)
    # Note: We only load ticker-level aggregated files, not page files (which are duplicates)
    trade_files = [
        f for f in trades_dir.rglob("*.json")
        if not f.name.endswith(".manifest.json") 
        and f.name != "summary.json"
        and "pages" not in f.parts  # Skip page files - they're duplicates of ticker-level files
    ]
    
    if not trade_files:
        logger.warning(f"No trade JSON files found in {trades_dir}")
        return 0
    
    logger.info(f"Found {len(trade_files)} trade files")
    
    if args.limit:
        trade_files = trade_files[:args.limit]
        logger.info(f"Limited to {len(trade_files)} files for testing")
    
    run_id: int | None = None
    
    try:
        with connect(dsn) as conn:
            # Start ingestion run
            target_key = f"trades_dir={trades_dir},files={len(trade_files)}"
            run = start_ingestion_run(
                conn,
                run_type="load_kalshi_trades",
                source_file_id=None,
                target_key=target_key,
            )
            run_id = run.ingest_run_id
            total_inserted = 0
            total_skipped = 0
            
            for i, trade_file in enumerate(trade_files, 1):
                logger.info(f"[{i}/{len(trade_files)}] Processing: {trade_file.name}")
                
                try:
                    inserted, skipped = load_trades_file(conn, trade_file)
                    total_inserted += inserted
                    total_skipped += skipped
                    
                    # Commit after each file for progress tracking
                    conn.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing {trade_file}: {e}", exc_info=True)
                    conn.rollback()
                    continue
            
            logger.info("=" * 70)
            logger.info("Load Complete")
            logger.info("=" * 70)
            logger.info(f"Total trades inserted: {total_inserted:,}")
            logger.info(f"Total trades skipped: {total_skipped:,}")
            logger.info(f"Total files processed: {len(trade_files)}")
            
            finish_ingestion_run_success(
                conn,
                ingest_run_id=run_id,
                rows_inserted=total_inserted,
                rows_updated=0,
                rows_deleted=0,
            )
            
            return 0
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if run_id is not None:
            try:
                with connect(dsn) as conn:
                    finish_ingestion_run_failed(conn, ingest_run_id=run_id, error_message=str(e))
            except Exception:
                pass  # Ignore errors in cleanup
        return 1


if __name__ == "__main__":
    sys.exit(main())

