#!/bin/bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

mode="preview"
for argument in "$@"; do
  case "$argument" in
    --preview) mode="preview" ;;
    --apply) mode="apply" ;;
    *)
      echo "Usage: $0 [--preview|--apply]" >&2
      echo "Initial provisioning is disabled: this reconciliation lane never creates PostgreSQL." >&2
      exit 2
      ;;
  esac
done

TEST_HARNESS="credential-free-reconciliation-mock-v1"
SAFE_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
test_command_root="${INFRA_RECONCILIATION_TEST_COMMAND_ROOT:-}"
is_mock_harness=false

if [[ "${INFRA_RECONCILIATION_TEST_HARNESS:-}" == "$TEST_HARNESS" ]]; then
  if [[ -z "$test_command_root" || "$test_command_root" != "$ROOT_DIR/.artifacts/"* ]]; then
    echo "Credential-free reconciliation mocks must use a test command directory under .artifacts." >&2
    exit 1
  fi
  PATH="$test_command_root"
  is_mock_harness=true
else
  PATH="$SAFE_PATH"
fi
export PATH

# The Make entrypoint starts this script with env -i. Clear these again for
# direct invocations before any command can consume an inherited configuration.
unset BASH_ENV ENV CDPATH AZURE_CONFIG_DIR AZD_CONFIG_DIR BICEP_CONFIG_FILE

environment="${AZURE_ENV_NAME:-maf-ora-azure}"
release_run_id="${RELEASE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
artifacts_dir="$ROOT_DIR/.artifacts/release/$release_run_id"
dry_run="${RELEASE_DRY_RUN:-false}"
template_source="infra/azure-apphosted/iac/main.bicep"
parameters_file="${INFRA_RECONCILIATION_PARAMETERS_FILE:-}"
reference="${INFRA_RECONCILIATION_REFERENCE:-}"
AZ_COMMAND=""
AZD_COMMAND=""
BICEP_COMMAND=""
PYTHON_COMMAND=""

