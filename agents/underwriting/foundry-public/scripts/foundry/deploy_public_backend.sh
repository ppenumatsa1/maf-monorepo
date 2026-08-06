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
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
database_url="$(get_env DATABASE_URL)"
if [[ -n "$database_url" && "$database_url" != "$runtime_database_url" ]]; then
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match before backend deployment." >&2
  exit 1
fi

frontend_fqdn="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.configuration.ingress.fqdn' \
    --output tsv
)"
current_image="$(
  az containerapp show \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.template.containers[0].image' \
    --output tsv
)"
[[ -n "$current_image" ]] || {
  echo "Unable to determine the current backend container image for $backend_name." >&2
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
  --file "$ROOT_DIR/backend/Dockerfile" \
  "$ROOT_DIR"

az containerapp secret set \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --secrets "runtime-db-url=$runtime_database_url" \
  --output none

az containerapp update \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --image "$image" \
  --set-env-vars \
    "DATABASE_URL=secretref:runtime-db-url" \
    "RUNTIME_DATABASE_URL=secretref:runtime-db-url" \
    "DB_AUTH_MODE=password" \
    "DB_SSLMODE=require" \
    "UNDERWRITING_EXECUTION_MODE=hosted" \
    "FRONTEND_ORIGIN=https://${frontend_fqdn}" \
  --output none

echo "PUBLIC_BACKEND_IMAGE=$image"
