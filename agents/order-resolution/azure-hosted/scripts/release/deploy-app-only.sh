#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

environment="${AZURE_ENV_NAME:-maf-ora-azure}"
release_run_id="${RELEASE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
artifacts_dir="$ROOT_DIR/.artifacts/release/$release_run_id"
dry_run="${RELEASE_DRY_RUN:-false}"

if [[ "$dry_run" == "true" ]]; then
  cat <<EOF
App-only release dry run:
  azd deploy backend --environment $environment --no-prompt
  azd deploy frontend --environment $environment --no-prompt
  make release-validate
No infrastructure provisioning will be invoked.
EOF
  exit 0
fi

mkdir -p "$artifacts_dir"

deploy_service() {
  local service="$1"
  azd deploy "$service" --environment "$environment" --no-prompt \
    >"$artifacts_dir/$service.deploy.log" 2>&1
}

deploy_service backend &
backend_pid=$!
deploy_service frontend &
frontend_pid=$!

backend_status=0
frontend_status=0
wait "$backend_pid" || backend_status=$?
wait "$frontend_pid" || frontend_status=$?

if (( backend_status != 0 || frontend_status != 0 )); then
  echo "App-only deployment failed; inspect logs under .artifacts/release/$release_run_id." >&2
  exit 1
fi

RELEASE_RUN_ID="$release_run_id" \
AZURE_ENV_NAME="$environment" \
make --no-print-directory release-validate
