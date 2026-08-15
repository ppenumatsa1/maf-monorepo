#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
cd "${ROOT_DIR}/infra/foundry-hosted"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt

get_env_value() {
  local key="$1"
  local value
  if value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$key" 2>/dev/null)"; then
    printf "%s" "$value"
  fi
}

url_encode() {
  local raw="$1"
  python3 - "$raw" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=''))
PY
}

url_host() {
  local value="$1"
  python3 - "$value" <<'PY'
import re
import sys
match = re.match(r'^[a-zA-Z0-9+.-]+://(?:[^@/]+@)?([^:/?]+)', sys.argv[1] or '')
print(match.group(1).lower() if match else '')
PY
}

replace_url_host() {
  local value="$1"
  local new_host="$2"
  python3 - "$value" "$new_host" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit

value = sys.argv[1]
new_host = sys.argv[2]
parts = urlsplit(value)
if not parts.scheme:
    print(value)
    raise SystemExit(0)

userinfo = ""
host_port = parts.netloc
if "@" in host_port:
    userinfo, host_port = host_port.rsplit("@", 1)

port = ""
if ":" in host_port:
    _, port = host_port.rsplit(":", 1)

netloc = f"{userinfo}@{new_host}" if userinfo else new_host
if port:
    netloc = f"{netloc}:{port}"

print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

set_if_missing() {
  local key="$1"
  local value="$2"
  local existing
  if [[ -z "$value" ]]; then
    return
  fi
  existing="$(get_env_value "$key")"
  if [[ -z "$existing" ]]; then
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set "$key" "$value" >/dev/null
    echo "defaulted $key=$value"
  fi
}

mode="${NETWORK_MODE:-$(get_env_value NETWORK_MODE)}"
if [[ "$mode" != "private" ]]; then
  echo "NETWORK_MODE must be 'private' for this branch. Found: $mode"
  exit 1
fi

set_if_missing NETWORK_MODE "$mode"
set_if_missing AI_SEARCH_LOCATION "$AI_SEARCH_LOCATION"
set_if_missing FOUNDRY_PROJECT_NAME "$FOUNDRY_PROJECT_NAME"
set_if_missing RESTORE_FOUNDRY_ACCOUNT "$RESTORE_FOUNDRY_ACCOUNT"
set_if_missing HOSTED_AGENT_NAME "$HOSTED_AGENT_NAME"
set_if_missing RUNTIME_DATABASE_URL "${RUNTIME_DATABASE_URL:-}"
set_if_missing DATABASE_URL "${DATABASE_URL:-}"
set_if_missing CREATE_POSTGRES_SERVER "$CREATE_POSTGRES_SERVER"
set_if_missing POSTGRES_SERVER_NAME "${POSTGRES_SERVER_NAME:-}"
set_if_missing POSTGRES_ADMIN_USERNAME "$POSTGRES_ADMIN_USERNAME"
set_if_missing POSTGRES_ADMIN_PASSWORD "${POSTGRES_ADMIN_PASSWORD:-}"
set_if_missing POSTGRES_DATABASE_NAME "$POSTGRES_DATABASE_NAME"
set_if_missing POSTGRES_LOCATION "$POSTGRES_LOCATION"
name_prefix="$(get_env_value NAME_PREFIX)"
[[ "$name_prefix" == "$NAME_PREFIX" ]] || {
  echo "AZD NAME_PREFIX does not match the selected deployment profile." >&2
  exit 1
}
set_if_missing ENABLE_CONTAINER_APPS "$ENABLE_CONTAINER_APPS"
set_if_missing CONTAINER_APPS_ENVIRONMENT_NAME "${CONTAINER_APPS_ENVIRONMENT_NAME:-${name_prefix}-private-aca}"
set_if_missing BACKEND_CONTAINER_APP_NAME "${BACKEND_CONTAINER_APP_NAME:-${name_prefix}-private-backend}"
set_if_missing FRONTEND_CONTAINER_APP_NAME "${FRONTEND_CONTAINER_APP_NAME:-${name_prefix}-private-frontend}"
set_if_missing SERVICE_BACKEND_IMAGE_NAME "${SERVICE_BACKEND_IMAGE_NAME:-mcr.microsoft.com/k8se/quickstart:latest}"
set_if_missing SERVICE_FRONTEND_IMAGE_NAME "${SERVICE_FRONTEND_IMAGE_NAME:-mcr.microsoft.com/k8se/quickstart:latest}"
set_if_missing ENABLE_POSTGRES_PRIVATE_ENDPOINT "$ENABLE_POSTGRES_PRIVATE_ENDPOINT"
set_if_missing CREATE_PRIVATE_DNS_VNET_LINKS "$CREATE_PRIVATE_DNS_VNET_LINKS"
set_if_missing CREATE_PRIVATE_ENDPOINTS "$CREATE_PRIVATE_ENDPOINTS"
set_if_missing CREATE_NAT_GATEWAY "$CREATE_NAT_GATEWAY"
set_if_missing CREATE_PRIVATE_RUNNER_ACCESS "$CREATE_PRIVATE_RUNNER_ACCESS"
set_if_missing CREATE_BASTION_HOST "$CREATE_BASTION_HOST"
set_if_missing CREATE_RUNNER_VM "$CREATE_RUNNER_VM"
set_if_missing ENABLE_STANDARD_AGENT_NETWORK_INJECTION "$ENABLE_STANDARD_AGENT_NETWORK_INJECTION"
set_if_missing ASSIGN_PRE_CAPHOST_RBAC "$ASSIGN_PRE_CAPHOST_RBAC"
set_if_missing ASSIGN_POST_CAPHOST_RBAC "$ASSIGN_POST_CAPHOST_RBAC"
set_if_missing CREATE_ACCOUNT_CAPABILITY_HOST "$CREATE_ACCOUNT_CAPABILITY_HOST"
set_if_missing CREATE_PROJECT_CAPABILITY_HOST "$CREATE_PROJECT_CAPABILITY_HOST"
set_if_missing MANAGE_PROJECT_CONNECTIONS "$MANAGE_PROJECT_CONNECTIONS"
set_if_missing FOUNDRY_MODEL_DEPLOYMENT_NAME "$FOUNDRY_MODEL_DEPLOYMENT_NAME"
set_if_missing FOUNDRY_EVAL_MODEL "${FOUNDRY_EVAL_MODEL:-$(get_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)}"
set_if_missing FOUNDRY_CHAT_DEPLOYMENT_CAPACITY "$FOUNDRY_CHAT_DEPLOYMENT_CAPACITY"
set_if_missing FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY"
set_if_missing RUNNER_VM_SSH_PUBLIC_KEY "${RUNNER_VM_SSH_PUBLIC_KEY:-}"
set_if_missing ENABLE_TELEMETRY "${ENABLE_TELEMETRY:-true}"
set_if_missing ENABLE_INSTRUMENTATION "${ENABLE_INSTRUMENTATION:-true}"
set_if_missing APP_ENV "${APP_ENV:-production}"
set_if_missing STORE_PROVIDER "${STORE_PROVIDER:-postgres}"
set_if_missing MEMORY_PROVIDER "${MEMORY_PROVIDER:-postgres}"
set_if_missing RAG_PROVIDER "${RAG_PROVIDER:-pgvector}"
set_if_missing OTEL_SERVICE_NAME "${OTEL_SERVICE_NAME:-maf-order-resolution-hosted}"
set_if_missing OTEL_SERVICE_NAMESPACE "${OTEL_SERVICE_NAMESPACE:-maf-order-resolution}"
set_if_missing OTEL_RECORD_CONTENT "${OTEL_RECORD_CONTENT:-false}"
set_if_missing DB_SCHEMA_MANAGED_EXTERNALLY true
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT true >/dev/null
echo "enforced FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT=true for marked private evaluation requests"

restore_foundry_account="$(get_env_value RESTORE_FOUNDRY_ACCOUNT)"
foundry_project_endpoint="$(get_env_value FOUNDRY_PROJECTS_ENDPOINT)"
azure_resource_group="$(get_env_value AZURE_RESOURCE_GROUP)"
foundry_account_name="${foundry_project_endpoint#https://}"
foundry_account_name="${foundry_account_name%%.*}"
if [[ "$restore_foundry_account" == "true" && -n "$azure_resource_group" && -n "$foundry_account_name" ]] && \
  az cognitiveservices account show \
    --name "$foundry_account_name" \
    --resource-group "$azure_resource_group" \
    --query id \
    --output tsv >/dev/null 2>&1; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set RESTORE_FOUNDRY_ACCOUNT false >/dev/null
  echo "cleared RESTORE_FOUNDRY_ACCOUNT because $foundry_account_name is active"
fi

runtime_database_url_existing="$(get_env_value RUNTIME_DATABASE_URL)"
create_postgres_server="$(get_env_value CREATE_POSTGRES_SERVER)"
postgres_server_name="$(get_env_value POSTGRES_SERVER_NAME)"
postgres_admin_username="$(get_env_value POSTGRES_ADMIN_USERNAME)"
postgres_admin_password="$(get_env_value POSTGRES_ADMIN_PASSWORD)"
postgres_database_name="$(get_env_value POSTGRES_DATABASE_NAME)"

if [[ -n "$postgres_server_name" ]]; then
  expected_host="${postgres_server_name,,}.postgres.database.azure.com"
  runtime_host="$(url_host "$runtime_database_url_existing")"
  if [[ -n "$runtime_database_url_existing" && "$runtime_host" != "$expected_host" ]]; then
    echo "RUNTIME_DATABASE_URL must target the canonical PostgreSQL server ${expected_host}."
    exit 1
  fi
  set_if_missing POSTGRES_SERVER_FQDN "$expected_host"
elif [[ "$create_postgres_server" != "true" ]]; then
  echo "POSTGRES_SERVER_NAME is required when CREATE_POSTGRES_SERVER is not true."
  exit 1
fi

if [[ "$create_postgres_server" != "true" && -z "$runtime_database_url_existing" ]]; then
  echo "RUNTIME_DATABASE_URL is required when reusing an existing PostgreSQL server."
  exit 1
fi

set_if_missing DATABASE_URL "$runtime_database_url_existing"
set_if_missing POSTGRES_PRIVATE_DNS_ZONE_NAME "privatelink.postgres.database.azure.com"

# Preserve lowercase env keys used by older scripts/workflows.
set_if_missing aiSearchLocation "$(get_env_value AI_SEARCH_LOCATION)"
set_if_missing foundryProjectName "$(get_env_value FOUNDRY_PROJECT_NAME)"
set_if_missing hostedAgentName "$(get_env_value HOSTED_AGENT_NAME)"
set_if_missing networkMode "$(get_env_value NETWORK_MODE)"
set_if_missing createPrivateDnsVnetLinks "$(get_env_value CREATE_PRIVATE_DNS_VNET_LINKS)"
set_if_missing createPrivateEndpoints "$(get_env_value CREATE_PRIVATE_ENDPOINTS)"
set_if_missing createNatGateway "$(get_env_value CREATE_NAT_GATEWAY)"
set_if_missing createPrivateRunnerAccess "$(get_env_value CREATE_PRIVATE_RUNNER_ACCESS)"
set_if_missing createBastionHost "$(get_env_value CREATE_BASTION_HOST)"
set_if_missing createRunnerVm "$(get_env_value CREATE_RUNNER_VM)"
set_if_missing enableStandardAgentNetworkInjection "$(get_env_value ENABLE_STANDARD_AGENT_NETWORK_INJECTION)"
set_if_missing assignPreCaphostRbac "$(get_env_value ASSIGN_PRE_CAPHOST_RBAC)"
set_if_missing assignPostCaphostRbac "$(get_env_value ASSIGN_POST_CAPHOST_RBAC)"
set_if_missing createAccountCapabilityHost "$(get_env_value CREATE_ACCOUNT_CAPABILITY_HOST)"
set_if_missing createProjectCapabilityHost "$(get_env_value CREATE_PROJECT_CAPABILITY_HOST)"
set_if_missing manageProjectConnections "$(get_env_value MANAGE_PROJECT_CONNECTIONS)"
set_if_missing enableContainerApps "$(get_env_value ENABLE_CONTAINER_APPS)"
set_if_missing containerAppsEnvironmentName "$(get_env_value CONTAINER_APPS_ENVIRONMENT_NAME)"
set_if_missing backendContainerAppName "$(get_env_value BACKEND_CONTAINER_APP_NAME)"
set_if_missing frontendContainerAppName "$(get_env_value FRONTEND_CONTAINER_APP_NAME)"
set_if_missing backendImageName "$(get_env_value SERVICE_BACKEND_IMAGE_NAME)"
set_if_missing frontendImageName "$(get_env_value SERVICE_FRONTEND_IMAGE_NAME)"
set_if_missing enablePostgresPrivateEndpoint "$(get_env_value ENABLE_POSTGRES_PRIVATE_ENDPOINT)"
set_if_missing foundryChatDeploymentCapacity "$(get_env_value FOUNDRY_CHAT_DEPLOYMENT_CAPACITY)"
set_if_missing foundryEmbeddingsDeploymentCapacity "$(get_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY)"
set_if_missing runnerVmSshPublicKey "$(get_env_value RUNNER_VM_SSH_PUBLIC_KEY)"
set_if_missing runtimeDatabaseUrl "$(get_env_value RUNTIME_DATABASE_URL)"
set_if_missing databaseUrl "$(get_env_value DATABASE_URL)"

project_endpoint="$(get_env_value AZURE_AI_PROJECT_ENDPOINT)"
project_id="$(get_env_value AZURE_AI_PROJECT_ID)"
if [[ "${FOUNDRY_POST_PROVISION_HYDRATE:-0}" == "1" ]]; then
  [[ -n "$project_endpoint" && -n "$project_id" ]] || {
    echo "Provision did not publish the Foundry project endpoint and resource ID." >&2
    exit 1
  }
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set FOUNDRY_PROJECT_ENDPOINT "$project_endpoint" >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint" >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set FOUNDRY_PROJECT_ID "$project_id" >/dev/null
  for output_key in \
    AZURE_CONTAINER_REGISTRY_NAME AZURE_CONTAINER_REGISTRY_ENDPOINT \
    CONTAINER_APPS_ENVIRONMENT_NAME BACKEND_CONTAINER_APP_NAME \
    FRONTEND_CONTAINER_APP_NAME PRIVATE_RUNNER_VM_NAME; do
    output_value="$(get_env_value "$output_key")"
    [[ -n "$output_value" ]] || {
      echo "Provision did not publish required output: $output_key" >&2
      exit 1
    }
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env set "$output_key" "$output_value" >/dev/null
  done
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set SERVICE_BACKEND_NAME "$(get_env_value BACKEND_CONTAINER_APP_NAME)" >/dev/null
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set SERVICE_FRONTEND_NAME "$(get_env_value FRONTEND_CONTAINER_APP_NAME)" >/dev/null
elif [[ -z "$project_endpoint" || -z "$project_id" ]]; then
  echo "Foundry outputs are not available yet; they will be hydrated after provisioning."
fi
