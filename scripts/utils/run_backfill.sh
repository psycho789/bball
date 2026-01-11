#!/usr/bin/env bash
set -euo pipefail

# Run a backfill in the background with:
# - unbuffered stdout/stderr (so logs update continuously)
# - a PID file
# - a DONE marker file when finished
#
# Usage:
#   source .env
#   ./scripts/run_backfill.sh --from 2023-24 --to 2023-24 --workers 2
#
# Outputs:
#   data/reports/backfill_<ts>.{log,jsonl,pid,done}

# If DATABASE_URL isn't exported, try to load it from a local .env file.
if [ -z "${DATABASE_URL:-}" ]; then
  if [ -f ".env" ]; then
    # export all vars defined in .env for this process
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Create .env (cp env.example .env) and export it (source .env)." >&2
  exit 2
fi

# Choose python executable:
# - prefer active venv python if present
# - else prefer .venv/bin/python if present
# - else fall back to python3 on PATH
PYTHON_BIN=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "No Python found. Activate .venv (source .venv/bin/activate) or install python3." >&2
  exit 127
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="data/reports/backfill_${TS}.jsonl"
LOG="data/reports/backfill_${TS}.log"
PIDFILE="data/reports/backfill_${TS}.pid"
DONEFILE="data/reports/backfill_${TS}.done"

mkdir -p data/reports

echo "Starting backfill at ${TS}"
echo "Report: ${REPORT}"
echo "Log:    ${LOG}"

# Run python unbuffered so log updates continuously.
(
  set +e
  echo "python_bin=${PYTHON_BIN}" > "${LOG}"
  PYTHONUNBUFFERED=1 "${PYTHON_BIN}" -u scripts/backfill_seasons.py --dsn "${DATABASE_URL}" --report-out "${REPORT}" "$@" >> "${LOG}" 2>&1
  code=$?
  echo "exit_code=${code}" > "${DONEFILE}"
  exit $code
) &

echo $! > "${PIDFILE}"
echo "PID $(cat "${PIDFILE}") started."
echo "DONE marker will be: ${DONEFILE}"
echo "Tail log: tail -f ${LOG}"


