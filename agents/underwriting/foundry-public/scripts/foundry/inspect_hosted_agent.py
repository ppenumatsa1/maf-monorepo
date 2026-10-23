from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    return dict(value)


def normalized(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def inspect_version(
    version: Mapping[str, Any],
    *,
    agent_name: str,
    agent_version: str,
    active_version: str,
    runtime_connection_name: str,
) -> dict[str, Any]:
    expected_database_placeholder = (
        f"${{{{connections.{runtime_connection_name}.credentials.database_url}}}}"
    )
    definition = mapping(version.get("definition") or {})
    container = mapping(
        definition.get("container_configuration") or definition.get("containerConfiguration") or {}
    )
    environment = mapping(
        definition.get("environment_variables") or definition.get("environmentVariables") or {}
    )
    identity = mapping(version.get("instance_identity") or {})
    protocols = [
        mapping(item)
        for item in (
            definition.get("protocol_versions") or definition.get("protocolVersions") or []
        )
    ]
    database_url = str(environment.get("DATABASE_URL") or "")
    runtime_database_url = str(environment.get("RUNTIME_DATABASE_URL") or "")
    image = str(container.get("image") or "")
    return {
        "name": agent_name,
        "version": str(version.get("version") or agent_version),
        "active_version": active_version,
        "is_active_version": active_version == str(version.get("version") or agent_version),
        "status": normalized(version.get("status")).casefold(),
        "image": image,
        "immutable_image_digest": bool(re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)),
        "protocols": [
            {
                "protocol": normalized(item.get("protocol")).casefold(),
                "version": normalized(item.get("version")),
            }
            for item in protocols
        ],
        "principal_id": str(identity.get("principal_id") or ""),
        "metadata": dict(mapping(version.get("metadata") or {})),
        "db_schema_managed_externally": str(
            environment.get("DB_SCHEMA_MANAGED_EXTERNALLY") or ""
        ).lower()
        == "true",
        "runtime_connection_name": runtime_connection_name,
        "database_url_placeholder": database_url == expected_database_placeholder,
        "runtime_database_url_placeholder": (runtime_database_url == expected_database_placeholder),
        "database_url_parity": database_url == runtime_database_url,
        "application_insights_managed_by_platform": not bool(
            environment.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
            or environment.get("UNDERWRITING_APPINSIGHTS_CONNECTION_STRING")
        ),
    }


def main() -> None:
    endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
    agent_name = required("HOSTED_AGENT_NAME")
    agent_version = required("HOSTED_AGENT_VERSION")
    runtime_connection_name = required("FOUNDRY_RUNTIME_CONNECTION_NAME")

    with AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    ) as project:
        version = mapping(
            project.agents.get_version(agent_name=agent_name, agent_version=agent_version)
        )
        agent = mapping(project.agents.get(agent_name=agent_name))
        versions = mapping(agent.get("versions") or {})
        latest = mapping(versions.get("latest") or {})

    print(
        json.dumps(
            inspect_version(
                version,
                agent_name=agent_name,
                agent_version=agent_version,
                active_version=str(latest.get("version") or ""),
                runtime_connection_name=runtime_connection_name,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
