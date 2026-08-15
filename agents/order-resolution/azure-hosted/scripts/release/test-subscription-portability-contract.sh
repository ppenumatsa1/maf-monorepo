#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TEST_DIR="$ROOT_DIR/.artifacts/subscription-portability-test-$$-$RANDOM"
FAKE_BIN="$TEST_DIR/bin"
PROFILE="$ROOT_DIR/deployment/profiles/azure-hosted.env"

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/az" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "$1 ${2:-} ${3:-}" in
  "account show --subscription")
    printf '%s\n' "7df95e88-701c-4693-af77-3159f83b558d"
    ;;
  "postgres flexible-server show")
    printf '%s\n' "/subscriptions/7df95e88-701c-4693-af77-3159f83b558d/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/maf-ora-azure-pg-test"
    ;;
  "postgres flexible-server db")
    printf '%s\n' "/subscriptions/7df95e88-701c-4693-af77-3159f83b558d/resourceGroups/rg-maf-ora-azure/providers/Microsoft.DBforPostgreSQL/flexibleServers/maf-ora-azure-pg-test/databases/maf_workflow"
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
      AZURE_SUBSCRIPTION_ID) printf '%s\n' "7df95e88-701c-4693-af77-3159f83b558d" ;;
      AZURE_RESOURCE_GROUP) printf '%s\n' "rg-maf-ora-azure" ;;
      AZURE_LOCATION) printf '%s\n' "northcentralus" ;;
      AZURE_POSTGRES_HOST) printf '%s\n' "maf-ora-azure-pg-test.postgres.database.azure.com" ;;
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
  AZD_LOG="$azd_log" \
  POSTGRES_BOOTSTRAP_ALLOWED_IP=8.8.8.8 \
  BACKEND_IMAGE=registry.example/backend:v1 \
  FRONTEND_IMAGE=registry.example/frontend:v1 \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME=operator@example.com \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID=11111111-1111-1111-1111-111111111111 \
  "$ROOT_DIR/scripts/release/prepare-bootstrap-environment.sh"
)"

for expected in \
  "set AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d" \
  "set AZURE_RESOURCE_GROUP=rg-maf-ora-azure" \
  "set AZURE_LOCATION=northcentralus" \
  "set INFRASTRUCTURE_MODE=bootstrap" \
  "set POSTGRES_BOOTSTRAP_ALLOWED_IP=8.8.8.8" \
  "set BACKEND_IMAGE=registry.example/backend:v1" \
  "set FRONTEND_IMAGE=registry.example/frontend:v1"; do
  grep -Fq "$expected" "$azd_log"
done
for expected in \
  "set FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME=Standard" \
  "set FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME=DataZoneStandard" \
  "set FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME=Standard"; do
  grep -Fq "$expected" "$azd_log"
done

firewall_sentinel="$TEST_DIR/firewall-deleted"
PATH="$FAKE_BIN:/usr/bin:/bin" \
AZD_LOG="$azd_log" \
FAKE_FIREWALL_SENTINEL="$firewall_sentinel" \
"$ROOT_DIR/scripts/release/transition-bootstrap-to-steady-state.sh"
[[ -f "$firewall_sentinel" ]]
grep -Fq "set INFRASTRUCTURE_MODE=steadyState" "$azd_log"
grep -Fq "set POSTGRES_BOOTSTRAP_ALLOWED_IP=" "$azd_log"

failed_transition_log="$TEST_DIR/failed-transition-azd.log"
rm -f "$firewall_sentinel"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
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
  's/7df95e88-701c-4693-af77-3159f83b558d/11111111-1111-1111-1111-111111111111/' \
  "$PROFILE" >"$wrong_profile"
if PATH="$FAKE_BIN:/usr/bin:/bin" \
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
grep -Fq "Selected Azure subscription must be" "$TEST_DIR/wrong-target.log"

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

if "python:3.12-alpine" in template or "placeholderImage" in template:
    raise SystemExit("Tracked IaC still contains a silently deployable placeholder image.")

required_parameters = {
    "targetSubscriptionId",
    "resourceGroupName",
    "infrastructureMode",
    "backendImage",
    "frontendImage",
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
