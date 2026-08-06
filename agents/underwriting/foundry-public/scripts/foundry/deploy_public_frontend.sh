#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt
}

resource_group="$(get_env AZURE_RESOURCE_GROUP)"
registry_name="$(get_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(get_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(get_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(get_env FRONTEND_CONTAINER_APP_NAME)"
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
