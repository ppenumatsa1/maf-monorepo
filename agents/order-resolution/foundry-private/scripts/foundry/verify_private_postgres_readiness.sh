#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"
source "${ROOT_DIR}/scripts/foundry/private_profile.sh"
PROFILE_FILE="$(private_profile_resolve "$ROOT_DIR")"

for binary in az azd base64 getent jq psql python3; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary" >&2
    exit 1
  }
done

source "${ROOT_DIR}/../deployment/profile.sh"
deployment_profile_load "$PROFILE_FILE"
deployment_profile_validate
deployment_profile_export
[[ "$DEPLOYMENT_LANE" == "foundry-private" ]] || {
  echo "The selected deployment profile is not the foundry-private lane." >&2
  exit 1
}

get_env_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --environment "$AZURE_ENV_NAME" \
      --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

resource_group="$(get_env_value AZURE_RESOURCE_GROUP)"
subscription_id="$(get_env_value AZURE_SUBSCRIPTION_ID)"
postgres_server_name="$(get_env_value POSTGRES_SERVER_NAME)"
postgres_fqdn="$(get_env_value POSTGRES_SERVER_FQDN)"
postgres_database="$(get_env_value POSTGRES_DATABASE_NAME)"
private_endpoint_name="$(get_env_value POSTGRES_PRIVATE_ENDPOINT_NAME)"
private_dns_zone="$(get_env_value POSTGRES_PRIVATE_DNS_ZONE_NAME)"
runtime_database_url="$(get_env_value RUNTIME_DATABASE_URL)"

for required_value in \
  resource_group subscription_id postgres_server_name postgres_fqdn \
  postgres_database private_endpoint_name private_dns_zone runtime_database_url; do
  [[ -n "${!required_value}" ]] || {
    echo "Missing private PostgreSQL readiness input: ${required_value}" >&2
    exit 1
  }
done

[[ "$resource_group" == "$AZURE_RESOURCE_GROUP" &&
  "$subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Selected AZD target does not match the private deployment profile." >&2
  exit 1
}

actual_subscription_id="$(az account show --query id --output tsv)"
[[ "$actual_subscription_id" == "$AZURE_SUBSCRIPTION_ID" ]] || {
  echo "Azure CLI is not scoped to the private deployment subscription." >&2
  exit 1
}

canonical_fqdn="${postgres_server_name,,}.postgres.database.azure.com"
[[ "${postgres_fqdn,,}" == "$canonical_fqdn" ]] || {
  echo "PostgreSQL FQDN does not match the canonical private server." >&2
  exit 1
}

server_json="$(
  az postgres flexible-server show \
    --resource-group "$resource_group" \
    --name "$postgres_server_name" \
    --query '{id:id,state:state,fqdn:fullyQualifiedDomainName,publicAccess:network.publicNetworkAccess}' \
    --output json
)"
[[ "$(jq -r '.state' <<<"$server_json")" == "Ready" &&
  "$(jq -r '.fqdn | ascii_downcase' <<<"$server_json")" == "$canonical_fqdn" &&
  "$(jq -r '.publicAccess' <<<"$server_json")" == "Disabled" ]] || {
  echo "PostgreSQL must be Ready with public network access disabled." >&2
  exit 1
}
server_id="$(jq -r '.id' <<<"$server_json")"

endpoint_json="$(
  az network private-endpoint show \
    --resource-group "$resource_group" \
    --name "$private_endpoint_name" \
    --query '{
      target:privateLinkServiceConnections[0].privateLinkServiceId,
      status:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status,
      group:privateLinkServiceConnections[0].groupIds[0],
      subnet:subnet.id,
      nic:networkInterfaces[0].id
    }' \
    --output json
)"
[[ "$(jq -r '.status' <<<"$endpoint_json")" == "Approved" &&
  "$(jq -r '.group' <<<"$endpoint_json")" == "postgresqlServer" &&
  "$(jq -r '.target | ascii_downcase' <<<"$endpoint_json")" == "${server_id,,}" ]] || {
  echo "PostgreSQL private endpoint is not approved for the canonical server." >&2
  exit 1
}

