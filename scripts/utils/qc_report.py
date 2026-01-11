#!/usr/bin/env python3
"""
Warehouse-level QC checks.

Current focus: PBP invariants for a single game_id.
- uniqueness of (game_id, order_number)
- uniqueness of (game_id, action_number)
- monotonic ordering of order_number
- rowcount matches archived JSON actions length (if pbp file provided)
- provenance columns are non-null (guaranteed by schema, but we validate)

Usage:
  python scripts/qc_report.py --dsn "$DATABASE_URL" --game-id 0022400196 --pbp-file data/raw/pbp/0022400196.json --out data/reports/qc_0022400196.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run QC checks for the NBA warehouse.")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--game-id", required=True, help="NBA gameId string")
    p.add_argument("--pbp-file", default="", help="Optional path to archived PBP JSON to validate row count")
    p.add_argument("--out", required=True, help="Output JSON report path")
    p.add_argument("--check-derived", action="store_true", help="Also validate derived.game_state_by_event invariants.")
    return p.parse_args()


def load_actions_count(pbp_file: str) -> int | None:
    if not pbp_file:
        return None
    obj = json.loads(Path(pbp_file).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        return None
    game = obj.get("game")
    if not isinstance(game, dict):
        return None
    actions = game.get("actions")
    if not isinstance(actions, list):
        return None
    return len(actions)


def main() -> int:
    args = parse_args()
    if not args.dsn:
        raise SystemExit("Missing --dsn and DATABASE_URL is not set.")

    expected_actions = load_actions_count(args.pbp_file)
    game_id = args.game_id

    report: dict[str, Any] = {
        "game_id": game_id,
        "expected_actions": expected_actions,
        "checks": [],
        "ok": True,
    }

    def check(name: str, ok: bool, details: Any) -> None:
        report["checks"].append({"name": name, "ok": ok, "details": details})
        if not ok:
            report["ok"] = False

    with psycopg.connect(args.dsn) as conn:
        # counts
        pbp_events = conn.execute("SELECT COUNT(*) FROM pbp_events WHERE game_id=%s", (game_id,)).fetchone()[0]
        check("pbp_events_present", pbp_events > 0, {"pbp_events": pbp_events})

        # rowcount match if we have expected count
        if expected_actions is not None:
            check("pbp_events_count_matches_actions", pbp_events == expected_actions, {"pbp_events": pbp_events, "actions": expected_actions})

        # duplicates by order_number
        dup_order = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT order_number
              FROM pbp_events
              WHERE game_id=%s
              GROUP BY order_number
              HAVING COUNT(*) > 1
            ) t
            """,
            (game_id,),
        ).fetchone()[0]
        check("unique_order_number_within_game", dup_order == 0, {"duplicate_order_numbers": int(dup_order)})

        dup_action = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT action_number
              FROM pbp_events
              WHERE game_id=%s
              GROUP BY action_number
              HAVING COUNT(*) > 1
            ) t
            """,
            (game_id,),
        ).fetchone()[0]
        check("unique_action_number_within_game", dup_action == 0, {"duplicate_action_numbers": int(dup_action)})

        # monotonic check: count inversions by comparing to sorted list
        inv = conn.execute(
            """
            WITH s AS (
              SELECT order_number,
                     LAG(order_number) OVER (ORDER BY order_number) AS prev
              FROM pbp_events
              WHERE game_id=%s
            )
            SELECT COUNT(*) FROM s WHERE prev IS NOT NULL AND order_number < prev
            """,
            (game_id,),
        ).fetchone()[0]
        check("order_number_monotonic", int(inv) == 0, {"inversions": int(inv)})

        # provenance not-null (should be schema-enforced)
        null_prov = conn.execute(
            """
            SELECT COUNT(*) FROM pbp_events
            WHERE game_id=%s AND (source_file_id IS NULL OR last_ingest_run_id IS NULL OR raw_action IS NULL)
            """,
            (game_id,),
        ).fetchone()[0]
        check("provenance_non_null", int(null_prov) == 0, {"rows_missing_provenance": int(null_prov)})

        if args.check_derived:
            # Derived view rowcount should match pbp_events rowcount
            derived_cnt = conn.execute(
                "SELECT COUNT(*) FROM derived.game_state_by_event WHERE game_id=%s",
                (game_id,),
            ).fetchone()[0]
            check("derived_rowcount_matches_pbp_events", int(derived_cnt) == int(pbp_events), {"derived": int(derived_cnt), "pbp_events": int(pbp_events)})

            # Clock parsing should succeed for almost all rows (clock is always present in observed PBP; allow some NULLs).
            null_clock = conn.execute(
                """
                SELECT COUNT(*) FROM derived.game_state_by_event
                WHERE game_id=%s AND seconds_remaining_period IS NULL
                """,
                (game_id,),
            ).fetchone()[0]
            check("derived_clock_parse_non_null", int(null_clock) == 0, {"rows_with_null_seconds_remaining_period": int(null_clock)})

            # seconds_remaining_regulation should be within [0,2880] when non-null
            bad_reg = conn.execute(
                """
                SELECT COUNT(*) FROM derived.game_state_by_event
                WHERE game_id=%s
                  AND seconds_remaining_regulation IS NOT NULL
                  AND (seconds_remaining_regulation < 0 OR seconds_remaining_regulation > 2880)
                """,
                (game_id,),
            ).fetchone()[0]
            check("derived_seconds_remaining_regulation_bounds", int(bad_reg) == 0, {"out_of_bounds_rows": int(bad_reg)})

            # score_diff consistency
            bad_diff = conn.execute(
                """
                SELECT COUNT(*) FROM derived.game_state_by_event
                WHERE game_id=%s AND score_diff_home <> (score_home - score_away)
                """,
                (game_id,),
            ).fetchone()[0]
            check("derived_score_diff_consistent", int(bad_diff) == 0, {"bad_rows": int(bad_diff)})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"QC ok={report['ok']} report={out_path}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


