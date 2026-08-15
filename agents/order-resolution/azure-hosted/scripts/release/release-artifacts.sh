#!/usr/bin/env bash

release_now_iso() {
  python3 - <<'PY'
from datetime import UTC, datetime

print(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
PY
}

release_record_timing() {
  local event="$1"
  local stage="${2-}"
  local status="${3-}"
  local arguments=(
    python3 "$ROOT_DIR/scripts/release/release-record.py" timing
    --release-dir "$RELEASE_ARTIFACTS_DIR"
    --event "$event"
    --at "$(release_now_iso)"
  )
  [[ -z "$stage" ]] || arguments+=(--stage "$stage")
  [[ -z "$status" ]] || arguments+=(--status "$status")
  "${arguments[@]}"
}

release_timing_value() {
  local expression="$1"
  python3 - "$RELEASE_ARTIFACTS_DIR/release.json" "$expression" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload["extensions"]["azure"]
for part in sys.argv[2].split("."):
    value = value[part]
print("null" if value is None else value)
PY
}

release_default_id() {
  python3 - <<'PY'
from datetime import UTC, datetime
import os

print(datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}")
PY
}

release_validate_release_id() {
  local value="$1"
  local name="${2:-RELEASE_ID}"

  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]] || {
    echo "$name must be 3-128 safe release-id characters." >&2
    return 1
  }
}

release_normalize_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).resolve(strict=False))
PY
}

release_assert_expected_path() {
  local name="$1"
  local candidate="$2"
  local expected="$3"

  [[ -n "$candidate" ]] || return 0

  local normalized_candidate normalized_expected
  normalized_candidate="$(release_normalize_path "$candidate")"
  normalized_expected="$(release_normalize_path "$expected")"
  [[ "$normalized_candidate" == "$normalized_expected" ]] || {
    echo "$name must resolve to $expected." >&2
    return 1
  }
}

release_validate_relative_path() {
  python3 - "$1" <<'PY'
from pathlib import PurePosixPath
import sys

value = sys.argv[1]
path = PurePosixPath(value)
if not value or path.is_absolute() or ".." in path.parts:
    raise SystemExit(1)
PY
}

release_evidence_type_for_name() {
  local name="${1##*/}"
  case "$name" in
    release-context.json) echo "release-context" ;;
    source-validation.json) echo "source-validation" ;;
    infrastructure.json) echo "infrastructure" ;;
    images.json) echo "images" ;;
    deployment.json) echo "deployment" ;;
    smoke.json) echo "smoke" ;;
    domain-e2e.json) echo "domain-e2e" ;;
    evaluation.json) echo "evaluation" ;;
    telemetry.json) echo "telemetry" ;;
    release-evidence.json) echo "release-evidence" ;;
    *) echo "${name%.json}" ;;
  esac
}

release_legacy_artifact_type() {
  echo "${1//-/_}"
}

release_init_context() {
  local requested_artifacts_dir="${RELEASE_ARTIFACTS_DIR:-}"
  local requested_logs_dir="${RELEASE_LOGS_DIR:-}"
  local requested_context_file="${RELEASE_CONTEXT_FILE:-}"

  RELEASE_ID="${RELEASE_ID:-${RELEASE_RUN_ID:-$(release_default_id)}}"
  release_validate_release_id "$RELEASE_ID" "RELEASE_ID"

  RELEASE_ARTIFACTS_ROOT="$ROOT_DIR/.artifacts/releases"
  RELEASE_ARTIFACTS_DIR="$RELEASE_ARTIFACTS_ROOT/$RELEASE_ID"
  RELEASE_EVIDENCE_DIR="$RELEASE_ARTIFACTS_DIR/evidence"
  RELEASE_LOGS_DIR="$RELEASE_ARTIFACTS_DIR/logs"
  RELEASE_CONTEXT_FILE="$RELEASE_EVIDENCE_DIR/release-context.json"

  release_assert_expected_path "RELEASE_ARTIFACTS_DIR" "$requested_artifacts_dir" "$RELEASE_ARTIFACTS_DIR"
  release_assert_expected_path "RELEASE_LOGS_DIR" "$requested_logs_dir" "$RELEASE_LOGS_DIR"
  release_assert_expected_path "RELEASE_CONTEXT_FILE" "$requested_context_file" "$RELEASE_CONTEXT_FILE"

  if [[ -z "${RELEASE_STARTED_AT:-}" && -z "${RELEASE_E2E_STARTED_AT:-}" ]]; then
    local known_context=""
    if [[ -f "$RELEASE_CONTEXT_FILE" ]]; then
      known_context="$RELEASE_CONTEXT_FILE"
    fi
    if [[ -n "$known_context" ]]; then
      RELEASE_STARTED_AT="$(python3 - "$known_context" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload.get("release_started_at", ""))
PY
)"
    fi
  fi

  RELEASE_STARTED_AT="${RELEASE_STARTED_AT:-${RELEASE_E2E_STARTED_AT:-$(release_now_iso)}}"

  export RELEASE_ID RELEASE_RUN_ID="$RELEASE_ID"
  export RELEASE_STARTED_AT RELEASE_E2E_STARTED_AT="$RELEASE_STARTED_AT"
  export RELEASE_ARTIFACTS_ROOT RELEASE_ARTIFACTS_DIR RELEASE_EVIDENCE_DIR
  export RELEASE_LOGS_DIR RELEASE_CONTEXT_FILE
}

