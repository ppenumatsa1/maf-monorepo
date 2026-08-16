#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

require_value() {
  local name="$1"
  local value="${!name:-}"
  [[ -n "$value" ]] || {
    echo "$name is required." >&2
    exit 1
  }
}

for name in \
  AZURE_SUBSCRIPTION_ID \
  AZURE_RESOURCE_GROUP \
  AZURE_LOCATION \
  AZURE_CONTAINER_REGISTRY_ENDPOINT \
  BACKEND_IMAGE \
  FRONTEND_IMAGE \
  RELEASE_RUN_ID
do
  require_value "$name"
done

require_selected_target \
  "$environment" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION"
[[ "$RELEASE_RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "RELEASE_RUN_ID may contain only letters, digits, dots, underscores, and hyphens." >&2
  exit 1
}

require_azure_cli_target "$AZURE_SUBSCRIPTION_ID"
write_release_context \
  "$environment" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION"

registry_name="${AZURE_CONTAINER_REGISTRY_ENDPOINT%%.*}"
[[ "$AZURE_CONTAINER_REGISTRY_ENDPOINT" == "$registry_name.azurecr.io" ]] || {
  echo "AZURE_CONTAINER_REGISTRY_ENDPOINT must be an Azure Container Registry login server." >&2
  exit 1
}

resolve_app_name() {
  local service_name="$1"
  local matching_apps
  readarray -t matching_apps < <(
    az containerapp list \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --query "[?tags.\"azd-service-name\"=='$service_name'].name" \
      --output tsv
  )
  [[ "${#matching_apps[@]}" == 1 ]] || {
    echo "Expected exactly one Container App tagged azd-service-name=$service_name." >&2
    exit 1
  }
  printf '%s\n' "${matching_apps[0]}"
}

backend_app="$(resolve_app_name backend)"
frontend_app="$(resolve_app_name frontend)"

for image in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
  [[ "$image" == "$AZURE_CONTAINER_REGISTRY_ENDPOINT/"* ]] || {
    echo "Release images must target the selected Azure Container Registry." >&2
    exit 1
  }
  docker image inspect "$image" >/dev/null
done

az acr login \
  --name "$registry_name" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  >"$RELEASE_LOGS_DIR/acr-login.log" 2>&1

digest_for_image() {
  local image="$1"
  local repository_and_tag="${image#"$AZURE_CONTAINER_REGISTRY_ENDPOINT/"}"
  local digest
  digest="$(az acr manifest show-metadata \
    --registry "$registry_name" \
    --name "$repository_and_tag" \
    --query digest \
    --output tsv)"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "Unable to resolve an immutable digest for $image." >&2
    exit 1
  }
  printf '%s\n' "$digest"
}

backend_repository="${BACKEND_IMAGE#"$AZURE_CONTAINER_REGISTRY_ENDPOINT/"}"
backend_repository="${backend_repository%:*}"
frontend_repository="${FRONTEND_IMAGE#"$AZURE_CONTAINER_REGISTRY_ENDPOINT/"}"
frontend_repository="${frontend_repository%:*}"
revision_suffix="ci-${RELEASE_RUN_ID//[^a-zA-Z0-9-]/-}"
revision_suffix="${revision_suffix,,}"
revision_suffix="${revision_suffix:0:64}"

deploy_image() {
  local service_name="$1"
  local app_name="$2"
  local source_image="$3"
  local repository="$4"
  local deploy_log="$RELEASE_LOGS_DIR/$service_name.image-deploy.log"
  local digest=""

  {
    docker push "$source_image"
    digest="$(digest_for_image "$source_image")"
    az containerapp update \
      --name "$app_name" \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --image "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$repository@$digest" \
      --revision-suffix "$revision_suffix" \
      --only-show-errors
  } >"$deploy_log" 2>&1
  printf '%s\n' "$digest"
}

backend_digest="$(deploy_image backend "$backend_app" "$BACKEND_IMAGE" "$backend_repository")"
frontend_digest="$(deploy_image frontend "$frontend_app" "$FRONTEND_IMAGE" "$frontend_repository")"

az containerapp ingress enable \
  --name "$backend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --type internal \
  --target-port 8000 \
  --transport auto \
  --allow-insecure false \
  --only-show-errors \
  --output none
backend_fqdn="$(
  az containerapp show \
    --name "$backend_app" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --query properties.configuration.ingress.fqdn \
    --output tsv
)"
[[ "$backend_fqdn" == *.internal.* ]] || {
  echo "Backend internal ingress did not produce an internal FQDN." >&2
  exit 1
}
az containerapp update \
  --name "$frontend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --set-env-vars "NGINX_API_UPSTREAM=https://$backend_fqdn" \
  --only-show-errors \
  --output none
az containerapp ingress enable \
  --name "$frontend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --type external \
  --target-port 5173 \
  --transport auto \
  --allow-insecure false \
  --only-show-errors \
  --output none

images_file="$(release_artifact_path images.json)"
python3 - "$images_file" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "$environment" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION" \
  "$backend_app" \
  "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$backend_repository@$backend_digest" \
  "$frontend_app" \
  "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$frontend_repository@$frontend_digest" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    path,
    release_id,
    release_started_at,
    environment,
    subscription_id,
    resource_group,
    location,
    backend_app,
    backend_image,
    frontend_app,
    frontend_image,
) = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "schema_version": 1,
            "contract": "azure-hosted-release/v1",
            "lane": "azure-hosted",
            "artifact_type": "images",
            "status": "passed",
            "release_id": release_id,
            "release_started_at": release_started_at,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "target": {
                "azd_env_name": environment,
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "location": location,
            },
            "backend": {
                "container_app": backend_app,
                "resource_id": (
                    f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
                    f"/providers/Microsoft.App/containerApps/{backend_app}"
                ),
                "image": backend_image,
                "image_digest": backend_image.split("@", 1)[1],
            },
            "frontend": {
                "container_app": frontend_app,
                "resource_id": (
                    f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
                    f"/providers/Microsoft.App/containerApps/{frontend_app}"
                ),
                "image": frontend_image,
                "image_digest": frontend_image.split("@", 1)[1],
            },
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY

echo "Deployed the tested immutable backend and frontend image digests."
