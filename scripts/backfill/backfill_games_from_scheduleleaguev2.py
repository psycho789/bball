#!/usr/bin/env python3
"""
Backfill games.home_team_id / games.away_team_id using the nba_api
ScheduleLeagueV2 endpoint.

Why:
  We need games.home_team_id/away_team_id populated to compute
  derived.pbp_event_state.possession_side (0=home, 1=away).

Source:
  nba_api.stats.endpoints.scheduleleaguev2.ScheduleLeagueV2
  Result set: SeasonGames, with columns:
    - gameId
    - homeTeam_teamId
    - awayTeam_teamId
    - homeTeam_teamTricode / teamCity / teamName (optional)
    - awayTeam_teamTricode / teamCity / teamName (optional)
    - gameDateTimeUTC (optional)
    - isNeutral (optional)

Usage:
  # Backfill a full season:
  ./.venv/bin/python scripts/backfill_games_from_scheduleleaguev2.py --dsn "$DATABASE_URL" --season 2024-25

  # Backfill a season range (inclusive):
  ./.venv/bin/python scripts/backfill_games_from_scheduleleaguev2.py --dsn "$DATABASE_URL" \
    --from-season 2015-16 --to-season 2022-23

  # Backfill a specific game id (infers season from game_id):
  ./.venv/bin/python scripts/backfill_games_from_scheduleleaguev2.py --dsn "$DATABASE_URL" --game-id 0021600638

  # Multiple seasons:
  ./.venv/bin/python scripts/backfill_games_from_scheduleleaguev2.py --dsn "$DATABASE_URL" --season 2023-24 --season 2024-25

  # Only fill missing home/away ids (default). Use --force to overwrite:
  ./.venv/bin/python scripts/backfill_games_from_scheduleleaguev2.py --dsn "$DATABASE_URL" --season 2024-25 --force

Notes:
  - This script makes live HTTP requests through nba_api. If you want a purely-offline
    backfill, use the boxscore-archive script instead.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import pandas as pd
import psycopg
from nba_api.stats.endpoints import scheduleleaguev2
from nba_api.stats.library.http import NBAStatsHTTP

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn, parse_iso8601_z
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill games home/away team ids from nba_api ScheduleLeagueV2.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--season", action="append", default=[], help="Season like 2024-25 (can be repeated).")
    p.add_argument("--game-id", action="append", default=[], help="Game ID to backfill (can be repeated).")
    p.add_argument("--from-season", default="", help="Range start season like 2015-16 (inclusive).")
    p.add_argument("--to-season", default="", help="Range end season like 2022-23 (inclusive).")
    p.add_argument("--league-id", default="00", help="NBA league id (default: 00).")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds (default: 30).")
    p.add_argument("--force", action="store_true", help="Overwrite existing games.home_team_id/away_team_id values.")
    return p.parse_args()


def _dedupe_keep_order(xs: list[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def _to_int_or_none(x: Any) -> int | None:
    if x is None:
        return None
    # pandas NA / numpy nan
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    try:
        return int(x)
    except Exception:
        return None


def _clean_tricode(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    return s


def _season_from_game_id(game_id: str) -> str:
    """
    NBA game_id encodes season start year at positions 4-5 (YY).
    Example: 0021600638 -> season start year 2016 -> "2016-17"
    """
    gid = (game_id or "").strip()
    if len(gid) < 5 or not gid[3:5].isdigit():
        raise ValueError(f"Cannot infer season from game_id={game_id!r}")
    yy = int(gid[3:5])
    start_year = 2000 + yy
    end_yy = str((start_year + 1) % 100).zfill(2)
    return f"{start_year}-{end_yy}"


def _season_start_year(season: str) -> int:
    s = (season or "").strip()
    if len(s) < 7 or s[4] != "-" or not s[:4].isdigit():
        raise ValueError(f"Invalid season {season!r}. Expected like '2016-17' or '2024-25'.")
    return int(s[:4])


def _season_type_from_game_id_prefix(game_id: str) -> str | None:
    """
    Conservative mapping based on common NBA game_id prefixes.
    """
    prefix = (game_id or "")[:3]
    return {
        "001": "preseason",
        "002": "regular",
        "003": "all_star",
        "004": "playoffs",
        "005": "playin",
        "006": "in_season",
    }.get(prefix)

def _format_season(start_year: int) -> str:
    return f"{start_year}-{str((start_year + 1) % 100).zfill(2)}"


def _season_range(from_season: str, to_season: str) -> list[str]:
    a = _season_start_year(from_season)
    b = _season_start_year(to_season)
    if b < a:
        raise ValueError(f"--to-season must be >= --from-season (got {from_season!r}..{to_season!r})")
    seasons = [_format_season(y) for y in range(a, b + 1)]
    # sanity: caller likely wants exact match on the endpoint format
    if seasons[0] != from_season.strip() or seasons[-1] != to_season.strip():
        raise ValueError(f"Invalid season range {from_season!r}..{to_season!r}")
    return seasons


def _extract_schedule_container(obj: dict[str, Any]) -> dict[str, Any]:
    """
    ScheduleLeagueV2 responses come back in a "v3-ish" shape that includes an object
    with gameDates[]. games[] entries.

    nba_api's parser assumes a non-empty `weeks` list, which is not always true for
    some historical seasons; this helper finds the container we need without relying
    on `weeks`.
    """
    if "leagueSchedule" in obj and isinstance(obj["leagueSchedule"], dict):
        return obj["leagueSchedule"]
    # Fallback: find the first dict value that looks like the schedule payload.
    for v in obj.values():
        if isinstance(v, dict) and isinstance(v.get("gameDates"), list):
            return v
    raise KeyError("Could not locate schedule container (expected a dict with gameDates[]).")


def _season_games_df_fallback_http(*, league_id: str, season: str, timeout: int) -> pd.DataFrame:
    """
    Fallback path when nba_api's ScheduleLeagueV2 parser errors (e.g., IndexError on weeks[0]).
    Uses raw HTTP + minimal JSON parsing to produce a DataFrame with the key fields we use.
    """
    url = f"https://stats.nba.com/stats/scheduleleaguev2?LeagueID={league_id}&Season={season}"
    retry = HttpRetry(max_attempts=4, timeout_seconds=float(timeout), deadline_seconds=float(timeout) * 4)
    status, _, body = http_get_bytes(url, retry=retry, headers={"Referer": "https://stats.nba.com/"})
    if status != 200:
        raise RuntimeError(f"ScheduleLeagueV2 HTTP {status} for season={season!r}")
    obj = parse_json_bytes(body)
    container = _extract_schedule_container(obj)
    game_dates = container.get("gameDates") or []
    if not isinstance(game_dates, list):
        raise RuntimeError("Unexpected ScheduleLeagueV2 payload: gameDates is not a list")

    rows: list[dict[str, Any]] = []
    for gd in game_dates:
        if not isinstance(gd, dict):
            continue
        games = gd.get("games") or []
        if not isinstance(games, list):
            continue
        for g in games:
            if not isinstance(g, dict):
                continue
            home = g.get("homeTeam") if isinstance(g.get("homeTeam"), dict) else {}
            away = g.get("awayTeam") if isinstance(g.get("awayTeam"), dict) else {}
            rows.append(
                {
                    "gameId": g.get("gameId"),
                    "gameDateTimeUTC": g.get("gameDateTimeUTC"),
                    "isNeutral": g.get("isNeutral"),
                    "homeTeam_teamId": home.get("teamId"),
                    "homeTeam_teamTricode": home.get("teamTricode"),
                    "homeTeam_teamCity": home.get("teamCity"),
                    "homeTeam_teamName": home.get("teamName"),
                    "awayTeam_teamId": away.get("teamId"),
                    "awayTeam_teamTricode": away.get("teamTricode"),
                    "awayTeam_teamCity": away.get("teamCity"),
                    "awayTeam_teamName": away.get("teamName"),
                }
            )
    return pd.DataFrame(rows)


def _season_games_df(*, league_id: str, season: str, timeout: int) -> pd.DataFrame:
    """
    Returns the SeasonGames dataframe for a given season.
    Uses nba_api first; falls back to raw HTTP parsing if nba_api's parser crashes
    on historical seasons.
    """
    try:
        ep = scheduleleaguev2.ScheduleLeagueV2(
            league_id=league_id,
            season=season,
            timeout=timeout,
        )
        dfs = ep.get_data_frames()
        if dfs:
            return dfs[0]
    except Exception:
        # fall back below
        pass
    # Fallback: raw JSON parsing.
    return _season_games_df_fallback_http(league_id=league_id, season=season, timeout=timeout)


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)
    game_ids = _dedupe_keep_order(args.game_id or [])
    seasons = _dedupe_keep_order(args.season or [])
    if args.from_season or args.to_season:
        if not (args.from_season and args.to_season):
            raise SystemExit("Pass both --from-season and --to-season (or neither).")
        seasons = _dedupe_keep_order(seasons + _season_range(args.from_season, args.to_season))
    if game_ids:
        seasons = _dedupe_keep_order(seasons + [_season_from_game_id(gid) for gid in game_ids])
    if not seasons:
        raise SystemExit("Provide at least one --season or --game-id.")

    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            total_games_seen = 0
            total_games_upserted = 0
            total_games_skipped_missing_team_ids = 0
            total_games_skipped_missing_teams_dim = 0

            for season in seasons:
                season_start = _season_start_year(season)
                season_games = _season_games_df(league_id=args.league_id, season=season, timeout=args.timeout)
                if "gameId" not in season_games.columns:
                    raise SystemExit(f"Unexpected SeasonGames columns for season={season!r}: {list(season_games.columns)[:20]}")

                for _, r in season_games.iterrows():
                    game_id = str(r.get("gameId") or "").strip()
                    if not game_id:
                        continue
                    if game_ids and game_id not in game_ids:
                        continue

                    home_id = _to_int_or_none(r.get("homeTeam_teamId"))
                    away_id = _to_int_or_none(r.get("awayTeam_teamId"))
                    if home_id is None or away_id is None or home_id <= 0 or away_id <= 0:
                        # Current season schedules may include TBD rows with teamId=0.
                        total_games_skipped_missing_team_ids += 1
                        continue

                    total_games_seen += 1

                    # Optional enrichment for teams
                    home_tri = _clean_tricode(r.get("homeTeam_teamTricode"))
                    away_tri = _clean_tricode(r.get("awayTeam_teamTricode"))
                    home_city = (r.get("homeTeam_teamCity") or None)
                    away_city = (r.get("awayTeam_teamCity") or None)
                    home_name = (r.get("homeTeam_teamName") or None)
                    away_name = (r.get("awayTeam_teamName") or None)

                    # teams.team_tricode is NOT NULL, so only insert a new team row if we have a tricode.
                    # If tricodes are missing but the team already exists, we can proceed.
                    for team_id, tri, city, name in (
                        (home_id, home_tri, home_city, home_name),
                        (away_id, away_tri, away_city, away_name),
                    ):
                        if tri is None:
                            exists = conn.execute("SELECT 1 FROM teams WHERE team_id = %s", (team_id,)).fetchone()
                            if not exists:
                                total_games_skipped_missing_teams_dim += 1
                                # Without a teams row, inserting games.home_team_id/away_team_id would violate FK.
                                break
                            continue
                        conn.execute(
                            """
                            INSERT INTO teams(team_id, team_tricode, team_city, team_name)
                            VALUES (%s,%s,%s,%s)
                            ON CONFLICT (team_id) DO UPDATE SET
                              team_tricode = COALESCE(EXCLUDED.team_tricode, teams.team_tricode),
                              team_city = COALESCE(EXCLUDED.team_city, teams.team_city),
                              team_name = COALESCE(EXCLUDED.team_name, teams.team_name)
                            """,
                            (team_id, tri, city, name),
                        )
                    else:
                        # only runs if we didn't break (i.e., teams rows exist / were inserted)
                        pass
                    # If we broke due to missing teams dim, skip this game row.
                    if home_tri is None and not conn.execute("SELECT 1 FROM teams WHERE team_id = %s", (home_id,)).fetchone():
                        continue
                    if away_tri is None and not conn.execute("SELECT 1 FROM teams WHERE team_id = %s", (away_id,)).fetchone():
                        continue

                    game_time_utc = parse_iso8601_z(str(r.get("gameDateTimeUTC") or ""))  # accepts "...Z"
                    is_neutral = r.get("isNeutral")
                    if isinstance(is_neutral, str):
                        is_neutral = is_neutral.lower() in ("true", "t", "1", "yes", "y")
                    elif not isinstance(is_neutral, bool):
                        is_neutral = None
                    season_type = _season_type_from_game_id_prefix(game_id)

                    if args.force:
                        conn.execute(
                            """
                            INSERT INTO games(game_id, game_time_utc, season, season_type, home_team_id, away_team_id, is_neutral)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (game_id) DO UPDATE SET
                              game_time_utc = COALESCE(EXCLUDED.game_time_utc, games.game_time_utc),
                              season = COALESCE(EXCLUDED.season, games.season),
                              season_type = COALESCE(EXCLUDED.season_type, games.season_type),
                              home_team_id = EXCLUDED.home_team_id,
                              away_team_id = EXCLUDED.away_team_id,
                              is_neutral = COALESCE(EXCLUDED.is_neutral, games.is_neutral)
                            """,
                            (game_id, game_time_utc, season_start, season_type, home_id, away_id, is_neutral),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO games(game_id, game_time_utc, season, season_type, home_team_id, away_team_id, is_neutral)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (game_id) DO UPDATE SET
                              game_time_utc = COALESCE(EXCLUDED.game_time_utc, games.game_time_utc),
                              season = COALESCE(games.season, EXCLUDED.season),
                              season_type = COALESCE(games.season_type, EXCLUDED.season_type),
                              home_team_id = COALESCE(games.home_team_id, EXCLUDED.home_team_id),
                              away_team_id = COALESCE(games.away_team_id, EXCLUDED.away_team_id),
                              is_neutral = COALESCE(games.is_neutral, EXCLUDED.is_neutral)
                            """,
                            (game_id, game_time_utc, season_start, season_type, home_id, away_id, is_neutral),
                        )

                    total_games_upserted += 1

    print(f"Seasons: {', '.join(seasons)}")
    print(f"Games seen with team ids: {total_games_seen}")
    print(f"Games upserted: {total_games_upserted}")
    if total_games_skipped_missing_team_ids:
        print(f"Games skipped (missing/invalid team ids): {total_games_skipped_missing_team_ids}")
    if total_games_skipped_missing_teams_dim:
        print(f"Games skipped (team not in teams dim and missing tricode): {total_games_skipped_missing_teams_dim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


