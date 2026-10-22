#!/usr/bin/env bash

_selected_target_script_path="${BASH_SOURCE[0]}"
_selected_target_script_dir="$(cd "${_selected_target_script_path%/*}" && pwd -P)"
_selected_target_project_dir="$(cd "$_selected_target_script_dir/../.." && pwd -P)"
_selected_target_repository_root="$(cd "$_selected_target_project_dir/../../.." && pwd -P)"
_selected_target_profile_input="${AZURE_HOSTED_PROFILE:-$_selected_target_project_dir/.azure/azure-hosted.env}"
_selected_target_profile_dir="${_selected_target_profile_input%/*}"
_selected_target_profile_name="${_selected_target_profile_input##*/}"
if [[ "$_selected_target_profile_dir" == "$_selected_target_profile_input" ]]; then
  _selected_target_profile_dir="."
fi
_selected_target_profile="$(
  cd "$_selected_target_profile_dir" 2>/dev/null &&
    printf '%s/%s' "$PWD" "$_selected_target_profile_name"
)" || {
  echo "AZURE_HOSTED_PROFILE parent directory is not readable." >&2
  return 1 2>/dev/null || exit 1
}
source "$_selected_target_project_dir/deployment/profile.sh"

[[ -f "$_selected_target_profile" && ! -L "$_selected_target_profile" ]] || {
  echo "AZURE_HOSTED_PROFILE must identify a readable regular non-symlink file." >&2
  return 1 2>/dev/null || exit 1
}

case "$_selected_target_profile" in
  "$_selected_target_repository_root"/*)
    _selected_target_relative="${_selected_target_profile#"$_selected_target_repository_root"/}"
    if git -C "$_selected_target_repository_root" ls-files --error-unmatch \
      -- "$_selected_target_relative" >/dev/null 2>&1; then
      echo "The selected Azure profile must not be tracked by git." >&2
      return 1 2>/dev/null || exit 1
    fi
    if ! git -C "$_selected_target_repository_root" check-ignore -q \
      -- "$_selected_target_relative"; then
      echo "An in-repository Azure profile must be covered by a git ignore rule." >&2
      return 1 2>/dev/null || exit 1
    fi
    ;;
esac

deployment_profile_load "$_selected_target_profile"
deployment_profile_validate
[[ "$(deployment_profile_value DEPLOYMENT_LANE)" == "azure-hosted" ]] || {
  echo "The selected profile is not the Azure-hosted lane." >&2
  return 1 2>/dev/null || exit 1
}

readonly APPROVED_PROFILE_PATH="$_selected_target_profile"
readonly APPROVED_AZURE_ENV_NAME="$(deployment_profile_value AZURE_ENV_NAME)"
readonly APPROVED_AZURE_TENANT_ID="$(deployment_profile_value AZURE_TENANT_ID)"
readonly APPROVED_AZURE_SUBSCRIPTION_ID="$(deployment_profile_value AZURE_SUBSCRIPTION_ID)"
readonly APPROVED_AZURE_RESOURCE_GROUP="$(deployment_profile_value AZURE_RESOURCE_GROUP)"
readonly APPROVED_AZURE_LOCATION="$(deployment_profile_value AZURE_LOCATION)"

require_selected_target() {
  local environment="$1"
  local subscription_id="$2"
  local resource_group="$3"
  local location="$4"

  [[ "$environment" == "$APPROVED_AZURE_ENV_NAME" ]] || {
    echo "Selected AZD environment does not match the external profile." >&2
    return 1
  }
  [[ "$subscription_id" == "$APPROVED_AZURE_SUBSCRIPTION_ID" ]] || {
    echo "Selected Azure subscription does not match the external profile." >&2
    return 1
  }
  [[ "$resource_group" == "$APPROVED_AZURE_RESOURCE_GROUP" ]] || {
    echo "Selected Azure resource group does not match the external profile." >&2
    return 1
  }
  [[ "$location" == "$APPROVED_AZURE_LOCATION" ]] || {
    echo "Selected Azure location does not match the external profile." >&2
    return 1
  }
}

require_azure_cli_target() {
  local subscription_id="$1"
  local resolved_subscription resolved_tenant subscription_state

  resolved_subscription="$(az account show \
    --subscription "$subscription_id" \
    --query id \
    --output tsv \
    --only-show-errors)"
  resolved_tenant="$(az account show \
    --subscription "$subscription_id" \
    --query tenantId \
    --output tsv \
    --only-show-errors)"
  subscription_state="$(az account show \
    --subscription "$subscription_id" \
    --query state \
    --output tsv \
    --only-show-errors)"
  [[ "$resolved_subscription" == "$APPROVED_AZURE_SUBSCRIPTION_ID" &&
    "$resolved_tenant" == "$APPROVED_AZURE_TENANT_ID" &&
    "$subscription_state" == "Enabled" ]] || {
    echo "Azure CLI cannot verify the tenant/subscription selected by the external profile." >&2
    return 1
  }
}
