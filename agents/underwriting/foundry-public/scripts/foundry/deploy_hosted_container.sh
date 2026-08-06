#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/.venv/bin/python"

command -v az >/dev/null
command -v azd >/dev/null
test -x "$PYTHON"

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

ensure_openai_runtime_role() {
  local resource_group foundry_account foundry_project hosted_agent identity_name principal_id scope
  resource_group="$(required_env AZURE_RESOURCE_GROUP)"
  foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
  foundry_project="$(required_env FOUNDRY_PROJECT_NAME)"
  hosted_agent="$(required_env HOSTED_AGENT_NAME)"
  identity_name="${foundry_account}-${foundry_project}-${hosted_agent}-AgentIdentity"
  principal_id="$(
    az ad sp list --display-name "$identity_name" --query '[0].id' --output tsv
  )"
  if [[ -z "$principal_id" ]]; then
    echo "Hosted agent identity '$identity_name' was not created." >&2
    exit 1
  fi

  scope="$(
    az cognitiveservices account show \
      --resource-group "$resource_group" \
      --name "$foundry_account" \
      --query id \
      --output tsv
  )"
  if ! az role assignment list \
    --assignee "$principal_id" \
    --role "Cognitive Services OpenAI User" \
    --scope "$scope" \
    --query 'length(@)' \
    --output tsv | grep -qx '1'; then
    az role assignment create \
      --assignee-object-id "$principal_id" \
      --assignee-principal-type ServicePrincipal \
      --role "Cognitive Services OpenAI User" \
      --scope "$scope" \
      --output none
  fi
}

"$ROOT_DIR/scripts/foundry/sync_hosted_source.sh"

registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
image_repository="underwriting-hosted"
image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image="${registry_endpoint}/${image_repository}:${image_tag}"
postgres_server_name="$(required_env POSTGRES_SERVER_NAME)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
database_url="$(required_env DATABASE_URL)"

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

az acr build \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent"

export AZURE_AI_PROJECT_ENDPOINT="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
export HOSTED_AGENT_NAME="$(required_env HOSTED_AGENT_NAME)"
export HOSTED_AGENT_IMAGE="$image"
export DATABASE_URL="$database_url"
export RUNTIME_DATABASE_URL="$runtime_database_url"
export DB_AUTH_MODE="password"
export UNDERWRITING_MODEL_DEPLOYMENT_NAME="$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
export UNDERWRITING_APPINSIGHTS_CONNECTION_STRING="$(required_env APPLICATIONINSIGHTS_CONNECTION_STRING)"
export AZURE_OPENAI_ENDPOINT="$(required_env AZURE_OPENAI_ENDPOINT)"

deployment_output="$("$PYTHON" "$ROOT_DIR/scripts/foundry/deploy_hosted_container.py")"
printf '%s\n' "$deployment_output"
agent_version="$(printf '%s\n' "$deployment_output" | sed -n 's/^HOSTED_AGENT_VERSION=//p' | tail -n 1)"
test -n "$agent_version"
ensure_openai_runtime_role

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_NAME "$HOSTED_AGENT_NAME" --cwd "$FOUNDRY_DIR" --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_VERSION "$agent_version" --cwd "$FOUNDRY_DIR" --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT \
    "${AZURE_AI_PROJECT_ENDPOINT}/agents/${HOSTED_AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1" \
    --cwd "$FOUNDRY_DIR" --no-prompt
