#!/usr/bin/env python3
"""Reconcile the Foundry Activity endpoint without exposing deployment details."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

API_VERSION = "v1"
TOKEN_RESOURCE = "https://ai.azure.com"
BOT_AUTH_TYPES = frozenset({"BotServiceRbac", "BotServiceTenant"})
SCOPE_AUTH_TYPES = {
    "Shared": "BotServiceRbac",
    "Tenant": "BotServiceTenant",
}
MAX_RESPONSE_BYTES = 1024 * 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ReconcileError(RuntimeError):
    """Expected operator-facing reconciliation failure."""


@dataclass(frozen=True)
class AgentState:
    document: dict[str, Any]
    etag: str | None


@dataclass(frozen=True)
class DesiredState:
    patch: dict[str, Any]
    protocols: tuple[str, ...]
    authorization_schemes: tuple[str, ...]
    changed: bool


class AgentClient(Protocol):
    def get_agent(self) -> AgentState: ...

    def patch_agent(self, patch: dict[str, Any], etag: str | None) -> None: ...


class TokenProvider(Protocol):
    def get_token(self) -> str: ...


def _require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReconcileError(f"Agent state is malformed: {description} must be an object.")
    return value


def _validated_endpoint_state(
    document: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    endpoint = _require_object(document.get("agent_endpoint"), "agent_endpoint")
    protocols = _require_object(
        endpoint.get("protocol_configuration"),
        "agent_endpoint.protocol_configuration",
    )
    for name, configuration in protocols.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(configuration, dict):
            raise ReconcileError(
                "Agent state is malformed: each protocol requires a name and "
                "an object configuration."
            )
    schemes_value = endpoint.get("authorization_schemes")
    if not isinstance(schemes_value, list):
        raise ReconcileError(
            "Agent state is malformed: agent_endpoint.authorization_schemes must be an array."
        )

    schemes: list[dict[str, Any]] = []
    for scheme in schemes_value:
        scheme_object = _require_object(scheme, "each authorization scheme")
        scheme_type = scheme_object.get("type")
        if not isinstance(scheme_type, str) or not scheme_type.strip():
            raise ReconcileError(
                "Agent state is malformed: each authorization scheme requires a type."
            )
        schemes.append(scheme_object)

    responses = protocols.get("responses")
    if not isinstance(responses, dict):
        raise ReconcileError(
            "Refusing to reconcile because the Responses protocol is missing or malformed."
        )
    if not any(scheme["type"] == "Entra" for scheme in schemes):
        raise ReconcileError(
            "Refusing to reconcile because the Entra authorization scheme is missing."
        )
    return endpoint, protocols, schemes


def _state_summary(
    protocols: Mapping[str, Any], schemes: list[dict[str, Any]]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    protocol_names = tuple(sorted(_safe_name(str(name)) for name in protocols))
    scheme_names = tuple(sorted(_safe_name(str(scheme["type"])) for scheme in schemes))
    return protocol_names, scheme_names


def _safe_name(value: str) -> str:
    return value if SAFE_NAME.fullmatch(value) else "<redacted>"


def build_desired_state(
    document: dict[str, Any],
    *,
    mode: str,
    publish_scope: str,
) -> DesiredState:
    if mode not in {"plan", "apply", "rollback"}:
        raise ReconcileError("Reconciliation mode must be plan, apply, or rollback.")
    if publish_scope not in SCOPE_AUTH_TYPES:
        raise ReconcileError("Publish scope must be Shared or Tenant.")
    _, current_protocols, current_schemes = _validated_endpoint_state(document)
    protocols = {name: dict(config) for name, config in current_protocols.items()}
    schemes = [dict(scheme) for scheme in current_schemes]

    if mode == "rollback":
        protocols.pop("activity", None)
        schemes = [scheme for scheme in schemes if scheme["type"] not in BOT_AUTH_TYPES]
    else:
        target_bot_type = SCOPE_AUTH_TYPES[publish_scope]
        activity = protocols.get("activity", {})
        if not isinstance(activity, dict):
            raise ReconcileError(
                "Agent state is malformed: the Activity protocol configuration must be an object."
            )
        protocols["activity"] = {
            **activity,
            "enable_m365_public_endpoint": True,
        }

        target_scheme = next(
            (dict(scheme) for scheme in schemes if scheme["type"] == target_bot_type),
            {"type": target_bot_type},
        )
        schemes = [scheme for scheme in schemes if scheme["type"] not in BOT_AUTH_TYPES]
        schemes.append(target_scheme)

    patch = {
        "agent_endpoint": {
            "protocol_configuration": protocols,
            "authorization_schemes": schemes,
        }
    }
    current_replaced_fields = {
        "agent_endpoint": {
            "protocol_configuration": current_protocols,
            "authorization_schemes": current_schemes,
        }
    }
    protocol_names, scheme_names = _state_summary(protocols, schemes)
    return DesiredState(
        patch=patch,
        protocols=protocol_names,
        authorization_schemes=scheme_names,
        changed=patch != current_replaced_fields,
    )


class AzureCliTokenProvider:
    def get_token(self) -> str:
        if shutil.which("az") is None:
            raise ReconcileError("Azure CLI is required to acquire a Foundry token.")
        command = [
            "az",
            "account",
            "get-access-token",
            "--resource",
            TOKEN_RESOURCE,
            "--query",
            "accessToken",
            "--output",
            "tsv",
            "--only-show-errors",
        ]
        environment = os.environ.copy()
        environment["AZURE_DEV_USER_AGENT"] = "microsoft_foundry_skill"
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
        except OSError:
            raise ReconcileError("Azure CLI token acquisition could not start.") from None
        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            raise ReconcileError(
                f"Azure CLI token acquisition failed with exit code {result.returncode}."
            )
        return token


class FoundryAgentClient:
    def __init__(
        self,
        *,
        project_endpoint: str,
        agent_name: str,
        token_provider: TokenProvider,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        parsed = urlsplit(project_endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ReconcileError("Project endpoint must be an absolute HTTPS URL.")
        if not agent_name.strip():
            raise ReconcileError("Agent name is required.")
        self._url = (
            f"{project_endpoint.rstrip('/')}/agents/{quote(agent_name, safe='')}"
            f"?api-version={API_VERSION}"
        )
        self._token_provider = token_provider
        self._opener = opener

    def _request(
        self,
        method: str,
        *,
        body: dict[str, Any] | None = None,
        etag: str | None = None,
    ) -> tuple[dict[str, Any] | None, Mapping[str, str]]:
        token = self._token_provider.get_token()
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/merge-patch+json"
        if etag:
            headers["If-Match"] = etag
        request = Request(self._url, data=data, headers=headers, method=method)

        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ReconcileError("Foundry response exceeded the safe size limit.")
                response_headers = response.headers
        except HTTPError as error:
            status = error.code
            reason = _safe_http_reason(status)
            error.close()
            if status == 412:
                raise ReconcileError(
                    "Foundry PATCH failed with HTTP 412 (precondition failed); "
                    "the agent changed after it was read."
                ) from None
            raise ReconcileError(f"Foundry request failed with HTTP {status} ({reason}).") from None
        except URLError:
            raise ReconcileError(
                "Foundry request failed before an HTTP response was received."
            ) from None
        except (TimeoutError, OSError):
            raise ReconcileError(
                "Foundry request failed before an HTTP response was received."
            ) from None

        if not raw:
            return None, response_headers
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ReconcileError("Foundry returned a non-JSON response.") from None
        if not isinstance(document, dict):
            raise ReconcileError("Foundry returned a malformed JSON response.")
        return document, response_headers

    def get_agent(self) -> AgentState:
        document, headers = self._request("GET")
        if document is None:
            raise ReconcileError("Foundry GET returned an empty response.")
        etag = headers.get("ETag") or headers.get("etag")
        return AgentState(document=document, etag=etag)

    def patch_agent(self, patch: dict[str, Any], etag: str | None) -> None:
        self._request("PATCH", body=patch, etag=etag)


def _safe_http_reason(status: int) -> str:
    try:
        return HTTPStatus(status).phrase.casefold()
    except ValueError:
        return "request failed"


def reconcile(
    client: AgentClient,
    *,
    mode: str,
    publish_scope: str,
) -> DesiredState:
    current = client.get_agent()
    desired = build_desired_state(
        current.document,
        mode=mode,
        publish_scope=publish_scope,
    )
    if mode != "plan" and desired.changed:
        client.patch_agent(desired.patch, current.etag)
    return desired


def format_result(mode: str, desired: DesiredState) -> str:
    status = "changed" if desired.changed else "no-change"
    return (
        f"activity-endpoint {mode}: {status}; "
        f"protocols={','.join(desired.protocols)}; "
        f"authorization={','.join(desired.authorization_schemes)}"
    )


def _azd_value(key: str, project_dir: Path) -> str | None:
    if shutil.which("azd") is None or not project_dir.is_dir():
        return None
    environment = os.environ.copy()
    environment["AZURE_DEV_USER_AGENT"] = "microsoft_foundry_skill"
    result = subprocess.run(
        ["azd", "env", "get-value", key],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _resolve_input(
    explicit: str | None,
    *,
    environment_names: tuple[str, ...],
    azd_names: tuple[str, ...],
    azd_project_dir: Path,
    description: str,
) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for name in environment_names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    for name in azd_names:
        value = _azd_value(name, azd_project_dir)
        if value:
            return value
    raise ReconcileError(
        f"{description} is required through an explicit argument, environment, "
        "or the selected AZD environment."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, apply, or roll back Foundry Activity endpoint state."
    )
    parser.add_argument("mode", choices=("plan", "apply", "rollback"))
    parser.add_argument("--project-endpoint")
    parser.add_argument("--agent-name")
    parser.add_argument(
        "--publish-scope",
        choices=tuple(SCOPE_AUTH_TYPES),
        default=os.getenv("TEAMS_PUBLISH_SCOPE", "Shared"),
    )
    parser.add_argument(
        "--azd-project-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "infra" / "foundry-hosted",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_endpoint = _resolve_input(
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
        agent_name = _resolve_input(
            args.agent_name,
            environment_names=(
                "HOSTED_AGENT_NAME",
                "FOUNDRY_HOSTED_AGENT_NAME",
                "AGENT_ORDER_RESOLUTION_HOSTED_NAME",
            ),
            azd_names=(
                "HOSTED_AGENT_NAME",
                "hostedAgentName",
                "AGENT_ORDER_RESOLUTION_HOSTED_NAME",
            ),
            azd_project_dir=args.azd_project_dir,
            description="Agent name",
        )
        client = FoundryAgentClient(
            project_endpoint=project_endpoint,
            agent_name=agent_name,
            token_provider=AzureCliTokenProvider(),
        )
        desired = reconcile(
            client,
            mode=args.mode,
            publish_scope=args.publish_scope,
        )
    except ReconcileError as error:
        print(f"activity-endpoint {args.mode}: error: {error}", file=sys.stderr)
        return 1

    print(format_result(args.mode, desired))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
