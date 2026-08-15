#!/bin/bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TEST_DIR="$ROOT_DIR/.artifacts/reconcile-owner-test-$$-$RANDOM"
FAKE_BIN="$TEST_DIR/bin"
SUBSCRIPTION_ID="7df95e88-701c-4693-af77-3159f83b558d"
POSTGRES_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/test-postgres"
POSTGRES_DATABASE_ID="$POSTGRES_ID/databases/maf_workflow"
SUCCESS_RUN_ID="direct-safe-apply-success-$$"

cleanup() {
  rm -rf "$TEST_DIR" "$ROOT_DIR/.artifacts/release/$SUCCESS_RUN_ID"
}
trap cleanup EXIT
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/azd" <<'EOF'
#!/bin/bash
set -euo pipefail
[[ "$1 ${2:-}" == "env get-value" ]]
if [[ "${FAKE_MISSING_AZD_VALUE:-}" == "$3" ]]; then
  exit 0
fi
case "$3" in
  AZURE_SUBSCRIPTION_ID) printf '%s\n' "7df95e88-701c-4693-af77-3159f83b558d" ;;
  AZURE_RESOURCE_GROUP) printf '%s\n' "rg-maf-ora-azure" ;;
  AZURE_LOCATION) printf '%s\n' "northcentralus" ;;
  AZURE_POSTGRES_HOST) printf '%s\n' "test-postgres.postgres.database.azure.com" ;;
  AZURE_POSTGRES_DATABASE) printf '%s\n' "maf_workflow" ;;
  FOUNDRY_PROJECT_NAME) printf '%s\n' "order-resolution" ;;
  FOUNDRY_CHAT_DEPLOYMENT_NAME) printf '%s\n' "gpt-4.1-mini" ;;
  FOUNDRY_CHAT_MODEL_FORMAT) printf '%s\n' "OpenAI" ;;
  FOUNDRY_CHAT_MODEL_NAME) printf '%s\n' "gpt-4.1-mini" ;;
  FOUNDRY_CHAT_MODEL_VERSION) printf '%s\n' "2025-04-14" ;;
  FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME) printf '%s\n' "Standard" ;;
  FOUNDRY_CHAT_DEPLOYMENT_CAPACITY) printf '%s\n' "50" ;;
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME) printf '%s\n' "text-embedding-3-small" ;;
  FOUNDRY_EMBEDDINGS_MODEL_FORMAT) printf '%s\n' "OpenAI" ;;
  FOUNDRY_EMBEDDINGS_MODEL_NAME) printf '%s\n' "text-embedding-3-small" ;;
  FOUNDRY_EMBEDDINGS_MODEL_VERSION) printf '%s\n' "1" ;;
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME) printf '%s\n' "DataZoneStandard" ;;
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY) printf '%s\n' "1" ;;
  FOUNDRY_EVALUATOR_DEPLOYMENT_NAME) printf '%s\n' "gpt-4.1-mini-evaluator" ;;
  FOUNDRY_EVALUATOR_MODEL_FORMAT) printf '%s\n' "OpenAI" ;;
  FOUNDRY_EVALUATOR_MODEL_NAME) printf '%s\n' "gpt-4.1-mini" ;;
  FOUNDRY_EVALUATOR_MODEL_VERSION) printf '%s\n' "2025-04-14" ;;
  FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME) printf '%s\n' "Standard" ;;
  FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY) printf '%s\n' "50" ;;
  FOUNDRY_RAI_POLICY_NAME) printf '%s\n' "Microsoft.Default" ;;
  *) echo "unexpected azd output: $3" >&2; exit 99 ;;
esac
EOF

cat >"$FAKE_BIN/az" <<'EOF'
#!/bin/bash
set -euo pipefail
printf '%q ' "$@" >>"$FAKE_AZ_LOG"
printf '\n' >>"$FAKE_AZ_LOG"

