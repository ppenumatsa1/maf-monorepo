#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <profile-path>\n' "$0" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
profile_path="$1"
azd_project_dir="${AZD_PROJECT_DIR:-$root_dir/infra/foundry-hosted}"
azd_command="${AZD_COMMAND:-azd}"
canonical_profile="$root_dir/deployment/profiles/foundry-public.env"
legacy_bootstrap_profile="$root_dir/deployment/profiles/foundry-public-bootstrap.env"

[[ -r "$profile_path" ]] || {
  printf 'Underwriting deployment profile error: profile is not readable: %s\n' "$profile_path" >&2
  exit 1
}
[[ -f "$azd_project_dir/azure.yaml" ]] || {
  printf 'Underwriting deployment profile error: AZD project is unavailable: %s\n' "$azd_project_dir" >&2
  exit 1
}
if [[ "$(realpath "$profile_path")" == "$(realpath "$legacy_bootstrap_profile")" ]]; then
  printf 'WARNING: foundry-public-bootstrap.env is legacy_pending_cutover; prefer %s\n' \
    "$canonical_profile" >&2
fi

declare -A values=()
allowed_keys=' CONTRACT_VERSION DEPLOYMENT_LANE AZURE_ENV_NAME AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION NAME_PREFIX POSTGRES_OPERATOR_IP '
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line="${raw_line%$'\r'}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" =~ ^([A-Z][A-Z0-9_]*)=([^[:cntrl:]]*)$ ]] || {
    printf 'Underwriting deployment profile error: invalid line: %s\n' "$raw_line" >&2
    exit 1
  }
  key="${BASH_REMATCH[1]}"
  value="${BASH_REMATCH[2]}"
  [[ "$allowed_keys" == *" $key "* ]] || {
    printf 'Underwriting deployment profile error: unsupported or secret-bearing key: %s\n' "$key" >&2
    exit 1
  }
  [[ -z "${values[$key]+x}" ]] || {
    printf 'Underwriting deployment profile error: duplicate key: %s\n' "$key" >&2
    exit 1
  }
  values["$key"]="$value"
done <"$profile_path"

required_keys=(
  CONTRACT_VERSION
  DEPLOYMENT_LANE
  AZURE_ENV_NAME
  AZURE_SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  NAME_PREFIX
)
for key in "${required_keys[@]}"; do
  [[ -n "${values[$key]:-}" ]] || {
    printf 'Underwriting deployment profile error: missing value: %s\n' "$key" >&2
    exit 1
  }
done

[[ "${values[CONTRACT_VERSION]}" == "1" ]] || {
  printf 'Underwriting deployment profile error: CONTRACT_VERSION must be 1\n' >&2
  exit 1
}
[[ "${values[DEPLOYMENT_LANE]}" == "foundry-public" ]] || {
  printf 'Underwriting deployment profile error: DEPLOYMENT_LANE must be foundry-public\n' >&2
  exit 1
}
[[ "${values[AZURE_SUBSCRIPTION_ID]}" == "7df95e88-701c-4693-af77-3159f83b558d" ]] || {
  printf 'Underwriting deployment profile error: non-canonical AZURE_SUBSCRIPTION_ID\n' >&2
  exit 1
}
[[ "${values[AZURE_RESOURCE_GROUP]}" == "rg-maf-underwriting" ]] || {
  printf 'Underwriting deployment profile error: non-canonical AZURE_RESOURCE_GROUP\n' >&2
  exit 1
}
[[ "${values[AZURE_LOCATION]}" == "eastus2" ]] || {
  printf 'Underwriting deployment profile error: non-canonical AZURE_LOCATION\n' >&2
  exit 1
}
[[ "${values[NAME_PREFIX]}" =~ ^[a-z0-9]{3,20}$ ]] || {
  printf 'Underwriting deployment profile error: NAME_PREFIX must be 3-20 lowercase alphanumeric characters\n' >&2
  exit 1
}
if [[ -n "${values[POSTGRES_OPERATOR_IP]:-}" &&
      ! "${values[POSTGRES_OPERATOR_IP]}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  printf 'Underwriting deployment profile error: POSTGRES_OPERATOR_IP must be an IPv4 address\n' >&2
  exit 1
fi

(
  cd "$azd_project_dir"
  "$azd_command" env select "${values[AZURE_ENV_NAME]}" --no-prompt
  for key in AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION NAME_PREFIX; do
    "$azd_command" env set "$key" "${values[$key]}" --no-prompt >/dev/null
  done
  if [[ -n "${values[POSTGRES_OPERATOR_IP]:-}" ]]; then
    "$azd_command" env set POSTGRES_OPERATOR_IP "${values[POSTGRES_OPERATOR_IP]}" --no-prompt >/dev/null
  fi
)

printf 'Applied canonical Underwriting AZD target profile: %s\n' "${values[AZURE_ENV_NAME]}"
