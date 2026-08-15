#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"
dry_run="${RELEASE_DRY_RUN:-false}"
skip_preflight="${RELEASE_SKIP_PREFLIGHT:-false}"
aggregated="false"
failed_stage="initialization"

get_azd_output() {
  local name="$1"
  azd env get-value "$name" --environment "$environment" 2>/dev/null
}

ensure_release_layout

subscription_id="$(get_azd_output AZURE_SUBSCRIPTION_ID)"
resource_group="$(get_azd_output AZURE_RESOURCE_GROUP)"
location="$(get_azd_output AZURE_LOCATION)"
api_url="${API_URL:-$(get_azd_output API_URL)}"
web_url="${WEB_URL:-$(get_azd_output WEB_URL)}"

[[ -n "$subscription_id" && -n "$resource_group" && -n "$location" ]] || {
  echo "Selected AZD environment is missing required target outputs." >&2
  exit 1
}
[[ "$api_url" =~ ^https?:// && "$web_url" =~ ^https?:// ]] || {
  echo "Selected AZD environment does not contain valid API_URL and WEB_URL outputs." >&2
  exit 1
}

require_selected_target "$environment" "$subscription_id" "$resource_group" "$location"
require_azure_cli_target "$subscription_id"
write_release_context "$environment" "$subscription_id" "$resource_group" "$location"

finalize_release_evidence() {
  local exit_code="$1"
  if [[ "$aggregated" != "true" ]]; then
    python3 scripts/release/aggregate-release-evidence.py "$RELEASE_ARTIFACTS_DIR" >/dev/null 2>&1 || true
  fi
  if [[ "$exit_code" -ne 0 && -f "$RELEASE_ARTIFACTS_DIR/release.json" ]]; then
    python3 scripts/release/release-record.py finalize \
      --release-dir "$RELEASE_ARTIFACTS_DIR" \
      --status failed \
      --completed-at "$(release_now_iso)" \
      --failed-stage "$failed_stage" \
      --error "Release validation stage failed." >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap 'finalize_release_evidence "$?"' EXIT

if [[ "$dry_run" == "true" ]]; then
  cat <<EOF
Hosted release validation dry run:
  make release-preflight
  make release-verify
  make release-smoke
  make release-browser-e2e
  make release-domain-e2e
  make release-eval
  make release-telemetry
  make release-evidence
EOF
  aggregated="true"
  trap - EXIT
  exit 0
fi

run_stage() {
  local name="$1"
  local timing_stage="$2"
  shift 2
  failed_stage="$name"
  release_record_timing stage-start "$timing_stage"

  if ! "$@"; then
    release_record_timing stage-end "$timing_stage" failed
    printf 'Hosted release validation failed: %s\n' "$name" >&2
    exit 1
  fi
  release_record_timing stage-end "$timing_stage" succeeded
}

run_final_evidence() {
  local name="$1"
  shift
  failed_stage="$name"

  if ! "$@"; then
    printf 'Hosted release validation failed: %s\n' "$name" >&2
    exit 1
  fi
}

if [[ "$skip_preflight" != "true" ]]; then
  failed_stage="release preflight"
  if ! make --no-print-directory release-preflight; then
    printf 'Hosted release validation failed: %s\n' "$failed_stage" >&2
    exit 1
  fi
fi
run_stage "deployment verification" verification make --no-print-directory release-verify
run_stage "smoke" smoke make --no-print-directory release-smoke
run_stage "hosted browser E2E" browser_e2e make --no-print-directory release-browser-e2e
run_stage "domain E2E" domain_e2e make --no-print-directory release-domain-e2e
run_stage "Foundry evaluation" evaluation make --no-print-directory release-eval
run_stage "telemetry correlation" telemetry make --no-print-directory release-telemetry
run_final_evidence "final evidence" make --no-print-directory release-evidence
aggregated="true"
