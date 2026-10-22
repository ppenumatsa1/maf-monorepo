#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from pip._vendor.packaging.tags import compatible_tags, cpython_tags
from pip._vendor.packaging.utils import InvalidWheelFilename, parse_wheel_filename

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


def validate_wheelhouse(wheelhouse: Path) -> list[Path]:
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise ValueError(f"Runtime wheelhouse is empty: {wheelhouse}")

    incompatible: list[str] = []
    for wheel in wheels:
        try:
            _, _, _, tags = parse_wheel_filename(wheel.name)
        except InvalidWheelFilename as exc:
            incompatible.append(f"{wheel.name}: {exc}")
            continue
        if tags.isdisjoint(TARGET_TAGS):
            incompatible.append(f"{wheel.name}: unsupported tags {sorted(map(str, tags))}")

    if incompatible:
        details = "\n".join(f"- {item}" for item in incompatible)
        raise ValueError(
            f"Wheelhouse contains wheels incompatible with CPython 3.13 Linux AMD64:\n{details}"
        )
    return wheels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    args = parser.parse_args()

    try:
        wheels = validate_wheelhouse(args.wheelhouse)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Validated {len(wheels)} CPython 3.13 Linux AMD64-compatible wheels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
