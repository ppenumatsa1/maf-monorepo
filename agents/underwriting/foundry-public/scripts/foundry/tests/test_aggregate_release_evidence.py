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


def verification_payload() -> dict[str, object]:
    return {
        "generated_at": TIMESTAMP,
        "target": {
            "subscription_id": "7df95e88-701c-4693-af77-3159f83b558d",
            "resource_group": "rg-maf-underwriting",
            "location": "eastus2",
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
            "image": "underwriting-hosted:1",
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


class AggregateReleaseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (ROOT / "backend" / ".tmp").mkdir(parents=True, exist_ok=True)

    def run_aggregate(
        self, evidence_dir: Path, verification: dict[str, object]
    ) -> subprocess.CompletedProcess[str]:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "foundry-verify.json").write_text(json.dumps(verification))
        for name in (
            "hosted-e2e-evidence.json",
            "hosted-smoke-evidence.json",
            "foundry-trace-eval.json",
            "appinsights-evidence.json",
        ):
            (evidence_dir / name).write_text(json.dumps({"generated_at": TIMESTAMP, "ok": True}))
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": RUNTIME_URL,
                "RUNTIME_DATABASE_URL": RUNTIME_URL,
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


if __name__ == "__main__":
    unittest.main()
