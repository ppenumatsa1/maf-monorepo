#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

write_release_context \
  "${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"
normalize_release_artifacts

echo "Prepared release context: $RELEASE_CONTEXT_FILE"
