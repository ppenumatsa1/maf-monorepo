#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

get_azd_output() {
  azd env get-value "$1" --environment "$environment" 2>/dev/null
}

write_release_context \
  "$environment" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"

api_url="${API_URL:-$(get_azd_output API_URL)}"
web_url="${WEB_URL:-$(get_azd_output WEB_URL)}"

if [[ ! "$api_url" =~ ^https?:// || ! "$web_url" =~ ^https?:// ]]; then
  echo "Selected AZD environment does not contain valid API_URL and WEB_URL outputs." >&2
  exit 1
fi

release_api_url="${RELEASE_API_BASE_URL:-$web_url}"

SMOKE_EVIDENCE_FILE="$(release_artifact_path smoke.json)" \
RELEASE_ID="$RELEASE_ID" \
RELEASE_STARTED_AT="$RELEASE_STARTED_AT" \
infra/azure-apphosted/runtime/smoke-test.sh "$release_api_url" "$web_url"
