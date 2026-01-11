#!/bin/bash
# Export only the schemas needed for the webapp (espn, kalshi, derived)
# Excludes the nba schema to reduce data size

set -e

# Default values
HOST="${DB_HOST:-127.0.0.1}"
PORT="${DB_PORT:-5432}"
USER="${DB_USER:-adamvoliva}"
DB="${DB_NAME:-bball_warehouse}"
OUTPUT_FILE="${1:-webapp_schema.sql}"

echo "Exporting webapp schema (espn, kalshi, derived) from ${USER}@${HOST}:${PORT}/${DB}"
echo "Output file: ${OUTPUT_FILE}"

pg_dump \
  -h "${HOST}" \
  -p "${PORT}" \
  -U "${USER}" \
  -d "${DB}" \
  --schema=espn \
  --schema=kalshi \
  --schema=derived \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  > "${OUTPUT_FILE}"

echo "✅ Schema exported to ${OUTPUT_FILE}"
echo ""
echo "To load into Render database:"
echo "  psql \"YOUR_RENDER_DATABASE_URL\" < ${OUTPUT_FILE}"

