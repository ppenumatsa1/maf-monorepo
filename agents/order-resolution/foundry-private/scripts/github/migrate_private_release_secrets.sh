#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin azd
require_bin gh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
ORDER_RESOLUTION_DIR="$(cd "$ROOT_DIR/.." && pwd -P)"
source "$ROOT_DIR/scripts/foundry/private_profile.sh"
PROFILE_PATH="$(private_profile_resolve "$ROOT_DIR" "${DEPLOYMENT_PROFILE_PATH:-}")"
source "$ORDER_RESOLUTION_DIR/deployment/profile.sh"
deployment_profile_load "$PROFILE_PATH"
deployment_profile_validate
deployment_profile_export

SOURCE_AZD_ENVIRONMENT="$AZURE_ENV_NAME"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

cd "$FOUNDRY_DIR"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$SOURCE_AZD_ENVIRONMENT" --no-prompt

for secret_name in POSTGRES_ADMIN_PASSWORD; do
  secret_value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$secret_name")"
  [[ -n "$secret_value" ]] || {
    echo "Required source secret ${secret_name} is empty."
    exit 1
  }
  printf '%s' "$secret_value" | gh secret set "$secret_name" \
    --repo "$GITHUB_REPOSITORY"
done

echo "Migrated required private release secrets without displaying their values."
