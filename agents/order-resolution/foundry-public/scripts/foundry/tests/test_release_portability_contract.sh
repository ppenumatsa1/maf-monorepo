#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scripts_dir="$root_dir/scripts/foundry"
scratch_dir="$root_dir/backend/.tmp/wheelhouse-portability-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

for script in \
  "$scripts_dir/build_python_wheelhouse.sh" \
  "$scripts_dir/ensure_backend_venv.sh" \
  "$scripts_dir/preflight_models.sh" \
  "$scripts_dir/preview_public_infrastructure.sh" \
  "$scripts_dir/sync_hosted_source.sh"; do
  bash -n "$script"
done

grep -Fq 'FROM python:3.13' "$root_dir/backend/Dockerfile"
grep -Fq 'FROM python:3.13' "$root_dir/backend/Dockerfile.hosted"
for dockerfile in "$root_dir/backend/Dockerfile" "$root_dir/backend/Dockerfile.hosted"; do
  grep -Fq -- '--no-index --find-links=/wheels' "$dockerfile"
  grep -Fq -- '--require-hashes -r requirements.lock' "$dockerfile"
  grep -Fq 'PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple' "$dockerfile"
done

grep -Fq 'BACKEND_PYTHON_BIN' "$scripts_dir/ensure_backend_venv.sh"
grep -Fq 'python3.13 python3.12 python3.11' "$scripts_dir/ensure_backend_venv.sh"
grep -Fq 'Backend dependencies require Python 3.11 or newer' \
  "$scripts_dir/ensure_backend_venv.sh"
grep -Fq -- '--index-url "https://packagefeedproxy.microsoft.io/pypi/simple"' \
  "$scripts_dir/ensure_backend_venv.sh"
grep -Fq -- '--extra-index-url "https://pypi.org/simple"' \
  "$scripts_dir/ensure_backend_venv.sh"

selector_bin="$scratch_dir/selector-bin"
mkdir -p "$selector_bin" "$scratch_dir/selector-home"
cat >"$selector_bin/python3.13" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$(basename "$0")" >>"$PYTHON_SELECTION_LOG"
exec /usr/bin/python3 "$@"
SH
chmod +x "$selector_bin/python3.13"
cp "$selector_bin/python3.13" "$selector_bin/python3.12"
cp "$selector_bin/python3.13" "$selector_bin/python3.11"
PYTHON_SELECTION_LOG="$scratch_dir/python-selection.log" \
  PATH="$selector_bin:/usr/bin:/bin" \
  HOME="$scratch_dir/selector-home" \
  "$scripts_dir/ensure_backend_venv.sh" >/dev/null
[[ "$(cat "$scratch_dir/python-selection.log")" == "python3.13" ]]

mkdir -p "$scratch_dir/python310"
cat >"$scratch_dir/python310/sitecustomize.py" <<'PY'
import sys

sys.version_info = (3, 10, 0, "final", 0)
PY
if PYTHONPATH="$scratch_dir/python310" \
  BACKEND_PYTHON_BIN=/usr/bin/python3 \
  "$scripts_dir/ensure_backend_venv.sh" \
  >"$scratch_dir/python310.out" 2>&1; then
  echo "Backend environment accepted Python older than 3.11." >&2
  exit 1
fi
grep -Fq 'Backend dependencies require Python 3.11 or newer' \
  "$scratch_dir/python310.out"

grep -Fq -- '--platform manylinux2014_x86_64' \
  "$scripts_dir/build_python_wheelhouse.sh"
grep -Fq -- '--python-version 3.13' "$scripts_dir/build_python_wheelhouse.sh"
grep -Fq -- '--implementation cp' "$scripts_dir/build_python_wheelhouse.sh"
grep -Fq -- '--abi cp313' "$scripts_dir/build_python_wheelhouse.sh"
grep -Fq -- '--require-hashes' "$scripts_dir/build_python_wheelhouse.sh"
grep -Fq 'backend/.wheels/' "$root_dir/.gitignore"
git -C "$root_dir" check-ignore -q backend/.wheels/contract-test.whl

for target in \
  up \
  docker-test \
  foundry-package \
  foundry-backend-deploy-ready \
  foundry-app-deploy \
  foundry-deploy \
  foundry-deploy-ready \
  foundry-release-deploy \
  foundry-up \
  foundry-release; do
  grep -Eq "^${target}:.*foundry-python-wheelhouse" "$root_dir/Makefile"
done
grep -Fq '$(MAKE) foundry-deploy-ready' "$root_dir/Makefile"
grep -Fq '$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy-ready' \
  "$root_dir/Makefile"
grep -Fq 'Automatic app-only release refused an infrastructure change.' \
  "$scripts_dir/deploy_public_dev.sh"
