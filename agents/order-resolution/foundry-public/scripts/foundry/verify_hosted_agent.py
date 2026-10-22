from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def read_value(value: object, name: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def verify_version_metadata(
    version: object,
    *,
    agent_name: str,
    agent_version: str,
    expected_image: str,
    runtime_connection_name: str,
) -> dict[str, object]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", runtime_connection_name):
        raise RuntimeError("FOUNDRY_RUNTIME_CONNECTION_NAME contains invalid characters.")
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", expected_image):
        raise RuntimeError("FOUNDRY_EXPECTED_HOSTED_IMAGE must be an immutable image digest.")
    expected_database_placeholder = (
        f"${{{{connections.{runtime_connection_name}.credentials.database_url}}}}"
    )

    status = str(read_value(version, "status") or "")
    retrieved_name = str(read_value(version, "name") or "")
    retrieved_version = str(read_value(version, "version") or "")
    definition = read_value(version, "definition")
    container_configuration = read_value(definition, "container_configuration")
    image = str(read_value(container_configuration, "image") or "")
    environment_variables = read_value(definition, "environment_variables")
    if not isinstance(environment_variables, dict):
        environment_variables = {}
    protocol_versions = read_value(definition, "protocol_versions")
    responses_protocol = False
    activity_protocol = False
    if isinstance(protocol_versions, list):
        responses_protocol = any(
            str(read_value(protocol, "protocol") or "").lower() == "responses"
            and str(read_value(protocol, "version") or "") == "2.0.0"
            for protocol in protocol_versions
        )
        activity_protocol = any(
            str(read_value(protocol, "protocol") or "").lower() == "activity"
            and str(read_value(protocol, "version") or "") == "2.0.0"
            for protocol in protocol_versions
        )
    instance_identity = read_value(version, "instance_identity")
    principal_id = str(read_value(instance_identity, "principal_id") or "")

    checks = {
        "active": status.lower() == "active",
        "name_matches": not retrieved_name or retrieved_name == agent_name,
        "version_matches": not retrieved_version or retrieved_version == agent_version,
        "image_is_immutable": bool(re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)),
        "image_matches": image == expected_image,
        "responses_protocol_matches": responses_protocol,
        "activity_protocol_matches": activity_protocol,
        "database_connection_placeholder_matches": (
            environment_variables.get("DATABASE_URL") == expected_database_placeholder
        ),
        "runtime_database_connection_placeholder_matches": (
            environment_variables.get("RUNTIME_DATABASE_URL") == expected_database_placeholder
        ),
        "schema_managed_externally": (
            str(environment_variables.get("DB_SCHEMA_MANAGED_EXTERNALLY", "")).lower() == "true"
        ),
        "hosted_pool_matches": (
            environment_variables.get("DB_POOL_MIN_SIZE") == "0"
            and environment_variables.get("DB_POOL_MAX_SIZE") == "2"
            and environment_variables.get("DB_POOL_MAX_IDLE_SECONDS") == "30"
        ),
        "principal_id_present": bool(principal_id),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"Hosted-agent verification failed: {', '.join(failed)}")

    return {
        "name": agent_name,
        "version": agent_version,
        "status": status,
        "image": image,
        "principal_id": principal_id,
        "runtime_connection_name": runtime_connection_name,
        "checks": checks,
    }


def main() -> None:
    endpoint = require("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = require("FOUNDRY_HOSTED_AGENT_NAME")
    agent_version = require("FOUNDRY_HOSTED_AGENT_VERSION")
    expected_image = require("FOUNDRY_EXPECTED_HOSTED_IMAGE")
    runtime_connection_name = require("FOUNDRY_RUNTIME_CONNECTION_NAME")

    with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
        version = project.agents.get_version(
            agent_name=agent_name,
            agent_version=agent_version,
        )

    result = verify_version_metadata(
        version,
        agent_name=agent_name,
        agent_version=agent_version,
        expected_image=expected_image,
        runtime_connection_name=runtime_connection_name,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
