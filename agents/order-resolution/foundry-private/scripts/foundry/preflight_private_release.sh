#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
source "${ROOT_DIR}/scripts/foundry/private_profile.sh"
PROFILE_FILE="$(private_profile_resolve "$ROOT_DIR")"

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

require_bin az
require_bin azd
require_bin jq

[[ -f "${FOUNDRY_DIR}/azure.yaml" ]] || {
  echo "Missing private AZD project: ${FOUNDRY_DIR}/azure.yaml"
  exit 1
}
[[ -f "${ROOT_DIR}/backend/Dockerfile" && -f "${ROOT_DIR}/frontend/Dockerfile" ]] || {
  echo "Backend and frontend container definitions are required."
  exit 1
}
[[ -f "${ROOT_DIR}/backend/Dockerfile.hosted" && -f "${ROOT_DIR}/backend/foundry/main.py" ]] || {
  echo "Hosted-agent image source is incomplete."
  exit 1
}

cd "${FOUNDRY_DIR}"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt

get_env_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null || true
}

require_env_value() {
  local key="$1"
  local value
  value="$(get_env_value "$key")"
  if [[ -z "$value" ]]; then
    echo "AZD environment value ${key} is required."
    exit 1
  fi
  printf '%s' "$value"
}

network_mode="$(require_env_value NETWORK_MODE)"
create_postgres_server="$(require_env_value CREATE_POSTGRES_SERVER)"
postgres_server="$(get_env_value POSTGRES_SERVER_NAME)"
runtime_database_url="$(get_env_value RUNTIME_DATABASE_URL)"
enable_container_apps="$(require_env_value ENABLE_CONTAINER_APPS)"
enable_postgres_private_endpoint="$(require_env_value ENABLE_POSTGRES_PRIVATE_ENDPOINT)"
resource_group="$(require_env_value AZURE_RESOURCE_GROUP)"
subscription_id="$(require_env_value AZURE_SUBSCRIPTION_ID)"
location="$(require_env_value AZURE_LOCATION)"
name_prefix="$(require_env_value NAME_PREFIX)"

[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" &&
  "$subscription_id" == "$AZURE_SUBSCRIPTION_ID" &&
  "$location" == "$AZURE_LOCATION" &&
  "$name_prefix" == "$NAME_PREFIX" ]] || {
  echo "Selected AZD target does not match the canonical private deployment profile."
  exit 1
}

if [[ "$network_mode" != "private" ]]; then
  echo "NETWORK_MODE must be private."
  exit 1
fi
if [[ "$enable_container_apps" != "true" || "$enable_postgres_private_endpoint" != "true" ]]; then
  echo "Private release requires ENABLE_CONTAINER_APPS=true and ENABLE_POSTGRES_PRIVATE_ENDPOINT=true."
  exit 1
fi

if [[ "$create_postgres_server" != "true" && ( -z "$postgres_server" || -z "$runtime_database_url" ) ]]; then
  echo "Reuse releases require POSTGRES_SERVER_NAME and RUNTIME_DATABASE_URL."
  exit 1
fi
if [[ -n "$runtime_database_url" && -z "$postgres_server" ]]; then
  echo "RUNTIME_DATABASE_URL cannot be set before the PostgreSQL server output is available."
  exit 1
fi
runtime_host="$(
  python3 - "$runtime_database_url" <<'PY'
import sys
from urllib.parse import urlsplit

print((urlsplit(sys.argv[1]).hostname or "").lower())
PY
)"
expected_host="${postgres_server,,}.postgres.database.azure.com"
if [[ -n "$runtime_database_url" && "$runtime_host" != "$expected_host" ]]; then
  echo "RUNTIME_DATABASE_URL must target the canonical PostgreSQL server ${expected_host}."
  exit 1
fi

if ! az account show --only-show-errors --output none; then
  echo "Azure CLI authentication is required for a local private release."
  exit 1
fi
actual_subscription_id="$(az account show --query id --output tsv)"
[[ "$actual_subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI is not scoped to the private deployment profile subscription."
  exit 1
}
if [[ "$(az group exists --name "$AZURE_RESOURCE_GROUP")" == "true" ]]; then
  resource_group_location="$(az group show --name "$AZURE_RESOURCE_GROUP" --query location --output tsv)"
  [[ "${resource_group_location,,}" == "${AZURE_LOCATION,,}" ]] || {
    echo "The selected resource group location does not match the private deployment profile."
    exit 1
  }
fi
if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ext show azure.ai.agents --output json --no-prompt >/dev/null 2>&1; then
  echo "Required azd extension azure.ai.agents is not installed."
  exit 1
fi

echo "Private release preflight passed for resource group ${resource_group}; secrets were not displayed."
