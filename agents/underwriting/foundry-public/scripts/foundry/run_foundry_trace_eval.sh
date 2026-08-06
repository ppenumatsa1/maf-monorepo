#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

read_azd_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" \
    --cwd "$FOUNDRY_DIR" --no-prompt
}

export FOUNDRY_PROJECTS_ENDPOINT="$(read_azd_value FOUNDRY_PROJECTS_ENDPOINT)"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="$(read_azd_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"

if [[ -z "$FOUNDRY_PROJECTS_ENDPOINT" || -z "$FOUNDRY_MODEL_DEPLOYMENT_NAME" ]]; then
  echo "The selected azd environment is missing Foundry evaluation configuration." >&2
  exit 1
fi

cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/backend" "$ROOT_DIR/.venv/bin/python" -m evals.foundry_trace_eval
