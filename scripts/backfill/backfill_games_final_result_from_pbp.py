#!/usr/bin/env python3
"""
Backfill games.final_score_home / games.final_score_away / games.winner_team_id
from the end-of-period PBP event that ends the game.

Notes:
  - Some PBP feeds include trailing administrative events after the final horn that
    may have score_home/score_away = 0. We therefore prefer the last `period/end`
    event as the final score snapshot, and fall back to the last event if needed.
  - Idempotent by default: only fills NULL fields. Use --force to overwrite.

Usage:
  # Backfill a specific game:
  ./.venv/bin/python scripts/backfill_games_final_result_from_pbp.py --dsn "$DATABASE_URL" --game-id 0022400196

  # Backfill all games that have PBP:
  ./.venv/bin/python scripts/backfill_games_final_result_from_pbp.py --dsn "$DATABASE_URL" --all

  # Overwrite existing values:
  ./.venv/bin/python scripts/backfill_games_final_result_from_pbp.py --dsn "$DATABASE_URL" --all --force
"""

from __future__ import annotations

import argparse
import os
from typing import Sequence

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill games final score and winner from pbp_events.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", help="Game ID (can be repeated).")
    p.add_argument("--all", action="store_true", help="Backfill all games that have PBP.")
    p.add_argument("--force", action="store_true", help="Overwrite existing games.*final* fields.")
    return p.parse_args()


def _dedupe_keep_order(xs: Sequence[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    game_ids = _dedupe_keep_order(args.game_id or [])
    if args.all and game_ids:
        raise SystemExit("Pass either --all or --game-id, not both.")
    if not args.all and not game_ids:
        raise SystemExit("Provide at least one --game-id, or pass --all.")

    where = ""
    where_period_end = ""
    params: tuple[object, ...] = tuple()
    if not args.all:
        where = "WHERE e.game_id = ANY(%s)"
        where_period_end = "WHERE e.game_id = ANY(%s) AND lower(e.action_type) = 'period' AND lower(e.sub_type) = 'end'"
        # We reference the game_id filter twice (period_end + last_evt), so pass it twice.
        params = (game_ids, game_ids)
    else:
        where_period_end = "WHERE lower(e.action_type) = 'period' AND lower(e.sub_type) = 'end'"

    # winner_team_id needs home/away team ids in games; if missing, it remains NULL.
    if args.force:
        sql = f"""
        WITH period_end AS (
          SELECT DISTINCT ON (e.game_id)
            e.game_id,
            e.score_home,
            e.score_away
          FROM pbp_events e
          {where_period_end}
          ORDER BY e.game_id, e.order_number DESC
        ),
        last_evt AS (
          SELECT DISTINCT ON (e.game_id)
            e.game_id,
            e.score_home,
            e.score_away
          FROM pbp_events e
          {where}
          ORDER BY e.game_id, e.order_number DESC
        ),
        final_evt AS (
          SELECT
            le.game_id,
            COALESCE(pe.score_home, le.score_home) AS score_home,
            COALESCE(pe.score_away, le.score_away) AS score_away
          FROM last_evt le
          LEFT JOIN period_end pe ON pe.game_id = le.game_id
        )
        UPDATE games g
        SET
          final_score_home = fe.score_home,
          final_score_away = fe.score_away,
          winner_team_id = CASE
            WHEN g.home_team_id IS NULL OR g.away_team_id IS NULL THEN NULL
            WHEN fe.score_home > fe.score_away THEN g.home_team_id
            WHEN fe.score_home < fe.score_away THEN g.away_team_id
            ELSE NULL
          END
        FROM final_evt fe
        WHERE g.game_id = fe.game_id
        """
    else:
        sql = f"""
        WITH period_end AS (
          SELECT DISTINCT ON (e.game_id)
            e.game_id,
            e.score_home,
            e.score_away
          FROM pbp_events e
          {where_period_end}
          ORDER BY e.game_id, e.order_number DESC
        ),
        last_evt AS (
          SELECT DISTINCT ON (e.game_id)
            e.game_id,
            e.score_home,
            e.score_away
          FROM pbp_events e
          {where}
          ORDER BY e.game_id, e.order_number DESC
        ),
        final_evt AS (
          SELECT
            le.game_id,
            COALESCE(pe.score_home, le.score_home) AS score_home,
            COALESCE(pe.score_away, le.score_away) AS score_away
          FROM last_evt le
          LEFT JOIN period_end pe ON pe.game_id = le.game_id
        )
        UPDATE games g
        SET
          final_score_home = COALESCE(g.final_score_home, fe.score_home),
          final_score_away = COALESCE(g.final_score_away, fe.score_away),
          winner_team_id = COALESCE(
            g.winner_team_id,
            CASE
              WHEN g.home_team_id IS NULL OR g.away_team_id IS NULL THEN NULL
              WHEN fe.score_home > fe.score_away THEN g.home_team_id
              WHEN fe.score_home < fe.score_away THEN g.away_team_id
              ELSE NULL
            END
          )
        FROM final_evt fe
        WHERE g.game_id = fe.game_id
        """

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            res = conn.execute(sql, params) if params else conn.execute(sql)
            # psycopg rowcount is best-effort for UPDATE; still useful.
            print(f"Updated {res.rowcount} game row(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


