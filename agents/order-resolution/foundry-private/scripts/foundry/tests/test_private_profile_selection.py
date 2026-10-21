import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path


PRIVATE_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = PRIVATE_ROOT.parents[2]
PROFILE_DIR = PRIVATE_ROOT.parent / "deployment" / "profiles"
CANONICAL_PROFILE = PROFILE_DIR / "foundry-private.env"
LOCAL_TEMPLATE = PROFILE_DIR / "foundry-private.local.env.example"
RESOLVER = PRIVATE_ROOT / "scripts" / "foundry" / "private_profile.sh"
SCRATCH_ROOT = Path(__file__).resolve().parent / ".test-artifacts"


def run_resolver(profile: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [
        "bash",
        "-c",
        'source "$1"; private_profile_resolve "$2"',
        "private-profile-test",
        str(RESOLVER),
        str(PRIVATE_ROOT),
    ]
    environment = os.environ.copy()
    if profile is None:
        environment.pop("DEPLOYMENT_PROFILE_FILE", None)
    else:
        environment["DEPLOYMENT_PROFILE_FILE"] = str(profile)
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateProfileSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.scratch = SCRATCH_ROOT / f"case-{os.getpid()}-{self._testMethodName}"
        self.scratch.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)
        if SCRATCH_ROOT.exists() and not any(SCRATCH_ROOT.iterdir()):
            SCRATCH_ROOT.rmdir()

    def make_valid_local_profile(self) -> Path:
        replacements = {
            "AZURE_SUBSCRIPTION_ID": "11111111-1111-4111-8111-111111111111",
            "AZURE_TENANT_ID": "22222222-2222-4222-8222-222222222222",
            "AZURE_RESOURCE_GROUP": "rg-local-clean-room",
            "AZURE_ENV_NAME": "local-clean-room",
            "AZD_ENVIRONMENT_NAME": "local-clean-room",
            "NAME_PREFIX": "localclean",
            "PRIVATE_RUNNER_LABEL": "local-private-runner",
            "PRIVATE_RUNNER_VM_NAME": "local-private-runner-vm",
            "FOUNDRY_PROJECT_NAME": "local-project",
            "HOSTED_AGENT_NAME": "local-hosted-agent",
            "POSTGRES_DATABASE_NAME": "local_workflow",
            "POSTGRES_ADMIN_USERNAME": "localadmin",
            "RUNNER_VM_ADMIN_USERNAME": "localrunner",
        }
        lines: list[str] = []
        for line in CANONICAL_PROFILE.read_text().splitlines():
            if not line or line.startswith("#"):
                lines.append(line)
                continue
            key, value = line.split("=", 1)
            lines.append(f"{key}={replacements.get(key, value)}")
        profile = self.scratch / "foundry-private.local.env"
        profile.write_text("\n".join(lines) + "\n")
        return profile

    def test_canonical_profile_remains_the_default(self) -> None:
        result = run_resolver()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), CANONICAL_PROFILE.resolve())
        self.assertIn("canonical repository profile", result.stderr)
        self.assertNotIn("supported explicit local profile", result.stderr)

    def test_explicit_local_profile_is_supported_and_identified(self) -> None:
        profile = self.make_valid_local_profile()

        result = run_resolver(profile)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), profile.resolve())
        self.assertIn("supported explicit local profile", result.stderr)
        self.assertNotIn(str(profile), result.stderr)
        self.assertNotIn("11111111-1111-4111-8111-111111111111", result.stderr)

    def test_missing_and_invalid_local_profiles_fail_without_printing_values(self) -> None:
        missing = self.scratch / "missing.local.env"
        missing_result = run_resolver(missing)
        self.assertNotEqual(missing_result.returncode, 0)
        self.assertIn("explicit local profile", missing_result.stderr)
        self.assertNotIn(str(missing), missing_result.stderr)

        invalid = self.scratch / "invalid.local.env"
        marker = "do-not-print-this-identifier"
        invalid.write_text(
            "\n".join(
                [
                    "CONTRACT_VERSION=1",
                    "DEPLOYMENT_LANE=foundry-private",
                    f"AZURE_ENV_NAME={marker}",
                ]
            )
            + "\n"
        )
        invalid_result = run_resolver(invalid)
        self.assertNotEqual(invalid_result.returncode, 0)
        self.assertIn("failed validation", invalid_result.stderr)
        self.assertNotIn(str(invalid), invalid_result.stderr)
        self.assertNotIn(marker, invalid_result.stderr)

    def test_local_profile_is_ignored_and_template_is_sanitized(self) -> None:
        local_profile = PROFILE_DIR / "foundry-private.local.env"
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", str(local_profile)],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        template_ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", str(LOCAL_TEMPLATE)],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
        self.assertNotEqual(template_ignored.returncode, 0)

        canonical_keys = {
            line.split("=", 1)[0]
            for line in CANONICAL_PROFILE.read_text().splitlines()
            if line and not line.startswith("#")
        }
        template_values = {
            key: value
            for key, value in (
                line.split("=", 1)
                for line in LOCAL_TEMPLATE.read_text().splitlines()
                if line and not line.startswith("#")
            )
        }
        self.assertEqual(template_values.keys(), canonical_keys)
        self.assertTrue(
            all(re.fullmatch(r"<[a-z0-9-]+>", value) for value in template_values.values())
        )
        self.assertNotRegex(
            LOCAL_TEMPLATE.read_text(),
            r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b",
        )

    def test_eval_foundry_normalizes_an_absolute_profile_path(self) -> None:
        profile = self.make_valid_local_profile().resolve()

        result = subprocess.run(
            [
                "make",
                "--dry-run",
                "eval-foundry",
                f"DEPLOYMENT_PROFILE_FILE={profile}",
            ],
            cwd=PRIVATE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'_ "{profile}"', result.stdout)
        self.assertNotIn(f'..//{profile}', result.stdout)


if __name__ == "__main__":
    unittest.main()