case "$1 ${2:-} ${3:-}" in
  "account show --subscription") printf '%s\n' "7df95e88-701c-4693-af77-3159f83b558d" ;;
  "group show --name") printf '%s\n' "/subscriptions/7df95e88-701c-4693-af77-3159f83b558d/resourceGroups/rg-maf-ora-azure" ;;
  "postgres flexible-server list") printf '%s\n' "1" ;;
  "postgres flexible-server show") printf '%s\n' "/subscriptions/7df95e88-701c-4693-af77-3159f83b558d/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/test-postgres" ;;
  "postgres flexible-server db") printf '%s\n' "/subscriptions/7df95e88-701c-4693-af77-3159f83b558d/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/test-postgres/databases/maf_workflow" ;;
  "containerapp list --resource-group")
    if [[ "$*" == *"backend"* ]]; then printf '%s\n' "maf-backend-test"
    else printf '%s\n' "maf-frontend-test"
    fi
    ;;
  "containerapp show --name")
    if [[ "$*" == *"maf-backend-test"* ]]; then printf '%s\n' "example.azurecr.io/backend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    else printf '%s\n' "example.azurecr.io/frontend@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    fi
    ;;
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
safe_what_if="$TEST_DIR/what-if-safe.json"
postgres_mutation_what_if="$TEST_DIR/what-if-postgres-mutation.json"
apply_sentinel="$TEST_DIR/apply-reached"
az_log="$TEST_DIR/az.log"

printf '%s\n' '{"fixture":"compiled-template"}' >"$compiled_template"
cat >"$safe_what_if" <<EOF
{"changes":[{"resourceId":"/subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-maf-ora-azure/providers/Microsoft.Insights/components/test","changeType":"NoChange"}]}
EOF
cat >"$postgres_mutation_what_if" <<EOF
{"changes":[{"resourceId":"$POSTGRES_ID","changeType":"Modify"},{"resourceId":"$POSTGRES_DATABASE_ID","changeType":"NoChange"}]}
EOF

run_apply() {
  local release_run_id="$1"
  local what_if_file="${2-$safe_what_if}"
  local missing_azd_value="${3-}"

  /usr/bin/env -u BASH_ENV -u ENV \
    PATH="$FAKE_BIN" \
    AZURE_SUBSCRIPTION_ID="" \
    AZURE_ENV_NAME="maf-ora-azure" \
    RELEASE_RUN_ID="$release_run_id" \
    INFRA_RECONCILIATION_TEST_HARNESS="credential-free-reconciliation-mock-v1" \
    INFRA_RECONCILIATION_TEST_COMMAND_ROOT="$FAKE_BIN" \
    FAKE_COMPILED_TEMPLATE="$compiled_template" \
    FAKE_WHAT_IF_RESPONSE="$what_if_file" \
    FAKE_APPLY_SENTINEL="$apply_sentinel" \
    FAKE_AZ_LOG="$az_log" \
    FAKE_MISSING_AZD_VALUE="$missing_azd_value" \
    "$ROOT_DIR/scripts/release/reconcile-infrastructure.sh" --apply
}

success_output="$(run_apply "$SUCCESS_RUN_ID")"
[[ -f "$apply_sentinel" ]] || {
  echo "Credential-free direct safe apply did not reach the Azure deployment create boundary." >&2
  exit 1
}
[[ "$success_output" == *"Infrastructure reconciliation completed while preserving PostgreSQL."* ]] || {
  echo "Credential-free direct safe apply did not complete reconciliation guards." >&2
  exit 1
}
grep -Fq "foundryChatDeploymentSkuName=Standard" "$az_log"
grep -Fq "foundryEmbeddingsDeploymentSkuName=DataZoneStandard" "$az_log"
grep -Fq "foundryEvaluatorDeploymentSkuName=Standard" "$az_log"
if grep -Eq "mcp(ApiKey|BearerToken|ServerUrl)" "$az_log"; then
  echo "Steady-state reconciliation unexpectedly passed application MCP configuration." >&2
  exit 1
fi

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
  "PostgreSQL mutation" \
  "steadyState mode must exclude it" \
  run_apply "postgres-mutation-$$" "$postgres_mutation_what_if"

rm -f "$apply_sentinel"
expect_failure \
  "missing stateful Foundry value" \
  "missing required steady-state value: FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME" \
  run_apply "missing-foundry-value-$$" "$safe_what_if" "FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME"
[[ ! -f "$apply_sentinel" ]] || {
  echo "Missing stateful Foundry configuration reached the Azure apply boundary." >&2
  exit 1
}

echo "Credential-free direct reconciliation guards passed; fake Azure apply was reached only after a fresh safe what-if."
