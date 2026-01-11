#!/usr/bin/env python3
"""
Export a regulation-safe modeling events dataset for in-game win probability training.

This exporter is read-only on Postgres (SELECT only).

Key design choice (leak-proof time feature):
- Use derived.game_state_by_event.seconds_remaining_regulation, not seconds_remaining_game.
  seconds_remaining_game depends on realized overtime length (future information during regulation).

Output schema (Parquet):
- game_id (string)
- event_id (int64)
- season_start (int16)
- point_differential (int32)              # home - away
- time_remaining_regulation (int32)       # 2880..0 during regulation
- possession_side (int8, nullable)        # 0 home, 1 away, null unknown
- final_winning_team (int8, nullable)     # 0 home, 1 away

Usage:
  ./.venv/bin/python scripts/export_winprob_modeling_events_parquet.py \
    --dsn "$DATABASE_URL" \
    --out data/exports/winprob_modeling_events.parquet
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import get_dsn
from scripts.lib._winprob_lib import utc_now_iso_compact


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export regulation-safe winprob modeling events to Parquet.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--out", required=True, help="Output Parquet path.")
    p.add_argument("--manifest-out", default="", help="Manifest JSON path (default: <out>.manifest.json).")
    p.add_argument("--chunk-rows", type=int, default=200_000, help="Rows per chunk (default: 200000).")
    p.add_argument(
        "--compression",
        default="zstd",
        choices=["zstd", "snappy", "gzip", "brotli", "none"],
        help="Parquet compression codec (default: zstd).",
    )
    p.add_argument(
        "--include-period-filter",
        action="store_true",
        help="Filter to regulation-only rows (period <= 4). This is enabled by default in SQL already.",
    )
    p.add_argument("--season-start", type=int, default=0, help="If non-zero, filter to a single season_start (e.g. 2024).")
    p.add_argument(
        "--limit-games",
        type=int,
        default=0,
        help="If >0, restrict to the first N game_id values (sorted ascending) after filtering. Deterministic.",
    )
    return p.parse_args()


_COL_TYPES: dict[str, pa.DataType] = {
    "game_id": pa.string(),
    "event_id": pa.int64(),
    "season_start": pa.int16(),
    "point_differential": pa.int32(),
    "time_remaining_regulation": pa.int32(),
    "possession_side": pa.int8(),
    "final_winning_team": pa.int8(),
}


def _rows_to_record_batch(names: list[str], rows: list[tuple[object, ...]]) -> pa.RecordBatch:
    cols = list(zip(*rows)) if rows else []
    arrays: list[pa.Array] = []
    for name, col in zip(names, cols, strict=True):
        typ = _COL_TYPES.get(name)
        arrays.append(pa.array(col, type=typ) if typ is not None else pa.array(col))
    return pa.RecordBatch.from_arrays(arrays, names=names)


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    manifest_path = Path(args.manifest_out) if args.manifest_out else out_path.with_suffix(out_path.suffix + ".manifest.json")

    compression = None if args.compression == "none" else args.compression

    season_start = int(args.season_start or 0)
    limit_games = int(args.limit_games or 0)

    sql = """
    WITH base AS (
      SELECT
        s.game_id,
        s.event_id,
        (2000 + substring(s.game_id from 4 for 2)::int)::smallint AS season_start,
        s.point_differential,
        gs.seconds_remaining_regulation AS time_remaining_regulation,
        s.possession_side,
        s.final_winning_team
      FROM derived.pbp_event_state s
      JOIN derived.game_state_by_event gs
        ON gs.event_id = s.event_id
      WHERE gs.period <= 4
        AND gs.seconds_remaining_regulation IS NOT NULL
        AND (%s = 0 OR (2000 + substring(s.game_id from 4 for 2)::int) = %s)
    ),
    games_sel AS (
      SELECT DISTINCT game_id
      FROM base
      ORDER BY game_id
      LIMIT (CASE WHEN %s <= 0 THEN 2147483647 ELSE %s END)
    )
    SELECT b.*
    FROM base b
    JOIN games_sel g ON g.game_id = b.game_id
    ORDER BY b.game_id, b.event_id
    """

    total_rows = 0
    writer: pq.ParquetWriter | None = None
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (season_start, season_start, limit_games, limit_games))
            names = [d.name for d in cur.description]
            schema = pa.schema([pa.field(n, _COL_TYPES.get(n, pa.null())) for n in names])
            writer = pq.ParquetWriter(tmp_path, schema, compression=compression)
            try:
                while True:
                    rows = cur.fetchmany(int(args.chunk_rows))
                    if not rows:
                        break
                    batch = _rows_to_record_batch(names, rows)
                    writer.write_batch(batch)
                    total_rows += len(rows)
            finally:
                writer.close()

        # Manifest stats from DB (same filters as the export).
        stats = conn.execute(
            """
            WITH base AS (
              SELECT
                s.game_id,
                (2000 + substring(s.game_id from 4 for 2)::int) AS season_start,
                gs.seconds_remaining_regulation AS time_remaining_regulation,
                s.possession_side
              FROM derived.pbp_event_state s
              JOIN derived.game_state_by_event gs ON gs.event_id = s.event_id
              WHERE gs.period <= 4 AND gs.seconds_remaining_regulation IS NOT NULL
                AND (%s = 0 OR (2000 + substring(s.game_id from 4 for 2)::int) = %s)
                AND (CASE WHEN %s <= 0 THEN true ELSE s.game_id IN (
                  SELECT DISTINCT s2.game_id
                  FROM derived.pbp_event_state s2
                  JOIN derived.game_state_by_event gs2 ON gs2.event_id = s2.event_id
                  WHERE gs2.period <= 4 AND gs2.seconds_remaining_regulation IS NOT NULL
                    AND (%s = 0 OR (2000 + substring(s2.game_id from 4 for 2)::int) = %s)
                  ORDER BY s2.game_id
                  LIMIT %s
                ) END)
            ),
            base_stats AS (
              SELECT
                COUNT(*) AS rows_total,
                COUNT(DISTINCT game_id) AS games_total,
                MIN(season_start) AS min_season_start,
                MAX(season_start) AS max_season_start,
                MIN(time_remaining_regulation) AS min_time_remaining_regulation,
                MAX(time_remaining_regulation) AS max_time_remaining_regulation,
                COUNT(*) FILTER (WHERE possession_side IS NULL) AS rows_null_possession,
                ROUND(100.0 * COUNT(*) FILTER (WHERE possession_side IS NULL) / NULLIF(COUNT(*), 0), 6) AS pct_null_possession
              FROM base
            ),
            games_times AS (
              SELECT
                b.game_id,
                g.game_time_utc
              FROM (SELECT DISTINCT game_id FROM base) b
              LEFT JOIN games g ON g.game_id = b.game_id
            ),
            time_stats AS (
              SELECT
                MIN(gt.game_time_utc) AS min_game_time_utc,
                MAX(gt.game_time_utc) AS max_game_time_utc,
                COUNT(*) FILTER (WHERE gt.game_time_utc IS NULL) AS games_null_game_time_utc
              FROM games_times gt
            )
            SELECT
              bs.rows_total,
              bs.games_total,
              bs.min_season_start,
              bs.max_season_start,
              bs.min_time_remaining_regulation,
              bs.max_time_remaining_regulation,
              bs.rows_null_possession,
              bs.pct_null_possession,
              ts.min_game_time_utc,
              ts.max_game_time_utc,
              ts.games_null_game_time_utc
            FROM base_stats bs
            CROSS JOIN time_stats ts;
            """,
            (season_start, season_start, limit_games, season_start, season_start, limit_games),
        ).fetchone()

    tmp_path.replace(out_path)

    fetched_at_utc = utc_now_iso_compact()
    manifest = {
        "created_at_utc": fetched_at_utc,
        "source": {
            "type": "postgres_select",
            "table": "derived.pbp_event_state JOIN derived.game_state_by_event",
            "filters": {
                "period_lte": 4,
                "seconds_remaining_regulation_not_null": True,
                "season_start": (None if season_start == 0 else season_start),
                "limit_games": (None if limit_games <= 0 else limit_games),
            },
        },
        "output": {
            "path": str(out_path),
            "format": "parquet",
            "compression": (args.compression if args.compression != "none" else None),
            "schema": list(_COL_TYPES.keys()),
        },
        "stats": {
            "rows_total": int(stats[0]),
            "games_total": int(stats[1]),
            "min_season_start": int(stats[2]),
            "max_season_start": int(stats[3]),
            "min_time_remaining_regulation": int(stats[4]),
            "max_time_remaining_regulation": int(stats[5]),
            "rows_null_possession": int(stats[6]),
            "pct_null_possession": float(stats[7]),
            "min_game_time_utc": (None if stats[8] is None else str(stats[8])),
            "max_game_time_utc": (None if stats[9] is None else str(stats[9])),
            "games_null_game_time_utc": int(stats[10]),
        },
        "notes": [
            "time_remaining_regulation is leak-proof during regulation; seconds_remaining_game is not used.",
            "possession_side is nullable and must be encoded with an explicit 'unknown' category for modeling.",
        ],
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    print(f"Wrote {out_path} rows_written={total_rows}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


