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
require_bin python3

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
  local value
  if value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null)"; then
    printf '%s' "$value"
  fi
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
runner_vm_size="$(require_env_value RUNNER_VM_SIZE)"
foundry_location="$(require_env_value FOUNDRY_LOCATION)"
ai_search_location="$(require_env_value AI_SEARCH_LOCATION)"
cosmos_location="$(require_env_value COSMOS_LOCATION)"
postgres_location="$(require_env_value POSTGRES_LOCATION)"
create_runner_vm="$(require_env_value CREATE_RUNNER_VM)"
ai_search_sku_name="$(require_env_value AI_SEARCH_SKU_NAME)"
postgres_sku_name="$(require_env_value POSTGRES_SKU_NAME)"
postgres_sku_tier="$(require_env_value POSTGRES_SKU_TIER)"
postgres_version="$(require_env_value POSTGRES_VERSION)"
foundry_chat_model_format="$(require_env_value FOUNDRY_CHAT_MODEL_FORMAT)"
foundry_model_deployment_name="$(require_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
foundry_chat_model_name="$(require_env_value FOUNDRY_CHAT_MODEL_NAME)"
foundry_chat_model_version="$(require_env_value FOUNDRY_CHAT_MODEL_VERSION)"
foundry_chat_deployment_sku_name="$(require_env_value FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME)"
foundry_chat_deployment_capacity="$(require_env_value FOUNDRY_CHAT_DEPLOYMENT_CAPACITY)"
foundry_embeddings_deployment_name="$(require_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"
foundry_embeddings_model_format="$(require_env_value FOUNDRY_EMBEDDINGS_MODEL_FORMAT)"
foundry_embeddings_model_name="$(require_env_value FOUNDRY_EMBEDDINGS_MODEL_NAME)"
foundry_embeddings_model_version="$(require_env_value FOUNDRY_EMBEDDINGS_MODEL_VERSION)"
foundry_embeddings_deployment_sku_name="$(require_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME)"
foundry_embeddings_deployment_capacity="$(require_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY)"

[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" &&
  "$subscription_id" == "$AZURE_SUBSCRIPTION_ID" &&
  "$location" == "$AZURE_LOCATION" &&
  "$name_prefix" == "$NAME_PREFIX" ]] || {
  echo "Selected AZD target does not match the selected private deployment profile."
  exit 1
}

profile_matches_azd() {
  local key="$1"
  local azd_value="$2"
  local profile_value="$3"
  [[ "$azd_value" == "$profile_value" ]] || {
    echo "Selected AZD value ${key}=${azd_value} does not match the deployment profile value ${profile_value}." >&2
    exit 1
  }
}

