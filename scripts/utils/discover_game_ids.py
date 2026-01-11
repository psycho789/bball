#!/usr/bin/env python3
"""
Discover historical NBA game IDs for a season using nba_api (stats.nba.com).

Implements:
- conservative throttling
- retries with exponential backoff + jitter
- raw response archival (JSON)
- deterministic, de-duplicated game list output (CSV)

Usage:
  python3 scripts/discover_game_ids.py --season 2023-24 --out data/discovery/game_ids_2023-24.csv

Artifacts:
  - Raw archive JSON:
      data/raw/nba_api/leaguegamefinder/season=2023-24/leaguegamefinder_2023-24_<fetched_at_utc>.json
  - Manifest JSON (sha256/size/timestamps):
      same path + ".manifest.json"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder


def utc_now_iso() -> str:
    # Stable, filename-friendly UTC timestamp
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_hex_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_sleep_seconds: float
    max_sleep_seconds: float
    jitter_seconds: float
    deadline_seconds: float


def sleep_with_jitter(seconds: float, jitter_seconds: float) -> None:
    if seconds <= 0:
        return
    jitter = random.uniform(0, jitter_seconds) if jitter_seconds > 0 else 0.0
    time.sleep(seconds + jitter)


def fetch_league_game_finder(
    season: str,
    league_id: str,
    throttle_seconds: float,
    retry: RetryPolicy,
) -> dict[str, Any]:
    """
    Returns the raw response dict from nba_api (resultSets + metadata).
    Retries on any exception (stats.nba.com can throw 403/429/etc via requests).
    """
    last_err: BaseException | None = None
    start = time.monotonic()
    for attempt in range(1, retry.max_attempts + 1):
        if time.monotonic() - start > retry.deadline_seconds:
            raise RuntimeError(f"Deadline exceeded after {retry.deadline_seconds:.1f}s for LeagueGameFinder {season}")
        try:
            # Throttle before the request (conservative baseline).
            sleep_with_jitter(throttle_seconds, jitter_seconds=retry.jitter_seconds)

            lgf = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                league_id_nullable=league_id,
            )
            # nba_api provides raw dict form; this is what we archive.
            return lgf.get_dict()
        except BaseException as e:  # noqa: BLE001
            last_err = e
            if attempt >= retry.max_attempts:
                break
            backoff = min(retry.base_sleep_seconds * (2 ** (attempt - 1)), retry.max_sleep_seconds)
            remaining = max(0.0, retry.deadline_seconds - (time.monotonic() - start))
            sleep_with_jitter(min(backoff, remaining), jitter_seconds=retry.jitter_seconds)

    raise RuntimeError(f"LeagueGameFinder failed after {retry.max_attempts} attempts") from last_err


def canonicalize_games(df: pd.DataFrame, season: str) -> list[dict[str, Any]]:
    """
    LeagueGameFinder returns team-game rows (~2 rows per game).
    We output one canonical row per GAME_ID.

    Canonical row selection strategy:
    - Prefer the row whose MATCHUP contains ' vs. ' (home team perspective).
    - Otherwise pick the lexicographically smallest MATCHUP row for determinism.
    """
    required_cols = {"GAME_ID", "GAME_DATE", "MATCHUP", "TEAM_ID", "TEAM_ABBREVIATION"}
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise RuntimeError(f"LeagueGameFinder missing expected columns: {missing}")

    # Deterministic ordering before group operations
    df2 = df.copy()
    df2["GAME_ID"] = df2["GAME_ID"].astype(str)
    df2["GAME_DATE"] = df2["GAME_DATE"].astype(str)
    df2["MATCHUP"] = df2["MATCHUP"].astype(str)
    df2["TEAM_ABBREVIATION"] = df2["TEAM_ABBREVIATION"].astype(str)

    out: list[dict[str, Any]] = []
    for game_id, g in df2.groupby("GAME_ID", sort=True):
        # sort rows for deterministic fallback selection
        g_sorted = g.sort_values(["MATCHUP", "TEAM_ID"], kind="mergesort")
        home_rows = g_sorted[g_sorted["MATCHUP"].str.contains(" vs. ", regex=False)]
        row = home_rows.iloc[0] if len(home_rows) > 0 else g_sorted.iloc[0]

        matchup = str(row["MATCHUP"])
        game_date = str(row["GAME_DATE"])

        # Derive home/away abbreviations from matchup format when possible.
        # Examples:
        #  - "BOS vs. DAL" => home=BOS, away=DAL
        #  - "DAL @ BOS"   => away=DAL, home=BOS
        home_abbr = None
        away_abbr = None
        if " vs. " in matchup:
            parts = matchup.split(" vs. ")
            if len(parts) == 2:
                home_abbr, away_abbr = parts[0].strip(), parts[1].strip()
        elif " @ " in matchup:
            parts = matchup.split(" @ ")
            if len(parts) == 2:
                away_abbr, home_abbr = parts[0].strip(), parts[1].strip()

        out.append(
            {
                "season": season,
                "game_id": game_id,
                "game_date": game_date,
                "matchup": matchup,
                "home_team_abbreviation": home_abbr,
                "away_team_abbreviation": away_abbr,
            }
        )

    # Stable sort: date then id (string sort is OK given YYYY-MM-DD format)
    out.sort(key=lambda r: (r["game_date"], r["game_id"]))
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "season",
        "game_id",
        "game_date",
        "matchup",
        "home_team_abbreviation",
        "away_team_abbreviation",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discover NBA game IDs for a season via nba_api LeagueGameFinder.")
    p.add_argument("--season", required=True, help="NBA season string, e.g. 2023-24")
    p.add_argument("--league-id", default="00", help="NBA league id (00=NBA)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument(
        "--throttle-seconds",
        type=float,
        default=1.0,
        help="Sleep this many seconds before each request (conservative default).",
    )
    p.add_argument("--max-attempts", type=int, default=6, help="Max attempts for the nba_api request.")
    p.add_argument("--base-backoff-seconds", type=float, default=1.0, help="Base sleep for exponential backoff.")
    p.add_argument("--max-backoff-seconds", type=float, default=60.0, help="Cap for exponential backoff.")
    p.add_argument("--jitter-seconds", type=float, default=0.25, help="Add jitter (0..jitter) to sleeps.")
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed for the request+retries.")
    p.add_argument(
        "--raw-dir",
        default="data/raw/nba_api/leaguegamefinder",
        help="Base directory for raw response archival.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    retry = RetryPolicy(
        max_attempts=args.max_attempts,
        base_sleep_seconds=args.base_backoff_seconds,
        max_sleep_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )

    fetched_at = utc_now_iso()
    raw_dir = Path(args.raw_dir) / f"season={args.season}"
    raw_path = raw_dir / f"leaguegamefinder_{args.season}_{fetched_at}.json"
    manifest_path = raw_dir / f"leaguegamefinder_{args.season}_{fetched_at}.manifest.json"

    resp = fetch_league_game_finder(
        season=args.season,
        league_id=args.league_id,
        throttle_seconds=args.throttle_seconds,
        retry=retry,
    )

    raw_bytes = json.dumps(resp, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sha = sha256_hex_bytes(raw_bytes)
    atomic_write_bytes(raw_path, raw_bytes)

    manifest = {
        "source": "nba_api.stats.endpoints.LeagueGameFinder",
        "season": args.season,
        "league_id": args.league_id,
        "fetched_at_utc": fetched_at,
        "path": str(raw_path),
        "sha256_hex": sha,
        "byte_size": len(raw_bytes),
        "python": sys.version,
        "throttle_seconds": args.throttle_seconds,
        "retry_policy": {
            "max_attempts": retry.max_attempts,
            "base_backoff_seconds": retry.base_sleep_seconds,
            "max_backoff_seconds": retry.max_sleep_seconds,
            "jitter_seconds": retry.jitter_seconds,
        },
    }
    atomic_write_bytes(manifest_path, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))

    # Convert to dataframe via nba_api response structure (resultSets[0]).
    # nba_api provides helper methods on endpoint objects, but we archived raw dict, so we reconstruct.
    result_sets = resp.get("resultSets")
    if not isinstance(result_sets, list) or not result_sets:
        raise RuntimeError("Unexpected LeagueGameFinder response: missing resultSets")
    rs0 = result_sets[0]
    headers = rs0.get("headers")
    rowset = rs0.get("rowSet")
    if not isinstance(headers, list) or not isinstance(rowset, list):
        raise RuntimeError("Unexpected LeagueGameFinder response: invalid headers/rowSet")

    df = pd.DataFrame(rowset, columns=headers)
    games = canonicalize_games(df, season=args.season)

    out_path = Path(args.out)
    write_csv(out_path, games)

    print(f"Wrote {len(games)} unique game_id rows to {out_path}")
    print(f"Archived raw response to {raw_path}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


