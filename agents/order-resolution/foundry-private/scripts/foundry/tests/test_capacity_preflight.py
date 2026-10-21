import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from capacity_preflight import (  # noqa: E402
    REQUIRED_PROVIDERS,
    CapacityPreflight,
    Config,
    ModelConfig,
    PreflightError,
)

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "capacity_preflight_success.json"
)

RESOURCE_TYPES = {
    "Microsoft.App": [("managedEnvironments", "target")],
    "Microsoft.Compute": [("virtualMachines", "target")],
    "Microsoft.ContainerRegistry": [("registries", "target")],
    "Microsoft.Insights": [("components", "target")],
    "Microsoft.ManagedIdentity": [("userAssignedIdentities", "target")],
    "Microsoft.Network": [("virtualNetworks", "target")],
    "Microsoft.OperationalInsights": [("workspaces", "target")],
    "Microsoft.Storage": [("storageAccounts", "target")],
    "Microsoft.CognitiveServices": [("accounts", "foundry")],
    "Microsoft.DocumentDB": [("databaseAccounts", "cosmos")],
    "Microsoft.Search": [("searchServices", "search")],
    "Microsoft.DBforPostgreSQL": [("flexibleServers", "postgres")],
}


class FixtureAzureClient:
    def __init__(self, fixture: dict) -> None:
        self.fixture = fixture
        self.calls: list[tuple[str, ...]] = []
        self.provider_states = {
            namespace: "Registered" for namespace in REQUIRED_PROVIDERS
        }

    def json(self, *args: str):
        self.calls.append(args)
        if args[:2] == ("provider", "show"):
            namespace = args[args.index("--namespace") + 1]
            locations = self.fixture["locations"]
            return {
                "registrationState": self.provider_states[namespace],
                "resourceTypes": [
                    {
                        "resourceType": resource_type,
                        "locations": [locations[location_key]],
                    }
                    for resource_type, location_key in RESOURCE_TYPES.get(
                        namespace, []
                    )
                ],
            }
        if args[:3] == ("cognitiveservices", "account", "list-skus"):
            return self.fixture["cognitive_skus"]
        if args[:3] == ("cognitiveservices", "account", "list"):
            return self.fixture.get("cognitive_accounts", [])
        if args[:4] == (
            "cognitiveservices",
            "account",
            "deployment",
            "list",
        ):
            return self.fixture.get("cognitive_deployments", [])
        if args[:3] == ("search", "service", "list"):
            return self.fixture.get("search_services", [])
        if args[:3] == ("containerapp", "env", "list"):
            return self.fixture.get("container_environments", [])
        if args[:2] == ("vm", "list"):
            return self.fixture.get("virtual_machines", [])
        if args[:3] == ("postgres", "flexible-server", "list-skus"):
            return self.fixture["postgres_skus"]
        if args[:2] == ("vm", "list-usage"):
            return self.fixture["compute_usage"]
        if args[:2] == ("quota", "list"):
            return self.fixture["container_quotas"]
        if args[:3] == ("quota", "usage", "list"):
            return self.fixture["container_usage"]
        if args[:3] == ("cognitiveservices", "usage", "list"):
            return self.fixture["cognitive_usage"]
        if args[:3] == ("cognitiveservices", "model", "list"):
            return self.fixture["models"]
        if args[:2] == ("rest", "--method"):
            url = args[args.index("--url") + 1]
            parsed = urlsplit(url)
            if parsed.path.endswith("/providers/Microsoft.Compute/skus"):
                return {"value": self.fixture["vm_skus"]}
            if "/providers/Microsoft.Search/locations/" in parsed.path:
                return self.fixture["search_usage"]
            if parsed.path.endswith("/modelCapacities"):
                model_name = parse_qs(parsed.query)["modelName"][0]
                return self.fixture["model_capacities"][model_name]
        raise AssertionError(f"unexpected Azure command: {args}")


def config() -> Config:
    return Config(
        subscription_id="00000000-0000-0000-0000-000000000000",
        resource_group="rg-test",
        target_region="eastus2",
        foundry_region="eastus2",
        search_region="eastus",
        cosmos_region="eastus2",
        postgres_region="eastus2",
        runner_vm_size="Standard_D4s_v7",
        create_runner_vm=True,
        enable_container_apps=True,
        search_sku="basic",
        postgres_sku="Standard_B1ms",
        postgres_tier="Burstable",
        postgres_version="18",
        chat=ModelConfig(
            "chat",
            "gpt-4o",
            "OpenAI",
            "gpt-4o",
            "2024-11-20",
            "GlobalStandard",
            30,
            "chatCompletion",
        ),
        embeddings=ModelConfig(
            "embeddings",
            "text-embedding-3-small",
            "OpenAI",
            "text-embedding-3-small",
            "1",
            "GlobalStandard",
            1,
            "embeddings",
        ),
    )


class CapacityPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text())
        self.client = FixtureAzureClient(self.fixture)

    def test_success_fixture_validates_exact_configuration(self) -> None:
        CapacityPreflight(self.client, config()).run()
        mutating_words = {"create", "delete", "register", "set", "update"}
        for call in self.client.calls:
            self.assertFalse(mutating_words.intersection(call), call)
            if call[0] == "rest":
                self.assertEqual(call[call.index("--method") + 1], "get")

    def test_unregistered_required_provider_fails_actionably(self) -> None:
        for namespace in ("Microsoft.ContainerService", "Microsoft.BotService"):
            with self.subTest(namespace=namespace):
                client = FixtureAzureClient(self.fixture)
                client.provider_states[namespace] = "NotRegistered"
                with self.assertRaisesRegex(
                    PreflightError,
                    rf"{re.escape(namespace)} \(NotRegistered\)",
                ):
                    CapacityPreflight(client, config()).run()

    def test_restricted_exact_runner_sku_does_not_fallback(self) -> None:
        self.fixture["vm_skus"][0]["restrictions"] = [
            {
                "type": "Location",
                "reasonCode": "NotAvailableForSubscription",
                "restrictionInfo": {"locations": ["eastus2"]},
            }
        ]
        with self.assertRaisesRegex(
            PreflightError, r"Standard_D4s_v7 is restricted in eastus2"
        ):
            CapacityPreflight(self.client, config()).run()

    def test_container_apps_managed_environment_quota_is_required(self) -> None:
        self.fixture["container_quotas"][0]["properties"]["limit"]["value"] = 1
        with self.assertRaisesRegex(
            PreflightError, r"Container Apps managed environments quota has 0 available"
        ):
            CapacityPreflight(self.client, config()).run()

    def test_configured_model_quota_must_cover_requested_capacity(self) -> None:
        self.fixture["cognitive_usage"][1]["limit"] = 20
        with self.assertRaisesRegex(
            PreflightError, r"chat model quota .* 30 is required"
        ):
            CapacityPreflight(self.client, config()).run()

    def test_missing_model_version_fails_without_success_fallback(self) -> None:
        self.fixture["models"][0]["model"]["version"] = "different"
        with self.assertRaisesRegex(
            PreflightError, r"gpt-4o/2024-11-20 is unavailable in eastus2"
        ):
            CapacityPreflight(self.client, config()).run()

    def test_existing_search_service_handles_empty_usage_metadata(self) -> None:
        self.fixture["search_usage"] = {"value": []}
        self.fixture["search_services"] = [
            {
                "location": "East US",
                "sku": {"name": "basic"},
                "status": "running",
            }
        ]

        preflight = CapacityPreflight(self.client, config())
        preflight.run()

        self.assertTrue(
            any("existing healthy AI Search service" in warning for warning in preflight.warnings)
        )

    def test_existing_container_environment_handles_empty_quota_metadata(self) -> None:
        self.fixture["container_quotas"] = []
        self.fixture["container_usage"] = []
        self.fixture["container_environments"] = [
            {
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ]

        preflight = CapacityPreflight(self.client, config())
        preflight.run()

        self.assertTrue(
            any(
                "existing healthy managed environment" in warning
                or "existing healthy Container Apps managed environment" in warning
                for warning in preflight.warnings
            )
        )

    def test_existing_model_deployments_handle_empty_ai_quota_metadata(self) -> None:
        self.fixture["cognitive_usage"] = []
        self.fixture["cognitive_accounts"] = [
            {
                "name": "foundry-account",
                "kind": "AIServices",
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ]
        self.fixture["cognitive_deployments"] = [
            {
                "name": configured.deployment_name,
                "properties": {
                    "model": {
                        "format": configured.model_format,
                        "name": configured.model_name,
                        "version": configured.model_version,
                    },
                    "provisioningState": "Succeeded",
                },
                "sku": {
                    "name": configured.sku_name,
                    "capacity": configured.capacity,
                },
            }
            for configured in (config().chat, config().embeddings)
        ]

        preflight = CapacityPreflight(self.client, config())
        preflight.run()

        self.assertTrue(
            any(
                "existing healthy account and exact model deployments" in warning
                or "existing healthy AI Services account" in warning
                for warning in preflight.warnings
            )
        )

    def test_existing_resources_allow_full_quota_reconciliation(self) -> None:
        self.fixture["search_usage"]["value"][0]["currentValue"] = 12
        self.fixture["search_services"] = [
            {
                "location": "East US",
                "sku": {"name": "basic"},
                "status": "running",
            }
        ]
        for usage in self.fixture["compute_usage"]:
            usage["currentValue"] = usage["limit"]
        self.fixture["virtual_machines"] = [
            {
                "location": "East US 2",
                "hardwareProfile": {"vmSize": "Standard_D4s_v7"},
                "provisioningState": "Succeeded",
            }
        ]
        self.fixture["container_quotas"][0]["properties"]["limit"]["value"] = 1
        self.fixture["container_usage"][0]["properties"]["usages"]["value"] = 1
        self.fixture["container_environments"] = [
            {
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ]
        for usage in self.fixture["cognitive_usage"]:
            usage["currentValue"] = usage["limit"]
        self.fixture["cognitive_accounts"] = [
            {
                "name": "foundry-account",
                "kind": "AIServices",
                "location": "East US 2",
                "properties": {"provisioningState": "Succeeded"},
            }
        ]
        self.fixture["cognitive_deployments"] = [
            {
                "name": configured.deployment_name,
                "properties": {
                    "model": {
                        "format": configured.model_format,
                        "name": configured.model_name,
                        "version": configured.model_version,
                    },
                    "provisioningState": "Succeeded",
                },
                "sku": {
                    "name": configured.sku_name,
                    "capacity": configured.capacity,
                },
            }
            for configured in (config().chat, config().embeddings)
        ]

        preflight = CapacityPreflight(self.client, config())
        preflight.run()

        self.assertTrue(
            any("no incremental Search quota" in warning for warning in preflight.warnings)
        )
        self.assertTrue(
            any("no incremental compute quota" in warning for warning in preflight.warnings)
        )
        self.assertTrue(
            any("no incremental environment quota" in warning for warning in preflight.warnings)
        )
        self.assertTrue(
            any("no incremental account or model quota" in warning for warning in preflight.warnings)
        )


if __name__ == "__main__":
    unittest.main()
