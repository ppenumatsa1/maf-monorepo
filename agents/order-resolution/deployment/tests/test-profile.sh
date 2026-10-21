#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

for profile in "$script_dir"/profiles/*.env; do
  bash "$script_dir/profile.sh" validate "$profile"
done

azure_hosted_example="$script_dir/profiles/azure-hosted.env.example"
bash "$script_dir/profile.sh" validate-example "$azure_hosted_example"
if bash "$script_dir/profile.sh" validate "$azure_hosted_example" >/dev/null 2>&1; then
  printf 'expected placeholder Azure-hosted example to fail normal validation\n' >&2
  exit 1
fi
grep -Fq 'AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000' \
  "$azure_hosted_example"
grep -Fq 'AZURE_LOCATION=examplelocation' "$azure_hosted_example"

test_dir="$script_dir/.test-artifacts/profile-$$"
mkdir -p "$test_dir"
invalid_profile="$test_dir/invalid.env"
valid_hosted_profile="$test_dir/azure-hosted.env"
duplicate_profile="$test_dir/duplicate.env"
unknown_profile="$test_dir/unknown.env"
symlink_profile="$test_dir/symlink.env"
azd_command="$test_dir/azd"
azd_log="$test_dir/azd.log"
trap 'rm -rf "$test_dir"' EXIT
sed \
  -e 's/example-azure-hosted/portable-azure-hosted/g' \
  -e 's/00000000-0000-0000-0000-000000000000/11111111-1111-4111-8111-111111111111/' \
  -e 's/rg-example-azure-hosted/rg-portable-azure-hosted/' \
  -e 's/examplelocation/regionone/' \
  -e 's/exampleazure/portableazure/' \
  "$azure_hosted_example" >"$valid_hosted_profile"
bash "$script_dir/profile.sh" validate "$valid_hosted_profile"

cat "$valid_hosted_profile" >"$duplicate_profile"
printf 'AZURE_LOCATION=regiontwo\n' >>"$duplicate_profile"
if bash "$script_dir/profile.sh" validate "$duplicate_profile" >/dev/null 2>&1; then
  printf 'expected duplicate Azure-hosted key to fail\n' >&2
  exit 1
fi

cat "$valid_hosted_profile" >"$unknown_profile"
printf 'UNKNOWN_TARGET_VALUE=value\n' >>"$unknown_profile"
if bash "$script_dir/profile.sh" validate "$unknown_profile" >/dev/null 2>&1; then
  printf 'expected unknown Azure-hosted key to fail\n' >&2
  exit 1
fi

ln -s "$valid_hosted_profile" "$symlink_profile"
if bash "$script_dir/profile.sh" validate "$symlink_profile" >/dev/null 2>&1; then
  printf 'expected symlink Azure-hosted profile to fail\n' >&2
  exit 1
fi
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

env -u AZURE_SUBSCRIPTION_ID -u AZURE_TENANT_ID \
  AZD_COMMAND="$azd_command" AZD_LOG="$azd_log" \
  bash "$script_dir/apply-azd-profile.sh" "$script_dir/profiles/foundry-public.env"

grep -Fq 'foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 00000000-0000-0000-0000-000000000000' "$azd_log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-order-resolution-public-dev' "$azd_log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$azd_log"
grep -Fq 'env set NAME_PREFIX orderpub' "$azd_log"

runtime_subscription="11111111-1111-4111-8111-111111111111"
runtime_tenant="22222222-2222-4222-8222-222222222222"
AZURE_SUBSCRIPTION_ID="$runtime_subscription" \
AZURE_TENANT_ID="$runtime_tenant" \
AZD_COMMAND="$azd_command" AZD_LOG="$azd_log" \
  bash "$script_dir/apply-azd-profile.sh" "$script_dir/profiles/foundry-private.env"

grep -Fq "foundry-private/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID $runtime_subscription" "$azd_log"
grep -Fq "env set AZURE_TENANT_ID $runtime_tenant" "$azd_log"
