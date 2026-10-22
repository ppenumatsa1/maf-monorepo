#!/usr/bin/env bash
set -euo pipefail
umask 077
unset AZURE_ENV_NAME

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TEST_DIR="$ROOT_DIR/.artifacts/subscription-portability-test-$$-$RANDOM"
FAKE_BIN="$TEST_DIR/bin"
PROFILE="$TEST_DIR/azure-hosted.env"
SUBSCRIPTION_ID="11111111-1111-4111-8111-111111111111"
TENANT_ID="22222222-2222-4222-8222-222222222222"
RESOURCE_GROUP="rg-portable-azure"
LOCATION="regionone"

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT
mkdir -p "$FAKE_BIN"
sed \
  -e 's/^AZURE_ENV_NAME=.*/AZURE_ENV_NAME=portable-azure-hosted/' \
  -e "0,/00000000-0000-0000-0000-000000000000/s//$TENANT_ID/" \
  -e "0,/00000000-0000-0000-0000-000000000000/s//$SUBSCRIPTION_ID/" \
  -e "s/^AZURE_RESOURCE_GROUP=.*/AZURE_RESOURCE_GROUP=$RESOURCE_GROUP/" \
  -e "s/^AZURE_LOCATION=.*/AZURE_LOCATION=$LOCATION/" \
  -e 's/^NAME_PREFIX=.*/NAME_PREFIX=portableazure/' \
  "$ROOT_DIR/../deployment/profiles/azure-hosted.env.example" >"$PROFILE"

cat >"$FAKE_BIN/az" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "$1 ${2:-} ${3:-}" in
  "account show --subscription")
    case "$*" in
      *"--query tenantId"*) printf '%s\n' "22222222-2222-4222-8222-222222222222" ;;
      *"--query state"*) printf '%s\n' "Enabled" ;;
      *) printf '%s\n' "11111111-1111-4111-8111-111111111111" ;;
    esac
    ;;
  "postgres flexible-server show")
    printf '%s\n' "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-portable-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/portable-pg-test"
    ;;
  "postgres flexible-server db")
    printf '%s\n' "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-portable-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/portable-pg-test/databases/maf_workflow"
    ;;
  "postgres flexible-server firewall-rule")
    case "$4" in
      show) printf '%s\t%s\t%s\n' "allow-bootstrap-runner" "8.8.8.8" "8.8.8.8" ;;
      delete)
        [[ "${FAKE_FIREWALL_DELETE_FAIL:-false}" != "true" ]] || exit 73
        : >"$FAKE_FIREWALL_SENTINEL"
        ;;
      list)
        [[ "${FAKE_FIREWALL_LIST_FAIL:-false}" != "true" ]] || exit 75
        if [[ "$*" == *"length("* ]]; then
          if [[ "${FAKE_FIREWALL_VERIFY_FAIL:-false}" == "true" ]]; then printf '%s\n' "1"
          elif [[ -f "$FAKE_FIREWALL_SENTINEL" ]]; then printf '%s\n' "0"
          else printf '%s\n' "1"
          fi
        elif [[ ! -f "$FAKE_FIREWALL_SENTINEL" ]]; then
          printf '%s\t%s\t%s\n' "allow-bootstrap-runner" "8.8.8.8" "8.8.8.8"
        fi
        ;;
      *) echo "unexpected firewall invocation: $*" >&2; exit 99 ;;
    esac
    ;;
  *) echo "unexpected az invocation: $*" >&2; exit 99 ;;
esac
EOF

