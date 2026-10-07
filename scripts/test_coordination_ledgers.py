"""Focused malformed-ledger regressions; no EVORA product verification."""
import unittest
from pathlib import Path

import test_phase_plan
import verify_coordination as audit


class RoadmapLedgerTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.roadmap = test_phase_plan.PhasePlanTests().plan()

    def test_invalid_state_duplicate_is_not_skipped(self):
        duplicate = self.roadmap.splitlines()[4].replace("Backlog", "Bogus")
        with self.assertRaisesRegex(ValueError, "Duplicate checkpoint|Invalid checkpoint state"):
            audit.verify_phases(self.rows, self.roadmap + duplicate + "\n")

    def test_malformed_checkpoint_is_not_skipped(self):
        with self.assertRaisesRegex(ValueError, "Malformed checkpoint"):
            audit.verify_phases(self.rows, self.roadmap + "| 1AA | F00 | F00 | proof | Backlog |\n")

    def test_canonical_header_is_required(self):
        with self.assertRaisesRegex(ValueError, "Roadmap ledger header"):
            audit.verify_phases(self.rows, self.roadmap.replace("Exact task membership", "Tasks"))

    def test_separator_is_required(self):
        for separator in ("|---|---|---|---|", "|---|---|bad|---|---|"):
            with self.subTest(separator=separator), self.assertRaisesRegex(ValueError, "separator"):
                audit.verify_phases(self.rows, self.roadmap.replace("|---|---|---|---|---|", separator))

    def test_wrong_row_width_is_not_skipped(self):
        with self.assertRaisesRegex(ValueError, "Malformed Roadmap ledger row"):
            audit.verify_phases(self.rows, self.roadmap + "| 0 | G00 | G00 | proof | Backlog | extra |\n")

    def test_duplicate_roadmap_exit_gate_is_rejected(self):
        duplicate = self.roadmap.replace("| F00 | F00 |", "| F00 | F00, F00 |")
        with self.assertRaisesRegex(ValueError, "Duplicate Roadmap exit gate"):
            audit.verify_phases(self.rows, duplicate)

    def test_roadmap_gate_must_be_an_exact_task_id(self):
        for gate in ("F00–F09", "F000", "F99"):
            with self.subTest(gate=gate):
                wrong = self.roadmap.replace("| F00 | F00 |", f"| F00 | {gate} |")
                with self.assertRaisesRegex(ValueError, "Roadmap.*exit gate"):
                    audit.verify_phases(self.rows, wrong)

    def test_roadmap_exit_gate_must_belong_to_same_checkpoint(self):
        wrong = self.roadmap.replace("| G00 | G00 |", "| G00 | F00 |")
        with self.assertRaisesRegex(ValueError, "Roadmap exit gate checkpoint mismatch"):
            audit.verify_phases(self.rows, wrong)

    def test_only_named_canonical_ledger_supplies_assignments(self):
        extra = "\n## Unrelated example\n| 0 | G00 | G00 | proof | Backlog |\n"
        self.assertEqual(audit.verify_phases(self.rows, self.roadmap + extra), {"0": 1, "1A": 1})


class FeatureInventoryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.rows = audit.parse_catalog((root / "docs/TASK_BREAKDOWN.md").read_text())
        checkpoints = {row["checkpoint"] for row in self.rows.values()}
        self.counts = dict.fromkeys(sorted(checkpoints, key=lambda value: (
            int(value.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")), value)), 1)
        self.feature_map = (root / "docs/FEATURE_SCOPE.md").read_text().split(
            "## Source technology choices", 1)[0]
        self.first = next(line for line in self.feature_map.splitlines()
                          if line.startswith("| Case creation/catalog/access |"))

    def test_complete_original_inventory_passes(self):
        self.assertEqual(audit.verify_feature_checkpoints(self.rows, self.counts, self.feature_map), 37)

    def test_all_u_tasks_prose_reference_is_supported(self):
        dashboard = next(line for line in self.feature_map.splitlines()
                         if line.startswith("| One accessible evidence-first React dashboard |"))
        cells = dashboard.split("|")
        cells[3] = " G01B/all U tasks in the catalog; I09 "
        feature_map = self.feature_map.replace(dashboard, "|".join(cells))
        self.assertEqual(audit.verify_feature_checkpoints(self.rows, self.counts, feature_map), 37)

    def test_numeric_task_ranges_are_rejected(self):
        for reference in ("F00-F09", "F00–F09", "F00—F09", "F00–09"):
            with self.subTest(reference=reference):
                cells = self.first.split("|")
                cells[3] = f" {reference} "
                ranged = "|".join(cells)
                with self.assertRaisesRegex(ValueError, "Feature task references require exact IDs, not ranges"):
                    audit.verify_feature_checkpoints(self.rows, self.counts,
                                                     self.feature_map.replace(self.first, ranged))

    def test_malformed_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "feature inventory header"):
            audit.verify_feature_checkpoints(self.rows, self.counts,
                                             self.feature_map.replace("Checkpoint coverage", "Wrong"))

    def test_missing_capability_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Feature capability coverage"):
            audit.verify_feature_checkpoints(self.rows, self.counts,
                                             self.feature_map.replace(self.first + "\n", ""))

    def test_duplicate_capability_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate feature capability"):
            audit.verify_feature_checkpoints(self.rows, self.counts,
                                             self.feature_map.rstrip() + "\n" + self.first + "\n")

    def test_renamed_capability_is_rejected_even_at_same_count(self):
        with self.assertRaisesRegex(ValueError, "Feature capability coverage"):
            audit.verify_feature_checkpoints(self.rows, self.counts, self.feature_map.replace(
                "Case creation/catalog/access", "Renamed initial capability", 1))

    def test_malformed_feature_row_is_not_skipped(self):
        with self.assertRaisesRegex(ValueError, "Malformed feature inventory row"):
            audit.verify_feature_checkpoints(self.rows, self.counts,
                                             self.feature_map.replace(self.first, self.first + " extra |"))

    def test_indented_wrong_coverage_is_not_skipped(self):
        wrong = "    " + self.first.replace("| 1A |", "| 0 |")
        with self.assertRaisesRegex(ValueError, "Feature checkpoint coverage mismatch"):
            audit.verify_feature_checkpoints(self.rows, self.counts,
                                             self.feature_map.replace(self.first, wrong))

    def test_indented_valid_inventory_passes(self):
        indented = "\n".join("    " + line if line.startswith("|") else line
                             for line in self.feature_map.splitlines())
        self.assertEqual(audit.verify_feature_checkpoints(self.rows, self.counts, indented), 37)

    def test_only_named_inventory_counts_capabilities(self):
        unrelated = "\n## Other inventory\n" + self.first + "\n"
        self.assertEqual(audit.verify_feature_checkpoints(
            self.rows, self.counts, self.feature_map + unrelated), 37)


if __name__ == "__main__":
    unittest.main()
