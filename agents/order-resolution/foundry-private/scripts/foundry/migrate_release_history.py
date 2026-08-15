#!/usr/bin/env python3
"""Plan the deferred release-history migration without changing history."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    releases = root / ".artifacts" / "releases"
    singular = root / ".artifacts" / "release"
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", ".artifacts/release/**", "backend/.foundry/results/**"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    plan = {
        "mode": "dry-run",
        "source_status": "legacy_pending_cutover",
        "destination_status": "prepared_not_live_validated",
        "singular_release_path": str(singular.relative_to(root)),
        "singular_release_exists": singular.exists(),
        "tracked_history": tracked,
        "planned_destination": str(releases.relative_to(root)),
        "copy_performed": False,
        "delete_performed": False,
        "future_delete_eligible": (
            (releases / "_history" / "live-release.marker").is_file()
            and (releases / "_history" / "durable-archive.marker").is_file()
        ),
        "required_delete_markers": [
            ".artifacts/releases/_history/live-release.marker",
            ".artifacts/releases/_history/durable-archive.marker",
        ],
    }
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
