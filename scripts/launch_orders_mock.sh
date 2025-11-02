#!/usr/bin/env bash
set -euo pipefail

# Launch the Orders service against a mock SQLite database and in-memory event bus.
# Usage: scripts/launch_orders_mock.sh
# Optional env vars:
#   ORDERS_HOST (default 0.0.0.0)
#   ORDERS_PORT (default 8080)
#   MOCK_SEED_COUNT (default 5)
#   SEED_MOCK_DATA (default 1 - set to 0 to skip seeding)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOCK_DIR="${ROOT}/workspace/services/orders/mock"
mkdir -p "${MOCK_DIR}"

export PYTHONPATH="${PYTHONPATH:-}${PYTHONPATH:+:}${ROOT}"

DB_PATH="${MOCK_DIR}/orders.db"
export ORDERS_DATABASE_URL="${ORDERS_DATABASE_URL:-sqlite+pysqlite:///${DB_PATH}}"
export ORDERS_EVENT_BROKER_URL="${ORDERS_EVENT_BROKER_URL:-memory://}"
export ORDERS_FEATURE_FLAG_TASK_INTENT="${ORDERS_FEATURE_FLAG_TASK_INTENT:-true}"

echo "Using ORDERS_DATABASE_URL=${ORDERS_DATABASE_URL}"
# Reset mock DB on seed to avoid UNIQUE constraint conflicts.
if [[ "${SEED_MOCK_DATA:-1}" -eq 1 && -f "${DB_PATH}" ]]; then
  rm -f "${DB_PATH}"
fi
python - <<'PY'
from services.orders.app import db, models
models.Base.metadata.create_all(bind=db.engine)
PY

if [[ "${SEED_MOCK_DATA:-1}" -eq 1 ]]; then
  MOCK_SEED_COUNT="${MOCK_SEED_COUNT:-5}"
  echo "Seeding ${MOCK_SEED_COUNT} mock orders..."
  python "${ROOT}/scripts/seed_orders_mock.py" --count "${MOCK_SEED_COUNT}"
else
  echo "Skipping mock data seeding (SEED_MOCK_DATA=${SEED_MOCK_DATA:-0})."
fi

HOST="${ORDERS_HOST:-0.0.0.0}"
PORT="${ORDERS_PORT:-8080}"
echo "Starting Orders service on http://${HOST}:${PORT}"
python -m uvicorn services.orders.app.main:app --host "${HOST}" --port "${PORT}"
