#!/usr/bin/env python3
"""
Fetch NBA boxscore JSON from the validated CDN endpoint and write an archive file + manifest.

Endpoint pattern:
  https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json

Validation:
  - JSON parses
  - has keys: meta.code == 200, game.gameId
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch NBA boxscore JSON from cdn.nba.com.")
    p.add_argument("--game-id", required=True, help="NBA gameId string, e.g. 0022400196")
    p.add_argument("--out", required=True, help="Output JSON path, e.g. data/raw/boxscore/0022400196.json")
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed for the fetch (caps retries).")
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    game_id = args.game_id
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"

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

    meta = obj.get("meta", {})
    if not isinstance(meta, dict) or meta.get("code") != 200:
        raise RuntimeError(f"Unexpected boxscore meta.code: {meta.get('code')}")

    game = obj.get("game", {})
    if not isinstance(game, dict) or str(game.get("gameId")) != str(game_id):
        raise RuntimeError("Unexpected boxscore game.gameId")

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
        source_type="boxscore",
        source_key=game_id,
        fetched_at_utc=fetched_at,
    )

    print(f"Wrote {out_path} (+ manifest).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


