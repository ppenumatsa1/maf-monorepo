#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ "${1:-}" == "--" ]]; then
  shift
fi

if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 -- <command> [args...]" >&2
  exit 2
fi

postgres_port="$(
  python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
compose_project="maf-validation-$(date +%s)-${RANDOM}"

cleanup() {
  docker compose --project-name "$compose_project" down --volumes --remove-orphans \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

export COMPOSE_PROJECT_NAME="$compose_project"
export POSTGRES_PORT="$postgres_port"
export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${postgres_port}/maf_workflow?sslmode=disable"

./scripts/local/ensure_test_postgres.sh
"$@"
