#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"

for command_name in az python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

require_azure_cli_target "$APPROVED_AZURE_SUBSCRIPTION_ID"
deployment_profile_export
python3 "$ROOT_DIR/scripts/release/capacity_preflight.py" "$@"
