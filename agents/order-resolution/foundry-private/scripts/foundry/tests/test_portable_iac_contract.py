import json
import re
import subprocess
import unittest
from pathlib import Path


PRIVATE_ROOT = Path(__file__).resolve().parents[3]
PROFILE_DIR = PRIVATE_ROOT.parent / "deployment" / "profiles"
PROFILE = PROFILE_DIR / "foundry-private.env"
LOADER = PROFILE_DIR.parent / "profile.sh"
IAC_DIR = PRIVATE_ROOT / "infra" / "foundry-hosted" / "iac"
MAIN = IAC_DIR / "main.bicep"
PARAMETERS = IAC_DIR / "main.parameters.json"
AZURE_YAML = PRIVATE_ROOT / "infra" / "foundry-hosted" / "azure.yaml"

SECRET_OR_RELEASE_INPUTS = {
    "POSTGRES_ADMIN_PASSWORD",
    "RUNNER_VM_SSH_PUBLIC_KEY",
    "RUNTIME_DATABASE_URL",
    "SERVICE_BACKEND_IMAGE_NAME",
    "SERVICE_FRONTEND_IMAGE_NAME",
}


def read_profile(path: Path = PROFILE) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise AssertionError(f"duplicate profile key: {key}")
        values[key] = value
    return values


class PortableIacContractTests(unittest.TestCase):
    def test_profile_is_canonical_non_secret_selected_target(self) -> None:
        values = read_profile()
        self.assertEqual(values["AZURE_RESOURCE_GROUP"], "rg-maf-ora-foundry-private")
        self.assertEqual(values["AZURE_LOCATION"], "eastus2")
        self.assertEqual(values["AZD_ENVIRONMENT_NAME"], "ora-foundry-private")
        self.assertEqual(
            {
                values["FOUNDRY_LOCATION"],
                values["AI_SEARCH_LOCATION"],
                values["COSMOS_LOCATION"],
                values["POSTGRES_LOCATION"],
            },
            {"eastus2"},
        )
        forbidden = re.compile(r"(PASSWORD|SECRET|TOKEN|PRIVATE_KEY|DATABASE_URL)$")
        self.assertFalse([key for key in values if forbidden.search(key)])

    def test_loader_fails_closed_for_missing_required_value(self) -> None:
        lines = [
            line
            for line in PROFILE.read_text().splitlines()
            if not line.startswith("AZURE_RESOURCE_GROUP=")
        ]
        scratch = PROFILE_DIR / ".profile-contract-test.env"
        try:
            scratch.write_text("\n".join(lines) + "\n")
            result = subprocess.run(
                ["bash", str(LOADER), "validate", str(scratch)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AZURE_RESOURCE_GROUP", result.stderr)
        finally:
            scratch.unlink(missing_ok=True)

    def test_parameter_placeholders_are_profile_or_secure_release_inputs(self) -> None:
        values = read_profile()
        parameters = json.loads(PARAMETERS.read_text())
        placeholders = {
            match.group(1)
            for match in re.finditer(
                r"\$\{([A-Z][A-Z0-9_]*)\}",
                json.dumps(parameters),
            )
        }
        self.assertFalse(placeholders - values.keys() - SECRET_OR_RELEASE_INPUTS)

    def test_generic_iac_contains_no_selected_target_literals(self) -> None:
        generic = "\n".join(
            path.read_text()
            for path in [MAIN, PARAMETERS, AZURE_YAML, *sorted((IAC_DIR / "modules").glob("*.bicep"))]
        )
        for literal in (
            "7df95e88-701c-4693-af77-3159f83b558d",
            "a679d99f-b8f5-4d50-843e-5b73405ce0fc",
            "rg-maf-ora-foundry-private",
            "ora-foundry-private",
            "foundry-private-env",
            "foundry-private-v2",
            "maffndpgv20722",
        ):
            self.assertNotIn(literal, generic)

    def test_names_and_outputs_are_scope_derived_and_authoritative(self) -> None:
        source = MAIN.read_text()
        self.assertIn("uniqueString(resourceGroup().id)", source)
        self.assertIn("var effectivePostgresServerName =", source)
        self.assertNotRegex(source, r"param postgresServerName\b")
        self.assertIn("output foundryAccountEndpoints object", source)
        self.assertIn("output deploymentContext object", source)
        self.assertIn("deploymentMode == 'bootstrap'", source)
        self.assertIn("existingBackendContainerApp", source)
        self.assertIn("existingPostgresServer", source)


if __name__ == "__main__":
    unittest.main()
