#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

require_bin az
require_bin azd
require_bin python3

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
runtime_username="$(required_env POSTGRES_RUNTIME_USERNAME)"
hosted_password="$(required_env POSTGRES_HOSTED_PASSWORD)"
operator_ip="$(required_env POSTGRES_OPERATOR_IP)"
database_url="$(required_env DATABASE_URL)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
db_auth_mode="$(required_env DB_AUTH_MODE)"

if [[ "$db_auth_mode" != "password" ]]; then
  echo "DB_AUTH_MODE must be password." >&2
  exit 1
fi
if [[ "$database_url" != "$runtime_database_url" ]]; then
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match." >&2
  exit 1
fi

POSTGRES_SERVER_NAME="$server_name" \
POSTGRES_DATABASE="$database_name" \
POSTGRES_RUNTIME_USERNAME="$runtime_username" \
POSTGRES_HOSTED_PASSWORD="$hosted_password" \
RUNTIME_DATABASE_URL="$runtime_database_url" \
  python3 - <<'PY'
import os
import sys
from hmac import compare_digest
from urllib.parse import parse_qs, unquote, urlsplit

parsed = urlsplit(os.environ["RUNTIME_DATABASE_URL"])
expected_host = f'{os.environ["POSTGRES_SERVER_NAME"]}.postgres.database.azure.com'
expected_database = os.environ["POSTGRES_DATABASE"]
expected_user = os.environ["POSTGRES_RUNTIME_USERNAME"]
expected_password = os.environ["POSTGRES_HOSTED_PASSWORD"]

if parsed.scheme != "postgresql+psycopg":
    sys.exit("RUNTIME_DATABASE_URL must use the postgresql+psycopg driver.")
if parsed.hostname != expected_host or parsed.port != 5432:
    sys.exit("RUNTIME_DATABASE_URL host or port does not match the configured PostgreSQL server.")
if unquote(parsed.username or "") != expected_user or not unquote(parsed.password or ""):
    sys.exit("RUNTIME_DATABASE_URL must contain the configured runtime user and a password.")
if not compare_digest(unquote(parsed.password or ""), expected_password):
    sys.exit("RUNTIME_DATABASE_URL password does not match POSTGRES_HOSTED_PASSWORD.")
if unquote(parsed.path.lstrip("/")) != expected_database:
    sys.exit("RUNTIME_DATABASE_URL database does not match POSTGRES_DATABASE.")
if parse_qs(parsed.query).get("sslmode") != ["require"]:
    sys.exit("RUNTIME_DATABASE_URL must require TLS.")
PY

az account set --subscription "$subscription_id"

server_state="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query state \
    --output tsv
)"
public_network_access="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query network.publicNetworkAccess \
    --output tsv
)"
password_auth="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query authConfig.passwordAuth \
    --output tsv
)"
active_directory_auth="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query authConfig.activeDirectoryAuth \
    --output tsv
)"

if [[ "$server_state" != "Ready" ]]; then
  echo "PostgreSQL server is not Ready." >&2
  exit 1
fi
if [[ "$public_network_access" != "Enabled" ]]; then
  echo "PostgreSQL public network access must be Enabled." >&2
  exit 1
fi
if [[ "$password_auth" != "Enabled" || "$active_directory_auth" != "Enabled" ]]; then
  echo "PostgreSQL must retain both password and Microsoft Entra authentication." >&2
  exit 1
fi

firewall_start="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-all-temporary \
    --query startIpAddress \
    --output tsv
)"
firewall_end="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-all-temporary \
    --query endIpAddress \
    --output tsv
)"
if [[ "$firewall_start" != "0.0.0.0" || "$firewall_end" != "0.0.0.0" ]]; then
  echo "allow-all-temporary must be restricted to 0.0.0.0-0.0.0.0." >&2
  exit 1
fi

operator_firewall_start="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-release-operator \
    --query startIpAddress \
    --output tsv
)"
operator_firewall_end="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-release-operator \
    --query endIpAddress \
    --output tsv
)"
if [[ "$operator_firewall_start" != "$operator_ip" || "$operator_firewall_end" != "$operator_ip" ]]; then
  echo "Release-operator firewall rule does not match POSTGRES_OPERATOR_IP." >&2
  exit 1
fi

if ! az postgres flexible-server db show \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$server_name" \
  --name "$database_name" \
  --output none >/dev/null 2>&1; then
  echo "Configured PostgreSQL runtime database is absent." >&2
  exit 1
fi

echo "PostgreSQL readiness passed: TLS URL, password runtime credential, dual authentication, and Azure-services firewall are configured."
