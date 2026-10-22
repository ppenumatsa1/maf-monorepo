#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

get_env() {
  local value
  if value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    printf '%s' "$value"
  fi
}

set_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set "$1" "$2" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
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

set_default() {
  local name="$1"
  local value="$2"
  if [[ -z "$(get_env "$name")" ]]; then
    set_env "$name" "$value"
  fi
}

for command in azd curl; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
required_env AZURE_RESOURCE_GROUP >/dev/null
required_env AZURE_LOCATION >/dev/null

set_env INFRASTRUCTURE_MODE bootstrap
operator_ip="$(get_env POSTGRES_OPERATOR_IP)"
if [[ -z "$operator_ip" ]]; then
  operator_ip="$(curl --fail --silent --show-error --max-time 10 -4 https://api.ipify.org)"
  set_env POSTGRES_OPERATOR_IP "$operator_ip"
fi
if [[ ! "$operator_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "POSTGRES_OPERATOR_IP must be a public IPv4 address." >&2
  exit 1
fi
for key in \
  FOUNDRY_ACCOUNT_NAME FOUNDRY_PROJECT_NAME FOUNDRY_CUSTOM_SUBDOMAIN_NAME \
  HOSTED_AGENT_NAME FOUNDRY_RUNTIME_CONNECTION_NAME \
  FOUNDRY_MODEL_DEPLOYMENT_NAME FOUNDRY_MODEL_FORMAT FOUNDRY_MODEL_NAME \
  FOUNDRY_MODEL_VERSION FOUNDRY_MODEL_SKU_NAME FOUNDRY_MODEL_CAPACITY \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME FOUNDRY_EMBEDDINGS_MODEL_FORMAT \
  FOUNDRY_EMBEDDINGS_MODEL_NAME FOUNDRY_EMBEDDINGS_MODEL_VERSION \
  FOUNDRY_EMBEDDINGS_MODEL_SKU_NAME FOUNDRY_EMBEDDINGS_MODEL_CAPACITY \
  FOUNDRY_EVAL_MODEL FOUNDRY_EVALUATION_MODEL_FORMAT \
  FOUNDRY_EVALUATION_MODEL_NAME FOUNDRY_EVALUATION_MODEL_VERSION \
  FOUNDRY_EVALUATION_MODEL_SKU_NAME FOUNDRY_EVALUATION_MODEL_CAPACITY \
  FOUNDRY_RAI_POLICY_NAME POSTGRES_DATABASE POSTGRES_ADMIN_USERNAME \
  POSTGRES_RUNTIME_USERNAME POSTGRES_SERVER_NAME POSTGRES_SERVER_LOCATION \
  CONTAINER_REGISTRY_NAME CONTAINER_REGISTRY_SKU_NAME \
  LOG_ANALYTICS_WORKSPACE_NAME APPLICATION_INSIGHTS_NAME \
  CONTAINER_APPS_ENVIRONMENT_NAME BACKEND_CONTAINER_APP_NAME \
  FRONTEND_CONTAINER_APP_NAME PUBLIC_BACKEND_MANAGED_IDENTITY_NAME \
  PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME BACKEND_IMAGE_REPOSITORY \
  FRONTEND_IMAGE_REPOSITORY HOSTED_AGENT_IMAGE_REPOSITORY \
  EVALUATION_STORAGE_ACCOUNT_NAME BOT_SERVICE_NAME BOT_SERVICE_SKU_NAME; do
  required_env "$key" >/dev/null
done
required_env BOOTSTRAP_RUNTIME_DATABASE_URL >/dev/null
required_env POSTGRES_ADMIN_PASSWORD >/dev/null

echo "Prepared the selected AZD environment for portable bootstrap mode."
echo "Set POSTGRES_ADMIN_PASSWORD and POSTGRES_HOSTED_PASSWORD securely before credential provisioning."
