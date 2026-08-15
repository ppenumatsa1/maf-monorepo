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
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required AZD environment value: $key" >&2
    exit 1
  fi
  printf '%s\n' "$value"
}

require_bin az
require_bin azd
require_bin docker

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/backend/.venv/bin/python"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/../deployment/profiles/foundry-private.env}"

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend virtual environment is required; run make ensure-foundry-deploy-env." >&2
  exit 1
fi

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt
get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null || true
}

resource_group="$(require_env AZURE_RESOURCE_GROUP "$(get_env AZURE_RESOURCE_GROUP)")"
[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" ]] || {
  echo "Selected AZD resource group does not match the private deployment profile." >&2
  exit 1
}
registry_name="$(az acr list --resource-group "$resource_group" --query '[0].name' --output tsv)"
registry_endpoint="$(az acr list --resource-group "$resource_group" --query '[0].loginServer' --output tsv)"
[[ -n "$registry_name" && -n "$registry_endpoint" ]] || {
  echo "Expected exactly one private ACR in the selected resource group." >&2
  exit 1
}
[[ "$(az acr list --resource-group "$resource_group" --query 'length([])' --output tsv)" == "1" ]] || {
  echo "Expected exactly one private ACR in the selected resource group." >&2
  exit 1
}

project_endpoint="$(require_env FOUNDRY_PROJECTS_ENDPOINT "$(get_env FOUNDRY_PROJECTS_ENDPOINT)")"
agent_name="$(require_env HOSTED_AGENT_NAME "$(get_env HOSTED_AGENT_NAME)")"
model_name="$(require_env FOUNDRY_MODEL_DEPLOYMENT_NAME "$(get_env FOUNDRY_MODEL_DEPLOYMENT_NAME)")"
runtime_database_url="$(require_env RUNTIME_DATABASE_URL "$(get_env RUNTIME_DATABASE_URL)")"
postgres_server_name="$(require_env POSTGRES_SERVER_NAME "$(get_env POSTGRES_SERVER_NAME)")"

if [[ "$runtime_database_url" != *"${postgres_server_name}.postgres.database.azure.com"* ]]; then
  echo "RUNTIME_DATABASE_URL must target ${postgres_server_name}.postgres.database.azure.com." >&2
  exit 1
fi

image_repository="${HOSTED_AGENT_IMAGE_REPOSITORY:-order-resolution-hosted}"
image_tag="${HOSTED_AGENT_IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)}"
image="${registry_endpoint}/${image_repository}:${image_tag}"

docker build \
  --platform linux/amd64 \
  --tag "$image" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent"

push_output=""
for retry_delay in 0 15 30 60; do
  if [[ "$retry_delay" -gt 0 ]]; then
    echo "Waiting ${retry_delay}s for private ACR push-role propagation."
    sleep "$retry_delay"
  fi
  if push_output="$(az acr login --name "$registry_name" 2>&1)" &&
    push_output+=$'\n'"$(docker push "$image" 2>&1)"; then
    printf '%s\n' "$push_output"
    break
  fi
  printf '%s\n' "$push_output" >&2
  if [[ "$push_output" != *"unauthorized"* && "$push_output" != *"denied"* ]]; then
    exit 1
  fi
done
[[ -n "$push_output" && "$push_output" != *"unauthorized"* && "$push_output" != *"denied"* ]] || {
  echo "Private ACR push role did not propagate before the deployment retry limit." >&2
  exit 1
}

image_digest="$(
  az acr repository show \
    --name "$registry_name" \
    --image "${image_repository}:${image_tag}" \
    --query digest \
    --output tsv
)"
[[ -n "$image_digest" ]] || {
  echo "Hosted-agent image was not found in the selected private ACR after push." >&2
  exit 1
}

export FOUNDRY_PROJECT_ENDPOINT="$project_endpoint"
export FOUNDRY_HOSTED_AGENT_NAME="$agent_name"
export FOUNDRY_IMAGE="$image"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="$model_name"
export APP_ENV="$(require_env APP_ENV "$(get_env APP_ENV)")"
export STORE_PROVIDER="$(require_env STORE_PROVIDER "$(get_env STORE_PROVIDER)")"
export MEMORY_PROVIDER="$(require_env MEMORY_PROVIDER "$(get_env MEMORY_PROVIDER)")"
export RAG_PROVIDER="$(require_env RAG_PROVIDER "$(get_env RAG_PROVIDER)")"
export DB_SCHEMA_MANAGED_EXTERNALLY="$(require_env DB_SCHEMA_MANAGED_EXTERNALLY "$(get_env DB_SCHEMA_MANAGED_EXTERNALLY)")"
export ENABLE_TELEMETRY="$(require_env ENABLE_TELEMETRY "$(get_env ENABLE_TELEMETRY)")"
export ENABLE_INSTRUMENTATION="$(require_env ENABLE_INSTRUMENTATION "$(get_env ENABLE_INSTRUMENTATION)")"
export OTEL_SERVICE_NAME="$(require_env OTEL_SERVICE_NAME "$(get_env OTEL_SERVICE_NAME)")"
export OTEL_SERVICE_NAMESPACE="$(require_env OTEL_SERVICE_NAMESPACE "$(get_env OTEL_SERVICE_NAMESPACE)")"
export OTEL_RECORD_CONTENT="$(require_env OTEL_RECORD_CONTENT "$(get_env OTEL_RECORD_CONTENT)")"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$(get_env OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)"
export FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT="$(require_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT "$(get_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT)")"
deployment_output="$("$PYTHON" "$ROOT_DIR/scripts/foundry/deploy_hosted_container.py")"
printf '%s\n' "$deployment_output"
agent_version="$(printf '%s\n' "$deployment_output" | sed -n 's/^HOSTED_AGENT_VERSION=//p' | tail -n 1)"
if [[ -z "$agent_version" ]]; then
  echo "Hosted agent deployment did not report an active version." >&2
  exit 1
fi

agent_endpoint="${project_endpoint}/agents/${agent_name}/endpoint/protocols/openai/responses?api-version=v1"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_NAME "$agent_name" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_VERSION "$agent_version" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_RESPONSES_ENDPOINT "$agent_endpoint" >/dev/null
echo "Verified hosted-agent image in private ACR: ${image}"
echo "Hosted agent image deployment completed: ${image}"
