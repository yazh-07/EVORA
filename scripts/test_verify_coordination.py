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
        operations=audit.verify_spec(self.spec)
        expected={operation['operationId'] for item in self.spec['paths'].values()
                  for method,operation in item.items() if method in {'get','post','put','patch','delete','head','options','trace'}}
        self.assertEqual(set(operations),expected)
        self.assertEqual(self.spec['paths']['/api/v1/cases/{caseId}/evidence/{evidenceId}/image-analysis']['post']['operationId'],'analyzeImage')
        self.assertIn('connectChatGPT',operations)

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
        project = Path(__file__).resolve().parents[1]
        source = project / 'fixtures/planning/legacy-coordination'
        paths = list(source.glob("*.md")) + list((source / "docs").glob("*.md"))
        paths += list((source / "fixtures").rglob("*.csv"))
        paths += [source / "specs/openapi.yaml", source / "scripts/verify_coordination.py",
                  source / ".github/pull_request_template.md", source / ".github/workflows/contract.yml"]
        for path in paths:
            target = self.root / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        # Exercise the current CLI against an explicitly historical planning tree.
        shutil.copyfile(project / 'scripts/verify_coordination.py',self.root / 'scripts/verify_coordination.py')
        self.bundle = self.root / "bundle.json"
        shutil.copyfile(source / 'openapi.json', self.bundle)

    def execute(self):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/verify_coordination.py"), str(self.bundle), '--historical-planning'],
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

    def test_cli_rejects_malformed_catalog_header(self):
        self.mutate("docs/TASK_BREAKDOWN.md", lambda text: text.replace(
            "Acceptance for this PR", "Acceptance for this PR (wrong)", 1))
        self.assert_failure("task catalog header")

    def test_cli_accepts_mirrored_canonical_exit_gate_change(self):
        def add_roadmap_gate(text):
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("| 1B |"):
                    cells = line.split("|")
                    cells[3] = " I00B, P01 "
                    lines[index] = "|".join(cells)
            return "\n".join(lines) + "\n"
        self.mutate("docs/ROADMAP.md", add_roadmap_gate)
        self.mutate("docs/INTEGRATION.md", lambda text: text.replace(
            "| 1B | I00B |", "| 1B | I00B, P01 |", 1))
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["tasks"], 126)

    def test_cli_rejects_missing_transcription_common_output_handoff(self):
        def remove_speech(text):
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("| P05C |"):
                    cells = line.split("|")
                    cells[3] = ", ".join(value.strip() for value in cells[3].split(",")
                                         if value.strip() != "P16B")
                    lines[index] = "|".join(cells)
            return "\n".join(lines) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", remove_speech)
        self.assert_failure("Transcription handoff P05C")

    def test_cli_rejects_missing_transcript_revision_operation(self):
        def remove_revision(text):
            spec = json.loads(text)
            for item in spec["paths"].values():
                for method, operation in list(item.items()):
                    if isinstance(operation, dict) and operation.get("operationId") == "appendTranscriptRevision":
                        del item[method]
            return json.dumps(spec)
        self.mutate("bundle.json", remove_revision)
        self.assert_failure("Expected preserved operations")

    def test_cli_rejects_same_checkpoint_exit_gate_substitution(self):
        self.mutate("docs/INTEGRATION.md", lambda text: text.replace("| 1B | I00B |", "| 1B | P01 |", 1))
        self.assert_failure("Runbook exit gate set mismatch")

    def test_cli_rejects_duplicate_runbook_exit_gate(self):
        self.mutate("docs/INTEGRATION.md", lambda text: text.replace("| 1B | I00B |", "| 1B | I00B, I00B |", 1))
        self.assert_failure("Duplicate Runbook exit gate")

    def test_cli_rejects_extra_column_runbook_duplicate(self):
        def append_malformed_duplicate(text):
            line = next(line for line in text.splitlines() if line.startswith("| 1B | I00B |"))
            return text.replace(line, line + "\n" + line + " extra |", 1)
        self.mutate("docs/INTEGRATION.md", append_malformed_duplicate)
        self.assert_failure("Malformed runbook ledger row")

    def test_cli_rejects_malformed_runbook_header(self):
        self.mutate("docs/INTEGRATION.md", lambda text: text.replace("Required real proof", "Wrong proof", 1))
        self.assert_failure("runbook ledger header")

    def test_cli_rejects_malformed_runbook_checkpoint(self):
        def append_malformed_id(text):
            line = next(line for line in text.splitlines() if line.startswith("| 1B | I00B |"))
            return text.replace(line, line + "\n" + line.replace("| 1B |", "| 1BB |", 1), 1)
        self.mutate("docs/INTEGRATION.md", append_malformed_id)
        self.assert_failure("Malformed runbook checkpoint")

    def test_cli_rejects_missing_assembled_publication_dependency(self):
        path = self.root / "docs/TASK_BREAKDOWN.md"
        original = path.read_text(encoding="utf-8")
        for task in ("U12A", "U12B", "U12C", "U12D", "U12E", "U13B"):
            with self.subTest(task=task):
                path.write_text(original, encoding="utf-8")
                def remove_assembly(text):
                    lines = text.splitlines()
                    for index, line in enumerate(lines):
                        if line.startswith(f"| {task} |"):
                            cells = line.split("|")
                            cells[3] = ", ".join(value.strip() for value in cells[3].split(",")
                                                 if value.strip() != "A17")
                            lines[index] = "|".join(cells)
                    return "\n".join(lines) + "\n"
                self.mutate("docs/TASK_BREAKDOWN.md", remove_assembly)
                self.assert_failure(f"Assembled publication dependency {task} requires A17")

    def test_cli_rejects_assembled_views_moved_before_publication(self):
        catalog_path = self.root / "docs/TASK_BREAKDOWN.md"
        roadmap_path = self.root / "docs/ROADMAP.md"
        catalog = catalog_path.read_text(encoding="utf-8")
        roadmap = roadmap_path.read_text(encoding="utf-8")
        for task in ("U12A", "U12B", "U12C", "U12D", "U12E", "U13B"):
            with self.subTest(task=task):
                catalog_path.write_text(catalog, encoding="utf-8")
                roadmap_path.write_text(roadmap, encoding="utf-8")
                self.mutate("docs/TASK_BREAKDOWN.md", lambda text: "\n".join(
                    line.rsplit("| 4B |", 1)[0] + "| 4A |" if line.startswith(f"| {task} |") else line
                    for line in text.splitlines()) + "\n")
                def move_assignment(text):
                    lines = text.splitlines()
                    for index, line in enumerate(lines):
                        if line.startswith(("| 4A |", "| 4B |")):
                            cells = line.split("|")
                            tasks = [value.strip() for value in cells[2].split(",")]
                            if cells[1].strip() == "4A":
                                tasks.append(task)
                            else:
                                tasks.remove(task)
                            cells[2] = " " + ", ".join(tasks) + " "
                            lines[index] = "|".join(cells)
                    return "\n".join(lines) + "\n"
                self.mutate("docs/ROADMAP.md", move_assignment)
                self.assert_failure(f"Later checkpoint prerequisite: {task} requires A17")

    def test_cli_rejects_malformed_feature_header(self):
        self.mutate("docs/FEATURE_SCOPE.md", lambda text: text.replace(
            "Evidence needed to claim it works | Checkpoint coverage",
            "Evidence needed to claim it works  Checkpoint coverage", 1))
        self.assert_failure("feature inventory header")

    def test_cli_rejects_omitted_feature(self):
        self.mutate("docs/FEATURE_SCOPE.md", lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith("| Case creation/catalog/access |")) + "\n")
        self.assert_failure("Feature capability coverage")

    def test_cli_rejects_duplicate_feature(self):
        def duplicate_feature(text):
            line = next(line for line in text.splitlines() if line.startswith("| Case creation/catalog/access |"))
            return text.replace(line, line + "\n" + line, 1)
        self.mutate("docs/FEATURE_SCOPE.md", duplicate_feature)
        self.assert_failure("Duplicate feature capability")

    def test_cli_rejects_indented_wrong_feature_coverage(self):
        self.mutate("docs/FEATURE_SCOPE.md", lambda text: "\n".join(
            "    " + line.replace("| 1A |", "| 0 |")
            if line.startswith("| Case creation/catalog/access |") else line
            for line in text.splitlines()) + "\n")
        self.assert_failure("Feature checkpoint coverage mismatch")

    def test_cli_rejects_feature_tracer_ranges(self):
        path = self.root / "docs/FEATURE_SCOPE.md"
        original = path.read_text(encoding="utf-8")
        for reference in ("I01-I03", "I01–I03", "I01—I03"):
            with self.subTest(reference=reference):
                path.write_text(original, encoding="utf-8")
                def restore_range(text):
                    lines = text.splitlines()
                    for index, line in enumerate(lines):
                        if line.startswith("| Full integration and clean reproducibility |"):
                            cells = line.split("|")
                            cells[3] = f" I09/I09B after tracer {reference} "
                            lines[index] = "|".join(cells)
                    return "\n".join(lines) + "\n"
                self.mutate("docs/FEATURE_SCOPE.md", restore_range)
                self.assert_failure("Feature task references require exact IDs, not ranges")

    def test_cli_rejects_invalid_state_duplicate_roadmap(self):
        def duplicate_with_invalid_state(text):
            line = next(line for line in text.splitlines() if line.startswith("| 1B |"))
            return text.replace(line, line + "\n" + line.replace("Backlog", "Bogus"), 1)
        self.mutate("docs/ROADMAP.md", duplicate_with_invalid_state)
        self.assert_failure("Duplicate checkpoint")

    def test_cli_rejects_invalid_roadmap_state(self):
        self.mutate("docs/ROADMAP.md", lambda text: text.replace("| Backlog |", "| Bogus |", 1))
        self.assert_failure("Invalid checkpoint state")

    def test_cli_rejects_malformed_roadmap_header(self):
        self.mutate("docs/ROADMAP.md", lambda text: text.replace("Exact task membership", "Task range", 1))
        self.assert_failure("Roadmap ledger header")

    def test_cli_rejects_canonical_table_separators(self):
        for relative, separator in (
                ("docs/TASK_BREAKDOWN.md", "|---|---|---|---|---|---|"),
                ("docs/ROADMAP.md", "|---|---|---|---|---|"),
                ("docs/INTEGRATION.md", "|---|---|---|---|"),
                ("docs/FEATURE_SCOPE.md", "|---|---|---|---|---|")):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_text(encoding="utf-8")
                self.mutate(relative, lambda text: text.replace(separator, separator.replace("---", "bad", 1), 1))
                self.assert_failure("separator")
                path.write_text(original, encoding="utf-8")

    def test_cli_rejects_missing_canonical_table_headings(self):
        for relative, heading in (
                ("docs/TASK_BREAKDOWN.md", "## Common-base and setup"),
                ("docs/ROADMAP.md", "## Exact checkpoint ledger"),
                ("docs/INTEGRATION.md", "## Checkpoint execution ledger"),
                ("docs/FEATURE_SCOPE.md", "## Complete feature ownership and acceptance")):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_text(encoding="utf-8")
                self.mutate(relative, lambda text: text.replace(heading, "## Wrong ledger", 1))
                self.assert_failure("heading")
                path.write_text(original, encoding="utf-8")

    def test_cli_ignores_tables_outside_canonical_sections(self):
        for relative in ("docs/TASK_BREAKDOWN.md", "docs/ROADMAP.md", "docs/INTEGRATION.md", "docs/FEATURE_SCOPE.md"):
            self.mutate(relative, lambda text: text + "\n## Unrelated example\n| 1B | P01 | bogus | Bogus |\n")
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["feature_capabilities"], 39)

    def test_cli_accepts_transitive_assembled_publication_dependency(self):
        self.mutate("docs/TASK_BREAKDOWN.md", lambda text: "\n".join(
            line.replace(", A17 |", ", A19 |") if line.startswith("| U12A |") else line
            for line in text.splitlines()) + "\n")
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("assembled_publication_dependencies", json.loads(result.stdout)["checks"])

    def test_archived_tree_cli_passes(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["operations"], 27)

    def test_cli_reports_phase_membership(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("checkpoint_tasks", report, "CLI does not verify/report phases")
        self.assertEqual(sum(report["checkpoint_tasks"].values()), report["tasks"])

    def test_cli_rejects_incomplete_final_report_closure(self):
        def remove_final_gate(text):
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("| I06 |"):
                    cells = line.split("|")
                    cells[3] = ", ".join(value.strip() for value in cells[3].split(",")
                                         if value.strip() != "I09B")
                    lines[index] = "|".join(cells)
            return "\n".join(lines) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", remove_final_gate)
        self.assert_failure("Final report dependency closure misses")

    def test_cli_rejects_missing_immutable_processing_handoff(self):
        def remove_provenance(text):
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if line.startswith("| A05 |"):
                    cells = line.split("|")
                    cells[3] = ", ".join(value.strip() for value in cells[3].split(",")
                                         if value.strip() != "P14")
                    lines[index] = "|".join(cells)
            return "\n".join(lines) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", remove_provenance)
        self.assert_failure("Immutable/audit handoff dependency")

    def test_cli_rejects_feature_checkpoint_drift(self):
        self.mutate("docs/FEATURE_SCOPE.md", lambda text: text.replace("| 1A |", "| 0 |", 1))
        self.assert_failure("Feature checkpoint coverage mismatch")

    def test_cli_rejects_future_checkpoint_exit_gate(self):
        self.mutate("docs/INTEGRATION.md", lambda text: text.replace(
            "| 1B | I00B |", "| 1B | I01 |", 1))
        self.assert_failure("Runbook exit gate checkpoint mismatch")

    def test_cli_rejects_missing_phase_assignment(self):
        self.mutate("docs/ROADMAP.md", lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith("| 1B |")) + "\n")
        self.assert_failure("Unassigned phase tasks")

    def test_cli_rejects_catalog_phase_drift(self):
        def move_task(text):
            return "\n".join(line.rsplit("| 1A |", 1)[0] + "| 1B |"
                             if line.startswith("| F00 |") else line
                             for line in text.splitlines()) + "\n"
        self.mutate("docs/TASK_BREAKDOWN.md", move_task)
        self.assert_failure("Checkpoint mismatch")

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
