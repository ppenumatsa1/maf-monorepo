#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <profile-path>\n' "$0" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repository_root="$(cd "$script_dir/../../.." && pwd -P)"
source "$script_dir/profile.sh"

deployment_profile_load "$1"
deployment_profile_validate
deployment_profile_export

case "$DEPLOYMENT_LANE" in
  azure-hosted) project_dir="$repository_root/agents/order-resolution/azure-hosted" ;;
  foundry-public) project_dir="$repository_root/agents/order-resolution/foundry-public/infra/foundry-hosted" ;;
  foundry-private) project_dir="$repository_root/agents/order-resolution/foundry-private/infra/foundry-hosted" ;;
esac

if [[ -n "${AZD_PROJECT_DIR:-}" ]]; then
  project_dir="$(cd "$AZD_PROJECT_DIR" && pwd -P)"
  [[ "$project_dir" == "$repository_root/"* ]] || {
    printf 'deployment profile error: AZD_PROJECT_DIR must be inside the repository\n' >&2
    exit 1
  }
fi

[[ -f "$project_dir/azure.yaml" ]] || {
  printf 'deployment profile error: no azure.yaml for %s\n' "$DEPLOYMENT_LANE" >&2
  exit 1
}

azd_command="${AZD_COMMAND:-azd}"
command -v "$azd_command" >/dev/null 2>&1 || {
  printf 'deployment profile error: azd is required\n' >&2
  exit 1
}

(
  cd "$project_dir"
  if [[ -f ".azure/$AZURE_ENV_NAME/.env" ]]; then
    "$azd_command" env select "$AZURE_ENV_NAME"
  else
    "$azd_command" env new "$AZURE_ENV_NAME" --no-prompt
  fi

  "$azd_command" env set AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
  "$azd_command" env set AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
  "$azd_command" env set AZURE_LOCATION "$AZURE_LOCATION"
  "$azd_command" env set NAME_PREFIX "$NAME_PREFIX"
)

printf 'Applied %s target profile to %s.\n' "$DEPLOYMENT_LANE" "$AZURE_ENV_NAME"
