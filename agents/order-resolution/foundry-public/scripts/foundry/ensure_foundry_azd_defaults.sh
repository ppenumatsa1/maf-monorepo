#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}/infra/foundry-hosted"

get_env_value() {
  local key="$1"
  local value
  if ! value="$(azd env get-value "$key" 2>/dev/null)"; then
    return 0
  fi
  printf '%s\n' "$value"
}

set_if_missing() {
  local key="$1"
  local value="$2"
  local existing
  existing="$(get_env_value "$key")"
  if [[ -z "$existing" ]]; then
    azd env set "$key" "$value" >/dev/null
    echo "defaulted $key=$value"
  fi
}

set_provision_image() {
  local key="$1"
  local container_app_name="$2"
  local bootstrap_image="$3"
  local active_image
  local resource_group

  resource_group="$(get_env_value AZURE_RESOURCE_GROUP)"
  active_image="$(az containerapp show \
    --name "$container_app_name" \
    --resource-group "$resource_group" \
    --query 'properties.template.containers[0].image' \
    --output tsv 2>/dev/null || true)"
  if [[ -n "$active_image" ]]; then
    azd env set "$key" "$active_image" >/dev/null
    echo "preserved $key from active Container App $container_app_name"
  else
    azd env set "$key" "$bootstrap_image" >/dev/null
    echo "set $key to the provision bootstrap image because $container_app_name is absent"
  fi
}

set_if_missing FOUNDRY_ACCOUNT_NAME "${FOUNDRY_ACCOUNT_NAME:-maffndaibfscpfhjr7sp4}"
set_if_missing CONTAINER_REGISTRY_NAME "${CONTAINER_REGISTRY_NAME:-maffndacrbfscpfhjr7sp4}"
set_if_missing FOUNDRY_PROJECT_NAME "${FOUNDRY_PROJECT_NAME:-order-resolution-public-managed-dev2}"
set_if_missing HOSTED_AGENT_NAME "${HOSTED_AGENT_NAME:-order-resolution-hosted}"
set_if_missing FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT "${FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT:-true}"
set_if_missing RUNTIME_DATABASE_URL "${RUNTIME_DATABASE_URL:-}"
azd env set AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING false >/dev/null
set_if_missing POSTGRES_SERVER_NAME "${POSTGRES_SERVER_NAME:-maffndpgbfscpfhjr7sp4cu}"
set_if_missing BACKEND_CONTAINER_APP_NAME "${BACKEND_CONTAINER_APP_NAME:-ora-public-dev2-backend}"
set_if_missing FRONTEND_CONTAINER_APP_NAME "${FRONTEND_CONTAINER_APP_NAME:-ora-public-dev2-frontend}"

# Provision must not depend on a prior azd deploy's ACR tag. New Container Apps
# use bootstrap images; existing apps retain their active images until azd deploy
# publishes a replacement.
set_provision_image SERVICE_BACKEND_IMAGE_NAME "$(get_env_value BACKEND_CONTAINER_APP_NAME)" "mcr.microsoft.com/k8se/quickstart:latest"
set_provision_image SERVICE_FRONTEND_IMAGE_NAME "$(get_env_value FRONTEND_CONTAINER_APP_NAME)" "mcr.microsoft.com/k8se/quickstart:latest"

foundry_project_name="$(get_env_value FOUNDRY_PROJECT_NAME)"
agent_endpoint="$(get_env_value AGENT_ORDER_RESOLUTION_HOSTED_ENDPOINT)"
if [[ -n "$agent_endpoint" && "$agent_endpoint" != *"/projects/${foundry_project_name}/"* ]]; then
  azd env set AGENT_ORDER_RESOLUTION_HOSTED_ENDPOINT "" >/dev/null
  azd env set AGENT_ORDER_RESOLUTION_HOSTED_RESPONSES_ENDPOINT "" >/dev/null
  azd env set AGENT_ORDER_RESOLUTION_HOSTED_VERSION "" >/dev/null
  echo "cleared stale hosted-agent deployment metadata"
fi

set_if_missing foundryProjectName "$(get_env_value FOUNDRY_PROJECT_NAME)"
set_if_missing hostedAgentName "$(get_env_value HOSTED_AGENT_NAME)"

# Preserve the application telemetry alias used by the backend and Container Apps.
appinsights_connection_string="$(get_env_value APPLICATIONINSIGHTS_CONNECTION_STRING)"
if [[ -n "$appinsights_connection_string" ]]; then
  set_if_missing APPINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
fi
set_if_missing OTEL_SERVICE_NAMESPACE "${OTEL_SERVICE_NAMESPACE:-maf-order-resolution}"
# The hosted deployment forwards this optional OTLP endpoint when configured.
set_if_missing OTEL_EXPORTER_OTLP_TRACES_ENDPOINT "${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-}"
