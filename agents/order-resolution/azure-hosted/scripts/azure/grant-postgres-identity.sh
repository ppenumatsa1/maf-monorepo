#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_POSTGRES_HOST:?AZURE_POSTGRES_HOST is required}"
: "${AZURE_POSTGRES_DATABASE:?AZURE_POSTGRES_DATABASE is required}"
: "${AZURE_POSTGRES_USER:?AZURE_POSTGRES_USER is required}"
: "${POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME:?POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME is required}"
: "${POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID:?POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID is required}"

if ! command -v psql >/dev/null 2>&1 || ! command -v az >/dev/null 2>&1; then
  echo "psql and az are required to configure PostgreSQL Entra access." >&2
  exit 1
fi

resource_group="rg-${AZURE_ENV_NAME:?AZURE_ENV_NAME is required}"
server_name="${AZURE_POSTGRES_HOST%%.*}"
tenant_id="$(az account show --query tenantId --output tsv)"
administrator_resource_id="/subscriptions/$(az account show --query id --output tsv)/resourceGroups/${resource_group}/providers/Microsoft.DBforPostgreSQL/flexibleServers/${server_name}/administrators/${POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID}"
backend_principal_id="$(az identity show \
  --resource-group "$resource_group" \
  --name "$AZURE_POSTGRES_USER" \
  --query principalId \
  --output tsv)"

az rest \
  --method PUT \
  --url "https://management.azure.com${administrator_resource_id}?api-version=2022-12-01" \
  --headers 'Content-Type=application/json' \
  --body "{\"properties\":{\"principalName\":\"${POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME}\",\"principalType\":\"User\",\"tenantId\":\"${tenant_id}\"}}" \
  --output none

export PGPASSWORD
PGPASSWORD="$(az account get-access-token \
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