cat >"$FAKE_BIN/azd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "$1 ${2:-}" in
  "env new") exit 1 ;;
  "env select") printf '%s\n' "select ${3:-}" >>"$AZD_LOG" ;;
  "env set")
    if [[ -n "${FAKE_AZD_SET_FAIL_ONCE_SENTINEL:-}" &&
      ! -f "$FAKE_AZD_SET_FAIL_ONCE_SENTINEL" ]]; then
      : >"$FAKE_AZD_SET_FAIL_ONCE_SENTINEL"
      exit 74
    fi
    printf '%s\n' "set $3=$4" >>"$AZD_LOG"
    ;;
  "env get-value")
    case "$3" in
      AZURE_SUBSCRIPTION_ID) printf '%s\n' "11111111-1111-4111-8111-111111111111" ;;
      AZURE_RESOURCE_GROUP) printf '%s\n' "rg-portable-azure" ;;
      AZURE_LOCATION) printf '%s\n' "regionone" ;;
      AZURE_POSTGRES_HOST) printf '%s\n' "portable-pg-test.postgres.database.azure.com" ;;
      AZURE_POSTGRES_DATABASE) printf '%s\n' "maf_workflow" ;;
      POSTGRES_BOOTSTRAP_ALLOWED_IP) printf '%s\n' "8.8.8.8" ;;
      *) echo "unexpected azd value: $3" >&2; exit 99 ;;
    esac
    ;;
  *) echo "unexpected azd invocation: $*" >&2; exit 99 ;;
esac
EOF

