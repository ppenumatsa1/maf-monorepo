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
  local value
  value="$(azd env get-value "$key" 2>/dev/null || true)"
  [[ -n "$value" ]] || {
    echo "AZD environment value $key is required." >&2
    exit 1
  }
  printf '%s' "$value"
}

require_exact_env() {
  local key="$1"
  local expected="$2"
  local actual
  actual="$(require_env "$key")"
  [[ "$actual" == "$expected" ]] || {
    echo "AZD environment value $key does not match the selected private release target." >&2
    exit 1
  }
}

require_single_resource_name() {
  local resource_type="$1"
  shift
  local -a names
  mapfile -t names < <(
    az "$@" list \
      --resource-group "$TARGET_RESOURCE_GROUP" \
      --query '[].name' \
      --output tsv
  )
  [[ "${#names[@]}" == "1" && -n "${names[0]}" ]] || {
    echo "Expected exactly one $resource_type resource in the selected private resource group." >&2
    exit 1
  }
  printf '%s' "${names[0]}"
}

require_project_connection() {
  local connection_name="$1"
  local category="$2"
  local auth_type="$3"
  local target="$4"
  local resource_id="$5"
  local connection_json
  connection_json="$(
    az rest \
      --method get \
      --url "https://management.azure.com${foundry_project_id}/connections/${connection_name}?api-version=2025-04-01-preview" \
      --query '{category:properties.category,authType:properties.authType,target:properties.target,resourceId:properties.metadata.ResourceId}' \
      --output json
  )"
  CONNECTION_JSON="$connection_json" \
    EXPECTED_CATEGORY="$category" \
    EXPECTED_AUTH_TYPE="$auth_type" \
    EXPECTED_TARGET="$target" \
    EXPECTED_RESOURCE_ID="$resource_id" \
    python3 - <<'PY'
import json
import os
import sys

connection = json.loads(os.environ["CONNECTION_JSON"])
connection["resourceId"] = connection.get("resourceId") or ""
expected = {
    "category": os.environ["EXPECTED_CATEGORY"],
    "authType": os.environ["EXPECTED_AUTH_TYPE"],
    "target": os.environ["EXPECTED_TARGET"],
    "resourceId": os.environ["EXPECTED_RESOURCE_ID"],
}
if connection != expected:
    sys.exit("Foundry project connection does not match the expected private dependency.")
PY
}

require_project_acr_roles() {
  local -a role_names
  mapfile -t role_names < <(
    az role assignment list \
      --assignee "$foundry_project_principal_id" \
      --scope "$acr_id" \
      --include-inherited \
      --all \
      --query '[].roleDefinitionName' \
      --output tsv
  )
  for required_role in AcrPull "Container Registry Repository Reader"; do
    printf '%s\n' "${role_names[@]}" | grep -Fxq "$required_role" || {
      echo "Foundry project identity is missing required $required_role access to the private ACR." >&2
      exit 1
    }
  done
}

for binary in az azd python3; do
  require_bin "$binary"
done

: "${AZD_ENVIRONMENT_NAME:?AZD_ENVIRONMENT_NAME is required}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${TARGET_RESOURCE_GROUP:?TARGET_RESOURCE_GROUP is required}"
: "${TARGET_FOUNDRY_PROJECT:?TARGET_FOUNDRY_PROJECT is required}"
: "${TARGET_POSTGRES_DATABASE:?TARGET_POSTGRES_DATABASE is required}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"

cd "$FOUNDRY_DIR"
azd env select "$AZD_ENVIRONMENT_NAME" --no-prompt

require_exact_env AZURE_RESOURCE_GROUP "$TARGET_RESOURCE_GROUP"
require_exact_env FOUNDRY_PROJECT_NAME "$TARGET_FOUNDRY_PROJECT"
require_exact_env POSTGRES_DATABASE_NAME "$TARGET_POSTGRES_DATABASE"
require_exact_env NETWORK_MODE private
require_exact_env ENABLE_CONTAINER_APPS true
require_exact_env ENABLE_POSTGRES_PRIVATE_ENDPOINT true

postgres_server_name="$(require_env POSTGRES_SERVER_NAME)"
postgres_server_fqdn="$(require_env POSTGRES_SERVER_FQDN)"
expected_postgres_fqdn="${postgres_server_name,,}.postgres.database.azure.com"
[[ "${postgres_server_fqdn,,}" == "$expected_postgres_fqdn" ]] || {
  echo "POSTGRES_SERVER_FQDN must name the canonical private PostgreSQL server." >&2
  exit 1
}

