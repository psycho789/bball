#!/usr/bin/env python3
"""
Load an archived odds_todaysGames snapshot (and its manifest) into PostgreSQL.

Idempotency:
- Upserts source_files by (source_type, source_key, sha256_hex)
- Upserts odds_snapshots by unique (source_file_id)
- Rebuilds odds_games/markets/books/outcomes for snapshot_id deterministically via delete+insert

Usage:
  python scripts/load_odds_snapshot.py \
    --odds-file data/raw/odds/odds_todaysGames_20251214T124632Z.json \
    --manifest-file data/raw/odds/odds_todaysGames_20251214T124632Z.json.manifest.json \
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
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
    read_manifest,
    start_ingestion_run,
    upsert_source_file,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load odds snapshot JSON into Postgres.")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--odds-file", required=True, help="Path to archived odds JSON")
    p.add_argument("--manifest-file", required=True, help="Path to manifest JSON (from fetcher)")
    return p.parse_args()


def _market_key(odds_type_id: Any, group_name: Any, name: Any) -> str:
    return f"{'' if odds_type_id is None else odds_type_id}:{group_name or ''}:{name or ''}"


def _to_decimal(s: Any) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(str(s))
    except (InvalidOperation, ValueError):
        return None


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    odds_path = Path(args.odds_file)
    manifest_path = Path(args.manifest_file)

    odds_obj = json.loads(odds_path.read_text(encoding="utf-8"))
    if not isinstance(odds_obj, dict):
        raise RuntimeError("odds file must be a JSON object")
    games = odds_obj.get("games")
    if not isinstance(games, list):
        raise RuntimeError("odds file missing top-level games[]")

    manifest = read_manifest(manifest_path)
    target_key = str(manifest.get("source_key") or "odds_today")

    rows_inserted = 0
    rows_updated = 0
    rows_deleted = 0

    with connect(dsn) as conn:
        run_id = None
        try:
            with conn.transaction():
                source_file_id = upsert_source_file(conn, manifest)
                run = start_ingestion_run(conn, run_type="load_odds_snapshot", source_file_id=source_file_id, target_key=target_key)
                run_id = run.ingest_run_id

                # Create/update snapshot row (idempotent by source_file_id)
                snap_row = conn.execute(
                    """
                    INSERT INTO odds_snapshots(source_file_id, fetched_at, raw_snapshot)
                    VALUES (%s, now(), %s)
                    ON CONFLICT (source_file_id) DO UPDATE
                      SET fetched_at=EXCLUDED.fetched_at, raw_snapshot=EXCLUDED.raw_snapshot
                    RETURNING snapshot_id
                    """,
                    (source_file_id, Jsonb(odds_obj)),
                ).fetchone()
                snapshot_id = int(snap_row[0])

                # Rebuild odds tables for this snapshot (cascade delete via odds_games)
                rows_deleted += conn.execute("DELETE FROM odds_games WHERE snapshot_id=%s", (snapshot_id,)).rowcount

                # Insert odds games + nested structures
                for g in games:
                    if not isinstance(g, dict):
                        continue
                    game_id = str(g.get("gameId") or "")
                    if not game_id:
                        continue

                    home_raw = g.get("homeTeamId")
                    away_raw = g.get("awayTeamId")
                    sr_match_id = g.get("srMatchId")
                    sr_id = g.get("sr_id")

                    # We can't guarantee teams dimension exists for these IDs (no tricode in odds feed),
                    # so store raw IDs and leave FK columns null.
                    conn.execute(
                        """
                        INSERT INTO odds_games(snapshot_id, game_id, home_team_id, away_team_id, sr_match_id, sr_id, home_team_id_raw, away_team_id_raw)
                        VALUES (%s,%s,NULL,NULL,%s,%s,%s,%s)
                        ON CONFLICT (snapshot_id, game_id) DO UPDATE SET
                          sr_match_id=EXCLUDED.sr_match_id,
                          sr_id=EXCLUDED.sr_id,
                          home_team_id_raw=EXCLUDED.home_team_id_raw,
                          away_team_id_raw=EXCLUDED.away_team_id_raw
                        """,
                        (snapshot_id, game_id, sr_match_id, sr_id, home_raw, away_raw),
                    )
                    rows_inserted += 1

                    markets = g.get("markets") or []
                    if not isinstance(markets, list):
                        continue

                    for m in markets:
                        if not isinstance(m, dict):
                            continue
                        odds_type_id = m.get("odds_type_id")
                        group_name = m.get("group_name")
                        name = m.get("name")
                        market_key = _market_key(odds_type_id, group_name, name)

                        conn.execute(
                            """
                            INSERT INTO odds_markets(snapshot_id, game_id, market_key, odds_type_id, group_name, name)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (snapshot_id, game_id, market_key) DO UPDATE SET
                              odds_type_id=EXCLUDED.odds_type_id,
                              group_name=EXCLUDED.group_name,
                              name=EXCLUDED.name
                            """,
                            (snapshot_id, game_id, market_key, odds_type_id, group_name, name),
                        )

                        books = m.get("books") or []
                        if not isinstance(books, list):
                            continue

                        for b in books:
                            if not isinstance(b, dict):
                                continue
                            book_id = str(b.get("id") or "")
                            if not book_id:
                                continue
                            book_name = b.get("name")
                            book_url = b.get("url")
                            country_code = b.get("countryCode")

                            conn.execute(
                                """
                                INSERT INTO odds_books(snapshot_id, game_id, market_key, book_id, book_name, book_url, country_code)
                                VALUES (%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (snapshot_id, game_id, market_key, book_id) DO UPDATE SET
                                  book_name=EXCLUDED.book_name,
                                  book_url=EXCLUDED.book_url,
                                  country_code=EXCLUDED.country_code
                                """,
                                (snapshot_id, game_id, market_key, book_id, book_name, book_url, country_code),
                            )

                            outcomes = b.get("outcomes") or []
                            if not isinstance(outcomes, list):
                                continue

                            for o in outcomes:
                                if not isinstance(o, dict):
                                    continue
                                outcome_type = str(o.get("type") or "")
                                odds_field_id = o.get("odds_field_id")
                                if not outcome_type or odds_field_id is None:
                                    continue
                                odds_raw = o.get("odds")
                                opening_raw = o.get("opening_odds")

                                conn.execute(
                                    """
                                    INSERT INTO odds_outcomes(
                                      snapshot_id, game_id, market_key, book_id, outcome_type, odds_field_id,
                                      odds, opening_odds, odds_trend, odds_raw, opening_odds_raw
                                    )
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                    ON CONFLICT (snapshot_id, game_id, market_key, book_id, outcome_type, odds_field_id)
                                    DO UPDATE SET
                                      odds=EXCLUDED.odds,
                                      opening_odds=EXCLUDED.opening_odds,
                                      odds_trend=EXCLUDED.odds_trend,
                                      odds_raw=EXCLUDED.odds_raw,
                                      opening_odds_raw=EXCLUDED.opening_odds_raw
                                    """,
                                    (
                                        snapshot_id,
                                        game_id,
                                        market_key,
                                        book_id,
                                        outcome_type,
                                        int(odds_field_id),
                                        _to_decimal(odds_raw),
                                        _to_decimal(opening_raw),
                                        o.get("odds_trend"),
                                        None if odds_raw is None else str(odds_raw),
                                        None if opening_raw is None else str(opening_raw),
                                    ),
                                )

                finish_ingestion_run_success(
                    conn,
                    ingest_run_id=run_id,
                    rows_inserted=rows_inserted,
                    rows_updated=rows_updated,
                    rows_deleted=rows_deleted,
                )

            print(f"Loaded odds snapshot games={len(games)} inserted={rows_inserted} deleted={rows_deleted}")
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


