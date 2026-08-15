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
  local value
  if ! value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    return 0
  fi
  printf '%s' "$value"
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

require_bin azd
require_bin sha256sum
require_bin curl
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
required_env AZURE_LOCATION >/dev/null
operator_ip="$(get_env POSTGRES_OPERATOR_IP)"
if [[ -z "$operator_ip" ]]; then
  operator_ip="$(curl --fail --silent --show-error --max-time 10 https://api.ipify.org)"
  set_env POSTGRES_OPERATOR_IP "$operator_ip"
fi
[[ "$operator_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || {
  echo "POSTGRES_OPERATOR_IP must be a public IPv4 address." >&2
  exit 1
}
name_prefix="$(required_env NAME_PREFIX)"
normalized_prefix="$(printf '%s' "$name_prefix" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
if [[ ${#normalized_prefix} -lt 3 || ${#normalized_prefix} -gt 20 ]]; then
  echo "NAME_PREFIX must normalize to 3-20 lowercase alphanumeric characters." >&2
  exit 1
fi
resource_name_suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
# The shared base must leave room for the shortest globally constrained suffix:
# a Storage account allows 24 characters and needs the four-character `eval`
# suffix. The hash still makes names distinct across target environments.
resource_name_base="${normalized_prefix:0:12}${resource_name_suffix}"

set_env INFRASTRUCTURE_MODE bootstrap
set_env NAME_PREFIX "$normalized_prefix"
set_default RESOURCE_NAME_SUFFIX "$resource_name_suffix"
set_default FOUNDRY_ACCOUNT_NAME "${resource_name_base}ai"
set_default FOUNDRY_PROJECT_NAME underwriting
set_default FOUNDRY_RUNTIME_CONNECTION_NAME underwritingruntimesecrets
set_default FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$(required_env FOUNDRY_ACCOUNT_NAME)"
set_default FOUNDRY_MODEL_DEPLOYMENT_NAME underwriting-gpt-4-1-mini
set_default FOUNDRY_MODEL_FORMAT OpenAI
set_default FOUNDRY_MODEL_NAME gpt-4.1-mini
set_default FOUNDRY_MODEL_VERSION 2025-04-14
set_default FOUNDRY_MODEL_SKU_NAME GlobalStandard
set_default FOUNDRY_MODEL_CAPACITY 2500
set_default FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_default POSTGRES_DATABASE underwriting
set_default POSTGRES_ADMIN_USERNAME pgadmin
set_default POSTGRES_RUNTIME_USERNAME underwriting_runtime
set_default DB_SCHEMA_MANAGED_EXTERNALLY true
set_default POSTGRES_SERVER_NAME "${resource_name_base}pg"
set_default POSTGRES_SERVER_LOCATION "$(required_env AZURE_LOCATION)"
set_default CONTAINER_REGISTRY_NAME "${resource_name_base}acr"
set_default LOG_ANALYTICS_WORKSPACE_NAME "${resource_name_base}-log"
set_default APPLICATION_INSIGHTS_NAME "${resource_name_base}-ai"
set_default CONTAINER_APPS_ENVIRONMENT_NAME "${resource_name_base}-cae"
set_default BACKEND_CONTAINER_APP_NAME "${resource_name_base}-backend"
set_default FRONTEND_CONTAINER_APP_NAME "${resource_name_base}-frontend"
set_default PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "${resource_name_base}-backend-mi"
set_default PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "${resource_name_base}-frontend-mi"
set_default BACKEND_IMAGE_REPOSITORY underwriting-public-backend
set_default FRONTEND_IMAGE_REPOSITORY underwriting-public-frontend
set_default EVALUATION_STORAGE_ACCOUNT_NAME "${resource_name_base}eval"
set_default BOOTSTRAP_RUNTIME_DATABASE_URL bootstrap-pending
set_default HOSTED_AGENT_NAME underwriting-hosted

echo "Prepared the selected AZD environment for bootstrap mode."
echo "Set POSTGRES_ADMIN_PASSWORD and POSTGRES_HOSTED_PASSWORD securely before provisioning credentials."
