from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / "reconcile_activity_endpoint.py"
SPEC = importlib.util.spec_from_file_location("reconcile_activity_endpoint", SCRIPT)
assert SPEC and SPEC.loader
activity = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = activity
SPEC.loader.exec_module(activity)


def agent_state(
    *,
    protocols: dict | None = None,
    schemes: list[dict] | None = None,
) -> dict:
    protocol_configuration = (
        protocols
        if protocols is not None
        else {
            "responses": {"version": "2.0.0"},
            "a2a": {"custom": True},
        }
    )
    authorization_schemes = (
        schemes
        if schemes is not None
        else [
            {
                "type": "Entra",
                "isolation_key_source": {"kind": "Entra"},
            },
            {"type": "CustomAuth", "setting": "preserve"},
        ]
    )
    return {
        "name": "fixture-agent",
        "agent_endpoint": {
            "protocol_configuration": protocol_configuration,
            "authorization_schemes": authorization_schemes,
            "version_selector": {"preserve": True},
        },
        "unrelated": {"preserve": True},
    }


class FakeClient:
    def __init__(self, document: dict, etag: str | None = '"fixture-etag"') -> None:
        self.document = document
        self.etag = etag
        self.patch_calls: list[tuple[dict, str | None]] = []

    def get_agent(self):
        return activity.AgentState(document=self.document, etag=self.etag)

    def patch_agent(self, patch, etag):
        self.patch_calls.append((patch, etag))


class StaticToken:
    def get_token(self) -> str:
        return "secret-access-token"


