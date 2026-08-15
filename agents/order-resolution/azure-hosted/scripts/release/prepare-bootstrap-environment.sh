#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
PROFILE="${BOOTSTRAP_PROFILE:-$ROOT_DIR/deployment/profiles/azure-hosted.env}"
source "$ROOT_DIR/scripts/release/selected-target.sh"

for command_name in az azd python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 1
  }
done

[[ -f "$PROFILE" && ! -L "$PROFILE" ]] || {
  echo "BOOTSTRAP_PROFILE must be a regular non-symlink file." >&2
  exit 1
}

allowed_keys=" CONTRACT_VERSION DEPLOYMENT_LANE AZURE_ENV_NAME AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP AZURE_LOCATION NAME_PREFIX POSTGRES_DATABASE_NAME "
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" =~ ^([A-Z0-9_]+)=([A-Za-z0-9._/-]+)$ ]] || {
    echo "Invalid bootstrap profile line: $line" >&2
    exit 1
  }
  key="${BASH_REMATCH[1]}"
  value="${BASH_REMATCH[2]}"
  [[ "$allowed_keys" == *" $key "* ]] || {
    echo "Unsupported bootstrap profile key: $key" >&2
    exit 1
  }
  printf -v "$key" '%s' "$value"
done <"$PROFILE"

for key in CONTRACT_VERSION DEPLOYMENT_LANE AZURE_ENV_NAME AZURE_SUBSCRIPTION_ID \
  AZURE_RESOURCE_GROUP AZURE_LOCATION NAME_PREFIX POSTGRES_DATABASE_NAME; do
  [[ -n "${!key:-}" ]] || {
    echo "Bootstrap profile is missing $key." >&2
    exit 1
  }
done

[[ "$CONTRACT_VERSION" == "1" && "$DEPLOYMENT_LANE" == "azure-hosted" ]] || {
  echo "Bootstrap profile contract is not supported by this lane." >&2
  exit 1
}
require_selected_target \
  "$AZURE_ENV_NAME" \
  "$AZURE_SUBSCRIPTION_ID" \
  "$AZURE_RESOURCE_GROUP" \
  "$AZURE_LOCATION"
[[ "$NAME_PREFIX" == "maf-ora-azure" && "$POSTGRES_DATABASE_NAME" == "maf_workflow" ]] || {
  echo "Bootstrap profile naming/database values do not match the approved topology." >&2
  exit 1
}

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

FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME="${FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME:-Standard}"
FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME="${FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME:-DataZoneStandard}"
FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME="${FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME:-Standard}"
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

FOUNDRY_PROJECT_NAME="${FOUNDRY_PROJECT_NAME:-order-resolution}"
FOUNDRY_CHAT_DEPLOYMENT_NAME="${FOUNDRY_CHAT_DEPLOYMENT_NAME:-gpt-4.1-mini}"
FOUNDRY_CHAT_MODEL_FORMAT="${FOUNDRY_CHAT_MODEL_FORMAT:-OpenAI}"
FOUNDRY_CHAT_MODEL_NAME="${FOUNDRY_CHAT_MODEL_NAME:-gpt-4.1-mini}"
FOUNDRY_CHAT_MODEL_VERSION="${FOUNDRY_CHAT_MODEL_VERSION:-2025-04-14}"
FOUNDRY_CHAT_DEPLOYMENT_CAPACITY="${FOUNDRY_CHAT_DEPLOYMENT_CAPACITY:-50}"
FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME="${FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME:-text-embedding-3-small}"
FOUNDRY_EMBEDDINGS_MODEL_FORMAT="${FOUNDRY_EMBEDDINGS_MODEL_FORMAT:-OpenAI}"
FOUNDRY_EMBEDDINGS_MODEL_NAME="${FOUNDRY_EMBEDDINGS_MODEL_NAME:-text-embedding-3-small}"
FOUNDRY_EMBEDDINGS_MODEL_VERSION="${FOUNDRY_EMBEDDINGS_MODEL_VERSION:-1}"
FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY="${FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY:-1}"
FOUNDRY_EVALUATOR_DEPLOYMENT_NAME="${FOUNDRY_EVALUATOR_DEPLOYMENT_NAME:-gpt-4.1-mini-evaluator}"
FOUNDRY_EVALUATOR_MODEL_FORMAT="${FOUNDRY_EVALUATOR_MODEL_FORMAT:-OpenAI}"
FOUNDRY_EVALUATOR_MODEL_NAME="${FOUNDRY_EVALUATOR_MODEL_NAME:-gpt-4.1-mini}"
FOUNDRY_EVALUATOR_MODEL_VERSION="${FOUNDRY_EVALUATOR_MODEL_VERSION:-2025-04-14}"
FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY="${FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY:-50}"
FOUNDRY_RAI_POLICY_NAME="${FOUNDRY_RAI_POLICY_NAME:-Microsoft.Default}"

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
set_azd_value AZURE_RESOURCE_GROUP "$AZURE_RESOURCE_GROUP"
set_azd_value AZURE_LOCATION "$AZURE_LOCATION"
set_azd_value INFRASTRUCTURE_MODE bootstrap
set_azd_value NAME_PREFIX "$NAME_PREFIX"
set_azd_value POSTGRES_DATABASE_NAME "$POSTGRES_DATABASE_NAME"
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
set_azd_value POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME"
set_azd_value POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID "$POSTGRES_ENTRA_ADMIN_PRINCIPAL_ID"
set_azd_value MCP_SERVER_URL "${MCP_SERVER_URL:-}"
set_azd_value MCP_API_KEY "${MCP_API_KEY:-}"
set_azd_value MCP_BEARER_TOKEN "${MCP_BEARER_TOKEN:-}"

echo "Prepared the approved AZD target for explicit bootstrap mode."
echo "Run an AZD/Bicep preview before any separately authorized bootstrap deployment."
