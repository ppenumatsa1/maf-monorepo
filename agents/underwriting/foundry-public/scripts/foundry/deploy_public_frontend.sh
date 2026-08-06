#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

require_bin az
require_bin azd
require_bin git

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
backend_fqdn="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.fqdn' \
    --output tsv
)"
current_image="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.template.containers[0].image' \
    --output tsv
)"
[[ -n "$current_image" ]] || {
  echo "Unable to determine the current frontend container image for $frontend_name." >&2
  exit 1
}

image_repository="${current_image#*/}"
image_repository="${image_repository%@*}"
image_repository="${image_repository%:*}"
image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="${registry_endpoint}/${image_repository}:${image_tag}"

az acr build \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --build-arg "VITE_API_BASE_URL=https://${backend_fqdn}" \
  --file "$ROOT_DIR/frontend/Dockerfile" \
  "$ROOT_DIR/frontend"

az containerapp update \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --image "$image" \
  --output none

echo "PUBLIC_FRONTEND_IMAGE=$image"