endpoint_subnet_id="$(jq -r '.subnet' <<<"$endpoint_json")"
endpoint_nic_id="$(jq -r '.nic' <<<"$endpoint_json")"
endpoint_private_ip="$(
  az network nic show \
    --ids "$endpoint_nic_id" \
    --query 'ipConfigurations[0].privateIPAddress' \
    --output tsv
)"
[[ -n "$endpoint_subnet_id" && -n "$endpoint_private_ip" ]] || {
  echo "PostgreSQL private endpoint is missing its subnet or private IP." >&2
  exit 1
}

dns_record_ips="$(
  az network private-dns record-set a show \
    --resource-group "$resource_group" \
    --zone-name "$private_dns_zone" \
    --name "$postgres_server_name" \
    --query 'aRecords[].ipv4Address' \
    --output tsv
)"
grep -Fxq "$endpoint_private_ip" <<<"$dns_record_ips" || {
  echo "Private DNS does not map PostgreSQL to the private endpoint IP." >&2
  exit 1
}

endpoint_vnet_id="${endpoint_subnet_id%/subnets/*}"
linked_vnet_ids="$(
  az network private-dns link vnet list \
    --resource-group "$resource_group" \
    --zone-name "$private_dns_zone" \
    --query '[].virtualNetwork.id' \
    --output tsv
)"
tr '[:upper:]' '[:lower:]' <<<"$linked_vnet_ids" |
  grep -Fxq "${endpoint_vnet_id,,}" || {
  echo "PostgreSQL private DNS zone is not linked to the endpoint VNet." >&2
  exit 1
}

resolved_ips="$(getent ahostsv4 "$canonical_fqdn" | awk '{print $1}' | sort -u)"
grep -Fxq "$endpoint_private_ip" <<<"$resolved_ips" || {
  echo "The private runner does not resolve PostgreSQL to its private endpoint IP." >&2
  exit 1
}

mapfile -t runtime_parts < <(
  RUNTIME_DATABASE_URL="$runtime_database_url" python3 - <<'PY'
import base64
import os
from urllib.parse import unquote, urlsplit

value = os.environ["RUNTIME_DATABASE_URL"]
if value.startswith("postgresql+psycopg://"):
    value = "postgresql://" + value.removeprefix("postgresql+psycopg://")
parsed = urlsplit(value)
parts = (
    unquote(parsed.username or ""),
    unquote(parsed.password or ""),
    parsed.hostname or "",
    unquote(parsed.path.lstrip("/")),
)
if not all(parts):
    raise SystemExit("Runtime database URL is incomplete.")
for part in parts:
    print(base64.b64encode(part.encode()).decode())
PY
)
(( ${#runtime_parts[@]} == 4 )) || {
  echo "Runtime database URL could not be parsed." >&2
  exit 1
}
runtime_username="$(base64 --decode <<<"${runtime_parts[0]}")"
runtime_password="$(base64 --decode <<<"${runtime_parts[1]}")"
runtime_host="$(base64 --decode <<<"${runtime_parts[2]}")"
runtime_database="$(base64 --decode <<<"${runtime_parts[3]}")"
[[ "${runtime_host,,}" == "$canonical_fqdn" &&
  "$runtime_database" == "$postgres_database" ]] || {
  echo "Runtime database URL does not target the canonical private database." >&2
  exit 1
}

verification_file="$(mktemp)"
trap 'rm -f "$verification_file"' EXIT
POSTGRES_DATABASE="$runtime_database" \
POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  python3 "${ROOT_DIR}/scripts/foundry/postgres_runtime_credentials.py" verify \
    >"$verification_file"

if ! PGPASSWORD="$runtime_password" PGSSLMODE=require \
  psql --host "$canonical_fqdn" --username "$runtime_username" \
    --dbname "$runtime_database" --set ON_ERROR_STOP=on --quiet \
    --file "$verification_file" >/dev/null 2>&1; then
  echo "Private PostgreSQL runtime readiness verification failed." >&2
  exit 1
fi

unset runtime_database_url runtime_password
echo "Private PostgreSQL readiness passed."
