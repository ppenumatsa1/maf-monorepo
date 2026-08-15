from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "release" / "release-record.py"
SCHEMA = ROOT / ".artifacts" / "releases" / "_contract" / "release-v1.schema.json"
STARTED = "2026-08-15T17:00:00Z"
COMPLETED = "2026-08-15T17:10:00Z"
TIMING = {
    "package_build": ("2026-08-15T17:01:00.100Z", "2026-08-15T17:02:00Z"),
    "app_deployment": ("2026-08-15T17:01:00.200Z", "2026-08-15T17:04:00Z"),
    "verification": ("2026-08-15T17:04:00Z", "2026-08-15T17:05:00Z"),
    "smoke": ("2026-08-15T17:05:00Z", "2026-08-15T17:05:30Z"),
    "browser_e2e": ("2026-08-15T17:05:30Z", "2026-08-15T17:06:00Z"),
    "domain_e2e": ("2026-08-15T17:06:00Z", "2026-08-15T17:06:30Z"),
    "evaluation": ("2026-08-15T17:06:30Z", "2026-08-15T17:08:00Z"),
    "telemetry": ("2026-08-15T17:08:00Z", "2026-08-15T17:09:00Z"),
    "final_evidence": ("2026-08-15T17:09:05Z", "2026-08-15T17:09:06Z"),
}


def initialize(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    release_dir = repository / ".artifacts" / "releases" / "release-001"
    profile = repository / "agents" / "order-resolution" / "deployment" / "profiles" / "azure-hosted.env"
    profile.parent.mkdir(parents=True)
    profile.write_text("CONTRACT_VERSION=1\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "init",
            "--release-dir",
            str(release_dir),
            "--project-root",
            str(repository),
            "--release-id",
            "release-001",
            "--started-at",
            STARTED,
            "--profile",
            str(profile),
            "--environment",
            "maf-ora-azure",
            "--subscription-id",
            "7df95e88-701c-4693-af77-3159f83b558d",
            "--resource-group",
            "rg-maf-ora-azure",
            "--location",
            "northcentralus",
        ],
        check=True,
    )
    return release_dir