profile_matches_azd RUNNER_VM_SIZE "$runner_vm_size" "$RUNNER_VM_SIZE"
profile_matches_azd FOUNDRY_LOCATION "$foundry_location" "$FOUNDRY_LOCATION"
profile_matches_azd AI_SEARCH_LOCATION "$ai_search_location" "$AI_SEARCH_LOCATION"
profile_matches_azd COSMOS_LOCATION "$cosmos_location" "$COSMOS_LOCATION"
profile_matches_azd POSTGRES_LOCATION "$postgres_location" "$POSTGRES_LOCATION"
profile_matches_azd CREATE_RUNNER_VM "$create_runner_vm" "$CREATE_RUNNER_VM"
profile_matches_azd AI_SEARCH_SKU_NAME "$ai_search_sku_name" "$AI_SEARCH_SKU_NAME"
profile_matches_azd POSTGRES_SKU_NAME "$postgres_sku_name" "$POSTGRES_SKU_NAME"
profile_matches_azd POSTGRES_SKU_TIER "$postgres_sku_tier" "$POSTGRES_SKU_TIER"
profile_matches_azd POSTGRES_VERSION "$postgres_version" "$POSTGRES_VERSION"
profile_matches_azd FOUNDRY_MODEL_DEPLOYMENT_NAME "$foundry_model_deployment_name" "$FOUNDRY_MODEL_DEPLOYMENT_NAME"
profile_matches_azd FOUNDRY_CHAT_MODEL_FORMAT "$foundry_chat_model_format" "$FOUNDRY_CHAT_MODEL_FORMAT"
profile_matches_azd FOUNDRY_CHAT_MODEL_NAME "$foundry_chat_model_name" "$FOUNDRY_CHAT_MODEL_NAME"
profile_matches_azd FOUNDRY_CHAT_MODEL_VERSION "$foundry_chat_model_version" "$FOUNDRY_CHAT_MODEL_VERSION"
profile_matches_azd FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME "$foundry_chat_deployment_sku_name" "$FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME"
profile_matches_azd FOUNDRY_CHAT_DEPLOYMENT_CAPACITY "$foundry_chat_deployment_capacity" "$FOUNDRY_CHAT_DEPLOYMENT_CAPACITY"
profile_matches_azd FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME "$foundry_embeddings_deployment_name" "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME"
profile_matches_azd FOUNDRY_EMBEDDINGS_MODEL_FORMAT "$foundry_embeddings_model_format" "$FOUNDRY_EMBEDDINGS_MODEL_FORMAT"
profile_matches_azd FOUNDRY_EMBEDDINGS_MODEL_NAME "$foundry_embeddings_model_name" "$FOUNDRY_EMBEDDINGS_MODEL_NAME"
profile_matches_azd FOUNDRY_EMBEDDINGS_MODEL_VERSION "$foundry_embeddings_model_version" "$FOUNDRY_EMBEDDINGS_MODEL_VERSION"
profile_matches_azd FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME "$foundry_embeddings_deployment_sku_name" "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME"
profile_matches_azd FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY "$foundry_embeddings_deployment_capacity" "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY"

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
  echo "RUNTIME_DATABASE_URL must target the PostgreSQL server selected by the deployment profile."
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
if ! az extension show --name quota --only-show-errors --output none >/dev/null 2>&1; then
  echo "Azure CLI extension 'quota' is required for read-only Container Apps quota checks. Install it with: az extension add --name quota" >&2
  exit 1
fi

python3 "${ROOT_DIR}/scripts/foundry/capacity_preflight.py" \
  --subscription-id "$AZURE_SUBSCRIPTION_ID" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --target-region "$AZURE_LOCATION" \
  --foundry-region "$FOUNDRY_LOCATION" \
  --search-region "$AI_SEARCH_LOCATION" \
  --cosmos-region "$COSMOS_LOCATION" \
  --postgres-region "$POSTGRES_LOCATION" \
  --runner-vm-size "$RUNNER_VM_SIZE" \
  --create-runner-vm "$CREATE_RUNNER_VM" \
  --enable-container-apps "$ENABLE_CONTAINER_APPS" \
  --search-sku "$AI_SEARCH_SKU_NAME" \
  --postgres-sku "$POSTGRES_SKU_NAME" \
  --postgres-tier "$POSTGRES_SKU_TIER" \
  --postgres-version "$POSTGRES_VERSION" \
  --chat-deployment-name "$FOUNDRY_MODEL_DEPLOYMENT_NAME" \
  --chat-model-format "$FOUNDRY_CHAT_MODEL_FORMAT" \
  --chat-model-name "$FOUNDRY_CHAT_MODEL_NAME" \
  --chat-model-version "$FOUNDRY_CHAT_MODEL_VERSION" \
  --chat-sku-name "$FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME" \
  --chat-capacity "$FOUNDRY_CHAT_DEPLOYMENT_CAPACITY" \
  --embeddings-deployment-name "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME" \
  --embeddings-model-format "$FOUNDRY_EMBEDDINGS_MODEL_FORMAT" \
  --embeddings-model-name "$FOUNDRY_EMBEDDINGS_MODEL_NAME" \
  --embeddings-model-version "$FOUNDRY_EMBEDDINGS_MODEL_VERSION" \
  --embeddings-sku-name "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME" \
  --embeddings-capacity "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY"

echo "Private release preflight passed; profile values and resource identifiers were not displayed."
