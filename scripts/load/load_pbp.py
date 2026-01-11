#!/usr/bin/env python3
"""
Load a single archived PBP JSON file (and its manifest) into PostgreSQL.

Idempotency:
- Upserts source_files by (source_type, source_key, sha256_hex)
- Upserts pbp_events by (game_id, order_number)
- Rebuilds child tables (qualifiers, people_filter) for the game deterministically

Run tracking:
- ingestion_runs row is created as 'running' and finalized as succeeded/failed
- pbp_events.source_file_id and pbp_events.last_ingest_run_id are set for all rows
- game_ingestion_state is updated on success

Usage:
  python scripts/load_pbp.py \
    --pbp-file data/raw/pbp/0022400196.json \
    --manifest-file data/raw/pbp/0022400196.json.manifest.json \
    --dsn "$DATABASE_URL"
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from psycopg import errors
from psycopg.types.json import Jsonb
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from scripts.lib._db_lib import (
    connect,
    finish_ingestion_run_failed,
    finish_ingestion_run_success,
    get_dsn,
    parse_iso8601_z,
    read_manifest,
    start_ingestion_run,
    upsert_source_file,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load NBA PBP JSON into Postgres (one game).")
    p.add_argument("--dsn", default=None, help="Postgres DSN (or set DATABASE_URL).")
    p.add_argument("--pbp-file", required=True, help="Path to archived PBP JSON")
    p.add_argument("--manifest-file", required=True, help="Path to manifest JSON (from fetcher)")
    p.add_argument(
        "--no-rebuild-children",
        action="store_true",
        help="Do NOT rebuild qualifiers/people_filter (not recommended). Default behavior rebuilds.",
    )
    return p.parse_args()


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _safe_bool_from_int(v: Any) -> bool:
    return True if v == 1 or v is True else False


def _upsert_team(conn, team_id: int, tricode: str | None) -> None:
    if not tricode:
        return
    conn.execute(
        """
        INSERT INTO teams(team_id, team_tricode)
        VALUES (%s, %s)
        ON CONFLICT (team_id) DO UPDATE SET team_tricode=EXCLUDED.team_tricode
        """,
        (team_id, tricode),
    )


def _upsert_player(conn, person_id: int, player_name: str | None, player_name_i: str | None) -> None:
    conn.execute(
        """
        INSERT INTO players(person_id, display_last_name, display_name_initial)
        VALUES (%s, %s, %s)
        ON CONFLICT (person_id) DO UPDATE SET
          display_last_name = COALESCE(EXCLUDED.display_last_name, players.display_last_name),
          display_name_initial = COALESCE(EXCLUDED.display_name_initial, players.display_name_initial),
          updated_at = now()
        """,
        (person_id, player_name, player_name_i),
    )


def _upsert_official(conn, official_id: int) -> None:
    conn.execute(
        "INSERT INTO officials(official_id) VALUES (%s) ON CONFLICT (official_id) DO NOTHING",
        (official_id,),
    )


def main() -> int:
    args = parse_args()
    dsn = get_dsn(args.dsn)

    pbp_path = Path(args.pbp_file)
    manifest_path = Path(args.manifest_file)
    pbp_obj = json.loads(pbp_path.read_text(encoding="utf-8"))
    if not isinstance(pbp_obj, dict):
        raise RuntimeError("PBP file must be a JSON object")

    game = pbp_obj.get("game")
    if not isinstance(game, dict):
        raise RuntimeError("PBP missing game object")
    game_id = str(game.get("gameId"))
    actions = game.get("actions")
    if not isinstance(actions, list):
        raise RuntimeError("PBP missing game.actions list")

    # Normalize older/alternate PBP archives to satisfy loader invariants:
    # - stats.nba.com playbyplayv3 payloads often omit `orderNumber` but include `actionNumber`.
    # - we use (game_id, order_number) as our stable uniqueness key in Postgres.
    seen_order: set[int] = set()
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            continue
        order_number = _safe_int(a.get("orderNumber"))
        if order_number is None:
            action_number = _safe_int(a.get("actionNumber"))
            if action_number is None:
                order_number = (i + 1) * 10000
            else:
                order_number = action_number * 10000
            while order_number in seen_order:
                order_number += 1
            a["orderNumber"] = order_number
        if order_number is not None:
            seen_order.add(order_number)

    # From here on, only process dict actions, in deterministic order.
    actions = [a for a in actions if isinstance(a, dict)]
    actions.sort(key=lambda a: (int(a.get("orderNumber") or 0), int(a.get("actionNumber") or 0)))

    manifest = read_manifest(manifest_path)

    rows_inserted = 0
    rows_updated = 0
    rows_deleted = 0

    # Retry to handle occasional deadlocks when running multiple workers.
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        with connect(dsn) as conn:
            run_id = None
            try:
                with conn.transaction():
                    # Ensure game exists
                    conn.execute("INSERT INTO games(game_id) VALUES (%s) ON CONFLICT (game_id) DO NOTHING", (game_id,))

                    source_file_id = upsert_source_file(conn, manifest)
                    run = start_ingestion_run(conn, run_type="load_pbp", source_file_id=source_file_id, target_key=game_id)
                    run_id = run.ingest_run_id

                    # Upsert dimensions found in actions
                    for a in actions:
                        tid = _safe_int(a.get("teamId"))
                        if tid == 0:
                            tid = None
                        tri = a.get("teamTricode")
                        if tid is not None:
                            _upsert_team(conn, tid, tri)

                        pid = _safe_int(a.get("personId"))
                        if pid is not None and pid != 0:
                            _upsert_player(conn, pid, a.get("playerName"), a.get("playerNameI"))

                        for extra_pid_key in (
                            "assistPersonId",
                            "blockPersonId",
                            "stealPersonId",
                            "foulDrawnPersonId",
                            "jumpBallWonPersonId",
                            "jumpBallLostPersonId",
                            "jumpBallRecoverdPersonId",
                        ):
                            extra_pid = _safe_int(a.get(extra_pid_key))
                            if extra_pid is not None and extra_pid != 0:
                                _upsert_player(conn, extra_pid, None, None)

                        oid = _safe_int(a.get("officialId"))
                        if oid is not None and oid != 0:
                            _upsert_official(conn, oid)

                    event_ids_by_order: dict[int, int] = {}
                    last_score_home = 0
                    last_score_away = 0
                    for a in actions:
                        order_number = _safe_int(a.get("orderNumber"))
                        if order_number is None:
                            raise RuntimeError("action missing orderNumber")

                        action_number = _safe_int(a.get("actionNumber"))
                        if action_number is None:
                            raise RuntimeError("action missing actionNumber")

                        period = _safe_int(a.get("period"))
                        if period is None:
                            raise RuntimeError("action missing period")

                        period_type = str(a.get("periodType") or "")
                        clock = str(a.get("clock") or "")
                        action_type = str(a.get("actionType") or "")
                        sub_type = str(a.get("subType") or "")
                        description = str(a.get("description") or "")

                        # Some feeds leave score fields blank ("") on non-scoring events (e.g. jump ball).
                        # Carry-forward the last known score (starting from 0-0).
                        score_home = _safe_int(a.get("scoreHome"))
                        score_away = _safe_int(a.get("scoreAway"))
                        if score_home is None:
                            score_home = last_score_home
                        if score_away is None:
                            score_away = last_score_away
                        last_score_home = score_home
                        last_score_away = score_away

                        team_id = _safe_int(a.get("teamId"))
                        if team_id == 0:
                            team_id = None
                        possession_team_id = _safe_int(a.get("possession"))
                        if possession_team_id == 0:
                            possession_team_id = None

                        person_id = _safe_int(a.get("personId"))
                        if person_id == 0:
                            person_id = None

                        edited_at = parse_iso8601_z(a.get("edited"))
                        time_actual = parse_iso8601_z(a.get("timeActual"))

                        is_field_goal = _safe_bool_from_int(a.get("isFieldGoal"))
                        is_target_score_last_period = bool(a.get("isTargetScoreLastPeriod"))

                        x = a.get("x")
                        y = a.get("y")
                        x_legacy = _safe_int(a.get("xLegacy"))
                        y_legacy = _safe_int(a.get("yLegacy"))
                        side = a.get("side")
                        descriptor = a.get("descriptor")

                        ins = conn.execute(
                            """
                            INSERT INTO pbp_events(
                              game_id, action_number, order_number, period, period_type, clock, time_actual,
                              action_type, sub_type, descriptor, description, edited_at,
                              team_id, possession_team_id, person_id,
                              score_home, score_away, is_field_goal, is_target_score_last_period,
                              x, y, x_legacy, y_legacy, side,
                              source_file_id, last_ingest_run_id, raw_action
                            )
                            VALUES (
                              %s,%s,%s,%s,%s,%s,%s,
                              %s,%s,%s,%s,%s,
                              %s,%s,%s,
                              %s,%s,%s,%s,
                              %s,%s,%s,%s,%s,
                              %s,%s,%s
                            )
                            ON CONFLICT (game_id, action_number) DO UPDATE SET
                              order_number = EXCLUDED.order_number,
                              period = EXCLUDED.period,
                              period_type = EXCLUDED.period_type,
                              clock = EXCLUDED.clock,
                              time_actual = EXCLUDED.time_actual,
                              action_type = EXCLUDED.action_type,
                              sub_type = EXCLUDED.sub_type,
                              descriptor = EXCLUDED.descriptor,
                              description = EXCLUDED.description,
                              edited_at = EXCLUDED.edited_at,
                              team_id = EXCLUDED.team_id,
                              possession_team_id = EXCLUDED.possession_team_id,
                              person_id = EXCLUDED.person_id,
                              score_home = EXCLUDED.score_home,
                              score_away = EXCLUDED.score_away,
                              is_field_goal = EXCLUDED.is_field_goal,
                              is_target_score_last_period = EXCLUDED.is_target_score_last_period,
                              x = EXCLUDED.x,
                              y = EXCLUDED.y,
                              x_legacy = EXCLUDED.x_legacy,
                              y_legacy = EXCLUDED.y_legacy,
                              side = EXCLUDED.side,
                              source_file_id = EXCLUDED.source_file_id,
                              last_ingest_run_id = EXCLUDED.last_ingest_run_id,
                              raw_action = EXCLUDED.raw_action
                            RETURNING event_id, (xmax = 0) AS inserted
                            """,
                            (
                                game_id,
                                action_number,
                                order_number,
                                period,
                                period_type,
                                clock,
                                time_actual,
                                action_type,
                                sub_type,
                                descriptor,
                                description,
                                edited_at,
                                team_id,
                                possession_team_id,
                                person_id,
                                score_home,
                                score_away,
                                is_field_goal,
                                is_target_score_last_period,
                                x,
                                y,
                                x_legacy,
                                y_legacy,
                                side,
                                source_file_id,
                                run_id,
                                Jsonb(a),
                            ),
                        ).fetchone()

                        event_id = int(ins[0])
                        if bool(ins[1]):
                            rows_inserted += 1
                        else:
                            rows_updated += 1

                        event_ids_by_order[order_number] = event_id

                    rebuild_children = not args.no_rebuild_children
                    if rebuild_children:
                        rows_deleted += conn.execute(
                            """
                            DELETE FROM pbp_event_qualifiers q
                            USING pbp_events e
                            WHERE q.event_id = e.event_id AND e.game_id = %s
                            """,
                            (game_id,),
                        ).rowcount
                        rows_deleted += conn.execute(
                            """
                            DELETE FROM pbp_event_people_filter f
                            USING pbp_events e
                            WHERE f.event_id = e.event_id AND e.game_id = %s
                            """,
                            (game_id,),
                        ).rowcount

                        for a in actions:
                            order_number = int(a["orderNumber"])
                            event_id = event_ids_by_order[order_number]

                            for q in a.get("qualifiers") or []:
                                if not q:
                                    continue
                                conn.execute(
                                    "INSERT INTO pbp_event_qualifiers(event_id, qualifier) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                    (event_id, str(q)),
                                )

                            for pid in a.get("personIdsFilter") or []:
                                pid_i = _safe_int(pid)
                                if pid_i is None or pid_i == 0:
                                    continue
                                _upsert_player(conn, pid_i, None, None)
                                conn.execute(
                                    "INSERT INTO pbp_event_people_filter(event_id, person_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                    (event_id, pid_i),
                                )

                    max_order = max(int(a["orderNumber"]) for a in actions) if actions else None
                    conn.execute(
                        """
                        INSERT INTO game_ingestion_state(
                          game_id, last_success_run_id, last_success_source_file_id, last_success_at,
                          last_seen_action_count, last_seen_max_order_number, updated_at
                        )
                        VALUES (%s,%s,%s, now(), %s, %s, now())
                        ON CONFLICT (game_id) DO UPDATE SET
                          last_success_run_id = EXCLUDED.last_success_run_id,
                          last_success_source_file_id = EXCLUDED.last_success_source_file_id,
                          last_success_at = now(),
                          last_seen_action_count = EXCLUDED.last_seen_action_count,
                          last_seen_max_order_number = EXCLUDED.last_seen_max_order_number,
                          updated_at = now()
                        """,
                        (game_id, run_id, source_file_id, len(actions), max_order),
                    )

                    finish_ingestion_run_success(
                        conn,
                        ingest_run_id=run_id,
                        rows_inserted=rows_inserted,
                        rows_updated=rows_updated,
                        rows_deleted=rows_deleted,
                    )

                print(
                    f"Loaded game_id={game_id} actions={len(actions)} "
                    f"inserted={rows_inserted} updated={rows_updated} deleted={rows_deleted}"
                )
                return 0
            except (errors.DeadlockDetected, errors.SerializationFailure) as e:
                # Mark current run failed and retry.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    if run_id is not None:
                        finish_ingestion_run_failed(conn, ingest_run_id=run_id, error_message=f"retryable_db_error: {e}")
                except Exception:
                    pass
                if attempt >= max_attempts:
                    raise
                # backoff
                time.sleep(0.25 * attempt)
                continue
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    if run_id is not None:
                        finish_ingestion_run_failed(conn, ingest_run_id=run_id, error_message=str(e))
                except Exception:
                    pass
                raise


if __name__ == "__main__":
    raise SystemExit(main())


