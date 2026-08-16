#!/usr/bin/env python3
"""Create and finalize strict lane-local release records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

LANE = "order-resolution-foundry-private"
CONTRACT = "maf-release/v1"
REQUIRED_GATES = (
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
REQUIRED_TIMING_STAGES = (
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
MAX_APP_TO_TELEMETRY_MS = 15 * 60 * 1000
TIMING_PREDECESSORS = {
    "hosted_image_package": ("app_only",),
    "aca_deploy": ("app_only",),
    "verification_smoke": ("hosted_image_package", "aca_deploy"),
    "hosted_agent_activation": ("verification_smoke",),
    "hitl_e2e": ("app_only",),
    "telemetry": ("hitl_e2e",),
    "evaluation": ("telemetry",),
    "final_evidence": ("evaluation", "telemetry"),
}
SECRET_KEY = re.compile(
    r"(?:^|_)(?:password|passwd|secret|token|api_key|connection_string|database_url|private_key)(?:$|_)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"https?://[^/@\s]+:[^@\s]+@|"
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^/\s:@]+:[^@\s]+@|"
    r"(?:AccountKey|SharedAccessKey|client_secret)\s*=\s*[^;\s]+|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
    re.IGNORECASE,
)
SAFE_ERROR = re.compile(r"^[A-Za-z0-9 .,;:_()/+-]{1,300}$")


class ReleaseError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def timing_time(value: str | None) -> tuple[str, datetime]:
    timestamp = value or utc_now_ms()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", timestamp):
        raise ReleaseError("Timing timestamps must be UTC with millisecond precision")
    try:
        parsed = parse_time(timestamp)
    except ValueError as exc:
        raise ReleaseError("Invalid timing timestamp") from exc
    return timestamp, parsed


def duration_ms(started_at: str, ended_at: str) -> int:
    duration = (parse_time(ended_at) - parse_time(started_at)).total_seconds() * 1000
    if duration < 0:
        raise ReleaseError("Timing stage ended before it started")
    return round(duration)


def empty_timing_stage() -> dict[str, Any]:
    return {
        "status": "pending",
        "started_at": None,
        "ended_at": None,
        "duration_ms": None,
        "attempts": [],
    }


def timing_extension() -> dict[str, Any]:
    return {
        "clock": "UTC",
        "unit": "milliseconds",
        "required_stages": list(REQUIRED_TIMING_STAGES),
        "stages": {name: empty_timing_stage() for name in REQUIRED_TIMING_STAGES},
        "total": {"started_at": None, "ended_at": None, "duration_ms": None},
    }


def get_timing(record: dict[str, Any]) -> dict[str, Any]:
    timing = record.get("extensions", {}).get("timing")
    if not isinstance(timing, dict):
        raise ReleaseError("Release timing extension is missing")
    stages = timing.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(REQUIRED_TIMING_STAGES):
        raise ReleaseError("Release timing stages do not satisfy the private lane contract")
    return timing


def validate_succeeded_timing(record: dict[str, Any]) -> None:
    timing = get_timing(record)
    stages = timing["stages"]
    for name in REQUIRED_TIMING_STAGES:
        stage = stages[name]
        if (
            stage.get("status") != "succeeded"
            or not stage.get("started_at")
            or not stage.get("ended_at")
            or stage.get("duration_ms") is None
        ):
            raise ReleaseError(f"Required timing stage is unfinished: {name}")
        expected = duration_ms(stage["started_at"], stage["ended_at"])
        if stage["duration_ms"] != expected:
            raise ReleaseError(f"Invalid duration for timing stage: {name}")

    app_start = parse_time(stages["app_only"]["started_at"])
    app_end = parse_time(stages["app_only"]["ended_at"])
    for name in ("hosted_image_package", "aca_deploy", "verification_smoke", "hosted_agent_activation"):
        stage_start = parse_time(stages[name]["started_at"])
        stage_end = parse_time(stages[name]["ended_at"])
        if stage_start < app_start or stage_end > app_end:
            raise ReleaseError(f"Timing stage falls outside app_only: {name}")

    for name, predecessors in TIMING_PREDECESSORS.items():
        stage_start = parse_time(stages[name]["started_at"])
        if name in {"hosted_image_package", "aca_deploy"}:
            if stage_start < app_start:
                raise ReleaseError(f"Invalid timing order for stage: {name}")
            continue
        for predecessor in predecessors:
            if stage_start < parse_time(stages[predecessor]["ended_at"]):
                raise ReleaseError(
                    f"Timing stage {name} started before {predecessor} completed"
                )

    total = timing.get("total", {})
    expected_start = stages["app_only"]["started_at"]
    expected_end = stages["telemetry"]["ended_at"]
    expected_duration = duration_ms(expected_start, expected_end)
    if expected_duration > MAX_APP_TO_TELEMETRY_MS:
        raise ReleaseError("Private app-only to telemetry exceeded the 15-minute release budget")
    if total != {
        "started_at": expected_start,
        "ended_at": expected_end,
        "duration_ms": expected_duration,
    }:
        raise ReleaseError("Release total timing is invalid")


def atomic_json(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.new")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    try:
        with os.fdopen(os.open(temporary, flags, 0o600), "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise ReleaseError(f"Release record already exists: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"Cannot read release JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"Expected a JSON object: {path}")
    return value


def validate_release_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", value):
        raise ReleaseError("Release ID does not satisfy the v1 contract")
    return value


def release_root(project_root: Path) -> Path:
    return project_root.resolve() / ".artifacts" / "releases"


def release_dir(project_root: Path, release_id: str) -> Path:
    root = release_root(project_root)
    candidate = root / validate_release_id(release_id)
    if candidate.parent != root:
        raise ReleaseError("Release path escaped the releases directory")
    return candidate


def relative_artifact_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0] not in {"evidence", "logs"}:
        raise ReleaseError(f"Unsafe artifact path: {value}")
    return path


def assert_below_release(directory: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise ReleaseError(f"Symlink artifacts are forbidden: {candidate}")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(directory.resolve(strict=True))
    except ValueError as exc:
        raise ReleaseError(f"Artifact escaped release directory: {candidate}") from exc
    return resolved


def scan_secret_like(value: Any, location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY.search(str(key)):
                raise ReleaseError(f"Secret-like key rejected at {location}.{key}")
            scan_secret_like(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_secret_like(child, f"{location}[{index}]")
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        raise ReleaseError(f"Secret-like value rejected at {location}")


def validate_evidence_json(
    value: Any, *, release_id: str, started_at: datetime, location: str = "$"
) -> None:
    scan_secret_like(value, location)
    if isinstance(value, dict):
        embedded_id = value.get("release_id")
        if embedded_id is not None and embedded_id != release_id:
            raise ReleaseError(f"Cross-release evidence rejected at {location}.release_id")
        for key, child in value.items():
            if key.endswith("_at") and isinstance(child, str):
                try:
                    timestamp = parse_time(child)
                except ValueError as exc:
                    raise ReleaseError(f"Invalid evidence timestamp at {location}.{key}") from exc
                if timestamp < started_at:
                    raise ReleaseError(f"Stale evidence timestamp rejected at {location}.{key}")
            validate_evidence_json(
                child, release_id=release_id, started_at=started_at, location=f"{location}.{key}"
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_evidence_json(
                child,
                release_id=release_id,
                started_at=started_at,
                location=f"{location}[{index}]",
            )


def collect_artifacts(directory: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    prior_paths = [item.get("path") for item in record.get("artifacts", [])]
    if len(prior_paths) != len(set(prior_paths)):
        raise ReleaseError("Duplicate artifact paths found in the release record")
    referenced: set[str] = set()
    for gate in record["gates"].values():
        artifact = gate.get("artifact")
        if artifact is not None:
            referenced.add(relative_artifact_path(artifact).as_posix())
    seen: set[str] = set()
    artifacts: list[dict[str, Any]] = []
    started_at = parse_time(record["started_at"])

    for section in ("evidence", "logs"):
        section_dir = directory / section
        if not section_dir.exists():
            continue
        if section_dir.is_symlink():
            raise ReleaseError(f"Symlink artifact directories are forbidden: {section_dir}")
        for path in sorted(section_dir.rglob("*")):
            if path.is_dir():
                continue
            resolved = assert_below_release(directory, path)
            relative = resolved.relative_to(directory.resolve()).as_posix()
            relative_artifact_path(relative)
            if relative in seen:
                raise ReleaseError(f"Duplicate artifact path rejected: {relative}")
            seen.add(relative)
            data = resolved.read_bytes()
            if SECRET_VALUE.search(data.decode("utf-8", errors="ignore")):
                raise ReleaseError(f"Secret-like value rejected in {relative}")
            if resolved.suffix.lower() == ".json":
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ReleaseError(f"Invalid JSON evidence: {relative}") from exc
                validate_evidence_json(
                    payload, release_id=record["release_id"], started_at=started_at
                )
            artifacts.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data),
                }
            )

    missing = sorted(referenced - seen)
    if missing:
        raise ReleaseError(f"Referenced evidence is missing: {', '.join(missing)}")
    return artifacts


def command_init(args: argparse.Namespace) -> None:
    project_root = Path(args.project_root)
    directory = release_dir(project_root, args.release_id)
    profile = Path(args.profile).resolve(strict=True)
    commit = args.commit.lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ReleaseError("Source commit must be a 7-40 character lowercase Git SHA")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", args.subscription_id):
        raise ReleaseError("Subscription ID does not satisfy the v1 contract")
    for label, value in (
        ("repository", args.repository),
        ("environment", args.environment),
        ("resource group", args.resource_group),
        ("location", args.location),
        ("executor", args.executor),
    ):
        if not value:
            raise ReleaseError(f"{label} is required")
    scan_secret_like(args.repository, "$.source.repository")
    if directory.exists():
        raise ReleaseError(f"Release directory already exists: {directory}")

    started_at = utc_now()
    profile_hash = hashlib.sha256(profile.read_bytes()).hexdigest()
    record = {
        "schema_version": 1,
        "contract": CONTRACT,
        "project": "order-resolution",
        "lane": LANE,
        "release_id": args.release_id,
        "source": {"repository": args.repository, "commit": commit},
        "target": {
            "profile": os.path.relpath(profile, project_root.resolve()),
            "profile_sha256": profile_hash,
            "environment": args.environment,
            "subscription_id": args.subscription_id,
            "resource_group": args.resource_group,
            "location": args.location,
        },
        "execution": {"executor": args.executor, "workflow_run_id": args.workflow_run_id},
        "status": "running",
        "started_at": started_at,
        "updated_at": started_at,
        "completed_at": None,
        "failed_stage": None,
        "error": None,
        "gates": {name: {"status": "pending", "artifact": None} for name in REQUIRED_GATES},
        "artifacts": [],
        "durable_artifact": None,
        "extensions": {
            "required_gates": list(REQUIRED_GATES),
            "timing": timing_extension(),
        },
    }
    (directory / "evidence").mkdir(parents=True)
    (directory / "logs").mkdir()
    (directory / "provenance").mkdir()
    atomic_json(directory / "release.json", record, exclusive=True)
    atomic_json(
        directory / "provenance" / "source.json",
        {
            "release_id": args.release_id,
            "repository": args.repository,
            "commit": commit,
            "profile_sha256": profile_hash,
            "recorded_at": started_at,
        },
        exclusive=True,
    )
    atomic_json(
        release_root(project_root) / "_history" / "foundry-private-active.json",
        {
            "release_id": args.release_id,
            "release_record": f"{args.release_id}/release.json",
            "source_commit": commit,
            "profile_sha256": profile_hash,
            "updated_at": started_at,
        },
    )
    print(directory)


def resolve_context(project_root: Path, release_id: str | None) -> tuple[Path, dict[str, Any]]:
    if release_id is None:
        active = load_json(
            release_root(project_root) / "_history" / "foundry-private-active.json"
        )
        release_id = str(active.get("release_id", ""))
    directory = release_dir(project_root, release_id)
    root = release_root(project_root)
    if directory.is_symlink():
        raise ReleaseError("Symlink release directories are forbidden")
    try:
        directory.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise ReleaseError("Release directory is missing or escaped the releases root") from exc
    record_path = directory / "release.json"
    if record_path.is_symlink():
        raise ReleaseError("Symlink release records are forbidden")
    record = load_json(record_path)
    if record.get("release_id") != release_id or record.get("lane") != LANE:
        raise ReleaseError("Release context does not match this lane")
    return directory, record


def command_resolve(args: argparse.Namespace) -> None:
    directory, record = resolve_context(Path(args.project_root), args.release_id)
    if record["status"] != "running":
        raise ReleaseError("Evidence retry requires the same running release context")
    if args.commit and record["source"]["commit"] != args.commit.lower():
        raise ReleaseError("Active release belongs to a different source commit")
    if args.profile:
        profile_bytes = Path(args.profile).resolve(strict=True).read_bytes()
        profile_hash = hashlib.sha256(profile_bytes).hexdigest()
        if record["target"]["profile_sha256"] != profile_hash:
            raise ReleaseError("Active release belongs to a different deployment profile")
    print(directory)


def command_gate(args: argparse.Namespace) -> None:
    project_root = Path(args.project_root)
    directory, record = resolve_context(project_root, args.release_id)
    if record["status"] != "running":
        raise ReleaseError("Cannot update a finalized release")
    if args.gate not in REQUIRED_GATES:
        raise ReleaseError(f"Unknown required gate: {args.gate}")
    artifact = None
    if args.artifact:
        artifact = relative_artifact_path(args.artifact).as_posix()
        candidate = directory / artifact
        assert_below_release(directory, candidate)
    record["gates"][args.gate] = {"status": args.status, "artifact": artifact}
    record["updated_at"] = utc_now()
    atomic_json(directory / "release.json", record)


def command_timing_start(args: argparse.Namespace) -> None:
    directory, record = resolve_context(Path(args.project_root), args.release_id)
    if record["status"] != "running":
        raise ReleaseError("Cannot update timing on a finalized release")
    timing = get_timing(record)
    stage = timing["stages"][args.stage]
    attempts = stage.get("attempts")
    if not isinstance(attempts, list):
        raise ReleaseError(f"Invalid timing attempts for stage: {args.stage}")
    if attempts and attempts[-1].get("status") == "running":
        raise ReleaseError(f"Timing stage already has a running attempt: {args.stage}")
    timestamp, _ = timing_time(args.at)
    if args.stage != "app_only":
        app_stage = timing["stages"]["app_only"]
        if not app_stage.get("started_at") or parse_time(timestamp) < parse_time(
            app_stage["started_at"]
        ):
            raise ReleaseError("app_only timing must start first")
    attempts.append(
        {
            "attempt": len(attempts) + 1,
            "status": "running",
            "started_at": timestamp,
            "ended_at": None,
            "duration_ms": None,
        }
    )
    stage.update(
        {
            "status": "running",
            "started_at": timestamp,
            "ended_at": None,
            "duration_ms": None,
        }
    )
    if args.stage == "app_only" and timing["total"]["started_at"] is None:
        timing["total"]["started_at"] = timestamp
    record["updated_at"] = utc_now()
    atomic_json(directory / "release.json", record)


def command_timing_end(args: argparse.Namespace) -> None:
    directory, record = resolve_context(Path(args.project_root), args.release_id)
    if record["status"] != "running":
        raise ReleaseError("Cannot update timing on a finalized release")
    timing = get_timing(record)
    stage = timing["stages"][args.stage]
    attempts = stage.get("attempts")
    if not attempts or attempts[-1].get("status") != "running":
        raise ReleaseError(f"Timing stage has no running attempt: {args.stage}")
    timestamp, _ = timing_time(args.at)
    elapsed = duration_ms(attempts[-1]["started_at"], timestamp)
    attempts[-1].update(
        {
            "status": args.status,
            "ended_at": timestamp,
            "duration_ms": elapsed,
        }
    )
    stage.update(
        {
            "status": args.status,
            "started_at": attempts[-1]["started_at"],
            "ended_at": timestamp,
            "duration_ms": elapsed,
        }
    )
    if args.stage == "telemetry" and args.status == "succeeded":
        total_started = timing["total"].get("started_at")
        if not total_started:
            raise ReleaseError("Release total timing has no app_only start")
        timing["total"] = {
            "started_at": total_started,
            "ended_at": timestamp,
            "duration_ms": duration_ms(total_started, timestamp),
        }
    record["updated_at"] = utc_now()
    atomic_json(directory / "release.json", record)


def command_finalize(args: argparse.Namespace) -> None:
    project_root = Path(args.project_root)
    directory, record = resolve_context(project_root, args.release_id)
    if record["status"] != "running":
        raise ReleaseError("Release has already been finalized")

    if args.status == "succeeded":
        failed = [
            name
            for name in REQUIRED_GATES
            if record["gates"].get(name, {}).get("status") != "succeeded"
        ]
        if failed:
            raise ReleaseError(f"Required gates are not succeeded: {', '.join(failed)}")
        validate_succeeded_timing(record)
        record["artifacts"] = collect_artifacts(directory, record)
        record["error"] = None
        record["failed_stage"] = None
    else:
        if not args.failed_stage or not args.error or not SAFE_ERROR.fullmatch(args.error):
            raise ReleaseError("Failed releases require a short, sanitized stage and error")
        scan_secret_like(args.error)
        record["failed_stage"] = args.failed_stage[:100]
        record["error"] = args.error
        record["artifacts"] = []

    completed_at = utc_now()
    record["status"] = args.status
    record["updated_at"] = completed_at
    record["completed_at"] = completed_at
    atomic_json(directory / "release.json", record)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subparsers = root.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", required=True)
    common.add_argument("--release-id")

    init = subparsers.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--release-id", required=True, type=validate_release_id)
    init.add_argument("--profile", required=True)
    init.add_argument("--repository", required=True)
    init.add_argument("--commit", required=True)
    init.add_argument("--environment", required=True)
    init.add_argument("--subscription-id", required=True)
    init.add_argument("--resource-group", required=True)
    init.add_argument("--location", required=True)
    init.add_argument("--executor", required=True)
    init.add_argument("--workflow-run-id")
    init.set_defaults(handler=command_init)

    resolve = subparsers.add_parser("resolve", parents=[common])
    resolve.add_argument("--commit")
    resolve.add_argument("--profile")
    resolve.set_defaults(handler=command_resolve)

    gate = subparsers.add_parser("gate", parents=[common])
    gate.add_argument("--gate", required=True)
    gate.add_argument("--status", required=True, choices=("succeeded", "failed"))
    gate.add_argument("--artifact")
    gate.set_defaults(handler=command_gate)

    timing_start = subparsers.add_parser("timing-start", parents=[common])
    timing_start.add_argument("--stage", required=True, choices=REQUIRED_TIMING_STAGES)
    timing_start.add_argument("--at")
    timing_start.set_defaults(handler=command_timing_start)

    timing_end = subparsers.add_parser("timing-end", parents=[common])
    timing_end.add_argument("--stage", required=True, choices=REQUIRED_TIMING_STAGES)
    timing_end.add_argument("--status", required=True, choices=("succeeded", "failed"))
    timing_end.add_argument("--at")
    timing_end.set_defaults(handler=command_timing_end)

    finalize = subparsers.add_parser("finalize", parents=[common])
    finalize.add_argument("--status", required=True, choices=("succeeded", "failed"))
    finalize.add_argument("--failed-stage")
    finalize.add_argument("--error")
    finalize.set_defaults(handler=command_finalize)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        args.handler(args)
    except (OSError, ReleaseError) as exc:
        print(f"release-record: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
