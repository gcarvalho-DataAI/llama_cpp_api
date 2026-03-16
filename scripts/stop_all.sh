#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

API_PID_FILE="/tmp/llama_proxy.pid"

cd "$ROOT_DIR"

if [[ -f "$API_PID_FILE" ]]; then
  api_pid="$(cat "$API_PID_FILE" || true)"
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill "$api_pid" || true
    echo "Stopped API proxy (pid=${api_pid})"
  fi
  rm -f "$API_PID_FILE"
fi

./scripts/stop_vllm.sh || true
./scripts/stop_llama_servers_multi.sh || true
