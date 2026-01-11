#!/usr/bin/env python3
"""
Audit ESPN "core" NBA probabilities endpoint support for a season.

We sample a set of dates, discover games from the ESPN scoreboard for each date,
then attempt to fetch the ESPN core probabilities payload for each (event_id, competition_id).

Purpose:
  - Answer questions like: "Is 2016-17 unsupported for *all* games, or only some?"
  - Find the approximate cutoff season where ESPN starts providing this endpoint.

Notes:
  - This does NOT write the probabilities JSON; it only requests and counts status codes.
  - Scoreboards are cached under data/raw/espn/scoreboard like other scripts, so reruns are fast.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest

ESPN_SCOREBOARD_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_PROBABILITIES_BASE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"


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


def _safe_prefix(body: bytes, limit: int = 240) -> str:
    try:
        s = body[:limit].decode("utf-8", errors="replace")
    except Exception:
        s = repr(body[:limit])
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _existing_with_manifest(path: Path) -> bool:
    return path.exists() and path.with_suffix(path.suffix + ".manifest.json").exists()


class _RateLimiter:
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


@dataclass(frozen=True)
class EventKey:
    event_id: str
    competition_id: str
    date_yyyymmdd: str


def _extract_event_keys(scoreboard_obj: dict[str, Any], *, ymd: str) -> list[EventKey]:
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
        out.append(EventKey(event_id=event_id, competition_id=competition_id, date_yyyymmdd=ymd))

    seen: set[str] = set()
    uniq: list[EventKey] = []
    for k in out:
        kk = f"{k.event_id}:{k.competition_id}"
        if kk in seen:
            continue
        seen.add(kk)
        uniq.append(k)
    return uniq


def _scoreboard_for_date(
    *,
    ymd: str,
    out_root: Path,
    retry: HttpRetry,
    fetched_at: str,
    overwrite_scoreboard: bool,
    rate_limiter: _RateLimiter,
) -> dict[str, Any]:
    scoreboard_dir = out_root / "scoreboard"
    scoreboard_dir.mkdir(parents=True, exist_ok=True)
    scoreboard_path = scoreboard_dir / f"scoreboard_{ymd}.json"
    scoreboard_manifest = scoreboard_path.with_suffix(scoreboard_path.suffix + ".manifest.json")
    scoreboard_url = f"{ESPN_SCOREBOARD_BASE}?dates={ymd}&limit=1000"

    if overwrite_scoreboard or (not _existing_with_manifest(scoreboard_path)):
        rate_limiter.wait()
        status, resp_headers, body = http_get_bytes(scoreboard_url, retry=retry)
        obj = parse_json_bytes(body)
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
        return obj

    return parse_json_bytes(scoreboard_path.read_bytes())


def _prob_url(event_id: str, competition_id: str) -> str:
    return f"{ESPN_PROBABILITIES_BASE}/events/{event_id}/competitions/{competition_id}/probabilities?limit=1000"


def _fetch_one(
    *,
    k: EventKey,
    retry: HttpRetry,
    rate_limiter: _RateLimiter,
) -> tuple[int, dict[str, Any]]:
    url = _prob_url(k.event_id, k.competition_id)
    if not k.event_id.isdigit() or not k.competition_id.isdigit():
        return 0, {"date": k.date_yyyymmdd, "event_id": k.event_id, "competition_id": k.competition_id, "url": url, "error": "non-numeric ids"}

    rate_limiter.wait()
    status, resp_headers, body = http_get_bytes(url, retry=retry, allow_non_200=True)
    rec: dict[str, Any] = {
        "date": k.date_yyyymmdd,
        "event_id": k.event_id,
        "competition_id": k.competition_id,
        "url": url,
        "http_status": int(status),
        "content_type": str(resp_headers.get("content-type") or ""),
    }
    if status != 200:
        rec["body_prefix"] = _safe_prefix(body)
    return int(status), rec


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit ESPN core probabilities support by sampling games.")
    p.add_argument("--season-label", required=True, help="Season label for reporting only, e.g. 2016-17")
    p.add_argument("--start-date", required=True, help="YYYYMMDD (inclusive)")
    p.add_argument("--end-date", required=True, help="YYYYMMDD (inclusive)")
    p.add_argument("--date-step-days", type=int, default=30, help="Sample every N days (default: 30). Use 1 to scan all dates.")
    p.add_argument("--max-dates", type=int, default=0, help="If >0, cap sampled dates after stepping.")
    p.add_argument("--max-games", type=int, default=0, help="If >0, cap total games sampled (after dedupe).")
    p.add_argument("--out-root", default="data/raw/espn", help="Root output directory (default: data/raw/espn)")
    p.add_argument("--overwrite-scoreboard", action="store_true", help="Refetch scoreboard JSON even if cached.")
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--requests-per-second", type=float, default=8.0, help="Global max request rate across workers. 0 disables.")
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0)
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    p.add_argument("--out", default="", help="Write JSON report to this path (default: data/reports/espn_prob_support_<season>_<ts>.json)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_yyyymmdd(args.start_date)
    end = _parse_yyyymmdd(args.end_date)
    step = max(1, int(args.date_step_days))

    all_dates = _iter_dates(start, end)
    sampled = [d for i, d in enumerate(all_dates) if (i % step) == 0]
    if args.max_dates and int(args.max_dates) > 0:
        sampled = sampled[: int(args.max_dates)]

    out_root = Path(args.out_root)
    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )
    fetched_at = utc_now_iso_compact()
    rate_limiter = _RateLimiter(float(args.requests_per_second or 0.0))

    # Discover games from sampled scoreboards
    tasks: list[EventKey] = []
    for d in sampled:
        ymd = d.strftime("%Y%m%d")
        sb = _scoreboard_for_date(
            ymd=ymd,
            out_root=out_root,
            retry=retry,
            fetched_at=fetched_at,
            overwrite_scoreboard=bool(args.overwrite_scoreboard),
            rate_limiter=rate_limiter,
        )
        tasks.extend(_extract_event_keys(sb, ymd=ymd))

    # Dedupe by game key
    seen: set[str] = set()
    uniq: list[EventKey] = []
    for k in tasks:
        kk = f"{k.event_id}:{k.competition_id}"
        if kk in seen:
            continue
        seen.add(kk)
        uniq.append(k)

    if args.max_games and int(args.max_games) > 0:
        uniq = uniq[: int(args.max_games)]

    workers = max(1, int(args.workers))
    print(
        f"[audit] season={args.season_label} sampled_dates={len(sampled)} games={len(uniq)} workers={workers} rps={float(args.requests_per_second or 0.0)}",
        flush=True,
    )

    counts: dict[str, int] = {"http_200": 0, "http_400": 0, "http_other": 0, "non_numeric": 0}
    examples_400: list[dict[str, Any]] = []
    examples_other: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                _fetch_one,
                k=k,
                retry=retry,
                rate_limiter=rate_limiter,
            )
            for k in uniq
        ]
        for fut in as_completed(futs):
            status, rec = fut.result()
            if status == 200:
                counts["http_200"] += 1
            elif status == 400:
                counts["http_400"] += 1
                if len(examples_400) < 10:
                    examples_400.append(rec)
            elif status == 0:
                counts["non_numeric"] += 1
            else:
                counts["http_other"] += 1
                if len(examples_other) < 10:
                    examples_other.append(rec)

    out_path = (
        Path(args.out)
        if args.out
        else Path("data/reports") / f"espn_prob_support_{args.season_label}_{fetched_at}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "season": str(args.season_label),
        "window": {"start": args.start_date, "end": args.end_date, "date_step_days": step, "max_dates": int(args.max_dates or 0)},
        "sampled_dates": [d.strftime("%Y%m%d") for d in sampled],
        "sampled_games": len(uniq),
        "counts": counts,
        "examples_http_400": examples_400,
        "examples_http_other": examples_other,
        "notes": {
            "meaning": "Counts reflect HTTP status from ESPN core probabilities endpoint for sampled games.",
            "common_400": "Often indicates 'Probabilities are not supported...' for that competition.",
        },
    }
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"[audit] wrote {out_path} counts={counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())








