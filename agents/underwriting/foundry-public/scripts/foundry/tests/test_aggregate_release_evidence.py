from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "foundry" / "aggregate_release_evidence.py"
RUNTIME_URL = (
    "postgresql+psycopg://underwriting_runtime:SecretPassword"
    "@underwritingpg.postgres.database.azure.com:5432/underwriting?sslmode=require"
)
RUNTIME_PASSWORD = urlsplit(RUNTIME_URL).password or ""
TIMESTAMP = "2026-08-15T20:00:00Z"
HOSTED_IMAGE = "example.azurecr.io/portable-hosted@sha256:" + "a" * 64


def verification_payload() -> dict[str, object]:
    return {
        "status": "passed",
        "generated_at": TIMESTAMP,
        "target": {
            "subscription_id": "11111111-1111-4111-8111-111111111111",
            "resource_group": "rg-fixture-underwriting",
            "location": "regionone",
        },
        "topology": {
            "frontend_url": "https://frontend.example",
            "frontend_external": True,
            "backend_internal": True,
            "same_origin_health": True,
            "same_origin_api": True,
            "direct_backend_publicly_reachable": False,
        },
        "container_apps": {
            "backend": {"name": "backend", "revision": "backend--1", "image": "backend:1"},
            "frontend": {"name": "frontend", "revision": "frontend--1", "image": "frontend:1"},
        },
        "hosted_agent": {
            "name": "underwriting-hosted",
            "version": "1",
            "status": "active",
            "image": HOSTED_IMAGE,
            "image_repository": "portable-hosted",
            "protocols": [
                {"protocol": "responses", "version": "2.0.0"},
                {"protocol": "activity", "version": "2.0.0"},
            ],
            "db_schema_managed_externally": True,
            "runtime_connection_name": "underwritingruntimesecrets",
            "database_url_placeholder": True,
            "runtime_database_url_placeholder": True,
            "database_url_parity": True,
            "application_insights_configured": True,
        },
        "runtime_secret_connection": {
            "name": "underwritingruntimesecrets",
            "category": "CustomKeys",
            "database_url_metadata_is_placeholder": True,
        },
        "application_insights_connection": True,
        "runtime_database": {
            "url_parity": True,
            "required_schema_ready": True,
            "schema_managed_externally": True,
        },
    }


def hosted_e2e_payload() -> dict[str, object]:
    workflow_run_ids = [
        "run-auto",
        "run-retry",
        "run-recovered",
        "run-web-referral",
    ]
    scenarios = [
        {
            "name": "automatic_completion",
            "status": "passed",
            "workflow_run_id": "run-auto",
        },
        {
            "name": "retry_completion",
            "status": "passed",
            "workflow_run_id": "run-retry",
        },
        {
            "name": "crash_resume_completion",
            "status": "passed",
            "workflow_run_id": "run-recovered",
        },
        {
            "name": "web_referral_pending",
            "status": "passed",
            "workflow_run_id": "run-web-referral",
            "machine_recommendation": "REFER_TO_HUMAN_UNDERWRITER",
            "review_status": "pending",
        },
        {
            "name": "web_review_missing_identity_rejected",
            "status": "passed",
            "workflow_run_id": "run-web-referral",
            "http_status": 403,
        },
        {
            "name": "web_review_spoofed_identity_rejected",
            "status": "passed",
            "workflow_run_id": "run-web-referral",
            "http_status": 403,
        },
    ]
    return {
        "generated_at": TIMESTAMP,
        "started_at": TIMESTAMP,
        "status": "passed",
        "playwright_status": "passed",
        "workflow_run_ids": workflow_run_ids,
        "scenarios": scenarios,
    }


def teams_native_payload() -> dict[str, object]:
    return {
        "generated_at": TIMESTAMP,
        "status": "passed",
        "workflow_run_ids": ["run-teams-approved", "run-teams-declined"],
        "conversation_hashes": ["a" * 64],
        "scenarios": [
            {
                "name": "teams_activity_card_delivery",
                "status": "passed",
                "workflow_run_id": "run-teams-approved",
                "conversation_hash": "a" * 64,
                "card_action_count": 2,
            },
            {
                "name": "teams_approved",
                "status": "passed",
                "workflow_run_id": "run-teams-approved",
                "conversation_hash": "a" * 64,
                "reviewer_outcome": "APPROVED",
                "reviewer_type": "human",
            },
            {
                "name": "teams_declined",
                "status": "passed",
                "workflow_run_id": "run-teams-declined",
                "conversation_hash": "a" * 64,
                "reviewer_outcome": "DECLINED",
                "reviewer_type": "human",
            },
        ],
    }


def source_documents() -> dict[str, dict[str, object]]:
    hosted_e2e = hosted_e2e_payload()
    teams_native = teams_native_payload()
    workflow_run_ids = [
        *hosted_e2e["workflow_run_ids"],
        *teams_native["workflow_run_ids"],
    ]
    assert isinstance(workflow_run_ids, list)
    count = len(workflow_run_ids)
    return {
        "hosted-e2e-evidence.json": hosted_e2e,
        "teams-native-acceptance.json": teams_native,
        "hosted-smoke-evidence.json": {
            "generated_at": TIMESTAMP,
            "status": "passed",
            "workflow_run_id": "run-smoke",
            "conversation_ids": ["conv-smoke"],
        },
        "foundry-trace-eval.json": {
            "generated_at": TIMESTAMP,
            "status": "completed",
            "trace_evidence_generated_at": TIMESTAMP,
            "conversation_ids": ["conv-smoke"],
            "result_counts": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
            },
            "criterion_result_counts": {
                "total": 2,
                "passed": 2,
                "failed": 0,
                "errored": 0,
                "skipped": 0,
            },
        },
        "appinsights-evidence.json": {
            "generated_at": TIMESTAMP,
            "status": "passed",
            "workflow_run_ids": workflow_run_ids,
            "matched_count": count,
            "request_run_count": count,
            "entrypoint_run_count": count,
            "hosted_invocation_run_count": count,
            "workflow_span_run_count": count,
            "exception_rows": 0,
        },
    }


class AggregateReleaseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (ROOT / "backend" / ".tmp").mkdir(parents=True, exist_ok=True)

    def run_aggregate(
        self,
        evidence_dir: Path,
        verification: dict[str, object],
        *,
        overrides: dict[str, dict[str, object]] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "foundry-verify.json").write_text(json.dumps(verification))
        documents = source_documents()
        documents.update(overrides or {})
        for name, document in documents.items():
            (evidence_dir / name).write_text(json.dumps(document))
        environment = os.environ.copy()
        environment.pop("RELEASE_ID", None)
        environment.pop("RELEASE_WINDOW_START", None)
        environment.pop("FOUNDRY_RELEASE_STARTED_AT", None)
        environment.update(
            {
                "DATABASE_URL": RUNTIME_URL,
                "RUNTIME_DATABASE_URL": RUNTIME_URL,
                "AZURE_SUBSCRIPTION_ID": "11111111-1111-4111-8111-111111111111",
                "AZURE_RESOURCE_GROUP": "rg-fixture-underwriting",
                "AZURE_LOCATION": "regionone",
                "FOUNDRY_RELEASE_EVIDENCE_DIR": str(evidence_dir),
                "FOUNDRY_RELEASE_EVIDENCE_FILE": str(evidence_dir / "release-evidence.json"),
            }
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_real_verification_shape_allows_placeholder_metadata(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
        ) as directory:
            evidence_dir = Path(directory)
            result = self.run_aggregate(evidence_dir, verification_payload())
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((evidence_dir / "release-evidence.json").read_text())
            verification = payload["evidence"]["verification"]
            self.assertTrue(
                verification["runtime_secret_connection"]["database_url_metadata_is_placeholder"]
            )
            self.assertTrue(verification["hosted_agent"]["database_url_placeholder"])

    def test_rejects_actual_runtime_url_and_password_values(self) -> None:
        for leaked_value in (RUNTIME_URL, RUNTIME_PASSWORD):
            with self.subTest(leaked_value="runtime_url" if "://" in leaked_value else "password"):
                with tempfile.TemporaryDirectory(
                    dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
                ) as directory:
                    verification = verification_payload()
                    verification["diagnostic_value"] = leaked_value
                    result = self.run_aggregate(Path(directory), verification)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("forbidden", result.stderr)
                    self.assertFalse((Path(directory) / "release-evidence.json").exists())

    def test_rejects_native_teams_evidence_without_decline(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
        ) as directory:
            teams_native = teams_native_payload()
            scenarios = teams_native["scenarios"]
            assert isinstance(scenarios, list)
            teams_native["scenarios"] = [
                scenario for scenario in scenarios if scenario["name"] != "teams_declined"
            ]
            result = self.run_aggregate(
                Path(directory),
                verification_payload(),
                overrides={"teams-native-acceptance.json": teams_native},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required scenarios", result.stderr)

    def test_rejects_web_review_evidence_that_trusts_spoofable_headers(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
        ) as directory:
            hosted_e2e = hosted_e2e_payload()
            scenarios = hosted_e2e["scenarios"]
            assert isinstance(scenarios, list)
            scenario = next(
                item for item in scenarios if item["name"] == "web_review_spoofed_identity_rejected"
            )
            scenario["http_status"] = 200
            result = self.run_aggregate(
                Path(directory),
                verification_payload(),
                overrides={"hosted-e2e-evidence.json": hosted_e2e},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Teams-only production review", result.stderr)

    def test_rejects_skipped_evaluation_results_and_telemetry_id_drift(self) -> None:
        cases = {
            "skipped": {
                "foundry-trace-eval.json": {
                    **source_documents()["foundry-trace-eval.json"],
                    "result_counts": {
                        "total": 1,
                        "passed": 0,
                        "failed": 0,
                        "errored": 0,
                        "skipped": 1,
                    },
                }
            },
            "ids": {
                "appinsights-evidence.json": {
                    **source_documents()["appinsights-evidence.json"],
                    "workflow_run_ids": ["run-other"],
                }
            },
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(
                    dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
                ) as directory:
                    result = self.run_aggregate(
                        Path(directory),
                        verification_payload(),
                        overrides=overrides,
                    )
                    self.assertNotEqual(result.returncode, 0)

    def test_rejects_private_application_fields_in_evidence(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
        ) as directory:
            hosted_e2e = hosted_e2e_payload()
            hosted_e2e["applicant_name"] = "Private Applicant"
            result = self.run_aggregate(
                Path(directory),
                verification_payload(),
                overrides={"hosted-e2e-evidence.json": hosted_e2e},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Private hosted evidence field is forbidden", result.stderr)

    def test_rejects_verification_without_activity_protocol(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "backend" / ".tmp", prefix="release-evidence-test-"
        ) as directory:
            verification = verification_payload()
            hosted = verification["hosted_agent"]
            assert isinstance(hosted, dict)
            hosted["protocols"] = [{"protocol": "responses", "version": "2.0.0"}]
            result = self.run_aggregate(Path(directory), verification)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Responses and Activity 2.0.0", result.stderr)


if __name__ == "__main__":
    unittest.main()
