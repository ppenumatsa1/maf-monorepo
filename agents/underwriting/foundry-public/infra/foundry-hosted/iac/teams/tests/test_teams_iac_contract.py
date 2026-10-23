from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

TEAMS_DIR = Path(__file__).resolve().parents[1]
MAIN = TEAMS_DIR / "main.bicep"


class TeamsIacContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            ["az", "bicep", "build", "--file", str(MAIN), "--stdout"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Bicep build/lint failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        cls.template = json.loads(result.stdout)
        cls.source = MAIN.read_text()

    def test_bot_service_contract_is_restricted_single_tenant_azurebot(self) -> None:
        bot = next(
            resource
            for resource in self.template["resources"]
            if resource["type"] == "Microsoft.BotService/botServices"
        )

        self.assertEqual(bot["apiVersion"], "2022-09-15")
        self.assertEqual(bot["kind"], "azurebot")
        self.assertEqual(bot["location"], "global")
        self.assertEqual(bot["properties"]["publicNetworkAccess"], "Disabled")
        self.assertEqual(bot["properties"]["msaAppType"], "SingleTenant")
        self.assertEqual(
            bot["properties"]["msaAppId"],
            "[variables('validatedAgentIdentityClientId')]",
        )
        self.assertEqual(
            bot["properties"]["msaAppTenantId"],
            "[variables('validatedTenantId')]",
        )
        self.assertNotIn(
            "defaultValue",
            self.template["parameters"]["botSkuName"],
        )

    def test_activity_endpoint_has_the_exact_foundry_activity_protocol_shape(self) -> None:
        self.assertIn(
            "var activityProtocolApiVersion = '2025-05-15-preview'",
            self.source,
        )
        self.assertIn(
            "var activityEndpoint = 'https://${validatedFoundryResourceName}.services.ai.azure.com/api/projects/${validatedFoundryProjectName}/agents/${validatedHostedAgentName}/endpoint/protocols/activityProtocol?api-version=${activityProtocolApiVersion}'",
            self.source,
        )
        self.assertNotIn("param endpoint string", self.source)

        bot = next(
            resource
            for resource in self.template["resources"]
            if resource["type"] == "Microsoft.BotService/botServices"
        )
        self.assertEqual(
            bot["properties"]["endpoint"],
            "[variables('activityEndpoint')]",
        )
        endpoint = self.template["variables"]["activityEndpoint"]
        self.assertIn(
            "https://{0}.services.ai.azure.com/api/projects/{1}/agents/{2}/endpoint/protocols/activityProtocol?api-version={3}",
            endpoint,
        )
        self.assertEqual(
            self.template["variables"]["activityProtocolApiVersion"],
            "2025-05-15-preview",
        )

    def test_teams_channel_is_declarative_and_named_ms_teams_channel(self) -> None:
        channel = next(
            resource
            for resource in self.template["resources"]
            if resource["type"] == "Microsoft.BotService/botServices/channels"
        )

        self.assertEqual(channel["apiVersion"], "2022-09-15")
        self.assertEqual(channel["location"], "global")
        self.assertEqual(channel["properties"]["channelName"], "MsTeamsChannel")
        self.assertEqual(
            channel["properties"]["properties"],
            {
                "acceptedTerms": True,
                "deploymentEnvironment": "CommercialDeployment",
                "enableCalling": False,
                "isEnabled": True,
            },
        )
        self.assertEqual(
            channel["name"],
            "[format('{0}/{1}', parameters('botName'), 'MsTeamsChannel')]",
        )

    def test_bot_diagnostics_send_requests_and_metrics_to_log_analytics(self) -> None:
        diagnostic = next(
            resource
            for resource in self.template["resources"]
            if resource["type"] == "Microsoft.Insights/diagnosticSettings"
        )

        self.assertEqual(diagnostic["apiVersion"], "2021-05-01-preview")
        self.assertEqual(diagnostic["name"], "bot-request-diagnostics")
        self.assertEqual(
            diagnostic["scope"],
            "[resourceId('Microsoft.BotService/botServices', parameters('botName'))]",
        )
        self.assertEqual(
            diagnostic["properties"]["workspaceId"],
            "[variables('validatedLogAnalyticsWorkspaceResourceId')]",
        )
        self.assertEqual(
            diagnostic["properties"]["logs"],
            [
                {
                    "category": "BotRequest",
                    "enabled": True,
                    "retentionPolicy": {"days": 0, "enabled": False},
                }
            ],
        )
        self.assertEqual(
            diagnostic["properties"]["metrics"],
            [
                {
                    "category": "AllMetrics",
                    "enabled": True,
                    "retentionPolicy": {"days": 0, "enabled": False},
                }
            ],
        )

    def test_contract_accepts_no_secrets_and_exposes_required_outputs(self) -> None:
        parameter_names = set(self.template["parameters"])
        self.assertEqual(
            {
                "agentIdentityClientId",
                "botDisplayName",
                "botName",
                "botSkuName",
                "foundryProjectName",
                "foundryResourceName",
                "hostedAgentName",
                "logAnalyticsWorkspaceResourceId",
                "tenantId",
            },
            parameter_names,
        )
        self.assertFalse(
            {
                name
                for name, parameter in self.template["parameters"].items()
                if parameter["type"] in {"secureString", "secureObject"}
            }
        )
        self.assertEqual(
            {
                "activityEndpoint",
                "botDiagnosticSettingResourceId",
                "botName",
                "botResourceId",
                "teamsChannelName",
                "teamsChannelResourceId",
            },
            set(self.template["outputs"]),
        )

    def test_parameters_are_bounded_and_runtime_identifiers_are_validated(self) -> None:
        parameters = self.template["parameters"]
        self.assertEqual(
            (
                parameters["agentIdentityClientId"]["minLength"],
                parameters["agentIdentityClientId"]["maxLength"],
            ),
            (36, 36),
        )
        self.assertEqual(
            (parameters["tenantId"]["minLength"], parameters["tenantId"]["maxLength"]),
            (36, 36),
        )
        self.assertEqual(parameters["botSkuName"]["allowedValues"], ["F0", "S1"])
        self.assertNotIn("defaultValue", parameters["botName"])
        for variable_name in (
            "validatedAgentIdentityClientId",
            "validatedFoundryProjectName",
            "validatedFoundryResourceName",
            "validatedHostedAgentName",
            "validatedLogAnalyticsWorkspaceResourceId",
            "validatedTenantId",
        ):
            self.assertIn("fail(", self.template["variables"][variable_name])

    def test_deployment_target_identifiers_are_not_hardcoded(self) -> None:
        parameters = self.template["parameters"]
        for parameter_name in ("agentIdentityClientId", "tenantId"):
            self.assertNotIn("defaultValue", parameters[parameter_name])
        self.assertNotIn("param subscriptionId", self.source)
        self.assertNotIn("param location", self.source)
        self.assertIsNone(
            re.search(
                r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b",
                self.source,
            )
        )


if __name__ == "__main__":
    unittest.main()
