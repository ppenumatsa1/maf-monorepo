#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

base_ref="${1:-HEAD}"
tracked_changes="$(git diff --name-only --relative "$base_ref" -- .)"
untracked_changes="$(git ls-files --others --exclude-standard -- .)"
changed_files="$(printf '%s\n%s\n' "$tracked_changes" "$untracked_changes" | sed '/^$/d' | sort -u)"

if [[ -z "$changed_files" ]]; then
  echo "deploy_mode=app_only"
  echo "release_authority=app_only"
  echo "release_permitted=true"
  echo "validation_mode=quick"
  echo "infrastructure_reconciliation=not_requested"
  echo "reason=no_changed_files"
  exit 0
fi

if grep -Eq '^infra/' <<<"$changed_files"; then
  if [[ "${FOUNDRY_INFRA_RECONCILED:-}" == "true" ]]; then
    echo "deploy_mode=app_only"
    echo "release_authority=app_only"
    echo "release_permitted=true"
    echo "validation_mode=full"
    echo "infrastructure_reconciliation=reviewed_applied"
    echo "reason=infrastructure_change_was_explicitly_reconciled"
    exit 0
  fi
  echo "deploy_mode=app_only"
  echo "release_authority=full_infra"
  echo "release_permitted=false"
  echo "validation_mode=full"
  echo "infrastructure_reconciliation=required"
  echo "reason=infrastructure_change_requires_explicit_reconciliation"
  exit 0
fi

if grep -Eq '^(Makefile|scripts/|deployment/|\.azure/|docker-compose\.yml|backend/Dockerfile(\.hosted)?|frontend/Dockerfile|frontend/nginx\.conf|pyproject\.toml|backend/requirements(\-dev)?\.txt|frontend/package(-lock)?\.json|\.env\.example|\.github/workflows/|backend/|frontend/)' <<<"$changed_files"; then
  echo "deploy_mode=app_only"
  echo "release_authority=app_only"
  echo "release_permitted=true"
  echo "validation_mode=full"
  echo "infrastructure_reconciliation=not_requested"
  echo "reason=runtime_or_package_surface_changed"
  exit 0
fi

echo "deploy_mode=app_only"
echo "release_authority=app_only"
echo "release_permitted=true"
echo "validation_mode=quick"
echo "infrastructure_reconciliation=not_requested"
echo "reason=non_runtime_change"
