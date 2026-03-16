#!/usr/bin/env bash
set -euo pipefail

VLLM_PID_FILE="/tmp/vllm_server.pid"

if [[ -f "$VLLM_PID_FILE" ]]; then
  vllm_pid="$(cat "$VLLM_PID_FILE" || true)"
  if [[ -n "$vllm_pid" ]] && kill -0 "$vllm_pid" 2>/dev/null; then
    kill "$vllm_pid" || true
    for _ in {1..10}; do
      if ! kill -0 "$vllm_pid" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$vllm_pid" 2>/dev/null; then
      kill -9 "$vllm_pid" || true
    fi
    echo "Stopped vLLM server (pid=${vllm_pid})"
  fi
  rm -f "$VLLM_PID_FILE"
fi

if command -v pkill >/dev/null 2>&1; then
  pkill -9 -f '/\.venv-vllm/bin/vllm serve' 2>/dev/null || true
  pkill -9 -f 'VLLM::EngineCore' 2>/dev/null || true
  pkill -9 -f 'multiprocessing.resource_tracker' 2>/dev/null || true
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k 8001/tcp 2>/dev/null || true
fi