def populate_required(release_dir: Path) -> None:
    record = json.loads((release_dir / "release.json").read_text(encoding="utf-8"))
    for gate in record["gates"].values():
        path = release_dir / gate["artifact"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            path.write_text(
                json.dumps(
                    {
                        "release_id": "release-001",
                        "generated_at": "2026-08-15T17:05:00Z",
                        "status": "passed",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            path.write_text("browser e2e passed\n", encoding="utf-8")


def timing(
    release_dir: Path,
    event: str,
    at: str,
    *,
    stage: str | None = None,
    status: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "timing",
        "--release-dir",
        str(release_dir),
        "--event",
        event,
        "--at",
        at,
    ]
    if stage:
        command.extend(("--stage", stage))
    if status:
        command.extend(("--status", status))
    return subprocess.run(command, capture_output=True, text=True)


def populate_timing(release_dir: Path) -> None:
    assert timing(
        release_dir, "app-only-start", "2026-08-15T17:01:00Z"
    ).returncode == 0
    for stage, (started_at, ended_at) in TIMING.items():
        assert timing(release_dir, "stage-start", started_at, stage=stage).returncode == 0
        assert (
            timing(
                release_dir,
                "stage-end",
                ended_at,
                stage=stage,
                status="succeeded",
            ).returncode
            == 0
        )


def finalize(release_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "finalize",
            "--release-dir",
            str(release_dir),
            "--status",
            "succeeded",
            "--completed-at",
            COMPLETED,
        ],
        capture_output=True,
        text=True,
    )


def test_atomic_init_and_finalize_match_common_schema(tmp_path: Path) -> None:
    release_dir = initialize(tmp_path)
    initial = json.loads((release_dir / "release.json").read_text(encoding="utf-8"))
    assert initial["status"] == "running"
    assert initial["extensions"]["release_authority"] == "prepared_not_live_validated"
    populate_required(release_dir)
    populate_timing(release_dir)

    completed = finalize(release_dir)
    assert completed.returncode == 0, completed.stderr
    final = json.loads((release_dir / "release.json").read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(final)
    assert final["status"] == "succeeded"
    assert len(final["artifacts"]) == len(final["gates"])
    assert all(len(item["sha256"]) == 64 for item in final["artifacts"])
    azure = final["extensions"]["azure"]
    assert azure["stages"]["package_build"]["duration_ms"] == 59_900
    assert azure["stages"]["app_deployment"]["duration_ms"] == 179_800
    assert azure["telemetry_succeeded_at"] == "2026-08-15T17:09:00Z"
    assert azure["benchmark_duration_ms"] == 480_000


@pytest.mark.parametrize(
    ("artifact", "payload", "message"),
    [
        (
            "evidence/deployment.json",
            {"release_id": "release-999", "generated_at": "2026-08-15T17:05:00Z", "status": "passed"},
            "cross-release",
        ),
        (
            "evidence/deployment.json",
            {"release_id": "release-001", "generated_at": "2026-08-15T16:59:00Z", "status": "passed"},
            "stale evidence",
        ),
        (
            "evidence/deployment.json",
            {
                "release_id": "release-001",
                "generated_at": "2026-08-15T17:05:00Z",
                "status": "passed",
                "api_key": "not-allowed",
            },
            "secret-like",
        ),
    ],
)
def test_finalize_rejects_invalid_evidence(
    tmp_path: Path, artifact: str, payload: dict[str, str], message: str
) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    populate_timing(release_dir)
    (release_dir / artifact).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert message in completed.stderr
    assert json.loads((release_dir / "release.json").read_text(encoding="utf-8"))["status"] == "running"


def test_finalize_rejects_artifact_symlink(tmp_path: Path) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    populate_timing(release_dir)
    artifact = release_dir / "evidence" / "deployment.json"
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    artifact.unlink()
    artifact.symlink_to(outside)

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert "symlinks are not accepted" in completed.stderr


def test_failed_finalize_records_safe_summary_without_all_gates(tmp_path: Path) -> None:
    release_dir = initialize(tmp_path)
    assert timing(
        release_dir, "app-only-start", "2026-08-15T17:01:00Z"
    ).returncode == 0
    assert timing(
        release_dir,
        "stage-start",
        "2026-08-15T17:01:00.100Z",
        stage="package_build",
    ).returncode == 0
    assert timing(
        release_dir,
        "stage-end",
        "2026-08-15T17:01:01.101Z",
        stage="package_build",
        status="failed",
    ).returncode == 0
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "finalize",
            "--release-dir",
            str(release_dir),
            "--status",
            "failed",
            "--completed-at",
            COMPLETED,
            "--failed-stage",
            "smoke",
            "--error",
            "Release validation stage failed.",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    record = json.loads((release_dir / "release.json").read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert record["failed_stage"] == "smoke"
    assert record["artifacts"] == []
    assert record["extensions"]["azure"]["stages"]["package_build"] == {
        "status": "failed",
        "started_at": "2026-08-15T17:01:00.100000Z",
        "ended_at": "2026-08-15T17:01:01.101000Z",
        "duration_ms": 1001,
    }


def test_finalize_rejects_modified_gate_declaration(tmp_path: Path) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    populate_timing(release_dir)
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["gates"]["images"]["artifact"] = "evidence/deployment.json"
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert "gate artifact was modified" in completed.stderr


def test_succeeded_finalize_rejects_unfinished_timing(tmp_path: Path) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    assert timing(
        release_dir, "app-only-start", "2026-08-15T17:01:00Z"
    ).returncode == 0

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert "finished timing stage" in completed.stderr


def test_timing_rejects_end_before_start_and_telemetry_before_app_only(
    tmp_path: Path,
) -> None:
    release_dir = initialize(tmp_path)
    telemetry = timing(
        release_dir,
        "stage-start",
        "2026-08-15T17:00:01Z",
        stage="telemetry",
    )
    assert telemetry.returncode == 1
    assert "app_only_started_at" in telemetry.stderr

    assert timing(
        release_dir, "app-only-start", "2026-08-15T17:01:00Z"
    ).returncode == 0
    assert timing(
        release_dir,
        "stage-start",
        "2026-08-15T17:02:00Z",
        stage="smoke",
    ).returncode == 0
    ended = timing(
        release_dir,
        "stage-end",
        "2026-08-15T17:01:59.999Z",
        stage="smoke",
        status="failed",
    )
    assert ended.returncode == 1
    assert "may not predate" in ended.stderr


def test_succeeded_finalize_rejects_final_evidence_before_telemetry(
    tmp_path: Path,
) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    populate_timing(release_dir)
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["extensions"]["azure"]["stages"]["final_evidence"].update(
        started_at="2026-08-15T17:08:59Z",
        ended_at="2026-08-15T17:08:59.500Z",
        duration_ms=500,
    )
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert "final evidence may not start before telemetry" in completed.stderr


def test_succeeded_finalize_rejects_telemetry_before_evaluation(
    tmp_path: Path,
) -> None:
    release_dir = initialize(tmp_path)
    populate_required(release_dir)
    populate_timing(release_dir)
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["extensions"]["azure"]["stages"]["telemetry"].update(
        started_at="2026-08-15T17:07:59Z",
        duration_ms=61_000,
    )
    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    completed = finalize(release_dir)

    assert completed.returncode == 1
    assert "invalid Azure timing order for stage: telemetry" in completed.stderr
