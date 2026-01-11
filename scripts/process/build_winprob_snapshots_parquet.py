#!/usr/bin/env python3
"""
Build fixed time-bucket "snapshot rows" from per-event modeling events.

Input: Parquet exported by scripts/export_winprob_modeling_events_parquet.py
Output: Parquet with one row per (game_id, bucket_seconds_remaining).

Selection algorithm (deterministic):
- For each game_id and each bucket b:
  - pick the row that minimizes |time_remaining_regulation - b|
  - tie-break by choosing the maximum event_id

This ensures:
- each game contributes exactly len(buckets) rows
- selection is deterministic given fixed input ordering/contents

Usage:
  ./.venv/bin/python scripts/build_winprob_snapshots_parquet.py \
    --in-parquet data/exports/winprob_modeling_events.parquet \
    --out data/exports/winprob_snapshots_60s.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._winprob_lib import utc_now_iso_compact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert per-event winprob events to fixed time-bucket snapshots (Parquet).")
    p.add_argument("--in-parquet", required=True, help="Input events Parquet path.")
    p.add_argument("--out", required=True, help="Output snapshots Parquet path.")
    p.add_argument("--manifest-out", default="", help="Manifest JSON path (default: <out>.manifest.json).")
    p.add_argument(
        "--buckets-seconds-remaining",
        default="",
        help="Comma-separated bucket anchors in seconds remaining (default: 2880..0 in steps of --bucket-step-seconds).",
    )
    p.add_argument("--bucket-step-seconds", type=int, default=60, help="Bucket step in seconds (default: 60).")
    p.add_argument("--max-bucket-seconds", type=int, default=2880, help="Max bucket anchor (default: 2880).")
    p.add_argument("--min-bucket-seconds", type=int, default=0, help="Min bucket anchor (default: 0).")
    p.add_argument("--batch-rows", type=int, default=250_000, help="Arrow read batch size (default: 250000).")
    p.add_argument(
        "--compression",
        default="zstd",
        choices=["zstd", "snappy", "gzip", "brotli", "none"],
        help="Parquet compression codec (default: zstd).",
    )
    return p.parse_args()


def _parse_int_list_csv(s: str) -> list[int]:
    out: list[int] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _default_buckets(*, max_s: int, min_s: int, step: int) -> list[int]:
    if step <= 0:
        raise ValueError("bucket step must be > 0")
    if max_s < min_s:
        raise ValueError("max bucket must be >= min bucket")
    # descending buckets
    out = list(range(int(max_s), int(min_s) - 1, -int(step)))
    if out[-1] != int(min_s):
        out.append(int(min_s))
    return out


def _possession_text(side: int | None) -> str:
    if side == 0:
        return "home"
    if side == 1:
        return "away"
    return "unknown"


_OUT_SCHEMA = pa.schema(
    [
        pa.field("game_id", pa.string()),
        pa.field("season_start", pa.int16()),
        pa.field("bucket_seconds_remaining", pa.int32()),
        pa.field("event_id", pa.int64()),
        pa.field("point_differential", pa.int32()),
        pa.field("time_remaining_regulation", pa.int32()),
        pa.field("possession_side", pa.int8()),
        pa.field("possession", pa.string()),
        pa.field("final_winning_team", pa.int8()),
    ]
)


def _pick_snapshot_indices(
    *,
    event_ids: np.ndarray,
    time_remaining: np.ndarray,
    buckets: list[int],
) -> list[int]:
    # For each bucket, compute argmin of abs diff with event_id tie-break.
    # Uses vectorized computation per bucket; game sizes are small enough for this to be fast.
    idxs: list[int] = []
    for b in buckets:
        dist = np.abs(time_remaining - int(b))
        min_dist = int(np.min(dist))
        candidates = np.where(dist == min_dist)[0]
        if len(candidates) == 1:
            idxs.append(int(candidates[0]))
            continue
        # tie-break by maximum event_id
        best = int(candidates[np.argmax(event_ids[candidates])])
        idxs.append(best)
    return idxs


def _rows_for_game(
    *,
    game_id: str,
    season_start: int,
    event_id: np.ndarray,
    point_differential: np.ndarray,
    time_remaining: np.ndarray,
    possession_side: np.ndarray,
    final_winning_team: np.ndarray,
    buckets: list[int],
) -> pa.RecordBatch:
    idxs = _pick_snapshot_indices(event_ids=event_id, time_remaining=time_remaining, buckets=buckets)

    out_game_id = [game_id] * len(buckets)
    out_season = [int(season_start)] * len(buckets)
    out_bucket = [int(b) for b in buckets]

    out_event = [int(event_id[i]) for i in idxs]
    out_pd = [int(point_differential[i]) for i in idxs]
    out_tr = [int(time_remaining[i]) for i in idxs]
    out_ps = [None if possession_side[i] < -0.5 else int(possession_side[i]) for i in idxs]
    out_pos = [_possession_text(None if possession_side[i] < -0.5 else int(possession_side[i])) for i in idxs]
    out_y = [None if final_winning_team[i] < -0.5 else int(final_winning_team[i]) for i in idxs]

    arrays: list[pa.Array] = [
        pa.array(out_game_id, type=pa.string()),
        pa.array(out_season, type=pa.int16()),
        pa.array(out_bucket, type=pa.int32()),
        pa.array(out_event, type=pa.int64()),
        pa.array(out_pd, type=pa.int32()),
        pa.array(out_tr, type=pa.int32()),
        pa.array(out_ps, type=pa.int8()),
        pa.array(out_pos, type=pa.string()),
        pa.array(out_y, type=pa.int8()),
    ]
    return pa.RecordBatch.from_arrays(arrays, schema=_OUT_SCHEMA)


def main() -> int:
    args = parse_args()
    in_path = Path(args.in_parquet)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    manifest_path = Path(args.manifest_out) if args.manifest_out else out_path.with_suffix(out_path.suffix + ".manifest.json")

    if args.buckets_seconds_remaining:
        buckets = _parse_int_list_csv(args.buckets_seconds_remaining)
    else:
        buckets = _default_buckets(max_s=int(args.max_bucket_seconds), min_s=int(args.min_bucket_seconds), step=int(args.bucket_step_seconds))
    if not buckets:
        raise SystemExit("No buckets configured.")

    compression = None if args.compression == "none" else args.compression

    # Input columns
    cols = [
        "game_id",
        "event_id",
        "season_start",
        "point_differential",
        "time_remaining_regulation",
        "possession_side",
        "final_winning_team",
    ]

    pf = pq.ParquetFile(in_path)
    writer = pq.ParquetWriter(tmp_path, _OUT_SCHEMA, compression=compression)

    # Streaming group-by-game buffer.
    cur_game_id: str | None = None
    buf: dict[str, list[Any]] = {k: [] for k in cols}

    def flush_one_game() -> tuple[int, int, int, int]:
        # returns (rows_out, games_out, null_possession_count_in_selected, null_label_count_in_selected)
        nonlocal cur_game_id, buf
        if cur_game_id is None:
            return (0, 0, 0, 0)
        n = len(buf["event_id"])
        if n <= 0:
            cur_game_id = None
            buf = {k: [] for k in cols}
            return (0, 0, 0, 0)

        season_start = int(buf["season_start"][0])
        event_id = np.asarray(buf["event_id"], dtype=np.int64)
        point_diff = np.asarray(buf["point_differential"], dtype=np.int32)
        time_rem = np.asarray(buf["time_remaining_regulation"], dtype=np.int32)

        # Nullable smallints: convert None -> -1 sentinel for internal arrays.
        poss = np.asarray([(-1 if v is None else int(v)) for v in buf["possession_side"]], dtype=np.int16)
        y = np.asarray([(-1 if v is None else int(v)) for v in buf["final_winning_team"]], dtype=np.int16)

        batch = _rows_for_game(
            game_id=str(cur_game_id),
            season_start=season_start,
            event_id=event_id,
            point_differential=point_diff,
            time_remaining=time_rem,
            possession_side=poss,
            final_winning_team=y,
            buckets=buckets,
        )
        writer.write_batch(batch)

        # Null accounting for the selected rows only
        ps_selected = batch.column("possession_side").to_pylist()
        y_selected = batch.column("final_winning_team").to_pylist()
        null_poss = sum(1 for v in ps_selected if v is None)
        null_y = sum(1 for v in y_selected if v is None)

        cur_game_id = None
        buf = {k: [] for k in cols}
        return (batch.num_rows, 1, int(null_poss), int(null_y))

    rows_out = 0
    games_out = 0
    null_poss_selected = 0
    null_y_selected = 0
    min_season = None
    max_season = None

    try:
        for rb in pf.iter_batches(batch_size=int(args.batch_rows), columns=cols):
            # Convert to python lists for grouping; batch sizes are large, but per-row operations are simple.
            data = rb.to_pydict()
            gids = data["game_id"]
            for i in range(len(gids)):
                gid = str(gids[i])
                if cur_game_id is None:
                    cur_game_id = gid
                if gid != cur_game_id:
                    ro, go, np0, ny0 = flush_one_game()
                    rows_out += ro
                    games_out += go
                    null_poss_selected += np0
                    null_y_selected += ny0
                    cur_game_id = gid

                for k in cols:
                    buf[k].append(data[k][i])

                ss = int(data["season_start"][i])
                if min_season is None or ss < min_season:
                    min_season = ss
                if max_season is None or ss > max_season:
                    max_season = ss

        ro, go, np0, ny0 = flush_one_game()
        rows_out += ro
        games_out += go
        null_poss_selected += np0
        null_y_selected += ny0
    finally:
        writer.close()

    tmp_path.replace(out_path)

    manifest = {
        "created_at_utc": utc_now_iso_compact(),
        "source": {
            "type": "parquet",
            "path": str(in_path),
        },
        "output": {
            "path": str(out_path),
            "format": "parquet",
            "compression": (args.compression if args.compression != "none" else None),
            "schema": [f.name for f in _OUT_SCHEMA],
        },
        "buckets": {
            "anchors_seconds_remaining": buckets,
            "count": len(buckets),
        },
        "stats": {
            "rows_total": int(rows_out),
            "games_total": int(games_out),
            "min_season_start": (None if min_season is None else int(min_season)),
            "max_season_start": (None if max_season is None else int(max_season)),
            "rows_null_possession_selected": int(null_poss_selected),
            "rows_null_label_selected": int(null_y_selected),
        },
        "notes": [
            "Snapshot selection is deterministic: argmin abs(time_remaining_regulation - bucket), tie-break by max event_id.",
            "Each game contributes exactly len(buckets) rows.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Wrote {out_path} rows={rows_out} games={games_out} buckets={len(buckets)}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


