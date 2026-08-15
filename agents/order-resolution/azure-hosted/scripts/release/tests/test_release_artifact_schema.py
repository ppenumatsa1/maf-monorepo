from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT_DIR = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    ROOT_DIR
    / "deployment"
    / "contracts"
    / "azure-hosted-release-artifact-envelope.schema.json"
)


def validate(payload: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def main() -> int:
    good_payload = {
        "schema_version": 1,
        "contract": "azure-hosted-release/v1",
        "evidence_type": "smoke",
        "artifact_type": "smoke",
        "lane": "azure-hosted",
        "status": "passed",
        "release_id": "20260815T000000Z-1234",
        "release_started_at": "2026-08-15T00:00:00Z",
        "generated_at": "2026-08-15T00:05:00Z",
        "target": {
            "azd_env_name": "maf-ora-azure",
            "subscription_id": "7df95e88-701c-4693-af77-3159f83b558d",
            "resource_group": "rg-maf-ora-azure",
            "location": "northcentralus",
            "api_url": "https://api.example.test",
        },
        "checks": [
            {
                "name": "smoke-test",
                "status": "passed",
                "log": "logs/smoke.log",
            }
        ],
        "extensions": {
            "canonical_file": "smoke.json",
            "scenario_count": 2,
        },
    }
    validate(good_payload)

    missing_evidence_type = dict(good_payload)
    missing_evidence_type.pop("evidence_type")
    try:
        validate(missing_evidence_type)
    except Exception:
        pass
    else:
        raise AssertionError("Schema accepted a payload without evidence_type.")

    forbidden_secret_key = dict(good_payload)
    forbidden_secret_key["extensions"] = {"secret": "nope"}
    try:
        validate(forbidden_secret_key)
    except Exception:
        pass
    else:
        raise AssertionError("Schema accepted a secret-like key.")

    forbidden_secret_value = dict(good_payload)
    forbidden_secret_value["extensions"] = {
        "connection": "DefaultEndpointsProtocol=https;AccountKey=abcd"
    }
    try:
        validate(forbidden_secret_value)
    except Exception:
        pass
    else:
        raise AssertionError("Schema accepted a connection-string-like value.")

    print("Release artifact envelope schema tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
