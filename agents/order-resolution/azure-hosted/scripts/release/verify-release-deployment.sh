#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"
source "$ROOT_DIR/scripts/release/selected-target.sh"
source "$ROOT_DIR/scripts/release/release-artifacts.sh"

environment="${AZURE_ENV_NAME:-$APPROVED_AZURE_ENV_NAME}"

get_azd_output() {
  azd env get-value "$1" --environment "$environment" 2>/dev/null
}

require_azd_output() {
  local name="$1"
  local value
  value="$(get_azd_output "$name")"
  [[ -n "$value" ]] || {
    echo "Selected AZD environment is missing required output: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

resolve_app_names() {
  az containerapp list \
    --resource-group "$APPROVED_AZURE_RESOURCE_GROUP" \
    --subscription "$APPROVED_AZURE_SUBSCRIPTION_ID" \
    --output json |
    python3 -c '
import json
import sys

apps = json.load(sys.stdin)
by_service = {}
for app in apps:
    service = (app.get("tags") or {}).get("azd-service-name")
    if service in {"backend", "frontend"}:
        by_service.setdefault(service, []).append(app["name"])
for service in ("backend", "frontend"):
    matches = by_service.get(service, [])
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one Container App tagged azd-service-name={service}.")
    print(matches[0])
'
}

active_revision() {
  local subscription_id="$1"
  local resource_group="$2"
  local app_name="$3"

  python3 - "$subscription_id" "$resource_group" "$app_name" <<'PY'
import json
import subprocess
import sys

subscription_id, resource_group, app_name = sys.argv[1:]
revisions = json.loads(
    subprocess.check_output(
        [
            "az",
            "containerapp",
            "revision",
            "list",
            "--subscription",
            subscription_id,
            "--resource-group",
            resource_group,
            "--name",
            app_name,
            "--output",
            "json",
        ],
        text=True,
    )
)
active = []
for item in revisions:
    properties = item.get("properties", {})
    template = item.get("template") or properties.get("template") or {}
    containers = template.get("containers") or []
    active_flag = item.get("active")
    if active_flag is None:
        active_flag = properties.get("active")
    if active_flag is not True or not containers:
        continue
    active.append(
        {
            "name": item.get("name"),
            "active": True,
            "image": containers[0].get("image", ""),
            "traffic_weight": item.get("trafficWeight", properties.get("trafficWeight", 0)),
            "health_state": item.get("healthState", properties.get("healthState", "")),
            "running_state": item.get("runningState", properties.get("runningState", "")),
        }
    )
if len(active) != 1:
    raise SystemExit(f"Container App {app_name} must have exactly one active revision.")
revision = active[0]
if revision["traffic_weight"] != 100:
    raise SystemExit(f"Container App {app_name} active revision must receive 100% of traffic.")
if revision["running_state"] not in {"", "Running"}:
    raise SystemExit(f"Container App {app_name} active revision is not running.")
if revision["health_state"] not in {"", "Healthy"}:
    raise SystemExit(f"Container App {app_name} active revision is not healthy.")
print(json.dumps(revision))
PY
}

write_release_context \
  "$environment" \
  "$APPROVED_AZURE_SUBSCRIPTION_ID" \
  "$APPROVED_AZURE_RESOURCE_GROUP" \
  "$APPROVED_AZURE_LOCATION"

subscription_id="$(require_azd_output AZURE_SUBSCRIPTION_ID)"
resource_group="$(require_azd_output AZURE_RESOURCE_GROUP)"
location="$(require_azd_output AZURE_LOCATION)"
api_url="$(require_azd_output API_URL)"
web_url="$(require_azd_output WEB_URL)"

require_selected_target "$environment" "$subscription_id" "$resource_group" "$location"
require_azure_cli_target "$subscription_id"

readarray -t app_names < <(resolve_app_names)
[[ "${#app_names[@]}" == 2 ]] || {
  echo "Unable to resolve backend and frontend Container Apps." >&2
  exit 1
}
backend_app="${app_names[0]}"
frontend_app="${app_names[1]}"
verification_temp_dir="$(mktemp -d)"
trap 'rm -rf "$verification_temp_dir"' EXIT
backend_json_file="$verification_temp_dir/backend.containerapp.json"
frontend_json_file="$verification_temp_dir/frontend.containerapp.json"
backend_revision_file="$verification_temp_dir/backend.revision.json"
frontend_revision_file="$verification_temp_dir/frontend.revision.json"

(
  az containerapp show \
    --name "$backend_app" \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --output json >"$backend_json_file"
) &
backend_show_pid=$!
(
  az containerapp show \
    --name "$frontend_app" \
    --resource-group "$resource_group" \
    --subscription "$subscription_id" \
    --output json >"$frontend_json_file"
) &
frontend_show_pid=$!
backend_show_status=0
frontend_show_status=0
wait "$backend_show_pid" || backend_show_status=$?
wait "$frontend_show_pid" || frontend_show_status=$?
if (( backend_show_status != 0 || frontend_show_status != 0 )); then
  echo "Unable to read both Container App resources." >&2
  exit 1
fi
backend_json="$(cat "$backend_json_file")"
frontend_json="$(cat "$frontend_json_file")"

backend_external="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["external"]).lower())' <<<"$backend_json")"
frontend_external="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["external"]).lower())' <<<"$frontend_json")"
[[ "$backend_external" == "false" && "$frontend_external" == "true" ]] || {
  echo "Expected internal backend and external frontend ingress." >&2
  exit 1
}

active_revision "$subscription_id" "$resource_group" "$backend_app" >"$backend_revision_file" &
backend_revision_pid=$!
active_revision "$subscription_id" "$resource_group" "$frontend_app" >"$frontend_revision_file" &
frontend_revision_pid=$!
backend_revision_status=0
frontend_revision_status=0
wait "$backend_revision_pid" || backend_revision_status=$?
wait "$frontend_revision_pid" || frontend_revision_status=$?
if (( backend_revision_status != 0 || frontend_revision_status != 0 )); then
  echo "Unable to verify both active Container App revisions." >&2
  exit 1
fi
backend_revision="$(cat "$backend_revision_file")"
frontend_revision="$(cat "$frontend_revision_file")"
images_file="$(release_artifact_path images.json)"
deployment_file="$(release_artifact_path deployment.json)"
backend_log_relative=""
frontend_log_relative=""

for candidate in backend.deploy.log frontend.deploy.log backend.image-deploy.log frontend.image-deploy.log; do
  if [[ -f "$RELEASE_LOGS_DIR/$candidate" ]]; then
    case "$candidate" in
      backend.*) backend_log_relative="logs/$candidate" ;;
      frontend.*) frontend_log_relative="logs/$candidate" ;;
    esac
  fi
