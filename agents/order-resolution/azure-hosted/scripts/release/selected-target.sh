#!/usr/bin/env bash

_selected_target_script_path="${BASH_SOURCE[0]}"
_selected_target_script_dir="$(cd "${_selected_target_script_path%/*}" && pwd -P)"
_selected_target_project_dir="$(cd "$_selected_target_script_dir/../.." && pwd -P)"
_selected_target_order_resolution_dir="$(cd "$_selected_target_project_dir/.." && pwd -P)"
_selected_target_profile="$_selected_target_order_resolution_dir/deployment/profiles/azure-hosted.env"
source "$_selected_target_order_resolution_dir/deployment/profile.sh"
deployment_profile_load "$_selected_target_profile"
deployment_profile_validate
[[ "$(deployment_profile_value DEPLOYMENT_LANE)" == "azure-hosted" ]] || {
  echo "Canonical profile is not the Azure-hosted lane." >&2
  return 1 2>/dev/null || exit 1
}

readonly APPROVED_AZURE_ENV_NAME="$(deployment_profile_value AZURE_ENV_NAME)"
readonly APPROVED_AZURE_SUBSCRIPTION_ID="$(deployment_profile_value AZURE_SUBSCRIPTION_ID)"
readonly APPROVED_AZURE_RESOURCE_GROUP="$(deployment_profile_value AZURE_RESOURCE_GROUP)"
readonly APPROVED_AZURE_LOCATION="$(deployment_profile_value AZURE_LOCATION)"

require_selected_target() {
  local environment="$1"
  local subscription_id="$2"
  local resource_group="$3"
  local location="$4"

  [[ "$environment" == "$APPROVED_AZURE_ENV_NAME" ]] || {
    echo "Selected AZD environment must be $APPROVED_AZURE_ENV_NAME." >&2
    return 1
  }
  [[ "$subscription_id" == "$APPROVED_AZURE_SUBSCRIPTION_ID" ]] || {
    echo "Selected Azure subscription must be $APPROVED_AZURE_SUBSCRIPTION_ID." >&2
    return 1
  }
  [[ "$resource_group" == "$APPROVED_AZURE_RESOURCE_GROUP" ]] || {
    echo "Selected Azure resource group must be $APPROVED_AZURE_RESOURCE_GROUP." >&2
    return 1
  }
  [[ "$location" == "$APPROVED_AZURE_LOCATION" ]] || {
    echo "Selected Azure location must be $APPROVED_AZURE_LOCATION." >&2
    return 1
  }
}

require_azure_cli_target() {
  local subscription_id="$1"
  local resolved_subscription

  resolved_subscription="$(az account show \
    --subscription "$subscription_id" \
    --query id \
    --output tsv)"
  [[ "$resolved_subscription" == "$APPROVED_AZURE_SUBSCRIPTION_ID" ]] || {
    echo "Azure CLI cannot resolve the approved subscription." >&2
    return 1
  }
}
