#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

require_value() {
  local name="$1"
  local value="${!name:-}"
  [[ -n "$value" ]] || {
    echo "$name is required." >&2
    exit 1
  }
}

for name in AZURE_ENV_NAME AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION; do
  require_value "$name"
done

[[ "$AZURE_ENV_NAME" == "maf-ora-azure" ]] || {
  echo "The CI validation environment must be maf-ora-azure." >&2
  exit 1
}
[[ "$AZURE_RESOURCE_GROUP" == "rg-$AZURE_ENV_NAME" ]] || {
  echo "AZURE_RESOURCE_GROUP does not match the selected AZD environment." >&2
  exit 1
}

azd env new "$AZURE_ENV_NAME" --no-prompt >/dev/null 2>&1 || \
  azd env select "$AZURE_ENV_NAME" --no-prompt

resolve_app_name() {
  local service_name="$1"
  local matching_apps
  readarray -t matching_apps < <(
    az containerapp list \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --query "[?tags.\"azd-service-name\"=='$service_name'].name" \
      --output tsv
  )
  [[ "${#matching_apps[@]}" == 1 ]] || {
    echo "Expected exactly one Container App tagged azd-service-name=$service_name." >&2
    exit 1
  }
  printf '%s\n' "${matching_apps[0]}"
}

backend_app="$(resolve_app_name backend)"
frontend_app="$(resolve_app_name frontend)"
api_fqdn="$(az containerapp show \
  --name "$backend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)"
web_fqdn="$(az containerapp show \
  --name "$frontend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)"
foundry_endpoint="$(az containerapp show \
  --name "$backend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query "properties.template.containers[0].env[?name=='FOUNDRY_PROJECTS_ENDPOINT'].value | [0]" \
  --output tsv)"
foundry_model="$(az containerapp show \
  --name "$backend_app" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query "properties.template.containers[0].env[?name=='FOUNDRY_MODEL_DEPLOYMENT_NAME'].value | [0]" \
  --output tsv)"
workspace_resource_id="$(az monitor log-analytics workspace list \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query '[0].id' \
  --output tsv)"

for value_name in api_fqdn web_fqdn foundry_endpoint foundry_model workspace_resource_id; do
  [[ -n "${!value_name}" ]] || {
    echo "Unable to reconstruct $value_name from the deployed application." >&2
    exit 1
  }
done

azd env set AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
azd env set AZURE_LOCATION "$AZURE_LOCATION"
azd env set AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
azd env set API_URL "https://$api_fqdn"
azd env set WEB_URL "https://$web_fqdn"
azd env set AZURE_LOG_ANALYTICS_WORKSPACE_ID "$workspace_resource_id"
azd env set FOUNDRY_PROJECTS_ENDPOINT "$foundry_endpoint"
azd env set FOUNDRY_MODEL_DEPLOYMENT_NAME "$foundry_model"
azd env set FOUNDRY_EVAL_MODEL "${FOUNDRY_EVAL_MODEL:-gpt-4.1-mini-evaluator}"

echo "Reconstructed non-secret AZD release-validation configuration."
