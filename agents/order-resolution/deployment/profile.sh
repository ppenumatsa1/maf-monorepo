#!/usr/bin/env bash
set -euo pipefail

# Deployment profiles are parsed as data, never sourced.

DEPLOYMENT_PROFILE_REQUIRED_KEYS=(
  CONTRACT_VERSION
  DEPLOYMENT_LANE
  AZURE_ENV_NAME
  AZURE_SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  NAME_PREFIX
)

DEPLOYMENT_PROFILE_KEYS=(
  "${DEPLOYMENT_PROFILE_REQUIRED_KEYS[@]}"
  AZURE_TENANT_ID
  AZD_ENVIRONMENT_NAME
  PRIVATE_RUNNER_LABEL
  PRIVATE_RUNNER_VM_NAME
  FOUNDRY_LOCATION
  AI_SEARCH_LOCATION
  COSMOS_LOCATION
  POSTGRES_LOCATION
  FOUNDRY_PROJECT_NAME
  HOSTED_AGENT_NAME
  POSTGRES_DATABASE_NAME
  POSTGRES_ADMIN_USERNAME
  VNET_ADDRESS_PREFIX
  AGENT_SUBNET_PREFIX
  PRIVATE_ENDPOINT_SUBNET_PREFIX
  RUNNER_SUBNET_PREFIX
  BASTION_SUBNET_PREFIX
  CONTAINER_APPS_SUBNET_PREFIX
  NETWORK_MODE
  DEPLOYMENT_MODE
  CREATE_PRIVATE_DNS_VNET_LINKS
  CREATE_PRIVATE_ENDPOINTS
  ENABLE_CONTAINER_APPS
  ENABLE_POSTGRES_PRIVATE_ENDPOINT
  CREATE_NAT_GATEWAY
  CREATE_PRIVATE_RUNNER_ACCESS
  ASSIGN_RUNNER_RESOURCE_GROUP_RBAC
  ASSIGN_RUNNER_USER_ACCESS_ADMINISTRATOR
  CREATE_BASTION_HOST
  CREATE_RUNNER_VM
  ENABLE_STANDARD_AGENT_NETWORK_INJECTION
  ASSIGN_PRE_CAPHOST_RBAC
  ASSIGN_POST_CAPHOST_RBAC
  CREATE_ACCOUNT_CAPABILITY_HOST
  CREATE_PROJECT_CAPABILITY_HOST
  MANAGE_PROJECT_CONNECTIONS
  CREATE_POSTGRES_SERVER
  RESTORE_FOUNDRY_ACCOUNT
  RUNNER_VM_SIZE
  RUNNER_VM_ADMIN_USERNAME
  FOUNDRY_MODEL_DEPLOYMENT_NAME
  FOUNDRY_CHAT_MODEL_FORMAT
  FOUNDRY_CHAT_MODEL_NAME
  FOUNDRY_CHAT_MODEL_VERSION
  FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME
  FOUNDRY_CHAT_DEPLOYMENT_CAPACITY
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME
  FOUNDRY_EMBEDDINGS_MODEL_FORMAT
  FOUNDRY_EMBEDDINGS_MODEL_NAME
  FOUNDRY_EMBEDDINGS_MODEL_VERSION
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY
  FOUNDRY_RAI_POLICY_NAME
  AI_SEARCH_SKU_NAME
  POSTGRES_SKU_NAME
  POSTGRES_SKU_TIER
  POSTGRES_VERSION
  POSTGRES_STORAGE_SIZE_GB
  POSTGRES_BACKUP_RETENTION_DAYS
)

declare -A DEPLOYMENT_PROFILE_VALUES=()

deployment_profile_error() {
  printf 'deployment profile error: %s\n' "$1" >&2
  return 1
}

deployment_profile_value() {
  local key="$1"

  [[ -v "DEPLOYMENT_PROFILE_VALUES[$key]" ]] || return 1
  printf '%s' "${DEPLOYMENT_PROFILE_VALUES[$key]}"
}

deployment_profile_load() {
  local profile_path="$1"
  local line line_number key value seen_keys=" "

  [[ -f "$profile_path" && ! -L "$profile_path" && -r "$profile_path" ]] || {
    deployment_profile_error "profile must be a readable regular file"
    return 1
  }

  DEPLOYMENT_PROFILE_VALUES=()
  line_number=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$((line_number + 1))
    case "$line" in
      ""|\#*) continue ;;
    esac

    [[ "$line" == *=* ]] || {
      deployment_profile_error "line $line_number must use KEY=VALUE syntax"
      return 1
    }
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ && -n "$value" && "$line" == "$key=$value" ]] || {
      deployment_profile_error "line $line_number is not an approved declaration"
      return 1
    }
    [[ "$value" =~ ^[A-Za-z0-9._()/:-]+$ ]] || {
      deployment_profile_error "line $line_number has an unsafe value"
      return 1
    }
    [[ " ${DEPLOYMENT_PROFILE_KEYS[*]} " == *" $key "* ]] || {
      deployment_profile_error "line $line_number has an unsupported key"
      return 1
    }
    [[ "$seen_keys" != *" $key "* ]] || {
      deployment_profile_error "line $line_number declares $key more than once"
      return 1
    }

    DEPLOYMENT_PROFILE_VALUES["$key"]="$value"
    seen_keys+="$key "
  done < "$profile_path"
}

