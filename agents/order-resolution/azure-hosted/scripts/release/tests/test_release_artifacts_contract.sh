#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
cd "$ROOT_DIR"
unset RELEASE_ARTIFACTS_ROOT RELEASE_ARTIFACTS_DIR RELEASE_EVIDENCE_DIR
unset RELEASE_LOGS_DIR RELEASE_CONTEXT_FILE
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

release_id="test-release-artifacts-$$"
release_started_at="2026-08-15T00:00:00Z"
canonical_dir="$ROOT_DIR/.artifacts/releases/$release_id"
profile_dir="$ROOT_DIR/.artifacts/release-profile-test-$$"
export AZURE_HOSTED_PROFILE="$profile_dir/azure-hosted.env"
mkdir -p "$profile_dir"
sed \
  -e 's/^AZURE_ENV_NAME=.*/AZURE_ENV_NAME=portable-azure-hosted/' \
  -e '0,/00000000-0000-0000-0000-000000000000/s//22222222-2222-4222-8222-222222222222/' \
  -e '0,/00000000-0000-0000-0000-000000000000/s//11111111-1111-4111-8111-111111111111/' \
  -e 's/^AZURE_RESOURCE_GROUP=.*/AZURE_RESOURCE_GROUP=rg-portable-azure/' \
  -e 's/^AZURE_LOCATION=.*/AZURE_LOCATION=regionone/' \
  -e 's/^NAME_PREFIX=.*/NAME_PREFIX=portableazure/' \
  "$ROOT_DIR/../deployment/profiles/azure-hosted.env.example" \
  >"$AZURE_HOSTED_PROFILE"
trap 'rm -rf "$canonical_dir" "$profile_dir"' EXIT

export RELEASE_RUN_ID="$release_id"
export RELEASE_ID="$release_id"
export RELEASE_STARTED_AT="$release_started_at"
export RELEASE_E2E_STARTED_AT="$release_started_at"
export RELEASE_SECRET_SHOULD_NOT_APPEAR="super-secret-value"

write_release_context "portable-azure-hosted" "11111111-1111-4111-8111-111111111111" "rg-portable-azure" "regionone"
normalize_release_artifacts

context_file="$(release_artifact_path release-context.json)"
[[ "$context_file" == "$canonical_dir/evidence/release-context.json" ]]
[[ -d "$canonical_dir/logs" ]]
[[ -f "$canonical_dir/release.json" ]]

python3 - "$context_file" "$ROOT_DIR/deployment/contracts/azure-hosted-release-artifact-envelope.schema.json" <<'PY'
import json
import sys
from jsonschema import Draft202012Validator

context_path, schema_path = sys.argv[1:]
payload = json.load(open(context_path, encoding="utf-8"))
schema = json.load(open(schema_path, encoding="utf-8"))
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema).validate(payload)
assert payload["evidence_type"] == "release-context"
assert payload["artifact_type"] == "release_context"
assert payload["checks"][0]["name"] == "target-selection"
assert payload["artifact_files"]["browser_e2e_log"] == "logs/browser-e2e.log"
assert payload["extensions"]["canonical_artifacts_root"] == ".artifacts/releases"
assert payload["extensions"]["release_authority"] == "prepared_not_live_validated"
assert payload["phases"].index("release-telemetry") < payload["phases"].index("release-eval")
PY

if grep -Fq "super-secret-value" "$context_file"; then
  echo "Release context leaked unrelated secret-like environment data." >&2
  exit 1
fi

deployment_file="$(release_artifact_path deployment.json)"
cat >"$deployment_file" <<'EOF'
{
  "artifact_type": "deployment",
  "status": "passed",
  "release_id": "placeholder",
  "release_started_at": "placeholder",
  "generated_at": "2026-08-15T00:00:01Z",
  "target": {
    "azd_env_name": "maf-ora-azure",
    "subscription_id": "11111111-1111-4111-8111-111111111111",
    "resource_group": "rg-portable-azure",
    "location": "regionone"
  },
  "api_url": "https://example.test",
  "web_url": "https://example-web.test"
}
EOF

normalize_release_artifacts

python3 - "$deployment_file" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload["evidence_type"] == "deployment"
assert payload["artifact_type"] == "deployment"
assert payload["release_id"].startswith("test-release-artifacts-")
assert payload["release_started_at"] == "2026-08-15T00:00:00Z"
assert payload["checks"] == []
assert payload["extensions"]["canonical_file"] == "deployment.json"
PY

target_json="$(release_target_json "portable-azure-hosted" "11111111-1111-4111-8111-111111111111" "rg-portable-azure" "regionone")"
if release_write_artifact "forbidden.json" "smoke" "passed" "$target_json" "[]" '{"secret":"nope"}' '{}'; then
  echo "release_write_artifact accepted a forbidden secret-like key." >&2
  exit 1
fi

release_write_artifact \
  "token-metrics.json" \
  "evaluation" \
  "passed" \
  "$target_json" \
  "[]" \
  '{}' \
  '{"usage":{"prompt_tokens":120,"completion_tokens":30,"total_tokens":150}}'

if release_write_artifact \
  "credential-token.json" \
  "evaluation" \
  "passed" \
  "$target_json" \
  "[]" \
  '{}' \
  '{"refresh_token":"not-allowed"}'
then
  echo "release_write_artifact accepted a credential-bearing token field." >&2
  exit 1
fi

echo "Release artifact contract tests passed."
