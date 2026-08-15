#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
WORK_DIR="$ROOT_DIR/.artifacts/tests/router-$$"
trap 'rm -rf "$WORK_DIR"' EXIT

mkdir -p "$WORK_DIR/scripts/skills" "$WORK_DIR/backend/app/modules/order_resolution" "$WORK_DIR/deployment/contracts" "$WORK_DIR/scripts/release"
cp "$ROOT_DIR/scripts/skills/deployment-mode-router.sh" "$WORK_DIR/scripts/skills/deployment-mode-router.sh"

cd "$WORK_DIR"
git init -q
git config user.email "copilot@example.com"
git config user.name "Copilot"
touch backend/app/modules/order_resolution/service.py
touch deployment/contracts/contract.json
mkdir -p scripts/release
touch scripts/release/existing.sh
git add .
git commit -qm "baseline"

parse_output() {
  local output="$1"
  deploy_mode=""
  validation_mode=""
  infrastructure_action=""
  reason=""
  while IFS='=' read -r key value; do
    case "$key" in
      deploy_mode) deploy_mode="$value" ;;
      validation_mode) validation_mode="$value" ;;
      infrastructure_action) infrastructure_action="$value" ;;
      reason) reason="$value" ;;
    esac
  done <<<"$output"
}

assert_case() {
  local expected_deploy="$1"
  local expected_validation="$2"
  local expected_infrastructure="$3"
  local expected_reason="$4"
  local output

  output="$(./scripts/skills/deployment-mode-router.sh HEAD)"
  parse_output "$output"
  [[ "$deploy_mode" == "$expected_deploy" ]]
  [[ "$validation_mode" == "$expected_validation" ]]
  [[ "$infrastructure_action" == "$expected_infrastructure" ]]
  [[ "$reason" == "$expected_reason" ]]
}

assert_case "app_only" "quick" "none" "no_changed_files"

echo "# changed" >> backend/app/modules/order_resolution/service.py
assert_case "app_only" "full" "none" "frontend_or_workflow_contract_or_hitl_surface_changed"
git checkout -- .
git clean -fd

touch scripts/release/untracked-runtime-change.sh
assert_case "app_only" "full" "preview_required" "release_or_runtime_surface_changed"
git clean -fd

echo "{}" >> deployment/contracts/contract.json
assert_case "app_only" "full" "explicit_apply_required" "infrastructure_contract_or_iac_surface_changed"

echo "Deployment mode router tests passed."