cat >"$FAKE_BIN/python3" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 "$@"
EOF
chmod 700 "$FAKE_BIN"/*

azd_log="$TEST_DIR/azd.log"
output="$(
  PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  AZD_LOG="$azd_log" \
  POSTGRES_BOOTSTRAP_ALLOWED_IP=8.8.8.8 \
  BACKEND_IMAGE=registry.example/backend:v1 \
  FRONTEND_IMAGE=registry.example/frontend:v1 \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME=operator@example.com \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID=11111111-1111-1111-1111-111111111111 \
  "$ROOT_DIR/scripts/release/prepare-bootstrap-environment.sh"
)"

for expected in \
  "set AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
  "set AZURE_TENANT_ID=$TENANT_ID" \
  "set AZURE_RESOURCE_GROUP=$RESOURCE_GROUP" \
  "set AZURE_LOCATION=$LOCATION" \
  "set INFRASTRUCTURE_MODE=bootstrap" \
  "set POSTGRES_SKU_NAME=Standard_B1ms" \
  "set POSTGRES_SKU_TIER=Burstable" \
  "set POSTGRES_VERSION=16" \
  "set POSTGRES_BOOTSTRAP_ALLOWED_IP=8.8.8.8" \
  "set BACKEND_IMAGE=registry.example/backend:v1" \
  "set FRONTEND_IMAGE=registry.example/frontend:v1"; do
  grep -Fq "$expected" "$azd_log"
done
for expected in \
  "set FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME=GlobalStandard" \
  "set FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME=GlobalStandard" \
  "set FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME=GlobalStandard" \
  "set FOUNDRY_EVALUATION_OPERATOR_PRINCIPAL_ID=11111111-1111-1111-1111-111111111111"; do
  grep -Fq "$expected" "$azd_log"
done

firewall_sentinel="$TEST_DIR/firewall-deleted"
PATH="$FAKE_BIN:/usr/bin:/bin" \
AZURE_HOSTED_PROFILE="$PROFILE" \
AZD_LOG="$azd_log" \
FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
"$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh"
[[ -f "$firewall_sentinel" ]]
grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$azd_log"
grep -Fq "set POSTGRES_BOOTSTRAP_ALLOWED_IP=" "$azd_log"

failed_transition_log="$TEST_DIR/failed-transition-azd.log"
rm -f "$firewall_sentinel"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  AZD_LOG="$failed_transition_log" \
  FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
  FAKE_FIREWALL_DELETE_FAIL=true \
  "$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh" \
  >"$TEST_DIR/failed-transition.log" 2>&1; then
  echo "Steady-state transition succeeded after firewall deletion failed." >&2
  exit 1
fi
[[ ! -e "$failed_transition_log" ]] ||
  ! grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$failed_transition_log"

verification_failure_log="$TEST_DIR/verification-failure-azd.log"
rm -f "$firewall_sentinel"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  AZD_LOG="$verification_failure_log" \
  FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
  FAKE_FIREWALL_VERIFY_FAIL=true \
  "$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh" \
  >"$TEST_DIR/verification-failure.log" 2>&1; then
  echo "Steady-state transition succeeded without verified firewall deletion." >&2
  exit 1
fi
grep -Fq "deletion could not be verified" "$TEST_DIR/verification-failure.log"
[[ ! -e "$verification_failure_log" ]] ||
  ! grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$verification_failure_log"

retry_azd_log="$TEST_DIR/retry-azd.log"
azd_failure_sentinel="$TEST_DIR/azd-update-failed-once"
rm -f "$firewall_sentinel"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  AZD_LOG="$retry_azd_log" \
  FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
  FAKE_AZD_SET_FAIL_ONCE_SENTINEL="$azd_failure_sentinel" \
  "$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh" \
  >"$TEST_DIR/azd-update-failure.log" 2>&1; then
  echo "Transition unexpectedly succeeded when the first AZD update failed." >&2
  exit 1
fi
[[ -f "$firewall_sentinel" && -f "$azd_failure_sentinel" ]]
[[ ! -e "$retry_azd_log" ]] ||
  ! grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$retry_azd_log"

PATH="$FAKE_BIN:/usr/bin:/bin" \
AZURE_HOSTED_PROFILE="$PROFILE" \
AZD_LOG="$retry_azd_log" \
FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
FAKE_AZD_SET_FAIL_ONCE_SENTINEL="$azd_failure_sentinel" \
"$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh" \
>"$TEST_DIR/azd-update-retry.log"
grep -Fq "already absent" "$TEST_DIR/azd-update-retry.log"
grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$retry_azd_log"
grep -Fq "set POSTGRES_BOOTSTRAP_ALLOWED_IP=" "$retry_azd_log"

lookup_failure_log="$TEST_DIR/lookup-failure-azd.log"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  AZD_LOG="$lookup_failure_log" \
  FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
  FAKE_FIREWALL_LIST_FAIL=true \
  "$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh" \
  >"$TEST_DIR/lookup-failure.log" 2>&1; then
  echo "Transition unexpectedly succeeded after an ambiguous firewall lookup failure." >&2
  exit 1
fi
[[ ! -e "$lookup_failure_log" ]] ||
  ! grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$lookup_failure_log"

wrong_profile="$TEST_DIR/wrong-target.env"
sed \
  "s/$SUBSCRIPTION_ID/33333333-3333-4333-8333-333333333333/" \
  "$PROFILE" >"$wrong_profile"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
  AZURE_HOSTED_PROFILE="$PROFILE" \
  BOOTSTRAP_PROFILE="$wrong_profile" \
  AZD_LOG="$TEST_DIR/wrong-target-azd.log" \
  POSTGRES_BOOTSTRAP_ALLOWED_IP=8.8.8.8 \
  BACKEND_IMAGE=registry.example/backend:v1 \
  FRONTEND_IMAGE=registry.example/frontend:v1 \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME=operator@example.com \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID=11111111-1111-1111-1111-111111111111 \
  "$ROOT_DIR/scripts/release/prepare-bootstrap-environment.sh" \
  >"$TEST_DIR/wrong-target.log" 2>&1; then
  echo "Bootstrap preparation accepted an unapproved subscription." >&2
  exit 1
fi
grep -Fq "Selected Azure subscription does not match" "$TEST_DIR/wrong-target.log"

python3 - "$ROOT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
template = (root / "infra/azure-apphosted/iac/main.bicep").read_text(encoding="utf-8")
parameters = json.loads(
    (root / "infra/azure-apphosted/iac/main.parameters.json").read_text(encoding="utf-8")
)

for required in (
    "subscription().subscriptionId == targetSubscriptionId",
    "fail('The active deployment subscription is not approved for this lane.')",
    "infrastructureMode == 'bootstrap'",
    "module postgres './modules/postgres-flexible-server.bicep' = if",
    "param backendImage string",
    "param frontendImage string",
    "param foundryEmbeddingsDeploymentSkuName string = 'DataZoneStandard'",
    "param foundryChatDeploymentSkuName string = 'Standard'",
    "param foundryEvaluatorDeploymentSkuName string = 'Standard'",
    "module backend './modules/container-app.bicep' = if (infrastructureMode == 'bootstrap')",
    "module frontend './modules/container-app.bicep' = if (infrastructureMode == 'bootstrap')",
):
    if required not in template:
        raise SystemExit(f"Missing portability IaC contract: {required}")

target_parameter_section = template.split(
    "@description('Infrastructure lifecycle mode.", 1
)[0]
if "@allowed([" in target_parameter_section:
    raise SystemExit("Tracked IaC target parameters must not contain concrete allowlists.")

if "python:3.12-alpine" in template or "placeholderImage" in template:
    raise SystemExit("Tracked IaC still contains a silently deployable placeholder image.")

required_parameters = {
    "targetSubscriptionId",
    "resourceGroupName",
    "infrastructureMode",
    "postgresSkuName",
    "postgresSkuTier",
    "postgresVersion",
    "backendImage",
    "frontendImage",
    "foundryEvaluationOperatorPrincipalId",
    "foundryEvaluatorDeploymentSkuName",
}
missing = required_parameters - parameters["parameters"].keys()
if missing:
    raise SystemExit(f"Missing hardened parameter bindings: {sorted(missing)}")

if (root / "infra/azure-apphosted/iac/parameters.dev.json").exists():
    raise SystemExit("Tracked deployable placeholder parameter file still exists.")

for path in (
    root / "infra/azure-apphosted/iac/main.bicep",
    root / "infra/azure-apphosted/iac/modules/foundry.bicep",
):
    if "GlobalStandard" in path.read_text(encoding="utf-8"):
        raise SystemExit(f"Bootstrap defaults must not assume exhausted GlobalStandard quota: {path}")

foundry_module = (
    root / "infra/azure-apphosted/iac/modules/foundry.bicep"
).read_text(encoding="utf-8")
evaluation_operator_assignment = foundry_module.split(
    "resource evaluationOperatorFoundryUserRoleAssignment", 1
)[1].split("resource evaluatorDeployment", 1)[0]
for required in (
    "name: guid(account.id, evaluationOperatorPrincipalId",
    "scope: account",
    "'53ca6127-db72-4b80-b1b0-d745d6d5456d'",
):
    if required not in evaluation_operator_assignment:
        raise SystemExit(
            f"Missing account-scoped Foundry evaluation operator contract: {required}"
        )
if "scope: project" in evaluation_operator_assignment:
    raise SystemExit("Foundry evaluation operator must not be scoped only to the project.")

reconcile = (root / "scripts/release/reconcile-infrastructure.sh").read_text(
    encoding="utf-8"
)
for required in (
    '"infrastructureMode=steadyState"',
    "steadyState mode must exclude it",
    "require_selected_target",
):
    if required not in reconcile:
        raise SystemExit(f"Missing steady-state reconciliation guard: {required}")

grant = (root / "scripts/azure/grant-postgres-identity.sh").read_text(encoding="utf-8")
for required in ("INFRASTRUCTURE_MODE", "Skipping PostgreSQL bootstrap grants in steadyState mode."):
    if required not in grant:
        raise SystemExit(f"Missing post-bootstrap grant guard: {required}")

schema_transition = (
    root / "scripts/azure/apply-postgres-schema.sh"
).read_text(encoding="utf-8")
for required in (
    "backend/app/sql/schema.sql",
    "REVOKE CREATE ON SCHEMA public",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES",
    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES",
    '[[ "$verification" == "f|t|t|t|0" ]]',
):
    if required not in schema_transition:
        raise SystemExit(f"Missing administrator-owned schema transition contract: {required}")

makefile = (root / "Makefile").read_text(encoding="utf-8")
if "prepare-steady-state:\n\t./scripts/azure/apply-postgres-schema.sh" not in makefile:
    raise SystemExit("Steady-state target does not apply the administrator-owned schema first.")

transition = (
    root / "scripts/release/transition-bootstrap-to-steady-state.sh"
).read_text(encoding="utf-8")
for required in (
    "postgres flexible-server db show",
    "INFRASTRUCTURE_MODE steadyState",
    "PostgreSQL server/database identity could not be verified",
    "firewall-rule delete",
    "allow-bootstrap-runner",
    "Bootstrap firewall rule deletion could not be verified",
):
    if required not in transition:
        raise SystemExit(f"Missing steady-state transition contract: {required}")
PY

echo "Subscription portability bootstrap and steady-state contracts passed."
