#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-$ROOT_DIR/../deployment/profiles/foundry-private.env}"

source "$ROOT_DIR/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env select "$AZURE_ENV_NAME" --cwd "$FOUNDRY_DIR" --no-prompt
AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set MANAGE_PROJECT_CONNECTIONS false \
    --environment "$AZURE_ENV_NAME" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null

run_provision() {
  local log_file="$1"
  set +e
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd provision --cwd "$FOUNDRY_DIR" --no-prompt ${FOUNDRY_PROVISION_NO_STATE:+--no-state} \
      2>&1 | tee "$log_file"
  local status="${PIPESTATUS[0]}"
  set -e
  return "$status"
}

log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

if ! run_provision "$log_file"; then
  if ! grep -Fq "AccountProvisioningStateInvalid" "$log_file"; then
    exit 1
  fi

  foundry_account="$(
    az cognitiveservices account list \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --query "[?kind=='AIServices'].name | [0]" \
      --output tsv
  )"
  [[ -n "$foundry_account" ]] || {
    echo "Foundry account recovery failed: no AIServices account was found." >&2
    exit 1
  }

  for _ in {1..40}; do
    state="$(
      az cognitiveservices account show \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$foundry_account" \
        --query properties.provisioningState \
        --output tsv
    )"
    [[ "$state" == "Succeeded" ]] && break
    [[ "$state" == "Failed" ]] && {
      echo "Foundry account entered Failed provisioning state." >&2
      exit 1
    }
    sleep 15
  done
  [[ "${state:-}" == "Succeeded" ]] || {
    echo "Foundry account did not reach Succeeded before retry." >&2
    exit 1
  }

  : >"$log_file"
  run_provision "$log_file"
fi

FOUNDRY_POST_PROVISION_HYDRATE=1 \
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  "$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
