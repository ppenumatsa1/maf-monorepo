from __future__ import annotations

import os
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


endpoint = require("FOUNDRY_PROJECT_ENDPOINT")
agent_name = require("FOUNDRY_HOSTED_AGENT_NAME")
image = require("FOUNDRY_IMAGE")
runtime_database_url = require("RUNTIME_DATABASE_URL")

environment_variables = {
    "FOUNDRY_PROJECTS_ENDPOINT": endpoint,
    "FOUNDRY_MODEL_DEPLOYMENT_NAME": require("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
    "DATABASE_URL": runtime_database_url,
    "FOUNDRY_RUNTIME_DATABASE_URL": runtime_database_url,
    "RUNTIME_DATABASE_URL": runtime_database_url,
    "APP_ENV": require("APP_ENV"),
    "STORE_PROVIDER": require("STORE_PROVIDER"),
    "MEMORY_PROVIDER": require("MEMORY_PROVIDER"),
    "RAG_PROVIDER": require("RAG_PROVIDER"),
    "ENABLE_TELEMETRY": require("ENABLE_TELEMETRY"),
    "ENABLE_INSTRUMENTATION": require("ENABLE_INSTRUMENTATION"),
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
    "OTEL_SERVICE_NAME": require("OTEL_SERVICE_NAME"),
    "OTEL_SERVICE_NAMESPACE": require("OTEL_SERVICE_NAMESPACE"),
    "OTEL_RECORD_CONTENT": require("OTEL_RECORD_CONTENT"),
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", ""
    ),
    "FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT": require(
        "FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT"
    ),
}

with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential()) as project:
    created = project.agents.create_version(
        agent_name=agent_name,
        description="Order Resolution private hosted workflow agent.",
        definition=HostedAgentDefinition(
            cpu="0.5",
            memory="1Gi",
            container_configuration=ContainerConfiguration(image=image),
            environment_variables=environment_variables,
            protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
        ),
    )
    print(f"Created {agent_name} version {created.version} from {image}.")

    for attempt in range(60):
        version = project.agents.get_version(
            agent_name=agent_name, agent_version=created.version
        )
        status = version["status"]
        print(f"{attempt + 1}/60: {status}")
        if status == "active":
            print(f"Hosted agent {agent_name} version {created.version} is active.")
            print(f"HOSTED_AGENT_VERSION={created.version}")
            sys.exit(0)
        if status == "failed":
            raise RuntimeError(dict(version))
        time.sleep(10)

raise TimeoutError("Hosted agent did not become active.")
