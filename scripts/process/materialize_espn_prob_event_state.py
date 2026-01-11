#!/usr/bin/env python3
"""
Materialize a compact ESPN per-play game state table (plus win probability time series) for modeling/analysis.

Writes into:
  espn.prob_event_state(
    game_id, event_id, point_differential, time_remaining,
    possession_side, home_score, away_score, current_winning_team, final_winning_team
  )

Source files:
  data/raw/espn/probabilities/{season_label}/event_{event_id}_comp_{competition_id}.json

This script fetches ESPN play payloads referenced by the probabilities file and caches them locally:
  data/raw/espn/plays/{season_label}/play_{play_id}.json (+ manifest)

Usage:
  python scripts/materialize_espn_prob_event_state.py --dsn "$DATABASE_URL" --season-label 2024-25 --limit-games 10
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


PROB_FILE_RE = re.compile(r"^event_(?P<event>\d+)_comp_(?P<comp>\d+)\.json$")


@dataclass(frozen=True)
class ProbRow:
    play_ref: str
    play_id: int
    sequence_number: int


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


def _safe_prefix(body: bytes, limit: int = 500) -> str:
    try:
        s = body[:limit].decode("utf-8", errors="replace")
    except Exception:
        s = repr(body[:limit])
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _extract_play_id_from_ref(play_ref: str) -> int | None:
    # Example:
    #   http://sports.core.api.espn.com/.../plays/4017033704?lang=en&region=us
    m = re.search(r"/plays/(\d+)", str(play_ref))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _extract_team_id_from_ref(team_ref: str) -> int | None:
    # Example:
    #   http://sports.core.api.espn.com/.../seasons/2025/teams/16?lang=en&region=us
    m = re.search(r"/teams/(\d+)", str(team_ref))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _team_side(team_id: int | None, *, home_team_id: int | None, away_team_id: int | None) -> int | None:
    # 0=home, 1=away
    if team_id is None or home_team_id is None or away_team_id is None:
        return None
    if team_id == home_team_id:
        return 0
    if team_id == away_team_id:
        return 1
    return None


def _infer_possession_side_from_play(
    play_obj: dict[str, Any],
    *,
    home_team_id: int | None,
    away_team_id: int | None,
) -> int | None:
    """
    Best-effort possession inference.

    ESPN play payloads do not provide a canonical "possession" field. However, for certain event categories
    the play-level `team` field is strongly associated with the possessing side (shots/FTs, rebounds, turnovers,
    jump balls). For everything else (timeouts, substitutions, many fouls/violations), return NULL.
    """
    team = play_obj.get("team")
    team_ref = team.get("$ref") if isinstance(team, dict) else None
    team_id = _extract_team_id_from_ref(str(team_ref)) if team_ref else None
    side = _team_side(team_id, home_team_id=home_team_id, away_team_id=away_team_id)
    if side is None:
        return None

    t = play_obj.get("type")
    ttext = t.get("text") if isinstance(t, dict) else None

    # Explicit and high-signal categories.
    if ttext == "Jumpball":
        return side
    if isinstance(ttext, str) and "Rebound" in ttext:
        return side
    if isinstance(ttext, str) and "Turnover" in ttext:
        return side
    if isinstance(ttext, str) and "Free Throw" in ttext:
        return side

    # Shot attempts (ESPN uses many granular shot type.text values, so rely on flags).
    if bool(play_obj.get("shootingPlay")):
        return side

    # Some payloads include numeric hints (keep conservative).
    pts_attempted = _to_int(play_obj.get("pointsAttempted"))
    if pts_attempted is not None and pts_attempted > 0:
        return side

    return None


def _iter_prob_files(prob_dir: Path) -> list[Path]:
    if not prob_dir.exists():
        return []
    out = [p for p in sorted(prob_dir.iterdir()) if p.is_file() and p.name.endswith(".json") and PROB_FILE_RE.match(p.name)]
    return out


def _load_prob_rows(prob_path: Path) -> tuple[str, str, int | None, int | None, list[ProbRow]]:
    m = PROB_FILE_RE.match(prob_path.name)
    if not m:
        raise RuntimeError(f"Unexpected probabilities filename: {prob_path.name}")
    espn_event_id = m.group("event")
    espn_competition_id = m.group("comp")

    obj = json.loads(prob_path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("probabilities file must be a JSON object")
    items = obj.get("items")
    if not isinstance(items, list):
        raise RuntimeError("probabilities file missing items[]")

    # Home/away team mapping is provided on each probability item. Extract from first usable entry.
    home_team_id: int | None = None
    away_team_id: int | None = None
    for it in items:
        if not isinstance(it, dict):
            continue
        ht = it.get("homeTeam")
        at = it.get("awayTeam")
        ht_ref = ht.get("$ref") if isinstance(ht, dict) else None
        at_ref = at.get("$ref") if isinstance(at, dict) else None
        home_team_id = _extract_team_id_from_ref(str(ht_ref)) if ht_ref else None
        away_team_id = _extract_team_id_from_ref(str(at_ref)) if at_ref else None
        if home_team_id is not None and away_team_id is not None:
            break

    rows: list[ProbRow] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        play = it.get("play") or {}
        play_ref = play.get("$ref") if isinstance(play, dict) else None
        if not play_ref:
            continue
        play_id = _extract_play_id_from_ref(str(play_ref))
        seq = _to_int(it.get("sequenceNumber"))
        if play_id is None or seq is None:
            continue

        rows.append(
            ProbRow(
                play_ref=str(play_ref),
                play_id=int(play_id),
                sequence_number=int(seq),
            )
        )

    # de-dupe (play_id can appear multiple times)
    rows.sort(key=lambda r: (r.sequence_number, r.play_id))
    seen: set[int] = set()
    uniq: list[ProbRow] = []
    for r in rows:
        if r.play_id in seen:
            continue
        seen.add(r.play_id)
        uniq.append(r)
    return espn_event_id, espn_competition_id, home_team_id, away_team_id, uniq


def _plays_collection_url(espn_event_id: str, espn_competition_id: str) -> str:
    # Return full play objects in items[] (plus refs); usually paginated.
    return (
        "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
        f"/events/{espn_event_id}/competitions/{espn_competition_id}/plays?limit=1000&lang=en&region=us"
    )


def _fetch_game_plays_cached(
    *,
    espn_event_id: str,
    espn_competition_id: str,
    plays_dir: Path,
    retry: HttpRetry,
    overwrite: bool,
    fetched_at: str,
) -> list[dict[str, Any]]:
    """
    Fetch the game-level plays collection once per competition and cache it locally.

    Returns items[] as a list of play objects.
    """
    url = _plays_collection_url(espn_event_id, espn_competition_id)
    out_path = plays_dir / f"event_{espn_event_id}_comp_{espn_competition_id}_plays.json"
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")

    if (not overwrite) and out_path.exists() and manifest_path.exists():
        obj = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        status, resp_headers, body = http_get_bytes(url, retry=retry, allow_non_200=True)
        if status != 200:
            ct = str(resp_headers.get("content-type") or "").replace("\\", "\\\\").replace('"', '\\"')
            raise RuntimeError(f"HTTP {status} content_type={ct} body_prefix={_safe_prefix(body)} url={url}")
        obj = parse_json_bytes(body)
        write_with_manifest(
            out_path,
            manifest_path,
            url=url,
            http_status=status,
            response_headers=resp_headers,
            body=body,
            source_type="espn_plays",
            source_key=f"{espn_event_id}:{espn_competition_id}",
            fetched_at_utc=fetched_at,
        )

    items = obj.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected plays payload (missing items[]): {out_path}")
    plays: list[dict[str, Any]] = [p for p in items if isinstance(p, dict)]
    return plays


def _fetch_play_cached(play_ref: str, *, plays_dir: Path, retry: HttpRetry, overwrite: bool, fetched_at: str) -> dict[str, Any]:
    play_id = _extract_play_id_from_ref(play_ref)
    if play_id is None:
        raise RuntimeError(f"Could not parse play id from ref: {play_ref}")

    out_path = plays_dir / f"play_{play_id}.json"
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")

    if (not overwrite) and out_path.exists() and manifest_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    status, resp_headers, body = http_get_bytes(play_ref, retry=retry, allow_non_200=True)
    if status != 200:
        ct = str(resp_headers.get("content-type") or "").replace("\\", "\\\\").replace('"', '\\"')
        raise RuntimeError(f"HTTP {status} content_type={ct} body_prefix={_safe_prefix(body)} ref={play_ref}")

    obj = parse_json_bytes(body)
    write_with_manifest(
        out_path,
        manifest_path,
        url=play_ref,
        http_status=status,
        response_headers=resp_headers,
        body=body,
        source_type="espn_play",
        source_key=str(play_id),
        fetched_at_utc=fetched_at,
    )
    return obj


def _seconds_remaining_game(period: int, clock_seconds: int, max_period: int) -> int | None:
    if period <= 0 or clock_seconds < 0 or max_period <= 0:
        return None
    # regulation: 4 * 12min; overtime: 5min each
    if max_period < 4:
        max_period = 4
    ot_count = max(0, max_period - 4)
    if period <= 4:
        return (4 - period) * 720 + clock_seconds + ot_count * 300
    # overtime period numbers: 5,6,...
    return max(0, (max_period - period) * 300 + clock_seconds)


def _winning_side(home_score: int | None, away_score: int | None) -> int | None:
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return 0
    if home_score < away_score:
        return 1
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Populate espn.prob_event_state from ESPN probabilities + plays.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--season-label", default="2024-25", help="Season label used in data/raw/espn/* subdirs.")
    p.add_argument("--probabilities-dir", default="", help="Override probabilities dir (default: data/raw/espn/probabilities/{season}).")
    p.add_argument("--plays-dir", default="", help="Override plays cache dir (default: data/raw/espn/plays/{season}).")
    p.add_argument(
        "--overwrite-plays",
        action="store_true",
        help="Re-fetch cached play payloads (and game-level plays collections) even if cached.",
    )
    p.add_argument("--overwrite-db", action="store_true", help="Delete+reinsert for competitions already present.")
    p.add_argument("--limit-games", type=int, default=0, help="Limit number of competition files processed (0=no limit).")
    p.add_argument("--throttle-seconds", type=float, default=0.1, help="Sleep between ESPN play fetches (best-effort).")
    p.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=15.0,
        help="Print a progress heartbeat at least this often. Set 0 to disable.",
    )
    p.add_argument(
        "--play-progress-every",
        type=int,
        default=50,
        help="While fetching plays for a competition, print progress every N plays. 0 disables.",
    )
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0)
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    season = str(args.season_label)
    prob_dir = Path(args.probabilities_dir) if args.probabilities_dir else Path("data/raw/espn/probabilities") / season
    plays_dir = Path(args.plays_dir) if args.plays_dir else Path("data/raw/espn/plays") / season
    plays_dir.mkdir(parents=True, exist_ok=True)

    prob_files = _iter_prob_files(prob_dir)
    if args.limit_games and args.limit_games > 0:
        prob_files = prob_files[: args.limit_games]
    if not prob_files:
        raise SystemExit(f"No probabilities files found in {prob_dir}")

    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )
    fetched_at = utc_now_iso_compact()

    total_rows = 0
    total_games = 0
    last_heartbeat = time.monotonic()

    print(f"[espn_materialize] start season={season} prob_dir={prob_dir} plays_dir={plays_dir} files={len(prob_files)}", flush=True)

    with psycopg.connect(dsn) as conn:
        for i, prob_path in enumerate(prob_files, start=1):
            espn_event_id, espn_comp_id, home_team_id, away_team_id, prob_rows = _load_prob_rows(prob_path)
            if not prob_rows:
                if args.verbose:
                    print(f"[{i}/{len(prob_files)}] {prob_path.name}: no usable items[]", flush=True)
                continue

            print(f"[{i}/{len(prob_files)}] comp={espn_comp_id} plays_in_prob={len(prob_rows)}", flush=True)

            # Check if game already exists
            already = conn.execute(
                "SELECT 1 FROM espn.prob_event_state WHERE game_id=%s LIMIT 1;",
                (espn_comp_id,),
            ).fetchone()
            
            if already:
                if not args.overwrite_db:
                    if args.verbose:
                        print(f"[{i}/{len(prob_files)}] {prob_path.name}: already materialized (skip)", flush=True)
                    continue
                else:
                    print(f"[{i}/{len(prob_files)}] comp={espn_comp_id}: game exists, will overwrite", flush=True)
            else:
                print(f"[{i}/{len(prob_files)}] comp={espn_comp_id}: new game, will insert", flush=True)

            # Fetch game-level plays collection once and index by play_id
            game_plays = _fetch_game_plays_cached(
                espn_event_id=espn_event_id,
                espn_competition_id=espn_comp_id,
                plays_dir=plays_dir,
                retry=retry,
                overwrite=bool(args.overwrite_plays),
                fetched_at=fetched_at,
            )
            plays_by_id: dict[int, dict[str, Any]] = {}
            max_period = 0
            final_home = None
            final_away = None
            max_seq_all = -1
            for p in game_plays:
                pid = _to_int(p.get("id"))
                if pid is None:
                    continue
                plays_by_id[int(pid)] = p
                per = p.get("period", {})
                per_num = _to_int(per.get("number") if isinstance(per, dict) else None) or 0
                if per_num > max_period:
                    max_period = per_num
                seq = _to_int(p.get("sequenceNumber")) or -1
                if seq > max_seq_all:
                    max_seq_all = seq
                    final_home = _to_int(p.get("homeScore"))
                    final_away = _to_int(p.get("awayScore"))

            # Fallback: ensure we can resolve plays referenced in probabilities (rarely missing)
            missing = [r for r in prob_rows if r.play_id not in plays_by_id]
            if missing:
                print(f"[{i}/{len(prob_files)}] comp={espn_comp_id} missing_plays={len(missing)} (fallback fetch)", flush=True)
            for j, r in enumerate(missing, start=1):
                now = time.monotonic()
                if args.heartbeat_seconds and args.heartbeat_seconds > 0 and (now - last_heartbeat) >= args.heartbeat_seconds:
                    print(
                        f"[espn_materialize] heartbeat file={i}/{len(prob_files)} comp={espn_comp_id} "
                        f"fetched_missing={j-1}/{len(missing)} total_rows={total_rows}",
                        flush=True,
                    )
                    last_heartbeat = now
                if args.play_progress_every and args.play_progress_every > 0 and (j % int(args.play_progress_every) == 0):
                    print(f"[{i}/{len(prob_files)}] comp={espn_comp_id} fetched_missing={j}/{len(missing)}", flush=True)

                play_obj = _fetch_play_cached(
                    r.play_ref,
                    plays_dir=plays_dir,
                    retry=retry,
                    overwrite=bool(args.overwrite_plays),
                    fetched_at=fetched_at,
                )
                plays_by_id[r.play_id] = play_obj

                # Throttle only when we actually perform a network fetch.
                if args.throttle_seconds and args.throttle_seconds > 0:
                    time.sleep(args.throttle_seconds)

            final_winner = _winning_side(final_home, final_away)

            rows_to_insert: list[tuple[Any, ...]] = []
            for r in prob_rows:
                play_obj = plays_by_id.get(r.play_id)
                if not isinstance(play_obj, dict):
                    continue
                home_score = _to_int(play_obj.get("homeScore"))
                away_score = _to_int(play_obj.get("awayScore"))
                point_diff = (home_score or 0) - (away_score or 0)

                p = play_obj.get("period", {})
                period_num = _to_int(p.get("number") if isinstance(p, dict) else None)

                clock = play_obj.get("clock", {})
                clock_val = _to_float(clock.get("value") if isinstance(clock, dict) else None)
                clock_seconds = int(round(clock_val)) if clock_val is not None else None

                time_remaining = (
                    _seconds_remaining_game(int(period_num or 0), int(clock_seconds or 0), int(max_period or 0))
                    if period_num is not None and clock_seconds is not None
                    else None
                )

                current_winner = _winning_side(home_score, away_score)

                possession_side = _infer_possession_side_from_play(
                    play_obj,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                )

                rows_to_insert.append(
                    (
                        espn_comp_id,  # game_id (ESPN competition id)
                        int(r.play_id),  # event_id (ESPN play id)
                        int(point_diff),
                        time_remaining,
                        home_score,
                        away_score,
                        current_winner,
                        final_winner,
                        possession_side,
                    )
                )

            with conn.transaction():
                with conn.cursor() as cur:
                    # Only delete if game exists and we're overwriting
                    if already and args.overwrite_db:
                        cur.execute("DELETE FROM espn.prob_event_state WHERE game_id=%s;", (espn_comp_id,))
                    
                    # Insert new rows (for new games or after deletion for overwrites)
                    if rows_to_insert:
                        cur.executemany(
                            """
                            INSERT INTO espn.prob_event_state (
                              game_id, event_id, point_differential, time_remaining,
                              home_score, away_score, current_winning_team, final_winning_team, possession_side
                            )
                            VALUES (
                              %s,%s,%s,%s,
                              %s,%s,%s,%s,%s
                            )
                            """,
                            rows_to_insert,
                        )

            total_rows += len(rows_to_insert)
            total_games += 1
            print(f"[{i}/{len(prob_files)}] materialized comp={espn_comp_id} rows={len(rows_to_insert)} final={final_home}-{final_away}")

    print(f"Done. competitions={total_games} rows={total_rows} prob_dir={prob_dir} plays_dir={plays_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