done

if [[ -f "$images_file" ]]; then
  python3 - "$images_file" "$RELEASE_ID" "$RELEASE_STARTED_AT" "$backend_revision" "$frontend_revision" <<'PY'
import json
import sys
from pathlib import Path

path, release_id, release_started_at, backend_revision_json, frontend_revision_json = sys.argv[1:]
payload = json.loads(Path(path).read_text(encoding="utf-8"))
if payload.get("contract") != "azure-hosted-release/v1":
    raise SystemExit("Existing images.json is missing the canonical release contract.")
if payload.get("lane") != "azure-hosted" or payload.get("artifact_type") != "images":
    raise SystemExit("Existing images.json is not an azure-hosted images artifact.")
if payload.get("release_id") != release_id:
    raise SystemExit("Existing images.json belongs to a different release.")
if payload.get("release_started_at") != release_started_at:
    raise SystemExit("Existing images.json belongs to a different release window.")
backend_image = json.loads(backend_revision_json)["image"]
frontend_image = json.loads(frontend_revision_json)["image"]
if payload.get("backend", {}).get("image") != backend_image:
    raise SystemExit("Existing images.json backend digest does not match the active revision.")
if payload.get("frontend", {}).get("image") != frontend_image:
    raise SystemExit("Existing images.json frontend digest does not match the active revision.")
PY
fi