[[ "$release_run_id" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "RELEASE_RUN_ID may contain only letters, digits, dots, underscores, and hyphens." >&2
  exit 1
}

verify_trusted_command() {
  local name="$1"
  local candidate resolved owner mode_bits

  if [[ "$is_mock_harness" == true ]]; then
    candidate="$test_command_root/$name"
    [[ -f "$candidate" && ! -L "$candidate" && -x "$candidate" ]] || {
      echo "Credential-free reconciliation mock command is invalid: $name" >&2
      exit 1
    }
    owner="$(/usr/bin/stat -c '%u' "$candidate")"
    mode_bits="$(/usr/bin/stat -c '%a' "$candidate")"
    if [[ "$owner" != "$UID" || $((8#$mode_bits & 8#022)) -ne 0 ]]; then
      echo "Credential-free reconciliation mock command has unsafe ownership or permissions: $name" >&2
      exit 1
    fi
    printf '%s\n' "$candidate"
    return
  fi

  candidate="$(command -v "$name" 2>/dev/null || true)"
  [[ "$candidate" == /* ]] || {
    echo "Infrastructure reconciliation requires an absolute executable path for $name." >&2
    exit 1
  }
  resolved="$(/usr/bin/readlink -f -- "$candidate" 2>/dev/null || true)"
  [[ -n "$resolved" && -f "$resolved" && -x "$resolved" ]] || {
    echo "Infrastructure reconciliation could not resolve an executable for $name." >&2
    exit 1
  }
  owner="$(/usr/bin/stat -c '%u' "$resolved")"
  mode_bits="$(/usr/bin/stat -c '%a' "$resolved")"
  if [[ "$owner" != "0" || $((8#$mode_bits & 8#022)) -ne 0 ]]; then
    echo "Infrastructure reconciliation refuses $name: it must be root-owned and not group/world writable." >&2
    exit 1
  fi
  printf '%s\n' "$resolved"
}

require_sha256() {
  local variable_name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9a-f]{64}$ ]]; then
    echo "$variable_name must be a lowercase SHA-256 digest." >&2
    exit 1
  fi
}

sha256_file() {
  /usr/bin/sha256sum "$1" | /usr/bin/awk '{print $1}'
}

template_parameters_digest() {
  local template_sha="$1"
  local parameters_sha="$2"
  printf '%s\n%s\n' "$template_sha" "$parameters_sha" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}'
}

require_parameters_file() {
  if [[ -z "$parameters_file" ]]; then
    echo "INFRA_RECONCILIATION_PARAMETERS_FILE is required." >&2
    exit 1
  fi
  [[ ! -L "$parameters_file" ]] || {
    echo "INFRA_RECONCILIATION_PARAMETERS_FILE must not be a symlink." >&2
    exit 1
  }
  parameters_file="$(/usr/bin/readlink -e -- "$parameters_file" 2>/dev/null || true)"
  [[ -n "$parameters_file" && -f "$parameters_file" ]] || {
    echo "INFRA_RECONCILIATION_PARAMETERS_FILE must resolve to a regular file." >&2
    exit 1
  }
  [[ "$parameters_file" == "$ROOT_DIR/"* ]] || {
    echo "INFRA_RECONCILIATION_PARAMETERS_FILE must resolve under the repository root." >&2
    exit 1
  }
}

require_owner_confirmation() {
  [[ "${INFRA_RECONCILIATION_APPROVED:-}" == "true" ]] || {
    echo "Applying infrastructure requires INFRA_RECONCILIATION_APPROVED=true after owner review of the captured what-if." >&2
    exit 1
  }
  if [[ -z "$reference" || ${#reference} -gt 256 || "$reference" == *$'\n'* || "$reference" == *$'\r'* ]]; then
    echo "INFRA_RECONCILIATION_REFERENCE must be a non-secret owner change reference of at most 256 characters." >&2
    exit 1
  fi
  require_sha256 "INFRA_RECONCILIATION_PREVIEW_SHA256" "${INFRA_RECONCILIATION_PREVIEW_SHA256:-}"
  require_sha256 "INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256" "${INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256:-}"
}

if [[ "$dry_run" == "true" ]]; then
  BICEP_COMMAND="$(verify_trusted_command bicep)"
  PATH="$SAFE_PATH" /bin/bash ./scripts/release/validate-release-assets.sh
  "$BICEP_COMMAND" build "$template_source" --stdout >/dev/null
  cat <<EOF
Infrastructure reconciliation dry run completed local source checks only.
It did not contact Azure, produce an authoritative what-if, or authorize provisioning.
Use --preview with INFRA_RECONCILIATION_PARAMETERS_FILE to capture the required Azure
subscription-scope what-if evidence.
EOF
  exit 0
fi

require_parameters_file
if [[ "$mode" == "apply" ]]; then
  require_owner_confirmation
fi

AZ_COMMAND="$(verify_trusted_command az)"
AZD_COMMAND="$(verify_trusted_command azd)"
BICEP_COMMAND="$(verify_trusted_command bicep)"
PYTHON_COMMAND="$(verify_trusted_command python3)"

get_azd_output() {
  "$AZD_COMMAND" env get-value "$1" --environment "$environment" 2>/dev/null
}

azd_subscription_id="$(get_azd_output AZURE_SUBSCRIPTION_ID)"
if [[ ! "$azd_subscription_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
  echo "The selected AZD environment must define AZURE_SUBSCRIPTION_ID as a subscription ID." >&2
  exit 1
fi
if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" && "$AZURE_SUBSCRIPTION_ID" != "$azd_subscription_id" ]]; then
  echo "AZURE_SUBSCRIPTION_ID does not match the selected AZD environment." >&2
  exit 1
fi
export AZURE_SUBSCRIPTION_ID="$azd_subscription_id"

resolved_subscription_id="$("$AZ_COMMAND" account show \
  --subscription "$AZURE_SUBSCRIPTION_ID" --query id --output tsv)"
if [[ "$resolved_subscription_id" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI could not resolve the selected AZD environment subscription ID." >&2
  exit 1
fi

resource_group="$(get_azd_output AZURE_RESOURCE_GROUP)"
location="$(get_azd_output AZURE_LOCATION)"
postgres_host="$(get_azd_output AZURE_POSTGRES_HOST)"
postgres_database="$(get_azd_output AZURE_POSTGRES_DATABASE)"
if [[ -z "$resource_group" || -z "$location" || -z "$postgres_host" || -z "$postgres_database" ]]; then
  echo "Selected AZD environment is missing resource group, location, or PostgreSQL outputs; reconciliation fails closed." >&2
  exit 1
fi
if [[ "$resource_group" != "rg-$environment" ]]; then
  echo "Selected AZD resource group does not match the deterministic Bicep resource group for this environment." >&2
  exit 1
fi
if [[ ! "$postgres_database" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Selected AZD PostgreSQL database output is not a supported identifier." >&2
  exit 1
fi
postgres_name="${postgres_host%%.*}"
if [[ -z "$postgres_name" || "$postgres_name" == "$postgres_host" ]]; then
  echo "Selected AZD PostgreSQL host output is invalid." >&2
  exit 1
fi

"$AZ_COMMAND" group show --name "$resource_group" --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query id --output tsv >/dev/null
postgres_count="$("$AZ_COMMAND" postgres flexible-server list \
  --resource-group "$resource_group" --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query 'length(@)' --output tsv)"
if [[ "$postgres_count" != "1" ]]; then
  echo "Reconciliation requires exactly one existing PostgreSQL flexible server and never creates another." >&2
  exit 1
fi
postgres_id="$("$AZ_COMMAND" postgres flexible-server show \
  --resource-group "$resource_group" --name "$postgres_name" \
  --subscription "$AZURE_SUBSCRIPTION_ID" --query id --output tsv)"
if [[ -z "$postgres_id" ]]; then
  echo "Reconciliation refuses to continue because the selected PostgreSQL server was not found." >&2
  exit 1
fi
postgres_database_id="${postgres_id}/databases/${postgres_database}"

/usr/bin/mkdir -p "$artifacts_dir"
compiled_template="$artifacts_dir/main.bicep.json"
what_if_file="$artifacts_dir/infrastructure-what-if.json"
PATH="$SAFE_PATH" /bin/bash ./scripts/release/validate-release-assets.sh \
  >"$artifacts_dir/release-assets-validation.log" 2>&1
"$BICEP_COMMAND" build "$template_source" --stdout >"$compiled_template"

template_sha256="$(sha256_file "$compiled_template")"
parameters_sha256="$(sha256_file "$parameters_file")"
evidence_sha256="$(template_parameters_digest "$template_sha256" "$parameters_sha256")"

"$AZ_COMMAND" deployment sub what-if \
  --name "maf-ora-reconcile-$release_run_id" \
  --location "$location" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --template-file "$compiled_template" \
  --parameters "@$parameters_file" \
  --result-format ResourceIdOnly \
  --no-pretty-print \
  --no-prompt \
  --only-show-errors \
  --output json >"$what_if_file"

"$PYTHON_COMMAND" - "$what_if_file" "$postgres_id" "$postgres_database_id" <<'PY'
import json
import sys

what_if_path, postgres_server_id, postgres_database_id = sys.argv[1:]
try:
    payload = json.load(open(what_if_path, encoding="utf-8"))
except (OSError, json.JSONDecodeError) as error:
    raise SystemExit(f"Azure what-if output is not machine-parseable JSON: {error}")

changes = payload.get("changes")
if not isinstance(changes, list):
    raise SystemExit("Azure what-if output has no machine-parseable changes list; refusing provision.")

postgres_server_id = postgres_server_id.lower()
postgres_database_id = postgres_database_id.lower()
server_no_change = False
database_no_change = False
for index, change in enumerate(changes):
    if not isinstance(change, dict):
        raise SystemExit(f"Azure what-if change {index} is malformed; refusing provision.")
    resource_id = change.get("resourceId")
    change_type = change.get("changeType")
    if not isinstance(resource_id, str) or not isinstance(change_type, str):
        raise SystemExit(f"Azure what-if change {index} lacks resourceId or changeType; refusing provision.")
    normalized_resource_id = resource_id.lower()
    if "/providers/microsoft.dbforpostgresql/" in normalized_resource_id and change_type != "NoChange":
        raise SystemExit(
            "Azure what-if includes a PostgreSQL resource mutation "
            f"({change_type}: {resource_id}); refusing provision."
        )
    if normalized_resource_id == postgres_server_id and change_type == "NoChange":
        server_no_change = True
    if normalized_resource_id == postgres_database_id and change_type == "NoChange":
        database_no_change = True

if not server_no_change or not database_no_change:
    raise SystemExit(
        "Azure what-if did not prove the selected PostgreSQL server and database are NoChange; "
        "refusing provision."
    )
PY

preview_sha256="$(sha256_file "$what_if_file")"
if [[ "$mode" == "preview" ]]; then
  cat <<EOF
Azure subscription-scope what-if completed without PostgreSQL mutations.
  what-if evidence: $what_if_file
  INFRA_RECONCILIATION_PREVIEW_SHA256=$preview_sha256
  INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256=$evidence_sha256
No resources were changed.

For a single-maintainer apply, verify this output and run with:
  INFRA_RECONCILIATION_APPROVED=true
  INFRA_RECONCILIATION_REFERENCE="<non-secret-owner-change-reference>"
  INFRA_RECONCILIATION_PREVIEW_SHA256=$preview_sha256
  INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256=$evidence_sha256
EOF
  exit 0
fi

if [[ "$INFRA_RECONCILIATION_PREVIEW_SHA256" != "$preview_sha256" ||
  "$INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256" != "$evidence_sha256" ]]; then
  echo "Owner-provided evidence digest does not match independently computed what-if or template/parameters evidence." >&2
  exit 1
fi

"$AZ_COMMAND" deployment sub create \
  --name "maf-ora-reconcile-$release_run_id" \
  --location "$location" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --template-file "$compiled_template" \
  --parameters "@$parameters_file" \
  --no-prompt \
  --only-show-errors \
  --output none >"$artifacts_dir/infrastructure-reconcile.log" 2>&1

reconciled_postgres_count="$("$AZ_COMMAND" postgres flexible-server list \
  --resource-group "$resource_group" --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query 'length(@)' --output tsv)"
reconciled_postgres_id="$("$AZ_COMMAND" postgres flexible-server show \
  --resource-group "$resource_group" --name "$postgres_name" \
  --subscription "$AZURE_SUBSCRIPTION_ID" --query id --output tsv)"
if [[ "$reconciled_postgres_count" != "1" || "$reconciled_postgres_id" != "$postgres_id" ]]; then
  echo "PostgreSQL identity changed during reconciliation; treating the release as unsafe." >&2
  exit 1
fi

echo "Owner-confirmed infrastructure reconciliation completed while preserving PostgreSQL (reference: $reference)."
