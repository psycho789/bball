#!/usr/bin/env python3
"""
Backfill games.home_team_id / games.away_team_id (and basic teams dim fields)
from archived boxscore JSONs.

Why:
  PBP JSON from cdn.nba.com liveData/playbyplay does NOT contain home/away team IDs
  at the game level (it's just {gameId, actions}). Boxscore JSON DOES contain homeTeam
  and awayTeam objects with teamId/tricode/name/city. We need those IDs to compute
  derived.pbp_event_state.possession_side (0=home, 1=away).

Usage:
  ./.venv/bin/python scripts/backfill_games_from_boxscore_archive.py --dsn "$DATABASE_URL" \
    --game-id 0022400196

  # multiple games
  ./.venv/bin/python scripts/backfill_games_from_boxscore_archive.py --dsn "$DATABASE_URL" \
    --game-id 0022400196 --game-id 0012300001
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill games home/away team ids from boxscore archives.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", required=True, help="Game ID (can be repeated).")
    p.add_argument(
        "--boxscore-dir",
        default="data/raw/boxscore",
        help="Directory containing {game_id}.json boxscore archives.",
    )
    return p.parse_args()


def _dedupe_keep_order(xs: list[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def _parse_dt(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        # e.g. "2024-11-08T19:00:00-08:00"
        dt = datetime.fromisoformat(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _team_fields(team_obj: Any) -> tuple[int, str | None, str | None, str | None]:
    if not isinstance(team_obj, dict):
        raise RuntimeError("expected team object dict in boxscore JSON")
    team_id = team_obj.get("teamId")
    if team_id is None:
        raise RuntimeError("missing teamId in boxscore team object")
    return (int(team_id), team_obj.get("teamTricode"), team_obj.get("teamCity"), team_obj.get("teamName"))


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)
    game_ids = _dedupe_keep_order(args.game_id or [])
    boxscore_dir = Path(args.boxscore_dir)

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            updated_games = 0
            for gid in game_ids:
                path = boxscore_dir / f"{gid}.json"
                if not path.exists():
                    raise SystemExit(f"Boxscore archive not found: {path}")

                obj = json.loads(path.read_text(encoding="utf-8"))
                game = obj.get("game")
                if not isinstance(game, dict):
                    raise SystemExit(f"Boxscore JSON missing game object: {path}")

                home = game.get("homeTeam")
                away = game.get("awayTeam")
                home_id, home_tri, home_city, home_name = _team_fields(home)
                away_id, away_tri, away_city, away_name = _team_fields(away)

                # Optional: game time strings (often present as local time w/ offset)
                game_time_utc = _parse_dt(game.get("gameTimeHome")) or _parse_dt(game.get("gameTimeAway"))

                # Upsert teams (minimal)
                conn.execute(
                    """
                    INSERT INTO teams(team_id, team_tricode, team_city, team_name)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (team_id) DO UPDATE SET
                      team_tricode = COALESCE(EXCLUDED.team_tricode, teams.team_tricode),
                      team_city = COALESCE(EXCLUDED.team_city, teams.team_city),
                      team_name = COALESCE(EXCLUDED.team_name, teams.team_name)
                    """,
                    (home_id, home_tri, home_city, home_name),
                )
                conn.execute(
                    """
                    INSERT INTO teams(team_id, team_tricode, team_city, team_name)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (team_id) DO UPDATE SET
                      team_tricode = COALESCE(EXCLUDED.team_tricode, teams.team_tricode),
                      team_city = COALESCE(EXCLUDED.team_city, teams.team_city),
                      team_name = COALESCE(EXCLUDED.team_name, teams.team_name)
                    """,
                    (away_id, away_tri, away_city, away_name),
                )

                # Upsert game home/away ids (and time if available)
                conn.execute(
                    """
                    INSERT INTO games(game_id, game_time_utc, home_team_id, away_team_id)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (game_id) DO UPDATE SET
                      game_time_utc = COALESCE(EXCLUDED.game_time_utc, games.game_time_utc),
                      home_team_id = COALESCE(EXCLUDED.home_team_id, games.home_team_id),
                      away_team_id = COALESCE(EXCLUDED.away_team_id, games.away_team_id)
                    """,
                    (gid, game_time_utc, home_id, away_id),
                )
                updated_games += 1

    print(f"Backfilled {updated_games} game(s) from boxscore archives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


