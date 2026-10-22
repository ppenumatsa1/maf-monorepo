#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

for command in az azd jq; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

get_env() {
  local value
  if value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    printf '%s' "$value"
  fi
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
project_name="$(required_env FOUNDRY_PROJECT_NAME)"
connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"

az account set --subscription "$subscription_id"
connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/${connection_name}?api-version=2025-04-01-preview"
metadata="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --query '{name:name,category:properties.category,auth_type:properties.authType,api_type:properties.metadata.ApiType}' \
    --output json
)"
jq -e --arg name "$connection_name" '
  .name == $name
  and .category == "CustomKeys"
  and .auth_type == "CustomKeys"
  and .api_type == "KeyValue"
' <<<"$metadata" >/dev/null || {
  echo "Existing Foundry runtime connection is missing or misconfigured." >&2
  exit 1
}

echo "Existing Foundry runtime connection passed read-only verification."
