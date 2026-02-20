#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

LLAMA_CPP_BIN="${LLAMA_CPP_BIN:-./llama.cpp/build/bin/llama-server}"
LLAMA_HOST_DEFAULT="${LLAMA_HOST:-127.0.0.1}"
LLAMA_CTX_DEFAULT="${LLAMA_CTX:-4096}"
LLAMA_N_BATCH_DEFAULT="${LLAMA_N_BATCH:-1024}"
LLAMA_THREADS_DEFAULT="${LLAMA_THREADS:-20}"
LLAMA_THREADS_BATCH_DEFAULT="${LLAMA_THREADS_BATCH:-20}"
LLAMA_EMBEDDINGS_DEFAULT="${LLAMA_EMBEDDINGS:-1}"

MODEL_UPSTREAMS="${MODEL_UPSTREAMS:-}"
MODEL_PATHS="${MODEL_PATHS:-}"
ENABLED_MODELS="${ENABLED_MODELS:-}"

if [[ -z "$MODEL_UPSTREAMS" ]]; then
  echo "MODEL_UPSTREAMS is empty; nothing to start." >&2
  exit 1
fi

if [[ -z "$MODEL_PATHS" ]]; then
  echo "MODEL_PATHS is empty; define model=file mappings." >&2
  exit 1
fi

declare -A upstream_map
declare -A path_map
declare -A enabled_map

IFS=',' read -ra upstream_items <<< "$MODEL_UPSTREAMS"
for item in "${upstream_items[@]}"; do
  [[ -z "$item" ]] && continue
  model="${item%%=*}"
  url="${item#*=}"
  model="${model// /}"
  url="${url// /}"
  [[ -z "$model" || -z "$url" || "$url" == "$model" ]] && continue
  upstream_map["$model"]="$url"
done

IFS=',' read -ra path_items <<< "$MODEL_PATHS"
for item in "${path_items[@]}"; do
  [[ -z "$item" ]] && continue
  model="${item%%=*}"
  file="${item#*=}"
  model="${model// /}"
  file="${file# }"
  [[ -z "$model" || -z "$file" || "$file" == "$model" ]] && continue
  path_map["$model"]="$file"
done

if [[ -n "$ENABLED_MODELS" ]]; then
  IFS=',' read -ra enabled_items <<< "$ENABLED_MODELS"
  for model in "${enabled_items[@]}"; do
    model="${model// /}"
    [[ -n "$model" ]] && enabled_map["$model"]=1
  done
fi

pid_file="/tmp/llama_multi_pids"
: > "$pid_file"

started=0
for model in "${!upstream_map[@]}"; do
  if [[ -n "$ENABLED_MODELS" && -z "${enabled_map[$model]:-}" ]]; then
    continue
  fi

  url="${upstream_map[$model]}"
  model_file="${path_map[$model]:-}"
  if [[ -z "$model_file" ]]; then
    echo "Skipping $model: no path in MODEL_PATHS" >&2
    continue
  fi

  if [[ "$url" =~ ^https?://([^:/]+)(:([0-9]+))?$ ]]; then
    host="${BASH_REMATCH[1]}"
    port="${BASH_REMATCH[3]:-8080}"
  else
    echo "Skipping $model: invalid URL '$url'" >&2
    continue
  fi

  [[ -z "$host" ]] && host="$LLAMA_HOST_DEFAULT"

  log_name="$(echo "$model" | tr -c '[:alnum:]_-' '_')"
  log_file="/tmp/llama_${log_name}.log"

  ARGS=(
    --model "$model_file"
    --host "$host"
    --port "$port"
    --ctx-size "$LLAMA_CTX_DEFAULT"
    --batch-size "$LLAMA_N_BATCH_DEFAULT"
  )

  if [[ "$LLAMA_THREADS_DEFAULT" != "0" ]]; then
    ARGS+=(--threads "$LLAMA_THREADS_DEFAULT")
  fi

  if [[ "$LLAMA_THREADS_BATCH_DEFAULT" != "0" ]]; then
    ARGS+=(--threads-batch "$LLAMA_THREADS_BATCH_DEFAULT")
  fi

  if [[ "$LLAMA_EMBEDDINGS_DEFAULT" == "1" ]]; then
    ARGS+=(--embeddings)
  fi

  (
    cd "$ROOT_DIR"
    setsid "$LLAMA_CPP_BIN" "${ARGS[@]}" >"$log_file" 2>&1 < /dev/null &
    pid=$!
    echo "$pid $model $url $model_file" >> "$pid_file"
    echo "Started $model on $url (pid=$pid)"
  )

  started=$((started + 1))
done

if [[ "$started" -eq 0 ]]; then
  echo "No model process started. Check MODEL_UPSTREAMS, MODEL_PATHS, and ENABLED_MODELS." >&2
  exit 1
fi

echo "PIDs saved in $pid_file"
