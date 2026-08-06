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
runtime_database_url="$(get_env RUNTIME_DATABASE_URL)"
if [[ -z "$runtime_database_url" ]]; then
  echo "RUNTIME_DATABASE_URL must be configured before deploying the public backend." >&2
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
