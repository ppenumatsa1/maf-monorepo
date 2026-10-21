from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = SCRIPTS_DIR / "publish_teams_agent.py"
MANIFEST = PRIVATE_ROOT / "infra" / "foundry-hosted" / "teams-publication.json"
SCRATCH = PRIVATE_ROOT / ".artifacts" / "tests" / "teams-publication"

sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("publish_teams_agent", SCRIPT)
assert SPEC and SPEC.loader
publishing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publishing
SPEC.loader.exec_module(publishing)


def agent_document() -> dict:
    return {
        "instance_identity": {
            "client_id": "00001111-aaaa-2222-bbbb-3333cccc4444",
            "principal_id": "do-not-log",
        },
        "agent_endpoint": {
            "protocol_configuration": {"responses": {"version": "2.0.0"}},
            "authorization_schemes": [{"type": "Entra"}],
        },
    }


def package_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("manifest.json", "{}")
        package.writestr("color.png", b"fixture")
    return buffer.getvalue()


def inspected_package_bytes(manifest: publishing.PublicationManifest) -> bytes:
    buffer = io.BytesIO()
    document = {
        "version": manifest.app_version,
        "name": {
            "short": manifest.metadata["agentDisplayName"],
            "full": manifest.metadata["agentDisplayName"],
        },
        "description": {
            "short": manifest.metadata["shortDescription"],
            "full": manifest.metadata["fullDescription"],
        },
        "developer": {
            "name": manifest.metadata["developerName"],
            "websiteUrl": manifest.metadata["developerWebsiteUrl"],
            "privacyUrl": manifest.metadata["privacyUrl"],
            "termsOfUseUrl": manifest.metadata["termsOfUseUrl"],
        },
        "icons": {
            "color": "default-color-icon.png",
            "outline": "default-outline-icon.png",
        },
        "bots": [
            {
                "botId": "00001111-aaaa-2222-bbbb-3333cccc4444",
                "scopes": ["personal"],
            }
        ],
    }
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("manifest.json", json.dumps(document))
        package.writestr("default-color-icon.png", b"fixture")
        package.writestr("default-outline-icon.png", b"fixture")
    return buffer.getvalue()


class StaticToken:
    def get_token(self) -> str:
        return "secret-token"


class FakeResponse:
    def __init__(self, raw: bytes):
        self.raw = raw

    def read(self, size: int) -> bytes:
        return self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeActivityClient:
    def __init__(self) -> None:
        self.get_calls = 0
        self.patch_calls: list[tuple[dict, str | None]] = []
        self.document = agent_document()

    def get_agent(self):
        self.get_calls += 1
        return publishing.activity.AgentState(self.document, '"etag"')

    def patch_agent(self, body, etag):
        self.patch_calls.append((body, etag))


class TeamsPublishingTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        SCRATCH.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def test_identity_extraction_validates_shape_without_using_principal_id(self) -> None:
        self.assertEqual(
            publishing.extract_agent_identity_client_id(agent_document()),
            "00001111-aaaa-2222-bbbb-3333cccc4444",
        )
        for malformed in (
            {},
            {"instance_identity": []},
            {"instance_identity": {}},
            {"instance_identity": {"client_id": "not-a-guid"}},
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(publishing.PublicationError):
                    publishing.extract_agent_identity_client_id(malformed)

    def test_bicep_command_is_declarative_and_passes_runtime_identity(self) -> None:
        command = publishing.build_bicep_command(
            resource_group="fixture-rg",
            template_file=Path("iac/teams/main.bicep"),
            coordinates=publishing.ProjectCoordinates("fixture-foundry", "fixture-project"),
            agent_name="fixture-agent",
            agent_identity_client_id="00001111-aaaa-2222-bbbb-3333cccc4444",
            tenant_id="11112222-bbbb-3333-cccc-4444dddd5555",
            log_analytics_workspace_resource_id=(
                "/subscriptions/sub/resourceGroups/fixture-rg/providers/"
                "Microsoft.OperationalInsights/workspaces/fixture-law"
            ),
            bot_display_name="Fixture Agent",
        )
        joined = " ".join(command)

        self.assertEqual(command[:4], ["az", "deployment", "group", "create"])
        self.assertIn("--template-file iac/teams/main.bicep", joined)
        self.assertIn("agentIdentityClientId=00001111-aaaa-2222-bbbb-3333cccc4444", command)
        self.assertIn("tenantId=11112222-bbbb-3333-cccc-4444dddd5555", command)
        self.assertIn(
            "logAnalyticsWorkspaceResourceId=/subscriptions/sub/resourceGroups/"
            "fixture-rg/providers/Microsoft.OperationalInsights/workspaces/fixture-law",
            command,
        )
        self.assertNotIn("az bot", joined)
        self.assertNotIn("channel", joined.casefold())

    def test_deploy_bot_reads_only_bicep_output_and_sanitizes_failure(self) -> None:
        resource_id = (
            "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.BotService/botServices/bot"
        )

        def success(command, *, cwd=None, env=None):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"botResourceId": {"value": resource_id}}),
                "",
            )

        self.assertEqual(publishing.deploy_bot(["az"], runner=success), resource_id)

        def failure(command, *, cwd=None, env=None):
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "tenant customer subscription secret",
            )

        with self.assertRaises(publishing.PublicationError) as caught:
            publishing.deploy_bot(["az"], runner=failure)
        self.assertNotIn("tenant", str(caught.exception))
        self.assertNotIn("customer", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_bot_resource_id_is_looked_up_from_arm_without_bot_cli(self) -> None:
        resource_id = (
            "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.BotService/botServices/bot"
        )
        commands = []

        def runner(command, *, cwd=None, env=None):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, resource_id + "\n", "")

        self.assertEqual(
            publishing.resolve_bot_resource_id(None, resource_group="fixture-rg", runner=runner),
            resource_id,
        )
        self.assertEqual(commands[0][:4], ["az", "deployment", "group", "show"])
        self.assertNotIn("bot", commands[0][1:3])

    def test_log_analytics_workspace_is_resolved_declaratively(self) -> None:
        resource_id = (
            "/subscriptions/sub/resourceGroups/fixture-rg/providers/"
            "Microsoft.OperationalInsights/workspaces/fixture-law"
        )
        commands = []

        def runner(command, *, cwd=None, env=None):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps([resource_id]), "")

        self.assertEqual(
            publishing.resolve_log_analytics_workspace_resource_id(
                resource_group="fixture-rg",
                runner=runner,
            ),
            resource_id,
        )
        self.assertEqual(
            commands[0][:5],
            ["az", "monitor", "log-analytics", "workspace", "list"],
        )

    def test_manifest_validation_hash_and_semantic_versioning(self) -> None:
        manifest = publishing.load_manifest(MANIFEST)
        self.assertEqual(manifest.app_version, "1.0.0")
        self.assertEqual(manifest.publish_scope, "Shared")
        self.assertEqual(len(manifest.sha256), 64)

        invalid = json.loads(MANIFEST.read_text())
        invalid["appVersion"] = "1"
        invalid_path = SCRATCH / "invalid.json"
        invalid_path.write_text(json.dumps(invalid))
        with self.assertRaises(publishing.PublicationError):
            publishing.load_manifest(invalid_path)

        state = publishing.LocalPublicationState(SCRATCH)
        state.write_public(
            {
                "schemaVersion": 1,
                "records": {
                    "1.0.0": {
                        "manifestHash": manifest.sha256,
                        "scope": "Shared",
                        "published": True,
                    }
                },
            }
        )
        with self.assertRaisesRegex(publishing.PublicationError, "already published"):
            state.validate_version_for_publish(manifest, state.read_public())

        changed = json.loads(MANIFEST.read_text())
        changed["metadata"]["shortDescription"] = "Changed without a version increment."
        changed_path = SCRATCH / "changed.json"
        changed_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(publishing.PublicationError, "different metadata"):
            state.ensure_manifest_compatible(
                publishing.load_manifest(changed_path),
                state.read_public(),
            )

        older = json.loads(MANIFEST.read_text())
        older["appVersion"] = "0.9.0"
        older_path = SCRATCH / "older.json"
        older_path.write_text(json.dumps(older))
        with self.assertRaisesRegex(publishing.PublicationError, "greater than"):
            state.validate_version_for_publish(
                publishing.load_manifest(older_path),
                state.read_public(),
            )

    def test_publish_payload_matches_documented_api(self) -> None:
        manifest = publishing.load_manifest(MANIFEST)
        resource_id = (
            "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.BotService/botServices/bot"
        )
        payload = publishing.build_publish_payload(manifest, resource_id)

        self.assertEqual(payload["botServiceArmId"], resource_id)
        self.assertEqual(payload["publishScope"], "Shared")
        self.assertEqual(payload["appVersion"], "1.0.0")
        self.assertIs(payload["publishAsAutopilot"], False)
        self.assertEqual(payload["agentDisplayName"], "Order Resolution Assistant")
        self.assertEqual(
            set(payload),
            publishing.METADATA_KEYS
            | {
                "botServiceArmId",
                "publishScope",
                "publishAsAutopilot",
                "appVersion",
            },
        )

    def test_shared_requires_interactive_user_context(self) -> None:
        publishing.require_interactive_user(
            publishing.AzureContext("11112222-bbbb-3333-cccc-4444dddd5555", "user"),
            "Shared",
        )
        for identity_type in ("servicePrincipal", "managedIdentity"):
            with self.subTest(identity_type=identity_type):
                with self.assertRaisesRegex(
                    publishing.PublicationError,
                    "interactive Azure CLI user",
                ):
                    publishing.require_interactive_user(
                        publishing.AzureContext(
                            "11112222-bbbb-3333-cccc-4444dddd5555",
                            identity_type,
                        ),
                        "Shared",
                    )
        publishing.require_interactive_user(
            publishing.AzureContext(
                "11112222-bbbb-3333-cccc-4444dddd5555",
                "servicePrincipal",
            ),
            "Tenant",
        )

    def test_shared_package_fails_before_activity_without_interactive_user(self) -> None:
        args = type(
            "Args",
            (),
            {
                "project_endpoint": "https://fixture.services.ai.azure.com/api/projects/private",
                "agent_name": "fixture-agent",
                "artifact_dir": SCRATCH,
                "azd_project_dir": SCRATCH,
            },
        )()
        manifest = publishing.load_manifest(MANIFEST)

        with (
            patch.object(
                publishing,
                "get_azure_context",
                return_value=publishing.AzureContext(
                    "11112222-bbbb-3333-cccc-4444dddd5555",
                    "servicePrincipal",
                ),
            ),
            patch.object(publishing, "_agent_client") as agent_client,
            self.assertRaisesRegex(
                publishing.PublicationError,
                "interactive Azure CLI user",
            ),
        ):
            publishing._command_package(args, manifest)
        agent_client.assert_not_called()

    def test_agent_name_resolves_from_order_resolution_azd_convention(self) -> None:
        args = type(
            "Args",
            (),
            {
                "project_endpoint": "https://fixture.services.ai.azure.com/api/projects/p",
                "agent_name": None,
                "azd_project_dir": SCRATCH,
            },
        )()
        with patch.dict(
            publishing.os.environ,
            {"AGENT_ORDER_RESOLUTION_HOSTED_NAME": "fixture-agent"},
            clear=False,
        ):
            endpoint, agent_name = publishing._resolve_common(args)
        self.assertEqual(endpoint, args.project_endpoint)
        self.assertEqual(agent_name, "fixture-agent")

    def test_activity_plan_precedes_apply_and_preserves_reconciler_safety(self) -> None:
        client = FakeActivityClient()

        planned, applied = publishing.prepare_activity(
            client,
            publish_scope="Shared",
            apply=True,
        )

        self.assertEqual(client.get_calls, 2)
        self.assertEqual(len(client.patch_calls), 1)
        self.assertTrue(planned.changed)
        self.assertIsNotNone(applied)
        patch, etag = client.patch_calls[0]
        self.assertEqual(etag, '"etag"')
        self.assertIn("responses", patch["agent_endpoint"]["protocol_configuration"])
        self.assertTrue(
            patch["agent_endpoint"]["protocol_configuration"]["activity"][
                "enable_m365_public_endpoint"
            ]
        )

    def test_package_and_publish_requests_use_documented_endpoints(self) -> None:
        requests = []
        responses = [
            FakeResponse(package_bytes()),
            FakeResponse(json.dumps({"titleId": "sensitive-title-id"}).encode()),
        ]

        def opener(request, timeout):
            self.assertEqual(timeout, 60)
            requests.append(request)
            return responses.pop(0)

        client = publishing.Microsoft365Client(
            project_endpoint="https://fixture.services.ai.azure.com/api/projects/private",
            agent_name="agent/name",
            token_provider=StaticToken(),
            opener=opener,
        )
        payload = {"appVersion": "1.0.0"}
        self.assertTrue(client.package(payload).startswith(b"PK"))
        self.assertEqual(client.publish(payload), "sensitive-title-id")

        self.assertIn("/microsoft365/zip?api-version=v1", requests[0].full_url)
        self.assertIn("/microsoft365/publish?api-version=v1", requests[1].full_url)
        self.assertIn("agent%2Fname", requests[0].full_url)
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertTrue(requests[0].get_header("Authorization"))
        self.assertEqual(requests[0].get_header("Content-type"), "application/json")

    def test_generated_package_inspection_uses_manifest_icon_references(self) -> None:
        manifest = publishing.load_manifest(MANIFEST)
        raw = inspected_package_bytes(manifest)

        publishing.inspect_generated_package(raw, manifest)

        changed = json.loads(MANIFEST.read_text())
        changed["metadata"]["developerName"] = "Different Developer"
        changed_path = SCRATCH / "different-developer.json"
        changed_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(
            publishing.PublicationError,
            "metadata does not match",
        ):
            publishing.inspect_generated_package(
                raw,
                publishing.load_manifest(changed_path),
            )

    def test_known_version_exists_and_other_errors_are_sanitized(self) -> None:
        response_body = b'{"error":{"message":"App version already exists customer-secret"}}'

        def version_opener(request, timeout):
            raise HTTPError(request.full_url, 409, "Conflict", {}, io.BytesIO(response_body))

        client = publishing.Microsoft365Client(
            project_endpoint="https://fixture.services.ai.azure.com/api/projects/private",
            agent_name="agent",
            token_provider=StaticToken(),
            opener=version_opener,
        )
        with self.assertRaisesRegex(
            publishing.PublicationError,
            "increment appVersion explicitly",
        ) as caught:
            client.publish({"appVersion": "1.0.0"})
        self.assertNotIn("customer-secret", str(caught.exception))
        self.assertNotIn("secret-token", str(caught.exception))

        def forbidden_opener(request, timeout):
            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                {},
                io.BytesIO(b"customer subscription response body"),
            )

        forbidden = publishing.Microsoft365Client(
            project_endpoint="https://fixture.services.ai.azure.com/api/projects/private",
            agent_name="agent",
            token_provider=StaticToken(),
            opener=forbidden_opener,
        )
        with self.assertRaises(publishing.PublicationError) as generic:
            forbidden.publish({"appVersion": "1.0.0"})
        self.assertEqual(
            str(generic.exception),
            "Microsoft 365 publish request failed with HTTP 403 (forbidden).",
        )

    def test_validation_errors_include_bounded_redacted_diagnostics(self) -> None:
        response_body = json.dumps(
            {
                "error": {
                    "code": "TeamsAppValidationFailed",
                    "message": (
                        "developerWebsiteUrl is invalid for "
                        "https://customer.example/path and tenant "
                        "11112222-bbbb-3333-cccc-4444dddd5555"
                    ),
                    "details": [
                        {
                            "target": "developerWebsiteUrl",
                            "message": (
                                "Bot "
                                "/subscriptions/sub/resourceGroups/customer-rg/providers/"
                                "Microsoft.BotService/botServices/customer-bot is invalid"
                            ),
                        }
                    ],
                }
            }
        ).encode()

        def validation_opener(request, timeout):
            raise HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(response_body),
            )

        client = publishing.Microsoft365Client(
            project_endpoint="https://fixture.services.ai.azure.com/api/projects/private",
            agent_name="agent",
            token_provider=StaticToken(),
            opener=validation_opener,
        )
        with self.assertRaises(publishing.PublicationError) as caught:
            client.package({"appVersion": "1.0.0"})

        message = str(caught.exception)
        self.assertIn("code=TeamsAppValidationFailed", message)
        self.assertIn("target=developerWebsiteUrl", message)
        self.assertIn("<redacted-url>", message)
        self.assertIn("<redacted-guid>", message)
        self.assertIn("<redacted-resource-id>", message)
        self.assertNotIn("customer.example", message)
        self.assertNotIn("customer-rg", message)
        self.assertNotIn("customer-bot", message)

    def test_public_state_is_sanitized_and_sensitive_values_are_separate(self) -> None:
        manifest = publishing.load_manifest(MANIFEST)
        state = publishing.LocalPublicationState(SCRATCH)
        state.update_record(
            manifest,
            flag="botDeployed",
            timestamp_field="botDeployedAt",
        )
        public_text = state.public_path.read_text()
        forbidden = (
            "subscriptions",
            "resourceGroups",
            "services.ai.azure.com",
            "tenant",
            "titleId",
            "botResourceId",
            "user",
            "response",
        )
        for value in forbidden:
            self.assertNotIn(value, public_text)
        self.assertIn(manifest.sha256, public_text)
        self.assertEqual(state.public_path.stat().st_mode & 0o777, 0o600)

        state.write_sensitive(
            {
                "schemaVersion": 1,
                "titleId": "sensitive-title",
            }
        )
        self.assertNotIn("sensitive-title", state.public_path.read_text())
        self.assertEqual(state.sensitive_path.stat().st_mode & 0o777, 0o600)

        state.sensitive_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "botResourceId": "must-not-be-persisted",
                }
            )
        )
        with self.assertRaisesRegex(publishing.PublicationError, "invalid schema"):
            state.read_sensitive()

    def test_verify_local_state_checks_manifest_hash_and_package(self) -> None:
        manifest = publishing.load_manifest(MANIFEST)
        state = publishing.LocalPublicationState(SCRATCH)
        state.update_record(
            manifest,
            flag="packageGenerated",
            timestamp_field="packageGeneratedAt",
        )
        state.packages_dir.mkdir()
        state.package_path(manifest).write_bytes(package_bytes())
        record = state.verify(manifest)
        self.assertTrue(record["packageGenerated"])

        state.package_path(manifest).write_bytes(b"not-a-zip")
        with self.assertRaisesRegex(publishing.PublicationError, "missing or invalid"):
            state.verify(manifest)

    def test_rollback_boundary_uses_documented_external_actions_only(self) -> None:
        plan = " ".join(publishing.build_rollback_plan())
        self.assertIn("Activity reconciler rollback", plan)
        self.assertIn("catalog entry through Microsoft 365 governance", plan)
        self.assertIn("no documented Foundry unpublish API", plan)
        self.assertIn("ARM/Bicep lifecycle", plan)
        self.assertNotIn("/unpublish", plan)
        self.assertNotIn("az bot delete", plan)


if __name__ == "__main__":
    unittest.main()
