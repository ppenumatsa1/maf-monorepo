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

allocate_postgres_port() {
  python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

compose_project=""

cleanup() {
  [[ -n "$compose_project" ]] || return 0
  docker compose --project-name "$compose_project" down --volumes --remove-orphans \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_attempts="${ISOLATED_POSTGRES_START_ATTEMPTS:-3}"
for ((attempt = 1; attempt <= start_attempts; attempt += 1)); do
  compose_project="maf-validation-$(date +%s)-${RANDOM}"
  postgres_port="$(allocate_postgres_port)"
  export COMPOSE_PROJECT_NAME="$compose_project"
  export POSTGRES_PORT="$postgres_port"
  export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${postgres_port}/maf_workflow?sslmode=disable"

  if ./scripts/local/ensure_test_postgres.sh; then
    "$@"
    exit
  fi

  cleanup
  compose_project=""
  if [[ "$attempt" -lt "$start_attempts" ]]; then
    echo "Retrying isolated PostgreSQL startup with a fresh port ($((attempt + 1))/${start_attempts})..." >&2
    sleep "$attempt"
  fi
done

echo "Unable to start isolated PostgreSQL after ${start_attempts} attempts." >&2
exit 1
