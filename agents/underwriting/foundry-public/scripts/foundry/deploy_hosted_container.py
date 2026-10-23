from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import Mapping
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointProtocol,
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential

IMMUTABLE_IMAGE_PATTERN = re.compile(r"^.+@sha256:[0-9a-f]{64}$")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def normalized_status(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").casefold()


def runtime_connection_placeholder(runtime_connection_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", runtime_connection_name):
        raise RuntimeError("FOUNDRY_RUNTIME_CONNECTION_NAME contains invalid characters.")
    return f"${{{{connections.{runtime_connection_name}.credentials.database_url}}}}"


def build_hosted_agent_definition() -> HostedAgentDefinition:
    image = required("HOSTED_AGENT_IMAGE")
    if not IMMUTABLE_IMAGE_PATTERN.fullmatch(image):
        raise RuntimeError("HOSTED_AGENT_IMAGE must use an immutable sha256 digest.")
    placeholder = runtime_connection_placeholder(required("FOUNDRY_RUNTIME_CONNECTION_NAME"))
    return HostedAgentDefinition(
        cpu="0.5",
        memory="1Gi",
        container_configuration=ContainerConfiguration(image=image),
        environment_variables={
            "APP_ENV": "production",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
            "DATABASE_URL": placeholder,
            "RUNTIME_DATABASE_URL": placeholder,
            "DB_AUTH_MODE": "password",
            "DB_SCHEMA_MANAGED_EXTERNALLY": required("DB_SCHEMA_MANAGED_EXTERNALLY"),
            "UNDERWRITING_MODEL_DEPLOYMENT_NAME": required("UNDERWRITING_MODEL_DEPLOYMENT_NAME"),
            "AZURE_OPENAI_ENDPOINT": required("AZURE_OPENAI_ENDPOINT"),
            "ENABLE_INSTRUMENTATION": "true",
            "ENABLE_TELEMETRY": "true",
            "OTEL_SERVICE_NAME": "underwriting-hosted",
        },
        protocol_versions=[
            ProtocolVersionRecord(
                protocol=AgentEndpointProtocol.RESPONSES,
                version="2.0.0",
            ),
            ProtocolVersionRecord(
                protocol=AgentEndpointProtocol.ACTIVITY,
                version="2.0.0",
            ),
        ],
    )


def active_version_metadata(project: AIProjectClient, agent_name: str) -> Mapping[str, Any]:
    agent = as_mapping(project.agents.get(agent_name=agent_name))
    versions = as_mapping(agent.get("versions") or {})
    latest = as_mapping(versions.get("latest") or {})
    if not latest:
        raise RuntimeError("Hosted agent active metadata did not include versions.latest.")
    return latest


def main() -> None:
    endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
    agent_name = required("HOSTED_AGENT_NAME")
    image = required("HOSTED_AGENT_IMAGE")
    release_id = os.getenv("RELEASE_ID", "").strip()
    metadata = {"image_digest": image.rsplit("@", 1)[-1]}
    if release_id:
        metadata["release_id"] = release_id

    with AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    ) as project:
        created = project.agents.create_version(
            agent_name=agent_name,
            description="Underwriting MAF hosted workflow agent.",
            definition=build_hosted_agent_definition(),
            metadata=metadata,
        )
        print(f"Created {agent_name} version {created.version} from {image}.")

        for attempt in range(60):
            version = as_mapping(
                project.agents.get_version(
                    agent_name=agent_name,
                    agent_version=created.version,
                )
            )
            status = normalized_status(version.get("status"))
            print(f"{attempt + 1}/60: {status}")
            if status == "active":
                latest = active_version_metadata(project, agent_name)
                if str(latest.get("version") or "") != str(created.version):
                    raise RuntimeError(
                        "Hosted agent active metadata does not reference the newly active version."
                    )
                identity = as_mapping(version.get("instance_identity") or {})
                principal_id = str(identity.get("principal_id") or "")
                print(f"Hosted agent {agent_name} version {created.version} is active.")
                print(f"HOSTED_AGENT_VERSION={created.version}")
                print(f"HOSTED_AGENT_IMAGE={image}")
                if principal_id:
                    print(f"HOSTED_AGENT_PRINCIPAL_ID={principal_id}")
                return
            if status == "failed":
                raise RuntimeError(dict(version))
            time.sleep(10)

    raise TimeoutError("Hosted agent did not become active.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise
