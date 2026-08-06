#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
# Fixed Azure target; do not parameterize this destructive workflow.
readonly SUBSCRIPTION_ID='4f18d577-3506-4a11-85e5-a83b14727a84'
readonly RESOURCE_GROUP='rg-underwriting-readiness-0731'
readonly SERVER_NAME='azpgwhcedyxchnbtmpub'
readonly SERVER_LOCATION='northcentralus'
readonly DATABASE_NAME='underwriting'
readonly CONFIRMATION_TOKEN='REBUILD-azpgwhcedyxchnbtmpub'

usage() {
  cat >&2 <<EOF
This permanently deletes PostgreSQL Flexible Server '$SERVER_NAME' and its underwriting database.
Run only with the exact confirmation token:
  make foundry-postgres-rebuild CONFIRM=$CONFIRMATION_TOKEN
EOF
  exit 2
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

[[ "$#" -eq 1 && "$1" == "$CONFIRMATION_TOKEN" ]] || usage

require_bin az
require_bin azd
require_bin make

# A recreated server needs a new administrator password, not the unavailable
# password of the deleted server. Persist it only in the local azd environment.
admin_password="$(
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value POSTGRES_ADMIN_PASSWORD --cwd "$FOUNDRY_DIR" --no-prompt
)"
if [[ -z "$admin_password" ]]; then
  require_bin openssl
  admin_password="Pgsql!9$(openssl rand -hex 32)"
  if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set POSTGRES_ADMIN_PASSWORD "$admin_password" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null; then
    echo "Unable to save the new PostgreSQL administrator password in the local azd environment." >&2
    exit 1
  fi
  echo "Generated a new PostgreSQL administrator password in the local azd environment."
fi
unset admin_password

az account set --subscription "$SUBSCRIPTION_ID"
active_subscription="$(az account show --query id --output tsv)"
if [[ "$active_subscription" != "$SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI did not select the expected subscription; refusing to delete." >&2
  exit 1
fi

if ! az postgres flexible-server list-skus --location "$SERVER_LOCATION" --output json \
  | grep -Fq '"name": "Standard_D2ds_v5"'; then
  echo "The captured Standard_D2ds_v5 SKU is unavailable in $SERVER_LOCATION; refusing to delete." >&2
  exit 1
fi

# Listing is intentionally scoped to the fixed resource group. This makes a
# retry after a failed provision safe: an already-deleted server is recreated,
# never substituted with a server selected by caller input.
existing_server="$(
  az postgres flexible-server list \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='$SERVER_NAME'].name | [0]" \
    --output tsv
)"

if [[ "$existing_server" == "$SERVER_NAME" ]]; then
  echo "Deleting PostgreSQL Flexible Server '$SERVER_NAME' in '$RESOURCE_GROUP'."
  az postgres flexible-server delete \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --yes
  echo "Waiting for PostgreSQL Flexible Server deletion to finish."
  az postgres flexible-server wait \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --deleted \
    --interval 15 \
    --timeout 1800
else
  echo "PostgreSQL Flexible Server '$SERVER_NAME' is already absent; continuing with declarative recreation."
fi

echo "Recreating '$SERVER_NAME' and database resources through Bicep."
# Do not allow caller-provided environment values to turn the provision phase
# into a different server or database after this script has deleted the fixed
# target. Bicep contains the remaining captured creation settings.
POSTGRES_SERVER_NAME="$SERVER_NAME" \
POSTGRES_SERVER_LOCATION="$SERVER_LOCATION" \
POSTGRES_DATABASE="$DATABASE_NAME" \
POSTGRES_ADMIN_USERNAME='pgadmin' \
  make -C "$ROOT_DIR" foundry-provision
