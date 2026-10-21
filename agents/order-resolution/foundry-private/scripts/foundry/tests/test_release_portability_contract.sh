#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
scripts_dir="$root_dir/scripts/foundry"
profile_path="$root_dir/../deployment/profiles/foundry-private.env"

bash "$root_dir/../deployment/profile.sh" validate "$profile_path"
python3 -m unittest "$scripts_dir/tests/test_private_profile_selection.py"

scoped_files=(
  "$root_dir/Makefile"
  "$scripts_dir/bootstrap_private_azd_environment.sh"
  "$scripts_dir/build_python_wheelhouse.sh"
  "$scripts_dir/ensure_foundry_azd_defaults.sh"
  "$scripts_dir/validate_private_runner_environment.sh"
  "$scripts_dir/preflight_private_release.sh"
  "$scripts_dir/deploy_private_app_release.sh"
  "$scripts_dir/deploy_hosted_container.sh"
  "$scripts_dir/ensure_backend_venv.sh"
  "$scripts_dir/verify_private_postgres_readiness.sh"
  "$scripts_dir/collect_private_release_evidence.sh"
  "$scripts_dir/release_record.py"
  "$scripts_dir/migrate_release_history.py"
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
if grep -En 'azd env get-value.*\|\| true' "${scoped_files[@]}"; then
  echo "Missing AZD values must not be replaced by azd error text from stdout." >&2
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
grep -Fq 'HOSTED_AGENT_SKIP_BUILD=true' "$scripts_dir/deploy_private_app_release.sh"
grep -Fq 'Reusing backend virtual environment' "$scripts_dir/ensure_backend_venv.sh"
grep -Fq 'BACKEND_PYTHON_BIN' "$scripts_dir/ensure_backend_venv.sh"
grep -Fq '"$HOME/.local/bin/uv" python install 3.13' \
  "$root_dir/scripts/github/bootstrap_vm_runner_host.sh"
grep -Fq 'type: "function_call_output"' \
  "$root_dir/scripts/github/foundry_hosted_e2e.sh"
grep -Fq -- '--data-binary "@$PAYLOAD_FILE"' \
  "$root_dir/scripts/github/foundry_hosted_e2e.sh"
if grep -Fq -- '--input-file "$PAYLOAD_FILE"' \
  "$root_dir/scripts/github/foundry_hosted_e2e.sh"; then
  echo "Hosted E2E must not pass Responses JSON through AZD --input-file." >&2
  exit 1
fi
if grep -Eq '\{input: \$input, decision: "approve", checkpoint_id:' \
  "$root_dir/scripts/github/foundry_hosted_e2e.sh"; then
  echo "Hosted E2E approvals must use structured function_call_output input." >&2
  exit 1
fi
grep -Fq '$(abspath $(PRIVATE_DEPLOYMENT_PROFILE))' "$root_dir/Makefile"
grep -Fq 'Reusing successful hosted E2E evidence from the active release.' \
  "$scripts_dir/collect_private_release_evidence.sh"
grep -Fq 'Reusing successful telemetry evidence from the active release.' \
  "$scripts_dir/collect_private_release_evidence.sh"
grep -Fq 'def release_root' "$scripts_dir/release_record.py"
grep -Fq '"mode": "dry-run"' "$scripts_dir/migrate_release_history.py"
grep -Fq 'PRIVATE_RELEASE_PREREQUISITES_PASSED=true' "$root_dir/Makefile"
grep -Fq -- '--platform manylinux2014_x86_64' \
  "$scripts_dir/build_python_wheelhouse.sh"
for target in up docker-test foundry-app-deploy foundry-hosted-app-deploy foundry-app-only-release; do
  grep -Eq "^${target}:.*foundry-python-wheelhouse" "$root_dir/Makefile"
done
grep -Fq '"$ROOT_DIR/scripts/foundry/preflight_private_release.sh"' \
  "$scripts_dir/provision_private_infrastructure.sh"

echo "Private release portability contract passed."
