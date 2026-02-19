#!/usr/bin/env bash
set -euo pipefail

# Downloads only the remaining large variants (70B Q4 + 70B Q5 shards).
# Requires HUGGING_FACE_TOKEN in environment or .env.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Python da venv nao encontrado em $VENV_PY"
  echo "Crie a venv e instale deps antes de continuar."
  exit 1
fi

exec "$VENV_PY" "$ROOT_DIR/scripts/download_models.py" --set 70b-q4 --set 70b-q5
