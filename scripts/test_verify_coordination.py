"""Negative tests for coordination tooling; these are not EVORA app tests."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
import sys

import verify_coordination as audit


class CatalogTests(unittest.TestCase):
    def test_catalog_parses_setup_and_feature_dependencies(self):
        self.assertIsNotNone(audit, "Coordination verifier is not implemented")
        text = (
            "| G00 | setup | contract | ready |\n"
            "| F00 | auth | G00 | `ApiError` | deny foreign case |\n"
        )
        rows = audit.parse_catalog(text)
        self.assertEqual(set(rows), {"G00", "F00"})
        self.assertEqual(rows["F00"]["dependencies"], {"G00"})


    def test_duplicate_ticket_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.parse_catalog("| F00 | auth | G00 | `ApiError` | check |\n" * 2)

    def test_malformed_task_row_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Malformed"):
            audit.parse_catalog("| F00 | missing columns |\n")

    def test_empty_catalog_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "No tasks"):
            audit.parse_catalog("# Empty catalog\n")

    def test_missing_dependency_is_rejected(self):
        rows = audit.parse_catalog("| F00 | auth | G99 | `ApiError` | check |\n")
        with self.assertRaisesRegex(ValueError, "Missing dependency"):
            audit.dependency_closure(rows)

    def test_dependency_cycle_is_rejected(self):
        rows = audit.parse_catalog(
            "| F00 | auth | F01 | `ApiError` | check |\n"
            "| F01 | case | F00 | `Case` | check |\n"
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            audit.dependency_closure(rows)

    def test_closure_includes_transitive_dependencies(self):
        rows = audit.parse_catalog(
            "| G00 | setup | contract | ready |\n"
            "| F00 | auth | G00 | `ApiError` | check |\n"
            "| F01 | case | F00 | `Case` | check |\n"
        )
        closure = audit.dependency_closure(rows)
        self.assertEqual(closure.get("F01"), {"G00", "F00"})


class ContractAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())

    def test_actual_contract_passes(self):
        self.assertTrue(callable(getattr(audit, "verify_spec", None)), "Spec verifier missing")
        self.assertEqual(len(audit.verify_spec(self.spec)), 25)

    def test_missing_error_response_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_spec", None)), "Spec verifier missing")
        spec = copy.deepcopy(self.spec)
        del spec["paths"]["/api/v1/cases"]["get"]["responses"]["400"]
        with self.assertRaisesRegex(ValueError, "400"):
            audit.verify_spec(spec)

    def test_changed_common_auth_response_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["paths"]["/api/v1/cases"]["get"]["responses"]["401"] = {"description": "Unspecified shape"}
        with self.assertRaisesRegex(ValueError, "401"):
            audit.verify_spec(spec)

    def test_changed_common_not_found_response_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["paths"]["/api/v1/cases/{caseId}"]["get"]["responses"]["404"] = {"description": "Unspecified shape"}
        with self.assertRaisesRegex(ValueError, "404"):
            audit.verify_spec(spec)

    def test_duplicate_operation_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_spec", None)), "Spec verifier missing")
        spec = copy.deepcopy(self.spec)
        spec["paths"]["/api/v1/cases"]["get"]["operationId"] = "createCase"
        with self.assertRaisesRegex(ValueError, "Duplicate operation"):
            audit.verify_spec(spec)

    def test_missing_snapshot_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_spec", None)), "Spec verifier missing")
        spec = copy.deepcopy(self.spec)
        spec["components"]["schemas"]["AnalysisRun"]["required"].remove("input_snapshot")
        with self.assertRaisesRegex(ValueError, "input_snapshot"):
            audit.verify_spec(spec)

    def test_broken_schema_reference_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_spec", None)), "Spec verifier missing")
        spec = copy.deepcopy(self.spec)
        spec["components"]["schemas"]["CasePage"]["properties"]["items"]["items"]["$ref"] = "#/components/schemas/DoesNotExist"
        with self.assertRaisesRegex(ValueError, "reference"):
            audit.verify_spec(spec)


class DocumentTests(unittest.TestCase):
    def test_broken_local_link_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_documents", None)), "Document verifier missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[missing](missing.md)\n")
            with self.assertRaisesRegex(ValueError, "link"):
                audit.verify_documents(root)

    def test_valid_local_link_is_accepted(self):
        self.assertTrue(callable(getattr(audit, "verify_documents", None)), "Document verifier missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[notes](notes.md)\n")
            (root / "notes.md").write_text("# Notes\n")
            self.assertEqual(audit.verify_documents(root), 2)

    def test_trailing_whitespace_is_rejected(self):
        self.assertTrue(callable(getattr(audit, "verify_documents", None)), "Document verifier missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Notes  \n")
            with self.assertRaisesRegex(ValueError, "whitespace"):
                audit.verify_documents(root)


class CommandLineTests(unittest.TestCase):
    """Exercise failure exits from isolated copies, never mutate the repository."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = Path(__file__).resolve().parents[1]
        paths = list(source.glob("*.md")) + list((source / "docs").glob("*.md"))
        paths += list((source / "fixtures").rglob("*.csv"))
        paths += [source / "specs/openapi.yaml", source / "scripts/verify_coordination.py",
                  source / ".github/pull_request_template.md", source / ".github/workflows/contract.yml"]
        for path in paths:
            target = self.root / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        self.bundle = self.root / "bundle.json"
        shutil.copyfile(os.environ["EVORA_CONTRACT_BUNDLE"], self.bundle)

    def execute(self):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/verify_coordination.py"), str(self.bundle)],
            capture_output=True, text=True, check=False, timeout=15,
        )

    def mutate(self, relative, transform):
        path = self.root / relative
        original = path.read_text(encoding="utf-8")
        replacement = transform(original)
        self.assertNotEqual(original, replacement, "Mutation must change its target")
        path.write_text(replacement, encoding="utf-8")

    def assert_failure(self, message):
        result = self.execute()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)

    def test_actual_tree_cli_passes(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["operations"], 25)

    def test_cli_rejects_invalid_fixture_header(self):
        self.mutate("fixtures/synthetic-case/gps.csv", lambda text: text.replace("latitude", "lat", 1))
        self.assert_failure("fixture header")

    def test_cli_rejects_missing_proposal_section_mapping(self):
        self.mutate("docs/PROPOSAL_TRACEABILITY.md", lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith("| 40 |")) + "\n")
        self.assert_failure("Traceability must map")

    def test_cli_rejects_missing_operation_assignment(self):
        self.mutate("docs/TASK_BREAKDOWN.md", lambda text: text.replace("`createCase`", "`Case`"))
        self.assert_failure("Unassigned operations")

    def test_cli_rejects_missing_ui_command(self):
        def remove_command(text):
            return "\n".join(line.replace("`startAnalysis`", "`AnalysisRun`")
                             if line.startswith("| U") else line for line in text.splitlines()) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", remove_command)
        self.assert_failure("Missing UI command")

    def test_cli_rejects_uncovered_full_scope(self):
        def remove_dependencies(text):
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("| I09B |"):
                    cells = line.split("|")
                    cells[3] = " — "
                    lines[index] = "|".join(cells)
            return "\n".join(lines) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", remove_dependencies)
        self.assert_failure("Full-scope reproducibility gate misses")


if __name__ == "__main__":
    unittest.main()
