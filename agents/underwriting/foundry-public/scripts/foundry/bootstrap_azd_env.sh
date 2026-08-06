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

require_bin az
require_bin azd
require_bin curl

subscription_id="${AZURE_SUBSCRIPTION_ID:-4f18d577-3506-4a11-85e5-a83b14727a84}"
resource_group="${AZURE_RESOURCE_GROUP:-rg-underwriting-readiness-0731}"
foundry_account="${FOUNDRY_ACCOUNT_NAME:-azfdwhcedyxchnbtm}"
foundry_project="${FOUNDRY_PROJECT_NAME:-azprwhcedyxchnbtm}"
registry="${CONTAINER_REGISTRY_NAME:-azcrwhcedyxchnbtm}"
postgres="${POSTGRES_SERVER_NAME:-azpgwhcedyxchnbtmpub}"
postgres_location="${POSTGRES_SERVER_LOCATION:-northcentralus}"
environment="${CONTAINER_APPS_ENVIRONMENT_NAME:-azmewhcedyxchnbtmpub}"
backend="${BACKEND_CONTAINER_APP_NAME:-azcawhcedyxchnbtmpubbe}"
backend_identity="${PUBLIC_BACKEND_MANAGED_IDENTITY_NAME:-azidwhcedyxchnbtm}"
frontend="${FRONTEND_CONTAINER_APP_NAME:-azcawhcedyxchnbtmpubfe}"
app_insights="${APPLICATION_INSIGHTS_NAME:-azaiwhcedyxchnbtm}"
log_analytics="${LOG_ANALYTICS_WORKSPACE_NAME:-azlawhcedyxchnbtm}"
hosted_agent="${HOSTED_AGENT_NAME:-underwriting-hosted}"
azd_environment="${FOUNDRY_AZD_ENV_NAME:-${AZD_ENV_NAME:-underwriting-foundry-public}}"

az account set --subscription "$subscription_id"
azd auth login --check-status >/dev/null
location="$(az group show --name "$resource_group" --query location -o tsv)"
operator_ip="${POSTGRES_OPERATOR_IP:-}"
if [[ -z "$operator_ip" ]]; then
  operator_ip="$(curl --fail --silent --show-error --max-time 10 https://api.ipify.org)"
fi
if [[ ! "$operator_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "POSTGRES_OPERATOR_IP must be a public IPv4 address." >&2
  exit 1
fi

registry_endpoint="$(az acr show --resource-group "$resource_group" --name "$registry" --query loginServer -o tsv)"
foundry_endpoint="$(az cognitiveservices account show --resource-group "$resource_group" --name "$foundry_account" --query properties.endpoint -o tsv)"
appinsights_connection_string="$(az monitor app-insights component show --resource-group "$resource_group" --app "$app_insights" --query connectionString -o tsv)"
appinsights_resource_id="$(az monitor app-insights component show --resource-group "$resource_group" --app "$app_insights" --query id -o tsv)"

(
  cd "$FOUNDRY_DIR"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$azd_environment" --no-prompt \
    || AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env new "$azd_environment" --no-prompt

  set_value() {
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set "$1" "$2" --no-prompt >/dev/null
  }

  set_value AZURE_SUBSCRIPTION_ID "$subscription_id"
  set_value AZURE_RESOURCE_GROUP "$resource_group"
  set_value AZURE_LOCATION "$location"
  set_value FOUNDRY_ACCOUNT_NAME "$foundry_account"
  set_value FOUNDRY_PROJECT_NAME "$foundry_project"
  set_value AZURE_AI_PROJECT_ENDPOINT "https://${foundry_account}.services.ai.azure.com/api/projects/${foundry_project}"
  set_value FOUNDRY_PROJECT_ENDPOINT "https://${foundry_account}.services.ai.azure.com/api/projects/${foundry_project}"
  set_value FOUNDRY_PROJECTS_ENDPOINT "https://${foundry_account}.services.ai.azure.com/api/projects/${foundry_project}"
  set_value CONTAINER_REGISTRY_NAME "$registry"
  set_value AZURE_CONTAINER_REGISTRY_NAME "$registry"
  set_value AZURE_CONTAINER_REGISTRY_ENDPOINT "$registry_endpoint"
  set_value POSTGRES_SERVER_NAME "$postgres"
  set_value POSTGRES_SERVER_LOCATION "$postgres_location"
  set_value POSTGRES_OPERATOR_IP "$operator_ip"
  set_value POSTGRES_DATABASE "${POSTGRES_DATABASE:-underwriting}"
  set_value POSTGRES_RUNTIME_USERNAME "${POSTGRES_RUNTIME_USERNAME:-underwriting_runtime}"
  set_value POSTGRES_ADMIN_USERNAME "${POSTGRES_ADMIN_USERNAME:-pgadmin}"
  set_value DB_AUTH_MODE "password"
  set_value CONTAINER_APPS_ENVIRONMENT_NAME "$environment"
  set_value BACKEND_CONTAINER_APP_NAME "$backend"
  set_value PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "$backend_identity"
  set_value FRONTEND_CONTAINER_APP_NAME "$frontend"
  set_value APPLICATION_INSIGHTS_NAME "$app_insights"
  set_value LOG_ANALYTICS_WORKSPACE_NAME "$log_analytics"
  set_value HOSTED_AGENT_NAME "$hosted_agent"
  set_value FOUNDRY_HOSTED_AGENT_NAME "$hosted_agent"
  set_value FOUNDRY_MODEL_DEPLOYMENT_NAME "${FOUNDRY_MODEL_DEPLOYMENT_NAME:-underwriting-gpt-4-1-mini}"
  set_value AZURE_OPENAI_ENDPOINT "$foundry_endpoint"
  set_value APPLICATIONINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
  set_value APPINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
  set_value APPLICATIONINSIGHTS_RESOURCE_ID "$appinsights_resource_id"
)

echo "Configured azd environment '$azd_environment' for existing underwriting resources."
echo "Run make foundry-provision, then make foundry-postgres-credentials with secure credentials before release deployment."
