#!/usr/bin/env bash
set -euo pipefail

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

for binary in az azd python3; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary"
    exit 1
  }
done

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt

get_env_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null || true
}

require_env_value() {
  local key="$1"
  local value
  value="$(get_env_value "$key")"
  [[ -n "$value" ]] || {
    echo "AZD environment value $key is required."
    exit 1
  }
  printf '%s' "$value"
}

require_exact_value() {
  local key="$1"
  local expected="$2"
  local actual
  actual="$(require_env_value "$key")"
  [[ "$actual" == "$expected" ]] || {
    echo "AZD environment value $key does not match the private deployment target."
    exit 1
  }
}

require_exact_value AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
require_exact_value AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
require_exact_value AZURE_LOCATION "$AZURE_LOCATION"
require_exact_value NAME_PREFIX "$NAME_PREFIX"
require_exact_value NETWORK_MODE private
require_exact_value ENABLE_CONTAINER_APPS true
require_exact_value ENABLE_POSTGRES_PRIVATE_ENDPOINT true
require_exact_value DB_SCHEMA_MANAGED_EXTERNALLY true

actual_subscription_id="$(az account show --query id --output tsv)"
[[ "$actual_subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI is not scoped to the configured private deployment subscription."
  exit 1
}

postgres_server_name="$(require_env_value POSTGRES_SERVER_NAME)"
postgres_fqdn="$(
  az postgres flexible-server show \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$postgres_server_name" \
    --query fullyQualifiedDomainName \
    --output tsv
)"
expected_postgres_fqdn="${postgres_server_name,,}.postgres.database.azure.com"
[[ "$postgres_fqdn" == "$expected_postgres_fqdn" ]] || {
  echo "The selected PostgreSQL server does not resolve to its canonical FQDN."
  exit 1
}

postgres_database_name="$(require_env_value POSTGRES_DATABASE_NAME)"
database_count="$(
  az postgres flexible-server db list \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --server-name "$postgres_server_name" \
    --query "[?name=='${postgres_database_name}'] | length(@)" \
    --output tsv
)"
[[ "$database_count" == "1" ]] || {
  echo "The selected PostgreSQL database does not exist exactly once."
  exit 1
}

runtime_database_url="$(require_env_value RUNTIME_DATABASE_URL)"
runtime_database_host="$(
  RUNTIME_DATABASE_URL="$runtime_database_url" python3 - <<'PY'
import os
from urllib.parse import urlsplit

print((urlsplit(os.environ["RUNTIME_DATABASE_URL"]).hostname or "").lower())
PY
)"
[[ "$runtime_database_host" == "$expected_postgres_fqdn" ]] || {
  echo "RUNTIME_DATABASE_URL does not target the canonical PostgreSQL server."
  exit 1
}

project_id="$(require_env_value FOUNDRY_PROJECT_ID)"
foundry_project_name="$(require_env_value FOUNDRY_PROJECT_NAME)"
project_id_lower="${project_id,,}"
expected_resource_group_segment="/resourcegroups/${AZURE_RESOURCE_GROUP,,}/"
expected_project_segment="/projects/${foundry_project_name,,}"
[[ "$project_id_lower" == *"$expected_resource_group_segment"* &&
   "$project_id_lower" == *"$expected_project_segment" ]] || {
  echo "FOUNDRY_PROJECT_ID is not scoped to the selected private project."
  exit 1
}

if [[ "$(require_env_value CREATE_POSTGRES_SERVER)" == "true" ]]; then
  [[ -n "$(require_env_value POSTGRES_ADMIN_PASSWORD)" ]] || {
    echo "The private environment requires its existing PostgreSQL administrator secret."
    exit 1
  }
fi

echo "Validated selected private deployment environment without displaying secret values."