deployment_profile_validate() {
  local key lane

  for key in "${DEPLOYMENT_PROFILE_REQUIRED_KEYS[@]}"; do
    [[ -n "${DEPLOYMENT_PROFILE_VALUES[$key]-}" ]] || {
      deployment_profile_error "required key is missing: $key"
      return 1
    }
  done

  [[ "$(deployment_profile_value CONTRACT_VERSION)" == "1" ]] || {
    deployment_profile_error "unsupported CONTRACT_VERSION"
    return 1
  }
  lane="$(deployment_profile_value DEPLOYMENT_LANE)"
  [[ "$lane" == "azure-hosted" || "$lane" == "foundry-public" || "$lane" == "foundry-private" ]] || {
    deployment_profile_error "DEPLOYMENT_LANE is invalid"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_ENV_NAME)" =~ ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ ]] || {
    deployment_profile_error "AZURE_ENV_NAME is invalid"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_SUBSCRIPTION_ID)" =~ ^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$ ]] || {
    deployment_profile_error "AZURE_SUBSCRIPTION_ID must be a GUID"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_RESOURCE_GROUP)" =~ ^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$ ]] || {
    deployment_profile_error "AZURE_RESOURCE_GROUP is invalid"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_LOCATION)" =~ ^[a-z0-9]{2,32}$ ]] || {
    deployment_profile_error "AZURE_LOCATION is invalid"
    return 1
  }
  [[ "$(deployment_profile_value NAME_PREFIX)" =~ ^[a-z][a-z0-9]{2,14}$ ]] || {
    deployment_profile_error "NAME_PREFIX must be 3-15 lowercase alphanumeric characters"
    return 1
  }
  if [[ "$lane" == "foundry-private" ]]; then
    local private_key
    local -a private_required_keys=(
      AZURE_TENANT_ID AZD_ENVIRONMENT_NAME PRIVATE_RUNNER_LABEL
      PRIVATE_RUNNER_VM_NAME FOUNDRY_LOCATION AI_SEARCH_LOCATION
      COSMOS_LOCATION POSTGRES_LOCATION FOUNDRY_PROJECT_NAME HOSTED_AGENT_NAME
      POSTGRES_DATABASE_NAME POSTGRES_ADMIN_USERNAME VNET_ADDRESS_PREFIX
      AGENT_SUBNET_PREFIX PRIVATE_ENDPOINT_SUBNET_PREFIX RUNNER_SUBNET_PREFIX
      BASTION_SUBNET_PREFIX CONTAINER_APPS_SUBNET_PREFIX NETWORK_MODE
      DEPLOYMENT_MODE CREATE_PRIVATE_DNS_VNET_LINKS CREATE_PRIVATE_ENDPOINTS
      ENABLE_CONTAINER_APPS ENABLE_POSTGRES_PRIVATE_ENDPOINT
      CREATE_NAT_GATEWAY CREATE_PRIVATE_RUNNER_ACCESS
      ASSIGN_RUNNER_RESOURCE_GROUP_RBAC
      ASSIGN_RUNNER_USER_ACCESS_ADMINISTRATOR CREATE_BASTION_HOST
      CREATE_RUNNER_VM ENABLE_STANDARD_AGENT_NETWORK_INJECTION
      ASSIGN_PRE_CAPHOST_RBAC ASSIGN_POST_CAPHOST_RBAC
      CREATE_ACCOUNT_CAPABILITY_HOST CREATE_PROJECT_CAPABILITY_HOST
      MANAGE_PROJECT_CONNECTIONS CREATE_POSTGRES_SERVER RESTORE_FOUNDRY_ACCOUNT
      RUNNER_VM_SIZE RUNNER_VM_ADMIN_USERNAME FOUNDRY_MODEL_DEPLOYMENT_NAME
      FOUNDRY_CHAT_MODEL_FORMAT FOUNDRY_CHAT_MODEL_NAME
      FOUNDRY_CHAT_MODEL_VERSION FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME
      FOUNDRY_CHAT_DEPLOYMENT_CAPACITY FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME
      FOUNDRY_EMBEDDINGS_MODEL_FORMAT FOUNDRY_EMBEDDINGS_MODEL_NAME
      FOUNDRY_EMBEDDINGS_MODEL_VERSION
      FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME
      FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY FOUNDRY_RAI_POLICY_NAME
      AI_SEARCH_SKU_NAME POSTGRES_SKU_NAME POSTGRES_SKU_TIER POSTGRES_VERSION
      POSTGRES_STORAGE_SIZE_GB POSTGRES_BACKUP_RETENTION_DAYS
    )
    for private_key in "${private_required_keys[@]}"; do
      [[ -n "${DEPLOYMENT_PROFILE_VALUES[$private_key]-}" ]] || {
        deployment_profile_error "required foundry-private key is missing: $private_key"
        return 1
      }
    done
    [[ "$(deployment_profile_value AZD_ENVIRONMENT_NAME)" == "$(deployment_profile_value AZURE_ENV_NAME)" ]] || {
      deployment_profile_error "AZD_ENVIRONMENT_NAME must match AZURE_ENV_NAME"
      return 1
    }
  fi
}

deployment_profile_export() {
  local key

  for key in "${!DEPLOYMENT_PROFILE_VALUES[@]}"; do
    export "$key=${DEPLOYMENT_PROFILE_VALUES[$key]}"
  done
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  [[ $# -eq 2 && "$1" == "validate" ]] || {
    printf 'Usage: %s validate <profile-path>\n' "$0" >&2
    exit 2
  }
  deployment_profile_load "$2"
  deployment_profile_validate
fi
