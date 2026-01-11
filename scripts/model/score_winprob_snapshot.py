#!/usr/bin/env python3
"""
Score a single in-game snapshot using a saved win-probability artifact.

Inputs:
- point_differential: int (home - away)
- time_remaining_regulation: int seconds remaining in regulation (0..2880; OT is represented as 0)
- possession: "home" | "away" | "unknown"

Outputs:
- p_home_win
- p_away_win

Usage:
  ./.venv/bin/python scripts/score_winprob_snapshot.py \
    --artifact artifacts/winprob_logreg_v1.json \
    --point-differential 5 \
    --time-remaining-regulation 300 \
    --possession home
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._winprob_lib import build_design_matrix, load_artifact, predict_proba


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score a single snapshot with the win-prob artifact.")
    p.add_argument("--artifact", required=True, help="Artifact JSON path.")
    p.add_argument("--point-differential", type=int, required=True, help="Home - away score differential.")
    p.add_argument("--time-remaining-regulation", type=int, required=True, help="Seconds remaining in regulation (0..2880).")
    p.add_argument("--possession", default="unknown", help='Possession: "home", "away", or "unknown" (default: unknown).')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    art = load_artifact(Path(args.artifact))

    X = build_design_matrix(
        point_differential=np.array([int(args.point_differential)], dtype=np.float64),
        time_remaining_regulation=np.array([int(args.time_remaining_regulation)], dtype=np.float64),
        possession=[str(args.possession)],
        preprocess=art.preprocess,
    )
    p_home = float(predict_proba(art, X=X)[0])
    out = {
        "p_home_win": p_home,
        "p_away_win": 1.0 - p_home,
        "inputs": {
            "point_differential": int(args.point_differential),
            "time_remaining_regulation": int(args.time_remaining_regulation),
            "possession": str(args.possession),
        },
        "model": {
            "version": art.version,
            "created_at_utc": art.created_at_utc,
        },
    }
    print(json.dumps(out, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


