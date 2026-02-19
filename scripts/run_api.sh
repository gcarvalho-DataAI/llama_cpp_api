#!/usr/bin/env bash
set -euo pipefail

# Load project .env automatically when present.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

export PYTHONUNBUFFERED=1

HOST="${API_HOST:-127.0.0.1}"
PORT="${API_PORT:-8000}"

if [[ -x "$ROOT_DIR/.venv/bin/uvicorn" ]]; then
  UVICORN_BIN="$ROOT_DIR/.venv/bin/uvicorn"
else
  UVICORN_BIN="uvicorn"
fi

cd "$ROOT_DIR"

exec "$UVICORN_BIN" app.main:app --host "$HOST" --port "$PORT"
