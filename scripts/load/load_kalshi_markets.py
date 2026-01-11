#!/usr/bin/env python3
"""
Load Kalshi NBA game markets snapshot into PostgreSQL.

Design Pattern: Idempotent Upsert with Snapshot-based Time Series
- Uses source_files for provenance tracking (deduplication by sha256)
- Creates snapshot record with full raw JSON payload
- Denormalizes markets into queryable rows

Algorithm: Single-pass linear scan O(n) where n = number of markets
Big O: O(n) time, O(n) space for the markets batch

Idempotency:
- Upserts source_files by (source_type, source_key, sha256_hex)
- Upserts kalshi_market_snapshots by unique (source_file_id)
- Rebuilds kalshi_markets for snapshot_id via delete+insert

Usage:
  python scripts/load_kalshi_markets.py \\
    --markets-file data/raw/kalshi/markets/fetch_2025-12-23T0747Z/all_markets.json \\
    --dsn "$DATABASE_URL"

Pros:
- Full historical data preserved for replay/reprocessing
- Matches existing codebase patterns
- Idempotent: safe to re-run without duplicating data

Cons:
- Requires generating manifest or deriving metadata from file
- Storage grows with each snapshot (acceptable for analytics use case)
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    parse_iso8601_z,
    start_ingestion_run,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load Kalshi markets snapshot JSON into Postgres.")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--markets-file", required=True, help="Path to all_markets.json")
    p.add_argument("--manifest-file", help="Optional path to manifest JSON (auto-generated if not provided)")
    return p.parse_args()


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_fetch_timestamp(s: str | None) -> datetime | None:
    """Parse fetch_timestamp like '2025-12-23T0747Z' or ISO8601."""
    if not s:
        return None
    # Try standard ISO first
    dt = parse_iso8601_z(s)
    if dt:
        return dt
    # Try compact format like "2025-12-23T0747Z"
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


def create_manifest_from_file(path: Path, markets_obj: dict[str, Any]) -> dict[str, Any]:
    """Generate manifest metadata from file when not provided."""
    fetch_ts = markets_obj.get("fetch_timestamp", "")
    series_ticker = markets_obj.get("series_ticker", "KXNBAGAME")
    
    # Parse the timestamp
    parsed_ts = parse_fetch_timestamp(fetch_ts)
    if parsed_ts:
        fetched_at_utc = parsed_ts.strftime("%Y%m%dT%H%M%SZ")
    else:
        # Fall back to file modification time
        fetched_at_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    return {
        "source_type": "kalshi_markets",
        "source_key": f"{series_ticker}_{fetch_ts}" if fetch_ts else series_ticker,
        "path": str(path),
        "fetched_at_utc": fetched_at_utc,
        "sha256_hex": compute_file_hash(path),
        "byte_size": path.stat().st_size,
        "http_status": 200,
    }


def upsert_kalshi_source_file(conn: Any, manifest: dict[str, Any]) -> int:
    """Insert/update a source_files row and return source_file_id."""
    from scripts.lib._db_lib import parse_iso8601_z

    fetched_at = parse_iso8601_z(str(manifest["fetched_at_utc"]))
    if fetched_at is None:
        try:
            fetched_at = datetime.strptime(str(manifest["fetched_at_utc"]), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except Exception as e:
            raise RuntimeError("manifest fetched_at_utc has unexpected format") from e

    sql = """
    INSERT INTO source_files(source_type, source_key, path, fetched_at, http_status, etag, last_modified, sha256_hex, byte_size)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (source_type, source_key, sha256_hex)
    DO UPDATE SET
      path = EXCLUDED.path,
      fetched_at = EXCLUDED.fetched_at,
      http_status = EXCLUDED.http_status,
      byte_size = EXCLUDED.byte_size
    RETURNING source_file_id
    """
    row = conn.execute(
        sql,
        (
            manifest["source_type"],
            manifest["source_key"],
            manifest["path"],
            fetched_at,
            manifest.get("http_status"),
            manifest.get("etag"),
            manifest.get("last_modified"),
            manifest["sha256_hex"],
            int(manifest["byte_size"]),
        ),
    ).fetchone()
    if not row:
        raise RuntimeError("failed to upsert source_files")
    return int(row[0])


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    markets_path = Path(args.markets_file)
    if not markets_path.exists():
        raise FileNotFoundError(f"Markets file not found: {markets_path}")

    # Load markets JSON
    markets_obj = json.loads(markets_path.read_text(encoding="utf-8"))
    if not isinstance(markets_obj, dict):
        raise RuntimeError("markets file must be a JSON object")
    
    markets_list = markets_obj.get("markets")
    if not isinstance(markets_list, list):
        raise RuntimeError("markets file missing top-level markets[]")

    # Load or generate manifest
    if args.manifest_file:
        manifest_path = Path(args.manifest_file)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = create_manifest_from_file(markets_path, markets_obj)

    # Extract metadata from markets object
    series_ticker = markets_obj.get("series_ticker", "KXNBAGAME")
    fetch_timestamp_str = markets_obj.get("fetch_timestamp", "")
    fetch_timestamp = parse_fetch_timestamp(fetch_timestamp_str)
    if not fetch_timestamp:
        fetch_timestamp = datetime.now(timezone.utc)
    total_markets = markets_obj.get("total_markets", len(markets_list))

    rows_inserted = 0
    rows_updated = 0
    rows_deleted = 0

    with connect(dsn) as conn:
        run_id = None
        try:
            with conn.transaction():
                source_file_id = upsert_kalshi_source_file(conn, manifest)
                run = start_ingestion_run(
                    conn, 
                    run_type="load_kalshi_markets", 
                    source_file_id=source_file_id, 
                    target_key=f"kalshi_{series_ticker}"
                )
                run_id = run.ingest_run_id

                # Create/update snapshot row (idempotent by source_file_id)
                # First, check if snapshot already exists to avoid sequence conflicts
                existing_snap = conn.execute(
                    "SELECT snapshot_id FROM kalshi.market_snapshots WHERE source_file_id = %s",
                    (source_file_id,)
                ).fetchone()
                
                if existing_snap:
                    # Update existing snapshot
                    snapshot_id = int(existing_snap[0])
                    conn.execute(
                        """
                        UPDATE kalshi.market_snapshots
                        SET series_ticker = %s,
                            fetch_timestamp = %s,
                            total_markets = %s,
                            raw_snapshot = %s
                        WHERE snapshot_id = %s
                        """,
                        (series_ticker, fetch_timestamp, total_markets, Jsonb(markets_obj), snapshot_id)
                    )
                else:
                    # Insert new snapshot
                    snap_row = conn.execute(
                        """
                        INSERT INTO kalshi.market_snapshots(source_file_id, series_ticker, fetch_timestamp, total_markets, raw_snapshot)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING snapshot_id
                        """,
                        (source_file_id, series_ticker, fetch_timestamp, total_markets, Jsonb(markets_obj)),
                    ).fetchone()
                    snapshot_id = int(snap_row[0])

                # Rebuild markets for this snapshot (delete existing, insert fresh)
                rows_deleted += conn.execute(
                    "DELETE FROM kalshi.markets WHERE snapshot_id=%s", 
                    (snapshot_id,)
                ).rowcount

                # Insert all markets
                for m in markets_list:
                    if not isinstance(m, dict):
                        continue
                    
                    ticker = m.get("ticker", "")
                    if not ticker:
                        continue

                    conn.execute(
                        """
                        INSERT INTO kalshi.markets(
                            snapshot_id, ticker, event_ticker,
                            title, subtitle, yes_sub_title, no_sub_title,
                            market_type, status, result,
                            last_price, yes_bid, yes_ask, no_bid, no_ask, previous_price,
                            volume, volume_24h, open_interest, liquidity,
                            open_time, close_time, expiration_time, expected_expiration_time, created_time,
                            rules_primary, rules_secondary, early_close_condition, can_close_early,
                            notional_value, tick_size
                        )
                        VALUES (
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s
                        )
                        """,
                        (
                            snapshot_id,
                            ticker,
                            m.get("event_ticker", ""),
                            m.get("title"),
                            m.get("subtitle"),
                            m.get("yes_sub_title"),
                            m.get("no_sub_title"),
                            m.get("market_type"),
                            m.get("status"),
                            m.get("result") or None,
                            m.get("last_price"),
                            m.get("yes_bid"),
                            m.get("yes_ask"),
                            m.get("no_bid"),
                            m.get("no_ask"),
                            m.get("previous_price"),
                            m.get("volume"),
                            m.get("volume_24h"),
                            m.get("open_interest"),
                            m.get("liquidity"),
                            parse_iso8601_z(m.get("open_time")),
                            parse_iso8601_z(m.get("close_time")),
                            parse_iso8601_z(m.get("expiration_time")),
                            parse_iso8601_z(m.get("expected_expiration_time")),
                            parse_iso8601_z(m.get("created_time")),
                            m.get("rules_primary"),
                            m.get("rules_secondary"),
                            m.get("early_close_condition"),
                            m.get("can_close_early"),
                            m.get("notional_value"),
                            m.get("tick_size"),
                        ),
                    )
                    rows_inserted += 1

                # Populate game_date and game_id for newly inserted markets
                conn.execute("""
                    UPDATE kalshi.markets
                    SET game_date = kalshi.parse_kalshi_game_date(event_ticker)
                    WHERE snapshot_id = %s AND game_date IS NULL
                """, (snapshot_id,))

                # Match to NBA games table (optional - for game_id)
                game_matches = conn.execute("""
                    WITH kalshi_parsed AS (
                        SELECT 
                            snapshot_id, ticker, event_ticker, game_date,
                            kalshi.parse_kalshi_team_codes(event_ticker) AS team_codes
                        FROM kalshi.markets
                        WHERE snapshot_id = %s AND game_date IS NOT NULL AND game_id IS NULL
                    ),
                    matches AS (
                        SELECT DISTINCT ON (kp.ticker)
                            kp.snapshot_id, kp.ticker, g.game_id
                        FROM kalshi_parsed kp
                        JOIN nba.games g ON (g.game_time_utc::date = kp.game_date)
                        JOIN nba.teams ht ON g.home_team_id = ht.team_id
                        JOIN nba.teams at ON g.away_team_id = at.team_id
                        WHERE kp.team_codes IS NOT NULL
                          AND (
                              (ht.team_tricode = kp.team_codes[1] AND at.team_tricode = kp.team_codes[2])
                              OR
                              (ht.team_tricode = kp.team_codes[2] AND at.team_tricode = kp.team_codes[1])
                          )
                    )
                    UPDATE kalshi.markets km
                    SET game_id = m.game_id
                    FROM matches m
                    WHERE km.snapshot_id = m.snapshot_id AND km.ticker = m.ticker
                    RETURNING km.ticker
                """, (snapshot_id,)).fetchall()
                games_matched = len(game_matches)

                # Match to ESPN games (REQUIRED - for espn_event_id)
                # Uses time-based matching: (expected_expiration_time - 3 hours) ≈ ESPN event_date
                # 30-minute tolerance handles schedule variations
                # Uses team codes from event_ticker for more reliable matching than display names
                # Normalizes team codes: GSW->GS, UTA->UTAH, NOP->NO to match ESPN abbreviations
                espn_matches = conn.execute("""
                    WITH kalshi_teams AS (
                        SELECT 
                            km.snapshot_id,
                            km.ticker,
                            km.expected_expiration_time,
                            km.event_ticker,
                            kalshi.parse_kalshi_team_codes(km.event_ticker) as team_codes
                        FROM kalshi.markets km
                        WHERE km.snapshot_id = %s
                          AND km.espn_event_id IS NULL
                          AND km.expected_expiration_time IS NOT NULL
                          AND km.event_ticker IS NOT NULL
                    ),
                    normalized_teams AS (
                        SELECT 
                            kt.*,
                            ARRAY[
                                CASE WHEN (kt.team_codes)[1] = 'GSW' THEN 'GS'
                                     WHEN (kt.team_codes)[1] = 'UTA' THEN 'UTAH'
                                     WHEN (kt.team_codes)[1] = 'NOP' THEN 'NO'
                                     ELSE (kt.team_codes)[1]
                                END,
                                CASE WHEN (kt.team_codes)[2] = 'GSW' THEN 'GS'
                                     WHEN (kt.team_codes)[2] = 'UTA' THEN 'UTAH'
                                     WHEN (kt.team_codes)[2] = 'NOP' THEN 'NO'
                                     ELSE (kt.team_codes)[2]
                                END
                            ] as normalized
                        FROM kalshi_teams kt
                    ),
                    espn_matches AS (
                        SELECT DISTINCT ON (nt.snapshot_id, nt.ticker)
                            nt.snapshot_id,
                            nt.ticker,
                            sg.event_id AS espn_event_id
                        FROM normalized_teams nt
                        JOIN espn.scoreboard_games sg 
                            ON ABS(EXTRACT(EPOCH FROM (
                                (nt.expected_expiration_time - INTERVAL '3 hours') - sg.event_date
                            ))) < 1800  -- within 30 minutes
                            AND nt.normalized IS NOT NULL
                            AND (
                                -- Match by team abbreviations (normalized to ESPN format)
                                (sg.home_team_abbrev = nt.normalized[1] AND sg.away_team_abbrev = nt.normalized[2])
                                OR (sg.home_team_abbrev = nt.normalized[2] AND sg.away_team_abbrev = nt.normalized[1])
                            )
                        ORDER BY nt.snapshot_id, nt.ticker, 
                                 ABS(EXTRACT(EPOCH FROM ((nt.expected_expiration_time - INTERVAL '3 hours') - sg.event_date)))
                    )
                    UPDATE kalshi.markets km
                    SET espn_event_id = em.espn_event_id
                    FROM espn_matches em
                    WHERE km.snapshot_id = em.snapshot_id
                      AND km.ticker = em.ticker
                    RETURNING km.ticker
                """, (snapshot_id,)).fetchall()
                espn_games_matched = len(espn_matches)

                finish_ingestion_run_success(
                    conn,
                    ingest_run_id=run_id,
                    rows_inserted=rows_inserted,
                    rows_updated=rows_updated,
                    rows_deleted=rows_deleted,
                )

            print(f"Loaded Kalshi markets snapshot: series={series_ticker} total={total_markets} inserted={rows_inserted} deleted={rows_deleted} nba_games_matched={games_matched} espn_games_matched={espn_games_matched}")
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