ensure_release_layout() {
  release_init_context

  mkdir -p "$RELEASE_ARTIFACTS_ROOT"

  if [[ -e "$RELEASE_ARTIFACTS_DIR" && ! -d "$RELEASE_ARTIFACTS_DIR" ]]; then
    echo "Release artifacts path exists but is not a directory: $RELEASE_ARTIFACTS_DIR" >&2
    return 1
  fi
  [[ ! -L "$RELEASE_ARTIFACTS_DIR" ]] || {
    echo "Release directory may not be a symlink: $RELEASE_ARTIFACTS_DIR" >&2
    return 1
  }
  mkdir -p "$RELEASE_EVIDENCE_DIR" "$RELEASE_LOGS_DIR"
}

release_artifact_path() {
  local name="$1"
  release_validate_relative_path "$name" || {
    echo "Release artifact path must be relative and must not traverse directories: $name" >&2
    return 1
  }
  ensure_release_layout
  case "$name" in
    logs/*) printf '%s/%s\n' "$RELEASE_ARTIFACTS_DIR" "$name" ;;
    *) printf '%s/%s\n' "$RELEASE_EVIDENCE_DIR" "$name" ;;
  esac
}

release_target_json() {
  local environment="$1"
  local subscription_id="$2"
  local resource_group="$3"
  local location="$4"
  local extra_json="${5-}"

  python3 - "$environment" "$subscription_id" "$resource_group" "$location" "$extra_json" <<'PY'
import json
import sys

environment, subscription_id, resource_group, location, extra_json = sys.argv[1:]
extra = json.loads(extra_json or "{}")
if not isinstance(extra, dict):
    raise SystemExit("Target extras must be a JSON object.")

payload = {
    "azd_env_name": environment,
    "subscription_id": subscription_id,
    "resource_group": resource_group,
    "location": location,
}
payload.update(extra)
print(json.dumps(payload, sort_keys=True))
PY
}

release_single_check_json() {
  local name="$1"
  local status="$2"
  local log_path="${3-}"
  local details_json="${4-}"

  python3 - "$name" "$status" "$log_path" "$details_json" <<'PY'
import json
import sys

name, status, log_path, details_json = sys.argv[1:]
payload = {
    "name": name,
    "status": status,
}
if log_path:
    payload["log"] = log_path
if details_json and details_json != "null":
    details = json.loads(details_json)
    if not isinstance(details, dict):
        raise SystemExit("Check details must be a JSON object.")
    payload.update(details)
print(json.dumps([payload], sort_keys=True))
PY
}

release_write_artifact() {
  local name="$1"
  local evidence_type="$2"
  local status="$3"
  local target_json="$4"
  local checks_json="${5-}"
  local extensions_json="${6-}"
  local extra_json="${7-}"
  local output_path

  output_path="$(release_artifact_path "$name")"
  python3 - \
    "$output_path" \
    "$RELEASE_ID" \
    "$RELEASE_STARTED_AT" \
    "$evidence_type" \
    "$status" \
    "$target_json" \
    "$checks_json" \
    "$extensions_json" \
    "$extra_json" <<'PY'
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

FORBIDDEN_KEY_PATTERN = re.compile(
    r"(api[_-]?key|bearer[_-]?token|connection[_-]?string|password|secret|database_url|runtime_database_url|access[_-]?token)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"AccountKey=", re.IGNORECASE),
    re.compile(r"SharedAccessSignature=", re.IGNORECASE),
    re.compile(r"DefaultEndpointsProtocol=", re.IGNORECASE),
    re.compile(r"://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]


def scan_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_KEY_PATTERN.search(str(key)):
                raise SystemExit(f"Forbidden key in release artifact at {path}.{key}")
            scan_forbidden(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_forbidden(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                raise SystemExit(f"Forbidden value detected in release artifact at {path}")


(
    output_path,
    release_id,
    release_started_at,
    evidence_type,
    status,
    target_json,
    checks_json,
    extensions_json,
    extra_json,
) = sys.argv[1:]
target = json.loads(target_json or "{}")
checks = json.loads(checks_json or "[]")
extensions = json.loads(extensions_json or "{}")
extra = json.loads(extra_json or "{}")

if not isinstance(target, dict):
    raise SystemExit("target must be a JSON object.")
if not isinstance(checks, list):
    raise SystemExit("checks must be a JSON array.")
if not isinstance(extensions, dict):
    raise SystemExit("extensions must be a JSON object.")
if not isinstance(extra, dict):
    raise SystemExit("extra fields must be a JSON object.")

payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "evidence_type": evidence_type,
    "artifact_type": evidence_type.replace("-", "_"),
    "status": status,
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    "target": target,
    "checks": checks,
    "extensions": extensions,
}
payload.update(extra)
payload["schema_version"] = 1
payload["contract"] = "azure-hosted-release/v1"
payload["lane"] = "azure-hosted"
payload["evidence_type"] = evidence_type
payload["artifact_type"] = evidence_type.replace("-", "_")
payload["status"] = status
payload["release_id"] = release_id
payload["release_started_at"] = release_started_at
payload.setdefault("generated_at", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
payload["target"] = target
payload["checks"] = checks
payload["extensions"] = extensions
scan_forbidden(payload)

path = Path(output_path)
path.parent.mkdir(parents=True, exist_ok=True)
temporary = path.with_name(f".{path.name}.{__import__('os').getpid()}.tmp")
with temporary.open("x", encoding="utf-8") as stream:
    stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    stream.flush()
    __import__("os").fsync(stream.fileno())
__import__("os").replace(temporary, path)
PY
}

release_write_stage_artifact() {
  local name="$1"
  local evidence_type="$2"
  local status="$3"
  local environment="$4"
  local subscription_id="$5"
  local resource_group="$6"
  local location="$7"
  local check_name="$8"
  local log_path="$9"
  local extra_json="${10-}"
  local target_extra_json="${11-}"
  local extensions_json="${12-}"
  local target_json checks_json

  target_json="$(release_target_json "$environment" "$subscription_id" "$resource_group" "$location" "$target_extra_json")"
  checks_json="$(release_single_check_json "$check_name" "$status" "$log_path")"
  release_write_artifact "$name" "$evidence_type" "$status" "$target_json" "$checks_json" "$extensions_json" "$extra_json"
}

release_adopt_root_file() {
  local name="$1"
  local source_path destination_path

  ensure_release_layout
  source_path="$RELEASE_ARTIFACTS_DIR/$name"
  destination_path="$RELEASE_LOGS_DIR/${name##*/}"

  if [[ ! -f "$source_path" || "$source_path" == "$destination_path" ]]; then
    return 0
  fi
  if [[ -e "$destination_path" ]]; then
    rm -f "$source_path"
    ln -s "logs/${name##*/}" "$source_path"
    return 0
  fi

  mv "$source_path" "$destination_path"
  ln -s "logs/${name##*/}" "$source_path"
}

