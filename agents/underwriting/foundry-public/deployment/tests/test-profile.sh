#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
profile="$script_dir/profiles/foundry-public.env"

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

azd_command="$(mktemp)"
azd_log="$(mktemp)"
bin_dir="$(mktemp -d)"
bootstrap_log="$(mktemp)"
trap 'rm -f "$azd_command" "$azd_log" "$bootstrap_log"; rm -rf "$bin_dir"' EXIT

cat > "$azd_command" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$azd_command"

AZD_COMMAND="$azd_command" AZD_LOG="$azd_log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'underwriting/foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 00000000-0000-0000-0000-000000000000' "$azd_log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-underwriting-foundry-public' "$azd_log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$azd_log"
grep -Fq 'env set NAME_PREFIX underwriting' "$azd_log"

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
