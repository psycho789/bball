#!/usr/bin/env python3
"""
Backfill games.home_team_id / games.away_team_id (and minimal teams dim) from
archived nba_api LeagueGameFinder JSON responses (OFFLINE).

Why:
  - PBP does not include game-level home/away team ids.
  - LeagueGameFinder rows include GAME_ID, TEAM_ID, TEAM_ABBREVIATION, and MATCHUP.
    MATCHUP encodes home/away:
      - "TEAM vs. OPP" => TEAM is home
      - "TEAM @ OPP"   => TEAM is away

Inputs:
  data/raw/nba_api/leaguegamefinder/season=YYYY-YY/leaguegamefinder_YYYY-YY_*.json

Usage:
  # One season (uses latest archived JSON found for that season)
  ./.venv/bin/python scripts/backfill_games_from_leaguegamefinder_archive.py --dsn "$DATABASE_URL" --season 2015-16

  # Range (inclusive)
  ./.venv/bin/python scripts/backfill_games_from_leaguegamefinder_archive.py --dsn "$DATABASE_URL" \
    --from-season 2015-16 --to-season 2022-23

  # Only specific games (infers season from game_id and filters within that season)
  ./.venv/bin/python scripts/backfill_games_from_leaguegamefinder_archive.py --dsn "$DATABASE_URL" \
    --game-id 0021600638 --game-id 0041500407
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill games home/away team ids from archived LeagueGameFinder JSON (offline).")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--season", action="append", default=[], help="Season like 2015-16 (can be repeated).")
    p.add_argument("--from-season", default="", help="Range start season like 2015-16 (inclusive).")
    p.add_argument("--to-season", default="", help="Range end season like 2022-23 (inclusive).")
    p.add_argument("--game-id", action="append", default=[], help="Game ID to backfill (can be repeated).")
    p.add_argument(
        "--input-root",
        default="data/raw/nba_api/leaguegamefinder",
        help="Root directory containing season=YYYY-YY subdirs with leaguegamefinder_*.json files.",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing games.home_team_id/away_team_id values.")
    return p.parse_args()


def _dedupe_keep_order(xs: list[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def _season_start_year(season: str) -> int:
    s = (season or "").strip()
    if len(s) < 7 or s[4] != "-" or not s[:4].isdigit():
        raise ValueError(f"Invalid season {season!r}. Expected like '2015-16'.")
    return int(s[:4])


def _format_season(start_year: int) -> str:
    return f"{start_year}-{str((start_year + 1) % 100).zfill(2)}"


def _season_range(from_season: str, to_season: str) -> list[str]:
    a = _season_start_year(from_season)
    b = _season_start_year(to_season)
    if b < a:
        raise ValueError(f"--to-season must be >= --from-season (got {from_season!r}..{to_season!r})")
    seasons = [_format_season(y) for y in range(a, b + 1)]
    if seasons[0] != from_season.strip() or seasons[-1] != to_season.strip():
        raise ValueError(f"Invalid season range {from_season!r}..{to_season!r}")
    return seasons


def _season_from_game_id(game_id: str) -> str:
    gid = (game_id or "").strip()
    if len(gid) < 5 or not gid[3:5].isdigit():
        raise ValueError(f"Cannot infer season from game_id={game_id!r}")
    yy = int(gid[3:5])
    start_year = 2000 + yy
    return _format_season(start_year)


def _season_type_from_game_id_prefix(game_id: str) -> str | None:
    prefix = (game_id or "")[:3]
    return {
        "001": "preseason",
        "002": "regular",
        "003": "all_star",
        "004": "playoffs",
        "005": "playin",
        "006": "in_season",
    }.get(prefix)


def _parse_game_date_utc(date_str: Any) -> datetime | None:
    """
    LeagueGameFinder GAME_DATE is 'YYYY-MM-DD' (no time). We *could* store
    midnight UTC as an approximate anchor, but leaving NULL is also acceptable.
    We'll store midnight UTC (00:00:00Z) to support year-based grouping.
    """
    if not date_str:
        return None
    s = str(date_str).strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@dataclass(frozen=True)
class TeamRow:
    team_id: int
    tricode: str
    name: str | None


@dataclass(frozen=True)
class GameSides:
    game_id: str
    game_date_utc: datetime | None
    season_start: int
    season_type: str | None
    home_team_id: int | None
    away_team_id: int | None


def _latest_archive_file(input_root: Path, season: str) -> Path:
    season_dir = input_root / f"season={season}"
    if not season_dir.exists():
        raise FileNotFoundError(f"Missing season directory: {season_dir}")
    candidates = sorted(
        [
            p
            for p in season_dir.glob("leaguegamefinder_*.json")
            if p.is_file() and not p.name.endswith(".manifest.json")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No leaguegamefinder JSON files found in: {season_dir}")
    return candidates[0]


def _load_rows(path: Path) -> tuple[list[str], list[list[Any]]]:
    obj = __import__("json").loads(path.read_text(encoding="utf-8"))
    rs = obj.get("resultSets")
    if not isinstance(rs, list) or not rs:
        raise RuntimeError(f"Unexpected LeagueGameFinder payload (missing resultSets list): {path}")
    # Find the main result set
    main = None
    for r in rs:
        if isinstance(r, dict) and r.get("name") == "LeagueGameFinderResults":
            main = r
            break
    if main is None:
        main = rs[0]
    headers = main.get("headers")
    row_set = main.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise RuntimeError(f"Unexpected LeagueGameFinder payload shape: {path}")
    return [str(h) for h in headers], row_set  # row_set is list[list[Any]]


def _infer_sides_from_matchup(matchup: str, team_tricode: str) -> tuple[bool | None, str | None]:
    """
    Returns (is_home, opponent_tricode).
    """
    m = (matchup or "").strip()
    tri = (team_tricode or "").strip()
    if not m or not tri:
        return None, None
    if " vs. " in m:
        # "GSW vs. CLE"
        try:
            left, right = m.split(" vs. ", 1)
            return True, right.strip() or None
        except Exception:
            return None, None
    if " @ " in m:
        # "CLE @ GSW"
        try:
            left, right = m.split(" @ ", 1)
            return False, right.strip() or None
        except Exception:
            return None, None
    return None, None


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    seasons = _dedupe_keep_order([s.strip() for s in (args.season or []) if s and s.strip()])
    game_ids = _dedupe_keep_order([g.strip() for g in (args.game_id or []) if g and g.strip()])

    if args.from_season or args.to_season:
        if not (args.from_season and args.to_season):
            raise SystemExit("Pass both --from-season and --to-season (or neither).")
        seasons = _dedupe_keep_order(seasons + _season_range(args.from_season, args.to_season))

    if game_ids:
        seasons = _dedupe_keep_order(seasons + [_season_from_game_id(g) for g in game_ids])

    if not seasons:
        raise SystemExit("Provide at least one --season/--from-season+--to-season or --game-id.")

    input_root = Path(args.input_root)

    total_games_parsed = 0
    total_games_upserted = 0
    total_games_missing_pair = 0

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            for season in seasons:
                season_start = _season_start_year(season)
                path = _latest_archive_file(input_root, season)
                headers, rows = _load_rows(path)
                idx = {h: i for i, h in enumerate(headers)}

                for req in ("GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "MATCHUP", "GAME_DATE"):
                    if req not in idx:
                        raise SystemExit(f"Missing required header {req!r} in {path} headers={headers}")

                per_game: dict[str, dict[str, Any]] = {}
                for r in rows:
                    try:
                        gid = str(r[idx["GAME_ID"]]).strip()
                    except Exception:
                        continue
                    if not gid:
                        continue
                    if game_ids and gid not in game_ids:
                        continue

                    try:
                        team_id = int(r[idx["TEAM_ID"]])
                    except Exception:
                        continue
                    tri = str(r[idx["TEAM_ABBREVIATION"]] or "").strip()
                    name = str(r[idx["TEAM_NAME"]] or "").strip() or None
                    matchup = str(r[idx["MATCHUP"]] or "").strip()
                    game_date_utc = _parse_game_date_utc(r[idx["GAME_DATE"]])

                    # teams: we can safely upsert because tricode is present in leaguegamefinder.
                    if tri:
                        conn.execute(
                            """
                            INSERT INTO teams(team_id, team_tricode, team_name)
                            VALUES (%s,%s,%s)
                            ON CONFLICT (team_id) DO UPDATE SET
                              team_tricode = COALESCE(EXCLUDED.team_tricode, teams.team_tricode),
                              team_name = COALESCE(EXCLUDED.team_name, teams.team_name)
                            """,
                            (team_id, tri, name),
                        )

                    is_home, _opp = _infer_sides_from_matchup(matchup, tri)
                    if is_home is None:
                        continue

                    g = per_game.setdefault(gid, {"home": None, "away": None, "date": game_date_utc})
                    # keep first non-null date
                    if g.get("date") is None and game_date_utc is not None:
                        g["date"] = game_date_utc
                    if is_home:
                        g["home"] = team_id
                    else:
                        g["away"] = team_id

                # Upsert games
                for gid, info in per_game.items():
                    total_games_parsed += 1
                    home_id = info.get("home")
                    away_id = info.get("away")
                    if not home_id or not away_id:
                        total_games_missing_pair += 1
                        continue
                    season_type = _season_type_from_game_id_prefix(gid)
                    game_time_utc = info.get("date")

                    if args.force:
                        conn.execute(
                            """
                            INSERT INTO games(game_id, game_time_utc, season, season_type, home_team_id, away_team_id)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (game_id) DO UPDATE SET
                              game_time_utc = COALESCE(EXCLUDED.game_time_utc, games.game_time_utc),
                              season = COALESCE(EXCLUDED.season, games.season),
                              season_type = COALESCE(EXCLUDED.season_type, games.season_type),
                              home_team_id = EXCLUDED.home_team_id,
                              away_team_id = EXCLUDED.away_team_id
                            """,
                            (gid, game_time_utc, season_start, season_type, home_id, away_id),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO games(game_id, game_time_utc, season, season_type, home_team_id, away_team_id)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (game_id) DO UPDATE SET
                              game_time_utc = COALESCE(EXCLUDED.game_time_utc, games.game_time_utc),
                              season = COALESCE(games.season, EXCLUDED.season),
                              season_type = COALESCE(games.season_type, EXCLUDED.season_type),
                              home_team_id = COALESCE(games.home_team_id, EXCLUDED.home_team_id),
                              away_team_id = COALESCE(games.away_team_id, EXCLUDED.away_team_id)
                            """,
                            (gid, game_time_utc, season_start, season_type, home_id, away_id),
                        )
                    total_games_upserted += 1

                print(f"season={season} archive={path.name} games_parsed={len(per_game)} games_upserted={sum(1 for v in per_game.values() if v.get('home') and v.get('away'))}")

    print(f"Seasons: {', '.join(seasons)}")
    print(f"Games parsed: {total_games_parsed}")
    print(f"Games upserted: {total_games_upserted}")
    if total_games_missing_pair:
        print(f"Games skipped (missing home/away pair): {total_games_missing_pair}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