class FakeResponse:
    def __init__(self, document: dict | None, headers: dict[str, str] | None = None):
        self._raw = b"" if document is None else json.dumps(document).encode()
        self.headers = headers or {}

    def read(self, _size: int) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ActivityEndpointStateTests(unittest.TestCase):
    def test_shared_preserves_unrelated_state_and_adds_activity_and_rbac(self) -> None:
        document = agent_state()

        desired = activity.build_desired_state(document, mode="apply", publish_scope="Shared")

        endpoint = desired.patch["agent_endpoint"]
        self.assertEqual(
            endpoint["protocol_configuration"],
            {
                "responses": {"version": "2.0.0"},
                "a2a": {"custom": True},
                "activity": {"enable_m365_public_endpoint": True},
            },
        )
        self.assertEqual(
            endpoint["authorization_schemes"],
            [
                {
                    "type": "Entra",
                    "isolation_key_source": {"kind": "Entra"},
                },
                {"type": "CustomAuth", "setting": "preserve"},
                {"type": "BotServiceRbac"},
            ],
        )
        self.assertNotIn("version_selector", endpoint)
        self.assertTrue(desired.changed)

    def test_tenant_replaces_all_bot_schemes_with_exactly_tenant(self) -> None:
        document = agent_state(
            schemes=[
                {"type": "Entra"},
                {"type": "BotServiceRbac"},
                {"type": "BotServiceTenant", "preserve": "target metadata"},
                {"type": "BotServiceTenant"},
                {"type": "Other"},
            ]
        )

        desired = activity.build_desired_state(document, mode="apply", publish_scope="Tenant")
        schemes = desired.patch["agent_endpoint"]["authorization_schemes"]

        self.assertEqual(
            schemes,
            [
                {"type": "Entra"},
                {"type": "Other"},
                {"type": "BotServiceTenant", "preserve": "target metadata"},
            ],
        )
        self.assertEqual([item["type"] for item in schemes].count("BotServiceTenant"), 1)
        self.assertNotIn("BotServiceRbac", [item["type"] for item in schemes])

    def test_apply_is_idempotent_and_skips_patch_when_converged(self) -> None:
        document = agent_state(
            protocols={
                "responses": {},
                "activity": {
                    "enable_m365_public_endpoint": True,
                    "preserve": "metadata",
                },
            },
            schemes=[{"type": "Entra"}, {"type": "BotServiceRbac"}],
        )
        client = FakeClient(document)

        desired = activity.reconcile(client, mode="apply", publish_scope="Shared")

        self.assertFalse(desired.changed)
        self.assertEqual(client.patch_calls, [])

    def test_rollback_removes_only_activity_and_bot_authorization(self) -> None:
        document = agent_state(
            protocols={
                "responses": {"version": "2.0.0"},
                "activity": {"enable_m365_public_endpoint": True},
                "invocations": {"preserve": True},
            },
            schemes=[
                {"type": "Entra", "preserve": True},
                {"type": "BotServiceRbac"},
                {"type": "BotServiceTenant"},
                {"type": "Other", "preserve": True},
            ],
        )

        desired = activity.build_desired_state(document, mode="rollback", publish_scope="Shared")

        self.assertEqual(
            desired.patch["agent_endpoint"]["protocol_configuration"],
            {
                "responses": {"version": "2.0.0"},
                "invocations": {"preserve": True},
            },
        )
        self.assertEqual(
            desired.patch["agent_endpoint"]["authorization_schemes"],
            [
                {"type": "Entra", "preserve": True},
                {"type": "Other", "preserve": True},
            ],
        )

    def test_missing_responses_or_entra_is_rejected(self) -> None:
        cases = (
            agent_state(protocols={"activity": {}}, schemes=[{"type": "Entra"}]),
            agent_state(protocols={"responses": {}}, schemes=[{"type": "Other"}]),
        )
        for document in cases:
            with self.subTest(document=document):
                with self.assertRaises(activity.ReconcileError):
                    activity.build_desired_state(document, mode="apply", publish_scope="Shared")

    def test_malformed_agent_state_is_rejected(self) -> None:
        malformed = (
            {},
            {"agent_endpoint": []},
            {
                "agent_endpoint": {
                    "protocol_configuration": [],
                    "authorization_schemes": [],
                }
            },
            {
                "agent_endpoint": {
                    "protocol_configuration": {"responses": {}},
                    "authorization_schemes": [{"missing": "type"}],
                }
            },
            {
                "agent_endpoint": {
                    "protocol_configuration": {
                        "responses": {},
                        "activity": [],
                    },
                    "authorization_schemes": [{"type": "Entra"}],
                }
            },
        )
        for document in malformed:
            with self.subTest(document=document):
                with self.assertRaises(activity.ReconcileError):
                    activity.build_desired_state(document, mode="apply", publish_scope="Shared")

    def test_invalid_mode_and_scope_are_rejected(self) -> None:
        with self.assertRaises(activity.ReconcileError):
            activity.build_desired_state(
                agent_state(),
                mode="replace",
                publish_scope="Shared",
            )
        with self.assertRaises(activity.ReconcileError):
            activity.build_desired_state(
                agent_state(),
                mode="apply",
                publish_scope="Personal",
            )

    def test_apply_passes_get_etag_as_if_match(self) -> None:
        requests = []
        responses = [
            FakeResponse(agent_state(), {"ETag": '"server-etag"'}),
            FakeResponse(None),
        ]

        def opener(request, timeout):
            self.assertEqual(timeout, 30)
            requests.append(request)
            return responses.pop(0)

        client = activity.FoundryAgentClient(
            project_endpoint="https://fixture.invalid/api/projects/private",
            agent_name="agent/name",
            token_provider=StaticToken(),
            opener=opener,
        )

        desired = activity.reconcile(client, mode="apply", publish_scope="Shared")

        self.assertTrue(desired.changed)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].get_method(), "GET")
        self.assertEqual(requests[1].get_method(), "PATCH")
        self.assertEqual(
            requests[0].get_header("Authorization"),
            "Bearer secret-access-token",
        )
        self.assertEqual(requests[1].get_header("If-match"), '"server-etag"')
        self.assertEqual(
            requests[1].get_header("Content-type"),
            "application/merge-patch+json",
        )
        self.assertNotIn("agent/name", requests[0].full_url)
        self.assertIn("agent%2Fname", requests[0].full_url)

    def test_apply_omits_if_match_when_get_has_no_etag(self) -> None:
        requests = []
        responses = [FakeResponse(agent_state()), FakeResponse(None)]

        def opener(request, timeout):
            requests.append(request)
            return responses.pop(0)

        client = activity.FoundryAgentClient(
            project_endpoint="https://fixture.invalid/api/projects/private",
            agent_name="agent",
            token_provider=StaticToken(),
            opener=opener,
        )

        activity.reconcile(client, mode="apply", publish_scope="Shared")

        self.assertIsNone(requests[1].get_header("If-match"))

    def test_http_errors_and_output_are_sanitized(self) -> None:
        endpoint = "https://customer-name.invalid/api/projects/customer-project"
        response_body = b'{"error":{"message":"customer-secret response body"}}'

        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                {},
                io.BytesIO(response_body),
            )

        client = activity.FoundryAgentClient(
            project_endpoint=endpoint,
            agent_name="customer-agent",
            token_provider=StaticToken(),
            opener=opener,
        )
        with self.assertRaises(activity.ReconcileError) as caught:
            client.get_agent()
        message = str(caught.exception)
        self.assertEqual(
            message,
            "Foundry request failed with HTTP 403 (forbidden).",
        )
        self.assertNotIn("customer", message)
        self.assertNotIn("secret-access-token", message)
        self.assertNotIn("response body", message)

        fake = FakeClient(agent_state())
        desired = activity.reconcile(fake, mode="plan", publish_scope="Shared")
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            print(activity.format_result("plan", desired))
        output = stdout.getvalue()
        self.assertNotIn("fixture-agent", output)
        self.assertNotIn("customer", output)
        self.assertNotIn("secret", output)
        self.assertIn("protocols=", output)
        self.assertIn("authorization=", output)

        unsafe = activity.build_desired_state(
            agent_state(
                protocols={"responses": {}, "customer/protocol": {}},
                schemes=[{"type": "Entra"}, {"type": "customer authorization"}],
            ),
            mode="plan",
            publish_scope="Shared",
        )
        self.assertIn("<redacted>", unsafe.protocols)
        self.assertIn("<redacted>", unsafe.authorization_schemes)

    def test_precondition_failure_is_sanitized(self) -> None:
        def opener(request, timeout):
            raise HTTPError(
                request.full_url,
                412,
                "Precondition Failed",
                {},
                io.BytesIO(b"sensitive body"),
            )

        client = activity.FoundryAgentClient(
            project_endpoint="https://fixture.invalid/api/projects/private",
            agent_name="agent",
            token_provider=StaticToken(),
            opener=opener,
        )
        with self.assertRaises(activity.ReconcileError) as caught:
            client.patch_agent({"agent_endpoint": {}}, '"stale"')
        self.assertIn("HTTP 412", str(caught.exception))
        self.assertNotIn("sensitive", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
