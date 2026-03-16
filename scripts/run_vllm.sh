#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
fi

export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-${HUGGING_FACE_TOKEN:-}}"
export HF_TOKEN="${HF_TOKEN:-${HUGGING_FACE_TOKEN:-}}"

VLLM_VENV="${VLLM_VENV:-$ROOT_DIR/.venv-vllm}"
VLLM_BIN="${VLLM_BIN:-$VLLM_VENV/bin/vllm}"
VLLM_HOST_VALUE="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT_VALUE="${VLLM_PORT:-8001}"
VLLM_MODEL_VALUE="${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
VLLM_SERVED_MODEL_NAME_VALUE="${VLLM_SERVED_MODEL_NAME:-qwen-linkedin}"
VLLM_GPU_MEMORY_UTILIZATION_VALUE="${VLLM_GPU_MEMORY_UTILIZATION:-0.7}"
VLLM_MAX_MODEL_LEN_VALUE="${VLLM_MAX_MODEL_LEN:-4096}"
VLLM_DTYPE_VALUE="${VLLM_DTYPE:-auto}"
VLLM_EXTRA_ARGS_VALUE="${VLLM_EXTRA_ARGS:-}"
VLLM_ENABLE_V1_MULTIPROCESSING_VALUE="${VLLM_ENABLE_V1_MULTIPROCESSING:-0}"
VLLM_READY_TIMEOUT_S_VALUE="${VLLM_READY_TIMEOUT_S:-240}"
VLLM_PID_FILE="/tmp/vllm_server.pid"
VLLM_LOG_FILE="/tmp/vllm_server.log"

if [[ ! -x "$VLLM_BIN" ]]; then
  echo "vLLM binary not found at $VLLM_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
./scripts/stop_vllm.sh || true

cmd=(
  env "VLLM_ENABLE_V1_MULTIPROCESSING=${VLLM_ENABLE_V1_MULTIPROCESSING_VALUE}"
  "$VLLM_BIN" serve "$VLLM_MODEL_VALUE"
  --served-model-name "$VLLM_SERVED_MODEL_NAME_VALUE"
  --host "$VLLM_HOST_VALUE"
  --port "$VLLM_PORT_VALUE"
  --dtype "$VLLM_DTYPE_VALUE"
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION_VALUE"
  --max-model-len "$VLLM_MAX_MODEL_LEN_VALUE"
)

if [[ -n "$VLLM_EXTRA_ARGS_VALUE" ]]; then
  # shellcheck disable=SC2206
  extra_args=( $VLLM_EXTRA_ARGS_VALUE )
  cmd+=("${extra_args[@]}")
fi

setsid "${cmd[@]}" >"$VLLM_LOG_FILE" 2>&1 < /dev/null &
vllm_pid=$!
echo "$vllm_pid" > "$VLLM_PID_FILE"

echo "Started vLLM model ${VLLM_SERVED_MODEL_NAME_VALUE} on http://${VLLM_HOST_VALUE}:${VLLM_PORT_VALUE} (pid=${vllm_pid})"
echo "vLLM log: ${VLLM_LOG_FILE}"

ready=0
for ((i=0; i<VLLM_READY_TIMEOUT_S_VALUE; i++)); do
  if curl -fsS "http://${VLLM_HOST_VALUE}:${VLLM_PORT_VALUE}/health" >/dev/null 2>&1 \
    && curl -fsS "http://${VLLM_HOST_VALUE}:${VLLM_PORT_VALUE}/v1/models" 2>/dev/null | rg -q "\"id\":\"${VLLM_SERVED_MODEL_NAME_VALUE}\"" ; then
    ready=1
    break
  fi
  if ! kill -0 "$vllm_pid" 2>/dev/null; then
    break
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "vLLM did not become ready within ${VLLM_READY_TIMEOUT_S_VALUE}s" >&2
  tail -n 120 "$VLLM_LOG_FILE" >&2 || true
  ./scripts/stop_vllm.sh || true
  exit 1
fi
