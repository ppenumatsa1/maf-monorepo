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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/backend/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend virtual environment is required; run make ensure-backend-env." >&2
  exit 1
fi

cd "$FOUNDRY_DIR"
get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null || true
}

registry_name="$(require_env AZURE_CONTAINER_REGISTRY_NAME "$(get_env AZURE_CONTAINER_REGISTRY_NAME)")"
registry_endpoint="$(require_env AZURE_CONTAINER_REGISTRY_ENDPOINT "$(get_env AZURE_CONTAINER_REGISTRY_ENDPOINT)")"
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

az acr build \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent"

export FOUNDRY_PROJECT_ENDPOINT="$project_endpoint"
export FOUNDRY_HOSTED_AGENT_NAME="$agent_name"
export FOUNDRY_IMAGE="$image"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="$model_name"
export RUNTIME_DATABASE_URL="$runtime_database_url"
export APP_ENV="$(require_env APP_ENV "$(get_env APP_ENV)")"
export STORE_PROVIDER="$(require_env STORE_PROVIDER "$(get_env STORE_PROVIDER)")"
export ENABLE_TELEMETRY="$(require_env ENABLE_TELEMETRY "$(get_env ENABLE_TELEMETRY)")"
export ENABLE_INSTRUMENTATION="$(require_env ENABLE_INSTRUMENTATION "$(get_env ENABLE_INSTRUMENTATION)")"
export OTEL_SERVICE_NAME="$(require_env OTEL_SERVICE_NAME "$(get_env OTEL_SERVICE_NAME)")"
export OTEL_SERVICE_NAMESPACE="$(require_env OTEL_SERVICE_NAMESPACE "$(get_env OTEL_SERVICE_NAMESPACE)")"
export OTEL_RECORD_CONTENT="$(require_env OTEL_RECORD_CONTENT "$(get_env OTEL_RECORD_CONTENT)")"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$(get_env OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)"
export TRACE_EVALUATION_RECORD_CONTENT="$(require_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT "$(get_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT)")"
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
echo "Hosted agent image deployment completed: ${image}"
