#!/usr/bin/env bash
set -euo pipefail
umask 077

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

web_url="${PLAYWRIGHT_BASE_URL:-${WEB_URL:-$(get_azd_output WEB_URL)}}"
[[ "$web_url" =~ ^https?:// ]] || {
  echo "Selected AZD environment does not contain a valid WEB_URL output." >&2
  exit 1
}

browser_log="$RELEASE_LOGS_DIR/browser-e2e.log"
PLAYWRIGHT_BASE_URL="$web_url" \
PLAYWRIGHT_ARTIFACTS_DIR="$RELEASE_LOGS_DIR/playwright" \
make --no-print-directory test-e2e >"$browser_log" 2>&1

echo "Hosted browser E2E completed: $browser_log"
