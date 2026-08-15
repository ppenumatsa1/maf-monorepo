#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inventory(source: Path, destination_prefix: str) -> list[dict[str, object]]:
    if not source.exists():
        return []
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"history source must be a regular directory: {source}")
    source_root = source.resolve()
    entries: list[dict[str, object]] = []
    for candidate in sorted(source.rglob("*")):
        if candidate.is_symlink():
            raise ValueError(f"history symlink rejected: {candidate}")
        if not candidate.is_file():
            continue
        resolved = candidate.resolve(strict=True)
        if source_root not in resolved.parents:
            raise ValueError(f"history traversal rejected: {candidate}")
        relative = candidate.relative_to(source).as_posix()
        entries.append(
            {
                "source": str(candidate),
                "destination": f"{destination_prefix}/{relative}",
                "sha256": digest(candidate),
                "size_bytes": candidate.stat().st_size,
                "action": "inventory_only",
            }
        )
    return entries


def write_atomic(path: Path, payload: dict[str, object]) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory legacy Order Resolution release history without copying or deleting it."
    )
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--order-resolution-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--live-release-marker", type=Path)
    parser.add_argument("--durable-archive-marker", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        print(
            "history migration error: live copying/deletion is deferred; this tool is dry-run only",
            file=sys.stderr,
        )
        return 2
    try:
        entries = inventory(
            args.project_root / ".artifacts" / "release",
            ".artifacts/releases/history/legacy-singular-release",
        )
        report_dir = args.order_resolution_root / "deployment-reports"
        if report_dir.exists():
            report_entries = []
            for report in sorted(report_dir.glob("*azure-hosted*")):
                if report.is_symlink() or not report.is_file():
                    continue
                report_entries.append(
                    {
                        "source": str(report),
                        "destination": (
                            ".artifacts/releases/history/tracked-reports/" + report.name
                        ),
                        "sha256": digest(report),
                        "size_bytes": report.stat().st_size,
                        "action": "inventory_only",
                    }
                )
            entries.extend(report_entries)
        live_marker = bool(args.live_release_marker and args.live_release_marker.is_file())
        archive_marker = bool(
            args.durable_archive_marker and args.durable_archive_marker.is_file()
        )
        manifest: dict[str, object] = {
            "contract": "maf-release-history-migration/v1",
            "mode": "dry-run",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "source_state": "legacy_pending_cutover",
            "destination_state": "prepared_not_live_validated",
            "entries": entries,
            "copy_performed": False,
            "delete_performed": False,
            "deletion_eligible": live_marker and archive_marker,
            "required_deletion_markers": {
                "live_release": live_marker,
                "durable_archive": archive_marker,
            },
        }
        if args.manifest:
            write_atomic(args.manifest, manifest)
        else:
            print(json.dumps(manifest, indent=2, sort_keys=True))
    except (OSError, ValueError) as exc:
        print(f"history migration error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
