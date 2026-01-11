#!/usr/bin/env python3
"""
Materialize a compact per-event game state table for modeling/analysis.

Writes into:
  derived.pbp_event_state(
    game_id, event_id, point_differential, time_remaining,
    possession_side, home_score, away_score, current_winning_team, final_winning_team
  )

Source:
  derived.game_state_by_event

Definitions:
  - point_differential is HOME - AWAY (matches derived.game_state_by_event.score_diff_home)
  - time_remaining is seconds remaining in the GAME (matches derived.game_state_by_event.seconds_remaining_game)
  - possession_side is 0 (home) / 1 (away) / NULL (unknown)
  - home_score / away_score are the scoreboard values at that event
  - current_winning_team is 0 (home leading) / 1 (away leading) / NULL (tied/unknown)
  - final_winning_team is 0 (home won) / 1 (away won) / NULL (tied/unknown); constant per game

Usage (recommended: per-game refresh):
  python scripts/materialize_pbp_event_state.py --dsn "$DATABASE_URL" --game-id 0022400196

Full rebuild (truncates destination table first):
  python scripts/materialize_pbp_event_state.py --dsn "$DATABASE_URL" --all

Fill only missing games (has PBP but not yet present in derived.pbp_event_state), batched:
  python scripts/materialize_pbp_event_state.py --dsn "$DATABASE_URL" --missing --batch-size 200
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable
from typing import Sequence

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Populate derived.pbp_event_state from derived.game_state_by_event.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", help="Game ID to (re)materialize (can be repeated).")
    p.add_argument(
        "--missing",
        action="store_true",
        help="Materialize for games that have PBP but are missing from derived.pbp_event_state (no TRUNCATE).",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Rebuild for all games (TRUNCATE derived.pbp_event_state then insert from derived.game_state_by_event).",
    )
    p.add_argument("--batch-size", type=int, default=250, help="Batch size for --missing (default: 250).")
    p.add_argument("--limit-games", type=int, default=0, help="Limit number of games processed (0 = no limit).")
    p.add_argument(
        "--update-final-winner-from-games",
        action="store_true",
        help="Update derived.pbp_event_state.final_winning_team from games.final_score_* (no rebuild).",
    )
    p.add_argument(
        "--update-final-winner-only-null",
        action="store_true",
        help="When using --update-final-winner-from-games, only update rows where final_winning_team is NULL.",
    )
    return p.parse_args()


def _dedupe_keep_order(xs: Sequence[str]) -> list[str]:
    # dict preserves insertion order
    return list(dict.fromkeys([x for x in xs if x]))

def _chunked(xs: list[str], n: int) -> Iterable[list[str]]:
    if n <= 0:
        raise ValueError("batch size must be > 0")
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def _load_missing_game_ids(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT g.game_id
        FROM games g
        WHERE EXISTS (SELECT 1 FROM pbp_events e WHERE e.game_id = g.game_id)
          AND NOT EXISTS (SELECT 1 FROM derived.pbp_event_state s WHERE s.game_id = g.game_id)
        ORDER BY g.game_id
        """
    ).fetchall()
    return [str(r[0]) for r in rows]


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    game_ids = _dedupe_keep_order(args.game_id or [])
    if args.update_final_winner_from_games and (args.all or args.missing):
        raise SystemExit("Pass either --update-final-winner-from-games or (--missing/--all), not both.")
    if args.update_final_winner_from_games and game_ids:
        # keep the updater simple: update all rows (or all NULL rows).
        raise SystemExit("Do not pass --game-id with --update-final-winner-from-games. Use a rebuild mode instead.")

    if args.all and (game_ids or args.missing or args.update_final_winner_from_games):
        raise SystemExit("Pass either --all or --game-id, not both.")
    if args.missing and game_ids:
        raise SystemExit("Pass either --missing or --game-id, not both.")
    if args.missing and args.all:
        raise SystemExit("Pass either --all or --missing, not both.")
    if not args.all and not args.missing and not args.update_final_winner_from_games and not game_ids:
        raise SystemExit("Provide at least one --game-id, or pass --missing / --all.")

    with psycopg.connect(dsn) as conn:
        if args.update_final_winner_from_games:
            with conn.transaction():
                where = "WHERE s.final_winning_team IS NULL" if args.update_final_winner_only_null else ""
                res = conn.execute(
                    f"""
                    UPDATE derived.pbp_event_state s
                    SET final_winning_team = CASE
                      WHEN g.final_score_home > g.final_score_away THEN 0
                      WHEN g.final_score_home < g.final_score_away THEN 1
                      ELSE NULL
                    END
                    FROM games g
                    WHERE g.game_id = s.game_id
                    {('AND s.final_winning_team IS NULL' if args.update_final_winner_only_null else '')}
                    """
                )
            print(f"Updated {res.rowcount} row(s) in derived.pbp_event_state.final_winning_team from games table.")
            return 0

        if args.all:
            with conn.transaction():
                conn.execute("TRUNCATE derived.pbp_event_state;")
                res = conn.execute(
                    """
                    INSERT INTO derived.pbp_event_state (
                      game_id, event_id, point_differential, time_remaining,
                      possession_side, home_score, away_score, current_winning_team, final_winning_team
                    )
                    SELECT
                      s.game_id, s.event_id, s.score_diff_home, s.seconds_remaining_game,
                      CASE
                        WHEN s.possession_team_id IS NULL THEN NULL
                        WHEN s.possession_team_id = g.home_team_id THEN 0
                        WHEN s.possession_team_id = g.away_team_id THEN 1
                        ELSE NULL
                      END AS possession_side,
                      s.score_home AS home_score,
                      s.score_away AS away_score,
                      CASE
                        WHEN s.score_home > s.score_away THEN 0
                        WHEN s.score_home < s.score_away THEN 1
                        ELSE NULL
                      END AS current_winning_team,
                      CASE
                        WHEN g.final_score_home > g.final_score_away THEN 0
                        WHEN g.final_score_home < g.final_score_away THEN 1
                        ELSE NULL
                      END AS final_winning_team
                    FROM derived.game_state_by_event s
                    JOIN games g ON g.game_id = s.game_id
                    """
                )
            print(f"Inserted {res.rowcount} row(s) into derived.pbp_event_state (full rebuild).")
            return 0

        if args.missing:
            missing_ids = _load_missing_game_ids(conn)
            if args.limit_games and args.limit_games > 0:
                missing_ids = missing_ids[: args.limit_games]
            if not missing_ids:
                print("No missing games found (derived.pbp_event_state already covers all games with PBP).")
                return 0

            total_inserted = 0
            batches = list(_chunked(missing_ids, args.batch_size))
            for i, batch in enumerate(batches, start=1):
                with conn.transaction():
                    # Per-game refresh: delete + insert (faster than row-by-row upserts at this scale).
                    conn.execute("DELETE FROM derived.pbp_event_state WHERE game_id = ANY(%s);", (batch,))
                    res = conn.execute(
                        """
                        INSERT INTO derived.pbp_event_state (
                          game_id, event_id, point_differential, time_remaining,
                          possession_side, home_score, away_score, current_winning_team, final_winning_team
                        )
                        SELECT
                          s.game_id, s.event_id, s.score_diff_home, s.seconds_remaining_game,
                          CASE
                            WHEN s.possession_team_id IS NULL THEN NULL
                            WHEN s.possession_team_id = g.home_team_id THEN 0
                            WHEN s.possession_team_id = g.away_team_id THEN 1
                            ELSE NULL
                          END AS possession_side,
                          s.score_home AS home_score,
                          s.score_away AS away_score,
                          CASE
                            WHEN s.score_home > s.score_away THEN 0
                            WHEN s.score_home < s.score_away THEN 1
                            ELSE NULL
                          END AS current_winning_team,
                          CASE
                            WHEN g.final_score_home > g.final_score_away THEN 0
                            WHEN g.final_score_home < g.final_score_away THEN 1
                            ELSE NULL
                          END AS final_winning_team
                        FROM derived.game_state_by_event s
                        JOIN games g ON g.game_id = s.game_id
                        WHERE s.game_id = ANY(%s)
                        """,
                        (batch,),
                    )
                total_inserted += res.rowcount
                print(f"[{i}/{len(batches)}] Inserted {res.rowcount} row(s) for {len(batch)} game(s).")

            print(f"Inserted {total_inserted} row(s) into derived.pbp_event_state for {len(missing_ids)} missing game(s).")
            return 0

            # Per-game refresh: delete + insert (faster than row-by-row upserts at this scale).
        # Per-game refresh: delete + insert (faster than row-by-row upserts at this scale).
        with conn.transaction():
            conn.execute("DELETE FROM derived.pbp_event_state WHERE game_id = ANY(%s);", (game_ids,))
            res = conn.execute(
                """
                INSERT INTO derived.pbp_event_state (
                  game_id, event_id, point_differential, time_remaining,
                  possession_side, home_score, away_score, current_winning_team, final_winning_team
                )
                SELECT
                  s.game_id, s.event_id, s.score_diff_home, s.seconds_remaining_game,
                  CASE
                    WHEN s.possession_team_id IS NULL THEN NULL
                    WHEN s.possession_team_id = g.home_team_id THEN 0
                    WHEN s.possession_team_id = g.away_team_id THEN 1
                    ELSE NULL
                  END AS possession_side,
                  s.score_home AS home_score,
                  s.score_away AS away_score,
                  CASE
                    WHEN s.score_home > s.score_away THEN 0
                    WHEN s.score_home < s.score_away THEN 1
                    ELSE NULL
                  END AS current_winning_team,
                  CASE
                    WHEN g.final_score_home > g.final_score_away THEN 0
                    WHEN g.final_score_home < g.final_score_away THEN 1
                    ELSE NULL
                  END AS final_winning_team
                FROM derived.game_state_by_event s
                JOIN games g ON g.game_id = s.game_id
                WHERE s.game_id = ANY(%s)
                """,
                (game_ids,),
            )
        print(f"Inserted {res.rowcount} row(s) into derived.pbp_event_state for {len(game_ids)} game(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


