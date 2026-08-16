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

resolve_app_names() {
  az containerapp list \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --output json |
    python3 -c '
import json
import sys

apps = json.load(sys.stdin)
by_service = {}
for app in apps:
    service = (app.get("tags") or {}).get("azd-service-name")
    if service in {"backend", "frontend"}:
        by_service.setdefault(service, []).append(app["name"])
for service in ("backend", "frontend"):
    matches = by_service.get(service, [])
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one Container App tagged azd-service-name={service}.")
    print(matches[0])
'
}

converge_ingress() {
  local app_name="$1"
  local ingress_type="$2"
  local target_port="$3"
  az containerapp ingress enable \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --type "$ingress_type" \
    --target-port "$target_port" \
    --transport auto \
    --allow-insecure false \
    --only-show-errors \
    --output none
}

pin_active_image() {
  local app_name="$1"
  local image registry repository_tag repository digest pinned_image
  image="$(
    az containerapp show \
      --name "$app_name" \
      --resource-group "$resource_group" \
      --subscription "$subscription_id" \
      --query 'properties.template.containers[0].image' \
      --output tsv
  )"
  if [[ "$image" == *@sha256:* ]]; then
    printf '%s\n' "$image"
    return
  fi
  registry="${image%%/*}"
  repository_tag="${image#*/}"
  repository="${repository_tag%:*}"
  digest="$(
    az acr repository show \
      --name "${registry%%.*}" \
      --image "$repository_tag" \
      --subscription "$subscription_id" \
      --query digest \
      --output tsv
  )"
  [[ "$digest" == sha256:* ]] || {
    echo "Unable to resolve immutable digest for $image." >&2
    return 1
  }
  pinned_image="$registry/$repository@$digest"
  az containerapp update \
    --name "$app_name" \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --image "$pinned_image" \
    --only-show-errors \
    --output none
  printf '%s\n' "$pinned_image"
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

readarray -t app_names < <(resolve_app_names)
[[ "${#app_names[@]}" == 2 ]] || {
  echo "Unable to resolve backend and frontend Container Apps." >&2
  exit 1
}
backend_app="${app_names[0]}"
frontend_app="${app_names[1]}"
pin_active_image "$backend_app" >/dev/null &
backend_pin_pid=$!
pin_active_image "$frontend_app" >/dev/null &
frontend_pin_pid=$!
backend_pin_status=0
frontend_pin_status=0
wait "$backend_pin_pid" || backend_pin_status=$?
wait "$frontend_pin_pid" || frontend_pin_status=$?
if (( backend_pin_status != 0 || frontend_pin_status != 0 )); then
  echo "Unable to pin both deployed images to immutable digests." >&2
  exit 1
fi
converge_ingress "$backend_app" internal 8000
backend_fqdn="$(
  az containerapp show \
    --name "$backend_app" \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --query properties.configuration.ingress.fqdn \
    --output tsv
)"
[[ "$backend_fqdn" == *.internal.* ]] || {
  echo "Backend internal ingress did not produce an internal FQDN." >&2
  exit 1
}
az containerapp update \
  --name "$frontend_app" \
  --resource-group "$resource_group" \
  --subscription "$subscription_id" \
  --set-env-vars "NGINX_API_UPSTREAM=https://$backend_fqdn" \
  --only-show-errors \
  --output none
converge_ingress "$frontend_app" external 5173

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
