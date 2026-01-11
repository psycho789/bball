#!/usr/bin/env python3
"""
Export derived.pbp_event_state to CSV.

By default requires one or more --game-id filters to avoid accidentally exporting
the entire table. Use --all to export everything.

Usage:
  ./.venv/bin/python scripts/export_pbp_event_state.py --dsn "$DATABASE_URL" \
    --game-id 0022400196 --out data/exports/pbp_event_state_0022400196.csv

Export all rows:
  ./.venv/bin/python scripts/export_pbp_event_state.py --dsn "$DATABASE_URL" \
    --all --out data/exports/pbp_event_state_all.csv

Exports include possession_side:
  - possession_side (0=home, 1=away, NULL=unknown)
Also includes:
  - home_score / away_score (scoreboard at that event)
  - current_winning_team (0=home leading, 1=away leading, NULL=tied/unknown)
  - final_winning_team (0=home won, 1=away won, NULL=tied/unknown)
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export derived.pbp_event_state to CSV.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", help="Game ID to export (can be repeated).")
    p.add_argument("--all", action="store_true", help="Export all rows (can be very large).")
    p.add_argument("--out", required=True, help="Output CSV path.")
    return p.parse_args()


def _dedupe_keep_order(xs: list[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    game_ids = _dedupe_keep_order(args.game_id or [])
    if args.all and game_ids:
        raise SystemExit("Pass either --all or --game-id, not both.")
    if not args.all and not game_ids:
        raise SystemExit("Provide at least one --game-id, or pass --all.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(dsn) as conn, out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "game_id",
                "event_id",
                "point_differential",
                "time_remaining",
                "possession_side",
                "home_score",
                "away_score",
                "current_winning_team",
                "final_winning_team",
            ]
        )

        if args.all:
            cur = conn.execute(
                """
                SELECT
                  game_id, event_id, point_differential, time_remaining,
                  possession_side, home_score, away_score, current_winning_team, final_winning_team
                FROM derived.pbp_event_state
                ORDER BY game_id, event_id
                """
            )
        else:
            cur = conn.execute(
                """
                SELECT
                  game_id, event_id, point_differential, time_remaining,
                  possession_side, home_score, away_score, current_winning_team, final_winning_team
                FROM derived.pbp_event_state
                WHERE game_id = ANY(%s)
                ORDER BY game_id, event_id
                """,
                (game_ids,),
            )

        for row in cur:
            w.writerow(row)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


