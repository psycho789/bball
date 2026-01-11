#!/usr/bin/env python3
"""
Create leak-proof train/test split artifacts by season_start, with explicit no-overlap checks.

This reads the snapshots Parquet dataset (one row per (game_id, bucket_seconds_remaining)),
derives distinct game lists, and writes deterministic text files:
- train: season_start < test_season_start
- test: season_start == test_season_start
- forward: season_start == forward_season_start (optional; drift-only)

Usage:
  ./.venv/bin/python scripts/export_winprob_split_game_ids.py \
    --snapshots-parquet data/exports/winprob_snapshots_60s.parquet \
    --test-season-start 2024 \
    --out-dir data/exports
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export train/test/forward game_id lists from snapshots parquet.")
    p.add_argument("--snapshots-parquet", required=True, help="Snapshots Parquet path.")
    p.add_argument("--test-season-start", type=int, default=2024, help="Held-out test season_start (default: 2024).")
    p.add_argument("--forward-season-start", type=int, default=2025, help="Forward-time season_start (default: 2025).")
    p.add_argument("--out-dir", required=True, help="Output directory for game-id lists.")
    return p.parse_args()


def _write_list(path: Path, xs: list[str]) -> None:
    path.write_text("".join(f"{x}\n" for x in xs), encoding="utf-8")


def main() -> int:
    args = parse_args()
    test_ss = int(args.test_season_start)
    forward_ss = int(args.forward_season_start)

    pf = pq.ParquetFile(Path(args.snapshots_parquet))
    tab = pf.read(columns=["game_id", "season_start"])
    df = tab.to_pandas()

    games = df.drop_duplicates(subset=["game_id"])[["game_id", "season_start"]].copy()
    games["game_id"] = games["game_id"].astype(str)
    games["season_start"] = games["season_start"].astype(int)

    train = sorted(games.loc[games["season_start"] < test_ss, "game_id"].tolist())
    test = sorted(games.loc[games["season_start"] == test_ss, "game_id"].tolist())
    forward = sorted(games.loc[games["season_start"] == forward_ss, "game_id"].tolist())

    # Mandatory overlap checks
    overlap_train_test = sorted(set(train).intersection(test))
    overlap_train_forward = sorted(set(train).intersection(forward))
    overlap_test_forward = sorted(set(test).intersection(forward))
    if overlap_train_test:
        raise SystemExit(f"Split invalid: train∩test has {len(overlap_train_test)} game_id(s)")
    if overlap_train_forward:
        raise SystemExit(f"Split invalid: train∩forward has {len(overlap_train_forward)} game_id(s)")
    if overlap_test_forward:
        raise SystemExit(f"Split invalid: test∩forward has {len(overlap_test_forward)} game_id(s)")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / f"train_game_ids_season_lt_{test_ss}.txt"
    test_path = out_dir / f"test_game_ids_season_{test_ss}.txt"
    forward_path = out_dir / f"forward_game_ids_season_{forward_ss}.txt"

    _write_list(train_path, train)
    _write_list(test_path, test)
    _write_list(forward_path, forward)

    print(f"Wrote {train_path} n={len(train)}")
    print(f"Wrote {test_path} n={len(test)}")
    print(f"Wrote {forward_path} n={len(forward)}")
    print("OK split_overlap=train∩test=train∩forward=test∩forward=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


