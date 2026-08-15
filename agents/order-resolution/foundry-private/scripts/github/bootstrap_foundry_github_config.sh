#!/usr/bin/env bash
set -euo pipefail

# Bootstrap GitHub configuration for Foundry private runner pipelines.
# Requires: gh CLI, jq
#
# Usage:
#   export GH_PAT=...
#   export REPO=ppenumatsa1/maf-order-resolution-agent
#   export AZURE_CLIENT_ID=...
#   export POSTGRES_SERVER_NAME=<canonical-private-flexible-server>
#   ./scripts/github/bootstrap_foundry_github_config.sh

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin gh
require_bin jq

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
order_resolution_dir="$(cd "$script_dir/../../.." && pwd -P)"
profile_path="${DEPLOYMENT_PROFILE_PATH:-$order_resolution_dir/deployment/profiles/foundry-private.env}"
source "$order_resolution_dir/deployment/profile.sh"
deployment_profile_load "$profile_path"
deployment_profile_validate
deployment_profile_export

[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "DEPLOYMENT_LANE must be foundry-private."
  exit 1
}

AZURE_TENANT_ID="$(deployment_profile_value AZURE_TENANT_ID)"
FOUNDRY_PROJECT_NAME="$(deployment_profile_value FOUNDRY_PROJECT_NAME)"
POSTGRES_DATABASE_NAME="$(deployment_profile_value POSTGRES_DATABASE_NAME)"
PRIVATE_RUNNER_LABEL="$(deployment_profile_value PRIVATE_RUNNER_LABEL)"
PRIVATE_RUNNER_VM_NAME="$(deployment_profile_value PRIVATE_RUNNER_VM_NAME)"

: "${REPO:=}"
: "${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required}"
: "${POSTGRES_SERVER_NAME:?POSTGRES_SERVER_NAME is required}"

if [[ -z "$REPO" ]]; then
  remote_url="$(git remote get-url origin 2>/dev/null || true)"
  if [[ "$remote_url" =~ github.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
    REPO="${BASH_REMATCH[1]}"
  fi
fi

if [[ -z "$REPO" ]]; then
  echo "REPO is required (owner/repo). Set REPO and retry."
  exit 1
fi

if [[ -n "${GH_PAT:-}" ]]; then
  export GH_TOKEN="$GH_PAT"
elif [[ -n "${GH_TOKEN:-}" ]]; then
  :
elif ! gh auth status >/dev/null 2>&1; then
  echo "No GitHub auth found. Set GH_PAT or run: gh auth login"
  exit 1
fi

echo "Setting repository-scoped OIDC and target variables"
gh variable set AZURE_CLIENT_ID -R "$REPO" -b "$AZURE_CLIENT_ID"
gh variable set AZURE_TENANT_ID -R "$REPO" -b "$AZURE_TENANT_ID"
gh variable set AZURE_SUBSCRIPTION_ID -R "$REPO" -b "$AZURE_SUBSCRIPTION_ID"
gh variable set AZURE_ENV_NAME -R "$REPO" -b "$AZURE_ENV_NAME"
gh variable set AZURE_RESOURCE_GROUP -R "$REPO" -b "$AZURE_RESOURCE_GROUP"
gh variable set FOUNDRY_PROJECT_NAME -R "$REPO" -b "$FOUNDRY_PROJECT_NAME"
gh variable set POSTGRES_SERVER_NAME -R "$REPO" -b "$POSTGRES_SERVER_NAME"
gh variable set POSTGRES_DATABASE_NAME -R "$REPO" -b "$POSTGRES_DATABASE_NAME"
gh variable set PRIVATE_RUNNER_LABEL -R "$REPO" -b "$PRIVATE_RUNNER_LABEL"
gh variable set PRIVATE_RUNNER_VM_NAME -R "$REPO" -b "$PRIVATE_RUNNER_VM_NAME"

echo "Validation: variables"
gh variable list -R "$REPO" --json name | jq -r '.[].name' | grep -E 'PRIVATE_RUNNER_(LABEL|VM_NAME)|AZURE_(CLIENT_ID|TENANT_ID|SUBSCRIPTION_ID|ENV_NAME|RESOURCE_GROUP)|FOUNDRY_PROJECT_NAME|POSTGRES_SERVER_NAME|POSTGRES_DATABASE_NAME' || true

echo "Done. The private runner must retain the selected AZD environment and its secrets locally."