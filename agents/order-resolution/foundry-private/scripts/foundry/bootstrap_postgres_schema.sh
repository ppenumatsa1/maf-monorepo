#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${POSTGRES_PROFILE_FILE:-}" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/../deployment/profile.sh"
  deployment_profile_load "$POSTGRES_PROFILE_FILE"
  deployment_profile_validate
  deployment_profile_export
fi
FOUNDRY_DIR="${POSTGRES_AZD_PROJECT_DIR:-$ROOT_DIR/infra/foundry-hosted}"
AZD_PROFILE="${POSTGRES_AZD_ENVIRONMENT:-${AZD_ENVIRONMENT_NAME:-}}"
SCHEMA_FILE="${POSTGRES_SCHEMA_FILE:-$ROOT_DIR/backend/app/sql/schema.sql}"

get_input() {
  local name="$1"
  local value
  value="$(printenv "$name" 2>/dev/null || true)"
  if [[ -z "$value" && -n "$AZD_PROFILE" ]]; then
    value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$name" \
      --environment "$AZD_PROFILE" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true)"
  fi
  [[ -n "$value" ]] || {
    echo "Missing required PostgreSQL input: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

get_input_alias() {
  local primary="$1"
  local fallback="$2"
  local value
  value="$(printenv "$primary" 2>/dev/null || true)"
  [[ -n "$value" ]] || value="$(printenv "$fallback" 2>/dev/null || true)"
  if [[ -z "$value" && -n "$AZD_PROFILE" ]]; then
    value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$primary" \
      --environment "$AZD_PROFILE" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true)"
    [[ -n "$value" ]] || value="$(
      AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$fallback" \
        --environment "$AZD_PROFILE" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
    )"
  fi
  [[ -n "$value" ]] || {
    echo "Missing required PostgreSQL input: $primary (or $fallback)" >&2
    exit 1
  }
  printf '%s' "$value"
}

for command in psql; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done
if [[ -n "$AZD_PROFILE" ]]; then
  command -v azd >/dev/null 2>&1 || {
    echo "Missing required binary: azd" >&2
    exit 1
  }
fi
[[ -r "$SCHEMA_FILE" ]] || {
  echo "Missing canonical PostgreSQL schema." >&2
  exit 1
}

server_fqdn="$(get_input_alias POSTGRES_SERVER_FQDN POSTGRES_SERVER_NAME)"
[[ "$server_fqdn" == *.* ]] || server_fqdn="${server_fqdn}.postgres.database.azure.com"
database_name="$(get_input_alias POSTGRES_DATABASE POSTGRES_DATABASE_NAME)"
admin_username="$(get_input POSTGRES_ADMIN_USERNAME)"
admin_password="$(get_input POSTGRES_ADMIN_PASSWORD)"

[[ "$server_fqdn" =~ ^[A-Za-z0-9][A-Za-z0-9-]*\.postgres\.database\.azure\.com$ ]] || {
  echo "POSTGRES_SERVER_FQDN must be a canonical PostgreSQL Flexible Server FQDN." >&2
  exit 1
}
[[ "$database_name" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || {
  echo "POSTGRES_DATABASE is not a valid identifier." >&2
  exit 1
}
[[ "$admin_password" != *$'\n'* && "$admin_password" != *$'\r'* ]] || {
  echo "POSTGRES_ADMIN_PASSWORD must be a single-line secret." >&2
  exit 1
}

if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "$server_fqdn" --username "$admin_username" --dbname "$database_name" \
    --set ON_ERROR_STOP=on --single-transaction --quiet --file "$SCHEMA_FILE" \
    >/dev/null 2>&1; then
  echo "PostgreSQL schema bootstrap failed; command output was withheld." >&2
  exit 1
fi

unset admin_password
echo "Bootstrapped the order-resolution PostgreSQL schema with administrator ownership."
