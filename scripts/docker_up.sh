#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE="${1:-lite}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is not available. Install 'docker compose' plugin or docker-compose." >&2
  exit 1
fi

if [[ "$PROFILE" == "full" ]]; then
  echo "Starting full stack: proxy + 8B + 70B Q4 + 70B Q5"
  "${COMPOSE[@]}" --profile full up -d --build
else
  echo "Starting lite stack: proxy + 8B"
  "${COMPOSE[@]}" up -d --build
fi

echo "\nServices:"
"${COMPOSE[@]}" ps
