#!/usr/bin/env python3
"""
Export derived.pbp_event_state to Parquet (compressed, typed, smaller than CSV).

This exporter is chunked/streaming to avoid loading the whole table into memory.

Usage:
  # One game
  ./.venv/bin/python scripts/export_pbp_event_state_parquet.py --dsn "$DATABASE_URL" \
    --game-id 0022400196 --out data/exports/pbp_event_state_0022400196.parquet

  # All rows (can still be large, but should be much smaller than CSV)
  ./.venv/bin/python scripts/export_pbp_event_state_parquet.py --dsn "$DATABASE_URL" \
    --all --out data/exports/pbp_event_state_all.parquet
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn


_COL_TYPES: dict[str, pa.DataType] = {
    "game_id": pa.string(),
    "event_id": pa.int64(),
    "point_differential": pa.int32(),
    "time_remaining": pa.int32(),
    "possession_side": pa.int8(),
    "home_score": pa.int32(),
    "away_score": pa.int32(),
    "current_winning_team": pa.int8(),
    "final_winning_team": pa.int8(),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export derived.pbp_event_state to Parquet.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", action="append", help="Game ID to export (can be repeated).")
    p.add_argument("--all", action="store_true", help="Export all rows (can be very large).")
    p.add_argument("--out", required=True, help="Output Parquet path.")
    p.add_argument("--chunk-rows", type=int, default=200_000, help="Rows per chunk (default: 200000).")
    p.add_argument(
        "--compression",
        default="zstd",
        choices=["zstd", "snappy", "gzip", "brotli", "none"],
        help="Parquet compression codec (default: zstd).",
    )
    return p.parse_args()


def _dedupe_keep_order(xs: Sequence[str]) -> list[str]:
    return list(dict.fromkeys([x for x in xs if x]))


def _rows_to_record_batch(names: list[str], rows: list[tuple[object, ...]]) -> pa.RecordBatch:
    # rows: list of tuples; convert column-wise
    cols = list(zip(*rows)) if rows else []
    arrays: list[pa.Array] = []
    for name, col in zip(names, cols, strict=True):
        typ = _COL_TYPES.get(name)
        arrays.append(pa.array(col, type=typ) if typ is not None else pa.array(col))
    return pa.RecordBatch.from_arrays(arrays, names=names)


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    game_ids = _dedupe_keep_order(args.game_id or [])
    if args.all and game_ids:
        raise SystemExit("Pass either --all or --game-id, not both.")
    if not args.all and not game_ids:
        raise SystemExit("Provide at least one --game-id, or pass --all.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    compression = None if args.compression == "none" else args.compression

    if args.all:
        sql = """
        SELECT
          game_id, event_id, point_differential, time_remaining,
          possession_side,
          home_score, away_score,
          current_winning_team, final_winning_team
        FROM derived.pbp_event_state
        ORDER BY game_id, event_id
        """
        params: tuple[object, ...] | None = None
    else:
        sql = """
        SELECT
          game_id, event_id, point_differential, time_remaining,
          possession_side,
          home_score, away_score,
          current_winning_team, final_winning_team
        FROM derived.pbp_event_state
        WHERE game_id = ANY(%s)
        ORDER BY game_id, event_id
        """
        params = (game_ids,)

    total = 0
    writer: pq.ParquetWriter | None = None
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                if params is None:
                    cur.execute(sql)
                else:
                    cur.execute(sql, params)

                names = [d.name for d in cur.description]
                # Force a stable schema so columns that are all-NULL in early chunks
                # don't get inferred as Arrow "null" type and then fail later.
                schema = pa.schema([pa.field(n, _COL_TYPES.get(n, pa.null())) for n in names])
                writer = pq.ParquetWriter(tmp_path, schema, compression=compression)

                while True:
                    rows = cur.fetchmany(args.chunk_rows)
                    if not rows:
                        break
                    batch = _rows_to_record_batch(names, rows)
                    writer.write_batch(batch)
                    total += len(rows)
    finally:
        if writer is not None:
            writer.close()

    tmp_path.replace(out_path)
    print(f"Wrote {out_path} ({total} row(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



