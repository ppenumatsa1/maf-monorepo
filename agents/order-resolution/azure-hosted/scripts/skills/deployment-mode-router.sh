#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

base_ref="${1:-HEAD}"
tracked_changes="$(git diff --name-only --relative "$base_ref" -- . || true)"
untracked_changes="$(git ls-files --others --exclude-standard -- . || true)"
changed_files="$(
  printf '%s\n%s\n' "$tracked_changes" "$untracked_changes" \
    | sed '/^$/d' \
    | sort -u
)"

if [[ -z "$changed_files" ]]; then
  echo "deploy_mode=app_only"
  echo "validation_mode=quick"
  echo "infrastructure_action=none"
  echo "reason=no_changed_files"
  exit 0
fi

if grep -Eq '^(deployment/(contracts/|profiles/)|infra/azure-apphosted/iac/|\.azure/|scripts/release/(prepare-bootstrap-environment\.sh|transition-bootstrap-to-steady-state\.sh|reconcile-infrastructure\.sh|run-reconcile-infrastructure\.sh)|scripts/azure/grant-postgres-identity\.sh)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "infrastructure_action=explicit_apply_required"
  echo "reason=infrastructure_contract_or_iac_surface_changed"
  exit 0
fi

if grep -Eq '^(docker-compose\.yml|frontend/Dockerfile|frontend/nginx\.conf|backend/Dockerfile|\.github/workflows/|infra/azure-apphosted/runtime/|scripts/release/|scripts/skills/)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "infrastructure_action=preview_required"
  echo "reason=release_or_runtime_surface_changed"
  exit 0
fi

if grep -Eq '^(frontend/|backend/app/maf/|backend/app/api/v1/schemas/|backend/app/api/v1/routers/|backend/app/modules/order_resolution/|backend/evals/|backend/tests/test_workflow\.py|backend/evals/cases\.jsonl|docs/design/hitl-approval-conditions\.md)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "validation_mode=full"
  echo "infrastructure_action=none"
  echo "reason=frontend_or_workflow_contract_or_hitl_surface_changed"
  exit 0
fi

echo "deploy_mode=app_only"
echo "validation_mode=quick"
echo "infrastructure_action=none"
echo "reason=application_only_change"
