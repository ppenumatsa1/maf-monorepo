from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from release_record import (
    atomic_json_write,
    configured_sensitive_values,
    finalize_record,
    finish_release_timing,
    register_artifact,
    validate_secret_free,
)

ROOT = Path(__file__).resolve().parents[2]
release_id = os.getenv("RELEASE_ID", "").strip()
DEFAULT_RESULTS = (
    ROOT / ".artifacts" / "releases" / release_id / "evidence"
    if release_id
    else ROOT / "backend" / ".foundry" / "results"
)
RESULTS = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_DIR", DEFAULT_RESULTS))
OUTPUT = Path(os.getenv("FOUNDRY_RELEASE_EVIDENCE_FILE", RESULTS / "release-evidence.json"))
SOURCES = {
    "verification": RESULTS / "foundry-verify.json",
    "hosted_e2e": RESULTS / "hosted-e2e-evidence.json",
    "hosted_smoke": RESULTS / "hosted-smoke-evidence.json",
    "trace_evaluation": RESULTS / "foundry-trace-eval.json",
    "application_insights": RESULTS / "appinsights-evidence.json",
}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def main() -> None:
    documents: dict[str, Any] = {}
    timestamps: list[datetime] = []
    sensitive_values = configured_sensitive_values()
    for name, path in SOURCES.items():
        if not path.is_file():
            raise RuntimeError(f"Missing release evidence: {path}")
        document = json.loads(path.read_text())
        validate_secret_free(document, sensitive_values=sensitive_values)
        timestamp = document.get("generated_at") or document.get("started_at")
        if isinstance(timestamp, str) and timestamp:
            timestamps.append(parse_timestamp(timestamp))
        else:
            timestamps.append(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
        documents[name] = document

    configured_start = os.getenv("RELEASE_WINDOW_START", "").strip()
    window_start = parse_timestamp(configured_start) if configured_start else min(timestamps)
    if any(timestamp < window_start for timestamp in timestamps):
        raise RuntimeError("One or more evidence files predate RELEASE_WINDOW_START.")

    payload = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_window": {
            "start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "target": {
            "subscription_id": "7df95e88-701c-4693-af77-3159f83b558d",
            "resource_group": "rg-maf-underwriting",
            "location": "eastus2",
        },
        "evidence": documents,
    }
    validate_secret_free(payload, sensitive_values=sensitive_values)
    atomic_json_write(OUTPUT, payload)
    if release_id:
        gates = {
            "verification": "foundry-verify.json",
            "hosted_e2e": "hosted-e2e-evidence.json",
            "hosted_smoke": "hosted-smoke-evidence.json",
            "trace_evaluation": "foundry-trace-eval.json",
            "application_insights": "appinsights-evidence.json",
        }
        for gate, filename in gates.items():
            register_artifact(release_id, f"evidence/{filename}", gate)
        register_artifact(release_id, f"evidence/{OUTPUT.name}")
        finish_release_timing(release_id, "final_evidence", "succeeded")
        finalize_record(release_id, "succeeded")
    print(f"Release-window evidence written to {OUTPUT}.")


if __name__ == "__main__":
    main()
