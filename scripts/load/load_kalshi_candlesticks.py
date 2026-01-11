#!/usr/bin/env python3
"""
Load Kalshi candlestick time-series data into PostgreSQL.

Design Pattern: Idempotent Time-Series Upsert
- Scans candlestick JSON files from a fetch directory
- Uses UPSERT (ON CONFLICT) for idempotent inserts by (ticker, period_ts, period_interval)

Algorithm: Linear scan O(n) where n = total candlesticks across all files
Big O: O(n) time complexity, O(1) space per batch

Usage:
  # Load all candlesticks from a fetch directory
  python scripts/load_kalshi_candlesticks.py \\
    --candlesticks-dir data/raw/kalshi/candlesticks/fetch_2025-12-23T0802Z \\
    --dsn "$DATABASE_URL"

  # Load a single candlestick file
  python scripts/load_kalshi_candlesticks.py \\
    --candlesticks-file data/raw/kalshi/candlesticks/.../candlesticks_KXNBAGAME_25DEC19CHICLE_CLE.json \\
    --dsn "$DATABASE_URL"

Pros:
- Idempotent: safe to re-run, updates existing records
- Handles both directory batch and single file modes
- Preserves full time-series for charting and analysis

Cons:
- Individual INSERTs (could be optimized with COPY for large batches)
- No manifest tracking (candlestick files don't have manifests)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import (
    connect,
    finish_ingestion_run_failed,
    finish_ingestion_run_success,
    get_dsn,
    start_ingestion_run,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load Kalshi candlestick data into Postgres.")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--candlesticks-dir", help="Directory containing candlestick JSON files")
    p.add_argument("--candlesticks-file", help="Single candlestick JSON file")
    return p.parse_args()


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ts_to_datetime(ts: int | None) -> datetime | None:
    """Convert Unix timestamp to datetime."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def find_candlestick_files(base_dir: Path) -> Iterator[Path]:
    """Recursively find all candlestick JSON files in a directory."""
    for path in base_dir.rglob("candlesticks_*.json"):
        yield path


def upsert_candlestick_source_file(conn: Any, path: Path) -> int:
    """Create a source_files record for a candlestick file."""
    sha256_hex = compute_file_hash(path)
    fetched_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    
    # Extract ticker from filename like "candlesticks_KXNBAGAME_25DEC19CHICLE_CLE.json"
    source_key = path.stem  # filename without extension
    
    sql = """
    INSERT INTO source_files(source_type, source_key, path, fetched_at, http_status, sha256_hex, byte_size)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_type, source_key, sha256_hex)
    DO UPDATE SET
      path = EXCLUDED.path,
      fetched_at = EXCLUDED.fetched_at,
      byte_size = EXCLUDED.byte_size
    RETURNING source_file_id
    """
    row = conn.execute(
        sql,
        (
            "kalshi_candlesticks",
            source_key,
            str(path),
            fetched_at,
            200,
            sha256_hex,
            path.stat().st_size,
        ),
    ).fetchone()
    return int(row[0])


