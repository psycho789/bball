#!/usr/bin/env python3
"""
Backfill ESPN NBA game probability data for a season by:
  1) fetching ESPN scoreboard for each date in a date range
  2) extracting (event_id, competition_id) pairs
  3) fetching ESPN core "probabilities" JSON for each pair

Output layout (recommended):
  data/raw/espn/scoreboard/scoreboard_{YYYYMMDD}.json
  data/raw/espn/probabilities/{season_label}/event_{event_id}_comp_{competition_id}.json

This mirrors the repo's "raw JSON + .manifest.json" archive pattern.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


ESPN_SCOREBOARD_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_PROBABILITIES_BASE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"


@dataclass(frozen=True)
class EventKey:
    event_id: str
    competition_id: str
    date_yyyymmdd: str


def _ts() -> str:
    # Compact UTC timestamp for log lines.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_yyyymmdd(s: str) -> date:
    s2 = s.strip()
    if len(s2) != 8 or not s2.isdigit():
        raise ValueError("Expected YYYYMMDD")
    return datetime.strptime(s2, "%Y%m%d").date()


def _iter_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end-date must be >= start-date")
    out: list[date] = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


def _extract_event_keys(scoreboard_obj: dict[str, Any]) -> list[EventKey]:
    events = scoreboard_obj.get("events")
    if not isinstance(events, list):
        return []
    out: list[EventKey] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        event_id = str(ev.get("id") or "").strip()
        if not event_id:
            continue
        competitions = ev.get("competitions")
        if not isinstance(competitions, list) or not competitions:
            continue
        comp0 = competitions[0]
        if not isinstance(comp0, dict):
            continue
        competition_id = str(comp0.get("id") or "").strip()
        if not competition_id:
            continue
        # date is filled by caller (scoreboard payload itself doesn't guarantee a stable date field)
        out.append(EventKey(event_id=event_id, competition_id=competition_id, date_yyyymmdd=""))
    # de-dupe while preserving order
    seen: set[str] = set()
    uniq: list[EventKey] = []
    for k in out:
        key = f"{k.event_id}:{k.competition_id}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(k)
    return uniq


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill ESPN NBA probabilities (win/game probability) for a date range.")
    p.add_argument("--season-label", default="2024-25", help="Used for output subdir, e.g. 2024-25")
    p.add_argument("--start-date", default="20241001", help="YYYYMMDD (default: 20241001)")
    p.add_argument("--end-date", default="20250630", help="YYYYMMDD (default: 20250630)")
    p.add_argument("--out-root", default="data/raw/espn", help="Root output directory (default: data/raw/espn)")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON files (and manifests).")
    p.add_argument("--max-games", type=int, default=0, help="If > 0, stop after writing this many probabilities files.")
    p.add_argument("--throttle-seconds", type=float, default=0.2, help="Sleep between HTTP requests (best-effort).")
    p.add_argument("--workers", type=int, default=12, help="Max concurrent probabilities fetch workers.")
    p.add_argument(
        "--requests-per-second",
        type=float,
        default=8.0,
        help="Global max request rate across workers (best-effort). Set 0 to disable rate limiting.",
    )
    p.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=15.0,
        help="Print a progress heartbeat at least this often (even without --verbose). Set 0 to disable.",
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Also print progress every N probabilities processed (written+skipped+errored). 0 disables.",
    )
    p.add_argument(
        "--error-log",
        default="data/reports/espn_probabilities_backfill_errors_{fetched_at_utc}.jsonl",
        help="Write per-game errors here (supports {fetched_at_utc}).",
    )
    p.add_argument("--stop-on-error", action="store_true", help="If set, abort on the first probabilities fetch error.")
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed per request (caps retries).")
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def _maybe_sleep(seconds: float) -> None:
    if seconds and seconds > 0:
        time.sleep(seconds)


class _RateLimiter:
    """
    Very small global rate limiter (best-effort) for HTTP GET requests.
    Enforces a minimum interval between requests across threads.
    """

    def __init__(self, requests_per_second: float) -> None:
        self._rps = float(requests_per_second)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._rps <= 0:
            return
        min_interval = 1.0 / self._rps
        while True:
            with self._lock:
                now = time.monotonic()
                if now >= self._next_allowed:
                    self._next_allowed = now + min_interval
                    return
                sleep_for = self._next_allowed - now
            if sleep_for > 0:
                time.sleep(sleep_for)


def _safe_prefix(body: bytes, limit: int = 500) -> str:
    """
    Best-effort short text prefix for logging/debugging.
    Escapes newlines so JSONL stays single-line.
    """
    try:
        s = body[:limit].decode("utf-8", errors="replace")
    except Exception:
        s = repr(body[:limit])
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _existing_with_manifest(path: Path) -> bool:
    return path.exists() and path.with_suffix(path.suffix + ".manifest.json").exists()


def _scoreboard_for_date(
    *,
    ymd: str,
    scoreboard_dir: Path,
    retry: HttpRetry,
    fetched_at: str,
    overwrite: bool,
    rate_limiter: _RateLimiter,
    throttle_seconds: float,
    verbose: bool,
) -> dict[str, Any]:
    scoreboard_path = scoreboard_dir / f"scoreboard_{ymd}.json"
    scoreboard_manifest = scoreboard_path.with_suffix(scoreboard_path.suffix + ".manifest.json")
    scoreboard_url = f"{ESPN_SCOREBOARD_BASE}?dates={ymd}&limit=1000"

    if overwrite or (not _existing_with_manifest(scoreboard_path)):
        if verbose:
            print(f"[{_ts()}] [espn] GET scoreboard ymd={ymd}", flush=True)
        rate_limiter.wait()
        status, resp_headers, body = http_get_bytes(scoreboard_url, retry=retry)
        scoreboard_obj = parse_json_bytes(body)
        write_with_manifest(
            scoreboard_path,
            scoreboard_manifest,
            url=scoreboard_url,
            http_status=status,
            response_headers=resp_headers,
            body=body,
            source_type="espn_scoreboard",
            source_key=ymd,
            fetched_at_utc=fetched_at,
        )
        _maybe_sleep(throttle_seconds)
        return scoreboard_obj

    return parse_json_bytes(scoreboard_path.read_bytes())


def _fetch_probabilities_one(
    *,
    k: EventKey,
    probs_dir: Path,
    retry: HttpRetry,
    fetched_at: str,
    overwrite: bool,
    rate_limiter: _RateLimiter,
    throttle_seconds: float,
    verbose: bool,
) -> tuple[str, EventKey, dict[str, Any] | None]:
    """
    Returns (status, k, error_record).
      status in {"written","skipped","error"}
      error_record is JSON-serializable when status=="error"
    """
    if not k.event_id.isdigit() or not k.competition_id.isdigit():
        return (
            "error",
            k,
            {
                "date": k.date_yyyymmdd,
                "event_id": k.event_id,
                "competition_id": k.competition_id,
                "error": "non-numeric ids",
            },
        )

    out_path = probs_dir / f"event_{k.event_id}_comp_{k.competition_id}.json"
    if (not overwrite) and _existing_with_manifest(out_path):
        return ("skipped", k, None)

    prob_url = f"{ESPN_PROBABILITIES_BASE}/events/{k.event_id}/competitions/{k.competition_id}/probabilities?limit=1000"
    try:
        if verbose:
            print(f"[{_ts()}] [espn] GET probabilities event={k.event_id} comp={k.competition_id} date={k.date_yyyymmdd}", flush=True)
        rate_limiter.wait()
        status, resp_headers, body = http_get_bytes(prob_url, retry=retry, allow_non_200=True)
        if status != 200:
            ct = str(resp_headers.get("content-type") or "").replace("\\", "\\\\").replace('"', '\\"')
            return (
                "error",
                k,
                {
                    "date": k.date_yyyymmdd,
                    "event_id": k.event_id,
                    "competition_id": k.competition_id,
                    "url": prob_url,
                    "http_status": int(status),
                    "content_type": ct,
                    "body_prefix": _safe_prefix(body),
                    "error": "HTTP non-200",
                },
            )

        _ = parse_json_bytes(body)  # validate parseable
        manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
        write_with_manifest(
            out_path,
            manifest_path,
            url=prob_url,
            http_status=status,
            response_headers=resp_headers,
            body=body,
            source_type="espn_probabilities",
            source_key=f"{k.event_id}:{k.competition_id}",
            fetched_at_utc=fetched_at,
        )
        _maybe_sleep(throttle_seconds)
        return ("written", k, None)
    except Exception as e:
        msg = str(e).replace("\\", "\\\\").replace('"', '\\"')
        return (
            "error",
            k,
            {
                "date": k.date_yyyymmdd,
                "event_id": k.event_id,
                "competition_id": k.competition_id,
                "url": prob_url,
                "error": msg,
            },
        )


def main() -> int:
    args = parse_args()

    start = _parse_yyyymmdd(args.start_date)
    end = _parse_yyyymmdd(args.end_date)
    dates = _iter_dates(start, end)

    out_root = Path(args.out_root)
    scoreboard_dir = out_root / "scoreboard"
    probs_dir = out_root / "probabilities" / str(args.season_label)
    scoreboard_dir.mkdir(parents=True, exist_ok=True)
    probs_dir.mkdir(parents=True, exist_ok=True)

    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )

    fetched_at = utc_now_iso_compact()
    error_log_path = Path(str(args.error_log).format(fetched_at_utc=fetched_at))
    error_log_path.parent.mkdir(parents=True, exist_ok=True)

    rate_limiter = _RateLimiter(float(args.requests_per_second or 0.0))
    workers = max(1, int(args.workers))

    written_prob_files = 0
    skipped_prob_files = 0
    total_event_pairs = 0
    total_prob_errors = 0
    total_prob_processed = 0
    last_heartbeat = time.monotonic()

    print(
        f"[{_ts()}] [espn] backfill start season={args.season_label} start={start.strftime('%Y%m%d')} end={end.strftime('%Y%m%d')} "
        f"days={len(dates)} out_root={out_root} error_log={error_log_path}",
        flush=True,
    )

    # (1) Build a deterministic task list by scanning scoreboards (cached if present).
    tasks: list[EventKey] = []
    for i, d in enumerate(dates):
        ymd = d.strftime("%Y%m%d")
        if (i == 0) or (i == len(dates) - 1) or ((i + 1) % 30 == 0):
            print(f"[{_ts()}] [espn] scoreboard_scan day={i+1}/{len(dates)} ymd={ymd}", flush=True)
        scoreboard_obj = _scoreboard_for_date(
            ymd=ymd,
            scoreboard_dir=scoreboard_dir,
            retry=retry,
            fetched_at=fetched_at,
            overwrite=bool(args.overwrite),
            rate_limiter=rate_limiter,
            throttle_seconds=float(args.throttle_seconds),
            verbose=bool(args.verbose),
        )
        keys = _extract_event_keys(scoreboard_obj)
        # annotate date
        keys = [EventKey(event_id=k.event_id, competition_id=k.competition_id, date_yyyymmdd=ymd) for k in keys]
        total_event_pairs += len(keys)
        tasks.extend(keys)

    # de-dupe tasks by (event_id, competition_id), keeping the first date we saw it.
    seen2: set[str] = set()
    uniq_tasks: list[EventKey] = []
    for k in tasks:
        kk = f"{k.event_id}:{k.competition_id}"
        if kk in seen2:
            continue
        seen2.add(kk)
        uniq_tasks.append(k)

    # Pre-filter: split into skipped vs to-fetch so --max-games applies to actual writes.
    to_fetch: list[EventKey] = []
    for k in uniq_tasks:
        out_path = probs_dir / f"event_{k.event_id}_comp_{k.competition_id}.json"
        if (not args.overwrite) and _existing_with_manifest(out_path):
            skipped_prob_files += 1
            total_prob_processed += 1
            continue
        to_fetch.append(k)

    if args.max_games and int(args.max_games) > 0:
        to_fetch = to_fetch[: int(args.max_games)]

    print(
        f"[{_ts()}] [espn] discovered unique_event_pairs={len(uniq_tasks)} already_cached={skipped_prob_files} to_fetch={len(to_fetch)} "
        f"workers={workers} rps={float(args.requests_per_second or 0.0)}",
        flush=True,
    )

    # (2) Fetch probabilities concurrently.
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                _fetch_probabilities_one,
                k=k,
                probs_dir=probs_dir,
                retry=retry,
                fetched_at=fetched_at,
                overwrite=bool(args.overwrite),
                rate_limiter=rate_limiter,
                throttle_seconds=float(args.throttle_seconds),
                verbose=bool(args.verbose),
            )
            for k in to_fetch
        ]
        for fut in as_completed(futs):
            status, k, err = fut.result()
            with lock:
                total_prob_processed += 1
                if status == "written":
                    written_prob_files += 1
                elif status == "skipped":
                    skipped_prob_files += 1
                else:
                    total_prob_errors += 1

                now = time.monotonic()
                if args.heartbeat_seconds and args.heartbeat_seconds > 0 and (now - last_heartbeat) >= args.heartbeat_seconds:
                    print(
                        f"[espn] heartbeat processed={total_prob_processed} wrote={written_prob_files} "
                        f"skipped={skipped_prob_files} errors={total_prob_errors}",
                        flush=True,
                    )
                    last_heartbeat = now
                if args.progress_every and args.progress_every > 0 and (total_prob_processed % int(args.progress_every) == 0):
                    print(
                        f"[{_ts()}] [espn] progress processed={total_prob_processed} wrote={written_prob_files} "
                        f"skipped={skipped_prob_files} errors={total_prob_errors}",
                        flush=True,
                    )

                if args.verbose:
                    print(
                        f"[{_ts()}] [espn] result status={status} event={k.event_id} comp={k.competition_id} date={k.date_yyyymmdd}",
                        flush=True,
                    )

            if err is not None:
                # Always print a compact error line (even without --verbose) so you can see failures in the log.
                http_status = err.get("http_status")
                body_prefix = str(err.get("body_prefix") or "")
                is_unsupported = (http_status == 400) and ("Probabilities are not supported" in body_prefix)
                tag = "UNSUPPORTED" if is_unsupported else "ERROR"
                if is_unsupported or args.verbose:
                    print(
                        f"[{_ts()}] [espn] {tag} event={err.get('event_id')} comp={err.get('competition_id')} "
                        f"date={err.get('date')} http_status={http_status} msg={err.get('error')}",
                        flush=True,
                    )
                # JSONL append (single record per line). Keep atomic-ish by opening per write.
                with error_log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(err, sort_keys=True) + "\n")
                if args.stop_on_error:
                    raise RuntimeError(f"Stopping due to --stop-on-error. Last error: {err}")

    print(
        f"[{_ts()}] Done. wrote_prob_files={written_prob_files} skipped_prob_files={skipped_prob_files} prob_errors={total_prob_errors} "
        f"scanned_dates={len(dates)} scanned_event_pairs={total_event_pairs} out_root={out_root}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


