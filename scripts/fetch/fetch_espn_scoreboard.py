#!/usr/bin/env python3
"""
Fetch ESPN NBA scoreboard JSON for a given date and write an archive file + manifest.

Endpoint:
  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD

Validation (lightweight):
  - JSON parses
  - top-level has key: events (list)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch ESPN NBA scoreboard JSON for a specific date.")
    p.add_argument("--date", required=True, help="Date in YYYYMMDD format, e.g. 20241022")
    p.add_argument("--out", required=True, help="Output JSON path, e.g. data/raw/espn/scoreboard/scoreboard_20241022.json")
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed for the fetch (caps retries).")
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    date = str(args.date).strip()
    if len(date) != 8 or not date.isdigit():
        raise SystemExit("--date must be YYYYMMDD")

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}&limit=1000"

    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )

    status, resp_headers, body = http_get_bytes(url, retry=retry)
    obj = parse_json_bytes(body)

    events = obj.get("events")
    if not isinstance(events, list):
        raise RuntimeError("Unexpected ESPN scoreboard payload: missing top-level events[]")

    out_path = Path(args.out)
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    fetched_at = utc_now_iso_compact()

    write_with_manifest(
        out_path,
        manifest_path,
        url=url,
        http_status=status,
        response_headers=resp_headers,
        body=body,
        source_type="espn_scoreboard",
        source_key=date,
        fetched_at_utc=fetched_at,
    )

    print(f"Wrote {out_path} (+ manifest). events={len(events)} date={date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


