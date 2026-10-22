from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"

SHARED_RUNTIME = {
    "fastapi": "0.156.3",
    "uvicorn[standard]": "0.54.0",
    "pydantic": "2.14.1",
    "python-dotenv": "1.2.4",
    "httpx": "0.28.1",
    "aiohttp": "3.14.5",
    "azure-monitor-opentelemetry": "1.8.11",
    "psycopg[binary]": "3.3.6",
    "psycopg-pool": "3.3.3",
    "agent-framework-core": "1.22.0",
    "agent-framework-orchestrations": "1.3.2",
    "agent-framework-foundry": "1.15.0",
    "azure-identity": "1.26.0",
}
EXCLUDED = (
    "azure-ai-agentserver",
    "microsoft-agents",
)


def requirements(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("#", "-r ")):
            continue
        name, version = line.split("==", 1)
        parsed[name] = version
    return parsed


def locked_packages(path: Path) -> set[str]:
    return {
        match.group(1).lower()
        for match in re.finditer(
            r"^([A-Za-z0-9_.-]+)==[^\\\s]+(?:\s+\\)?$",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    }


def main() -> int:
    runtime = requirements(BACKEND / "requirements.txt")
    dev = requirements(BACKEND / "requirements-dev.txt")
    assert {name: runtime[name] for name in SHARED_RUNTIME} == SHARED_RUNTIME
    assert runtime["opentelemetry-exporter-otlp-proto-http"] == "1.45.1"
    assert dev["azure-ai-projects"] == "2.7.0"
    assert dev["pyyaml"] == "6.0.3"
    assert dev["pytest"] == "9.1.1"
    assert dev["pytest-asyncio"] == "1.4.0"
    assert dev["pytest-cov"] == "7.1.0"
    assert dev["ruff"] == "0.17.1"
    assert dev["black"] == "26.10.1"

    runtime_lock = BACKEND / "requirements.lock"
    dev_lock = BACKEND / "requirements-dev.lock"
    for lock in (runtime_lock, dev_lock):
        text = lock.read_text(encoding="utf-8")
        assert "--python-version 3.13" in text.splitlines()[1]
        assert "--generate-hashes" in text.splitlines()[1]
        assert "--hash=sha256:" in text
        assert not any(excluded in text for excluded in EXCLUDED)
    assert "azure-ai-projects" in locked_packages(dev_lock)

    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        "ARG BACKEND_PLATFORM=linux/amd64",
        "python:3.13-slim",
        "PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple",
        "--platform manylinux2014_x86_64",
        "--python-version 3.13",
        "--abi cp313",
        "--no-index --find-links=/wheels",
        "--require-hashes -r requirements.lock",
    ):
        assert required in dockerfile

    builder = (ROOT / "scripts/release/build_python_wheelhouse.sh").read_text(
        encoding="utf-8"
    )
    for required in (
        'INDEX_URL="https://packagefeedproxy.microsoft.io/pypi/simple"',
        'EXTRA_INDEX_URL="https://pypi.org/simple"',
        "--platform manylinux2014_x86_64",
        "--python-version 3.13",
        "--implementation cp",
        "--abi cp313",
        "--require-hashes",
        "validate_python_wheelhouse.py",
    ):
        assert required in builder

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("up", "docker-test", "build-release-images", "release-app"):
        assert re.search(rf"^{target}:.*python-wheelhouse", makefile, re.MULTILINE)

    fixture_root = BACKEND / ".lock-build/wheelhouse-contract-test"
    wheelhouse = fixture_root / "wheels"
    lock_file = fixture_root / "requirements.lock"
    wheel = wheelhouse / "fixture-1.0-py3-none-any.whl"
    shutil.rmtree(fixture_root, ignore_errors=True)
    wheelhouse.mkdir(parents=True)
    try:
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                "fixture-1.0.dist-info/WHEEL",
                "Wheel-Version: 1.0\nGenerator: contract-test\n"
                "Root-Is-Purelib: true\nTag: py3-none-any\n",
            )
            archive.writestr(
                "fixture-1.0.dist-info/METADATA",
                "Metadata-Version: 2.1\nName: fixture\nVersion: 1.0\n",
            )
            archive.writestr("fixture-1.0.dist-info/RECORD", "")
        wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
        lock_file.write_text(
            "# generated contract fixture\n"
            f"fixture==1.0 \\\n    --hash=sha256:{wheel_hash}\n",
            encoding="utf-8",
        )
        validator = ROOT / "scripts/release/validate_python_wheelhouse.py"
        command = [
            sys.executable,
            str(validator),
            str(wheelhouse),
            str(lock_file),
        ]
        subprocess.run(
            [
                *command,
                "--write-contract",
                "--contract-hash",
                "0" * 64,
                "--index-url",
                "https://packagefeedproxy.microsoft.io/pypi/simple",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(command, check=True, capture_output=True, text=True)
    finally:
        shutil.rmtree(fixture_root, ignore_errors=True)

    print("Azure-hosted Python wheelhouse delivery contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
