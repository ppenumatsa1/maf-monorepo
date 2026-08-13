#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_bin az
require_bin azd
require_bin make

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

FOUNDRY_RELEASE_BASE_REF="${FOUNDRY_RELEASE_BASE_REF:-HEAD}"
FOUNDRY_VALIDATION_MODE="${FOUNDRY_VALIDATION_MODE:-}"
FOUNDRY_DEPLOY_MODE="${FOUNDRY_DEPLOY_MODE:-}"
FOUNDRY_SMOKE_MODE="${FOUNDRY_SMOKE_MODE:-happy}"
FOUNDRY_DEPLOYMENT_PROFILE="${FOUNDRY_DEPLOYMENT_PROFILE:-}"

if [[ -n "$FOUNDRY_DEPLOYMENT_PROFILE" ]]; then
  bash "$ROOT_DIR/deployment/apply-azd-profile.sh" "$FOUNDRY_DEPLOYMENT_PROFILE"
fi
./scripts/foundry/ensure_foundry_azd_defaults.sh

wait_for_parallel_jobs() {
  local status=0
  local pid
  for pid in "$@"; do
    if ! wait "$pid"; then
      status=1
    fi
  done
  return "$status"
}

router_output="$(./scripts/skills/deployment-mode-router.sh "$FOUNDRY_RELEASE_BASE_REF")"
printf '%s\n' "$router_output"

deploy_mode="$(printf '%s\n' "$router_output" | sed -n 's/^deploy_mode=//p' | tail -n 1)"
validation_mode="$(printf '%s\n' "$router_output" | sed -n 's/^validation_mode=//p' | tail -n 1)"
reason="$(printf '%s\n' "$router_output" | sed -n 's/^reason=//p' | tail -n 1)"

if [[ -n "$FOUNDRY_DEPLOY_MODE" ]]; then
  deploy_mode="$FOUNDRY_DEPLOY_MODE"
fi
if [[ -n "$FOUNDRY_VALIDATION_MODE" ]]; then
  validation_mode="$FOUNDRY_VALIDATION_MODE"
fi

echo "Release router selected deploy_mode=${deploy_mode} validation_mode=${validation_mode} reason=${reason} base_ref=${FOUNDRY_RELEASE_BASE_REF}"

case "$validation_mode" in
  quick)
    validation_target=validate-quick
    ;;
  full)
    validation_target=validate-full
    ;;
  *)
    echo "Unsupported validation mode: $validation_mode" >&2
    exit 1
    ;;
esac

make "$validation_target" &
validation_pid=$!
make foundry-iac-build &
iac_pid=$!
wait_for_parallel_jobs "$validation_pid" "$iac_pid"

case "$deploy_mode" in
  app_only)
    make foundry-release-deploy
    make foundry-appinsights-connection
    ;;
  full)
    echo "Routine releases are app-only. Run the explicitly approved provisioning workflow separately." >&2
    exit 1
    ;;
  *)
    echo "Unsupported deploy mode: $deploy_mode" >&2
    exit 1
    ;;
esac

SMOKE_MODE="$FOUNDRY_SMOKE_MODE" make foundry-smoke
make foundry-eval &
evaluation_pid=$!
if ! make foundry-hosted-e2e; then
  wait "$evaluation_pid" || true
  exit 1
fi
make foundry-telemetry &
telemetry_pid=$!
wait_for_parallel_jobs "$evaluation_pid" "$telemetry_pid"

echo "Underwriting Foundry public release completed."