container_environment_name="$(require_env CONTAINER_APPS_ENVIRONMENT_NAME)"
backend_app_name="$(require_env BACKEND_CONTAINER_APP_NAME)"
frontend_app_name="$(require_env FRONTEND_CONTAINER_APP_NAME)"
hosted_agent_name="$(require_env HOSTED_AGENT_NAME)"
foundry_model_deployment_name="$(require_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
foundry_project_id="$(require_env FOUNDRY_PROJECT_ID)"
foundry_project_endpoint="$(require_env FOUNDRY_PROJECTS_ENDPOINT)"
configured_acr_login_server="$(require_env containerRegistryLoginServer)"
configured_acr_endpoint="$(require_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
postgres_private_endpoint_name="$(require_env POSTGRES_PRIVATE_ENDPOINT_NAME)"

actual_subscription_id="$(az account show --query id --output tsv)"
[[ "$actual_subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI is not scoped to the selected private release subscription." >&2
  exit 1
}

az group show --name "$TARGET_RESOURCE_GROUP" --output none

foundry_project_id_lower="${foundry_project_id,,}"
expected_resource_group_segment="/resourcegroups/${TARGET_RESOURCE_GROUP,,}/"
expected_project_segment="/projects/${TARGET_FOUNDRY_PROJECT,,}"
[[ "$foundry_project_id_lower" == *"$expected_resource_group_segment"* &&
  "$foundry_project_id_lower" == *"/providers/microsoft.cognitiveservices/accounts/"* &&
  "$foundry_project_id_lower" == *"$expected_project_segment" ]] || {
  echo "FOUNDRY_PROJECT_ID is not scoped to the selected private Foundry project." >&2
  exit 1
}

foundry_account_name="$(
  python3 - "$foundry_project_id" <<'PY'
import sys

segments = [segment for segment in sys.argv[1].split("/") if segment]
for index, segment in enumerate(segments[:-1]):
    if segment.lower() == "accounts":
        print(segments[index + 1])
        break
PY
)"
[[ -n "$foundry_account_name" ]] || {
  echo "FOUNDRY_PROJECT_ID does not include a Foundry account name." >&2
  exit 1
}

expected_project_endpoint="https://${foundry_account_name}.services.ai.azure.com/api/projects/${TARGET_FOUNDRY_PROJECT}"
[[ "${foundry_project_endpoint,,}" == "${expected_project_endpoint,,}" ]] || {
  echo "FOUNDRY_PROJECTS_ENDPOINT does not match the selected Foundry account and project." >&2
  exit 1
}

foundry_kind="$(
  az cognitiveservices account show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$foundry_account_name" \
    --query kind \
    --output tsv
)"
[[ "$foundry_kind" == "AIServices" ]] || {
  echo "The selected Foundry account must be an AIServices account." >&2
  exit 1
}

foundry_public_network_access="$(
  az cognitiveservices account show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$foundry_account_name" \
    --query properties.publicNetworkAccess \
    --output tsv
)"
[[ "$foundry_public_network_access" == "Disabled" ]] || {
  echo "The selected Foundry account does not preserve private network access." >&2
  exit 1
}

foundry_project_name="$(
  az rest \
    --method get \
    --url "https://management.azure.com${foundry_project_id}?api-version=2025-06-01" \
    --query name \
    --output tsv
)"
[[ "$foundry_project_name" == "$TARGET_FOUNDRY_PROJECT" ]] || {
  echo "The selected Foundry project does not exist." >&2
  exit 1
}
foundry_project_principal_id="$(
  az rest \
    --method get \
    --url "https://management.azure.com${foundry_project_id}?api-version=2025-06-01" \
    --query identity.principalId \
    --output tsv
)"
[[ -n "$foundry_project_principal_id" ]] || {
  echo "The selected Foundry project does not have a managed identity." >&2
  exit 1
}

az cognitiveservices account deployment show \
  --resource-group "$TARGET_RESOURCE_GROUP" \
  --name "$foundry_account_name" \
  --deployment-name "$foundry_model_deployment_name" \
  --output none

postgres_fqdn="$(
  az postgres flexible-server show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$postgres_server_name" \
    --query fullyQualifiedDomainName \
    --output tsv
)"
[[ "${postgres_fqdn,,}" == "$expected_postgres_fqdn" ]] || {
  echo "The selected PostgreSQL server does not resolve to its canonical FQDN." >&2
  exit 1
}

database_count="$(
  az postgres flexible-server db list \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --server-name "$postgres_server_name" \
    --query "[?name=='${TARGET_POSTGRES_DATABASE}'] | length(@)" \
    --output tsv
)"
[[ "$database_count" == "1" ]] || {
  echo "The selected PostgreSQL database does not exist exactly once." >&2
  exit 1
}

az network private-endpoint show \
  --resource-group "$TARGET_RESOURCE_GROUP" \
  --name "$postgres_private_endpoint_name" \
  --output none

