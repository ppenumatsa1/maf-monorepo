#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
order_resolution_dir="$(cd "$script_dir/../../.." && pwd -P)"
lane_root="$order_resolution_dir/foundry-private"
source "$lane_root/scripts/foundry/private_profile.sh"
profile_path="$(private_profile_resolve "$lane_root" "${DEPLOYMENT_PROFILE_PATH:-}")"

source "$order_resolution_dir/deployment/profile.sh"
deployment_profile_load "$profile_path"
deployment_profile_validate

[[ "$(deployment_profile_value DEPLOYMENT_LANE)" == "foundry-private" ]] || {
  echo "GitHub target validation failed: DEPLOYMENT_LANE must be foundry-private." >&2
  exit 1
}

require_mirror() {
  local profile_key="$1"
  local github_name="$2"
  local github_value="$3"
  local profile_value

  profile_value="$(deployment_profile_value "$profile_key")" || {
    echo "GitHub target validation failed: profile loader must expose $profile_key." >&2
    exit 1
  }
  [[ -n "$github_value" ]] || {
    echo "GitHub target validation failed: repository variable $github_name is required." >&2
    exit 1
  }
  [[ "$github_value" == "$profile_value" ]] || {
    echo "GitHub target validation failed: $github_name does not match profile key $profile_key." >&2
    exit 1
  }
}

require_mirror AZURE_ENV_NAME AZURE_ENV_NAME "${AZD_ENVIRONMENT_NAME:-}"
require_mirror AZURE_TENANT_ID AZURE_TENANT_ID "${AZURE_TENANT_ID:-}"
require_mirror AZURE_SUBSCRIPTION_ID AZURE_SUBSCRIPTION_ID "${AZURE_SUBSCRIPTION_ID:-}"
require_mirror AZURE_RESOURCE_GROUP AZURE_RESOURCE_GROUP "${TARGET_RESOURCE_GROUP:-}"
require_mirror FOUNDRY_PROJECT_NAME FOUNDRY_PROJECT_NAME "${TARGET_FOUNDRY_PROJECT:-}"
require_mirror POSTGRES_DATABASE_NAME POSTGRES_DATABASE_NAME "${TARGET_POSTGRES_DATABASE:-}"
require_mirror PRIVATE_RUNNER_LABEL PRIVATE_RUNNER_LABEL "${PRIVATE_RUNNER_LABEL:-}"
require_mirror PRIVATE_RUNNER_VM_NAME PRIVATE_RUNNER_VM_NAME "${PRIVATE_RUNNER_VM_NAME:-}"

echo "GitHub repository variables match the canonical foundry-private profile."
