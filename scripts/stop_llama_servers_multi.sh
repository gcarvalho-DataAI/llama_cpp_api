#!/usr/bin/env bash
set -euo pipefail

pid_file="/tmp/llama_multi_pids"
if [[ ! -f "$pid_file" ]]; then
  echo "No pid file found at $pid_file"
  exit 0
fi

while read -r pid model url _rest; do
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped $model ($url) pid=$pid"
  fi
done < "$pid_file"

rm -f "$pid_file"
echo "Done."
