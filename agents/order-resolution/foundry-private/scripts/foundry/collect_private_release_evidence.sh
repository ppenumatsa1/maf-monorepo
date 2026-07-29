#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"

require_bin az
require_bin azd
require_bin jq

cd "$FOUNDRY_DIR"
resource_group="$(azd env get-value AZURE_RESOURCE_GROUP)"
connection_json="$(azd ai connection show ApplicationInsights --output json --no-prompt)"
application_insights_target="$(printf '%s' "$connection_json" | jq -r '.target // .metadata.ResourceId // .properties.target // empty')"
if [[ -z "$resource_group" || -z "$application_insights_target" ]]; then
  echo "Private release evidence requires an AZD resource group and ApplicationInsights project connection."
  exit 1
fi

hosted_agent_name="$(azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_NAME)"
hosted_agent_version="$(azd env get-value AGENT_ORDER_RESOLUTION_HOSTED_VERSION)"
if [[ -z "$hosted_agent_name" || -z "$hosted_agent_version" ]]; then
  echo "Private release evidence requires the active hosted agent name and version."
  exit 1
fi

cd "$ROOT_DIR"
./scripts/github/foundry_hosted_e2e.sh
AZURE_RESOURCE_GROUP="$resource_group" \
APPLICATION_INSIGHTS_RESOURCE_ID="$application_insights_target" \
FOUNDRY_EVALUATION_AGENT_ID="${hosted_agent_name}:${hosted_agent_version}" \
./scripts/foundry/verify_telemetry.sh
FOUNDRY_EVAL_ENFORCE_PASS=true \
FOUNDRY_EVAL_MAX_ERRORED=0 \
make eval-foundry

echo "Private release evidence collection completed."
