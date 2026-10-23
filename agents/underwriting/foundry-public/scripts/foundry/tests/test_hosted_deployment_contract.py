from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "foundry"
sys.path.insert(0, str(SCRIPTS))

import deploy_hosted_container  # noqa: E402
import inspect_hosted_agent  # noqa: E402

DIGEST_IMAGE = "example.azurecr.io/portable-hosted@sha256:" + "a" * 64


def _hosted_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "HOSTED_AGENT_IMAGE": DIGEST_IMAGE,
        "FOUNDRY_RUNTIME_CONNECTION_NAME": "underwritingruntimesecrets",
        "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
        "UNDERWRITING_MODEL_DEPLOYMENT_NAME": "underwriting-gpt-4-1-mini",
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        "UNDERWRITING_APPINSIGHTS_CONNECTION_STRING": "configured",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_hosted_definition_uses_current_sdk_shape_and_immutable_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _hosted_environment(monkeypatch)

    definition = deploy_hosted_container.build_hosted_agent_definition()
    payload = definition.as_dict()
    placeholder = "${{connections.underwritingruntimesecrets.credentials.database_url}}"

    assert payload["container_configuration"]["image"] == DIGEST_IMAGE
    assert payload["environment_variables"]["DATABASE_URL"] == placeholder
    assert payload["environment_variables"]["RUNTIME_DATABASE_URL"] == placeholder
    assert payload["protocol_versions"] == [
        {"protocol": "responses", "version": "2.0.0"},
        {"protocol": "activity", "version": "2.0.0"},
    ]
    assert "postgresql" not in json.dumps(payload)


def test_hosted_definition_rejects_mutable_image(monkeypatch: pytest.MonkeyPatch) -> None:
    _hosted_environment(monkeypatch)
    monkeypatch.setenv("HOSTED_AGENT_IMAGE", "example.azurecr.io/underwriting-hosted:latest")

    with pytest.raises(RuntimeError, match="immutable sha256 digest"):
        deploy_hosted_container.build_hosted_agent_definition()


def test_inspection_requires_active_exact_metadata() -> None:
    placeholder = "${{connections.underwritingruntimesecrets.credentials.database_url}}"
    result = inspect_hosted_agent.inspect_version(
        {
            "version": "42",
            "status": "active",
            "metadata": {"release_id": "release-42"},
            "instance_identity": {"principal_id": "principal-42"},
            "definition": {
                "container_configuration": {"image": DIGEST_IMAGE},
                "protocol_versions": [
                    {"protocol": "responses", "version": "2.0.0"},
                    {"protocol": "activity", "version": "2.0.0"},
                ],
                "environment_variables": {
                    "DATABASE_URL": placeholder,
                    "RUNTIME_DATABASE_URL": placeholder,
                    "DB_SCHEMA_MANAGED_EXTERNALLY": "true",
                    "UNDERWRITING_APPINSIGHTS_CONNECTION_STRING": "configured",
                },
            },
        },
        agent_name="underwriting-hosted",
        agent_version="42",
        active_version="42",
        runtime_connection_name="underwritingruntimesecrets",
    )

    assert result["is_active_version"]
    assert result["immutable_image_digest"]
    assert result["principal_id"] == "principal-42"
    assert result["protocols"] == [
        {"protocol": "responses", "version": "2.0.0"},
        {"protocol": "activity", "version": "2.0.0"},
    ]


def test_release_scripts_persist_only_placeholder_metadata() -> None:
    deploy_python = (ROOT / "scripts/foundry/deploy_hosted_container.py").read_text()
    deploy_shell = (ROOT / "scripts/foundry/deploy_hosted_container.sh").read_text()

    assert "credentials.database_url" in deploy_python
    assert "--arg runtime_database_url" not in deploy_shell
    assert "AGENT_UNDERWRITING_HOSTED_IMAGE" in deploy_shell
    assert "AGENT_UNDERWRITING_HOSTED_IMAGE_REPOSITORY" in deploy_shell
    assert 'image_repository="$(required_env HOSTED_AGENT_IMAGE_REPOSITORY)"' in deploy_shell
    assert 'image_repository="underwriting-hosted"' not in deploy_shell
    assert "HOSTED_AGENT_DEPLOYMENT_METADATA_FILE" in deploy_shell
