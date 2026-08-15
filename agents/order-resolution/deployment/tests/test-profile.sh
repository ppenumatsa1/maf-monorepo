#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

for profile in "$script_dir"/profiles/*.env; do
  bash "$script_dir/profile.sh" validate "$profile"
done

grep -Fq 'DEPLOYMENT_LANE=azure-hosted' "$script_dir/profiles/azure-hosted.env"
grep -Fq 'AZURE_ENV_NAME=maf-ora-azure' "$script_dir/profiles/azure-hosted.env"
grep -Fq 'AZURE_LOCATION=northcentralus' "$script_dir/profiles/azure-hosted.env"
grep -Fq 'agents/order-resolution/deployment/profiles/azure-hosted.env' \
  "$script_dir/../azure-hosted/deployment/profiles/azure-hosted-bootstrap.env"

test_dir="$script_dir/.test-artifacts/profile-$$"
mkdir -p "$test_dir"
invalid_profile="$test_dir/invalid.env"
azd_command="$test_dir/azd"
azd_log="$test_dir/azd.log"
trap 'rm -rf "$test_dir"' EXIT
cat > "$invalid_profile" <<'EOF'
CONTRACT_VERSION=1
DEPLOYMENT_LANE=foundry-public
AZURE_ENV_NAME=order-resolution-public-dev
AZURE_SUBSCRIPTION_ID=not-a-guid
AZURE_RESOURCE_GROUP=rg-order-resolution-public-dev
AZURE_LOCATION=eastus2
NAME_PREFIX=orderpub
EOF

if bash "$script_dir/profile.sh" validate "$invalid_profile" >/dev/null 2>&1; then
  printf 'expected invalid profile to fail\n' >&2
  exit 1
fi

cat > "$azd_command" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$azd_command"

AZD_COMMAND="$azd_command" AZD_LOG="$azd_log" \
  bash "$script_dir/apply-azd-profile.sh" "$script_dir/profiles/foundry-public.env"

grep -Fq 'foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 00000000-0000-0000-0000-000000000000' "$azd_log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-order-resolution-public-dev' "$azd_log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$azd_log"
grep -Fq 'env set NAME_PREFIX orderpub' "$azd_log"
