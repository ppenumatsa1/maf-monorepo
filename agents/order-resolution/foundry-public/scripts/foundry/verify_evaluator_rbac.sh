#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

for command in az azd jq python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

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

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
foundry_account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"

actual_subscription="$(az account show --query id --output tsv)"
[[ "$actual_subscription" == "$subscription_id" ]] || {
  echo "Azure CLI subscription does not match the selected external profile." >&2
  exit 1
}

access_token="$(
  az account get-access-token \
    --resource https://management.azure.com/ \
    --query accessToken \
    --output tsv
)"
principal_id="$(
  printf '%s' "$access_token" |
    python3 -c '
import base64
import json
import sys

parts = sys.stdin.read().strip().split(".")
if len(parts) != 3:
    raise SystemExit("Azure access token is not a JWT")
payload = parts[1] + "=" * (-len(parts[1]) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
principal_id = claims.get("oid")
if not isinstance(principal_id, str) or not principal_id:
    raise SystemExit("Azure access token does not contain an oid claim")
print(principal_id)
'
)"
unset access_token

foundry_account_id="$(
  az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account_name" \
    --query id \
    --output tsv
)"
[[ -n "$foundry_account_id" ]] || {
  echo "Foundry account was not found for evaluator RBAC verification." >&2
  exit 1
}

assignments="$(
  az role assignment list \
    --subscription "$subscription_id" \
    --assignee-object-id "$principal_id" \
    --scope "$foundry_account_id" \
    --include-inherited \
    --fill-principal-name false \
    --output json
)"
for required_role in "Foundry User" "Cognitive Services OpenAI User"; do
  jq -e --arg role "$required_role" --arg scope "${foundry_account_id,,}" '
    any(
      .[];
      .roleDefinitionName == $role
        and ((.scope // "") | ascii_downcase) == $scope
    )
  ' <<<"$assignments" >/dev/null || {
    echo "The release identity requires ${required_role} at the Foundry account scope for strict cloud evaluation." >&2
    exit 1
  }
done

echo "Evaluator RBAC verification passed."
