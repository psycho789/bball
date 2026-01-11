#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for connecting to Postgres using DATABASE_URL.
#
# Usage:
#   source .env
#   ./scripts/psql.sh
#
# Or pass a DSN explicitly:
#   ./scripts/psql.sh 'postgresql://user:pass@127.0.0.1:5432/bball_warehouse'

DSN="${1:-${DATABASE_URL:-}}"
if [ -z "${DSN}" ]; then
  echo "Missing DSN. Provide as arg or set DATABASE_URL (e.g. source .env)." >&2
  exit 2
fi

exec psql "${DSN}"


