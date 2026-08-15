#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
scripts_dir="$root_dir/scripts/foundry"
profile_path="$root_dir/../deployment/profiles/foundry-private.env"

bash "$root_dir/../deployment/profile.sh" validate "$profile_path"

scoped_files=(
  "$root_dir/Makefile"
  "$scripts_dir/bootstrap_private_azd_environment.sh"
  "$scripts_dir/ensure_foundry_azd_defaults.sh"
  "$scripts_dir/validate_private_runner_environment.sh"
  "$scripts_dir/preflight_private_release.sh"
  "$scripts_dir/deploy_hosted_container.sh"
  "$scripts_dir/verify_private_postgres_readiness.sh"
  "$scripts_dir/collect_private_release_evidence.sh"
  "$scripts_dir/validate_private_app_release.sh"
  "$scripts_dir/verify_private_app_images.sh"
)

if grep -En 'foundry-private-env|rg-maf-ora-foundry-v2|maffndpgv20722|foundry-private-v2|mafprv' "${scoped_files[@]}"; then
  echo "Target-specific legacy defaults remain in private release tooling." >&2
  exit 1
fi

if grep -En '(^|[;&|$(][[:space:]]*)azd[[:space:]]' "${scoped_files[@]}"; then
  echo "Every azd command must set AZURE_DEV_USER_AGENT=microsoft_foundry_skill." >&2
  exit 1
fi

if grep -Eq '^foundry_project_(id|endpoint)="(https://|/subscriptions)' \
  "$scripts_dir/bootstrap_private_azd_environment.sh"; then
  echo "Bootstrap must not pre-construct Foundry project coordinates." >&2
  exit 1
fi
grep -Fq 'az rest' "$scripts_dir/bootstrap_private_azd_environment.sh"

grep -Fq 'FOUNDRY_POST_PROVISION_HYDRATE=1' "$root_dir/Makefile"
grep -Fq 'DB_SCHEMA_MANAGED_EXTERNALLY=true' "$root_dir/Makefile"
grep -Fq '"DB_SCHEMA_MANAGED_EXTERNALLY": require("DB_SCHEMA_MANAGED_EXTERNALLY")' \
  "$scripts_dir/deploy_hosted_container.py"
grep -Fq 'public network access disabled' "$scripts_dir/verify_private_postgres_readiness.sh"
grep -Fq 'postgres_runtime_credentials.py" verify' "$scripts_dir/verify_private_postgres_readiness.sh"

echo "Private release portability contract passed."
