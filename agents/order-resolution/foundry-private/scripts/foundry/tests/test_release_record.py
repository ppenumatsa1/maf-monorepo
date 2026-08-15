from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "scripts" / "foundry" / "release_record.py"
MIGRATION_TOOL = ROOT / "scripts" / "foundry" / "migrate_release_history.py"
SCHEMA = ROOT / ".artifacts" / "releases" / "_contract" / "release-v1.schema.json"
SOURCE_SCHEMA = Path(
    "/home/praveen/.copilot/session-state/888383de-fd62-45b9-b652-651a5f017674/"
    "files/release-v1.schema.json"
)
SCRATCH = ROOT / "scripts" / "foundry" / "tests" / ".scratch-release-record"
GATES = (
    "private_app_preflight",
    "postgres_readiness",
    "app_deployment",
    "image_verification",
    "hosted_agent_deployment",
    "hitl_e2e",
    "telemetry",
    "foundry_evaluation",
    "release_evidence",
)
TIMING_STAGES = (
    "app_only",
    "hosted_image_package",
    "aca_deploy",
    "verification_smoke",
    "hosted_agent_activation",
    "hitl_e2e",
    "telemetry",
    "evaluation",
    "final_evidence",
)


class ReleaseRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)
        SCRATCH.mkdir()
        self.profile = SCRATCH / "foundry-private.env"
        self.profile.write_text("DEPLOYMENT_LANE=foundry-private\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    def run_tool(
        self, *arguments: str, expected: int = 0
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["python3", str(TOOL), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(expected, result.returncode, result.stderr)
        return result

    def init(self, release_id: str) -> Path:
        result = self.run_tool(
            "init",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--profile",
            str(self.profile),
            "--repository",
            "local:test",
            "--commit",
            "0123456789abcdef",
            "--environment",
            "private-test",
            "--subscription-id",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "test-rg",
            "--location",
            "eastus2",
            "--executor",
            "unit-test",
        )
        return Path(result.stdout.strip())

    def mark_all_gates(self, release_id: str, artifact: str) -> None:
        for gate in GATES:
            self.run_tool(
                "gate",
                "--project-root",
                str(SCRATCH),
                "--release-id",
                release_id,
                "--gate",
                gate,
                "--status",
                "succeeded",
                "--artifact",
                artifact,
            )

    def time_stage(
        self,
        release_id: str,
        stage: str,
        started_at: str,
        ended_at: str,
        status: str = "succeeded",
    ) -> None:
        self.run_tool(
            "timing-start",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--stage",
            stage,
            "--at",
            started_at,
        )
        self.run_tool(
            "timing-end",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--stage",
            stage,
            "--status",
            status,
            "--at",
            ended_at,
        )

    def mark_all_timings(self, release_id: str) -> None:
        timings = {
            "app_only": ("2026-08-15T20:00:00.000Z", "2026-08-15T20:00:09.000Z"),
            "hosted_image_package": (
                "2026-08-15T20:00:00.100Z",
                "2026-08-15T20:00:05.100Z",
            ),
            "aca_deploy": ("2026-08-15T20:00:00.200Z", "2026-08-15T20:00:04.200Z"),
            "verification_smoke": (
                "2026-08-15T20:00:05.100Z",
                "2026-08-15T20:00:06.100Z",
            ),
            "hosted_agent_activation": (
                "2026-08-15T20:00:06.100Z",
                "2026-08-15T20:00:09.000Z",
            ),
            "hitl_e2e": ("2026-08-15T20:00:09.000Z", "2026-08-15T20:00:11.000Z"),
            "telemetry": ("2026-08-15T20:00:11.000Z", "2026-08-15T20:00:13.000Z"),
            "evaluation": ("2026-08-15T20:00:13.000Z", "2026-08-15T20:00:15.000Z"),
            "final_evidence": (
                "2026-08-15T20:00:15.000Z",
                "2026-08-15T20:00:16.000Z",
            ),
        }
        for stage in TIMING_STAGES:
            self.time_stage(release_id, stage, *timings[stage])

    def test_contract_copy_is_byte_exact(self) -> None:
        self.assertEqual(SOURCE_SCHEMA.read_bytes(), SCHEMA.read_bytes())

    def test_init_finalize_hashes_artifact_and_rejects_duplicate_init(self) -> None:
        release_id = "release-success"
        directory = self.init(release_id)
        self.run_tool(
            "init",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--profile",
            str(self.profile),
            "--repository",
            "local:test",
            "--commit",
            "0123456789abcdef",
            "--environment",
            "private-test",
            "--subscription-id",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "test-rg",
            "--location",
            "eastus2",
            "--executor",
            "unit-test",
            expected=2,
        )
        started_at = json.loads((directory / "release.json").read_text())["started_at"]
        evidence = directory / "evidence" / "gate.json"
        evidence.write_text(
            json.dumps(
                {
                    "release_id": release_id,
                    "started_at": started_at,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": "succeeded",
                }
            ),
            encoding="utf-8",
        )
        self.mark_all_gates(release_id, "evidence/gate.json")
        self.mark_all_timings(release_id)
        self.run_tool(
            "finalize",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--status",
            "succeeded",
        )
        record = json.loads((directory / "release.json").read_text())
        self.assertEqual("succeeded", record["status"])
        self.assertEqual(
            hashlib.sha256(evidence.read_bytes()).hexdigest(),
            record["artifacts"][0]["sha256"],
        )
        timing = record["extensions"]["timing"]
        self.assertEqual(5000, timing["stages"]["hosted_image_package"]["duration_ms"])
        self.assertEqual(4000, timing["stages"]["aca_deploy"]["duration_ms"])
        self.assertEqual(13000, timing["total"]["duration_ms"])
        self.assertEqual(
            timing["stages"]["telemetry"]["ended_at"], timing["total"]["ended_at"]
        )

    def test_timing_preserves_overlap_and_failed_attempt_retry_context(self) -> None:
        release_id = "release-retry"
        directory = self.init(release_id)
        self.time_stage(
            release_id,
            "app_only",
            "2026-08-15T20:00:00.000Z",
            "2026-08-15T20:00:09.000Z",
        )
        self.time_stage(
            release_id,
            "hosted_image_package",
            "2026-08-15T20:00:00.100Z",
            "2026-08-15T20:00:05.100Z",
        )
        self.time_stage(
            release_id,
            "aca_deploy",
            "2026-08-15T20:00:00.200Z",
            "2026-08-15T20:00:01.200Z",
            "failed",
        )
        self.time_stage(
            release_id,
            "aca_deploy",
            "2026-08-15T20:00:01.300Z",
            "2026-08-15T20:00:04.300Z",
        )
        self.run_tool(
            "resolve",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            release_id,
            "--commit",
            "0123456789abcdef",
            "--profile",
            str(self.profile),
        )
        record = json.loads((directory / "release.json").read_text())
        aca = record["extensions"]["timing"]["stages"]["aca_deploy"]
        self.assertEqual(2, len(aca["attempts"]))
        self.assertEqual("failed", aca["attempts"][0]["status"])
        self.assertEqual(1000, aca["attempts"][0]["duration_ms"])
        self.assertEqual("succeeded", aca["attempts"][1]["status"])
        self.assertLess(
            datetime.fromisoformat(aca["started_at"].replace("Z", "+00:00")),
            datetime.fromisoformat(
                record["extensions"]["timing"]["stages"]["hosted_image_package"][
                    "ended_at"
                ].replace("Z", "+00:00")
            ),
        )

    def test_succeeded_finalize_rejects_unfinished_and_invalid_ordering(self) -> None:
        for release_id in ("release-unfinished", "release-ordering"):
            directory = self.init(release_id)
            started_at = json.loads((directory / "release.json").read_text())["started_at"]
            evidence = directory / "evidence" / "gate.json"
            evidence.write_text(
                json.dumps(
                    {
                        "release_id": release_id,
                        "started_at": started_at,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            self.mark_all_gates(release_id, "evidence/gate.json")
            if release_id == "release-ordering":
                self.mark_all_timings(release_id)
                record = json.loads((directory / "release.json").read_text())
                record["extensions"]["timing"]["stages"]["evaluation"]["started_at"] = (
                    "2026-08-15T20:00:12.000Z"
                )
                (directory / "release.json").write_text(json.dumps(record), encoding="utf-8")
            self.run_tool(
                "finalize",
                "--project-root",
                str(SCRATCH),
                "--release-id",
                release_id,
                "--status",
                "succeeded",
                expected=2,
            )

    def test_rejects_unsafe_stale_cross_release_and_secret_evidence(self) -> None:
        for release_id, payload in (
            (
                "release-stale",
                {
                    "release_id": "release-stale",
                    "generated_at": (
                        datetime.now(timezone.utc) - timedelta(days=1)
                    ).isoformat(),
                },
            ),
            (
                "release-cross",
                {
                    "release_id": "another-release",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            ),
            (
                "release-secret",
                {
                    "release_id": "release-secret",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "api_token": "not-allowed",
                },
            ),
        ):
            directory = self.init(release_id)
            evidence = directory / "evidence" / "gate.json"
            evidence.write_text(json.dumps(payload), encoding="utf-8")
            self.mark_all_gates(release_id, "evidence/gate.json")
            self.run_tool(
                "finalize",
                "--project-root",
                str(SCRATCH),
                "--release-id",
                release_id,
                "--status",
                "succeeded",
                expected=2,
            )

        self.run_tool(
            "gate",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            "release-secret",
            "--gate",
            "release_evidence",
            "--status",
            "succeeded",
            "--artifact",
            "../outside.json",
            expected=2,
        )

    def test_rejects_symlink_and_requires_all_gates(self) -> None:
        directory = self.init("release-symlink")
        outside = SCRATCH / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        (directory / "evidence" / "linked.json").symlink_to(outside)
        self.run_tool(
            "gate",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            "release-symlink",
            "--gate",
            "release_evidence",
            "--status",
            "succeeded",
            "--artifact",
            "evidence/linked.json",
            expected=2,
        )
        self.run_tool(
            "finalize",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            "release-symlink",
            "--status",
            "succeeded",
            expected=2,
        )

    def test_resolve_rejects_cross_profile_context(self) -> None:
        self.init("release-profile")
        other_profile = SCRATCH / "other.env"
        other_profile.write_text("DEPLOYMENT_LANE=other\n", encoding="utf-8")
        self.run_tool(
            "resolve",
            "--project-root",
            str(SCRATCH),
            "--release-id",
            "release-profile",
            "--commit",
            "0123456789abcdef",
            "--profile",
            str(other_profile),
            expected=2,
        )

    def test_migration_is_dry_run_and_requires_future_markers(self) -> None:
        result = subprocess.run(
            ["python3", str(MIGRATION_TOOL), "--project-root", str(ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )
        plan = json.loads(result.stdout)
        self.assertEqual("dry-run", plan["mode"])
        self.assertFalse(plan["copy_performed"])
        self.assertFalse(plan["delete_performed"])
        self.assertFalse(plan["future_delete_eligible"])


if __name__ == "__main__":
    unittest.main()
