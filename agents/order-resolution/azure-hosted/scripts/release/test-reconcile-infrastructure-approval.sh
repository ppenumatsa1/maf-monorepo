#!/bin/bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TEST_DIR="$ROOT_DIR/.artifacts/reconcile-owner-test-$$-$RANDOM"
FAKE_BIN="$TEST_DIR/bin"
SUBSCRIPTION_ID="11111111-1111-1111-1111-111111111111"
POSTGRES_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/test-postgres"
POSTGRES_DATABASE_ID="$POSTGRES_ID/databases/maf_workflow"
SUCCESS_RUN_ID="owner-confirmation-success-$$"

cleanup() {
  rm -rf "$TEST_DIR" "$ROOT_DIR/.artifacts/release/$SUCCESS_RUN_ID"
}
trap cleanup EXIT
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/azd" <<'EOF'
#!/bin/bash
set -euo pipefail
[[ "$1 ${2:-}" == "env get-value" ]]
case "$3" in
  AZURE_SUBSCRIPTION_ID) printf '%s\n' "11111111-1111-1111-1111-111111111111" ;;
  AZURE_RESOURCE_GROUP) printf '%s\n' "rg-maf-ora-azure" ;;
  AZURE_LOCATION) printf '%s\n' "northcentralus" ;;
  AZURE_POSTGRES_HOST) printf '%s\n' "test-postgres.postgres.database.azure.com" ;;
  AZURE_POSTGRES_DATABASE) printf '%s\n' "maf_workflow" ;;
  *) echo "unexpected azd output: $3" >&2; exit 99 ;;
esac
EOF

cat >"$FAKE_BIN/az" <<'EOF'
#!/bin/bash
set -euo pipefail

case "$1 ${2:-} ${3:-}" in
  "account show --subscription") printf '%s\n' "11111111-1111-1111-1111-111111111111" ;;
  "group show --name") printf '%s\n' "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-maf-ora-azure" ;;
  "postgres flexible-server list") printf '%s\n' "1" ;;
  "postgres flexible-server show") printf '%s\n' "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/test-postgres" ;;
  "deployment sub what-if") /bin/cat "$FAKE_WHAT_IF_RESPONSE" ;;
  "deployment sub create") : >"$FAKE_APPLY_SENTINEL" ;;
  *) echo "unexpected az invocation: $*" >&2; exit 99 ;;
esac
EOF

cat >"$FAKE_BIN/bicep" <<'EOF'
#!/bin/bash
set -euo pipefail
[[ "$1" == "build" && "$3" == "--stdout" ]]
/bin/cat "$FAKE_COMPILED_TEMPLATE"
EOF

cat >"$FAKE_BIN/python3" <<'EOF'
#!/bin/bash
exec /usr/bin/python3 "$@"
EOF
chmod 700 "$FAKE_BIN"/*

compiled_template="$TEST_DIR/compiled-template.json"
parameters_file="$TEST_DIR/parameters.json"
safe_what_if="$TEST_DIR/what-if-safe.json"
postgres_mutation_what_if="$TEST_DIR/what-if-postgres-mutation.json"
apply_sentinel="$TEST_DIR/apply-reached"

printf '%s\n' '{"fixture":"compiled-template"}' >"$compiled_template"
printf '%s\n' '{"parameters":{"fixture":"owner-confirmed"}}' >"$parameters_file"
cat >"$safe_what_if" <<EOF
{"changes":[{"resourceId":"$POSTGRES_ID","changeType":"NoChange"},{"resourceId":"$POSTGRES_DATABASE_ID","changeType":"NoChange"}]}
EOF
cat >"$postgres_mutation_what_if" <<EOF
{"changes":[{"resourceId":"$POSTGRES_ID","changeType":"Modify"},{"resourceId":"$POSTGRES_DATABASE_ID","changeType":"NoChange"}]}
EOF

template_sha256="$(sha256sum "$compiled_template" | awk '{print $1}')"
parameters_sha256="$(sha256sum "$parameters_file" | awk '{print $1}')"
template_parameters_sha256="$(
  printf '%s\n%s\n' "$template_sha256" "$parameters_sha256" | sha256sum | awk '{print $1}'
)"
preview_sha256="$(sha256sum "$safe_what_if" | awk '{print $1}')"

run_apply() {
  local release_run_id="$1"
  local approved="${2-true}"
  local owner_reference="${3-owner-change-20260807}"
  local supplied_preview_sha="${4-$preview_sha256}"
  local what_if_file="${5-$safe_what_if}"

  /usr/bin/env -u BASH_ENV -u ENV \
    PATH="$FAKE_BIN" \
    AZURE_SUBSCRIPTION_ID="" \
    AZURE_ENV_NAME="maf-ora-azure" \
    RELEASE_RUN_ID="$release_run_id" \
    INFRA_RECONCILIATION_TEST_HARNESS="credential-free-reconciliation-mock-v1" \
    INFRA_RECONCILIATION_TEST_COMMAND_ROOT="$FAKE_BIN" \
    INFRA_RECONCILIATION_PARAMETERS_FILE="$parameters_file" \
    INFRA_RECONCILIATION_REFERENCE="$owner_reference" \
    INFRA_RECONCILIATION_APPROVED="$approved" \
    INFRA_RECONCILIATION_PREVIEW_SHA256="$supplied_preview_sha" \
    INFRA_RECONCILIATION_TEMPLATE_PARAMETERS_SHA256="$template_parameters_sha256" \
    FAKE_COMPILED_TEMPLATE="$compiled_template" \
    FAKE_WHAT_IF_RESPONSE="$what_if_file" \
    FAKE_APPLY_SENTINEL="$apply_sentinel" \
    "$ROOT_DIR/scripts/release/reconcile-infrastructure.sh" --apply
}

success_output="$(run_apply "$SUCCESS_RUN_ID")"
[[ -f "$apply_sentinel" ]] || {
  echo "Credential-free owner confirmation success path did not reach the Azure deployment create boundary." >&2
  exit 1
}
[[ "$success_output" == *"Owner-confirmed infrastructure reconciliation completed while preserving PostgreSQL"* ]] || {
  echo "Credential-free owner confirmation success path did not complete reconciliation guards." >&2
  exit 1
}

expect_failure() {
  local description="$1"
  local expected="$2"
  shift 2
  local output
  if output="$("$@" 2>&1)"; then
    echo "$description unexpectedly succeeded." >&2
    exit 1
  fi
  [[ "$output" == *"$expected"* ]] || {
    echo "$description did not produce its expected failure: $expected" >&2
    printf '%s\n' "$output" >&2
    exit 1
  }
}

expect_failure \
  "missing owner confirmation" \
  "requires INFRA_RECONCILIATION_APPROVED=true" \
  run_apply "missing-confirmation-$$" false
expect_failure \
  "missing owner reference" \
  "must be a non-secret owner change reference" \
  run_apply "missing-reference-$$" true ""
expect_failure \
  "mismatched preview digest" \
  "does not match independently computed what-if" \
  run_apply "mismatched-preview-$$" true "owner-change-20260807" "$(printf '0%.0s' {1..64})"
expect_failure \
  "PostgreSQL mutation" \
  "Azure what-if includes a PostgreSQL resource mutation" \
  run_apply "postgres-mutation-$$" true "owner-change-20260807" "$preview_sha256" "$postgres_mutation_what_if"

echo "Credential-free owner-confirmation reconciliation guards passed; fake Azure apply was reached only after every guard."
