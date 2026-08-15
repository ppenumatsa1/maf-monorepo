#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

write_release_context \
  "${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"

source_validation_log="$RELEASE_LOGS_DIR/source-validation.log"
bicep_build_log="$RELEASE_LOGS_DIR/bicep-build.log"
source_validation_file="$(release_artifact_path source-validation.json)"

make --no-print-directory release-source-validation >"$source_validation_log" 2>&1 &
source_validation_pid=$!
make --no-print-directory bicep-build >"$bicep_build_log" 2>&1 &
bicep_build_pid=$!

source_validation_status="passed"
bicep_build_status="passed"
overall_status="passed"

wait "$source_validation_pid" || {
  source_validation_status="failed"
  overall_status="failed"
}
wait "$bicep_build_pid" || {
  bicep_build_status="failed"
  overall_status="failed"
}

python3 - "$source_validation_file" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION" \
  "$overall_status" \
  "$source_validation_status" \
  "logs/$(basename "$source_validation_log")" \
  "$bicep_build_status" \
  "logs/$(basename "$bicep_build_log")" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    output_path,
    release_id,
    release_started_at,
    environment,
    subscription_id,
    resource_group,
    location,
    overall_status,
    source_validation_status,
    source_validation_log,
    bicep_build_status,
    bicep_build_log,
) = sys.argv[1:]

payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "artifact_type": "source_validation",
    "status": overall_status,
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    "target": {
        "azd_env_name": environment,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
    },
    "checks": [
        {
            "name": "release-source-validation",
            "status": source_validation_status,
            "log": source_validation_log,
        },
        {
            "name": "bicep-build",
            "status": bicep_build_status,
            "log": bicep_build_log,
        },
    ],
}

Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

[[ "$overall_status" == "passed" ]]
