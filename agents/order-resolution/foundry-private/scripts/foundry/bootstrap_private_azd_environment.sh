#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin azd
require_bin python3

: "${AZD_ENVIRONMENT_NAME:?AZD_ENVIRONMENT_NAME is required}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is required}"
: "${TARGET_RESOURCE_GROUP:?TARGET_RESOURCE_GROUP is required}"
: "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD is required}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${ROOT_DIR}/infra/foundry-hosted"

POSTGRES_SERVER_NAME="${POSTGRES_SERVER_NAME:-maffndpgv20722}"
POSTGRES_DATABASE_NAME="${POSTGRES_DATABASE_NAME:-maf_workflow}"
POSTGRES_ADMIN_USERNAME="${POSTGRES_ADMIN_USERNAME:-pgadmin}"
FOUNDRY_ACCOUNT_NAME="${FOUNDRY_ACCOUNT_NAME:-mafprv0722v3ai4aiw7fw5gjdo4}"
FOUNDRY_PROJECT_NAME="${TARGET_FOUNDRY_PROJECT:-order-resolution}"
AZURE_LOCATION="${AZURE_LOCATION:-eastus2}"
POSTGRES_LOCATION="${POSTGRES_LOCATION:-centralus}"
NAME_PREFIX="${NAME_PREFIX:-mafprv0722v3}"

encoded_password="$(
  POSTGRES_ADMIN_PASSWORD="$POSTGRES_ADMIN_PASSWORD" python3 - <<'PY'
import os
from urllib.parse import quote

print(quote(os.environ["POSTGRES_ADMIN_PASSWORD"], safe=""))
PY
)"
runtime_database_url="postgresql://${POSTGRES_ADMIN_USERNAME}:${encoded_password}@${POSTGRES_SERVER_NAME}.postgres.database.azure.com:5432/${POSTGRES_DATABASE_NAME}?sslmode=require"
foundry_project_id="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${TARGET_RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_ACCOUNT_NAME}/projects/${FOUNDRY_PROJECT_NAME}"
foundry_project_endpoint="https://${FOUNDRY_ACCOUNT_NAME}.services.ai.azure.com/api/projects/${FOUNDRY_PROJECT_NAME}"

cd "$FOUNDRY_DIR"
if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$AZD_ENVIRONMENT_NAME" --no-prompt >/dev/null 2>&1; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env new "$AZD_ENVIRONMENT_NAME" \
    --location "$AZURE_LOCATION" \
    --subscription "$AZURE_SUBSCRIPTION_ID" \
    --no-prompt
fi

AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set \
  AZURE_SUBSCRIPTION_ID="$AZURE_SUBSCRIPTION_ID" \
  AZURE_LOCATION="$AZURE_LOCATION" \
  AZURE_RESOURCE_GROUP="$TARGET_RESOURCE_GROUP" \
  NAME_PREFIX="$NAME_PREFIX" \
  NETWORK_MODE=private \
  FOUNDRY_LOCATION="$AZURE_LOCATION" \
  FOUNDRY_PROJECT_NAME="$FOUNDRY_PROJECT_NAME" \
  FOUNDRY_PROJECT_ID="$foundry_project_id" \
  FOUNDRY_PROJECTS_ENDPOINT="$foundry_project_endpoint" \
  FOUNDRY_PROJECT_ENDPOINT="$foundry_project_endpoint" \
  POSTGRES_SERVER_NAME="$POSTGRES_SERVER_NAME" \
  POSTGRES_DATABASE_NAME="$POSTGRES_DATABASE_NAME" \
  POSTGRES_LOCATION="$POSTGRES_LOCATION" \
  POSTGRES_ADMIN_USERNAME="$POSTGRES_ADMIN_USERNAME" \
  POSTGRES_ADMIN_PASSWORD="$POSTGRES_ADMIN_PASSWORD" \
  CREATE_POSTGRES_SERVER=false \
  RUNTIME_DATABASE_URL="$runtime_database_url" \
  DATABASE_URL="$runtime_database_url" \
  ENABLE_CONTAINER_APPS=true \
  ENABLE_POSTGRES_PRIVATE_ENDPOINT=true \
  MANAGE_PROJECT_CONNECTIONS=false

echo "Bootstrapped the selected private AZD environment without displaying secrets."
