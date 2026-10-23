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
  INFRASTRUCTURE_MODE
  FOUNDRY_LOCATION
  FOUNDRY_ACCOUNT_NAME
  FOUNDRY_PROJECT_NAME
  FOUNDRY_CUSTOM_SUBDOMAIN_NAME
  HOSTED_AGENT_NAME
  FOUNDRY_RUNTIME_CONNECTION_NAME
  FOUNDRY_MODEL_DEPLOYMENT_NAME
  FOUNDRY_MODEL_FORMAT
  FOUNDRY_MODEL_NAME
  FOUNDRY_MODEL_VERSION
  FOUNDRY_MODEL_SKU_NAME
  FOUNDRY_MODEL_CAPACITY
  FOUNDRY_RAI_POLICY_NAME
  POSTGRES_SERVER_NAME
  POSTGRES_SERVER_LOCATION
  POSTGRES_SKU_NAME
  POSTGRES_SKU_TIER
  POSTGRES_VERSION
  POSTGRES_DATABASE
  POSTGRES_ADMIN_USERNAME
  POSTGRES_RUNTIME_USERNAME
  CONTAINER_REGISTRY_NAME
  CONTAINER_REGISTRY_SKU_NAME
  CONTAINER_APPS_ENVIRONMENT_NAME
  BACKEND_CONTAINER_APP_NAME
  FRONTEND_CONTAINER_APP_NAME
  PUBLIC_BACKEND_MANAGED_IDENTITY_NAME
  PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME
  APPLICATION_INSIGHTS_NAME
  LOG_ANALYTICS_WORKSPACE_NAME
  BACKEND_IMAGE_REPOSITORY
  FRONTEND_IMAGE_REPOSITORY
  HOSTED_AGENT_IMAGE_REPOSITORY
  EVALUATION_STORAGE_ACCOUNT_NAME
  BOT_SERVICE_NAME
  BOT_SERVICE_SKU_NAME
)

DEPLOYMENT_PROFILE_KEYS=(
  "${DEPLOYMENT_PROFILE_REQUIRED_KEYS[@]}"
  POSTGRES_OPERATOR_IP
)

declare -A DEPLOYMENT_PROFILE_VALUES=()

deployment_profile_error() {
  printf 'deployment profile error: %s\n' "$1" >&2
  return 1
}

deployment_profile_load() {
  local profile_path="$1"
  local line line_number key value seen_keys=" " environment_value

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
  done <"$profile_path"

  if [[ "${DEPLOYMENT_PROFILE_ALLOW_ENV_OVERRIDES:-false}" == "true" ]]; then
    for key in "${DEPLOYMENT_PROFILE_KEYS[@]}"; do
      environment_value="${!key-}"
      if [[ -n "$environment_value" ]]; then
        [[ "$environment_value" =~ ^[A-Za-z0-9._()/:-]+$ ]] || {
          deployment_profile_error "authenticated environment override is unsafe: $key"
          return 1
        }
        DEPLOYMENT_PROFILE_VALUES["$key"]="$environment_value"
      fi
    done
  fi
}

deployment_profile_validate() {
  local key

  for key in "${DEPLOYMENT_PROFILE_REQUIRED_KEYS[@]}"; do
    [[ -n "${DEPLOYMENT_PROFILE_VALUES[$key]-}" ]] || {
      deployment_profile_error "required key is missing: $key"
      return 1
    }
    [[ "${DEPLOYMENT_PROFILE_VALUES[$key]}" != replace-with-* &&
      "${DEPLOYMENT_PROFILE_VALUES[$key]}" != "REPLACE" ]] || {
      deployment_profile_error "placeholder value remains for $key"
      return 1
    }
  done

  [[ "${DEPLOYMENT_PROFILE_VALUES[CONTRACT_VERSION]}" == "1" ]] || {
    deployment_profile_error "unsupported CONTRACT_VERSION"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[DEPLOYMENT_LANE]}" == "foundry-public" ]] || {
    deployment_profile_error "DEPLOYMENT_LANE must be foundry-public"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[AZURE_ENV_NAME]}" =~ ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ ]] || {
    deployment_profile_error "AZURE_ENV_NAME is invalid"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[AZURE_SUBSCRIPTION_ID]}" =~ ^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$ ]] || {
    deployment_profile_error "AZURE_SUBSCRIPTION_ID must be a GUID"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[AZURE_RESOURCE_GROUP]}" =~ ^[A-Za-z0-9][A-Za-z0-9._()-]{0,89}$ ]] || {
    deployment_profile_error "AZURE_RESOURCE_GROUP is invalid"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[AZURE_LOCATION]}" =~ ^[a-z0-9]{2,32}$ ]] || {
    deployment_profile_error "AZURE_LOCATION is invalid"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[NAME_PREFIX]}" =~ ^[a-z0-9]{3,20}$ ]] || {
    deployment_profile_error "NAME_PREFIX must be 3-20 lowercase alphanumeric characters"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[AZURE_SUBSCRIPTION_ID]}" != "00000000-0000-0000-0000-000000000000" ]] || {
    deployment_profile_error "AZURE_SUBSCRIPTION_ID must select a real external target"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[INFRASTRUCTURE_MODE]}" == "reuse" ||
    "${DEPLOYMENT_PROFILE_VALUES[INFRASTRUCTURE_MODE]}" == "bootstrap" ]] || {
    deployment_profile_error "INFRASTRUCTURE_MODE must be reuse or bootstrap"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[FOUNDRY_LOCATION]}" == "${DEPLOYMENT_PROFILE_VALUES[AZURE_LOCATION]}" &&
    "${DEPLOYMENT_PROFILE_VALUES[POSTGRES_SERVER_LOCATION]}" == "${DEPLOYMENT_PROFILE_VALUES[AZURE_LOCATION]}" ]] || {
    deployment_profile_error "public deployment requires one region for Foundry, Container Apps, PostgreSQL, ACR, and monitoring"
    return 1
  }
  for key in FOUNDRY_MODEL_CAPACITY; do
    [[ "${DEPLOYMENT_PROFILE_VALUES[$key]}" =~ ^[1-9][0-9]*$ ]] || {
      deployment_profile_error "$key must be a positive integer"
      return 1
    }
  done
  for key in FOUNDRY_MODEL_SKU_NAME; do
    [[ "${DEPLOYMENT_PROFILE_VALUES[$key]}" =~ ^(Standard|DataZoneStandard|GlobalStandard)$ ]] || {
      deployment_profile_error "$key is not a supported model deployment SKU"
      return 1
    }
  done
  [[ "${DEPLOYMENT_PROFILE_VALUES[CONTAINER_REGISTRY_SKU_NAME]}" =~ ^(Basic|Standard|Premium)$ ]] || {
    deployment_profile_error "CONTAINER_REGISTRY_SKU_NAME is invalid"
    return 1
  }
  [[ "${DEPLOYMENT_PROFILE_VALUES[BOT_SERVICE_SKU_NAME]}" =~ ^(F0|S1)$ ]] || {
    deployment_profile_error "BOT_SERVICE_SKU_NAME is invalid"
    return 1
  }
  if [[ -n "${DEPLOYMENT_PROFILE_VALUES[POSTGRES_OPERATOR_IP]-}" &&
        ! "${DEPLOYMENT_PROFILE_VALUES[POSTGRES_OPERATOR_IP]}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    deployment_profile_error "POSTGRES_OPERATOR_IP must be an IPv4 address"
    return 1
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