def load_candlestick_file(conn: Any, path: Path, source_file_id: int | None) -> tuple[int, int]:
    """
    Load candlesticks from a single JSON file.
    Returns (inserted_count, updated_count).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    
    # Extract request info
    request = data.get("request", {})
    ticker = request.get("ticker", "")
    period_interval = request.get("period_interval", 1)  # minutes
    
    # Get response data
    response = data.get("response", {})
    response_data = response.get("data", {})
    candlesticks = response_data.get("candlesticks", [])
    
    if not ticker or not candlesticks:
        return 0, 0
    
    inserted = 0
    updated = 0
    
    for c in candlesticks:
        if not isinstance(c, dict):
            continue
        
        end_period_ts = c.get("end_period_ts")
        if end_period_ts is None:
            continue
        
        period_dt = ts_to_datetime(end_period_ts)
        
        # Extract price OHLC
        price = c.get("price", {})
        
        # Extract yes_bid OHLC
        yes_bid = c.get("yes_bid", {})
        
        # Extract yes_ask OHLC
        yes_ask = c.get("yes_ask", {})
        
        # Upsert candlestick
        result = conn.execute(
            """
            INSERT INTO kalshi.candlesticks(
                source_file_id, ticker, period_ts, period_interval_min,
                price_open, price_high, price_low, price_close, price_mean, price_previous,
                yes_bid_open, yes_bid_high, yes_bid_low, yes_bid_close,
                yes_ask_open, yes_ask_high, yes_ask_low, yes_ask_close,
                volume, open_interest
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (ticker, period_ts, period_interval_min)
            DO UPDATE SET
                source_file_id = COALESCE(EXCLUDED.source_file_id, kalshi.candlesticks.source_file_id),
                price_open = EXCLUDED.price_open,
                price_high = EXCLUDED.price_high,
                price_low = EXCLUDED.price_low,
                price_close = EXCLUDED.price_close,
                price_mean = EXCLUDED.price_mean,
                price_previous = EXCLUDED.price_previous,
                yes_bid_open = EXCLUDED.yes_bid_open,
                yes_bid_high = EXCLUDED.yes_bid_high,
                yes_bid_low = EXCLUDED.yes_bid_low,
                yes_bid_close = EXCLUDED.yes_bid_close,
                yes_ask_open = EXCLUDED.yes_ask_open,
                yes_ask_high = EXCLUDED.yes_ask_high,
                yes_ask_low = EXCLUDED.yes_ask_low,
                yes_ask_close = EXCLUDED.yes_ask_close,
                volume = EXCLUDED.volume,
                open_interest = EXCLUDED.open_interest
            RETURNING (xmax = 0) AS inserted
            """,
            (
                source_file_id,
                ticker,
                period_dt,
                period_interval,
                price.get("open"),
                price.get("high"),
                price.get("low"),
                price.get("close"),
                price.get("mean"),
                price.get("previous"),
                yes_bid.get("open"),
                yes_bid.get("high"),
                yes_bid.get("low"),
                yes_bid.get("close"),
                yes_ask.get("open"),
                yes_ask.get("high"),
                yes_ask.get("low"),
                yes_ask.get("close"),
                c.get("volume"),
                c.get("open_interest"),
            ),
        ).fetchone()
        
        if result and result[0]:
            inserted += 1
        else:
            updated += 1
    
    return inserted, updated


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    if not args.candlesticks_dir and not args.candlesticks_file:
        raise RuntimeError("Must specify either --candlesticks-dir or --candlesticks-file")

    # Collect files to process
    files_to_process: list[Path] = []
    
    if args.candlesticks_file:
        file_path = Path(args.candlesticks_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Candlesticks file not found: {file_path}")
        files_to_process.append(file_path)
    
    if args.candlesticks_dir:
        dir_path = Path(args.candlesticks_dir)
        if not dir_path.exists():
            raise FileNotFoundError(f"Candlesticks directory not found: {dir_path}")
        files_to_process.extend(find_candlestick_files(dir_path))

    if not files_to_process:
        print("No candlestick files found to process.")
        return 0

    total_inserted = 0
    total_updated = 0
    files_processed = 0

    with connect(dsn) as conn:
        run_id = None
        try:
            with conn.transaction():
                run = start_ingestion_run(
                    conn,
                    run_type="load_kalshi_candlesticks",
                    source_file_id=None,
                    target_key="kalshi_candlesticks",
                )
                run_id = run.ingest_run_id

                for file_path in files_to_process:
                    try:
                        source_file_id = upsert_candlestick_source_file(conn, file_path)
                        inserted, updated = load_candlestick_file(conn, file_path, source_file_id)
                        total_inserted += inserted
                        total_updated += updated
                        files_processed += 1
                        
                        if files_processed % 10 == 0:
                            print(f"  Processed {files_processed} files...")
                    except Exception as e:
                        print(f"Warning: Failed to process {file_path}: {e}")
                        continue

                finish_ingestion_run_success(
                    conn,
                    ingest_run_id=run_id,
                    rows_inserted=total_inserted,
                    rows_updated=total_updated,
                    rows_deleted=0,
                )

            print(f"Loaded Kalshi candlesticks: files={files_processed} inserted={total_inserted} updated={total_updated}")
            return 0

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                if run_id is not None:
                    finish_ingestion_run_failed(conn, ingest_run_id=run_id, error_message=str(e))
            except Exception:
                pass
            raise


if __name__ == "__main__":
    raise SystemExit(main())



