#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${POSTGRES_PROFILE_FILE:-}" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/../deployment/profile.sh"
  deployment_profile_load "$POSTGRES_PROFILE_FILE"
  deployment_profile_validate
  deployment_profile_export
fi
FOUNDRY_DIR="${POSTGRES_AZD_PROJECT_DIR:-$ROOT_DIR/infra/foundry-hosted}"
AZD_PROFILE="${POSTGRES_AZD_ENVIRONMENT:-${AZD_ENVIRONMENT_NAME:-}}"
CREDENTIAL_HELPER="$SCRIPT_DIR/postgres_runtime_credentials.py"

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

get_optional_alias() {
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
  printf '%s' "$value"
}

save_profile_secret() {
  local name="$1"
  local value="$2"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set "$name" "$value" --environment "$AZD_PROFILE" \
      --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null 2>&1 || {
    echo "Unable to save the PostgreSQL runtime configuration to the AZD profile." >&2
    exit 1
  }

  save_infra_parameter() {
    local name="$1"
    local value="$2"
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env config set "infra.parameters.${name}" "$value" \
        --environment "$AZD_PROFILE" --cwd "$FOUNDRY_DIR" >/dev/null 2>&1 || {
      echo "Unable to stage the PostgreSQL runtime infrastructure parameter." >&2
      exit 1
    }
  }
}

for command in python3 psql; do
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
elif [[ -z "${POSTGRES_RUNTIME_URL_OUTPUT_FILE:-}" ]]; then
  echo "Set POSTGRES_AZD_ENVIRONMENT or POSTGRES_RUNTIME_URL_OUTPUT_FILE to persist the runtime URL." >&2
  exit 1
elif [[ ! -d "$(dirname "$POSTGRES_RUNTIME_URL_OUTPUT_FILE")" ]]; then
  echo "POSTGRES_RUNTIME_URL_OUTPUT_FILE parent directory does not exist." >&2
  exit 1
fi

server_fqdn="$(get_input_alias POSTGRES_SERVER_FQDN POSTGRES_SERVER_NAME)"
[[ "$server_fqdn" == *.* ]] || server_fqdn="${server_fqdn}.postgres.database.azure.com"
database_name="$(get_input_alias POSTGRES_DATABASE POSTGRES_DATABASE_NAME)"
runtime_username="$(get_input POSTGRES_RUNTIME_USERNAME)"
runtime_password="$(get_optional_alias POSTGRES_RUNTIME_PASSWORD POSTGRES_HOSTED_PASSWORD)"
admin_username="$(get_input POSTGRES_ADMIN_USERNAME)"
admin_password="$(get_input POSTGRES_ADMIN_PASSWORD)"

if [[ -z "$runtime_password" ]]; then
  existing_runtime_url="$(get_optional_alias RUNTIME_DATABASE_URL DATABASE_URL)"
  if [[ -n "$existing_runtime_url" ]]; then
    runtime_password="$(
      RUNTIME_DATABASE_URL="$existing_runtime_url" python3 - <<'PY'
import os
from urllib.parse import unquote, urlsplit

value = os.environ["RUNTIME_DATABASE_URL"]
if value.startswith("postgresql+psycopg://"):
    value = "postgresql://" + value.removeprefix("postgresql+psycopg://")
print(unquote(urlsplit(value).password or ""))
PY
    )"
  fi
fi
if [[ -z "$runtime_password" ]]; then
  runtime_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi

[[ "$server_fqdn" =~ ^[A-Za-z0-9][A-Za-z0-9-]*\.postgres\.database\.azure\.com$ ]] || {
  echo "POSTGRES_SERVER_FQDN must be a canonical PostgreSQL Flexible Server FQDN." >&2
  exit 1
}
for identifier in "$database_name" "$runtime_username"; do
  [[ "$identifier" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || {
    echo "PostgreSQL database and runtime role names must be valid identifiers." >&2
    exit 1
  }
done
(( ${#runtime_password} >= 16 && ${#runtime_password} <= 128 )) || {
  echo "POSTGRES_RUNTIME_PASSWORD must contain 16-128 characters." >&2
  exit 1
}
[[ "$runtime_password" != *$'\n'* && "$runtime_password" != *$'\r'* ]] || {
  echo "POSTGRES_RUNTIME_PASSWORD must be a single-line secret." >&2
  exit 1
}

POSTGRES_SERVER_FQDN="$server_fqdn" \
POSTGRES_DATABASE="$database_name" \
POSTGRES_ADMIN_USERNAME="$admin_username" \
POSTGRES_ADMIN_PASSWORD="$admin_password" \
POSTGRES_AZD_PROJECT_DIR="$FOUNDRY_DIR" \
POSTGRES_AZD_ENVIRONMENT="$AZD_PROFILE" \
POSTGRES_PROFILE_FILE= \
  bash "$SCRIPT_DIR/bootstrap_postgres_schema.sh"

scratch_dir="$ROOT_DIR/backend/.tmp/foundry"
run_stamp="$(date -u +%Y%m%d%H%M%S)-$$"
provision_file="$scratch_dir/postgres-runtime-provision-${run_stamp}.sql"
verification_file="$scratch_dir/postgres-runtime-verify-${run_stamp}.sql"
mkdir -p "$scratch_dir"
trap 'rm -f "$provision_file" "$verification_file"' EXIT
umask 077

POSTGRES_DATABASE="$database_name" \
POSTGRES_RUNTIME_USERNAME="$runtime_username" \
POSTGRES_RUNTIME_PASSWORD="$runtime_password" \
POSTGRES_ADMIN_USERNAME="$admin_username" \
  python3 "$CREDENTIAL_HELPER" provision >"$provision_file"

if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "$server_fqdn" --username "$admin_username" --dbname "$database_name" \
    --set ON_ERROR_STOP=on --single-transaction --quiet --file "$provision_file" \
    >/dev/null 2>&1; then
  echo "Runtime credential provisioning failed; command output was withheld." >&2
  exit 1
fi

runtime_database_url="$(
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  POSTGRES_RUNTIME_PASSWORD="$runtime_password" \
  POSTGRES_SERVER_FQDN="$server_fqdn" \
    python3 "$CREDENTIAL_HELPER" runtime-url
)"
POSTGRES_DATABASE="$database_name" POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  python3 "$CREDENTIAL_HELPER" verify >"$verification_file"

if ! PGPASSWORD="$runtime_password" PGSSLMODE=require \
  psql --host "$server_fqdn" --username "$runtime_username" --dbname "$database_name" \
    --set ON_ERROR_STOP=on --quiet --file "$verification_file" >/dev/null 2>&1; then
  echo "Runtime credential verification failed; command output was withheld." >&2
  exit 1
fi

if [[ -n "$AZD_PROFILE" ]]; then
  save_profile_secret RUNTIME_DATABASE_URL "$runtime_database_url"
  save_profile_secret DATABASE_URL "$runtime_database_url"
  save_profile_secret DB_SCHEMA_MANAGED_EXTERNALLY true
  save_infra_parameter runtimeDatabaseUrl "$runtime_database_url"
elif [[ -n "${POSTGRES_RUNTIME_URL_OUTPUT_FILE:-}" ]]; then
  printf '%s\n' "$runtime_database_url" >"$POSTGRES_RUNTIME_URL_OUTPUT_FILE"
  chmod 600 "$POSTGRES_RUNTIME_URL_OUTPUT_FILE"
fi

unset admin_password runtime_password runtime_database_url
echo "Provisioned and verified the least-privilege PostgreSQL runtime credential."
