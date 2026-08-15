#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"

case "${INFRASTRUCTURE_MODE:-}" in
  bootstrap) ;;
  steadyState)
    echo "Skipping PostgreSQL bootstrap grants in steadyState mode."
    exit 0
    ;;
  *)
    echo "INFRASTRUCTURE_MODE must be bootstrap or steadyState." >&2
    exit 1
    ;;
esac

: "${AZURE_ENV_NAME:?AZURE_ENV_NAME is required}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_LOCATION:?AZURE_LOCATION is required}"
: "${AZURE_POSTGRES_HOST:?AZURE_POSTGRES_HOST is required}"
: "${AZURE_POSTGRES_DATABASE:?AZURE_POSTGRES_DATABASE is required}"
: "${AZURE_POSTGRES_USER:?AZURE_POSTGRES_USER is required}"
: "${POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME:?POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME is required}"
: "${POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID:?POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID is required}"

if ! command -v psql >/dev/null 2>&1 || ! command -v az >/dev/null 2>&1; then
  echo "psql and az are required to configure PostgreSQL Entra access." >&2
  exit 1
fi

require_selected_target \
  "$AZURE_ENV_NAME" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION"
require_azure_cli_target "$AZURE_SUBSCRIPTION_ID"

resource_group="$AZURE_RESOURCE_GROUP"
server_name="${AZURE_POSTGRES_HOST%%.*}"
backend_principal_id="$(az identity show \
  --resource-group "$resource_group" \
  --name "$AZURE_POSTGRES_USER" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --query principalId \
  --output tsv)"

az postgres flexible-server microsoft-entra-admin create \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-group "$resource_group" \
  --server-name "$server_name" \
  --display-name "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME" \
  --object-id "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID" \
  --type User \
  --output none

export PGPASSWORD
PGPASSWORD="$(az account get-access-token \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-type oss-rdbms \
  --query accessToken \
  --output tsv)"

admin_uri="host=${AZURE_POSTGRES_HOST} port=5432 dbname=postgres user=${POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME} sslmode=require"

wait_for_entra_admin() {
  local attempt
  local max_attempts="${POSTGRES_ENTRA_ADMIN_READY_ATTEMPTS:-18}"
  local retry_seconds="${POSTGRES_ENTRA_ADMIN_READY_RETRY_SECONDS:-10}"

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    if psql "$admin_uri" --set=ON_ERROR_STOP=1 --command='SELECT 1' >/dev/null 2>&1; then
      return
    fi
    if ((attempt < max_attempts)); then
      echo "Waiting for PostgreSQL Entra administrator propagation (${attempt}/${max_attempts})..." >&2
      sleep "$retry_seconds"
    fi
  done

  echo "PostgreSQL Entra administrator did not accept token authentication after ${max_attempts} attempts." >&2
  exit 1
}

wait_for_entra_admin

psql "$admin_uri" \
  --set=ON_ERROR_STOP=1 \
  --set=backend_principal="$AZURE_POSTGRES_USER" \
  --set=backend_principal_id="$backend_principal_id" \
  --set=database_name="$AZURE_POSTGRES_DATABASE" <<'SQL'
SELECT pg_catalog.pgaadauth_create_principal_with_oid(
  :'backend_principal',
  :'backend_principal_id',
  'service',
  false,
  false
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'backend_principal');

GRANT CONNECT ON DATABASE :"database_name" TO :"backend_principal";
SQL

application_uri="host=${AZURE_POSTGRES_HOST} port=5432 dbname=${AZURE_POSTGRES_DATABASE} user=${POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME} sslmode=require"

psql "$application_uri" \
  --set=ON_ERROR_STOP=1 \
  --set=backend_principal="$AZURE_POSTGRES_USER" <<'SQL'
GRANT USAGE, CREATE ON SCHEMA public TO :"backend_principal";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :"backend_principal";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :"backend_principal";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO :"backend_principal";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO :"backend_principal";
SQL
