#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
SCHEMA_FILE="$ROOT_DIR/backend/app/sql/schema.sql"

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

for command in az azd psql; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done
[[ -r "$SCHEMA_FILE" ]] || {
  echo "Missing canonical PostgreSQL schema." >&2
  exit 1
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
admin_username="$(required_env POSTGRES_ADMIN_USERNAME)"
admin_password="$(required_env POSTGRES_ADMIN_PASSWORD)"

az account set --subscription "$subscription_id" >/dev/null
if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "${server_name}.postgres.database.azure.com" \
    --username "$admin_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --file "$SCHEMA_FILE" >/dev/null 2>&1; then
  echo "PostgreSQL schema bootstrap failed; command output was withheld to protect credentials." >&2
  exit 1
fi

unset admin_password
echo "Bootstrapped the order-resolution PostgreSQL schema."
