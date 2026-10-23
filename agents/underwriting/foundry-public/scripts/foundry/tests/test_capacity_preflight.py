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
    "Microsoft.Storage": ("storageAccounts",),
}


def config(mode: str = "app_only") -> Config:
    return Config(
        mode=mode,
        subscription_id="11111111-1111-4111-8111-111111111111",
        resource_group="rg-portable",
        target_region="eastus2",
        foundry_region="eastus2",
        foundry_account="portable-foundry",
        foundry_project="portable-project",
        postgres_name="portable-postgres",
        postgres_region="eastus2",
        postgres_sku="Standard_D2s_v5",
        postgres_tier="GeneralPurpose",
        postgres_version="17",
        container_environment="portable-cae",
        backend_app="portable-backend",
        frontend_app="portable-frontend",
        registry_name="portableacr",
        registry_sku="Basic",
        application_insights_name="portable-ai",
        log_analytics_name="portable-log",
        bot_name="portable-bot",
        bot_sku="F0",
        models=(
            ModelConfig(
                "chat",
                "portable-chat",
                "OpenAI",
                "chat-model",
                "1",
                "GlobalStandard",
                25,
                "chatCompletion",
            ),
        ),
    )


def healthy_fixture() -> dict:
    cfg = config()
    return {
        "accounts": [
            {
                "name": cfg.foundry_account,
                "kind": "AIServices",
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "projects": [
            {
                "name": f"{cfg.foundry_account}/{cfg.foundry_project}",
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "deployments": [
            {
                "name": model.deployment_name,
                "properties": {
                    "model": {
                        "format": model.model_format,
                        "name": model.model_name,
                        "version": model.model_version,
                    },
                    "provisioningState": "Succeeded",
                },
                "sku": {"name": model.sku_name, "capacity": model.capacity},
            }
            for model in cfg.models
        ],
        "models": [
            {
                "model": {
                    "format": model.model_format,
                    "name": model.model_name,
                    "version": model.model_version,
                    "capabilities": {model.capability: "true"},
                    "skus": [
                        {
                            "name": model.sku_name,
                            "usageName": f"{model.label}.quota",
                        }
                    ],
                }
            }
            for model in cfg.models
        ],
        "usage": [
            {"name": {"value": "OpenAI.S0.AccountCount"}, "currentValue": 1, "limit": 1},
            *[
                {
                    "name": {"value": f"{model.label}.quota"},
                    "currentValue": model.capacity,
                    "limit": model.capacity,
                }
                for model in cfg.models
            ],
        ],
        "components": [
            {
                "name": cfg.application_insights_name,
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "workspaces": [
            {
                "name": cfg.log_analytics_name,
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "postgres": [
            {
                "name": cfg.postgres_name,
                "location": "East US 2",
                "version": cfg.postgres_version,
                "state": "Ready",
                "sku": {"name": cfg.postgres_sku, "tier": cfg.postgres_tier},
            }
        ],
        "postgres_skus": [{"name": cfg.postgres_sku, "tier": cfg.postgres_tier}],
        "environments": [
            {
                "name": cfg.container_environment,
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "apps": [
            {
                "name": cfg.backend_app,
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            },
            {
                "name": cfg.frontend_app,
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            },
        ],
        "registries": [
            {
                "name": cfg.registry_name,
                "location": "East US 2",
                "sku": {"name": cfg.registry_sku},
                "provisioningState": "Succeeded",
            }
        ],
        "bots": [
            {
                "name": cfg.bot_name,
                "kind": "azurebot",
                "sku": {"name": cfg.bot_sku},
                "properties": {"provisioningState": "Succeeded"},
            }
        ],
        "channels": [{"name": f"{cfg.bot_name}/MsTeamsChannel"}],
        "container_quotas": [],
        "container_usage": [],
    }


class FakeAzureClient:
    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture
        self.calls: list[tuple[str, ...]] = []

    def json(self, *args: str):
        self.calls.append(args)
        if args[:2] == ("provider", "show"):
            namespace = args[args.index("--namespace") + 1]
            return {
                "registrationState": "Registered",
                "resourceTypes": [
                    {"resourceType": resource_type, "locations": ["East US 2"]}
                    for resource_type in RESOURCE_TYPES.get(namespace, ())
                ],
            }
        if args[:3] == ("cognitiveservices", "account", "list"):
            return self.fixture["accounts"]
        if args[:4] == ("cognitiveservices", "account", "project", "list"):
            return self.fixture["projects"]
        if args[:4] == ("cognitiveservices", "account", "deployment", "list"):
            return self.fixture["deployments"]
        if args[:3] == ("cognitiveservices", "model", "list"):
            return self.fixture["models"]
        if args[:3] == ("cognitiveservices", "usage", "list"):
            return self.fixture["usage"]
        if args[:3] == ("postgres", "flexible-server", "list"):
            return self.fixture["postgres"]
        if args[:3] == ("postgres", "flexible-server", "list-skus"):
            return self.fixture["postgres_skus"]
        if args[:3] == ("containerapp", "env", "list"):
            return self.fixture["environments"]
        if args[:2] == ("containerapp", "list"):
            return self.fixture["apps"]
        if args[:2] == ("acr", "list"):
            return self.fixture["registries"]
        if args[:2] == ("quota", "list"):
            return self.fixture["container_quotas"]
        if args[:3] == ("quota", "usage", "list"):
            return self.fixture["container_usage"]
        if args[:1] == ("rest",):
            url = args[args.index("--url") + 1]
            if "Microsoft.Insights/components" in url:
                return {"value": self.fixture["components"]}
            if "Microsoft.OperationalInsights/workspaces" in url:
                return {"value": self.fixture["workspaces"]}
            if "Microsoft.BotService/botServices/" in url and "/channels?" in url:
                return {"value": self.fixture["channels"]}
            if "Microsoft.BotService/botServices?" in url:
                return {"value": self.fixture["bots"]}
        raise AssertionError(f"unexpected Azure command: {args}")


class CapacityPreflightTests(unittest.TestCase):
    def test_unchanged_healthy_resources_need_zero_incremental_quota(self) -> None:
        client = FakeAzureClient(healthy_fixture())

        result = CapacityPreflight(client, config()).run()

        self.assertTrue(all(value == 0 for value in result["incremental"].values()))
        self.assertFalse(result["mutation_performed"])
        self.assertFalse(
            any(
                call[:3]
                in {
                    ("cognitiveservices", "usage", "list"),
                }
                or call[:2] == ("quota", "list")
                for call in client.calls
            )
        )
        self.assertTrue(any("zero additional quota" in item for item in result["messages"]))

    def test_app_only_rejects_any_resource_growth_before_mutation(self) -> None:
        fixture = healthy_fixture()
        fixture["apps"] = fixture["apps"][:1]

        with self.assertRaisesRegex(
            PreflightError, "app_only requires an unchanged healthy existing"
        ):
            CapacityPreflight(FakeAzureClient(fixture), config()).run()

    def test_app_only_does_not_require_post_release_teams_resources(self) -> None:
        fixture = healthy_fixture()
        fixture["bots"] = []
        fixture["channels"] = []

        result = CapacityPreflight(FakeAzureClient(fixture), config()).run()

        self.assertEqual(result["incremental"]["bot_services"], 0)
        self.assertEqual(result["incremental"]["teams_channels"], 0)

    def test_full_infra_checks_only_incremental_model_growth(self) -> None:
        fixture = healthy_fixture()
        fixture["deployments"][0]["sku"]["capacity"] = 20
        fixture["usage"][1]["currentValue"] = 95
        fixture["usage"][1]["limit"] = 100

        result = CapacityPreflight(FakeAzureClient(fixture), config("full_infra")).run()

        self.assertEqual(result["incremental"]["model_capacity"], 5)
        self.assertEqual(
            sum(result["incremental"].values()),
            5,
        )

    def test_full_infra_fails_when_incremental_model_quota_is_insufficient(self) -> None:
        fixture = healthy_fixture()
        fixture["deployments"][0]["sku"]["capacity"] = 20
        fixture["usage"][1]["currentValue"] = 98
        fixture["usage"][1]["limit"] = 100

        with self.assertRaisesRegex(PreflightError, "5 incremental capacity is required"):
            CapacityPreflight(FakeAzureClient(fixture), config("full_infra")).run()

    def test_full_infra_checks_environment_quota_only_when_environment_is_missing(
        self,
    ) -> None:
        fixture = healthy_fixture()
        fixture["environments"] = []
        fixture["container_quotas"] = [
            {
                "name": {"value": "ManagedEnvironmentCount"},
                "properties": {"limit": {"value": 2}},
            }
        ]
        fixture["container_usage"] = [
            {
                "name": {"value": "ManagedEnvironmentCount"},
                "properties": {"usages": {"value": 1}},
            }
        ]

        result = CapacityPreflight(FakeAzureClient(fixture), config("full_infra")).run()

        self.assertEqual(result["incremental"]["container_apps_environments"], 1)

    def test_full_infra_counts_only_missing_monitoring_resources(self) -> None:
        fixture = healthy_fixture()
        fixture["components"] = []

        result = CapacityPreflight(FakeAzureClient(fixture), config("full_infra")).run()

        self.assertEqual(result["incremental"]["application_insights"], 1)
        self.assertEqual(result["incremental"]["log_analytics_workspaces"], 0)

    def test_preflight_rejects_multi_region_or_non_north_america_targets(self) -> None:
        base = config()
        multi_region = Config(**{**base.__dict__, "postgres_region": "westus2"})
        outside_region = Config(
            **{
                **base.__dict__,
                "target_region": "westeurope",
                "foundry_region": "westeurope",
                "postgres_region": "westeurope",
            }
        )

        for candidate in (multi_region, outside_region):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(
                    PreflightError, "one North America region"
                ):
                    CapacityPreflight(FakeAzureClient(healthy_fixture()), candidate).run()

    def test_full_infra_accepts_current_postgres_capability_shape(self) -> None:
        fixture = healthy_fixture()
        fixture["postgres"] = []
        fixture["postgres_skus"] = [
            {
                "name": "FlexibleServerCapabilities",
                "supportedServerEditions": [
                    {
                        "name": config().postgres_tier,
                        "supportedServerSkus": [
                            {"name": config().postgres_sku},
                        ],
                    }
                ],
            }
        ]

        result = CapacityPreflight(FakeAzureClient(fixture), config("full_infra")).run()

        self.assertEqual(result["incremental"]["postgres_servers"], 1)

    def test_model_replacement_requires_full_requested_capacity(self) -> None:
        fixture = healthy_fixture()
        fixture["deployments"][0]["properties"]["model"]["version"] = "other"
        fixture["usage"][1]["currentValue"] = 0
        fixture["usage"][1]["limit"] = 25

        result = CapacityPreflight(FakeAzureClient(deepcopy(fixture)), config("full_infra")).run()

        self.assertEqual(result["incremental"]["model_capacity"], 25)


if __name__ == "__main__":
    unittest.main()