grep -Fq 'FOUNDRY_FULL_INFRA_AUTHORIZED=true' "$root_dir/Makefile"
for deploy_script in \
  "$scripts_dir/deploy_public_backend.sh" \
  "$scripts_dir/deploy_hosted_container.sh"; do
  grep -Fq 'validate_python_wheelhouse.py' "$deploy_script"
done

fixture_root="$scratch_dir/clean-clone"
mkdir -p \
  "$fixture_root/backend/foundry" \
  "$fixture_root/scripts/foundry" \
  "$fixture_root/infra/foundry-hosted"
cp "$scripts_dir/build_python_wheelhouse.sh" \
  "$scripts_dir/sync_hosted_source.sh" \
  "$scripts_dir/validate_python_wheelhouse.py" \
  "$fixture_root/scripts/foundry/"
cp "$root_dir/backend/Dockerfile.hosted" "$fixture_root/backend/Dockerfile.hosted"
cp "$root_dir/backend/requirements.txt" "$fixture_root/backend/requirements.txt"
cp "$root_dir/backend/requirements.lock" "$fixture_root/backend/requirements.lock"
printf 'print("fixture")\n' >"$fixture_root/backend/foundry/main.py"
printf '#!/usr/bin/env bash\n' >"$fixture_root/fake-python"
cat >>"$fixture_root/fake-python" <<'SH'
set -euo pipefail
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "download" ]]; then
  args=" $* "
  for required in \
    " --platform manylinux2014_x86_64 " \
    " --python-version 3.13 " \
    " --implementation cp " \
    " --abi cp313 " \
    " --require-hashes "; do
    [[ "$args" == *"$required"* ]] || {
      echo "Missing cross-platform wheel argument:$required" >&2
      exit 1
    }
  done
  while [[ "$#" -gt 0 ]]; do
    if [[ "$1" == "--dest" ]]; then
      mkdir -p "$2"
      : >"$2/fixture-1.0-py3-none-any.whl"
      exit 0
    fi
    shift
  done
  exit 1
fi
exec python3 "$@"
SH
chmod +x "$fixture_root/fake-python"

[[ ! -e "$fixture_root/backend/.wheels" ]]
PYTHON_BIN="$fixture_root/fake-python" \
  "$fixture_root/scripts/foundry/build_python_wheelhouse.sh"
[[ -f "$fixture_root/backend/.wheels/fixture-1.0-py3-none-any.whl" ]]
"$fixture_root/scripts/foundry/sync_hosted_source.sh"
[[ -f "$fixture_root/infra/foundry-hosted/agent/.wheels/fixture-1.0-py3-none-any.whl" ]]

wrong_wheels="$scratch_dir/wrong-platform"
mkdir -p "$wrong_wheels"
: >"$wrong_wheels/fixture-1.0-cp313-cp313-manylinux2014_aarch64.whl"
if python3 "$scripts_dir/validate_python_wheelhouse.py" "$wrong_wheels" \
  >"$scratch_dir/wrong-platform.out" 2>&1; then
  echo "Wheel validation accepted an ARM64 wheel for the AMD64 image." >&2
  exit 1
fi
grep -Fq 'incompatible with CPython 3.13 Linux AMD64' \
  "$scratch_dir/wrong-platform.out"

python3 -m unittest discover -s "$scripts_dir/tests" -p 'test_capacity_preflight.py'
python3 -m unittest discover -s "$scripts_dir/tests" -p 'test_preview_safety.py'
bash "$root_dir/deployment/tests/test-profile.sh"

git -C "$root_dir" check-ignore --no-index -q deployment/profiles/foundry-public.env
[[ ! -e "$root_dir/deployment/profiles/foundry-public.env" ]]
if grep -En \
  'AZURE_SUBSCRIPTION_ID=[0-9a-fA-F-]{36}|AZURE_RESOURCE_GROUP=rg-[A-Za-z0-9-]+|legacy_pending_cutover' \
  "$root_dir/Makefile" \
  "$scripts_dir/deploy_public_dev.sh" \
  "$scripts_dir/preflight_models.sh" \
  "$scripts_dir/capacity_preflight.py" \
  "$scripts_dir/preview_public_infrastructure.sh"; then
  echo "Target-specific release fallback remains in generic public tooling." >&2
  exit 1
fi
if grep -En 'mktemp|/tmp/' \
  "$scripts_dir/converge_runtime_secret_connection.sh" \
  "$scripts_dir/verify_deployment.sh" \
  "$scripts_dir/preview_public_infrastructure.sh" \
  "$scripts_dir/preflight_models.sh"; then
  echo "Release tooling must keep scratch files inside the ignored project tree." >&2
  exit 1
fi

echo "Public release portability contract passed."
