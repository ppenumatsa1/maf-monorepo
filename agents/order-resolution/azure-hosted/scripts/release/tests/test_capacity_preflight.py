from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from capacity_preflight import (  # noqa: E402
    CapacityPreflight,
    Config,
    ModelConfig,
    PreflightError,
)


RESOURCE_TYPES = {
    "Microsoft.App": ("managedEnvironments", "containerApps"),
    "Microsoft.CognitiveServices": ("accounts",),
    "Microsoft.ContainerRegistry": ("registries",),
    "Microsoft.DBforPostgreSQL": ("flexibleServers",),
    "Microsoft.Insights": ("components",),
    "Microsoft.ManagedIdentity": ("userAssignedIdentities",),
    "Microsoft.OperationalInsights": ("workspaces",),
}


def config() -> Config:
    return Config(
        subscription_id="11111111-1111-4111-8111-111111111111",
        region="regionone",
        postgres_sku="Standard_B1ms",
        postgres_tier="Burstable",
        models=(
            ModelConfig(
                "chat",
                "OpenAI",
                "chat-model",
                "1",
                "GlobalStandard",
                50,
                "chatCompletion",
            ),
            ModelConfig(
                "embeddings",
                "OpenAI",
                "embedding-model",
                "1",
                "GlobalStandard",
                1,
                "embeddings",
            ),
            ModelConfig(
                "evaluator",
                "OpenAI",
                "chat-model",
                "1",
                "GlobalStandard",
                50,
                "chatCompletion",
            ),
        ),
    )


def fixture() -> dict:
    return {
        "models": [
            {
                "model": {
                    "format": "OpenAI",
                    "name": "chat-model",
                    "version": "1",
                    "capabilities": {"chatCompletion": "true"},
                    "skus": [
                        {
                            "name": "GlobalStandard",
                            "usageName": "OpenAI.GlobalStandard.chat-model",
                        }
                    ],
                }
            },
            {
                "model": {
                    "format": "OpenAI",
                    "name": "embedding-model",
                    "version": "1",
                    "capabilities": {"embeddings": "true"},
                    "skus": [
                        {
                            "name": "GlobalStandard",
                            "usageName": "OpenAI.GlobalStandard.embedding-model",
                        }
                    ],
                }
            },
        ],
        "usage": [
            {
                "name": {"value": "AIServices.S0.AccountCount"},
                "currentValue": 0,
                "limit": 10,
            },
            {
                "name": {"value": "OpenAI.GlobalStandard.chat-model"},
                "currentValue": 0,
                "limit": 100,
            },
            {
                "name": {"value": "OpenAI.GlobalStandard.embedding-model"},
                "currentValue": 0,
                "limit": 10,
            },
        ],
        "postgres": [
            {
                "name": "Burstable",
                "supportedServerSkus": [{"name": "Standard_B1ms"}],
            }
        ],
        "quotas": [
            {
                "name": "ManagedEnvironmentCount",
                "properties": {"limit": {"value": 50}},
            },
            {"name": "SandboxCores", "properties": {"limit": {"value": 20}}},
        ],
        "quota_usage": [
            {
                "name": "ManagedEnvironmentCount",
                "properties": {"usages": {"value": 0}},
            },
            {"name": "SandboxCores", "properties": {"usages": {"value": 0}}},
        ],
    }


class FakeAzureClient:
    def __init__(self, data: dict) -> None:
        self.data = data

    def json(self, *args: str):
        if args[:2] == ("provider", "show"):
            namespace = args[args.index("--namespace") + 1]
            return {
                "registrationState": "Registered",
                "resourceTypes": [
                    {"resourceType": resource_type, "locations": ["Region One"]}
                    for resource_type in RESOURCE_TYPES.get(namespace, ())
                ],
            }
        if args[:3] == ("cognitiveservices", "account", "list-skus"):
            return [{"name": "S0", "restrictions": []}]
        if args[:3] == ("cognitiveservices", "model", "list"):
            return self.data["models"]
        if args[:3] == ("cognitiveservices", "usage", "list"):
            return self.data["usage"]
        if args[:3] == ("postgres", "flexible-server", "list-skus"):
            return self.data["postgres"]
        if args[:2] == ("quota", "list"):
            return self.data["quotas"]
        if args[:3] == ("quota", "usage", "list"):
            return self.data["quota_usage"]
        raise AssertionError(f"unexpected Azure command: {args}")


class CapacityPreflightTests(unittest.TestCase):
    def test_complete_single_region_topology_passes_without_mutation(self) -> None:
        result = CapacityPreflight(FakeAzureClient(fixture()), config()).run()

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["region"], "regionone")
        self.assertFalse(result["mutation_performed"])

    def test_shared_chat_quota_is_aggregated_for_chat_and_evaluator(self) -> None:
        data = fixture()
        data["usage"][1]["limit"] = 99

        with self.assertRaisesRegex(PreflightError, "aggregate Foundry model quota"):
            CapacityPreflight(FakeAzureClient(data), config()).run()

    def test_missing_model_sku_fails_closed(self) -> None:
        data = fixture()
        data["models"][0]["model"]["skus"][0]["name"] = "OtherSku"

        with self.assertRaisesRegex(PreflightError, "configured SKU"):
            CapacityPreflight(FakeAzureClient(data), config()).run()

    def test_missing_postgres_sku_fails_closed(self) -> None:
        data = fixture()
        data["postgres"] = []

        with self.assertRaisesRegex(PreflightError, "PostgreSQL SKU"):
            CapacityPreflight(FakeAzureClient(data), config()).run()

    def test_container_apps_core_capacity_fails_closed(self) -> None:
        data = fixture()
        data["quota_usage"][1]["properties"]["usages"]["value"] = 19

        with self.assertRaisesRegex(PreflightError, "SandboxCores"):
            CapacityPreflight(FakeAzureClient(data), config()).run()

    def test_unavailable_resource_type_region_fails_closed(self) -> None:
        class MissingRegionClient(FakeAzureClient):
            def json(self, *args: str):
                payload = super().json(*args)
                if args[:2] == ("provider", "show") and args[
                    args.index("--namespace") + 1
                ] == "Microsoft.App":
                    payload = deepcopy(payload)
                    payload["resourceTypes"][0]["locations"] = ["Other Region"]
                return payload

        with self.assertRaisesRegex(PreflightError, "unavailable"):
            CapacityPreflight(MissingRegionClient(fixture()), config()).run()


if __name__ == "__main__":
    unittest.main()
