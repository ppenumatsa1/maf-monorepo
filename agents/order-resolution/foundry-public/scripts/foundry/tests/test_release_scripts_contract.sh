#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scratch_dir="$root_dir/backend/.tmp/release-script-contract-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

for script in \
  "$root_dir/scripts/foundry/preflight_models.sh" \
  "$root_dir/scripts/foundry/preview_public_infrastructure.sh" \
  "$root_dir/scripts/foundry/verify_runtime_secret_connection.sh" \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh" \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh" \
  "$root_dir/scripts/foundry/verify_evaluator_rbac.sh" \
  "$root_dir/scripts/foundry/hosted_smoke.sh" \
  "$root_dir/scripts/foundry/verify_deployment.sh" \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh" \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"; do
  bash -n "$script"
done

grep -Fq 'deployment/profiles/*.env' "$root_dir/.gitignore"
git -C "$root_dir" check-ignore --no-index -q deployment/profiles/foundry-public.env
grep -Fq 'FOUNDRY_DEPLOYMENT_PROFILE:-$ROOT_DIR/deployment/profiles/foundry-public.env' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq '[[ "$INFRASTRUCTURE_MODE" == "reuse" ]]' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq '.artifacts/releases/$FOUNDRY_RELEASE_ID' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'FOUNDRY_PREVIEW_EVIDENCE_FILE' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'release_evidence.py finalize' "$root_dir/Makefile"

grep -Fq 'Cognitive Services OpenAI User' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq 'Foundry User' \
  "$root_dir/scripts/foundry/verify_evaluator_rbac.sh"
grep -Fq 'Cognitive Services OpenAI User' \
  "$root_dir/scripts/foundry/verify_evaluator_rbac.sh"
grep -Fq -- '--assignee-object-id' \
  "$root_dir/scripts/foundry/verify_evaluator_rbac.sh"
grep -A3 '^foundry-release-preflight:' "$root_dir/Makefile" |
  grep -Fq 'foundry-evaluator-rbac-check'
grep -Fq -- '--assignee-object-id' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq '"cognitiveservices",' \
  "$root_dir/scripts/foundry/capacity_preflight.py"
grep -Fq '"usage",' "$root_dir/scripts/foundry/capacity_preflight.py"
! grep -Eq 'deployment (create|update|delete)' \
  "$root_dir/scripts/foundry/preflight_models.sh"
grep -Fq -- '--mode "$CAPACITY_MODE"' "$root_dir/scripts/foundry/preflight_models.sh"
grep -Fq 'FOUNDRY_CAPACITY_MODE=full_infra' "$root_dir/Makefile"
grep -Fq 'azd provision --preview --no-prompt' \
  "$root_dir/scripts/foundry/preview_public_infrastructure.sh"
grep -Fq 'validate_preview_output.py' \
  "$root_dir/scripts/foundry/preview_public_infrastructure.sh"
grep -A2 '^foundry-release-preflight:' "$root_dir/Makefile" |
  grep -Fq 'foundry-reuse-preview'
grep -A2 '^foundry-provision-preview:' "$root_dir/Makefile" |
  grep -Fq 'FOUNDRY_PREVIEW_MODE=full_infra'
grep -Fq 'FOUNDRY_RUNTIME_CONNECTION_NAME' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
grep -Fq 'properties.metadata.ApiType' \
  "$root_dir/scripts/foundry/verify_runtime_secret_connection.sh"
grep -Fq 'rm -f -- "$PARAMETER_FILE"' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
grep -Fq -- '--subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
grep -Fq 'credentials.database_url' \
  "$root_dir/scripts/foundry/deploy_hosted_container.py"
! grep -Fq 'require("RUNTIME_DATABASE_URL")' \
  "$root_dir/scripts/foundry/deploy_hosted_container.py"
! grep -Fq 'require("RUNTIME_DATABASE_URL")' \
  "$root_dir/scripts/foundry/verify_hosted_agent.py"
grep -Fq -- '--subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq -- '--subscription "$SUBSCRIPTION_ID"' \
  "$root_dir/scripts/foundry/verify_telemetry.sh"
grep -Fq '    - task_completion' "$root_dir/backend/eval.yaml"
grep -Fq '    - coherence' "$root_dir/backend/eval.yaml"
grep -Fq 'FOUNDRY_EVAL_ERROR_RETRY_ATTEMPTS' \
  "$root_dir/scripts/foundry/run_foundry_eval.sh"
grep -Fq 'and ([$results[] | (.failed // 0)] | add) == 0' \
  "$root_dir/scripts/foundry/run_foundry_eval.sh"

for script in \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh"; do
  grep -Fq '@${image_digest}' "$script"
done

python3 - \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh" \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/preflight_models.sh" \
  "$root_dir/scripts/foundry/verify_deployment.sh" <<'PY'
