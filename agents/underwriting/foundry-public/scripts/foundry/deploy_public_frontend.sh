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
require_bin docker
require_bin git

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
image_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"
az account set --subscription "$subscription_id" >/dev/null
backend_external="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.external' \
    --output tsv
)"
backend_external="${backend_external,,}"
if [[ "$backend_external" != "false" && "${ALLOW_PUBLIC_BACKEND_FOR_MIGRATION:-0}" != "1" ]]; then
  echo "Backend ingress must already be internal. Use the one-time foundry-backend-internalize command for migration." >&2
  exit 1
fi
backend_fqdn="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.fqdn' \
    --output tsv
)"
image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="${registry_endpoint}/${image_repository}:${image_tag}"

az acr login \
  --subscription "$subscription_id" \
  --name "$registry_name" \
  --output none
docker build \
  --file "$ROOT_DIR/frontend/Dockerfile" \
  --tag "$image" \
  "$ROOT_DIR/frontend"
docker push "$image"

az containerapp update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --image "$image" \
  --set-env-vars "NGINX_API_UPSTREAM=https://${backend_fqdn}" \
  --output none

az containerapp ingress update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --type external \
  --target-port 80 \
  --output none

echo "PUBLIC_FRONTEND_IMAGE=$image"
