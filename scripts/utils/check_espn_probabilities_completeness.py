#!/usr/bin/env python3
"""
Check whether ESPN probabilities have been fully archived for a season/date window.

Definition of "complete":
  - For every (event_id, competition_id) discovered from ESPN scoreboards in the date window,
    either:
      (a) the probabilities JSON + manifest exist on disk, OR
      (b) the game is recorded as "unsupported" by ESPN (HTTP 400 with message like
          "Probabilities are not supported...") in one of the provided error logs.

This lets you safely rerun backfills until the checker reports 100% accounted-for.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ESPN_UNSUPPORTED_SUBSTR = "Probabilities are not supported"


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


def _existing_with_manifest(path: Path) -> bool:
    return path.exists() and path.with_suffix(path.suffix + ".manifest.json").exists()


@dataclass(frozen=True)
class EventKey:
    event_id: str
    competition_id: str
    date_yyyymmdd: str

    def key(self) -> str:
        return f"{self.event_id}:{self.competition_id}"


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
    # de-dupe while preserving first date
    seen: set[str] = set()
    uniq: list[EventKey] = []
    for k in out:
        kk = k.key()
        if kk in seen:
            continue
        seen.add(kk)
        uniq.append(k)
    return uniq


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _collect_unsupported_keys(error_logs: list[Path]) -> set[str]:
    unsupported: set[str] = set()
    for p in error_logs:
        for rec in _read_jsonl(p):
            status = rec.get("http_status")
            body_prefix = str(rec.get("body_prefix") or "")
            if status != 400:
                continue
            if ESPN_UNSUPPORTED_SUBSTR not in body_prefix:
                continue
            event_id = str(rec.get("event_id") or "").strip()
            comp_id = str(rec.get("competition_id") or "").strip()
            if event_id and comp_id:
                unsupported.add(f"{event_id}:{comp_id}")
    return unsupported


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check completeness of locally cached ESPN probabilities for a season.")
    p.add_argument("--season-label", required=True, help="Season label used for probabilities subdir, e.g. 2019-20")
    p.add_argument("--start-date", required=True, help="YYYYMMDD (inclusive) for expected scoreboard scan")
    p.add_argument("--end-date", required=True, help="YYYYMMDD (inclusive) for expected scoreboard scan")
    p.add_argument("--out-root", default="data/raw/espn", help="Root output directory (default: data/raw/espn)")
    p.add_argument(
        "--error-log",
        action="append",
        default=[],
        help="Optional JSONL error log(s) from backfill runs. Repeatable. 400 'not supported' is counted as complete.",
    )
    p.add_argument("--show-missing", type=int, default=25, help="Print up to N missing games (default: 25). 0 disables.")
    p.add_argument("--out", default="", help="Write JSON report to this path (optional).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    season = str(args.season_label)
    start = _parse_yyyymmdd(args.start_date)
    end = _parse_yyyymmdd(args.end_date)
    dates = _iter_dates(start, end)

    out_root = Path(args.out_root)
    scoreboard_dir = out_root / "scoreboard"
    probs_dir = out_root / "probabilities" / season

    # Load expected games from cached scoreboards
    expected: dict[str, EventKey] = {}
    missing_scoreboards: list[str] = []
    for d in dates:
        ymd = d.strftime("%Y%m%d")
        sb_path = scoreboard_dir / f"scoreboard_{ymd}.json"
        if not _existing_with_manifest(sb_path):
            missing_scoreboards.append(ymd)
            continue
        try:
            sb_obj = json.loads(sb_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(sb_obj, dict):
            continue
        for k in _extract_event_keys(sb_obj, ymd=ymd):
            expected.setdefault(k.key(), k)

    unsupported = _collect_unsupported_keys([Path(x) for x in (args.error_log or [])])

    present = 0
    accounted_unsupported = 0
    missing: list[dict[str, str]] = []

    for kk, k in expected.items():
        prob_path = probs_dir / f"event_{k.event_id}_comp_{k.competition_id}.json"
        if _existing_with_manifest(prob_path):
            present += 1
            continue
        if kk in unsupported:
            accounted_unsupported += 1
            continue
        missing.append({"date": k.date_yyyymmdd, "event_id": k.event_id, "competition_id": k.competition_id})

    expected_n = len(expected)
    accounted = present + accounted_unsupported
    pct = (accounted / expected_n) if expected_n else 0.0

    summary = {
        "season": season,
        "window": {"start": args.start_date, "end": args.end_date},
        "dirs": {"scoreboard_dir": str(scoreboard_dir), "probabilities_dir": str(probs_dir)},
        "expected_games": expected_n,
        "present_probability_files": present,
        "accounted_unsupported_via_error_logs": accounted_unsupported,
        "missing_probability_files": len(missing),
        "missing_scoreboard_days": len(missing_scoreboards),
        "complete": (len(missing) == 0 and len(missing_scoreboards) == 0),
        "accounted_fraction": pct,
        "notes": {
            "definition": "complete=true means: all scoreboards present AND every expected game has a probabilities file OR is marked unsupported in error logs",
            "unsupported_match": ESPN_UNSUPPORTED_SUBSTR,
        },
    }

    print(
        f"[check] season={season} expected={expected_n} present={present} unsupported={accounted_unsupported} "
        f"missing_prob={len(missing)} missing_scoreboards={len(missing_scoreboards)} accounted={pct:.3f} complete={summary['complete']}",
        flush=True,
    )
    if missing_scoreboards:
        print(f"[check] missing_scoreboard_days (first 10): {missing_scoreboards[:10]}", flush=True)
    if args.show_missing and int(args.show_missing) > 0 and missing:
        n = min(int(args.show_missing), len(missing))
        print(f"[check] missing_probability_files (showing {n}/{len(missing)}):", flush=True)
        for row in missing[:n]:
            print(f"  date={row['date']} event_id={row['event_id']} competition_id={row['competition_id']}", flush=True)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"summary": summary, "missing": missing, "missing_scoreboard_days": missing_scoreboards}, indent=2) + "\n", encoding="utf-8")
        print(f"[check] wrote {out_path}", flush=True)

    return 0 if summary["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())








