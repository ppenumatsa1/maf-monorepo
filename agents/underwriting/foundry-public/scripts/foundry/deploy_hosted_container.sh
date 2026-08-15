#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/.venv/bin/python"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
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

require_bin az
require_bin azd
require_bin git
[[ -x "$PYTHON" ]] || {
  echo "Project virtual environment is required; run make install first." >&2
  exit 1
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
"$ROOT_DIR/scripts/foundry/sync_hosted_source.sh"

registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
foundry_account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
foundry_project_name="$(required_env FOUNDRY_PROJECT_NAME)"
agent_name="$(required_env HOSTED_AGENT_NAME)"
runtime_connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"
image_repository="underwriting-hosted"
image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="${registry_endpoint}/${image_repository}:${image_tag}"
postgres_server_name="$(required_env POSTGRES_SERVER_NAME)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
database_url="$(required_env DATABASE_URL)"

[[ "$runtime_connection_name" == "underwritingruntimesecrets" ]] || {
  echo "FOUNDRY_RUNTIME_CONNECTION_NAME must be underwritingruntimesecrets." >&2
  exit 1
}
if [[ "$runtime_database_url" != "$database_url" ]]; then
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match." >&2
  exit 1
fi
if [[ "$runtime_database_url" != *"postgresql+psycopg://"* ||
      "$runtime_database_url" != *"@${postgres_server_name}.postgres.database.azure.com:5432/"* ||
      "$runtime_database_url" != *"sslmode=require"* ]]; then
  echo "RUNTIME_DATABASE_URL must be a TLS PostgreSQL URL for the configured server." >&2
  exit 1
fi

az account set --subscription "$subscription_id" >/dev/null
connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account_name}/projects/${foundry_project_name}/connections/${runtime_connection_name}?api-version=2025-04-01-preview"
connection_category="$(
  az rest \
    --method get \
    --url "$connection_url" \
    --query properties.category \
    --output tsv
)"
[[ "$connection_category" == "CustomKeys" ]] || {
  echo "Hosted runtime CustomKeys connection is missing; run make foundry-runtime-connection." >&2
  exit 1
}

az acr build \
  --subscription "$subscription_id" \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent"

export AZURE_AI_PROJECT_ENDPOINT="$project_endpoint"
export HOSTED_AGENT_NAME="$agent_name"
export HOSTED_AGENT_IMAGE="$image"
export FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name"
export DB_AUTH_MODE="password"
export DB_SCHEMA_MANAGED_EXTERNALLY="true"
export UNDERWRITING_MODEL_DEPLOYMENT_NAME="$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
export UNDERWRITING_APPINSIGHTS_CONNECTION_STRING="$(required_env APPLICATIONINSIGHTS_CONNECTION_STRING)"
export AZURE_OPENAI_ENDPOINT="$(required_env AZURE_OPENAI_ENDPOINT)"

deployment_output="$("$PYTHON" "$ROOT_DIR/scripts/foundry/deploy_hosted_container.py")"
unset database_url runtime_database_url
printf '%s\n' "$deployment_output"
agent_version="$(printf '%s\n' "$deployment_output" | sed -n 's/^HOSTED_AGENT_VERSION=//p' | tail -n 1)"
[[ -n "$agent_version" ]] || {
  echo "Hosted agent deployment did not report an active version." >&2
  exit 1
}
"$ROOT_DIR/scripts/foundry/converge_hosted_agent_rbac.sh"

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_NAME "$HOSTED_AGENT_NAME" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_VERSION "$agent_version" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT \
    "${AZURE_AI_PROJECT_ENDPOINT}/agents/${HOSTED_AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1" \
    --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null

echo "Hosted agent image deployment completed: ${image}"