container_environment_id="$(
  az containerapp env show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$container_environment_name" \
    --query id \
    --output tsv
)"
container_environment_subnet_id="$(
  az containerapp env show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$container_environment_name" \
    --query properties.vnetConfiguration.infrastructureSubnetId \
    --output tsv
)"
[[ -n "$container_environment_id" && -n "$container_environment_subnet_id" ]] || {
  echo "The selected Container Apps environment is not VNet integrated." >&2
  exit 1
}

for app_name in "$backend_app_name" "$frontend_app_name"; do
  app_environment_id="$(
    az containerapp show \
      --resource-group "$TARGET_RESOURCE_GROUP" \
      --name "$app_name" \
      --query properties.managedEnvironmentId \
      --output tsv
  )"
  [[ "${app_environment_id,,}" == "${container_environment_id,,}" ]] || {
    echo "Container App $app_name is not attached to the selected private environment." >&2
    exit 1
  }
done

backend_external_ingress="$(
  az containerapp show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$backend_app_name" \
    --query properties.configuration.ingress.external \
    --output tsv
)"
frontend_external_ingress="$(
  az containerapp show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$frontend_app_name" \
    --query properties.configuration.ingress.external \
    --output tsv
)"
[[ "$backend_external_ingress" == "false" && "$frontend_external_ingress" == "true" ]] || {
  echo "Container App ingress does not preserve the private backend and external frontend topology." >&2
  exit 1
}

mapfile -t acr_names < <(
  az acr list --resource-group "$TARGET_RESOURCE_GROUP" --query '[].name' --output tsv
)
[[ "${#acr_names[@]}" == "1" ]] || {
  echo "Expected exactly one private ACR in the selected resource group." >&2
  exit 1
}
acr_name="${acr_names[0]}"
acr_login_server="$(
  az acr show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$acr_name" \
    --query loginServer \
    --output tsv
)"
acr_public_network_access="$(
  az acr show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$acr_name" \
    --query publicNetworkAccess \
    --output tsv
)"
[[ "$acr_login_server" == *.azurecr.io &&
  "$configured_acr_login_server" == "$acr_login_server" &&
  "$configured_acr_endpoint" == "$acr_login_server" &&
  "$acr_public_network_access" == "Disabled" ]] || {
  echo "The selected ACR does not match the configured private image registry." >&2
  exit 1
}

acr_id="$(
  az acr show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$acr_name" \
    --query id \
    --output tsv
)"

storage_account_name="$(
  require_single_resource_name "storage account" storage account
)"
storage_resource_id="$(
  az storage account show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$storage_account_name" \
    --query id \
    --output tsv
)"
storage_target="$(
  az storage account show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$storage_account_name" \
    --query primaryEndpoints.blob \
    --output tsv
)"

cosmos_account_name="$(
  require_single_resource_name "Cosmos DB account" cosmosdb
)"
cosmos_resource_id="$(
  az cosmosdb show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$cosmos_account_name" \
    --query id \
    --output tsv
)"
cosmos_target="$(
  az cosmosdb show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$cosmos_account_name" \
    --query documentEndpoint \
    --output tsv
)"

search_service_name="$(
  require_single_resource_name "AI Search service" search service
)"
search_resource_id="$(
  az search service show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --name "$search_service_name" \
    --query id \
    --output tsv
)"

application_insights_name="$(
  require_single_resource_name "Application Insights component" monitor app-insights component
)"
application_insights_resource_id="$(
  az monitor app-insights component show \
    --resource-group "$TARGET_RESOURCE_GROUP" \
    --app "$application_insights_name" \
    --query id \
    --output tsv
)"

require_project_connection \
  "${cosmos_account_name}-${TARGET_FOUNDRY_PROJECT}" \
  CosmosDB \
  AAD \
  "$cosmos_target" \
  "$cosmos_resource_id"
require_project_connection \
  "${storage_account_name}-${TARGET_FOUNDRY_PROJECT}" \
  AzureStorageAccount \
  AAD \
  "$storage_target" \
  "$storage_resource_id"
require_project_connection \
  "${search_service_name}-${TARGET_FOUNDRY_PROJECT}" \
  CognitiveSearch \
  AAD \
  "https://${search_service_name}.search.windows.net" \
  "$search_resource_id"
require_project_connection \
  ApplicationInsights \
  AppInsights \
  ApiKey \
  "$application_insights_resource_id" \
  "$application_insights_resource_id"
require_project_connection \
  orderresolutionruntimesecrets \
  CustomKeys \
  CustomKeys \
  https://runtime-secrets.local \
  ""
require_project_acr_roles

[[ -n "$hosted_agent_name" ]] || {
  echo "HOSTED_AGENT_NAME is required." >&2
  exit 1
}

echo "Validated existing private app-release dependencies, project connections, and RBAC; no secrets or Azure resources were modified."
