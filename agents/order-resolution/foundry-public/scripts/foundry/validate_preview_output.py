#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SUMMARY = re.compile(
    r"(?P<count>\d+)\s+(?:resource(?:s)?\s+)?to\s+"
    r"(?P<operation>create|delete|replace|modify|update)",
    re.IGNORECASE,
)
TERRAFORM_SUMMARY = re.compile(
    r"(?P<add>\d+)\s+to\s+add,\s+"
    r"(?P<change>\d+)\s+to\s+change,\s+"
    r"(?P<destroy>\d+)\s+to\s+destroy",
    re.IGNORECASE,
)
BRACKET_OPERATION = re.compile(
    r"\[(?:create|delete|replace|modify|update|deploy)\]",
    re.IGNORECASE,
)
SAFE_RESULT = re.compile(
    r"\bno changes(?: to apply)?\b|\[(?:skip|nochange|ignore|unchanged)\]",
    re.IGNORECASE,
)
OPERATION_LINE = re.compile(
    r"^\s*(?:[+~!-]\s+|\b(?:create|delete|replace|modify|update)\b)",
    re.IGNORECASE,
)
MUTATING_OPERATION = re.compile(r"\b(?:create|delete|replace|modify|update)\b", re.IGNORECASE)


def validate_preview(text: str) -> dict[str, object]:
    normalized = ANSI.sub("", text)
    violations: list[str] = []
    result_observed = False
    for line_number, raw_line in enumerate(normalized.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        for match in SUMMARY.finditer(line):
            result_observed = True
            if int(match.group("count")) > 0:
                violations.append(
                    f"line {line_number}: non-zero {match.group('operation').lower()} count"
                )
        terraform_summary = TERRAFORM_SUMMARY.search(line)
        if terraform_summary:
            result_observed = True
            if any(int(terraform_summary.group(name)) > 0 for name in ("add", "change", "destroy")):
                violations.append(f"line {line_number}: non-zero infrastructure change count")
        if SAFE_RESULT.search(line):
            result_observed = True
        if BRACKET_OPERATION.search(line):
            violations.append(f"line {line_number}: mutating operation")
        if OPERATION_LINE.search(raw_line) and MUTATING_OPERATION.search(raw_line):
            violations.append(f"line {line_number}: mutating operation")
        if re.search(r"\bpreview\s+(?:failed|incomplete|unknown)\b", line, re.IGNORECASE):
            violations.append(f"line {line_number}: preview did not complete safely")
    if violations:
        raise ValueError("Infrastructure preview is not non-mutating: " + "; ".join(violations))
    if not result_observed:
        raise ValueError(
            "Infrastructure preview is incomplete: no authoritative change result was found"
        )
    return {
        "status": "passed",
        "mutation_performed": False,
        "preview_sha256_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("preview", type=Path)
    parser.add_argument("--output", choices=("json", "text"), default="text")
    args = parser.parse_args()
    try:
        result = validate_preview(args.preview.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.output == "json":
        print(json.dumps(result, sort_keys=True))
    else:
        print("Infrastructure preview contains no mutating operations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
