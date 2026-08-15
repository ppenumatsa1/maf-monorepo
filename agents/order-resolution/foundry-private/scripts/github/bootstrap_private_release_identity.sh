#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IDENTITY_DIR="${ROOT_DIR}/infra/github-actions-identity"
PROJECT_MANAGER_TEMPLATE="${IDENTITY_DIR}/foundry-project-manager.bicep"
ORDER_RESOLUTION_DIR="$(cd "$ROOT_DIR/.." && pwd -P)"
PROFILE_PATH="${DEPLOYMENT_PROFILE_PATH:-$ORDER_RESOLUTION_DIR/deployment/profiles/foundry-private.env}"
source "$ORDER_RESOLUTION_DIR/deployment/profile.sh"
deployment_profile_load "$PROFILE_PATH"
deployment_profile_validate
deployment_profile_export

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

SUBSCRIPTION_ID="$AZURE_SUBSCRIPTION_ID"
RESOURCE_GROUP="$AZURE_RESOURCE_GROUP"
AZURE_TENANT_ID="$(deployment_profile_value AZURE_TENANT_ID)"
DEPLOYMENT_NAME="order-resolution-private-github-identity"
github_owner="${GITHUB_REPOSITORY%%/*}"
github_repository_name="${GITHUB_REPOSITORY#*/}"
github_owner_id="$(gh api "users/${github_owner}" --jq .id)"
github_repository_id="$(gh api "repos/${GITHUB_REPOSITORY}" --jq .id)"
GITHUB_SUBJECT="${GITHUB_SUBJECT:-repo:${github_owner}@${github_owner_id}/${github_repository_name}@${github_repository_id}:ref:refs/heads/main}"
APPLICATION_UNIQUE_NAME="${APPLICATION_UNIQUE_NAME:-order-resolution-private-${SUBSCRIPTION_ID}}"
APPLICATION_DISPLAY_NAME="${APPLICATION_DISPLAY_NAME:-Order Resolution Foundry Private GitHub Actions}"
FEDERATED_CREDENTIAL_NAME="${FEDERATED_CREDENTIAL_NAME:-github-main}"
LEGACY_APPLICATION_ID="${LEGACY_APPLICATION_ID:-}"
LEGACY_FEDERATED_CREDENTIAL_NAME="${LEGACY_FEDERATED_CREDENTIAL_NAME:-}"
INCORRECT_MANAGED_IDENTITY_OPERATOR_ROLE_ID="f1a07417-d97a-45cb-824c-7a7467783830"

require_bin az
require_bin jq
require_bin gh

az account set --subscription "$SUBSCRIPTION_ID"

deployment_json="$(
  az deployment group create \
    --name "$DEPLOYMENT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "${IDENTITY_DIR}/main.bicep" \
    --parameters \
      githubRepository="$GITHUB_REPOSITORY" \
      githubSubject="$GITHUB_SUBJECT" \
      applicationUniqueName="$APPLICATION_UNIQUE_NAME" \
      applicationDisplayName="$APPLICATION_DISPLAY_NAME" \
      federatedCredentialName="$FEDERATED_CREDENTIAL_NAME" \
    --output json
)"

client_id="$(jq -r '.properties.outputs.githubActionsClientId.value // empty' <<<"$deployment_json")"
principal_id="$(jq -r '.properties.outputs.githubActionsPrincipalId.value // empty' <<<"$deployment_json")"
[[ -n "$client_id" ]] || {
  echo "Identity deployment did not return githubActionsClientId."
  exit 1
}
[[ -n "$principal_id" ]] || {
  echo "Identity deployment did not return githubActionsPrincipalId."
  exit 1
}

foundry_account_name="$(
  az cognitiveservices account list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?kind=='AIServices'].name | [0]" \
    --output tsv
)"
container_registry_name="$(
  az acr list --resource-group "$RESOURCE_GROUP" --query '[0].name' --output tsv
)"
[[ -n "$foundry_account_name" && -n "$container_registry_name" ]] || {
  echo "The Foundry account and private ACR must exist before release identity bootstrap."
  exit 1
}
az deployment group create \
  --name order-resolution-private-foundry-project-manager \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$PROJECT_MANAGER_TEMPLATE" \
  --parameters \
    deploymentPrincipalId="$principal_id" \
    foundryAccountName="$foundry_account_name" \
    foundryProjectName="$FOUNDRY_PROJECT_NAME" \
    containerRegistryName="$container_registry_name" \
  --output none

gh variable set AZURE_CLIENT_ID --repo "$GITHUB_REPOSITORY" --body "$client_id"
gh variable set AZURE_TENANT_ID --repo "$GITHUB_REPOSITORY" --body "$AZURE_TENANT_ID"
gh variable set AZURE_SUBSCRIPTION_ID --repo "$GITHUB_REPOSITORY" --body "$SUBSCRIPTION_ID"

if [[ -n "$LEGACY_APPLICATION_ID" && -n "$LEGACY_FEDERATED_CREDENTIAL_NAME" ]]; then
  legacy_credential_id="$(
    az ad app federated-credential list \
      --id "$LEGACY_APPLICATION_ID" \
      --query "[?name=='${LEGACY_FEDERATED_CREDENTIAL_NAME}'].id | [0]" \
      --output tsv
  )"
  if [[ -n "$legacy_credential_id" ]]; then
    az ad app federated-credential delete \
      --id "$LEGACY_APPLICATION_ID" \
      --federated-credential-id "$legacy_credential_id"
    echo "Retired the explicitly selected legacy federated credential."
  fi
fi

incorrect_role_assignment_ids="$(
  az role assignment list \
    --assignee "$client_id" \
    --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
    --query "[?ends_with(roleDefinitionId, '/${INCORRECT_MANAGED_IDENTITY_OPERATOR_ROLE_ID}')].id" \
    --output tsv
)"
while IFS= read -r incorrect_role_assignment_id; do
  [[ -n "$incorrect_role_assignment_id" ]] || continue
  az role assignment delete --ids "$incorrect_role_assignment_id"
  echo "Removed the superseded Managed Identity Operator assignment."
done <<<"$incorrect_role_assignment_ids"

echo "Private GitHub Actions identity is synchronized."
