#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin gh
require_bin jq

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IDENTITY_DIR="${ROOT_DIR}/infra/github-actions-identity"

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-4f18d577-3506-4a11-85e5-a83b14727a84}"
RESOURCE_GROUP="${TARGET_RESOURCE_GROUP:-rg-maf-ora-foundry-v2}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-ppenumatsa1/maf-monorepo}"
GITHUB_ENVIRONMENT="${GITHUB_ENVIRONMENT:-foundry-private-env}"
AZURE_TENANT_ID="${AZURE_TENANT_ID:-5a591fcf-3aaf-4a22-92a3-6871a34fa158}"
DEPLOYMENT_NAME="order-resolution-private-github-identity"
LOCATION="${AZURE_LOCATION:-eastus2}"
LEGACY_APPLICATION_ID="${LEGACY_APPLICATION_ID:-d4b2e92f-2555-4565-aca3-290cbe6a97f1}"
LEGACY_FEDERATED_CREDENTIAL_NAME="github-maf-monorepo-foundry-private-env"
INCORRECT_MANAGED_IDENTITY_OPERATOR_ROLE_ID="f1a07417-d97a-45cb-824c-7a7467783830"

az account set --subscription "$SUBSCRIPTION_ID"

deployment_json="$(
  az deployment group create \
    --name "$DEPLOYMENT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "${IDENTITY_DIR}/main.bicep" \
    --parameters \
      githubRepository="$GITHUB_REPOSITORY" \
    --output json
)"

client_id="$(jq -r '.properties.outputs.githubActionsClientId.value // empty' <<<"$deployment_json")"
[[ -n "$client_id" ]] || {
  echo "Identity deployment did not return githubActionsClientId."
  exit 1
}

gh api --method PUT "repos/${GITHUB_REPOSITORY}/environments/${GITHUB_ENVIRONMENT}" --silent
gh variable set AZURE_CLIENT_ID --repo "$GITHUB_REPOSITORY" --env "$GITHUB_ENVIRONMENT" --body "$client_id"
gh variable set AZURE_TENANT_ID --repo "$GITHUB_REPOSITORY" --env "$GITHUB_ENVIRONMENT" --body "$AZURE_TENANT_ID"
gh variable set AZURE_SUBSCRIPTION_ID --repo "$GITHUB_REPOSITORY" --env "$GITHUB_ENVIRONMENT" --body "$SUBSCRIPTION_ID"

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
  echo "Retired the temporary legacy monorepo federated credential."
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

echo "Private GitHub Actions identity and environment configuration are synchronized."
