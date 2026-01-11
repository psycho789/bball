#!/usr/bin/env bash
set -euo pipefail

# Run the ESPN probabilities backfill in the background with:
# - unbuffered stdout/stderr (so logs update continuously)
# - a PID file
# - a DONE marker file when finished (with exit_code)
#
# Example:
#   ./scripts/run_espn_probabilities_backfill.sh --from 2017-18 --to 2025-26 --workers 16 --requests-per-second 8
#
# Outputs:
#   data/reports/espn_probabilities_backfill_<ts>.{log,pid,done}

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
LOG="data/reports/espn_probabilities_backfill_${TS}.log"
PIDFILE="data/reports/espn_probabilities_backfill_${TS}.pid"
DONEFILE="data/reports/espn_probabilities_backfill_${TS}.done"

mkdir -p data/reports

echo "Starting ESPN probabilities backfill at ${TS}"
echo "Log:  ${LOG}"
echo "PID:  ${PIDFILE}"
echo "Done: ${DONEFILE}"
echo "CWD:  $(pwd)"
echo "Args: $*"
echo ""
echo "Defaults enabled by this runner:"
echo "  - per-season completeness check (prints COMPLETE=true/false)"
echo "  - stop the overall run if a season is incomplete"
echo "  - very verbose logging (--verbose, heartbeat every 5s, progress every 25 games)"
if [ -n "${DATABASE_URL:-}" ]; then
  echo "  - DB load after all seasons complete (DATABASE_URL is set)"
else
  echo "  - DB load after all seasons complete: DISABLED (DATABASE_URL is not set)"
fi
echo ""

# Run python unbuffered so log updates continuously.
(
  set +e
  {
    echo "ts=${TS}"
    echo "python_bin=${PYTHON_BIN}"
    echo "cwd=$(pwd)"
    echo "args=$*"
    if [ -n "${DATABASE_URL:-}" ]; then
      echo "db_load_after=true (DATABASE_URL is set)"
    else
      echo "db_load_after=false (DATABASE_URL is not set)"
    fi
    echo ""
  } > "${LOG}"

  # Always self-audit each season: run completeness checker + stop if incomplete.
  #
  # Also enable very-verbose mode by default so logs show continuous activity:
  # - per-request lines (written/skipped/error)
  # - frequent heartbeats/progress lines
  #
  # You can override any of these by passing your own flags later (they come after DEFAULT_ARGS).
  DEFAULT_ARGS=(
    --run-completeness-check
    --stop-if-incomplete
    --check-show-missing 10
    --verbose
    --heartbeat-seconds 5
    --progress-every 25
  )

  # If DATABASE_URL is set, also run DB migrations + load probabilities items[] AFTER all seasons complete.
  LOAD_ARGS=()
  if [ -n "${DATABASE_URL:-}" ]; then
    LOAD_ARGS=(--load-to-db-after)
  fi

  # Bash 3.2 + `set -u` can be picky about expanding empty arrays; expand LOAD_ARGS safely.
  PYTHONUNBUFFERED=1 "${PYTHON_BIN}" -u scripts/backfill_espn_probabilities_range.py "${DEFAULT_ARGS[@]}" ${LOAD_ARGS[@]+"${LOAD_ARGS[@]}"} "$@" >> "${LOG}" 2>&1
  code=$?
  echo "exit_code=${code}" > "${DONEFILE}"
  exit $code
) &

echo $! > "${PIDFILE}"
echo "PID $(cat "${PIDFILE}") started."
echo "Tail log: tail -f ${LOG}"
echo "Check status: ps -p $(cat "${PIDFILE}") -o pid,etime,command"
echo "Done marker: test -f ${DONEFILE} && cat ${DONEFILE}"


