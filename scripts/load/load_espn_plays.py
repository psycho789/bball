#!/usr/bin/env python3
"""
Load ESPN plays payload items[] into Postgres as JSON-identical rows.

Input files:
  data/raw/espn/plays/{season_label}/event_{event_id}_comp_{competition_id}_plays.json

Output table:
  derived.espn_plays

Design goals:
  - resumable: uses UPSERT on a stable per-play key
  - verbose: frequent progress + per-file counters, configurable heartbeat
  - minimal assumptions: stores each play as raw JSONB, plus extracts common fields for querying
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


PLAYS_FILE_RE = re.compile(r"^event_(?P<event>\d+)_comp_(?P<comp>\d+)_plays\.json$")


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


def _to_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
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
    """Parse ESPN timestamp like '2024-10-22T23:51Z' or '2024-10-22T23:51:07Z'."""
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


def _extract_ref(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    ref = obj.get("$ref")
    if not isinstance(ref, str) or not ref:
        return None
    return ref


@dataclass(frozen=True)
class FileKey:
    season_label: str
    game_id: str
    path: Path


def _iter_plays_files(plays_dir: Path) -> list[FileKey]:
    if not plays_dir.exists():
        return []
    out: list[FileKey] = []
    for p in sorted(plays_dir.iterdir()):
        if not (p.is_file() and p.name.endswith(".json") and not p.name.endswith(".manifest.json")):
            continue
        m = PLAYS_FILE_RE.match(p.name)
        if not m:
            continue
        game_id = m.group("comp")
        out.append(FileKey(season_label=str(plays_dir.name), game_id=str(game_id), path=p))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load ESPN plays items[] (raw JSON) into Postgres.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--season-label", default="", help="If set, only load this season (e.g. 2024-25).")
    p.add_argument("--plays-root", default="data/raw/espn/plays", help="Root dir containing season subdirs.")
    p.add_argument("--limit-files", type=int, default=0, help="If >0, stop after N files.")
    p.add_argument("--commit-every", type=int, default=50, help="Commit every N files (default: 50).")
    p.add_argument(
        "--rows-per-batch",
        type=int,
        default=5000,
        help="Batch upserts into executemany() calls of this many rows (default: 5000).",
    )
    p.add_argument("--heartbeat-seconds", type=float, default=10.0, help="Print a progress heartbeat at least this often. 0 disables.")
    p.add_argument("--verbose", action="store_true", help="Print per-file details.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    root = Path(args.plays_root)
    if args.season_label:
        season_dirs = [root / str(args.season_label)]
    else:
        season_dirs = [p for p in sorted(root.iterdir()) if p.is_dir()]

    # Gather files
    files: list[FileKey] = []
    for sd in season_dirs:
        files.extend(_iter_plays_files(sd))
    if args.limit_files and int(args.limit_files) > 0:
        files = files[: int(args.limit_files)]
    if not files:
        raise SystemExit(f"No plays files found under {root} (season_label={args.season_label or 'ALL'})")

    ts = _utc_now_iso()
    print(f"[load_espn_plays] start ts={ts} seasons={len(season_dirs)} files={len(files)} root={root}", flush=True)

    last_hb = time.monotonic()
    hb = float(args.heartbeat_seconds or 0.0)
    commit_every = max(1, int(args.commit_every))
    rows_per_batch = max(1, int(args.rows_per_batch))

    total_files = 0
    total_items = 0
    total_upserts = 0
    total_errors = 0

    upsert_sql = """
    INSERT INTO derived.espn_plays (
      season_label, game_id, play_id,
      sequence_number, play_type_id, play_type_text,
      text, short_text,
      period, clock_seconds, clock_display,
      home_score, away_score, score_value,
      is_scoring_play, is_shooting_play, points_attempted,
      coordinate_x, coordinate_y,
      team_ref, wallclock, modified,
      raw_play
    )
    VALUES (
      %s,%s,%s,
      %s,%s,%s,
      %s,%s,
      %s,%s,%s,
      %s,%s,%s,
      %s,%s,%s,
      %s,%s,
      %s,%s,%s,
      %s
    )
    ON CONFLICT (season_label, game_id, play_id)
    DO UPDATE SET
      sequence_number = EXCLUDED.sequence_number,
      play_type_id = EXCLUDED.play_type_id,
      play_type_text = EXCLUDED.play_type_text,
      text = EXCLUDED.text,
      short_text = EXCLUDED.short_text,
      period = EXCLUDED.period,
      clock_seconds = EXCLUDED.clock_seconds,
      clock_display = EXCLUDED.clock_display,
      home_score = EXCLUDED.home_score,
      away_score = EXCLUDED.away_score,
      score_value = EXCLUDED.score_value,
      is_scoring_play = EXCLUDED.is_scoring_play,
      is_shooting_play = EXCLUDED.is_shooting_play,
      points_attempted = EXCLUDED.points_attempted,
      coordinate_x = EXCLUDED.coordinate_x,
      coordinate_y = EXCLUDED.coordinate_y,
      team_ref = EXCLUDED.team_ref,
      wallclock = EXCLUDED.wallclock,
      modified = EXCLUDED.modified,
      raw_play = EXCLUDED.raw_play;
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
                        f"[load_espn_plays] heartbeat file={i}/{len(files)} total_files={total_files} total_items={total_items} "
                        f"upserts={total_upserts} errors={total_errors}",
                        flush=True,
                    )
                    last_hb = now

                try:
                    obj = json.loads(fk.path.read_text(encoding="utf-8"))
                    items = obj.get("items")
                    if not isinstance(items, list):
                        if args.verbose:
                            print(f"[load_espn_plays] skip file={fk.path} reason=no_items_list", flush=True)
                        total_files += 1
                        continue

                    file_items = 0
                    file_upserts = 0
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        file_items += 1

                        play_id = _to_int(it.get("id"))
                        if play_id is None:
                            continue  # Skip items without a play ID

                        # Extract type info
                        play_type = it.get("type") or {}
                        play_type_id = _to_int(play_type.get("id"))
                        play_type_text = play_type.get("text")

                        # Extract period info
                        period_obj = it.get("period") or {}
                        period = _to_int(period_obj.get("number"))

                        # Extract clock info
                        clock_obj = it.get("clock") or {}
                        clock_seconds = _to_float(clock_obj.get("value"))
                        clock_display = clock_obj.get("displayValue")

                        # Extract coordinate info (may have sentinel values like -214748340)
                        coord_obj = it.get("coordinate") or {}
                        coord_x = _to_int(coord_obj.get("x"))
                        coord_y = _to_int(coord_obj.get("y"))
                        # Filter out sentinel values
                        if coord_x is not None and abs(coord_x) > 100000:
                            coord_x = None
                        if coord_y is not None and abs(coord_y) > 100000:
                            coord_y = None

                        row = (
                            fk.season_label,
                            fk.game_id,
                            play_id,
                            _to_int(it.get("sequenceNumber")),
                            play_type_id,
                            play_type_text,
                            it.get("text"),
                            it.get("shortText"),
                            period,
                            clock_seconds,
                            clock_display,
                            _to_int(it.get("homeScore")),
                            _to_int(it.get("awayScore")),
                            _to_int(it.get("scoreValue")),
                            _to_bool(it.get("scoringPlay")),
                            _to_bool(it.get("shootingPlay")),
                            _to_int(it.get("pointsAttempted")),
                            coord_x,
                            coord_y,
                            _extract_ref(it.get("team")),
                            _parse_timestamp(it.get("wallclock")),
                            _parse_timestamp(it.get("modified")),
                            json.dumps(it),
                        )
                        pending_rows.append(row)
                        if len(pending_rows) >= rows_per_batch:
                            file_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()

                    total_files += 1
                    total_items += file_items
                    total_upserts += file_upserts

                    if args.verbose:
                        print(
                            f"[load_espn_plays] file={i}/{len(files)} season={fk.season_label} game_id={fk.game_id} "
                            f"items={file_items} upserts={file_upserts} path={fk.path}",
                            flush=True,
                        )

                    if (total_files % commit_every) == 0:
                        if pending_rows:
                            total_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()
                        conn.commit()
                        print(
                            f"[load_espn_plays] commit files={total_files} items={total_items} upserts={total_upserts} errors={total_errors}",
                            flush=True,
                        )

                except Exception as e:
                    total_files += 1
                    total_errors += 1
                    msg = str(e).replace("\n", "\\n")
                    print(f"[load_espn_plays] ERROR file={fk.path} err={msg}", flush=True)
                    conn.rollback()
                    pending_rows.clear()
                    continue

            if pending_rows:
                total_upserts += flush_rows(cur, pending_rows)
                pending_rows.clear()
            conn.commit()

    print(
        f"[load_espn_plays] done files={total_files} items={total_items} upserts={total_upserts} errors={total_errors}",
        flush=True,
    )
    return 0 if total_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())







