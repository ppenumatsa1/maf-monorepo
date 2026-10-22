#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from pip._vendor.packaging.tags import compatible_tags, cpython_tags
from pip._vendor.packaging.utils import (
    InvalidWheelFilename,
    canonicalize_name,
    parse_wheel_filename,
)

TARGET_INDEX_URL = "https://packagefeedproxy.microsoft.io/pypi/simple"
TARGET_PLATFORMS = (
    "manylinux2014_x86_64",
    "manylinux2010_x86_64",
    "manylinux1_x86_64",
    *(f"manylinux_2_{minor}_x86_64" for minor in range(17, 4, -1)),
)
TARGET_TAGS = set(
    cpython_tags(
        python_version=(3, 13),
        abis=("cp313", "abi3", "none"),
        platforms=TARGET_PLATFORMS,
    )
)
TARGET_TAGS.update(
    compatible_tags(
        python_version=(3, 13),
        interpreter="cp313",
        platforms=TARGET_PLATFORMS,
    )
)
REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_lock(lock_file: Path) -> dict[str, tuple[str, set[str]]]:
    entries: dict[str, tuple[str, set[str]]] = {}
    current_name: str | None = None
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        requirement = REQUIREMENT_RE.match(line)
        if requirement:
            current_name = canonicalize_name(requirement.group(1))
            entries[current_name] = (requirement.group(2), set())
        if current_name:
            entries[current_name][1].update(HASH_RE.findall(line))
    if not entries:
        raise ValueError(f"Dependency lock is empty: {lock_file}")
    unhashed = sorted(name for name, (_, hashes) in entries.items() if not hashes)
    if unhashed:
        raise ValueError(f"Dependency lock has unhashed requirements: {', '.join(unhashed)}")
    return entries


def validate_wheelhouse(
    wheelhouse: Path, lock_file: Path
) -> tuple[list[Path], dict[str, str]]:
    entries = parse_lock(lock_file)
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise ValueError(f"Runtime wheelhouse is empty: {wheelhouse}")

    failures: list[str] = []
    wheel_hashes: dict[str, str] = {}
    found_packages: set[str] = set()
    for wheel in wheels:
        if not zipfile.is_zipfile(wheel):
            failures.append(f"{wheel.name}: file is not a valid wheel archive")
            continue
        try:
            name, version, _, tags = parse_wheel_filename(wheel.name)
        except InvalidWheelFilename as exc:
            failures.append(f"{wheel.name}: {exc}")
            continue
        normalized_name = canonicalize_name(name)
        found_packages.add(normalized_name)
        expected = entries.get(normalized_name)
        if expected is None:
            failures.append(f"{wheel.name}: package is not present in {lock_file.name}")
            continue
        expected_version, expected_hashes = expected
        if str(version) != expected_version:
            failures.append(
                f"{wheel.name}: version {version} does not match locked {expected_version}"
            )
        if tags.isdisjoint(TARGET_TAGS):
            failures.append(f"{wheel.name}: unsupported tags {sorted(map(str, tags))}")
        wheel_hash = sha256(wheel)
        wheel_hashes[wheel.name] = wheel_hash
        if wheel_hash not in expected_hashes:
            failures.append(f"{wheel.name}: sha256 is not authorized by {lock_file.name}")

    missing = sorted(set(entries) - found_packages)
    if missing:
        failures.append(f"missing locked wheels: {', '.join(missing)}")
    if failures:
        details = "\n".join(f"- {failure}" for failure in failures)
        raise ValueError(f"Wheelhouse contract validation failed:\n{details}")
    return wheels, wheel_hashes


def validate_contract(
    contract_file: Path,
    lock_file: Path,
    wheel_hashes: dict[str, str],
) -> dict[str, object]:
    if not contract_file.is_file():
        raise ValueError(f"Wheelhouse contract is missing: {contract_file}")
    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "index_url": TARGET_INDEX_URL,
        "implementation": "cp",
        "python_version": "3.13",
        "abi": "cp313",
        "platform": "manylinux2014_x86_64",
        "requirements_sha256": sha256(lock_file),
        "wheels": wheel_hashes,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise ValueError(f"Wheelhouse contract field {key!r} does not match")
    if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("contract_hash", ""))):
        raise ValueError("Wheelhouse contract_hash must be a sha256 digest")
    return contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("requirements_lock", type=Path)
    parser.add_argument("--write-contract", action="store_true")
    parser.add_argument("--contract-hash")
    parser.add_argument("--index-url", default=TARGET_INDEX_URL)
    args = parser.parse_args()

    try:
        wheels, wheel_hashes = validate_wheelhouse(
            args.wheelhouse, args.requirements_lock
        )
        contract_file = args.wheelhouse / ".wheelhouse-contract.json"
        if args.write_contract:
            if args.index_url != TARGET_INDEX_URL:
                raise ValueError(f"Wheelhouse feed must be {TARGET_INDEX_URL}")
            if not re.fullmatch(r"[0-9a-f]{64}", args.contract_hash or ""):
                raise ValueError("--contract-hash must be a sha256 digest")
            contract = {
                "schema_version": 1,
                "contract_hash": args.contract_hash,
                "index_url": args.index_url,
                "implementation": "cp",
                "python_version": "3.13",
                "abi": "cp313",
                "platform": "manylinux2014_x86_64",
                "requirements_sha256": sha256(args.requirements_lock),
                "wheels": wheel_hashes,
            }
            contract_file.write_text(
                json.dumps(contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        validate_contract(contract_file, args.requirements_lock, wheel_hashes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Validated {len(wheels)} hash-locked CPython 3.13 Linux AMD64 wheels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