import re
import sys
from pathlib import Path

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    source = path.read_text(encoding="utf-8")
    assert not re.search(
        r"AZURE_SUBSCRIPTION_ID\s*[:=]\s*['\"]?[0-9a-fA-F]{8}-",
        source,
    ), path
    assert not re.search(
        r"AZURE_RESOURCE_GROUP\s*[:=]\s*['\"]?rg-[A-Za-z0-9-]+",
        source,
    ), path
PY

grep -Fq 'subscription_id="$(require_env AZURE_SUBSCRIPTION_ID' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'az account set --subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'AZURE_SUBSCRIPTION_ID="$(required_env AZURE_SUBSCRIPTION_ID)"' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'az account set --subscription "$AZURE_SUBSCRIPTION_ID"' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'ensure_hosted_agent_rbac.sh" verify' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'foundry-runtime-connection-check' "$root_dir/Makefile"
! grep -A8 '^foundry-release-deploy:' "$root_dir/Makefile" |
  grep -Fq 'foundry-runtime-connection-ready'
grep -A8 '^foundry-release-deploy:' "$root_dir/Makefile" |
  grep -Fq '$(MAKE) -j3 foundry-deploy-ready foundry-backend-deploy-ready foundry-frontend-deploy-ready'

az bicep build \
  --file "$root_dir/infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep" \
  --stdout | python3 -c '
import json
import sys

template = json.load(sys.stdin)
assert template["parameters"]["runtimeDatabaseUrl"]["type"] == "securestring"
assert "defaultValue" not in template["parameters"]["runtimeConnectionName"]
resources = template["resources"]
connections = [
    item for item in resources
    if item["type"] == "Microsoft.CognitiveServices/accounts/projects/connections"
]
assert len(connections) == 1
properties = connections[0]["properties"]
assert properties["category"] == "CustomKeys"
assert properties["authType"] == "CustomKeys"
assert "database_url" in properties["credentials"]["keys"]
'

if FOUNDRY_DEPLOY_MODE=full \
  bash "$root_dir/scripts/foundry/deploy_public_dev.sh" \
  >"$scratch_dir/deploy-mode-contract.out" 2>&1; then
  echo "FOUNDRY_DEPLOY_MODE override must be rejected." >&2
  exit 1
fi
grep -Fq 'FOUNDRY_DEPLOY_MODE is no longer supported' \
  "$scratch_dir/deploy-mode-contract.out"

router_fixture="$scratch_dir/router-fixture"
mkdir -p "$router_fixture/scripts/skills" "$router_fixture/infra"
cp "$root_dir/scripts/skills/deployment-mode-router.sh" \
  "$router_fixture/scripts/skills/deployment-mode-router.sh"
git -C "$router_fixture" init -q
git -C "$router_fixture" config user.email test@example.invalid
git -C "$router_fixture" config user.name "Release Router Test"
printf 'baseline\n' >"$router_fixture/infra/main.bicep"
git -C "$router_fixture" add infra/main.bicep scripts/skills/deployment-mode-router.sh
git -C "$router_fixture" commit -qm baseline
printf 'reviewed change\n' >>"$router_fixture/infra/main.bicep"

router_blocked="$(bash "$router_fixture/scripts/skills/deployment-mode-router.sh" HEAD)"
grep -Fq 'release_permitted=false' <<<"$router_blocked"
grep -Fq 'infrastructure_reconciliation=required' <<<"$router_blocked"

router_reconciled="$(
  FOUNDRY_INFRA_RECONCILED=true \
    bash "$router_fixture/scripts/skills/deployment-mode-router.sh" HEAD
)"
grep -Fq 'release_permitted=true' <<<"$router_reconciled"
grep -Fq 'validation_mode=full' <<<"$router_reconciled"
grep -Fq 'infrastructure_reconciliation=reviewed_applied' <<<"$router_reconciled"

if FOUNDRY_FULL_INFRA_AUTHORIZED=true \
  bash "$root_dir/scripts/foundry/deploy_public_dev.sh" \
  >"$scratch_dir/release-authority-contract.out" 2>&1; then
  echo "App-only release must reject full infrastructure authority." >&2
  exit 1
fi
grep -Fq 'cannot be combined with an app-only release' \
  "$scratch_dir/release-authority-contract.out"

if FOUNDRY_FULL_INFRA_AUTHORIZED= \
  make -C "$root_dir" foundry-provision \
  >"$scratch_dir/full-infra-authority.out" 2>&1; then
  echo "Full infrastructure apply must require explicit authority." >&2
  exit 1
fi
grep -Fq 'FOUNDRY_FULL_INFRA_AUTHORIZED=true' \
  "$scratch_dir/full-infra-authority.out"

for target in \
  foundry-provision-ready foundry-postgres-schema foundry-postgres-credentials \
  foundry-runtime-connection foundry-runtime-connection-ready foundry-hosted-rbac \
  foundry-teams-deploy-bot; do
  grep -A3 "^${target}:" "$root_dir/Makefile" |
    grep -Fq 'FOUNDRY_FULL_INFRA_AUTHORIZED'
done
