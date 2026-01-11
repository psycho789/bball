#!/usr/bin/env python3
"""
Fetch the NBA 'odds_todaysGames' snapshot feed and write an archive file + manifest.

Endpoint:
  https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json

Validation (per observed payload):
  - JSON parses
  - top-level has key: games (list)

Note:
  This is treated as a snapshot feed; the recommended output filename includes a fetch timestamp.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


ODDS_URL = "https://cdn.nba.com/static/json/liveData/odds/odds_todaysGames.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch NBA odds_todaysGames snapshot JSON from cdn.nba.com.")
    p.add_argument(
        "--out",
        required=True,
        help="Output JSON path (supports {fetched_at_utc} placeholder), e.g. data/raw/odds/odds_todaysGames_{fetched_at_utc}.json",
    )
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed for the fetch (caps retries).")
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    fetched_at = utc_now_iso_compact()

    out_path = Path(args.out.format(fetched_at_utc=fetched_at))
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")

    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )

    status, resp_headers, body = http_get_bytes(ODDS_URL, retry=retry)
    obj = parse_json_bytes(body)

    games = obj.get("games")
    if not isinstance(games, list):
        raise RuntimeError("Unexpected odds payload: missing top-level games[]")

    # source_key: we don't have an explicit date parameter; use the fetched_at day as logical key
    source_key = fetched_at[:8]  # YYYYMMDD

    write_with_manifest(
        out_path,
        manifest_path,
        url=ODDS_URL,
        http_status=status,
        response_headers=resp_headers,
        body=body,
        source_type="odds_today",
        source_key=source_key,
        fetched_at_utc=fetched_at,
    )

    print(f"Wrote {out_path} (+ manifest). games={len(games)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


