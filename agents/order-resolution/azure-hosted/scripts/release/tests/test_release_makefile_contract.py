from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT_DIR / "Makefile"


def require(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Missing Makefile contract: {needle}")


def main() -> int:
    content = MAKEFILE.read_text(encoding="utf-8")

    for target in (
        "release-profile-apply:",
        "release-preflight:",
        "release-package:",
        "release-deploy:",
        "release-verify:",
        "release-smoke:",
        "release-browser-e2e:",
        "release-domain-e2e:",
        "release-eval:",
        "release-telemetry:",
        "release-evidence:",
        "release-provision:",
        "release:",
    ):
        require(content, target)

    require(content, "./scripts/release/prepare-release-context.sh")
    require(content, "./scripts/release/run-preflight.sh")
    require(content, "./scripts/release/verify-release-deployment.sh")
    require(content, "./scripts/release/run-release-smoke.sh")
    require(content, "./scripts/release/run-browser-e2e.sh")
    require(content, "./scripts/release/run-domain-e2e.sh")
    require(content, "./scripts/release/verify-app-insights-correlation.sh")
    require(content, "aggregate-release-evidence.py")
    require(content, 'FOUNDRY_EVAL_OUTPUT_FILE="$$RELEASE_EVIDENCE_DIR/evaluation.json"')
    require(content, "FOUNDRY_EVAL_ENFORCE_PASS=true")
    require(content, "release_write_stage_artifact \"infrastructure.json\"")
    require(content, "release-validate:")
    require(content, "./scripts/release/validate-hosted-release.sh")
    require(content, "release_record_timing stage-start package_build")
    require(content, "release_record_timing stage-end package_build succeeded")
    require(content, "release_record_timing stage-start final_evidence")
    require(content, "release_record_timing stage-end final_evidence succeeded")

    print("Release Makefile contract tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
