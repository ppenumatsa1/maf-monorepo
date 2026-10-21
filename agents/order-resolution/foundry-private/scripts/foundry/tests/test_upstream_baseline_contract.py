from __future__ import annotations

import ipaddress
import json
import unittest
from pathlib import Path

PRIVATE_ROOT = Path(__file__).resolve().parents[3]
IAC_DIR = PRIVATE_ROOT / "infra" / "foundry-hosted" / "iac"
MAIN = IAC_DIR / "main.bicep"
PARAMETERS = IAC_DIR / "main.parameters.json"
VNET = IAC_DIR / "modules" / "vnet.bicep"
PROFILE = PRIVATE_ROOT.parent / "deployment" / "profiles" / "foundry-private.env"
REFERENCE = PRIVATE_ROOT / "infra" / "foundry-hosted" / "upstream-reference.json"

EXPECTED_REFERENCE = {
    "repository": "https://github.com/microsoft-foundry/foundry-samples",
    "path": "infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup",
    "url": (
        "https://github.com/microsoft-foundry/foundry-samples/tree/main/"
        "infrastructure/infrastructure-setup-bicep/"
        "15-private-network-standard-agent-setup"
    ),
    "commit": "ce52cffdbd91716723b06eb1bce39f964a23ed45",
    "commitDate": "2026-09-15T18:26:22Z",
    "auditedOn": "2026-10-19",
}


def read_profile() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in PROFILE.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


class UpstreamBaselineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = MAIN.read_text()
        cls.parameters = json.loads(PARAMETERS.read_text())["parameters"]
        cls.vnet = VNET.read_text()
        cls.profile = read_profile()
        cls.reference = json.loads(REFERENCE.read_text())

    def test_reference_is_pinned_as_a_selected_control_baseline(self) -> None:
        self.assertEqual(self.reference["schemaVersion"], 1)
        self.assertEqual(self.reference["reference"], EXPECTED_REFERENCE)
        self.assertEqual(
            self.reference["comparison"],
            {
                "mode": "selected-control-contract",
                "byteForByteParityRequired": False,
                "repositoryTopologyRemainsAuthoritative": True,
                "monitoringChangesIncluded": False,
            },
        )

    def test_foundry_account_disables_public_and_local_auth(self) -> None:
        account = section(
            self.main,
            "resource foundryAccount ",
            "resource foundryProject ",
        )
        self.assertIn("disableLocalAuth: true", account)
        self.assertIn(
            "publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'",
            account,
        )
        self.assertEqual(self.profile["NETWORK_MODE"], "private")

    def test_agent_network_injection_uses_a_delegated_24_subnet(self) -> None:
        injection = section(
            self.main,
            "var foundryNetworkInjectionProperties ",
            "#disable-next-line no-hardcoded-env-urls",
        )
        agent_subnet = section(
            self.vnet,
            "name: agentSubnetName",
            "name: privateEndpointSubnetName",
        )

        self.assertIn("scenario: 'agent'", injection)
        self.assertIn("subnetArmId: agentSubnetResourceId", injection)
        self.assertIn("useMicrosoftManagedNetwork: false", injection)
        self.assertEqual(self.profile["ENABLE_STANDARD_AGENT_NETWORK_INJECTION"], "true")
        self.assertEqual(
            ipaddress.ip_network(self.profile["AGENT_SUBNET_PREFIX"]).prefixlen,
            24,
        )
        self.assertIn("serviceName: 'Microsoft.App/environments'", agent_subnet)

    def test_acr_is_private_and_agent_service_endpoint_is_retained(self) -> None:
        registry = section(
            self.main,
            "resource containerRegistry ",
            "resource logAnalytics ",
        )
        acr_endpoint = section(
            self.main,
            "module acrPrivateEndpoint ",
            "module postgresPrivateEndpoint ",
        )
        agent_subnet = section(
            self.vnet,
            "name: agentSubnetName",
            "name: privateEndpointSubnetName",
        )

        self.assertIn("adminUserEnabled: false", registry)
        self.assertIn(
            "publicNetworkAccess: privateNetworking ? 'Disabled' : 'Enabled'",
            registry,
        )
        self.assertIn("targetResourceId: containerRegistry.id", acr_endpoint)
        self.assertIn("'registry'", acr_endpoint)
        self.assertIn("'privatelink.azurecr.io'", self.main)
        self.assertIn("serviceEndpoints:", agent_subnet)
        self.assertIn("service: 'Microsoft.CognitiveServices'", agent_subnet)
        self.assertEqual(self.profile["CREATE_PRIVATE_ENDPOINTS"], "true")

    def test_capability_host_defaults_remain_disabled(self) -> None:
        self.assertEqual(self.profile["CREATE_ACCOUNT_CAPABILITY_HOST"], "false")
        self.assertEqual(self.profile["CREATE_PROJECT_CAPABILITY_HOST"], "false")
        self.assertEqual(
            self.parameters["createAccountCapabilityHost"]["value"],
            "${CREATE_ACCOUNT_CAPABILITY_HOST}",
        )
        self.assertEqual(
            self.parameters["createProjectCapabilityHost"]["value"],
            "${CREATE_PROJECT_CAPABILITY_HOST}",
        )


if __name__ == "__main__":
    unittest.main()
