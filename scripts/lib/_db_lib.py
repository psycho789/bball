from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_dsn(explicit: str | None) -> str:
    dsn = explicit or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("Missing --dsn and DATABASE_URL is not set.")
    return dsn


def parse_iso8601_z(s: str | None) -> datetime | None:
    if not s:
        return None
    # supports strings like "2024-11-09T03:10:39Z" or "...03:10:39.2Z"
    try:
        if s.endswith("Z"):
            s2 = s[:-1] + "+00:00"
        else:
            s2 = s
        return datetime.fromisoformat(s2)
    except Exception:
        return None


def read_manifest(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("manifest must be a JSON object")
    return obj


def upsert_source_file(conn: psycopg.Connection, manifest: dict[str, Any]) -> int:
    """
    Insert/update a source_files row from a manifest and return source_file_id.

    Uses the unique constraint (source_type, source_key, sha256_hex) as the stable identity.
    """
    required = ["source_type", "source_key", "path", "fetched_at_utc", "sha256_hex", "byte_size"]
    missing = [k for k in required if k not in manifest or manifest.get(k) in (None, "")]
    if missing:
        raise RuntimeError(f"manifest missing required fields: {missing}")

    fetched_at = parse_iso8601_z(str(manifest["fetched_at_utc"]))
    if fetched_at is None:
        # fetched_at_utc is compact like 20251214T123630Z in our scripts
        try:
            fetched_at = datetime.strptime(str(manifest["fetched_at_utc"]), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except Exception as e:
            raise RuntimeError("manifest fetched_at_utc has unexpected format") from e

    sql = """
    INSERT INTO source_files(source_type, source_key, path, fetched_at, http_status, etag, last_modified, sha256_hex, byte_size)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (source_type, source_key, sha256_hex)
    DO UPDATE SET
      path = EXCLUDED.path,
      fetched_at = EXCLUDED.fetched_at,
      http_status = EXCLUDED.http_status,
      etag = EXCLUDED.etag,
      last_modified = EXCLUDED.last_modified,
      byte_size = EXCLUDED.byte_size
    RETURNING source_file_id
    """
    row = conn.execute(
        sql,
        (
            manifest["source_type"],
            manifest["source_key"],
            manifest["path"],
            fetched_at,
            manifest.get("http_status"),
            manifest.get("etag"),
            manifest.get("last_modified"),
            manifest["sha256_hex"],
            int(manifest["byte_size"]),
        ),
    ).fetchone()
    if not row:
        raise RuntimeError("failed to upsert source_files")
    return int(row[0])


@dataclass
class IngestionRun:
    ingest_run_id: int


def start_ingestion_run(conn: psycopg.Connection, *, run_type: str, source_file_id: int | None, target_key: str) -> IngestionRun:
    row = conn.execute(
        """
        INSERT INTO ingestion_runs(run_type, started_at, status, source_file_id, target_key)
        VALUES (%s, now(), 'running', %s, %s)
        RETURNING ingest_run_id
        """,
        (run_type, source_file_id, target_key),
    ).fetchone()
    return IngestionRun(ingest_run_id=int(row[0]))


def finish_ingestion_run_success(
    conn: psycopg.Connection,
    *,
    ingest_run_id: int,
    rows_inserted: int,
    rows_updated: int,
    rows_deleted: int,
) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET status='succeeded',
            finished_at=now(),
            rows_inserted=%s,
            rows_updated=%s,
            rows_deleted=%s,
            error_message=NULL
        WHERE ingest_run_id=%s
        """,
        (rows_inserted, rows_updated, rows_deleted, ingest_run_id),
    )


def finish_ingestion_run_failed(conn: psycopg.Connection, *, ingest_run_id: int, error_message: str) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET status='failed',
            finished_at=now(),
            error_message=%s
        WHERE ingest_run_id=%s
        """,
        (error_message[:20000], ingest_run_id),
    )


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


