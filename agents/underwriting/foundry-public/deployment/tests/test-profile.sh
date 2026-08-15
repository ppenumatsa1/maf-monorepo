#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
profile="$script_dir/profiles/foundry-public.env"
bootstrap_profile="$script_dir/profiles/foundry-public-bootstrap.env"

for forbidden_key in \
  RUNTIME_DATABASE_URL \
  DATABASE_URL \
  APPLICATIONINSIGHTS_CONNECTION_STRING \
  POSTGRES_ADMIN_PASSWORD \
  AZURE_CONTAINER_REGISTRY_NAME \
  POSTGRES_SERVER_NAME; do
  if grep -q "^${forbidden_key}=" "$profile"; then
    printf 'profile must not contain %s\n' "$forbidden_key" >&2
    exit 1
  fi
done

grep -Fxq 'AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d' "$profile"
grep -Fxq 'AZURE_RESOURCE_GROUP=rg-maf-underwriting' "$profile"
grep -Fxq 'AZURE_LOCATION=eastus2' "$profile"
grep -Fxq 'AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d' "$bootstrap_profile"
grep -Fxq 'AZURE_RESOURCE_GROUP=rg-maf-underwriting' "$bootstrap_profile"
! grep -Eq '00000000-0000-0000-0000-000000000000|203\.0\.113\.10|rg-underwriting-foundry-public' \
  "$profile" "$bootstrap_profile"

scratch_dir="$project_dir/backend/.tmp/profile-contract-$$"
azd_command="$scratch_dir/azd-command"
azd_log="$scratch_dir/azd.log"
bin_dir="$scratch_dir/bin"
bootstrap_log="$scratch_dir/bootstrap.log"
mkdir -p "$bin_dir"
trap 'rm -rf "$scratch_dir"' EXIT

cat > "$azd_command" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$azd_command"

AZD_COMMAND="$azd_command" AZD_LOG="$azd_log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'underwriting/foundry-public/infra/foundry-hosted|env select underwriting-foundry-public --no-prompt' "$azd_log"
grep -Fq 'env set AZURE_SUBSCRIPTION_ID 7df95e88-701c-4693-af77-3159f83b558d --no-prompt' "$azd_log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-maf-underwriting --no-prompt' "$azd_log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$azd_log"
grep -Fq 'env set NAME_PREFIX underwriting' "$azd_log"
! grep -Fq 'agents/order-resolution' "$script_dir/apply-azd-profile.sh"

router_output="$("$project_dir/scripts/skills/deployment-mode-router.sh" HEAD)"
grep -Fxq 'deploy_mode=app_only' <<<"$router_output"

for command in az azd curl; do
  cat > "$bin_dir/$command" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "env" && "$2" == "get-value" ]]; then
  exit 0
fi
printf 'unexpected command: %s\n' "$*" >&2
exit 1
EOF
  chmod +x "$bin_dir/$command"
done

if PATH="$bin_dir:$PATH" bash "$project_dir/scripts/foundry/bootstrap_azd_env.sh" >"$bootstrap_log" 2>&1; then
  printf 'bootstrap must reject a selected environment without target configuration\n' >&2
  exit 1
fi
grep -Fq 'Missing selected AZD environment value: AZURE_SUBSCRIPTION_ID' "$bootstrap_log"

if FOUNDRY_DEPLOY_MODE=full PATH="$bin_dir:$PATH" \
  bash "$project_dir/scripts/foundry/deploy_public_dev.sh" >"$bootstrap_log" 2>&1; then
  printf 'release script must reject FOUNDRY_DEPLOY_MODE overrides\n' >&2
  exit 1
fi
grep -Fq 'FOUNDRY_DEPLOY_MODE overrides are forbidden' "$bootstrap_log"
