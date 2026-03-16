#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
fi

API_HOST_VALUE="${API_HOST:-127.0.0.1}"
API_PORT_VALUE="${API_PORT:-8000}"
API_PID_FILE="/tmp/llama_proxy.pid"
API_LOG_FILE="/tmp/llama_proxy.log"
INFERENCE_BACKEND_VALUE="${INFERENCE_BACKEND:-llama.cpp}"

cd "$ROOT_DIR"

if [[ "$INFERENCE_BACKEND_VALUE" == "vllm" ]]; then
  ./scripts/stop_llama_servers_multi.sh || true
  ./scripts/run_vllm.sh
else
  ./scripts/stop_vllm.sh || true
  ./scripts/stop_llama_servers_multi.sh || true
  ./scripts/run_llama_servers_multi.sh
fi

if [[ -f "$API_PID_FILE" ]]; then
  old_pid="$(cat "$API_PID_FILE" || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" || true
    sleep 1
  fi
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${API_PORT_VALUE}/tcp" 2>/dev/null || true
fi

setsid ./scripts/run_api.sh >"$API_LOG_FILE" 2>&1 < /dev/null &
api_pid=$!
echo "$api_pid" > "$API_PID_FILE"

sleep 2

echo "Backend: ${INFERENCE_BACKEND_VALUE}"
echo "API started on http://${API_HOST_VALUE}:${API_PORT_VALUE} (pid=${api_pid})"
echo "API log: ${API_LOG_FILE}"
