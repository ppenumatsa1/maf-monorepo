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
  value="$(azd env get-value "$key" 2>/dev/null || true)"
  [[ -n "$value" ]] || {
    echo "AZD environment value $key is required." >&2
    exit 1
  }
  printf '%s' "$value"
}

for binary in az azd; do
  require_bin "$binary"
done

: "${AZD_ENVIRONMENT_NAME:?AZD_ENVIRONMENT_NAME is required}"
: "${TARGET_RESOURCE_GROUP:?TARGET_RESOURCE_GROUP is required}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"

cd "$FOUNDRY_DIR"
azd env select "$AZD_ENVIRONMENT_NAME" --no-prompt

resource_group="$(require_env AZURE_RESOURCE_GROUP)"
[[ "$resource_group" == "$TARGET_RESOURCE_GROUP" ]] || {
  echo "AZURE_RESOURCE_GROUP does not match the selected private release target." >&2
  exit 1
}

backend_app_name="$(require_env BACKEND_CONTAINER_APP_NAME)"
frontend_app_name="$(require_env FRONTEND_CONTAINER_APP_NAME)"
configured_acr_login_server="$(require_env containerRegistryLoginServer)"

mapfile -t acr_login_servers < <(
  az acr list --resource-group "$resource_group" --query '[].loginServer' --output tsv
)
[[ "${#acr_login_servers[@]}" == "1" &&
  "${acr_login_servers[0]}" == "$configured_acr_login_server" ]] || {
  echo "Expected exactly one configured private ACR in the selected resource group." >&2
  exit 1
}

for app_name in "$backend_app_name" "$frontend_app_name"; do
  revision_name="$(
    az containerapp show \
      --resource-group "$resource_group" \
      --name "$app_name" \
      --query properties.latestReadyRevisionName \
      --output tsv
  )"
  [[ -n "$revision_name" ]] || {
    echo "Container App $app_name has no ready revision." >&2
    exit 1
  }

  mapfile -t images < <(
    az containerapp revision show \
      --resource-group "$resource_group" \
      --name "$app_name" \
      --revision "$revision_name" \
      --query 'properties.template.containers[].image' \
      --output tsv
  )
  [[ "${#images[@]}" -gt 0 ]] || {
    echo "Container App $app_name has no container images in its ready revision." >&2
    exit 1
  }
  for image in "${images[@]}"; do
    [[ "${image,,}" == "${configured_acr_login_server,,}/"* ]] || {
      echo "Container App $app_name uses an image outside the selected private ACR." >&2
      exit 1
    }
  done
done

echo "Verified active backend and frontend Container App revisions use the selected private ACR."
