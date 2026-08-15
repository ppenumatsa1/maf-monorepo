#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_env() {
  local key="$1"
  local value
  value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$key" 2>/dev/null || true)"
  [[ -n "$value" ]] || {
    echo "AZD environment value $key is required." >&2
    exit 1
  }
  printf '%s' "$value"
}

for binary in az azd; do
  require_bin "$binary"
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
source "${ROOT_DIR}/scripts/foundry/private_profile.sh"
PROFILE_FILE="$(private_profile_resolve "$ROOT_DIR")"

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt

resource_group="$(require_env AZURE_RESOURCE_GROUP)"
[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" ]] || {
  echo "AZURE_RESOURCE_GROUP does not match the selected private release target." >&2
  exit 1
}

backend_app_name="$(require_env BACKEND_CONTAINER_APP_NAME)"
frontend_app_name="$(require_env FRONTEND_CONTAINER_APP_NAME)"
configured_acr_login_server="$(require_env containerRegistryLoginServer)"

backend_schema_management="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$backend_app_name" \
    --query "properties.template.containers[0].env[?name=='DB_SCHEMA_MANAGED_EXTERNALLY'].value | [0]" \
    --output tsv
)"
[[ "$backend_schema_management" == "true" ]] || {
  echo "The production backend must set DB_SCHEMA_MANAGED_EXTERNALLY=true." >&2
  exit 1
}

mapfile -t acr_login_servers < <(
  az acr list --resource-group "$resource_group" --query '[].loginServer' --output tsv
)
[[ "${#acr_login_servers[@]}" == "1" &&
  "${acr_login_servers[0]}" == "$configured_acr_login_server" ]] || {
  echo "Expected exactly one configured private ACR in the selected resource group." >&2
  exit 1
}

for app_name in "$backend_app_name" "$frontend_app_name"; do
  verified=false
  for attempt in $(seq 1 "${APP_IMAGE_VERIFY_MAX_ATTEMPTS:-12}"); do
    revision_name="$(
      az containerapp show \
        --resource-group "$resource_group" \
        --name "$app_name" \
        --query properties.latestReadyRevisionName \
        --output tsv
    )"
    images=()
    if [[ -n "$revision_name" ]]; then
      mapfile -t images < <(
        az containerapp revision show \
          --resource-group "$resource_group" \
          --name "$app_name" \
          --revision "$revision_name" \
          --query 'properties.template.containers[].image' \
          --output tsv
      )
    fi
    if [[ "${#images[@]}" -gt 0 ]]; then
      verified=true
      for image in "${images[@]}"; do
        if [[ "${image,,}" != "${configured_acr_login_server,,}/"* ]]; then
          verified=false
          break
        fi
      done
    fi
    [[ "$verified" == "true" ]] && break
    sleep "${APP_IMAGE_VERIFY_RETRY_SECONDS:-10}"
  done
  [[ "$verified" == "true" ]] || {
    echo "Container App $app_name did not converge to a ready revision in the selected private ACR." >&2
    exit 1
  }
done

echo "Verified active backend and frontend Container App revisions use the selected private ACR."
