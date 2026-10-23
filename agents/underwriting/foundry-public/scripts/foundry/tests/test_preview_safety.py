from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from validate_preview_output import validate_preview  # noqa: E402


class PreviewSafetyTests(unittest.TestCase):
    def test_zero_change_preview_is_accepted(self) -> None:
        preview = """
            Previewing changes...
            0 resources to create
            0 resources to delete
            0 resources to replace
            No changes to apply.
            """
        result = validate_preview(preview)
        self.assertFalse(result["mutation_performed"])

    def test_create_delete_replace_and_update_are_rejected(self) -> None:
        for operation in ("create", "delete", "replace", "modify", "update"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "not non-mutating"):
                    validate_preview(f"1 resource to {operation}\n")

    def test_full_infrastructure_preview_allows_create_only(self) -> None:
        result = validate_preview(
            "2 resources to create\n0 resources to delete\n0 resources to replace\n",
            mode="full_infra",
        )
        self.assertEqual(result["preview_mode"], "full_infra")
        for operation in ("delete", "replace", "modify", "update"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, f"non-zero {operation} count"):
                    validate_preview(
                        f"1 resource to {operation}\n",
                        mode="full_infra",
                    )

    def test_protected_stateful_network_and_rbac_drift_is_named(self) -> None:
        for resource in (
            "Microsoft.Authorization/roleAssignments",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.DBforPostgreSQL/flexibleServers",
        ):
            with self.subTest(resource=resource):
                with self.assertRaisesRegex(
                    ValueError, "unexpected stateful/network/RBAC change"
                ):
                    validate_preview(
                        f"~ Modify {resource} fixture\n",
                        mode="full_infra",
                    )

    def test_operation_detail_is_rejected_even_without_summary(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutating operation"):
            validate_preview("+ Create Microsoft.App/managedEnvironments example\n")

    def test_bracketed_azd_mutation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutating operation"):
            validate_preview("resource-name [Modify]\n")

    def test_empty_or_progress_only_output_fails_closed(self) -> None:
        for output in ("", "Previewing changes...\n", "Deployment Plan\n"):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    validate_preview(output)

    def test_failed_preview_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not complete safely"):
            validate_preview("Preview failed before ARM what-if completed.\n")


if __name__ == "__main__":
    unittest.main()
