"""Regression checks for phase planning only, not EVORA application behavior."""
import unittest

import verify_coordination as audit


class PhasePlanTests(unittest.TestCase):
    def test_catalog_retains_checkpoint_membership(self):
        try:
            rows = audit.parse_catalog(
                "| G00 | base | — | contract | check | 0 |\n"
                "| F00 | auth | G00 | `ApiError` | check | 1A |\n"
            )
        except ValueError as error:
            self.fail(f"Checkpoint column is not supported: {error}")
        self.assertEqual(rows["F00"].get("checkpoint"), "1A")
        self.assertEqual(rows["F00"]["dependencies"], {"G00"})

    def plan(self):
        rows = audit.parse_catalog(
            "| G00 | base | — | contract | check | 0 |\n"
            "| F00 | auth | G00 | `ApiError` | check | 1A |\n"
        )
        roadmap = (
            "## Exact checkpoint ledger\n\n"
            "| Checkpoint | Exact task membership | Exit gate IDs | Exit evidence | State |\n"
            "|---|---|---|---|---|\n"
            "| 0 | G00 | G00 | skeleton proof | Backlog |\n"
            "| 1A | F00 | F00 | intake proof | Backlog |\n"
        )
        return rows, roadmap

    def test_valid_plan_matches_catalog_and_roadmap(self):
        self.assertTrue(callable(getattr(audit, "verify_phases", None)),
                        "Phase verifier is not implemented")
        rows, roadmap = self.plan()
        self.assertEqual(audit.verify_phases(rows, roadmap), {"0": 1, "1A": 1})

    def test_later_checkpoint_prerequisite_is_rejected(self):
        rows, roadmap = self.plan()
        rows["G00"]["dependencies"] = {"F00"}
        rows["F00"]["dependencies"] = set()
        with self.assertRaisesRegex(ValueError, "Later checkpoint prerequisite"):
            audit.verify_phases(rows, roadmap)

    def test_out_of_order_checkpoints_are_rejected(self):
        rows, roadmap = self.plan()
        for row in rows.values():
            row["dependencies"] = set()
        with self.assertRaisesRegex(ValueError, "Checkpoint order"):
            lines = roadmap.splitlines()
            audit.verify_phases(rows, "\n".join(lines[:4] + list(reversed(lines[4:]))))

    def test_missing_assignment_is_rejected(self):
        rows, roadmap = self.plan()
        with self.assertRaisesRegex(ValueError, "Unassigned phase"):
            audit.verify_phases(rows, "\n".join(roadmap.splitlines()[:-1]))

    def test_duplicate_task_assignment_is_rejected(self):
        rows, roadmap = self.plan()
        with self.assertRaisesRegex(ValueError, "Duplicate phase assignment"):
            audit.verify_phases(rows, roadmap.replace("| F00 |", "| G00, F00 |"))

    def test_unknown_assignment_is_rejected(self):
        rows, roadmap = self.plan()
        with self.assertRaisesRegex(ValueError, "Unknown checkpoint task"):
            audit.verify_phases(rows, roadmap.replace("F00", "F99"))

    def test_catalog_checkpoint_drift_is_rejected(self):
        rows, roadmap = self.plan()
        rows["F00"]["checkpoint"] = "0"
        with self.assertRaisesRegex(ValueError, "Checkpoint mismatch"):
            audit.verify_phases(rows, roadmap)

    def test_task_ranges_are_rejected(self):
        rows, roadmap = self.plan()
        with self.assertRaisesRegex(ValueError, "exact task IDs"):
            audit.verify_phases(rows, roadmap.replace("F00", "F00–F09"))

    def test_duplicate_checkpoint_is_rejected(self):
        rows, roadmap = self.plan()
        with self.assertRaisesRegex(ValueError, "Duplicate checkpoint"):
            audit.verify_phases(rows, roadmap + roadmap.splitlines()[4] + "\n")

    def test_empty_plan_is_rejected(self):
        rows, _ = self.plan()
        with self.assertRaisesRegex(ValueError, "Missing.*heading"):
            audit.verify_phases(rows, "# No checkpoints\n")


if __name__ == "__main__":
    unittest.main()
