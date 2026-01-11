#!/usr/bin/env python3
"""
Export derived game state timeline rows for modeling (baseline: score diff + time remaining).

Outputs CSV for simplicity and portability.

Usage:
  python scripts/export_game_state.py --dsn "$DATABASE_URL" --game-id 0022400196 --out data/exports/game_state_0022400196.csv

Or export all rows for a list of game ids:
  python scripts/export_game_state.py --dsn "$DATABASE_URL" --game-id 0022400196 --game-id 0012300001 --out data/exports/game_state_sample.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export derived.game_state_by_event to CSV.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", required=True, help="Game ID (can be repeated).")
    p.add_argument("--out", required=True, help="Output CSV path.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dsn:
        raise SystemExit("Missing --dsn and DATABASE_URL is not set.")

    game_ids = list(dict.fromkeys(args.game_id))  # preserve order, de-dupe
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(args.dsn) as conn, out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "game_id",
                "order_number",
                "period",
                "clock",
                "seconds_remaining_period",
                "seconds_remaining_regulation",
                "seconds_elapsed_game",
                "seconds_remaining_game",
                "score_home",
                "score_away",
                "score_diff_home",
                "is_overtime",
            ]
        )

        for gid in game_ids:
            cur = conn.execute(
                """
                SELECT
                  game_id, order_number, period, clock,
                  seconds_remaining_period, seconds_remaining_regulation,
                  seconds_elapsed_game, seconds_remaining_game,
                  score_home, score_away, score_diff_home, is_overtime
                FROM derived.game_state_by_event
                WHERE game_id=%s
                ORDER BY order_number
                """,
                (gid,),
            )
            for row in cur:
                w.writerow(row)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


