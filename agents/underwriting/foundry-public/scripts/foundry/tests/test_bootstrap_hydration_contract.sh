#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scratch_dir="$root_dir/backend/.tmp/bootstrap-hydration-contract-$$"
bin_dir="$scratch_dir/bin"
command_log="$scratch_dir/commands.log"
mkdir -p "$bin_dir"
trap 'rm -rf "$scratch_dir"' EXIT

cat >"$bin_dir/azd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'azd %s\n' "$*" >>"$COMMAND_LOG"
if [[ "$1 $2" == "env get-value" ]]; then
  case "$3" in
    INFRASTRUCTURE_MODE) echo bootstrap ;;
    AZURE_SUBSCRIPTION_ID) echo 11111111-1111-4111-8111-111111111111 ;;
    AZURE_RESOURCE_GROUP) echo rg-empty-underwriting ;;
    AZURE_LOCATION) echo eastus2 ;;
    FOUNDRY_ACCOUNT_NAME) echo portable-foundry ;;
    FOUNDRY_PROJECT_NAME) echo underwriting ;;
    CONTAINER_REGISTRY_NAME) echo portableacr ;;
    POSTGRES_SERVER_NAME) echo portable-postgres ;;
    CONTAINER_APPS_ENVIRONMENT_NAME) echo portable-cae ;;
    BACKEND_CONTAINER_APP_NAME) echo portable-backend ;;
    PUBLIC_BACKEND_MANAGED_IDENTITY_NAME) echo portable-backend-mi ;;
    FRONTEND_CONTAINER_APP_NAME) echo portable-frontend ;;
    APPLICATION_INSIGHTS_NAME) echo portable-ai ;;
    LOG_ANALYTICS_WORKSPACE_NAME) echo portable-log ;;
    HOSTED_AGENT_NAME) echo underwriting-hosted ;;
    POSTGRES_OPERATOR_IP) echo 203.0.113.10 ;;
  esac
fi
EOF

cat >"$bin_dir/az" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'az %s\n' "$*" >>"$COMMAND_LOG"
case "$1 $2" in
  "account set") exit 0 ;;
  "group exists") echo false ;;
esac
echo "unexpected Azure resource query before bootstrap resources exist" >&2
exit 90
EOF

cat >"$bin_dir/curl" <<'EOF'
#!/usr/bin/env bash
exit 91
EOF

chmod +x "$bin_dir/azd" "$bin_dir/az" "$bin_dir/curl"

PATH="$bin_dir:$PATH" COMMAND_LOG="$command_log" \
  bash "$root_dir/scripts/foundry/bootstrap_azd_env.sh" >/dev/null
! grep -q '^az ' "$command_log"
! grep -Eq 'AZURE_RESOURCE_GROUP|POSTGRES_SERVER_NAME|CONTAINER_REGISTRY_NAME|APPLICATION_INSIGHTS_NAME' \
  "$command_log"

: >"$command_log"
PATH="$bin_dir:$PATH" COMMAND_LOG="$command_log" \
  bash "$root_dir/scripts/foundry/ensure_foundry_azd_defaults.sh" >/dev/null
! grep -q '^az ' "$command_log"
! grep -Fq 'env set INFRASTRUCTURE_MODE reuse' "$command_log"

: >"$command_log"
if PATH="$bin_dir:$PATH" COMMAND_LOG="$command_log" FOUNDRY_BOOTSTRAP_HYDRATE=1 \
  bash "$root_dir/scripts/foundry/bootstrap_azd_env.sh" \
  >"$scratch_dir/hydrate.out" 2>&1; then
  echo "Hydration must fail while the bootstrap resource group is absent." >&2
  exit 1
fi
grep -Fq 'preserving INFRASTRUCTURE_MODE=bootstrap' "$scratch_dir/hydrate.out"
grep -Fq 'az group exists' "$command_log"
! grep -Eq 'postgres flexible-server|acr show|cognitiveservices account|app-insights component' \
  "$command_log"
! grep -Fq 'env set INFRASTRUCTURE_MODE reuse' "$command_log"
