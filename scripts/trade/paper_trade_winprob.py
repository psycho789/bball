#!/usr/bin/env python3
"""
Paper trading decision rule + auditable decision log (no real betting).

Input:
- Parquet produced by scripts/join_winprob_to_odds_snapshot.py

Deterministic rule set (default):
- Consider only rows where implied probabilities are present.
- Select side with maximum positive edge, if:
  - edge >= --min-edge
  - absolute odds constraints are met (optional)
- Emit JSONL decision log (append-only).

Usage:
  ./.venv/bin/python scripts/paper_trade_winprob.py \
    --joined-parquet data/exports/winprob_with_odds_20251214.parquet \
    --out-jsonl data/exports/paper_trades_20251214.jsonl \
    --min-edge 0.02
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._winprob_lib import utc_now_iso_compact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Paper trade decisions from joined model+odds dataset.")
    p.add_argument("--joined-parquet", required=True, help="Parquet file produced by join script.")
    p.add_argument("--out-jsonl", required=True, help="Output JSONL path (append-only).")
    p.add_argument("--min-edge", type=float, default=0.02, help="Minimum edge required to place a paper trade (default: 0.02).")
    p.add_argument("--max-trades", type=int, default=0, help="If >0, cap number of trades emitted (deterministic order).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.joined_parquet)
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pq.read_table(in_path).to_pandas()
    if len(df) == 0:
        raise SystemExit("Joined dataset has 0 rows.")

    min_edge = float(args.min_edge)
    df = df[df["implied_home"].notna() & df["implied_away"].notna()].copy()

    # Deterministic ordering by game_id.
    df = df.sort_values(["game_id"]).reset_index(drop=True)

    decisions: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        edge_home = r.get("edge_home")
        edge_away = r.get("edge_away")
        if edge_home is None or edge_away is None:
            continue
        edge_home = float(edge_home)
        edge_away = float(edge_away)
        if edge_home >= edge_away and edge_home >= min_edge:
            side = "home"
            edge = edge_home
            model_p = float(r["model_p_home"])
            implied_p = float(r["implied_home"])
            odds = float(r["odds_home_dec"])
        elif edge_away > edge_home and edge_away >= min_edge:
            side = "away"
            edge = edge_away
            model_p = float(r["model_p_away"])
            implied_p = float(r["implied_away"])
            odds = float(r["odds_away_dec"])
        else:
            side = "no_bet"
            edge = max(edge_home, edge_away)
            model_p = None
            implied_p = None
            odds = None

        decisions.append(
            {
                "created_at_utc": utc_now_iso_compact(),
                "game_id": str(r["game_id"]),
                "bucket_seconds_remaining": int(r["bucket_seconds_remaining"]),
                "inputs": {
                    "point_differential": int(r["point_differential"]),
                    "time_remaining_regulation": int(r["time_remaining_regulation"]),
                    "possession": str(r["possession"]),
                },
                "model": {
                    "p_home": float(r["model_p_home"]),
                    "p_away": float(r["model_p_away"]),
                },
                "market": {
                    "book_id": str(r["book_id"]),
                    "book_name": r.get("book_name"),
                    "odds_home_dec": float(r["odds_home_dec"]),
                    "odds_away_dec": float(r["odds_away_dec"]),
                    "implied_home": float(r["implied_home"]),
                    "implied_away": float(r["implied_away"]),
                },
                "decision": {
                    "action": ("bet" if side in ("home", "away") else "no_bet"),
                    "side": side,
                    "min_edge": min_edge,
                    "edge": edge,
                    "model_p_selected": model_p,
                    "implied_p_selected": implied_p,
                    "odds_selected_dec": odds,
                },
            }
        )

        if int(args.max_trades) > 0 and len([d for d in decisions if d["decision"]["action"] == "bet"]) >= int(args.max_trades):
            break

    # Append-only write
    with out_path.open("a", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d, sort_keys=False) + "\n")

    n_bets = sum(1 for d in decisions if d["decision"]["action"] == "bet")
    print(f"Wrote {out_path} decisions={len(decisions)} bets={n_bets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


