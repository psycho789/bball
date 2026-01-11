#!/usr/bin/env python3
"""
Simple SQL-first migration runner for PostgreSQL.

Applies *.sql files in lexicographic order from db/migrations/, recording each applied
filename in schema_migrations.

Usage:
  python3 scripts/migrate.py --dsn "$DATABASE_URL"

Notes:
  - Designed to be idempotent: already-applied migrations are skipped.
  - Each migration is executed inside a transaction; failure rolls back that migration.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg


SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
""".strip()


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply SQL migrations to PostgreSQL.")
    p.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN, e.g. postgresql://user:pass@host:5432/dbname (or set DATABASE_URL).",
    )
    p.add_argument(
        "--migrations-dir",
        default="db/migrations",
        help="Directory containing ordered *.sql migration files.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which migrations would run, but do not apply anything.",
    )
    args = p.parse_args()
    if not args.dry_run and not args.dsn:
        p.error("Missing --dsn and DATABASE_URL is not set.")
    return args


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    if not migrations_dir.exists() or not migrations_dir.is_dir():
        raise RuntimeError(f"migrations dir not found: {migrations_dir}")

    paths = sorted([p for p in migrations_dir.iterdir() if p.is_file() and p.name.endswith(".sql")])
    migrations: list[Migration] = []
    for p in paths:
        migrations.append(Migration(version=p.name, path=p))
    return migrations


def fetch_applied_versions(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_MIGRATIONS_DDL)
        cur.execute("SELECT version FROM schema_migrations ORDER BY version;")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn: psycopg.Connection, m: Migration) -> None:
    sql_text = m.path.read_text(encoding="utf-8")
    if not sql_text.strip():
        raise RuntimeError(f"migration file is empty: {m.path}")

    with conn.transaction():
        with conn.cursor() as cur:
            # Postgres supports multiple statements in a single query string.
            cur.execute(sql_text)
            cur.execute("INSERT INTO schema_migrations(version) VALUES (%s);", (m.version,))


def main() -> int:
    args = parse_args()
    migrations_dir = Path(args.migrations_dir)
    migrations = discover_migrations(migrations_dir)

    if args.dry_run:
        print("Dry run. Migrations found:")
        for m in migrations:
            print(f" - {m.version}")
        return 0

    with psycopg.connect(args.dsn) as conn:
        applied = fetch_applied_versions(conn)
        to_apply = [m for m in migrations if m.version not in applied]

        if not to_apply:
            print("No pending migrations.")
            return 0

        print(f"Applying {len(to_apply)} migration(s)...")
        for m in to_apply:
            print(f" -> {m.version}")
            apply_migration(conn, m)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