python3 - "$images_file" \
  "$deployment_file" \
  "$RELEASE_ID" \
  "$RELEASE_STARTED_AT" \
  "$environment" \
  "$subscription_id" \
  "$resource_group" \
  "$location" \
  "$api_url" \
  "$web_url" \
  "$backend_json" \
  "$backend_app" \
  "$backend_revision" \
  "$frontend_json" \
  "$frontend_app" \
  "$frontend_revision" \
  "$backend_log_relative" \
  "$frontend_log_relative" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    images_path,
    deployment_path,
    release_id,
    release_started_at,
    environment,
    subscription_id,
    resource_group,
    location,
    api_url,
    web_url,
    backend_app_json,
    backend_app,
    backend_revision_json,
    frontend_app_json,
    frontend_app,
    frontend_revision_json,
    backend_log,
    frontend_log,
) = sys.argv[1:]
backend_app_payload = json.loads(backend_app_json)
backend_revision = json.loads(backend_revision_json)
frontend_app_payload = json.loads(frontend_app_json)
frontend_revision = json.loads(frontend_revision_json)
timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")


def image_digest(image: str) -> str | None:
    if "@sha256:" not in image:
        return None
    return image.split("@", 1)[1]


def service_payload(
    *,
    service_name: str,
    app_name: str,
    app_payload: dict[str, object],
    revision: dict[str, object],
    deploy_log: str,
) -> dict[str, object]:
    properties = app_payload.get("properties") or {}
    configuration = properties.get("configuration") or {}
    ingress = configuration.get("ingress") or {}
    identity = app_payload.get("identity") or {}
    return {
        "azd_service_name": service_name,
        "container_app": app_name,
        "resource_id": app_payload.get("id"),
        "image": revision["image"],
        "image_digest": image_digest(str(revision["image"])),
        "revision": revision["name"],
        "active_revision": {
            "name": revision["name"],
            "active": True,
            "traffic_weight": revision.get("traffic_weight"),
            "health_state": revision.get("health_state") or "Healthy",
            "running_state": revision.get("running_state") or "Running",
        },
        "ingress": {
            "external": ingress.get("external"),
            "fqdn": ingress.get("fqdn"),
            "target_port": ingress.get("targetPort"),
            "transport": ingress.get("transport"),
        },
        "target_identity": {
            "resource_id": app_payload.get("id"),
            "managed_identity_type": identity.get("type"),
            "principal_id": identity.get("principalId"),
            "tenant_id": identity.get("tenantId"),
        },
        "deploy_log": deploy_log or None,
    }


backend_service = service_payload(
    service_name="backend",
    app_name=backend_app,
    app_payload=backend_app_payload,
    revision=backend_revision,
    deploy_log=backend_log,
)
frontend_service = service_payload(
    service_name="frontend",
    app_name=frontend_app,
    app_payload=frontend_app_payload,
    revision=frontend_revision,
    deploy_log=frontend_log,
)

images_payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "artifact_type": "images",
    "status": "passed",
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": timestamp,
    "target": {
        "azd_env_name": environment,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
    },
    "backend": {
        "container_app": backend_app,
        "resource_id": backend_service["resource_id"],
        "image": backend_revision["image"],
        "image_digest": backend_service["image_digest"],
        "revision": backend_revision["name"],
    },
    "frontend": {
        "container_app": frontend_app,
        "resource_id": frontend_service["resource_id"],
        "image": frontend_revision["image"],
        "image_digest": frontend_service["image_digest"],
        "revision": frontend_revision["name"],
    },
}
deployment_payload = {
    "schema_version": 1,
    "contract": "azure-hosted-release/v1",
    "lane": "azure-hosted",
    "artifact_type": "deployment",
    "status": "passed",
    "release_id": release_id,
    "release_started_at": release_started_at,
    "generated_at": timestamp,
    "target": {
        "azd_env_name": environment,
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "location": location,
    },
    "deploy_mode": "app_only",
    "api_url": api_url,
    "web_url": web_url,
    "verification": {
        "backend_external": False,
        "frontend_external": True,
        "backend_active_revision": backend_revision["name"],
        "frontend_active_revision": frontend_revision["name"],
    },
    "services": {
        "backend": backend_service,
        "frontend": frontend_service,
    },
}
Path(images_path).write_text(json.dumps(images_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path(deployment_path).write_text(json.dumps(deployment_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "Verified active backend/frontend revisions and wrote deployment evidence."
