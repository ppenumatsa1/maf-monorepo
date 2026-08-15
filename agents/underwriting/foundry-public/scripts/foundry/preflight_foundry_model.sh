#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

for binary in az azd jq; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary" >&2
    exit 1
  }
done

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
deployment_name="$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
expected_model="$(required_env FOUNDRY_MODEL_NAME)"
expected_version="$(required_env FOUNDRY_MODEL_VERSION)"
expected_sku="$(required_env FOUNDRY_MODEL_SKU_NAME)"
expected_capacity="$(required_env FOUNDRY_MODEL_CAPACITY)"

az account set --subscription "$subscription_id" >/dev/null
deployment="$(
  az cognitiveservices account deployment show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$account_name" \
    --deployment-name "$deployment_name" \
    --output json
)"
actual_model="$(jq -r '.properties.model.name // empty' <<<"$deployment")"
actual_version="$(jq -r '.properties.model.version // empty' <<<"$deployment")"
actual_sku="$(jq -r '.sku.name // empty' <<<"$deployment")"
actual_capacity="$(jq -r '.sku.capacity // 0' <<<"$deployment")"

[[ "$actual_model" == "$expected_model" && "$actual_version" == "$expected_version" ]] || {
  echo "Foundry model deployment does not match the configured domain model/version." >&2
  exit 1
}
[[ "$actual_sku" == "$expected_sku" ]] || {
  echo "Foundry model SKU is '$actual_sku', expected '$expected_sku'; preflight will not change it." >&2
  exit 1
}
[[ "$actual_capacity" == "$expected_capacity" ]] || {
  echo "Foundry model capacity is '$actual_capacity', expected '$expected_capacity'; preflight will not change it." >&2
  exit 1
}

usage_json="$(
  az cognitiveservices usage list \
    --subscription "$subscription_id" \
    --location "$location" \
    --output json
)"
MODEL_NAME="$expected_model" SKU_NAME="$expected_sku" CAPACITY="$expected_capacity" \
  python3 -c '
import json
import os
import re
import sys

records = json.load(sys.stdin)
model = re.sub(r"[^a-z0-9]", "", os.environ["MODEL_NAME"].lower())
sku = re.sub(r"[^a-z0-9]", "", os.environ["SKU_NAME"].lower())
matches = []
for record in records:
    name = record.get("name") or {}
    text = " ".join(
        str(value)
        for value in (
            name.get("value"),
            name.get("localizedValue"),
            record.get("unit"),
        )
        if value is not None
    )
    normalized = re.sub(r"[^a-z0-9]", "", text.lower())
    if model in normalized and sku in normalized:
        matches.append(record)
if not matches:
    raise SystemExit("No regional quota record matched the configured model and SKU.")
limit = max(float(item.get("limit") or 0) for item in matches)
current = max(float(item.get("currentValue") or 0) for item in matches)
capacity = float(os.environ["CAPACITY"])
if limit <= 0 or current > limit or capacity > limit:
    raise SystemExit(
        f"Configured model capacity/quota is not viable: current={current:g}, limit={limit:g}, capacity={capacity:g}."
    )
print(f"Foundry model/quota preflight passed: current={current:g}, limit={limit:g}, capacity={capacity:g}.")
' <<<"$usage_json"
