#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"

for command_name in az azd psql; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

get_azd_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --environment "$environment" 2>/dev/null
}

subscription_id="$(get_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(get_azd_value AZURE_RESOURCE_GROUP)"
location="$(get_azd_value AZURE_LOCATION)"
postgres_host="$(get_azd_value AZURE_POSTGRES_HOST)"
postgres_database="$(get_azd_value AZURE_POSTGRES_DATABASE)"
runtime_role="$(get_azd_value AZURE_POSTGRES_USER)"
admin_role="$(get_azd_value POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME)"

require_selected_target "$environment" "$subscription_id" "$resource_group" "$location"
require_azure_cli_target "$subscription_id"

[[ -n "$postgres_host" && "$postgres_host" == *.postgres.database.azure.com ]] || {
  echo "Selected AZD environment has an invalid PostgreSQL host." >&2
  exit 1
}
[[ "$postgres_database" == "maf_workflow" && -n "$runtime_role" && -n "$admin_role" ]] || {
  echo "Selected AZD PostgreSQL identity values do not match the approved topology." >&2
  exit 1
}

schema_path="$ROOT_DIR/backend/app/sql/schema.sql"
[[ -f "$schema_path" && ! -L "$schema_path" && -r "$schema_path" ]] || {
  echo "Canonical PostgreSQL schema is not a readable regular file." >&2
  exit 1
}

export PGHOST="$postgres_host"
export PGPORT=5432
export PGDATABASE="$postgres_database"
export PGUSER="$admin_role"
export PGSSLMODE=require
export PGPASSWORD
PGPASSWORD="$(
  az account get-access-token \
    --subscription "$subscription_id" \
    --resource-type oss-rdbms \
    --query accessToken \
    --output tsv
)"

psql --set=ON_ERROR_STOP=1 --file="$schema_path"

psql \
  --set=ON_ERROR_STOP=1 \
  --set=runtime_role="$runtime_role" <<'SQL'
BEGIN;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM :"runtime_role";
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM :"runtime_role";
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM :"runtime_role";

GRANT USAGE ON SCHEMA public TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"runtime_role";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON TABLES FROM :"runtime_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM :"runtime_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"runtime_role";

COMMIT;
SQL

verification="$(
  psql \
    --tuples-only \
    --no-align \
    --set=ON_ERROR_STOP=1 \
    --set=runtime_role="$runtime_role" <<'SQL'
SELECT concat_ws(
  '|',
  has_schema_privilege(:'runtime_role', 'public', 'CREATE'),
  has_schema_privilege(:'runtime_role', 'public', 'USAGE'),
  COALESCE((
    SELECT bool_and(
      has_table_privilege(
        :'runtime_role',
        format('%I.%I', schemaname, tablename),
        'SELECT,INSERT,UPDATE,DELETE'
      )
    )
    FROM pg_tables
    WHERE schemaname = 'public'
  ), false),
  COALESCE((
    SELECT bool_and(
      has_sequence_privilege(
        :'runtime_role',
        format('%I.%I', sequence_schema, sequence_name),
        'USAGE,SELECT,UPDATE'
      )
    )
    FROM information_schema.sequences
    WHERE sequence_schema = 'public'
  ), false),
  (
    SELECT count(*)
    FROM pg_class AS relation
    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    JOIN pg_roles AS owner_role ON owner_role.oid = relation.relowner
    WHERE namespace.nspname = 'public'
      AND relation.relkind IN ('r', 'p', 'S')
      AND owner_role.rolname = :'runtime_role'
  )
);
SQL
)"

[[ "$verification" == "f|t|t|t|0" ]] || {
  echo "PostgreSQL least-privilege verification failed." >&2
  exit 1
}

echo "Applied the canonical PostgreSQL schema with administrator ownership and verified runtime DML-only access."