release_assert_secret_free_file() {
  local path="$1"

  python3 - "$path" <<'PY'
import json
import re
import sys
from pathlib import Path

FORBIDDEN_KEY_PATTERN = re.compile(
    r"(api[_-]?key|bearer[_-]?token|connection[_-]?string|password|secret|database_url|runtime_database_url|access[_-]?token)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"AccountKey=", re.IGNORECASE),
    re.compile(r"SharedAccessSignature=", re.IGNORECASE),
    re.compile(r"DefaultEndpointsProtocol=", re.IGNORECASE),
    re.compile(r"://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]


def scan_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_KEY_PATTERN.search(str(key)):
                raise SystemExit(f"Forbidden key in release artifact at {path}.{key}")
            scan_forbidden(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_forbidden(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                raise SystemExit(f"Forbidden value detected in release artifact at {path}")


payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
scan_forbidden(payload)
PY
}

release_normalize_artifact_file() {
  local path="$1"
  local expected_evidence_type="${2:-}"

  [[ -f "$path" ]] || return 0

  python3 - "$path" "$RELEASE_ID" "$RELEASE_STARTED_AT" "$expected_evidence_type" "$RELEASE_CONTEXT_FILE" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

path, release_id, release_started_at, expected_evidence_type, context_path = sys.argv[1:]
artifact_path = Path(path)
payload = json.loads(artifact_path.read_text(encoding="utf-8"))
if not isinstance(payload, dict):
    raise SystemExit(f"{artifact_path.name} must contain a JSON object.")

context_target = {}
context_file = Path(context_path)
if context_file.is_file():
    context_payload = json.loads(context_file.read_text(encoding="utf-8"))
    if isinstance(context_payload, dict) and isinstance(context_payload.get("target"), dict):
        context_target = context_payload["target"]

evidence_type = expected_evidence_type or payload.get("evidence_type") or payload.get("artifact_type") or artifact_path.stem
evidence_type = str(evidence_type).replace("_", "-")
payload["schema_version"] = 1
payload["contract"] = "azure-hosted-release/v1"
payload["lane"] = "azure-hosted"
payload["evidence_type"] = evidence_type
payload["artifact_type"] = evidence_type.replace("-", "_")
payload["release_id"] = release_id
payload["release_started_at"] = release_started_at
payload.setdefault("generated_at", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
payload["target"] = payload.get("target") if isinstance(payload.get("target"), dict) else context_target
payload["checks"] = payload.get("checks") if isinstance(payload.get("checks"), list) else []
extensions = payload.get("extensions") if isinstance(payload.get("extensions"), dict) else {}
extensions.setdefault("canonical_file", artifact_path.name)
payload["extensions"] = extensions
temporary = artifact_path.with_name(f".{artifact_path.name}.{__import__('os').getpid()}.tmp")
with temporary.open("x", encoding="utf-8") as stream:
    stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    stream.flush()
    __import__("os").fsync(stream.fileno())
__import__("os").replace(temporary, artifact_path)
PY
  release_assert_secret_free_file "$path"
}

normalize_release_artifacts() {
  local name path

  ensure_release_layout
  for name in \
    release-context.json \
    source-validation.json \
    infrastructure.json \
    images.json \
    deployment.json \
    smoke.json \
    domain-e2e.json \
    evaluation.json \
    telemetry.json \
    release-evidence.json
  do
    path="$(release_artifact_path "$name")"
    if [[ -f "$path" ]]; then
      release_normalize_artifact_file "$path" "$(release_evidence_type_for_name "$name")"
    fi
  done
}

write_release_context() {
  local environment="$1"
  local subscription_id="$2"
  local resource_group="$3"
  local location="$4"
  local target_json checks_json extensions_json extra_json

  ensure_release_layout
  target_json="$(release_target_json "$environment" "$subscription_id" "$resource_group" "$location")"
  checks_json="$(release_single_check_json "target-selection" "passed")"
  extensions_json="$(python3 - "$RELEASE_ID" <<'PY'
import json
import sys

release_id = sys.argv[1]
print(json.dumps({
    "canonical_artifacts_root": ".artifacts/releases",
    "release_authority": "prepared_not_live_validated",
}))
PY
)"
  extra_json="$(python3 <<'PY'
import json

print(json.dumps({
    "artifact_files": {
        "release_context": "evidence/release-context.json",
        "source_validation": "evidence/source-validation.json",
        "infrastructure": "evidence/infrastructure.json",
        "images": "evidence/images.json",
        "deployment": "evidence/deployment.json",
        "smoke": "evidence/smoke.json",
        "domain_e2e": "evidence/domain-e2e.json",
        "evaluation": "evidence/evaluation.json",
        "telemetry": "evidence/telemetry.json",
        "release_evidence": "evidence/release-evidence.json",
        "browser_e2e_log": "logs/browser-e2e.log",
        "logs": "logs/",
    },
    "phases": [
        "release-profile-apply",
        "release-preflight",
        "release-package",
        "release-deploy",
        "release-verify",
        "release-smoke",
        "release-browser-e2e",
        "release-domain-e2e",
        "release-eval",
        "release-telemetry",
        "release-evidence",
        "release",
    ],
}))
PY
)"
  release_write_artifact "release-context.json" "release-context" "ready" "$target_json" "$checks_json" "$extensions_json" "$extra_json"
  local repository_root canonical_profile
  repository_root="$(cd "$ROOT_DIR/../../.." && pwd -P)"
  canonical_profile="$ROOT_DIR/../deployment/profiles/azure-hosted.env"
  python3 "$ROOT_DIR/scripts/release/release-record.py" init \
    --release-dir "$RELEASE_ARTIFACTS_DIR" \
    --project-root "$repository_root" \
    --release-id "$RELEASE_ID" \
    --started-at "$RELEASE_STARTED_AT" \
    --profile "$canonical_profile" \
    --environment "$environment" \
    --subscription-id "$subscription_id" \
    --resource-group "$resource_group" \
    --location "$location"
}
