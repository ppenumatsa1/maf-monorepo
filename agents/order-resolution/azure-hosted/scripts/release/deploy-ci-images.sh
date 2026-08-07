#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

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
  AZURE_CONTAINER_REGISTRY_ENDPOINT \
  BACKEND_IMAGE \
  FRONTEND_IMAGE \
  RELEASE_RUN_ID
do
  require_value "$name"
done

[[ "$AZURE_SUBSCRIPTION_ID" =~ ^[0-9a-fA-F-]{36}$ ]] || {
  echo "AZURE_SUBSCRIPTION_ID is not a subscription ID." >&2
  exit 1
}
[[ "$AZURE_RESOURCE_GROUP" == "rg-maf-ora-azure" ]] || {
  echo "The CI app-release script is restricted to rg-maf-ora-azure." >&2
  exit 1
}
[[ "$RELEASE_RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "RELEASE_RUN_ID may contain only letters, digits, dots, underscores, and hyphens." >&2
  exit 1
}

resolved_subscription="$(az account show --subscription "$AZURE_SUBSCRIPTION_ID" --query id --output tsv)"
[[ "$resolved_subscription" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI cannot resolve the selected release subscription." >&2
  exit 1
}

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

az acr login --name "$registry_name" --subscription "$AZURE_SUBSCRIPTION_ID"
docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

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
backend_digest="$(digest_for_image "$BACKEND_IMAGE")"
frontend_digest="$(digest_for_image "$FRONTEND_IMAGE")"
revision_suffix="ci-${RELEASE_RUN_ID//[^a-zA-Z0-9-]/-}"
revision_suffix="${revision_suffix:0:64}"

az containerapp update \
  --name "$backend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --image "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$backend_repository@$backend_digest" \
  --revision-suffix "$revision_suffix" \
  --only-show-errors
az containerapp update \
  --name "$frontend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --image "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$frontend_repository@$frontend_digest" \
  --revision-suffix "$revision_suffix" \
  --only-show-errors

artifacts_dir="$ROOT_DIR/.artifacts/release/$RELEASE_RUN_ID"
mkdir -p "$artifacts_dir"
python3 - "$artifacts_dir/images.json" \
  "$backend_app" \
  "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$backend_repository@$backend_digest" \
  "$frontend_app" \
  "$AZURE_CONTAINER_REGISTRY_ENDPOINT/$frontend_repository@$frontend_digest" <<'PY'
import json
import sys
from pathlib import Path

path, backend_app, backend_image, frontend_app, frontend_image = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "backend": {"container_app": backend_app, "image": backend_image},
            "frontend": {"container_app": frontend_app, "image": frontend_image},
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY

echo "Deployed the tested immutable backend and frontend image digests."
