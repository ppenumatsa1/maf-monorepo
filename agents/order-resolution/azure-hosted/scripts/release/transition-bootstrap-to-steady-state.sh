#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"
environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

get_azd_value() {
  azd env get-value "$1" --environment "$environment" 2>/dev/null
}

subscription_id="$(get_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(get_azd_value AZURE_RESOURCE_GROUP)"
location="$(get_azd_value AZURE_LOCATION)"
postgres_host="$(get_azd_value AZURE_POSTGRES_HOST)"
postgres_database="$(get_azd_value AZURE_POSTGRES_DATABASE)"
bootstrap_allowed_ip="$(get_azd_value POSTGRES_BOOTSTRAP_ALLOWED_IP)"
require_selected_target "$environment" "$subscription_id" "$resource_group" "$location"
require_azure_cli_target "$subscription_id"

postgres_name="${postgres_host%%.*}"
[[ -n "$postgres_name" && "$postgres_name" != "$postgres_host" && "$postgres_database" == "maf_workflow" ]] || {
  echo "Selected AZD PostgreSQL outputs do not match the approved topology." >&2
  exit 1
}
[[ -n "$bootstrap_allowed_ip" ]] || {
  echo "Selected AZD environment is missing the bootstrap firewall IP; cleanup refused." >&2
  exit 1
}
postgres_id="$(az postgres flexible-server show \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$postgres_name" \
  --query id \
  --output tsv)"
database_id="$(az postgres flexible-server db show \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$postgres_name" \
  --name "$postgres_database" \
  --query id \
  --output tsv)"
[[ -n "$postgres_id" && "$database_id" == "$postgres_id/databases/$postgres_database" ]] || {
  echo "PostgreSQL server/database identity could not be verified; steady-state transition refused." >&2
  exit 1
}

firewall_rules_output="$(az postgres flexible-server firewall-rule list \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$postgres_name" \
  --query "[?name=='allow-bootstrap-runner'].[name,startIpAddress,endIpAddress]" \
  --output tsv)"
readarray -t bootstrap_firewall_rules <<<"$firewall_rules_output"
if [[ -z "$firewall_rules_output" ]]; then
  bootstrap_firewall_rules=()
fi
if [[ "${#bootstrap_firewall_rules[@]}" -gt 1 ]]; then
  echo "Multiple bootstrap firewall rule records were returned; cleanup refused." >&2
  exit 1
fi

if [[ "${#bootstrap_firewall_rules[@]}" -eq 1 ]]; then
  read -r firewall_rule_name firewall_start_ip firewall_end_ip <<<"${bootstrap_firewall_rules[0]}"
  if [[ "$firewall_rule_name" != "allow-bootstrap-runner" ||
    "$firewall_start_ip" != "$bootstrap_allowed_ip" ||
    "$firewall_end_ip" != "$bootstrap_allowed_ip" ]]; then
    echo "Bootstrap firewall rule does not exactly match the selected operator IP; cleanup refused." >&2
    exit 1
  fi

  az postgres flexible-server firewall-rule delete \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$postgres_name" \
    --name allow-bootstrap-runner \
    --yes
else
  echo "Bootstrap firewall rule is already absent; continuing the verified steady-state transition."
fi

remaining_bootstrap_rules="$(az postgres flexible-server firewall-rule list \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$postgres_name" \
  --query "length([?name=='allow-bootstrap-runner'])" \
  --output tsv)"
[[ "$remaining_bootstrap_rules" == "0" ]] || {
  echo "Bootstrap firewall rule deletion could not be verified; steady-state transition refused." >&2
  exit 1
}

azd env set INFRASTRUCTURE_MODE steadyState --environment "$environment" --no-prompt >/dev/null
azd env set POSTGRES_BOOTSTRAP_ALLOWED_IP "" --environment "$environment" --no-prompt >/dev/null

echo "Selected AZD environment is now in steadyState mode; PostgreSQL is excluded from IaC."
