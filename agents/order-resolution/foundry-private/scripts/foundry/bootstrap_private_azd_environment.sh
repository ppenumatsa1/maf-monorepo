#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin azd
require_bin python3

: "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD is required}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
PROFILE_FILE="${DEPLOYMENT_PROFILE_FILE:-${ROOT_DIR}/../deployment/profiles/foundry-private.env}"
PROFILE_LOADER="${ROOT_DIR}/../deployment/profile.sh"

source "$PROFILE_LOADER"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

cd "$FOUNDRY_DIR"
if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZURE_ENV_NAME" --no-prompt >/dev/null 2>&1; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env new "$AZURE_ENV_NAME" \
    --location "$AZURE_LOCATION" \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --no-prompt
fi

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  AZURE_SUBSCRIPTION_ID="$AZURE_SUBSCRIPTION_ID" \
  AZURE_LOCATION="$AZURE_LOCATION" \
  AZURE_RESOURCE_GROUP="$AZURE_RESOURCE_GROUP" \
  NAME_PREFIX="$NAME_PREFIX" \
  NETWORK_MODE=private \
  FOUNDRY_LOCATION="$AZURE_LOCATION" \
  FOUNDRY_PROJECT_NAME="$FOUNDRY_PROJECT_NAME" \
  POSTGRES_DATABASE_NAME="$POSTGRES_DATABASE_NAME" \
  POSTGRES_LOCATION="$POSTGRES_LOCATION" \
  POSTGRES_ADMIN_USERNAME="$POSTGRES_ADMIN_USERNAME" \
  POSTGRES_ADMIN_PASSWORD="$POSTGRES_ADMIN_PASSWORD" \
  CREATE_POSTGRES_SERVER=true \
  ENABLE_CONTAINER_APPS=true \
  ENABLE_POSTGRES_PRIVATE_ENDPOINT=true \
  MANAGE_PROJECT_CONNECTIONS=false

echo "Bootstrapped private AZD parameters; provisioned Foundry outputs remain unset until hydration."
