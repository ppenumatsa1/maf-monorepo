#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin azd
require_bin az
require_bin python3

: "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD is required}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/../deployment/profiles/foundry-private.env}"
PROFILE_LOADER="${ROOT_DIR}/../deployment/profile.sh"

source "$PROFILE_LOADER"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

cd "$FOUNDRY_DIR"
if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt >/dev/null 2>&1; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env new "$AZURE_ENV_NAME" \
    --location "$AZURE_LOCATION" \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --no-prompt
fi

AZD_PROJECT_DIR="$FOUNDRY_DIR" \
  bash "$ROOT_DIR/../deployment/apply-azd-profile.sh" "$PROFILE_FILE"

resource_value() {
  local resource_type="$1"
  local query="$2"
  az resource list \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --resource-type "$resource_type" \
    --query "$query" \
    --output tsv
}

foundry_account_name="$(resource_value Microsoft.CognitiveServices/accounts "[?kind=='AIServices'].name | [0]")"
acr_name="$(resource_value Microsoft.ContainerRegistry/registries "[0].name")"
container_environment_name="$(resource_value Microsoft.App/managedEnvironments "[0].name")"
backend_app_name="$(resource_value Microsoft.App/containerApps "[?contains(name, 'backend')].name | [0]")"
frontend_app_name="$(resource_value Microsoft.App/containerApps "[?contains(name, 'frontend')].name | [0]")"
postgres_server_name="$(resource_value Microsoft.DBforPostgreSQL/flexibleServers "[0].name")"
postgres_private_endpoint_name="$(resource_value Microsoft.Network/privateEndpoints "[?contains(name, 'postgres')].name | [0]")"

for required_value in \
  "$foundry_account_name" "$acr_name" "$container_environment_name" \
  "$backend_app_name" "$frontend_app_name" "$postgres_server_name" \
  "$postgres_private_endpoint_name"; do
  [[ -n "$required_value" ]] || {
    echo "Unable to discover all provisioned private release resources." >&2
    exit 1
  }
done

foundry_project_id="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${foundry_account_name}/projects/${FOUNDRY_PROJECT_NAME}"
foundry_project_endpoint="https://${foundry_account_name}.services.ai.azure.com/api/projects/${FOUNDRY_PROJECT_NAME}"
acr_endpoint="${acr_name}.azurecr.io"
postgres_server_fqdn="${postgres_server_name}.postgres.database.azure.com"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  POSTGRES_ADMIN_PASSWORD="$POSTGRES_ADMIN_PASSWORD" \
  FOUNDRY_ACCOUNT_NAME="$foundry_account_name" \
  AZURE_AI_PROJECT_ID="$foundry_project_id" \
  AZURE_AI_PROJECT_ENDPOINT="$foundry_project_endpoint" \
  FOUNDRY_PROJECT_ID="$foundry_project_id" \
  FOUNDRY_PROJECT_ENDPOINT="$foundry_project_endpoint" \
  FOUNDRY_PROJECTS_ENDPOINT="$foundry_project_endpoint" \
  AZURE_CONTAINER_REGISTRY_NAME="$acr_name" \
  AZURE_CONTAINER_REGISTRY_ENDPOINT="$acr_endpoint" \
  containerRegistryLoginServer="$acr_endpoint" \
  AZURE_CONTAINER_ENVIRONMENT_NAME="$container_environment_name" \
  CONTAINER_APPS_ENVIRONMENT_NAME="$container_environment_name" \
  SERVICE_BACKEND_NAME="$backend_app_name" \
  BACKEND_CONTAINER_APP_NAME="$backend_app_name" \
  SERVICE_FRONTEND_NAME="$frontend_app_name" \
  FRONTEND_CONTAINER_APP_NAME="$frontend_app_name" \
  POSTGRES_SERVER_NAME="$postgres_server_name" \
  POSTGRES_SERVER_FQDN="$postgres_server_fqdn" \
  POSTGRES_PRIVATE_ENDPOINT_NAME="$postgres_private_endpoint_name" \
  DB_SCHEMA_MANAGED_EXTERNALLY=true

if [[ -n "${RUNTIME_DATABASE_URL:-}" ]]; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
    RUNTIME_DATABASE_URL="$RUNTIME_DATABASE_URL" \
    DATABASE_URL="$RUNTIME_DATABASE_URL"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env config set \
    infra.parameters.runtimeDatabaseUrl "$RUNTIME_DATABASE_URL"
fi

echo "Bootstrapped the private AZD environment from the canonical profile and live resource outputs."
