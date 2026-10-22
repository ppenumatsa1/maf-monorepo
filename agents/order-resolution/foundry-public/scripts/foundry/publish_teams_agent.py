#!/usr/bin/env python3
"""Versioned Microsoft 365 package and publication orchestration for Foundry agents."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

import reconcile_activity_endpoint as activity

SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
GUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
BOT_RESOURCE_ID = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
    r"Microsoft\.BotService/botServices/[^/]+$",
    re.IGNORECASE,
)
LOG_ANALYTICS_WORKSPACE_RESOURCE_ID = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
    r"Microsoft\.OperationalInsights/workspaces/[^/]+$",
    re.IGNORECASE,
)
PROJECT_HOST_SUFFIX = ".services.ai.azure.com"
PROJECT_PATH_PREFIX = "/api/projects/"
MAX_PUBLICATION_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_ERROR_BYTES = 256 * 1024
MAX_SAFE_ERROR_DETAIL = 800
PUBLIC_STATE_SCHEMA = 1
SENSITIVE_STATE_SCHEMA = 1
GUID_IN_TEXT = re.compile(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
RESOURCE_ID_IN_TEXT = re.compile(
    r"/subscriptions/[^\s\"']+(?:/[^\s\"']+)*",
    re.IGNORECASE,
)
URL_IN_TEXT = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
EMAIL_IN_TEXT = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")
TOKEN_IN_TEXT = re.compile(r"\b[A-Za-z0-9_-]{80,}\b")
SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
SAFE_RESOURCE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")
MANIFEST_KEYS = {
    "schemaVersion",
    "appVersion",
    "publishScope",
    "publishAsAutopilot",
    "metadata",
}
METADATA_KEYS = {
    "agentDisplayName",
    "shortDescription",
    "fullDescription",
    "developerName",
    "developerWebsiteUrl",
    "privacyUrl",
    "termsOfUseUrl",
}
RECORD_KEYS = {
    "manifestHash",
    "scope",
    "botDeployed",
    "botDeployedAt",
    "packageGenerated",
    "packageGeneratedAt",
    "published",
    "publishedAt",
}


class PublicationError(activity.ReconcileError):
    """Expected sanitized publication failure."""


@dataclass(frozen=True)
class PublicationManifest:
    app_version: str
    version_tuple: tuple[int, int, int]
    publish_scope: str
    publish_as_autopilot: bool
    metadata: dict[str, str]
    sha256: str


@dataclass(frozen=True)
class ProjectCoordinates:
    foundry_resource_name: str
    foundry_project_name: str


@dataclass(frozen=True)
class AzureContext:
    tenant_id: str
    user_type: str


class CommandRunner(Protocol):
    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_exact_keys(document: Mapping[str, Any], expected: set[str], description: str) -> None:
    actual = set(document)
    if actual != expected:
        raise PublicationError(
            f"{description} must contain exactly the documented template fields."
        )


def _require_text(value: Any, description: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PublicationError(f"{description} must be a non-empty bounded string.")
    return value.strip()


def _require_https_url(value: Any, description: str) -> str:
    text = _require_text(value, description, maximum=2048)
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise PublicationError(f"{description} must be an absolute HTTPS URL.")
    return text


def load_manifest(path: Path) -> PublicationManifest:
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except OSError:
        raise PublicationError("The committed publication manifest could not be read.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationError("The committed publication manifest is not valid JSON.") from None
    if not isinstance(document, dict):
        raise PublicationError("The publication manifest must be a JSON object.")
    _require_exact_keys(document, MANIFEST_KEYS, "The publication manifest")
    if document["schemaVersion"] != 1:
        raise PublicationError("The publication manifest schemaVersion must be 1.")

    app_version = _require_text(document["appVersion"], "appVersion", maximum=64)
    match = SEMVER.fullmatch(app_version)
    if match is None:
        raise PublicationError("appVersion must use explicit MAJOR.MINOR.PATCH semantics.")
    publish_scope = document["publishScope"]
    if publish_scope not in activity.SCOPE_AUTH_TYPES:
        raise PublicationError("publishScope must be Shared or Tenant.")
    if document["publishAsAutopilot"] is not False:
        raise PublicationError("publishAsAutopilot must remain false for this workflow.")

    metadata_value = document["metadata"]
    if not isinstance(metadata_value, dict):
        raise PublicationError("metadata must be an object.")
    _require_exact_keys(metadata_value, METADATA_KEYS, "metadata")
    metadata = {
        "agentDisplayName": _require_text(
            metadata_value["agentDisplayName"], "agentDisplayName", maximum=128
        ),
        "shortDescription": _require_text(
            metadata_value["shortDescription"], "shortDescription", maximum=80
        ),
        "fullDescription": _require_text(
            metadata_value["fullDescription"], "fullDescription", maximum=4000
        ),
        "developerName": _require_text(
            metadata_value["developerName"], "developerName", maximum=128
        ),
        "developerWebsiteUrl": _require_https_url(
            metadata_value["developerWebsiteUrl"], "developerWebsiteUrl"
        ),
        "privacyUrl": _require_https_url(metadata_value["privacyUrl"], "privacyUrl"),
        "termsOfUseUrl": _require_https_url(metadata_value["termsOfUseUrl"], "termsOfUseUrl"),
    }
    return PublicationManifest(
        app_version=app_version,
        version_tuple=tuple(int(part) for part in match.groups()),
        publish_scope=publish_scope,
        publish_as_autopilot=False,
        metadata=metadata,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def parse_project_endpoint(project_endpoint: str) -> ProjectCoordinates:
    parsed = urlsplit(project_endpoint)
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme != "https"
        or not parsed.netloc.endswith(PROJECT_HOST_SUFFIX)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not path.startswith(PROJECT_PATH_PREFIX)
    ):
        raise PublicationError("Project endpoint does not match the Foundry project URL shape.")
    resource_name = parsed.netloc[: -len(PROJECT_HOST_SUFFIX)]
    project_name = unquote(path[len(PROJECT_PATH_PREFIX) :])
    for value in (resource_name, project_name):
        if (
            not value
            or "/" in value
            or " " in value
            or any(character in value for character in "?#")
        ):
            raise PublicationError(
                "Project endpoint contains a resource or project name that is not deployable."
            )
    return ProjectCoordinates(resource_name, project_name)


def extract_agent_identity_client_id(document: Mapping[str, Any]) -> str:
    instance_identity = document.get("instance_identity")
    if not isinstance(instance_identity, dict):
        raise PublicationError("Agent response is missing instance_identity.")
    client_id = instance_identity.get("client_id")
    if not isinstance(client_id, str) or GUID.fullmatch(client_id) is None:
        raise PublicationError("Agent response contains an invalid identity client ID.")
    return client_id


def _azure_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["AZURE_DEV_USER_AGENT"] = "microsoft_foundry_skill"
    return environment


def get_azure_context(runner: CommandRunner = _run_command) -> AzureContext:
    result = runner(
        [
            "az",
            "account",
            "show",
            "--query",
            "{tenantId:tenantId,userType:user.type}",
            "--output",
            "json",
            "--only-show-errors",
        ],
        env=_azure_environment(),
    )
    if result.returncode != 0:
        raise PublicationError(
            f"Azure CLI account inspection failed with exit code {result.returncode}."
        )
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise PublicationError("Azure CLI account inspection returned malformed JSON.") from None
    if not isinstance(document, dict):
        raise PublicationError("Azure CLI account inspection returned malformed JSON.")
    tenant_id = document.get("tenantId")
    user_type = document.get("userType")
    if not isinstance(tenant_id, str) or GUID.fullmatch(tenant_id) is None:
        raise PublicationError("Azure CLI account context has an invalid tenant.")
    if not isinstance(user_type, str) or not user_type:
        raise PublicationError("Azure CLI account context has no identity type.")
    return AzureContext(tenant_id=tenant_id, user_type=user_type)


def require_interactive_user(context: AzureContext, publish_scope: str) -> None:
    if publish_scope == "Shared" and context.user_type.casefold() != "user":
        raise PublicationError(
            "Shared publication requires an interactive Azure CLI user login; "
            "service-principal and managed-identity contexts are rejected."
        )


def build_bicep_command(
    *,
    resource_group: str,
    template_file: Path,
    coordinates: ProjectCoordinates,
    agent_name: str,
    agent_identity_client_id: str,
    tenant_id: str,
    log_analytics_workspace_resource_id: str,
    bot_name: str,
    bot_sku_name: str,
    bot_display_name: str,
) -> list[str]:
    if not resource_group.strip():
        raise PublicationError("Azure resource group is required.")
    if GUID.fullmatch(agent_identity_client_id) is None or GUID.fullmatch(tenant_id) is None:
        raise PublicationError("Runtime identity inputs must have GUID shape.")
    if LOG_ANALYTICS_WORKSPACE_RESOURCE_ID.fullmatch(log_analytics_workspace_resource_id) is None:
        raise PublicationError("Log Analytics workspace resource ID is malformed.")
    if SAFE_RESOURCE_NAME.fullmatch(bot_name) is None:
        raise PublicationError("Bot Service name is malformed.")
    if bot_sku_name not in {"F0", "S1"}:
        raise PublicationError("Bot Service SKU must be F0 or S1.")
    return [
        "az",
        "deployment",
        "group",
        "create",
        "--name",
        "foundry-teams-bot",
        "--resource-group",
        resource_group,
        "--template-file",
        str(template_file),
        "--parameters",
        f"foundryResourceName={coordinates.foundry_resource_name}",
        f"foundryProjectName={coordinates.foundry_project_name}",
        f"hostedAgentName={agent_name}",
        f"agentIdentityClientId={agent_identity_client_id}",
        f"tenantId={tenant_id}",
        f"logAnalyticsWorkspaceResourceId={log_analytics_workspace_resource_id}",
        f"botName={bot_name}",
        f"botSkuName={bot_sku_name}",
        f"botDisplayName={bot_display_name}",
        "--query",
        "properties.outputs",
        "--output",
        "json",
        "--only-show-errors",
    ]


def build_bicep_preview_command(
    *,
    resource_group: str,
    template_file: Path,
    coordinates: ProjectCoordinates,
    agent_name: str,
    agent_identity_client_id: str,
    tenant_id: str,
    log_analytics_workspace_resource_id: str,
    bot_name: str,
    bot_sku_name: str,
    bot_display_name: str,
) -> list[str]:
    command = build_bicep_command(
        resource_group=resource_group,
        template_file=template_file,
        coordinates=coordinates,
        agent_name=agent_name,
        agent_identity_client_id=agent_identity_client_id,
        tenant_id=tenant_id,
        log_analytics_workspace_resource_id=log_analytics_workspace_resource_id,
        bot_name=bot_name,
        bot_sku_name=bot_sku_name,
        bot_display_name=bot_display_name,
    )
    command[3] = "what-if"
    query_index = command.index("--query")
    del command[query_index : query_index + 2]
    output_index = command.index("--output")
    command[output_index + 1] = "json"
    command[output_index:output_index] = [
        "--result-format",
        "FullResourcePayloads",
        "--no-pretty-print",
    ]
    return command


def preview_bot(
    command: list[str],
    *,
    runner: CommandRunner = _run_command,
) -> dict[str, Any]:
    result = runner(command, env=_azure_environment())
    if result.returncode != 0:
        raise PublicationError(f"Teams Bot ARM what-if failed with exit code {result.returncode}.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise PublicationError("Teams Bot ARM what-if returned malformed JSON.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("changes", []), list):
        raise PublicationError("Teams Bot ARM what-if returned an invalid result.")
    return payload


def deploy_bot(
    command: list[str],
    *,
    runner: CommandRunner = _run_command,
) -> str:
    result = runner(command, env=_azure_environment())
    if result.returncode != 0:
        raise PublicationError(
            f"Bot Bicep deployment failed with exit code {result.returncode}; "
            "review the resource-group deployment operations."
        )
    try:
        outputs = json.loads(result.stdout)
        bot_resource_id = outputs["botResourceId"]["value"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise PublicationError("Bot Bicep deployment returned malformed outputs.") from None
    if not isinstance(bot_resource_id, str) or BOT_RESOURCE_ID.fullmatch(bot_resource_id) is None:
        raise PublicationError("Bot Bicep deployment returned an invalid botResourceId.")
    return bot_resource_id


def resolve_log_analytics_workspace_resource_id(
    *,
    resource_group: str,
    runner: CommandRunner = _run_command,
) -> str:
    result = runner(
        [
            "az",
            "monitor",
            "log-analytics",
            "workspace",
            "list",
            "--resource-group",
            resource_group,
            "--query",
            "[].id",
            "--output",
            "json",
            "--only-show-errors",
        ],
        env=_azure_environment(),
    )
    if result.returncode != 0:
        raise PublicationError(
            f"Log Analytics workspace lookup failed with exit code {result.returncode}."
        )
    try:
        workspace_ids = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise PublicationError("Log Analytics workspace lookup returned malformed JSON.") from None
    if not isinstance(workspace_ids, list) or len(workspace_ids) != 1:
        raise PublicationError(
            "The Teams Bot deployment requires exactly one Log Analytics workspace "
            "in the selected resource group."
        )
    workspace_id = workspace_ids[0]
    if (
        not isinstance(workspace_id, str)
        or LOG_ANALYTICS_WORKSPACE_RESOURCE_ID.fullmatch(workspace_id) is None
    ):
        raise PublicationError("Log Analytics workspace lookup returned an invalid resource ID.")
    return workspace_id


def resolve_bot_resource_id(
    explicit: str | None,
    *,
    resource_group: str,
    runner: CommandRunner = _run_command,
) -> str:
    if explicit:
        bot_resource_id = explicit.strip()
    else:
        result = runner(
            [
                "az",
                "deployment",
                "group",
                "show",
                "--name",
                "foundry-teams-bot",
                "--resource-group",
                resource_group,
                "--query",
                "properties.outputs.botResourceId.value",
                "--output",
                "tsv",
                "--only-show-errors",
            ],
            env=_azure_environment(),
        )
        if result.returncode != 0:
            raise PublicationError(
                f"Bot deployment output lookup failed with exit code {result.returncode}."
            )
        bot_resource_id = result.stdout.strip()
    if BOT_RESOURCE_ID.fullmatch(bot_resource_id) is None:
        raise PublicationError("Bot deployment output is missing or malformed.")
    return bot_resource_id


def build_publish_payload(
    manifest: PublicationManifest,
    bot_resource_id: str,
) -> dict[str, Any]:
    if BOT_RESOURCE_ID.fullmatch(bot_resource_id) is None:
        raise PublicationError("The Bot Service ARM ID is missing or malformed.")
    return {
        **manifest.metadata,
        "botServiceArmId": bot_resource_id,
        "publishScope": manifest.publish_scope,
        "publishAsAutopilot": manifest.publish_as_autopilot,
        "appVersion": manifest.app_version,
    }


def _read_bounded(stream: Any, maximum: int) -> bytes:
    raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise PublicationError("Foundry publication response exceeded the safe size limit.")
    return raw


def _is_version_exists_error(raw: bytes) -> bool:
    lowered = raw.lower()
    return b"version" in lowered and b"already exists" in lowered


def inspect_generated_package(raw: bytes, manifest: PublicationManifest) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            names = set(package.namelist())
            if "manifest.json" not in names:
                raise PublicationError("Microsoft 365 package response is missing manifest.json.")
            try:
                document = json.loads(package.read("manifest.json"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise PublicationError(
                    "Microsoft 365 package manifest.json is malformed."
                ) from None
    except zipfile.BadZipFile:
        raise PublicationError("Microsoft 365 package response is not a valid ZIP.") from None

    if not isinstance(document, dict):
        raise PublicationError("Microsoft 365 package manifest.json is malformed.")
    if document.get("version") != manifest.app_version:
        raise PublicationError("Microsoft 365 package version does not match appVersion.")

    name = document.get("name")
    descriptions = document.get("description")
    developer = document.get("developer")
    icons = document.get("icons")
    bots = document.get("bots")
    expected_full_name = manifest.metadata["agentDisplayName"]
    expected_short_name = expected_full_name[:30]
    if (
        not isinstance(name, dict)
        or name.get("short") != expected_short_name
        or name.get("full") != expected_full_name
        or not isinstance(descriptions, dict)
        or descriptions.get("short") != manifest.metadata["shortDescription"]
        or descriptions.get("full") != manifest.metadata["fullDescription"]
        or not isinstance(developer, dict)
        or developer.get("name") != manifest.metadata["developerName"]
        or developer.get("websiteUrl") != manifest.metadata["developerWebsiteUrl"]
        or developer.get("privacyUrl") != manifest.metadata["privacyUrl"]
        or developer.get("termsOfUseUrl") != manifest.metadata["termsOfUseUrl"]
    ):
        raise PublicationError(
            "Microsoft 365 package metadata does not match the publication manifest."
        )
    if not isinstance(icons, dict):
        raise PublicationError("Microsoft 365 package icon metadata is malformed.")
    for icon_type in ("color", "outline"):
        icon_name = icons.get(icon_type)
        if (
            not isinstance(icon_name, str)
            or not icon_name
            or Path(icon_name).name != icon_name
            or icon_name not in names
        ):
            raise PublicationError("Microsoft 365 package icon references are invalid.")
    if (
        not isinstance(bots, list)
        or len(bots) != 1
        or not isinstance(bots[0], dict)
        or not isinstance(bots[0].get("botId"), str)
        or GUID.fullmatch(bots[0]["botId"]) is None
    ):
        raise PublicationError("Microsoft 365 package Bot reference is invalid.")


def _sanitize_error_text(value: Any, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    text = RESOURCE_ID_IN_TEXT.sub("<redacted-resource-id>", text)
    text = GUID_IN_TEXT.sub("<redacted-guid>", text)
    text = EMAIL_IN_TEXT.sub("<redacted-email>", text)
    text = URL_IN_TEXT.sub("<redacted-url>", text)
    text = TOKEN_IN_TEXT.sub("<redacted-token>", text)
    return text[:maximum]


def _validation_error_detail(raw: bytes) -> str | None:
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    error = document.get("error", document)
    if not isinstance(error, dict):
        return None

    parts: list[str] = []
    code = error.get("code")
    if isinstance(code, str) and SAFE_ERROR_CODE.fullmatch(code):
        parts.append(f"code={code}")
    message = _sanitize_error_text(error.get("message"), maximum=500)
    if message:
        parts.append(f"message={message}")

    details = error.get("details")
    if isinstance(details, list):
        for detail in details[:3]:
            if not isinstance(detail, dict):
                continue
            target = _sanitize_error_text(detail.get("target"), maximum=80)
            detail_message = _sanitize_error_text(detail.get("message"), maximum=240)
            if target:
                parts.append(f"target={target}")
            if detail_message:
                parts.append(f"detail={detail_message}")

    if not parts:
        return None
    return "; ".join(parts)[:MAX_SAFE_ERROR_DETAIL]


class Microsoft365Client:
    def __init__(
        self,
        *,
        project_endpoint: str,
        agent_name: str,
        token_provider: activity.TokenProvider,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parse_project_endpoint(project_endpoint)
        if not agent_name.strip():
            raise PublicationError("Agent name is required.")
        base = f"{project_endpoint.rstrip('/')}/agents/{quote(agent_name, safe='')}/microsoft365"
        self._urls = {
            "zip": f"{base}/zip?api-version={activity.API_VERSION}",
            "publish": f"{base}/publish?api-version={activity.API_VERSION}",
        }
        self._token_provider = token_provider
        self._opener = opener

    def _post(self, action: str, payload: Mapping[str, Any]) -> bytes:
        if action not in self._urls:
            raise PublicationError("Unsupported Microsoft 365 operation.")
        token = self._token_provider.get_token()
        request = Request(
            self._urls[action],
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json" if action == "publish" else "application/zip",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=60) as response:
                return _read_bounded(response, MAX_PUBLICATION_RESPONSE_BYTES)
        except HTTPError as error:
            try:
                raw = _read_bounded(error, MAX_ERROR_BYTES)
            finally:
                error.close()
            if _is_version_exists_error(raw):
                raise PublicationError(
                    "Microsoft 365 rejected appVersion because that version already exists; "
                    "increment appVersion explicitly."
                ) from None
            validation_detail = _validation_error_detail(raw)
            detail_suffix = (
                f"; validation={validation_detail}"
                if error.code in {400, 422} and validation_detail
                else ""
            )
            raise PublicationError(
                f"Microsoft 365 {action} request failed with HTTP {error.code} "
                f"({activity._safe_http_reason(error.code)}){detail_suffix}."
            ) from None
        except URLError:
            raise PublicationError(
                f"Microsoft 365 {action} request failed before an HTTP response was received."
            ) from None
        except (TimeoutError, OSError):
            raise PublicationError(
                f"Microsoft 365 {action} request failed before an HTTP response was received."
            ) from None

    def package(self, payload: Mapping[str, Any]) -> bytes:
        raw = self._post("zip", payload)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as package:
                if "manifest.json" not in package.namelist():
                    raise PublicationError(
                        "Microsoft 365 package response is missing manifest.json."
                    )
        except zipfile.BadZipFile:
            raise PublicationError("Microsoft 365 package response is not a valid ZIP.") from None
        return raw

    def publish(self, payload: Mapping[str, Any]) -> str:
        raw = self._post("publish", payload)
        try:
            document = json.loads(raw)
            title_id = document["titleId"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise PublicationError("Microsoft 365 publish response is malformed.") from None
        if not isinstance(title_id, str) or not title_id.strip() or len(title_id) > 256:
            raise PublicationError("Microsoft 365 publish response has an invalid titleId.")
        return title_id


class LocalPublicationState:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.public_path = artifact_dir / "state.json"
        self.sensitive_path = artifact_dir / "sensitive-state.json"
        self.packages_dir = artifact_dir / "packages"

    def _read_json(self, path: Path, *, sensitive: bool) -> dict[str, Any]:
        if not path.exists():
            return {
                "schemaVersion": SENSITIVE_STATE_SCHEMA if sensitive else PUBLIC_STATE_SCHEMA,
                **({} if sensitive else {"records": {}}),
            }
        try:
            document = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise PublicationError("Local publication state is unreadable or malformed.") from None
        if not isinstance(document, dict):
            raise PublicationError("Local publication state is malformed.")
        return document

    def read_public(self) -> dict[str, Any]:
        document = self._read_json(self.public_path, sensitive=False)
        if set(document) != {"schemaVersion", "records"} or document["schemaVersion"] != 1:
            raise PublicationError("Sanitized local publication state has an invalid schema.")
        records = document["records"]
        if not isinstance(records, dict):
            raise PublicationError("Sanitized local publication state has invalid records.")
        for version, record in records.items():
            if SEMVER.fullmatch(version) is None or not isinstance(record, dict):
                raise PublicationError("Sanitized local publication state has an invalid record.")
            if not set(record).issubset(RECORD_KEYS):
                raise PublicationError("Sanitized local publication state has unsafe fields.")
            if SHA256.fullmatch(record.get("manifestHash", "")) is None:
                raise PublicationError("Sanitized local publication state has an invalid hash.")
            if record.get("scope") not in activity.SCOPE_AUTH_TYPES:
                raise PublicationError("Sanitized local publication state has an invalid scope.")
            for flag in ("botDeployed", "packageGenerated", "published"):
                if flag in record and not isinstance(record[flag], bool):
                    raise PublicationError(
                        "Sanitized local publication state has an invalid result flag."
                    )
            for timestamp in ("botDeployedAt", "packageGeneratedAt", "publishedAt"):
                if timestamp in record and (
                    not isinstance(record[timestamp], str)
                    or SAFE_TIMESTAMP.fullmatch(record[timestamp]) is None
                ):
                    raise PublicationError(
                        "Sanitized local publication state has an invalid timestamp."
                    )
        return document

    def read_sensitive(self) -> dict[str, Any]:
        document = self._read_json(self.sensitive_path, sensitive=True)
        if document.get("schemaVersion") != 1 or not set(document).issubset(
            {"schemaVersion", "titleId"}
        ):
            raise PublicationError("Sensitive local publication state has an invalid schema.")
        return document

    def _write_json(self, path: Path, document: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = path.with_name(path.name + ".new")
        try:
            staged.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
            staged.chmod(0o600)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)

    def write_public(self, document: Mapping[str, Any]) -> None:
        self._write_json(self.public_path, document)

    def write_sensitive(self, document: Mapping[str, Any]) -> None:
        self._write_json(self.sensitive_path, document)

    def package_path(self, manifest: PublicationManifest) -> Path:
        return self.packages_dir / f"appPackage-{manifest.app_version}.zip"

    def ensure_manifest_compatible(
        self,
        manifest: PublicationManifest,
        document: Mapping[str, Any],
    ) -> None:
        existing = document["records"].get(manifest.app_version)
        if existing is not None and (
            existing.get("manifestHash") != manifest.sha256
            or existing.get("scope") != manifest.publish_scope
        ):
            raise PublicationError(
                "appVersion is already recorded with different metadata or scope; "
                "increment appVersion explicitly."
            )

    def validate_version_for_publish(
        self,
        manifest: PublicationManifest,
        document: Mapping[str, Any],
    ) -> None:
        records = document["records"]
        self.ensure_manifest_compatible(manifest, document)
        existing = records.get(manifest.app_version)
        if existing is not None:
            if existing.get("published") is True:
                raise PublicationError(
                    "appVersion is already published locally; increment appVersion explicitly."
                )
        published_versions = [
            tuple(int(part) for part in version.split("."))
            for version, record in records.items()
            if record.get("published") is True
        ]
        if published_versions and manifest.version_tuple <= max(published_versions):
            raise PublicationError(
                "appVersion must be greater than the latest locally published version."
            )

    def update_record(
        self,
        manifest: PublicationManifest,
        *,
        flag: str,
        timestamp_field: str,
    ) -> None:
        document = self.read_public()
        record = document["records"].setdefault(
            manifest.app_version,
            {
                "manifestHash": manifest.sha256,
                "scope": manifest.publish_scope,
                "botDeployed": False,
                "packageGenerated": False,
                "published": False,
            },
        )
        if (
            record.get("manifestHash") != manifest.sha256
            or record.get("scope") != manifest.publish_scope
        ):
            raise PublicationError(
                "Local publication state conflicts with the manifest; increment appVersion."
            )
        record[flag] = True
        record[timestamp_field] = _utc_now()
        self.write_public(document)

    def verify(self, manifest: PublicationManifest) -> dict[str, Any]:
        document = self.read_public()
        record = document["records"].get(manifest.app_version)
        if not isinstance(record, dict):
            raise PublicationError("No sanitized local state exists for appVersion.")
        if (
            record.get("manifestHash") != manifest.sha256
            or record.get("scope") != manifest.publish_scope
        ):
            raise PublicationError("Manifest hash or scope does not match local state.")
        if record.get("packageGenerated") is True:
            package_path = self.package_path(manifest)
            if not package_path.is_file() or not zipfile.is_zipfile(package_path):
                raise PublicationError("Recorded Microsoft 365 package is missing or invalid.")
        return record


def build_rollback_plan() -> tuple[str, ...]:
    return (
        "Run the existing Activity reconciler rollback to remove Activity and Bot authorization.",
        "Remove the catalog entry through Microsoft 365 governance; no documented Foundry unpublish API is automated.",
        "Delete or retain Bot Service only through a reviewed ARM/Bicep lifecycle action.",
    )


def prepare_activity(
    client: activity.AgentClient,
    *,
    publish_scope: str,
    apply: bool,
) -> tuple[activity.DesiredState, activity.DesiredState | None]:
    planned = activity.reconcile(client, mode="plan", publish_scope=publish_scope)
    applied = (
        activity.reconcile(client, mode="apply", publish_scope=publish_scope) if apply else None
    )
    return planned, applied


def _resolve_common(args: argparse.Namespace) -> tuple[str, str]:
    project_endpoint = activity._resolve_input(
        args.project_endpoint,
        environment_names=(
            "FOUNDRY_PROJECT_ENDPOINT",
            "FOUNDRY_PROJECTS_ENDPOINT",
            "AZURE_AI_PROJECT_ENDPOINT",
            "AZURE_AIPROJECT_ENDPOINT",
        ),
        azd_names=(
            "FOUNDRY_PROJECT_ENDPOINT",
            "FOUNDRY_PROJECTS_ENDPOINT",
            "AZURE_AI_PROJECT_ENDPOINT",
            "AZURE_AIPROJECT_ENDPOINT",
        ),
        azd_project_dir=args.azd_project_dir,
        description="Project endpoint",
    )
    agent_name = activity._resolve_input(
        args.agent_name,
        environment_names=(
            "AGENT_ORDER_RESOLUTION_HOSTED_NAME",
            "HOSTED_AGENT_NAME",
            "FOUNDRY_HOSTED_AGENT_NAME",
        ),
        azd_names=(
            "AGENT_ORDER_RESOLUTION_HOSTED_NAME",
            "HOSTED_AGENT_NAME",
            "hostedAgentName",
        ),
        azd_project_dir=args.azd_project_dir,
        description="Agent name",
    )
    return project_endpoint, agent_name


def _agent_client(project_endpoint: str, agent_name: str) -> activity.FoundryAgentClient:
    return activity.FoundryAgentClient(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        token_provider=activity.AzureCliTokenProvider(),
    )


def _m365_client(project_endpoint: str, agent_name: str) -> Microsoft365Client:
    return Microsoft365Client(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        token_provider=activity.AzureCliTokenProvider(),
    )


def _print_activity(
    planned: activity.DesiredState,
    applied: activity.DesiredState | None,
) -> None:
    print(activity.format_result("plan", planned))
    if applied is not None:
        print(activity.format_result("apply", applied))


def _command_plan(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    coordinates = parse_project_endpoint(project_endpoint)
    state_store = LocalPublicationState(args.artifact_dir)
    public_state = state_store.read_public()
    state_store.ensure_manifest_compatible(manifest, public_state)
    if any(record.get("published") is True for record in public_state["records"].values()):
        state_store.validate_version_for_publish(manifest, public_state)
    resource_group = activity._resolve_input(
        args.resource_group,
        environment_names=("AZURE_RESOURCE_GROUP",),
        azd_names=("AZURE_RESOURCE_GROUP",),
        azd_project_dir=args.azd_project_dir,
        description="Azure resource group",
    )
    context = get_azure_context()
    require_interactive_user(context, manifest.publish_scope)
    workspace_resource_id = resolve_log_analytics_workspace_resource_id(
        resource_group=resource_group
    )
    bot_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_NAME",),
        azd_names=("BOT_SERVICE_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service name",
    )
    bot_sku_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_SKU_NAME",),
        azd_names=("BOT_SERVICE_SKU_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service SKU",
    )
    client = _agent_client(project_endpoint, agent_name)
    state = client.get_agent()
    identity_client_id = extract_agent_identity_client_id(state.document)
    desired = activity.build_desired_state(
        state.document,
        mode="plan",
        publish_scope=manifest.publish_scope,
    )
    build_bicep_command(
        resource_group=resource_group,
        template_file=args.template_file,
        coordinates=coordinates,
        agent_name=agent_name,
        agent_identity_client_id=identity_client_id,
        tenant_id=context.tenant_id,
        log_analytics_workspace_resource_id=workspace_resource_id,
        bot_name=bot_name,
        bot_sku_name=bot_sku_name,
        bot_display_name=manifest.metadata["agentDisplayName"],
    )
    print(activity.format_result("plan", desired))
    approval = (
        "; tenant admin approval remains external" if manifest.publish_scope == "Tenant" else ""
    )
    print(
        "teams-publication plan: ready; "
        f"version={manifest.app_version}; scope={manifest.publish_scope}; "
        f"manifestSha256={manifest.sha256}; botDeployment=az-deployment-group{approval}"
    )


def _command_deploy_bot(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    coordinates = parse_project_endpoint(project_endpoint)
    state_store = LocalPublicationState(args.artifact_dir)
    state_store.ensure_manifest_compatible(manifest, state_store.read_public())
    resource_group = activity._resolve_input(
        args.resource_group,
        environment_names=("AZURE_RESOURCE_GROUP",),
        azd_names=("AZURE_RESOURCE_GROUP",),
        azd_project_dir=args.azd_project_dir,
        description="Azure resource group",
    )
    context = get_azure_context()
    workspace_resource_id = resolve_log_analytics_workspace_resource_id(
        resource_group=resource_group
    )
    bot_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_NAME",),
        azd_names=("BOT_SERVICE_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service name",
    )
    bot_sku_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_SKU_NAME",),
        azd_names=("BOT_SERVICE_SKU_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service SKU",
    )
    client = _agent_client(project_endpoint, agent_name)
    state = client.get_agent()
    identity_client_id = extract_agent_identity_client_id(state.document)
    desired = activity.build_desired_state(
        state.document,
        mode="plan",
        publish_scope=manifest.publish_scope,
    )
    print(activity.format_result("plan", desired))
    command = build_bicep_command(
        resource_group=resource_group,
        template_file=args.template_file,
        coordinates=coordinates,
        agent_name=agent_name,
        agent_identity_client_id=identity_client_id,
        tenant_id=context.tenant_id,
        log_analytics_workspace_resource_id=workspace_resource_id,
        bot_name=bot_name,
        bot_sku_name=bot_sku_name,
        bot_display_name=manifest.metadata["agentDisplayName"],
    )
    deploy_bot(command)
    state_store.update_record(
        manifest,
        flag="botDeployed",
        timestamp_field="botDeployedAt",
    )
    print(
        "teams-publication deploy-bot: complete; "
        f"version={manifest.app_version}; botResourceId=validated-not-persisted"
    )


def _command_preview_bot(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    coordinates = parse_project_endpoint(project_endpoint)
    resource_group = activity._resolve_input(
        args.resource_group,
        environment_names=("AZURE_RESOURCE_GROUP",),
        azd_names=("AZURE_RESOURCE_GROUP",),
        azd_project_dir=args.azd_project_dir,
        description="Azure resource group",
    )
    context = get_azure_context()
    workspace_resource_id = resolve_log_analytics_workspace_resource_id(
        resource_group=resource_group
    )
    bot_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_NAME",),
        azd_names=("BOT_SERVICE_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service name",
    )
    bot_sku_name = activity._resolve_input(
        None,
        environment_names=("BOT_SERVICE_SKU_NAME",),
        azd_names=("BOT_SERVICE_SKU_NAME",),
        azd_project_dir=args.azd_project_dir,
        description="Bot Service SKU",
    )
    state = _agent_client(project_endpoint, agent_name).get_agent()
    identity_client_id = extract_agent_identity_client_id(state.document)
    payload = preview_bot(
        build_bicep_preview_command(
            resource_group=resource_group,
            template_file=args.template_file,
            coordinates=coordinates,
            agent_name=agent_name,
            agent_identity_client_id=identity_client_id,
            tenant_id=context.tenant_id,
            log_analytics_workspace_resource_id=workspace_resource_id,
            bot_name=bot_name,
            bot_sku_name=bot_sku_name,
            bot_display_name=manifest.metadata["agentDisplayName"],
        )
    )
    change_types = sorted(
        {
            str(change.get("changeType", "Unknown"))
            for change in payload.get("changes", [])
            if isinstance(change, dict)
        }
    )
    print(
        "teams-publication preview-bot: complete; "
        f"changeCount={len(payload.get('changes', []))}; "
        f"changeTypes={','.join(change_types) or 'None'}; mutationPerformed=false"
    )


def _command_package(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    state_store = LocalPublicationState(args.artifact_dir)
    public_state = state_store.read_public()
    existing = public_state["records"].get(manifest.app_version)
    package_path = state_store.package_path(manifest)
    state_store.ensure_manifest_compatible(manifest, public_state)
    context = get_azure_context()
    require_interactive_user(context, manifest.publish_scope)
    client = _agent_client(project_endpoint, agent_name)
    planned, applied = prepare_activity(
        client,
        publish_scope=manifest.publish_scope,
        apply=True,
    )
    _print_activity(planned, applied)
    if (
        isinstance(existing, dict)
        and existing.get("manifestHash") == manifest.sha256
        and existing.get("scope") == manifest.publish_scope
        and existing.get("packageGenerated") is True
        and package_path.is_file()
        and zipfile.is_zipfile(package_path)
    ):
        print(
            "teams-publication package: no-change; "
            f"version={manifest.app_version}; artifact={package_path.name}"
        )
        return
    resource_group = activity._resolve_input(
        args.resource_group,
        environment_names=("AZURE_RESOURCE_GROUP",),
        azd_names=("AZURE_RESOURCE_GROUP",),
        azd_project_dir=args.azd_project_dir,
        description="Azure resource group",
    )
    bot_resource_id = resolve_bot_resource_id(
        args.bot_resource_id,
        resource_group=resource_group,
    )
    raw = _m365_client(project_endpoint, agent_name).package(
        build_publish_payload(manifest, bot_resource_id)
    )
    inspect_generated_package(raw, manifest)
    package_path.parent.mkdir(parents=True, exist_ok=True)
    staged_package = package_path.with_name(package_path.name + ".new")
    try:
        staged_package.write_bytes(raw)
        staged_package.chmod(0o600)
        staged_package.replace(package_path)
    finally:
        staged_package.unlink(missing_ok=True)
    state_store.update_record(
        manifest,
        flag="packageGenerated",
        timestamp_field="packageGeneratedAt",
    )
    print(
        "teams-publication package: complete; "
        f"version={manifest.app_version}; artifact={package_path.name}"
    )


def _command_publish(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    state_store = LocalPublicationState(args.artifact_dir)
    public_state = state_store.read_public()
    state_store.validate_version_for_publish(manifest, public_state)
    context = get_azure_context()
    require_interactive_user(context, manifest.publish_scope)
    resource_group = activity._resolve_input(
        args.resource_group,
        environment_names=("AZURE_RESOURCE_GROUP",),
        azd_names=("AZURE_RESOURCE_GROUP",),
        azd_project_dir=args.azd_project_dir,
        description="Azure resource group",
    )
    bot_resource_id = resolve_bot_resource_id(
        args.bot_resource_id,
        resource_group=resource_group,
    )
    client = _agent_client(project_endpoint, agent_name)
    planned, applied = prepare_activity(
        client,
        publish_scope=manifest.publish_scope,
        apply=True,
    )
    _print_activity(planned, applied)
    title_id = _m365_client(project_endpoint, agent_name).publish(
        build_publish_payload(manifest, bot_resource_id)
    )
    sensitive = state_store.read_sensitive()
    sensitive["titleId"] = title_id
    state_store.write_sensitive(sensitive)
    state_store.update_record(
        manifest,
        flag="published",
        timestamp_field="publishedAt",
    )
    approval = (
        "; tenant admin approval remains external" if manifest.publish_scope == "Tenant" else ""
    )
    print(
        "teams-publication publish: complete; "
        f"version={manifest.app_version}; scope={manifest.publish_scope}; "
        f"titleId=stored-sensitive{approval}"
    )


def _command_verify(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    record = LocalPublicationState(args.artifact_dir).verify(manifest)
    print(
        "teams-publication verify-local-state: valid; "
        f"version={manifest.app_version}; scope={manifest.publish_scope}; "
        f"botDeployed={str(record.get('botDeployed') is True).lower()}; "
        f"packageGenerated={str(record.get('packageGenerated') is True).lower()}; "
        f"published={str(record.get('published') is True).lower()}"
    )


def _command_rollback_plan(args: argparse.Namespace, manifest: PublicationManifest) -> None:
    project_endpoint, agent_name = _resolve_common(args)
    client = _agent_client(project_endpoint, agent_name)
    current = client.get_agent()
    desired = activity.build_desired_state(
        current.document,
        mode="rollback",
        publish_scope=manifest.publish_scope,
    )
    print(activity.format_result("rollback-plan", desired))
    for index, step in enumerate(build_rollback_plan(), start=1):
        print(f"rollback-step-{index}: {step}")


def _parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Plan and execute versioned Foundry publication to Microsoft 365."
    )
    parser.add_argument(
        "mode",
        choices=(
            "plan",
            "preview-bot",
            "deploy-bot",
            "package",
            "publish",
            "verify-local-state",
            "rollback-plan",
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "infra" / "foundry-hosted" / "teams-publication.json",
    )
    parser.add_argument("--project-endpoint")
    parser.add_argument("--agent-name")
    parser.add_argument("--resource-group")
    parser.add_argument("--bot-resource-id", help=argparse.SUPPRESS)
    parser.add_argument(
        "--template-file",
        type=Path,
        default=root / "infra" / "foundry-hosted" / "iac" / "teams" / "main.bicep",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=root / ".artifacts" / "teams-publication",
    )
    parser.add_argument(
        "--azd-project-dir",
        type=Path,
        default=root / "infra" / "foundry-hosted",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.mode == "plan":
            _command_plan(args, manifest)
        elif args.mode == "preview-bot":
            _command_preview_bot(args, manifest)
        elif args.mode == "deploy-bot":
            _command_deploy_bot(args, manifest)
        elif args.mode == "package":
            _command_package(args, manifest)
        elif args.mode == "publish":
            _command_publish(args, manifest)
        elif args.mode == "verify-local-state":
            _command_verify(args, manifest)
        else:
            _command_rollback_plan(args, manifest)
    except PublicationError as error:
        print(f"teams-publication {args.mode}: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
