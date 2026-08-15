#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"
dry_run="${RELEASE_DRY_RUN:-false}"

get_azd_value() {
  azd env get-value "$1" --environment "$environment" 2>/dev/null
}

subscription_id="$(get_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(get_azd_value AZURE_RESOURCE_GROUP)"
location="$(get_azd_value AZURE_LOCATION)"
require_selected_target "$environment" "$subscription_id" "$resource_group" "$location"
require_azure_cli_target "$subscription_id"
write_release_context \
  "$environment" \
  "$subscription_id" \
  "$resource_group" \
  "$location"

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

if [[ "$(release_timing_value app_only_started_at)" == "null" ]]; then
  release_record_timing app-only-start
fi
package_timed_here="false"
if [[ "$(release_timing_value stages.package_build.status)" == "pending" ]]; then
  release_record_timing stage-start package_build
  package_timed_here="true"
fi
release_record_timing stage-start app_deployment

deploy_service() {
  local service="$1"
  azd deploy "$service" --environment "$environment" --no-prompt \
    >"$RELEASE_LOGS_DIR/$service.deploy.log" 2>&1
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
  if [[ "$package_timed_here" == "true" ]]; then
    release_record_timing stage-end package_build failed
  fi
  release_record_timing stage-end app_deployment failed
  echo "App-only deployment failed; inspect logs under $RELEASE_LOGS_DIR." >&2
  exit 1
fi
if [[ "$package_timed_here" == "true" ]]; then
  release_record_timing stage-end package_build succeeded
fi
release_record_timing stage-end app_deployment succeeded

RELEASE_ID="$RELEASE_ID" \
RELEASE_RUN_ID="$RELEASE_ID" \
RELEASE_STARTED_AT="$RELEASE_STARTED_AT" \
AZURE_ENV_NAME="$environment" \
RELEASE_SKIP_PREFLIGHT=true \
make --no-print-directory release-validate
