#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
source "$ROOT_DIR/scripts/release/selected-target.sh"
PROFILE="${BOOTSTRAP_PROFILE:-$APPROVED_PROFILE_PATH}"

for command_name in az azd python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

deployment_profile_load "$PROFILE"
deployment_profile_validate
deployment_profile_export
require_selected_target \
  "$AZURE_ENV_NAME" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION"

for key in POSTGRES_BOOTSTRAP_ALLOWED_IP BACKEND_IMAGE FRONTEND_IMAGE \
  POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID; do
  [[ -n "${!key:-}" ]] || {
    echo "$key must be supplied by the operator and is intentionally not tracked." >&2
    exit 1
  }
done

python3 - "$POSTGRES_BOOTSTRAP_ALLOWED_IP" <<'PY'
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
if address.version != 4 or not address.is_global:
    raise SystemExit("POSTGRES_BOOTSTRAP_ALLOWED_IP must be a public IPv4 address.")
PY

for image_variable in BACKEND_IMAGE FRONTEND_IMAGE; do
  image="${!image_variable}"
  [[ "$image" == */* && "$image" != *"REPLACE_"* && "${image,,}" != *placeholder* ]] || {
    echo "$image_variable must be an explicit deployable image reference." >&2
    exit 1
  }
done

for sku_variable in \
  FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME \
  FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME; do
  sku_value="${!sku_variable}"
  case "$sku_value" in
    Standard|DataZoneStandard|GlobalStandard) ;;
    *)
      echo "$sku_variable is not a supported explicit bootstrap SKU." >&2
      exit 1
      ;;
  esac
  printf -v "$sku_variable" '%s' "$sku_value"
done

for capacity_variable in \
  FOUNDRY_CHAT_DEPLOYMENT_CAPACITY \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY \
  FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY; do
  [[ "${!capacity_variable}" =~ ^[1-9][0-9]*$ ]] || {
    echo "$capacity_variable must be a positive integer." >&2
    exit 1
  }
done

require_azure_cli_target "$AZURE_SUBSCRIPTION_ID"

azd env new "$AZURE_ENV_NAME" --no-prompt >/dev/null 2>&1 || \
  azd env select "$AZURE_ENV_NAME" --no-prompt

set_azd_value() {
  azd env set "$1" "$2" --environment "$AZURE_ENV_NAME" --no-prompt >/dev/null
}

set_azd_value AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
set_azd_value AZURE_TENANT_ID "$AZURE_TENANT_ID"
set_azd_value AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
set_azd_value AZURE_LOCATION "$AZURE_LOCATION"
set_azd_value INFRASTRUCTURE_MODE bootstrap
set_azd_value NAME_PREFIX "$NAME_PREFIX"
set_azd_value POSTGRES_DATABASE_NAME "$POSTGRES_DATABASE_NAME"
set_azd_value POSTGRES_SKU_NAME "$POSTGRES_SKU_NAME"
set_azd_value POSTGRES_SKU_TIER "$POSTGRES_SKU_TIER"
set_azd_value POSTGRES_VERSION "$POSTGRES_VERSION"
set_azd_value POSTGRES_BOOTSTRAP_ALLOWED_IP "$POSTGRES_BOOTSTRAP_ALLOWED_IP"
set_azd_value BACKEND_IMAGE "$BACKEND_IMAGE"
set_azd_value FRONTEND_IMAGE "$FRONTEND_IMAGE"
set_azd_value FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME "$FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME"
set_azd_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME"
set_azd_value FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME "$FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME"
set_azd_value FOUNDRY_PROJECT_NAME "$FOUNDRY_PROJECT_NAME"
set_azd_value FOUNDRY_CHAT_DEPLOYMENT_NAME "$FOUNDRY_CHAT_DEPLOYMENT_NAME"
set_azd_value FOUNDRY_CHAT_MODEL_FORMAT "$FOUNDRY_CHAT_MODEL_FORMAT"
set_azd_value FOUNDRY_CHAT_MODEL_NAME "$FOUNDRY_CHAT_MODEL_NAME"
set_azd_value FOUNDRY_CHAT_MODEL_VERSION "$FOUNDRY_CHAT_MODEL_VERSION"
set_azd_value FOUNDRY_CHAT_DEPLOYMENT_CAPACITY "$FOUNDRY_CHAT_DEPLOYMENT_CAPACITY"
set_azd_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME"
set_azd_value FOUNDRY_EMBEDDINGS_MODEL_FORMAT "$FOUNDRY_EMBEDDINGS_MODEL_FORMAT"
set_azd_value FOUNDRY_EMBEDDINGS_MODEL_NAME "$FOUNDRY_EMBEDDINGS_MODEL_NAME"
set_azd_value FOUNDRY_EMBEDDINGS_MODEL_VERSION "$FOUNDRY_EMBEDDINGS_MODEL_VERSION"
set_azd_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY "$FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY"
set_azd_value FOUNDRY_EVALUATOR_DEPLOYMENT_NAME "$FOUNDRY_EVALUATOR_DEPLOYMENT_NAME"
set_azd_value FOUNDRY_EVALUATOR_MODEL_FORMAT "$FOUNDRY_EVALUATOR_MODEL_FORMAT"
set_azd_value FOUNDRY_EVALUATOR_MODEL_NAME "$FOUNDRY_EVALUATOR_MODEL_NAME"
set_azd_value FOUNDRY_EVALUATOR_MODEL_VERSION "$FOUNDRY_EVALUATOR_MODEL_VERSION"
set_azd_value FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY "$FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY"
set_azd_value FOUNDRY_RAI_POLICY_NAME "$FOUNDRY_RAI_POLICY_NAME"
set_azd_value FOUNDRY_EVALUATION_OPERATOR_PRINCIPAL_ID "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID"
set_azd_value POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME"
set_azd_value POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID"
set_azd_value MCP_SERVER_URL "${MCP_SERVER_URL:-}"
set_azd_value MCP_API_KEY "${MCP_API_KEY:-}"
set_azd_value MCP_BEARER_TOKEN "${MCP_BEARER_TOKEN:-}"

echo "Prepared the approved AZD target for explicit bootstrap mode."
echo "Run an AZD/Bicep preview before any separately authorized bootstrap deployment."
