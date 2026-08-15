#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin base64
require_bin jq

get_arm_token() {
  local output=""
  local exit_code=0
  local retry_delay=0
  for retry_delay in 0 15 30; do
    if [[ "$retry_delay" -gt 0 ]]; then
      echo "Waiting ${retry_delay}s before retrying the ARM token exchange."
      sleep "$retry_delay"
    fi
    set +e
    output="$(az account get-access-token --resource https://management.azure.com --query accessToken --output tsv 2>&1)"
    exit_code=$?
    set -e
    if [[ "$exit_code" -eq 0 ]]; then
      printf '%s\n' "$output"
      return 0
    fi
    if [[ "$output" != *"Connection reset by peer"* ]]; then
      printf '%s\n' "$output" >&2
      return "$exit_code"
    fi
  done
  printf '%s\n' "$output" >&2
  return "$exit_code"
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE_FILE="${ROOT_DIR}/infra/github-actions-identity/foundry-project-manager.bicep"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/deployment/profiles/foundry-private.env}"
source "${ROOT_DIR}/deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

SUBSCRIPTION_ID="$AZURE_SUBSCRIPTION_ID"
RESOURCE_GROUP="${TARGET_RESOURCE_GROUP:-$AZURE_RESOURCE_GROUP}"
FOUNDRY_PROJECT_NAME="${TARGET_FOUNDRY_PROJECT:-$FOUNDRY_PROJECT_NAME}"

az account set --subscription "$SUBSCRIPTION_ID"

if [[ -z "${FOUNDRY_ACCOUNT_NAME:-}" ]]; then
  FOUNDRY_ACCOUNT_NAME="$(
    az cognitiveservices account list \
      --resource-group "$RESOURCE_GROUP" \
      --query "[?kind=='AIServices'].name | [0]" \
      --output tsv
  )"
fi
[[ -n "$FOUNDRY_ACCOUNT_NAME" ]] || {
  echo "A Foundry account is required in the selected resource group." >&2
  exit 1
}

container_registry_name="$(az acr list --resource-group "$RESOURCE_GROUP" --query '[0].name' --output tsv)"
[[ -n "$container_registry_name" ]] || {
  echo "Expected exactly one private ACR in the selected resource group."
  exit 1
}
[[ "$(az acr list --resource-group "$RESOURCE_GROUP" --query 'length(@)' --output tsv)" == "1" ]] || {
  echo "Expected exactly one private ACR in the selected resource group."
  exit 1
}

arm_token="$(get_arm_token)"
token_payload="$(cut -d. -f2 <<<"$arm_token")"
token_payload="${token_payload//-/+}"
token_payload="${token_payload//_/\/}"
case $((${#token_payload} % 4)) in
  2) token_payload+='==' ;;
  3) token_payload+='=' ;;
  0) ;;
  *)
    echo "Azure ARM token payload is invalid."
    exit 1
    ;;
esac

deployment_principal_id="$(printf '%s' "$token_payload" | base64 --decode | jq -r '.oid // empty')"
[[ "$deployment_principal_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || {
  echo "Azure ARM token does not identify a service principal object ID."
  exit 1
}

az deployment group create \
  --name order-resolution-private-foundry-project-manager \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$TEMPLATE_FILE" \
  --parameters \
    deploymentPrincipalId="$deployment_principal_id" \
    foundryAccountName="$FOUNDRY_ACCOUNT_NAME" \
    foundryProjectName="$FOUNDRY_PROJECT_NAME" \
    containerRegistryName="$container_registry_name" \
  --output none

echo "Foundry Project Manager and private ACR push roles are synchronized for the protected release identity."
