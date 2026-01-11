#!/usr/bin/env python3
"""
Load ESPN probabilities payload items[] into Postgres as JSON-identical rows.

Input files:
  data/raw/espn/probabilities/{season_label}/event_{event_id}_comp_{competition_id}.json

Output table:
  espn.probabilities_raw_items

Design goals:
  - resumable: uses UPSERT on a stable per-item key
  - verbose: frequent progress + per-file counters, configurable heartbeat
  - minimal assumptions: stores each item as raw JSONB, plus extracts common numeric fields for querying
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
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


PROB_FILE_RE = re.compile(r"^event_(?P<event>\d+)_comp_(?P<comp>\d+)\.json$")


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


def _parse_last_modified(s: Any) -> datetime | None:
    # ESPN examples: "2024-10-22T23:51Z" or "2024-10-22T23:51:07Z"
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


def _extract_play_id_from_ref(play_ref: str) -> int | None:
    m = re.search(r"/plays/(\d+)", str(play_ref))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


@dataclass(frozen=True)
class FileKey:
    season_label: str
    game_id: str
    path: Path


def _iter_prob_files(prob_dir: Path) -> list[FileKey]:
    if not prob_dir.exists():
        return []
    out: list[FileKey] = []
    for p in sorted(prob_dir.iterdir()):
        if not (p.is_file() and p.name.endswith(".json")):
            continue
        m = PROB_FILE_RE.match(p.name)
        if not m:
            continue
        game_id = m.group("comp")
        out.append(FileKey(season_label=str(prob_dir.name), game_id=str(game_id), path=p))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load ESPN probabilities items[] (raw JSON) into Postgres.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--season-label", default="", help="If set, only load this season (e.g. 2024-25).")
    p.add_argument("--probabilities-root", default="data/raw/espn/probabilities", help="Root dir containing season subdirs.")
    p.add_argument("--min-modified-time", help="Only process files modified after this ISO8601 datetime (e.g. 2025-12-24T01:00:00-08:00).")
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

    root = Path(args.probabilities_root)
    if args.season_label:
        season_dirs = [root / str(args.season_label)]
    else:
        season_dirs = [p for p in sorted(root.iterdir()) if p.is_dir()]

    # Gather files
    files: list[FileKey] = []
    for sd in season_dirs:
        files.extend(_iter_prob_files(sd))
    
    # Filter by modification time if provided
    if args.min_modified_time:
        try:
            min_time = datetime.fromisoformat(args.min_modified_time.replace('Z', '+00:00'))
            if min_time.tzinfo is None:
                min_time = min_time.replace(tzinfo=timezone.utc)
            original_count = len(files)
            files = [
                fk for fk in files
                if datetime.fromtimestamp(fk.path.stat().st_mtime, tz=timezone.utc) >= min_time
            ]
            if args.verbose:
                print(f"[load_espn_prob_raw] Filtered to {len(files)} files modified after {min_time} (from {original_count} total)", flush=True)
        except Exception as e:
            print(f"[load_espn_prob_raw] WARNING: Failed to parse --min-modified-time '{args.min_modified_time}': {e}", flush=True)
    
    if args.limit_files and int(args.limit_files) > 0:
        files = files[: int(args.limit_files)]
    if not files:
        raise SystemExit(f"No probability files found under {root} (season_label={args.season_label or 'ALL'})")

    ts = _utc_now_iso()
    print(f"[load_espn_prob_raw] start ts={ts} seasons={len(season_dirs)} files={len(files)} root={root}", flush=True)

    last_hb = time.monotonic()
    hb = float(args.heartbeat_seconds or 0.0)
    commit_every = max(1, int(args.commit_every))
    rows_per_batch = max(1, int(args.rows_per_batch))

    total_files = 0
    total_items = 0
    total_upserts = 0
    total_errors = 0

    upsert_sql = """
    INSERT INTO espn.probabilities_raw_items (
      season_label, game_id,
      event_id, sequence_number, last_modified_utc,
      home_win_percentage, away_win_percentage, tie_percentage,
      spread_cover_prob_home, spread_push_prob, total_over_prob,
      play_ref, home_team_ref, away_team_ref, competition_ref, source_ref,
      raw_item
    )
    VALUES (
      %s,%s,
      %s,%s,%s,
      %s,%s,%s,
      %s,%s,%s,
      %s,%s,%s,%s,%s,
      %s
    )
    ON CONFLICT (season_label, game_id, sequence_number, event_id)
    DO UPDATE SET
      last_modified_utc = EXCLUDED.last_modified_utc,
      home_win_percentage = EXCLUDED.home_win_percentage,
      away_win_percentage = EXCLUDED.away_win_percentage,
      tie_percentage = EXCLUDED.tie_percentage,
      spread_cover_prob_home = EXCLUDED.spread_cover_prob_home,
      spread_push_prob = EXCLUDED.spread_push_prob,
      total_over_prob = EXCLUDED.total_over_prob,
      play_ref = EXCLUDED.play_ref,
      home_team_ref = EXCLUDED.home_team_ref,
      away_team_ref = EXCLUDED.away_team_ref,
      competition_ref = EXCLUDED.competition_ref,
      source_ref = EXCLUDED.source_ref,
      raw_item = EXCLUDED.raw_item;
    """

    def flush_rows(cur: psycopg.Cursor, rows: list[tuple[Any, ...]]) -> int:
        """
        Execute a batch of upserts.

        Note: executemany still executes one statement per row on the server, but it
        significantly reduces Python-level overhead and can reuse server-side plans.
        """
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
                        f"[load_espn_prob_raw] heartbeat file={i}/{len(files)} total_files={total_files} total_items={total_items} "
                        f"upserts={total_upserts} errors={total_errors}",
                        flush=True,
                    )
                    last_hb = now

                try:
                    obj = json.loads(fk.path.read_text(encoding="utf-8"))
                    items = obj.get("items")
                    if not isinstance(items, list):
                        if args.verbose:
                            print(f"[load_espn_prob_raw] skip file={fk.path} reason=no_items_list", flush=True)
                        total_files += 1
                        continue

                    file_items = 0
                    file_upserts = 0
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        file_items += 1

                        seq = _to_int(it.get("sequenceNumber"))
                        last_mod = _parse_last_modified(it.get("lastModified"))

                        play_ref = _extract_ref(it.get("play"))
                        play_id = _extract_play_id_from_ref(play_ref) if play_ref else None

                        row = (
                            fk.season_label,
                            fk.game_id,
                            play_id,
                            seq,
                            last_mod,
                            _to_float(it.get("homeWinPercentage")),
                            _to_float(it.get("awayWinPercentage")),
                            _to_float(it.get("tiePercentage")),
                            _to_float(it.get("spreadCoverProbHome")),
                            _to_float(it.get("spreadPushProb")),
                            _to_float(it.get("totalOverProb")),
                            play_ref,
                            _extract_ref(it.get("homeTeam")),
                            _extract_ref(it.get("awayTeam")),
                            _extract_ref(it.get("competition")),
                            _extract_ref(it.get("source")),
                            json.dumps(it),  # jsonb via cast by psycopg
                        )
                        pending_rows.append(row)
                        if len(pending_rows) >= rows_per_batch:
                            file_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()

                    total_files += 1
                    total_items += file_items
                    # If we only flushed some rows due to hitting the batch limit,
                    # file_upserts reflects those; add any remaining rows at the end of the run.
                    total_upserts += file_upserts

                    if args.verbose:
                        print(
                            f"[load_espn_prob_raw] file={i}/{len(files)} season={fk.season_label} game_id={fk.game_id} "
                            f"items={file_items} upserts={file_upserts} path={fk.path}",
                            flush=True,
                        )

                    if (total_files % commit_every) == 0:
                        # Flush before committing so the counters reflect what's durable.
                        if pending_rows:
                            total_upserts += flush_rows(cur, pending_rows)
                            pending_rows.clear()
                        conn.commit()
                        print(
                            f"[load_espn_prob_raw] commit files={total_files} items={total_items} upserts={total_upserts} errors={total_errors}",
                            flush=True,
                        )

                except Exception as e:
                    total_files += 1
                    total_errors += 1
                    msg = str(e).replace("\n", "\\n")
                    print(f"[load_espn_prob_raw] ERROR file={fk.path} err={msg}", flush=True)
                    conn.rollback()
                    pending_rows.clear()
                    continue

            if pending_rows:
                total_upserts += flush_rows(cur, pending_rows)
                pending_rows.clear()
            conn.commit()

    print(
        f"[load_espn_prob_raw] done files={total_files} items={total_items} upserts={total_upserts} errors={total_errors}",
        flush=True,
    )
    return 0 if total_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


