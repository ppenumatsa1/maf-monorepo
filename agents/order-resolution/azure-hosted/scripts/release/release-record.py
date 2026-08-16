#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT = "maf-release/v1"
LANE = "order-resolution-azure-hosted"
REQUIRED_GATES = {
    "source_validation": "evidence/source-validation.json",
    "images": "evidence/images.json",
    "deployment": "evidence/deployment.json",
    "smoke": "evidence/smoke.json",
    "browser_e2e": "logs/browser-e2e.log",
    "domain_e2e": "evidence/domain-e2e.json",
    "evaluation": "evidence/evaluation.json",
    "telemetry": "evidence/telemetry.json",
    "release_evidence": "evidence/release-evidence.json",
}
TIMED_STAGES = (
    "package_build",
    "app_deployment",
    "verification",
    "smoke",
    "browser_e2e",
    "domain_e2e",
    "evaluation",
    "telemetry",
    "final_evidence",
)
FORBIDDEN_KEY = re.compile(
    r"(api[_-]?key|bearer[_-]?token|connection[_-]?string|password|secret|"
    r"database_url|runtime_database_url|access[_-]?token|client[_-]?secret)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE = [
    re.compile(r"AccountKey=", re.IGNORECASE),
    re.compile(r"SharedAccessSignature=", re.IGNORECASE),
    re.compile(r"DefaultEndpointsProtocol=", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"://[^/\s:@]+:[^@\s]+@"),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
    re.compile(r"\b(?:sk|ghp|github_pat|eyJ)[-_A-Za-z0-9.]{20,}\b"),
]


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(root: Path, *args: str, fallback: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip() or fallback
    except (OSError, subprocess.CalledProcessError):
        return fallback


def parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def parse_utc_timestamp(value: str, field: str) -> datetime:
    parsed = parse_timestamp(value, field)
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def duration_ms(started_at: datetime, ended_at: datetime) -> int:
    delta = ended_at - started_at
    if delta.total_seconds() < 0:
        raise ValueError("timing end may not predate its start")
    return (delta.days * 86_400_000) + (delta.seconds * 1000) + (delta.microseconds // 1000)


def azure_timing(record: dict[str, Any]) -> dict[str, Any]:
    extensions = record.get("extensions")
    if not isinstance(extensions, dict):
        raise ValueError("release.json extensions must be an object")
    azure = extensions.get("azure")
    if not isinstance(azure, dict):
        raise ValueError("release.json Azure extension is missing")
    stages = azure.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(TIMED_STAGES):
        raise ValueError("release.json Azure timing stages were modified")
    return azure


def validate_succeeded_timing(record: dict[str, Any]) -> None:
    azure = azure_timing(record)
    app_only_value = azure.get("app_only_started_at")
    if not isinstance(app_only_value, str):
        raise ValueError("succeeded release requires app_only_started_at")
    app_only_started_at = parse_utc_timestamp(app_only_value, "app_only_started_at")

    started: dict[str, datetime] = {}
    ended: dict[str, datetime] = {}
    for name in TIMED_STAGES:
        stage = azure["stages"][name]
        if not isinstance(stage, dict) or stage.get("status") != "succeeded":
            raise ValueError(f"succeeded release requires finished timing stage: {name}")
        started_value = stage.get("started_at")
        ended_value = stage.get("ended_at")
        recorded_duration = stage.get("duration_ms")
        if not isinstance(started_value, str) or not isinstance(ended_value, str):
            raise ValueError(f"succeeded release requires timestamps for timing stage: {name}")
        started_at = parse_utc_timestamp(started_value, f"{name}.started_at")
        ended_at = parse_utc_timestamp(ended_value, f"{name}.ended_at")
        expected_duration = duration_ms(started_at, ended_at)
        if started_at < app_only_started_at:
            raise ValueError(f"timing stage predates app_only_started_at: {name}")
        if type(recorded_duration) is not int or recorded_duration != expected_duration:
            raise ValueError(f"invalid duration for timing stage: {name}")
        started[name] = started_at
        ended[name] = ended_at

    ordering = (
        (max(ended["package_build"], ended["app_deployment"]), started["verification"], "verification"),
        (ended["verification"], started["smoke"], "smoke"),
        (ended["smoke"], started["browser_e2e"], "browser_e2e"),
        (ended["smoke"], started["domain_e2e"], "domain_e2e"),
        (
            max(ended["browser_e2e"], ended["domain_e2e"]),
            started["evaluation"],
            "evaluation",
        ),
        (ended["evaluation"], started["telemetry"], "telemetry"),
    )
    for prerequisite_end, stage_start, name in ordering:
        if stage_start < prerequisite_end:
            raise ValueError(f"invalid Azure timing order for stage: {name}")

    telemetry_succeeded_value = azure.get("telemetry_succeeded_at")
    if not isinstance(telemetry_succeeded_value, str):
        raise ValueError("succeeded release requires telemetry_succeeded_at")
    telemetry_succeeded_at = parse_utc_timestamp(
        telemetry_succeeded_value, "telemetry_succeeded_at"
    )
    if telemetry_succeeded_at != ended["telemetry"]:
        raise ValueError("telemetry_succeeded_at must match the telemetry stage end")
    if telemetry_succeeded_at < app_only_started_at:
        raise ValueError("telemetry_succeeded_at may not predate app_only_started_at")
    expected_total = duration_ms(app_only_started_at, telemetry_succeeded_at)
    if type(azure.get("benchmark_duration_ms")) is not int or azure["benchmark_duration_ms"] != expected_total:
        raise ValueError("invalid Azure benchmark_duration_ms")
    final_started_at = parse_utc_timestamp(
        azure["stages"]["final_evidence"]["started_at"], "final_evidence.started_at"
    )
    if final_started_at < telemetry_succeeded_at:
        raise ValueError("final evidence may not start before telemetry succeeds")


def scan_secret_like(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if FORBIDDEN_KEY.search(str(key)):
                raise ValueError(f"secret-like key rejected at {location}.{key}")
            scan_secret_like(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_secret_like(child, f"{location}[{index}]")
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in FORBIDDEN_VALUE):
            raise ValueError(f"secret-like value rejected at {location}")


def checked_artifact(release_dir: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        not relative
        or pure.is_absolute()
        or ".." in pure.parts
        or pure.parts[0] not in {"evidence", "logs"}
    ):
        raise ValueError(f"unsafe artifact path: {relative}")
    candidate = release_dir.joinpath(*pure.parts)
    if candidate.is_symlink():
        raise ValueError(f"artifact symlinks are not accepted: {relative}")
    resolved_root = release_dir.resolve()
    resolved = candidate.resolve(strict=True)
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise ValueError(f"artifact escapes release directory: {relative}")
    if not resolved.is_file():
        raise ValueError(f"artifact is not a regular file: {relative}")
    return resolved


def validate_evidence(path: Path, relative: str, release_id: str, started_at: datetime) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError(f"binary artifact is not eligible for sanitized release metadata: {relative}")
    text = raw.decode("utf-8")
    if any(pattern.search(text) for pattern in FORBIDDEN_VALUE):
        raise ValueError(f"secret-like value rejected in {relative}")
    status = "succeeded"
    if path.suffix == ".json":
        payload = json.loads(text)
        scan_secret_like(payload)
        if isinstance(payload, dict):
            evidence_release_id = payload.get("release_id")
            if evidence_release_id is not None and evidence_release_id != release_id:
                raise ValueError(f"cross-release evidence rejected: {relative}")
            for field in ("generated_at", "release_started_at", "started_at"):
                value = payload.get(field)
                if isinstance(value, str) and parse_timestamp(value, f"{relative}.{field}") < started_at:
                    raise ValueError(f"stale evidence rejected: {relative}")
            evidence_status = payload.get("status")
            if evidence_status not in {None, "passed", "succeeded", "ready"}:
                status = "failed"
    return status


def init_record(args: argparse.Namespace) -> None:
    release_dir = args.release_dir.resolve()
    if release_dir.name != args.release_id or release_dir.parent.name != "releases":
        raise ValueError("release directory must be .artifacts/releases/<release-id>")
    profile_input = args.profile
    if profile_input.is_symlink():
        raise ValueError("profile must be a regular non-symlink file")
    profile = profile_input.resolve(strict=True)
    if not profile.is_file():
        raise ValueError("profile must be a regular non-symlink file")
    root = Path(args.project_root).resolve()
    record_path = release_dir / "release.json"
    if record_path.exists():
        existing = json.loads(record_path.read_text(encoding="utf-8"))
        if existing.get("release_id") != args.release_id or existing.get("started_at") != args.started_at:
            raise ValueError("existing release.json belongs to another release window")
        return
    started_at = parse_timestamp(args.started_at, "started_at")
    now = started_at.isoformat().replace("+00:00", "Z")
    record = {
        "schema_version": 1,
        "contract": CONTRACT,
        "project": "agents/order-resolution/azure-hosted",
        "lane": LANE,
        "release_id": args.release_id,
        "source": {
            "repository": git_value(root, "config", "--get", "remote.origin.url", fallback=str(root)),
            "commit": git_value(root, "rev-parse", "HEAD", fallback="0000000"),
        },
        "target": {
            "profile": profile.relative_to(root).as_posix(),
            "profile_sha256": sha256(profile),
            "environment": args.environment,
            "subscription_id": args.subscription_id,
            "resource_group": args.resource_group,
            "location": args.location,
        },
        "execution": {
            "executor": os.environ.get("GITHUB_ACTOR") or os.environ.get("USER") or "local",
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "failed_stage": None,
        "error": None,
        "gates": {
            gate: {"status": "pending", "artifact": artifact}
            for gate, artifact in REQUIRED_GATES.items()
        },
        "artifacts": [],
        "durable_artifact": None,
        "extensions": {
            "release_authority": "prepared_not_live_validated",
            "azure": {
                "app_only_started_at": None,
                "telemetry_succeeded_at": None,
                "benchmark_duration_ms": None,
                "stages": {
                    stage: {
                        "status": "pending",
                        "started_at": None,
                        "ended_at": None,
                        "duration_ms": None,
                    }
                    for stage in TIMED_STAGES
                },
            },
        },
    }
    atomic_json(record_path, record)


def update_timing(args: argparse.Namespace) -> None:
    record_path = args.release_dir.resolve() / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("status") != "running":
        raise ValueError("timing may only update a running release")
    at = parse_utc_timestamp(args.at, "at")
    normalized_at = at.isoformat().replace("+00:00", "Z")
    azure = azure_timing(record)

    if args.event == "app-only-start":
        if azure.get("app_only_started_at") is not None:
            raise ValueError("app_only_started_at is already recorded")
        azure["app_only_started_at"] = normalized_at
    else:
        stage = azure["stages"][args.stage]
        if args.event == "stage-start":
            if stage.get("status") != "pending":
                raise ValueError(f"timing stage is not pending: {args.stage}")
            app_only_value = azure.get("app_only_started_at")
            if not isinstance(app_only_value, str):
                raise ValueError("app_only_started_at must be recorded before timing stages")
            if at < parse_utc_timestamp(app_only_value, "app_only_started_at"):
                raise ValueError("timing stage may not predate app_only_started_at")
            stage.update(status="running", started_at=normalized_at)
        else:
            if stage.get("status") != "running" or not isinstance(stage.get("started_at"), str):
                raise ValueError(f"timing stage is not running: {args.stage}")
            started_at = parse_utc_timestamp(stage["started_at"], f"{args.stage}.started_at")
            stage.update(
                status=args.status,
                ended_at=normalized_at,
                duration_ms=duration_ms(started_at, at),
            )
            if args.stage == "telemetry":
                if args.status == "succeeded":
                    app_only_value = azure.get("app_only_started_at")
                    if not isinstance(app_only_value, str):
                        raise ValueError("telemetry cannot succeed before app_only_started_at")
                    app_only_started_at = parse_utc_timestamp(
                        app_only_value, "app_only_started_at"
                    )
                    azure["telemetry_succeeded_at"] = normalized_at
                    azure["benchmark_duration_ms"] = duration_ms(app_only_started_at, at)
                else:
                    azure["telemetry_succeeded_at"] = None
                    azure["benchmark_duration_ms"] = None

    record["updated_at"] = normalized_at
    scan_secret_like(record)
    atomic_json(record_path, record)


def resume_record(args: argparse.Namespace) -> None:
    record_path = args.release_dir.resolve() / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("status") != "failed":
        raise ValueError("only a failed release may be resumed")
    at = parse_utc_timestamp(args.at, "at")
    normalized_at = at.isoformat().replace("+00:00", "Z")
    azure = azure_timing(record)
    from_index = TIMED_STAGES.index(args.from_stage)
    for stage_name in TIMED_STAGES[from_index:]:
        azure["stages"][stage_name] = {
            "status": "pending",
            "started_at": None,
            "ended_at": None,
            "duration_ms": None,
        }
    if from_index <= TIMED_STAGES.index("telemetry"):
        azure["telemetry_succeeded_at"] = None
        azure["benchmark_duration_ms"] = None
    record.update(
        status="running",
        updated_at=normalized_at,
        completed_at=None,
        failed_stage=None,
        error=None,
        artifacts=[],
    )
    scan_secret_like(record)
    atomic_json(record_path, record)


def finalize_record(args: argparse.Namespace) -> None:
    release_dir = args.release_dir.resolve()
    record_path = release_dir / "release.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("contract") != CONTRACT or record.get("release_id") != release_dir.name:
        raise ValueError("release.json identity does not match its directory")
    started_at = parse_timestamp(record["started_at"], "started_at")
    declared_gates = record.get("gates")
    if not isinstance(declared_gates, dict) or set(declared_gates) != set(REQUIRED_GATES):
        raise ValueError("release.json required-gate declaration was modified")
    paths = []
    for gate, expected_artifact in REQUIRED_GATES.items():
        declaration = declared_gates.get(gate)
        if not isinstance(declaration, dict) or declaration.get("artifact") != expected_artifact:
            raise ValueError(f"release.json gate artifact was modified: {gate}")
        paths.append(expected_artifact)
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate artifact paths rejected")
    artifacts = []
    for gate, relative in REQUIRED_GATES.items():
        candidate = release_dir / relative
        if args.status == "failed" and not candidate.exists():
            continue
        path = checked_artifact(release_dir, relative)
        gate_status = validate_evidence(path, relative, record["release_id"], started_at)
        record["gates"][gate] = {"status": gate_status, "artifact": relative}
        artifacts.append(
            {"path": relative, "sha256": sha256(path), "size_bytes": path.stat().st_size}
        )
    if args.status == "succeeded" and any(
        gate["status"] != "succeeded" for gate in record["gates"].values()
    ):
        raise ValueError("succeeded release requires every declared gate to succeed")
    if args.status == "succeeded":
        validate_succeeded_timing(record)
    artifacts.sort(key=lambda item: str(item["path"]))
    now = args.completed_at
    if parse_timestamp(now, "completed_at") < started_at:
        raise ValueError("completed_at may not predate started_at")
    record["artifacts"] = artifacts
    record["status"] = args.status
    record["updated_at"] = now
    record["completed_at"] = now
    record["failed_stage"] = args.failed_stage if args.status == "failed" else None
    record["error"] = args.error if args.status == "failed" else None
    scan_secret_like(record)
    atomic_json(record_path, record)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--release-dir", type=Path, required=True)
    init.add_argument("--project-root", type=Path, required=True)
    init.add_argument("--release-id", required=True)
    init.add_argument("--started-at", required=True)
    init.add_argument("--profile", type=Path, required=True)
    init.add_argument("--environment", required=True)
    init.add_argument("--subscription-id", required=True)
    init.add_argument("--resource-group", required=True)
    init.add_argument("--location", required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--release-dir", type=Path, required=True)
    finalize.add_argument("--status", choices=("succeeded", "failed"), required=True)
    finalize.add_argument("--completed-at", required=True)
    finalize.add_argument("--failed-stage")
    finalize.add_argument("--error")
    resume = subparsers.add_parser("resume")
    resume.add_argument("--release-dir", type=Path, required=True)
    resume.add_argument("--from-stage", choices=TIMED_STAGES, required=True)
    resume.add_argument("--at", required=True)
    timing = subparsers.add_parser("timing")
    timing.add_argument("--release-dir", type=Path, required=True)
    timing.add_argument(
        "--event", choices=("app-only-start", "stage-start", "stage-end"), required=True
    )
    timing.add_argument("--stage", choices=TIMED_STAGES)
    timing.add_argument("--status", choices=("succeeded", "failed"))
    timing.add_argument("--at", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "init":
            init_record(args)
        elif args.command == "resume":
            resume_record(args)
        elif args.command == "finalize":
            if args.status == "failed":
                if not args.failed_stage or not args.error:
                    raise ValueError("failed finalization requires --failed-stage and --error")
                if len(args.error) > 240 or "\n" in args.error:
                    raise ValueError("failure summary must be a single safe line of at most 240 characters")
            finalize_record(args)
        else:
            if args.event != "app-only-start" and not args.stage:
                raise ValueError("stage timing events require --stage")
            if args.event == "stage-end" and not args.status:
                raise ValueError("stage-end requires --status")
            if args.event != "stage-end" and args.status:
                raise ValueError("--status is only valid for stage-end")
            update_timing(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"release record error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
