#!/usr/bin/env bash
set -euo pipefail

# Profiles are parsed as data and are never sourced.
readonly DEPLOYMENT_PROFILE_KEYS=(
  CONTRACT_VERSION
  DEPLOYMENT_LANE
  AZURE_ENV_NAME
  AZURE_SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  NAME_PREFIX
  POSTGRES_DATABASE_NAME
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
    [[ "$value" =~ ^[A-Za-z0-9._()/-]+$ ]] || {
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
}

deployment_profile_validate() {
  local key
  for key in \
    CONTRACT_VERSION DEPLOYMENT_LANE AZURE_ENV_NAME AZURE_SUBSCRIPTION_ID \
    AZURE_RESOURCE_GROUP AZURE_LOCATION NAME_PREFIX POSTGRES_DATABASE_NAME
  do
    [[ -n "${DEPLOYMENT_PROFILE_VALUES[$key]-}" ]] || {
      deployment_profile_error "required key is missing: $key"
      return 1
    }
  done

  [[ "$(deployment_profile_value CONTRACT_VERSION)" == "1" ]] || {
    deployment_profile_error "unsupported CONTRACT_VERSION"
    return 1
  }
  [[ "$(deployment_profile_value DEPLOYMENT_LANE)" == "azure-hosted" ]] || {
    deployment_profile_error "DEPLOYMENT_LANE must be azure-hosted"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_ENV_NAME)" =~ ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ ]] || {
    deployment_profile_error "AZURE_ENV_NAME is invalid"
    return 1
  }
  [[ "$(deployment_profile_value AZURE_SUBSCRIPTION_ID)" =~ ^[0-9A-Fa-f-]{36}$ ]] || {
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
  [[ "$(deployment_profile_value NAME_PREFIX)" =~ ^[a-z][a-z0-9-]{1,13}[a-z0-9]$ ]] || {
    deployment_profile_error "NAME_PREFIX must be 3-15 lowercase alphanumeric/hyphen characters"
    return 1
  }
  [[ "$(deployment_profile_value POSTGRES_DATABASE_NAME)" =~ ^[A-Za-z0-9_-]+$ ]] || {
    deployment_profile_error "POSTGRES_DATABASE_NAME is invalid"
    return 1
  }
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  [[ $# -eq 2 && "$1" == "validate" ]] || {
    printf 'Usage: %s validate <profile-path>\n' "$0" >&2
    exit 2
  }
  deployment_profile_load "$2"
  deployment_profile_validate
fi
