from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "migrate-release-history.py"


def test_dry_run_inventories_without_copy_or_delete(tmp_path: Path) -> None:
    project = tmp_path / "azure-hosted"
    order_resolution = tmp_path / "order-resolution"
    legacy = project / ".artifacts" / "release" / "old-release"
    reports = order_resolution / "deployment-reports"
    legacy.mkdir(parents=True)
    reports.mkdir(parents=True)
    (legacy / "release.json").write_text('{"status":"succeeded"}\n', encoding="utf-8")
    report = reports / "order-resolution-azure-hosted-release-report.md"
    report.write_text("legacy report\n", encoding="utf-8")
    manifest = project / ".artifacts" / "releases" / "history" / "dry-run.json"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(project),
            "--order-resolution-root",
            str(order_resolution),
            "--manifest",
            str(manifest),
        ],
        check=True,
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"
    assert payload["copy_performed"] is False
    assert payload["delete_performed"] is False
    assert payload["deletion_eligible"] is False
    assert len(payload["entries"]) == 2
    assert (legacy / "release.json").is_file()
    assert report.is_file()


def test_apply_is_rejected_even_when_markers_exist(tmp_path: Path) -> None:
    project = tmp_path / "azure-hosted"
    order_resolution = tmp_path / "order-resolution"
    project.mkdir()
    order_resolution.mkdir()
    live = tmp_path / "live.marker"
    archive = tmp_path / "archive.marker"
    live.write_text("future-live-validation\n", encoding="utf-8")
    archive.write_text("future-durable-archive\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(project),
            "--order-resolution-root",
            str(order_resolution),
            "--live-release-marker",
            str(live),
            "--durable-archive-marker",
            str(archive),
            "--apply",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "dry-run only" in completed.stderr
