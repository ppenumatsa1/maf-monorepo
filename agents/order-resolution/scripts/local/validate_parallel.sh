#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ID="parallel-$$"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required for parallel local validation."
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  echo "Docker Compose v2 is required for parallel local validation."
  exit 1
}

declare -a cleanup_specs=()
declare -a pids=()

free_port() {
  python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

cleanup() {
  local spec
  local directory
  local project
  for spec in "${cleanup_specs[@]}"; do
    directory="${spec%%|*}"
    project="${spec#*|}"
    docker compose -f "${directory}/docker-compose.yml" -p "$project" down --volumes --remove-orphans >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

run_lane() {
  local lane="$1"
  local port="$2"
  local project="maf-order-resolution-${lane}-${RUN_ID}"
  local database_url="postgresql://postgres:postgres@127.0.0.1:${port}/maf_workflow?sslmode=disable"

  cleanup_specs+=("${ROOT_DIR}/${lane}|${project}")
  (
    cd "${ROOT_DIR}/${lane}"
    export COMPOSE_PROJECT_NAME="$project"
    export DATABASE_URL="$database_url"
    if [[ "$lane" == "foundry-public" ]]; then
      export POSTGRES_HOST_PORT="$port"
    else
      export POSTGRES_PORT="$port"
    fi
    case "$lane" in
      azure-hosted|foundry-public)
        make bootstrap
        make test
        make eval-backend
        make test-e2e
        ;;
      foundry-private)
        make test
        ;;
    esac
  ) &
  pids+=("$!")
}

# Azure-hosted and Foundry-public execute local workflow tests, deterministic
# evaluations, and their local E2E gates. Foundry-private intentionally runs
# only basic local tests; its E2E and evaluations require later private-lane
# review and post-deployment evidence.
run_lane "azure-hosted" "$(free_port)"
run_lane "foundry-public" "$(free_port)"
run_lane "foundry-private" "$(free_port)"

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done

exit "$status"
