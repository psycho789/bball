#!/usr/bin/env python3
"""
Load ESPN scoreboard data into Postgres - daily game listings with scores and metadata.

Input files:
  data/raw/espn/scoreboard/scoreboard_{YYYYMMDD}.json

Output table:
  espn.scoreboard_games

Design goals:
  - resumable: uses UPSERT on (event_id, scoreboard_date)
  - verbose: frequent progress + per-file counters, configurable heartbeat
  - minimal assumptions: stores each event as raw JSONB, plus extracts common fields for querying
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


SCOREBOARD_FILE_RE = re.compile(r"^scoreboard_(?P<date>\d{8})\.json$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_int(x: Any) -> int | None:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return int(x)
        return int(float(x))
    except Exception:
        return None


def _to_bool(x: Any) -> bool | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        return x.lower() in ("true", "1", "yes")
    return bool(x)


def _parse_timestamp(s: Any) -> datetime | None:
    """Parse ESPN timestamp like '2024-10-22T23:51Z' or '2017-10-01T22:00Z'."""
    if not isinstance(s, str) or not s:
        return None
    t = s.strip()
    try:
        if t.endswith("Z"):
            t2 = t[:-1] + "+00:00"
        else:
            t2 = t
        return datetime.fromisoformat(t2)
    except Exception:
        return None


def _parse_date_str(s: str) -> date | None:
    """Parse YYYYMMDD string to date."""
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except Exception:
        return None


@dataclass(frozen=True)
class FileKey:
    scoreboard_date: date
    path: Path


def _iter_scoreboard_files(scoreboard_dir: Path) -> list[FileKey]:
    if not scoreboard_dir.exists():
        return []
    out: list[FileKey] = []
    for p in sorted(scoreboard_dir.iterdir()):
        if not (p.is_file() and p.name.endswith(".json") and not p.name.endswith(".manifest.json")):
            continue
        m = SCOREBOARD_FILE_RE.match(p.name)
        if not m:
            continue
        date_str = m.group("date")
        sb_date = _parse_date_str(date_str)
        if sb_date:
            out.append(FileKey(scoreboard_date=sb_date, path=p))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load ESPN scoreboard data (raw JSON) into Postgres.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--scoreboard-dir", default="data/raw/espn/scoreboard", help="Dir containing scoreboard_YYYYMMDD.json files.")
    p.add_argument("--min-date", help="Only process files with date >= this date (YYYY-MM-DD format).")
    p.add_argument("--limit-files", type=int, default=0, help="If >0, stop after N files.")
    p.add_argument("--commit-every", type=int, default=100, help="Commit every N files (default: 100).")
    p.add_argument(
        "--rows-per-batch",
        type=int,
        default=1000,
        help="Batch upserts into executemany() calls of this many rows (default: 1000).",
    )
    p.add_argument("--heartbeat-seconds", type=float, default=10.0, help="Print a progress heartbeat at least this often. 0 disables.")
    p.add_argument("--verbose", action="store_true", help="Print per-file details.")
    return p.parse_args()


def _find_competitor(competitors: list[dict], home_away: str) -> dict | None:
    """Find competitor by homeAway field."""
    for c in competitors:
        if c.get("homeAway") == home_away:
            return c
    return None


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    scoreboard_dir = Path(args.scoreboard_dir)
    files = _iter_scoreboard_files(scoreboard_dir)
    
    # Filter by date if provided
    if args.min_date:
        try:
            min_date_obj = datetime.strptime(args.min_date, "%Y-%m-%d").date()
            original_count = len(files)
            files = [fk for fk in files if fk.scoreboard_date >= min_date_obj]
            if args.verbose:
                print(f"[load_espn_scoreboard] Filtered to {len(files)} files with date >= {min_date_obj} (from {original_count} total)", flush=True)
        except Exception as e:
            print(f"[load_espn_scoreboard] WARNING: Failed to parse --min-date '{args.min_date}': {e}", flush=True)
    
    if args.limit_files and int(args.limit_files) > 0:
        files = files[: int(args.limit_files)]
    if not files:
        raise SystemExit(f"No scoreboard files found in {scoreboard_dir}")

    ts = _utc_now_iso()
    print(f"[load_espn_scoreboard] start ts={ts} files={len(files)} dir={scoreboard_dir}", flush=True)

    last_hb = time.monotonic()
    hb = float(args.heartbeat_seconds or 0.0)
    commit_every = max(1, int(args.commit_every))
    rows_per_batch = max(1, int(args.rows_per_batch))

    total_files = 0
    total_events = 0
    total_upserts = 0
    total_errors = 0

    upsert_sql = """
    INSERT INTO espn.scoreboard_games (
      event_id, scoreboard_date,
      event_uid, event_date, event_name, short_name,
      season_year, season_type, season_slug,
      competition_id, venue_id, venue_name, venue_city, venue_state, is_neutral_site, attendance,
      home_team_id, home_team_abbrev, home_team_name, home_team_display_name, home_score, home_winner,
      away_team_id, away_team_abbrev, away_team_name, away_team_display_name, away_score, away_winner,
      status_type_id, status_name, status_state, status_completed, status_period, status_clock,
      broadcast,
      raw_event
    )
    VALUES (
      %s,%s,
      %s,%s,%s,%s,
      %s,%s,%s,
      %s,%s,%s,%s,%s,%s,%s,
      %s,%s,%s,%s,%s,%s,
      %s,%s,%s,%s,%s,%s,
      %s,%s,%s,%s,%s,%s,
      %s,
      %s
    )
    ON CONFLICT (event_id, scoreboard_date)
    DO UPDATE SET
      event_uid = EXCLUDED.event_uid,
      event_date = EXCLUDED.event_date,
      event_name = EXCLUDED.event_name,
      short_name = EXCLUDED.short_name,
      season_year = EXCLUDED.season_year,
      season_type = EXCLUDED.season_type,
      season_slug = EXCLUDED.season_slug,
      competition_id = EXCLUDED.competition_id,
      venue_id = EXCLUDED.venue_id,
      venue_name = EXCLUDED.venue_name,
      venue_city = EXCLUDED.venue_city,
      venue_state = EXCLUDED.venue_state,
      is_neutral_site = EXCLUDED.is_neutral_site,
      attendance = EXCLUDED.attendance,
      home_team_id = EXCLUDED.home_team_id,
      home_team_abbrev = EXCLUDED.home_team_abbrev,
      home_team_name = EXCLUDED.home_team_name,
      home_team_display_name = EXCLUDED.home_team_display_name,
      home_score = EXCLUDED.home_score,
      home_winner = EXCLUDED.home_winner,
      away_team_id = EXCLUDED.away_team_id,
      away_team_abbrev = EXCLUDED.away_team_abbrev,
      away_team_name = EXCLUDED.away_team_name,
      away_team_display_name = EXCLUDED.away_team_display_name,
      away_score = EXCLUDED.away_score,
      away_winner = EXCLUDED.away_winner,
      status_type_id = EXCLUDED.status_type_id,
      status_name = EXCLUDED.status_name,
      status_state = EXCLUDED.status_state,
      status_completed = EXCLUDED.status_completed,
      status_period = EXCLUDED.status_period,
      status_clock = EXCLUDED.status_clock,
      broadcast = EXCLUDED.broadcast,
      raw_event = EXCLUDED.raw_event;
    """

    def flush_rows(cur: psycopg.Cursor, rows: list[tuple[Any, ...]]) -> int:
        if not rows:
            return 0
        cur.executemany(upsert_sql, rows)
        return len(rows)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            pending_rows: list[tuple[Any, ...]] = []
            for i, fk in enumerate(files, start=1):
                now = time.monotonic()
                if hb > 0 and (now - last_hb) >= hb:
                    print(
                        f"[load_espn_scoreboard] heartbeat file={i}/{len(files)} total_files={total_files} total_events={total_events} "
                        f"upserts={total_upserts} errors={total_errors}",
                        flush=True,
                    )
                    last_hb = now

                try:
                    obj = json.loads(fk.path.read_text(encoding="utf-8"))
                    events = obj.get("events")
                    if not isinstance(events, list):
                        if args.verbose:
                            print(f"[load_espn_scoreboard] skip file={fk.path} reason=no_events_list", flush=True)
                        total_files += 1
                        continue

                    file_events = 0
                    file_upserts = 0
                    for ev in events:
                        if not isinstance(ev, dict):
                            continue

                        event_id = ev.get("id")
                        if not event_id:
                            continue
                        file_events += 1

                        # Extract season info
                        season_obj = ev.get("season") or {}
                        season_year = _to_int(season_obj.get("year"))
                        season_type = _to_int(season_obj.get("type"))
                        season_slug = season_obj.get("slug")

                        # Extract first competition (there's usually just one)
                        competitions = ev.get("competitions") or []
                        comp = competitions[0] if competitions else {}
                        competition_id = comp.get("id")

                        # Extract venue
                        venue = comp.get("venue") or {}
                        venue_address = venue.get("address") or {}

                        # Extract competitors (home/away)
                        competitors = comp.get("competitors") or []
                        home = _find_competitor(competitors, "home") or {}
                        away = _find_competitor(competitors, "away") or {}

                        home_team = home.get("team") or {}
                        away_team = away.get("team") or {}

                        # Extract status
                        status = ev.get("status") or comp.get("status") or {}
                        status_type = status.get("type") or {}

                        # Extract broadcast
                        broadcasts = comp.get("broadcasts") or []
                        broadcast_names = []
                        for b in broadcasts:
                            names = b.get("names") or []
                            broadcast_names.extend(names)
                        broadcast = ", ".join(broadcast_names) if broadcast_names else comp.get("broadcast")

                        row = (
                            str(event_id),
                            fk.scoreboard_date,
                            ev.get("uid"),
                            _parse_timestamp(ev.get("date")),
                            ev.get("name"),
                            ev.get("shortName"),
                            season_year,
                            season_type,
                            season_slug,
                            competition_id,
                            venue.get("id"),
                            venue.get("fullName"),
                            venue_address.get("city"),
                            venue_address.get("state"),
                            _to_bool(comp.get("neutralSite")),
                            _to_int(comp.get("attendance")),
                            home_team.get("id"),
                            home_team.get("abbreviation"),
                            home_team.get("name"),
                            home_team.get("displayName"),
                            _to_int(home.get("score")),
                            _to_bool(home.get("winner")),
                            away_team.get("id"),
                            away_team.get("abbreviation"),
                            away_team.get("name"),
                            away_team.get("displayName"),
                            _to_int(away.get("score")),
                            _to_bool(away.get("winner")),
                            status_type.get("id"),
                            status_type.get("name"),
                            status_type.get("state"),
                            _to_bool(status_type.get("completed")),
                            _to_int(status.get("period")),
                            status.get("displayClock"),
                            broadcast,
                            json.dumps(ev),
                        )
                        pending_rows.append(row)
                        if len(pending_rows) >= rows_per_batch:
                            file_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()

                    total_files += 1
                    total_events += file_events
                    total_upserts += file_upserts

                    if args.verbose:
                        print(
                            f"[load_espn_scoreboard] file={i}/{len(files)} date={fk.scoreboard_date} "
                            f"events={file_events} upserts={file_upserts} path={fk.path}",
                            flush=True,
                        )

                    if (total_files % commit_every) == 0:
                        if pending_rows:
                            total_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()
                        conn.commit()
                        print(
                            f"[load_espn_scoreboard] commit files={total_files} events={total_events} upserts={total_upserts} errors={total_errors}",
                            flush=True,
                        )

                except Exception as e:
                    total_files += 1
                    total_errors += 1
                    msg = str(e).replace("\n", "\\n")
                    print(f"[load_espn_scoreboard] ERROR file={fk.path} err={msg}", flush=True)
                    conn.rollback()
                    pending_rows.clear()
                    continue

            if pending_rows:
                total_upserts += flush_rows(cur, pending_rows)
                pending_rows.clear()
            conn.commit()

    print(
        f"[load_espn_scoreboard] done files={total_files} events={total_events} upserts={total_upserts} errors={total_errors}",
        flush=True,
    )
    return 0 if total_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())



