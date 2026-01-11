#!/usr/bin/env python3
"""
Join model probabilities to an NBA odds_todaysGames snapshot to compute implied probabilities and edge.

Important constraint:
- NBA provides today-only odds via odds_todaysGames; historical odds require continuous snapshot capture.

Join strategy (explicit and auditable):
- Join on game_id (NBA gameId in odds feed matches games.game_id / derived tables).
- Use a fixed snapshot bucket (default: 2880 seconds remaining in regulation) to represent a "pre-game" state.
  This is an approximation of a timestamp-as-of join and is used as a bridge until true live timestamp alignment exists.

Odds interpretation:
- Odds are decimal odds strings (e.g., "1.360").
- Raw implied probability: 1 / decimal_odds
- Vig-adjusted implied probability: raw / (raw_home + raw_away)

Usage:
  ./.venv/bin/python scripts/join_winprob_to_odds_snapshot.py \
    --artifact artifacts/winprob_logreg_v1.json \
    --snapshots-parquet data/exports/winprob_snapshots_60s.parquet \
    --odds-file data/raw/odds/odds_todaysGames_20251214T124632Z.json \
    --bucket-seconds-remaining 2880 \
    --book-id 4 \
    --out data/exports/winprob_with_odds_20251214.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._winprob_lib import build_design_matrix, load_artifact, predict_proba, utc_now_iso_compact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Join winprob model outputs to odds snapshot and compute edge.")
    p.add_argument("--artifact", required=True, help="Winprob artifact JSON path.")
    p.add_argument("--snapshots-parquet", required=True, help="Snapshots Parquet path.")
    p.add_argument("--odds-file", required=True, help="odds_todaysGames JSON path.")
    p.add_argument("--bucket-seconds-remaining", type=int, default=2880, help="Snapshot bucket to score (default: 2880).")
    p.add_argument("--market-group", default="regular", help='Market group_name (default: "regular").')
    p.add_argument("--market-name", default="2way", help='Market name (default: "2way").')
    p.add_argument("--book-id", default="", help="Optional book id to select (string). If empty, choose first book with both outcomes.")
    p.add_argument("--out", required=True, help="Output Parquet path.")
    p.add_argument("--manifest-out", default="", help="Manifest JSON path (default: <out>.manifest.json).")
    return p.parse_args()


def _to_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _extract_2way_odds_for_game(game_obj: dict[str, Any], *, market_group: str, market_name: str, book_id: str) -> dict[str, Any] | None:
    markets = game_obj.get("markets")
    if not isinstance(markets, list):
        return None
    for m in markets:
        if not isinstance(m, dict):
            continue
        if str(m.get("group_name") or "") != market_group:
            continue
        if str(m.get("name") or "") != market_name:
            continue
        books = m.get("books")
        if not isinstance(books, list):
            continue
        for b in books:
            if not isinstance(b, dict):
                continue
            bid = str(b.get("id") or "")
            if book_id and bid != book_id:
                continue
            outs = b.get("outcomes")
            if not isinstance(outs, list):
                continue
            home_odds = away_odds = None
            for o in outs:
                if not isinstance(o, dict):
                    continue
                t = str(o.get("type") or "")
                if t == "home":
                    home_odds = _to_float(o.get("odds"))
                elif t == "away":
                    away_odds = _to_float(o.get("odds"))
            if home_odds is None or away_odds is None:
                continue
            return {
                "book_id": bid,
                "book_name": b.get("name"),
                "home_odds_dec": home_odds,
                "away_odds_dec": away_odds,
            }
    return None


def main() -> int:
    args = parse_args()
    art = load_artifact(Path(args.artifact))
    odds_obj = json.loads(Path(args.odds_file).read_text(encoding="utf-8"))
    games = odds_obj.get("games")
    if not isinstance(games, list):
        raise SystemExit("odds file missing top-level games[]")

    # Load snapshots and filter to the requested bucket.
    bucket = int(args.bucket_seconds_remaining)
    pf = pq.ParquetFile(Path(args.snapshots_parquet))
    tab = pf.read(
        columns=[
            "game_id",
            "bucket_seconds_remaining",
            "point_differential",
            "time_remaining_regulation",
            "possession",
            "final_winning_team",
            "season_start",
        ]
    )
    df = tab.to_pandas()
    df = df[df["bucket_seconds_remaining"].astype(int) == bucket].copy()
    df["game_id"] = df["game_id"].astype(str)
    df_by_gid = {gid: row for gid, row in df.set_index("game_id").iterrows()}

    out_rows: list[dict[str, Any]] = []
    for g in games:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("gameId") or "")
        if not gid:
            continue
        snap = df_by_gid.get(gid)
        if snap is None:
            continue
        odds = _extract_2way_odds_for_game(
            g, market_group=str(args.market_group), market_name=str(args.market_name), book_id=str(args.book_id or "")
        )
        if odds is None:
            continue

        X = build_design_matrix(
            point_differential=np.array([float(snap["point_differential"])], dtype=np.float64),
            time_remaining_regulation=np.array([float(snap["time_remaining_regulation"])], dtype=np.float64),
            possession=[str(snap["possession"])],
            preprocess=art.preprocess,
        )
        p_home = float(predict_proba(art, X=X)[0])
        p_away = 1.0 - p_home

        home_dec = float(odds["home_odds_dec"])
        away_dec = float(odds["away_odds_dec"])
        imp_home_raw = 1.0 / home_dec
        imp_away_raw = 1.0 / away_dec
        s = imp_home_raw + imp_away_raw
        imp_home = imp_home_raw / s if s > 0 else None
        imp_away = imp_away_raw / s if s > 0 else None

        out_rows.append(
            {
                "game_id": gid,
                "bucket_seconds_remaining": bucket,
                "point_differential": int(snap["point_differential"]),
                "time_remaining_regulation": int(snap["time_remaining_regulation"]),
                "possession": str(snap["possession"]),
                "season_start": int(snap["season_start"]),
                "model_p_home": p_home,
                "model_p_away": p_away,
                "book_id": str(odds["book_id"]),
                "book_name": odds.get("book_name"),
                "odds_home_dec": home_dec,
                "odds_away_dec": away_dec,
                "implied_home_raw": imp_home_raw,
                "implied_away_raw": imp_away_raw,
                "implied_home": imp_home,
                "implied_away": imp_away,
                "edge_home": (None if imp_home is None else p_home - imp_home),
                "edge_away": (None if imp_away is None else p_away - imp_away),
            }
        )

    out_df = pd.DataFrame(out_rows)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(out_df, preserve_index=False), out_path, compression="zstd")

    manifest_path = Path(args.manifest_out) if args.manifest_out else out_path.with_suffix(out_path.suffix + ".manifest.json")
    manifest = {
        "created_at_utc": utc_now_iso_compact(),
        "artifact": {"path": str(Path(args.artifact))},
        "inputs": {"snapshots_parquet": str(Path(args.snapshots_parquet)), "odds_file": str(Path(args.odds_file))},
        "join_policy": {
            "key": "game_id",
            "bucket_seconds_remaining": bucket,
            "market_group": str(args.market_group),
            "market_name": str(args.market_name),
            "book_id": (None if not args.book_id else str(args.book_id)),
        },
        "output": {"path": str(out_path), "rows": int(len(out_df))},
        "notes": [
            "Implied probabilities are computed from decimal odds and normalized to remove the 2-way overround.",
            "This join uses a fixed snapshot bucket and does not perform timestamp-as-of alignment.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} rows={len(out_df)}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


