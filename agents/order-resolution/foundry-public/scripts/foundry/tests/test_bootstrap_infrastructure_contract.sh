#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
prepare_script="$root_dir/scripts/foundry/prepare_bootstrap_env.sh"
template="$root_dir/infra/foundry-hosted/iac/main.bicep"
mock_bin="$root_dir/scripts/foundry/tests/mock-bin"
hydration_mock_bin="$root_dir/scripts/foundry/tests/mock-hydration-bin"
scratch_dir="$root_dir/backend/.tmp/bootstrap-contract-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

output="$(PATH="$mock_bin:$PATH" bash "$prepare_script" 2>&1)"
for expected in \
  'set INFRASTRUCTURE_MODE=bootstrap' \
  'Prepared the selected AZD environment for portable bootstrap mode.'; do
  grep -Fxq "$expected" <<<"$output"
done
! grep -Fq 'set FOUNDRY_ACCOUNT_NAME=' <<<"$output"
! grep -Fq 'set FOUNDRY_MODEL_SKU_NAME=' <<<"$output"
! grep -Fq 'set CONTAINER_REGISTRY_NAME=' <<<"$output"

grep -Fq "param infrastructureMode string" "$template"
! grep -Fq "param infrastructureMode string =" "$template"
grep -Fq 'param foundryAccountName string' "$template"
! grep -Fq 'param foundryAccountName string =' "$template"
grep -Fq 'param containerRegistryName string' "$template"
! grep -Fq 'param containerRegistryName string =' "$template"
grep -Fq 'param containerAppsEnvironmentName string' "$template"
! grep -Fq 'param containerAppsEnvironmentName string =' "$template"
grep -Fq 'param postgresServerName string' "$template"
! grep -Fq 'param postgresServerName string =' "$template"
for external_parameter in \
  location foundryCustomSubDomainName logAnalyticsWorkspaceName \
  applicationInsightsName backendContainerAppName frontendContainerAppName \
  publicBackendManagedIdentityName publicFrontendManagedIdentityName \
  aiSearchServiceName aiSearchLocation aiSearchSkuName \
  postgresServerLocation evaluationStorageAccountName \
  bootstrapRuntimeDatabaseUrl; do
  grep -Fq "param ${external_parameter} " "$template"
  ! grep -Eq "param ${external_parameter} [^=]+=" "$template"
done
for postgres_parameter in postgresVersion postgresSkuName postgresSkuTier; do
  grep -Fq "\"${postgres_parameter}\": { \"value\": \"\${POSTGRES_" \
    "$root_dir/infra/foundry-hosted/iac/main.parameters.json"
done
grep -Fq "resource foundryAccountBootstrap" "$template"
grep -Fq "resource foundryProjectBootstrap" "$template"
grep -Fq "resource foundryChatDeploymentBootstrap" "$template"
grep -Fq "resource foundryEmbeddingsDeploymentBootstrap" "$template"
grep -Fq "resource foundryEvaluationDeploymentBootstrap" "$template"
grep -Fq "resource aiSearchBootstrap" "$template"
grep -A15 "resource aiSearchBootstrap" "$template" | grep -Fq "publicNetworkAccess: 'enabled'"
grep -A15 "resource aiSearchBootstrap" "$template" | grep -Fq "disableLocalAuth: true"
grep -B5 -A2 "param foundryChatModelSkuName string" "$template" | grep -Fq "'DataZoneStandard'"
grep -Fq "resource postgresServerBootstrap" "$template"
grep -Fq "resource evaluationStorageAccountBootstrap" "$template"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "publicNetworkAccess: 'Disabled'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "bypass: 'AzureServices'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "defaultAction: 'Deny'"
grep -A50 "resource backendContainerAppBootstrap" "$template" | grep -Fq "external: false"
grep -A50 "resource frontendContainerAppBootstrap" "$template" | grep -Fq "external: true"
grep -Fq "set_env INFRASTRUCTURE_MODE reuse" "$root_dir/scripts/foundry/bootstrap_azd_env.sh"
! grep -REq 'AZURE_RESOURCE_GROUP=rg-[A-Za-z0-9-]+' \
  "$root_dir/Makefile" "$root_dir/scripts/foundry" "$root_dir/infra/foundry-hosted/iac" "$root_dir/deployment"

az bicep build --file "$template" --stdout | python3 -c '
import json
import sys

template = json.load(sys.stdin)
parameter_file = json.loads(
    open(sys.argv[1], encoding="utf-8").read()
)["parameters"]
missing = sorted(
    name for name, value in template["parameters"].items()
    if "defaultValue" not in value and name not in parameter_file
)
assert not missing, missing
assignments = [
    resource for resource in template["resources"]
    if resource["type"] == "Microsoft.Authorization/roleAssignments"
]
assert len(assignments) == 10
assert all("scope" in assignment for assignment in assignments)
assert all(resource.get("condition") for resource in assignments)
' "$root_dir/infra/foundry-hosted/iac/main.parameters.json"

MOCK_AZD_LOG="$scratch_dir/hydrated.env" \
  PATH="$hydration_mock_bin:$PATH" \
  bash "$root_dir/scripts/foundry/bootstrap_azd_env.sh" >/dev/null

for output_name in \
  AZURE_AI_PROJECT_ENDPOINT AZURE_AI_PROJECT_ID FOUNDRY_PROJECT_ENDPOINT \
  FOUNDRY_PROJECTS_ENDPOINT FOUNDRY_ACCOUNT_NAME FOUNDRY_PROJECT_NAME \
  FOUNDRY_CUSTOM_SUBDOMAIN_NAME \
  FOUNDRY_HOSTED_RESPONSES_URL FOUNDRY_MODEL_DEPLOYMENT_NAME \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME FOUNDRY_EVAL_MODEL HOSTED_AGENT_NAME \
  FOUNDRY_RUNTIME_CONNECTION_NAME \
  AZURE_OPENAI_ENDPOINT AZURE_CONTAINER_REGISTRY_NAME \
  AZURE_CONTAINER_REGISTRY_ENDPOINT APPLICATIONINSIGHTS_RESOURCE_ID \
  APPLICATIONINSIGHTS_CONNECTION_STRING LOG_ANALYTICS_WORKSPACE_ID \
  AZURE_POSTGRES_SERVER_FQDN POSTGRES_SERVER_NAME POSTGRES_SERVER_LOCATION \
  POSTGRES_DATABASE AZURE_CONTAINER_APPS_ENVIRONMENT_ID \
  CONTAINER_APPS_ENVIRONMENT_NAME BACKEND_CONTAINER_APP_ID \
  BACKEND_CONTAINER_APP_NAME FRONTEND_CONTAINER_APP_ID \
  FRONTEND_CONTAINER_APP_NAME PUBLIC_BACKEND_MANAGED_IDENTITY_NAME \
  PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME BACKEND_IMAGE_REPOSITORY \
  FRONTEND_IMAGE_REPOSITORY API_BASE_URL WEB_URL; do
  grep -q "^${output_name}=" "$scratch_dir/hydrated.env"
done
grep -Fxq 'FOUNDRY_CUSTOM_SUBDOMAIN_NAME=portable-subdomain' \
  "$scratch_dir/hydrated.env"
