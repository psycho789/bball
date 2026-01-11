#!/usr/bin/env python3
"""
Fetch ESPN "probabilities" JSON for an NBA event/competition and write an archive file + manifest.

Endpoint (core API):
  https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{event_id}/competitions/{competition_id}/probabilities

Notes:
  - This is commonly where ESPN exposes game probability / win probability time-series.
  - IDs are discovered from the ESPN scoreboard payload for a given date.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch ESPN probabilities JSON for an NBA event/competition.")
    p.add_argument("--event-id", required=True, help="ESPN event id, e.g. 401585021")
    p.add_argument("--competition-id", required=True, help="ESPN competition id (from scoreboard competitions[].id)")
    p.add_argument(
        "--out",
        required=True,
        help="Output JSON path, e.g. data/raw/espn/probabilities/2024-25/event_401585021_comp_401585021.json",
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
    event_id = str(args.event_id).strip()
    competition_id = str(args.competition_id).strip()
    if not event_id.isdigit():
        raise SystemExit("--event-id must be digits")
    if not competition_id.isdigit():
        raise SystemExit("--competition-id must be digits")

    url = (
        "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
        f"/events/{event_id}/competitions/{competition_id}/probabilities?limit=1000"
    )

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

    # lightweight validation: object parses and has some expected keys
    # (schema differs by sport, so we keep this permissive)
    if not isinstance(obj, dict) or not obj:
        raise RuntimeError("Unexpected ESPN probabilities payload: expected non-empty object")

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
        source_type="espn_probabilities",
        source_key=f"{event_id}:{competition_id}",
        fetched_at_utc=fetched_at,
    )

    print(f"Wrote {out_path} (+ manifest). event_id={event_id} competition_id={competition_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


