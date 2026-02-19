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

# Example launcher for llama.cpp server (CPU-focused)
# You must build llama.cpp and download a GGUF model first.
#
# Required env vars:
#   LLAMA_CPP_BIN   -> path to llama.cpp 'server' binary
#   LLAMA_MODEL     -> path to .gguf model
# Optional:
#   LLAMA_PORT      -> default 8080
#   LLAMA_THREADS   -> default auto
#   LLAMA_CTX       -> default 4096
#   LLAMA_N_BATCH   -> default 512
#   LLAMA_HOST      -> default 127.0.0.1
#   LLAMA_THREADS_BATCH -> default auto
#   LLAMA_EMBEDDINGS -> 1 enables embedding endpoint

LLAMA_CPP_BIN="${LLAMA_CPP_BIN:-./llama.cpp/build/bin/llama-server}"
LLAMA_MODEL="${LLAMA_MODEL:-./models/llama.gguf}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_CTX="${LLAMA_CTX:-4096}"
LLAMA_N_BATCH="${LLAMA_N_BATCH:-512}"
LLAMA_THREADS="${LLAMA_THREADS:-0}"
LLAMA_THREADS_BATCH="${LLAMA_THREADS_BATCH:-0}"
LLAMA_EMBEDDINGS="${LLAMA_EMBEDDINGS:-1}"

ARGS=(
  --model "$LLAMA_MODEL"
  --host "$LLAMA_HOST"
  --port "$LLAMA_PORT"
  --ctx-size "$LLAMA_CTX"
  --batch-size "$LLAMA_N_BATCH"
)

if [[ "$LLAMA_THREADS" != "0" ]]; then
  ARGS+=(--threads "$LLAMA_THREADS")
fi

if [[ "$LLAMA_THREADS_BATCH" != "0" ]]; then
  ARGS+=(--threads-batch "$LLAMA_THREADS_BATCH")
fi

if [[ "$LLAMA_EMBEDDINGS" == "1" ]]; then
  ARGS+=(--embeddings)
fi

exec "$LLAMA_CPP_BIN" \
  "${ARGS[@]}"
