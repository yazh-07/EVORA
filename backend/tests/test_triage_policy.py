"""G02 pure-policy behavior and real-bundle schemas; no live producer doubles hidden."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from itertools import combinations, permutations
import json
import os
from pathlib import Path
import re
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from backend.triage import goldens as g
from backend.triage import policy as p


BAD_NUMBERS = (-0.01, 1.01, float("nan"), float("inf"), -float("inf"), True, "0.5")
FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=ValueError)
def fixture_datetime(value):
    # The pinned minimal jsonschema install lacks its optional RFC3339 checker.
    # Explicitly check fixture timestamps rather than silently accepting any text.
    if not isinstance(value, str):
        return True
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        return False
    return datetime.fromisoformat(value.upper()).tzinfo is not None


def inputs(values, evidence_id=g.EVIDENCE_IDS[0]):
    return {name: p.FactorValue(value, g.SYNTHETIC_REASON, (evidence_id,))
            for name, value in values.items()}


def score(values, *, count=1, evidence_id=g.EVIDENCE_IDS[0]):
    return p.score_evidence(evidence_id=evidence_id, observation_count=count,
                            factors=inputs(values, evidence_id), case_evidence_ids=g.EVIDENCE_IDS)


def wire_result(scored, template=g.POSITIVE_OUTPUTS[0]):
    result = deepcopy(template)
    result.update(score=scored.score, priority=scored.priority,
                  factors=list(scored.factors), explanation=scored.explanation)
    return result


class FactorFunctions(unittest.TestCase):
    def test_relevance_ratio_dedup_missing_and_negative(self):
        self.assertEqual(p.relevance(["device:D-7"] * 20, ["device:D-7", "device:D-8"]), 0.5)
        self.assertEqual(p.relevance(["D-7"], ["D-7"] * 2), 1)
        self.assertEqual(p.relevance([], ["D-7"]), 0)
        self.assertIsNone(p.relevance([], []))
        self.assertIsNone(p.relevance(None, ["D-7"]))
        self.assertIsNone(p.relevance([], None))
        for matched, known in ((["D-8"], ["D-7"]), ([" "], [" "]), ([None], [None])):
            with self.subTest(matched=matched), self.assertRaises(ValueError):
                p.relevance(matched, known)

    def test_connectivity_distinct_supported_neighbors_and_saturation(self):
        ids = [f"00000000-0000-4000-8000-{index:012d}" for index in range(20)]
        for count, expected in ((0, 0), (1, 0.1), (5, 0.5), (10, 1), (20, 1)):
            self.assertEqual(p.connectivity(ids[:count] * 3), expected)
        self.assertIsNone(p.connectivity(None))
        with self.assertRaises(ValueError):
            p.connectivity(["anonymous-node"])

    def test_gap_coverage_match_maximum_not_count_or_nonoccurrence(self):
        for values, expected in (([], 0), ([0], 0), ([0.2, 0.8, 0.8], 0.8), ([1], 1)):
            self.assertEqual(p.gap_relevance(values), expected)
        self.assertIsNone(p.gap_relevance(None))

    def test_conflict_strength_maximum_and_unknown(self):
        self.assertIsNone(p.conflict_relevance(None))
        self.assertEqual(p.conflict_relevance([]), 0)
        self.assertEqual(p.conflict_relevance([0.3, 0.6, 0.6]), 0.6)
        self.assertEqual(p.conflict_relevance([1]), 1)

    def test_source_quality_explicit_unknown_and_bounds(self):
        self.assertIsNone(p.source_quality(None))
        for value in (0, 0.3, 1):
            self.assertEqual(p.source_quality(value), value)
        for bad in BAD_NUMBERS:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.source_quality(bad)

    def test_strength_functions_reject_bad_inputs_without_clamping(self):
        for function in (p.gap_relevance, p.conflict_relevance):
            for bad in BAD_NUMBERS:
                with self.subTest(function=function.__name__, bad=bad), self.assertRaises(ValueError):
                    function([bad])

    def test_temporal_window_symmetric_missing_and_precision_controls(self):
        for delta, expected in ((0, 1), (43200, 0.5), (-43200, 0.5),
                                (86400, 0), (-86400, 0), (172800, 0)):
            self.assertEqual(p.temporal_proximity(delta), expected)
        self.assertIsNone(p.temporal_proximity(None))
        # Includes timezone ambiguity, uncertain clocks and media-only offsets.
        self.assertIsNone(p.temporal_proximity(0, comparable=False))
        for bad in (float("nan"), float("inf"), True, "2026-10-21T12:00:00Z"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.temporal_proximity(bad)
        with self.assertRaises(ValueError):
            p.temporal_proximity(0, comparable="unknown")

    def test_anomaly_maps_once_and_merge_is_idempotent(self):
        for conflict, relevant, expected in ((True, True, "conflict_relevance"),
                                            (True, False, "conflict_relevance"),
                                            (False, True, "relevance"), (False, False, None)):
            self.assertEqual(p.anomaly_factor(potential_conflict=conflict, case_relevant=relevant), expected)
        self.assertEqual(p.merge_anomaly(None, 0.7), 0.7)
        self.assertEqual(p.merge_anomaly(0.8, 0.7), 0.8)
        self.assertEqual(p.merge_anomaly(p.merge_anomaly(0.2, 0.7), 0.7), 0.7)
        for bad in BAD_NUMBERS:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.merge_anomaly(None, bad)
            with self.assertRaises(ValueError):
                p.merge_anomaly(bad, 0.5)
        with self.assertRaises(ValueError):
            p.anomaly_factor(potential_conflict=1, case_relevant=True)


class SourceIndependence(unittest.TestCase):
    def setUp(self):
        self.target, self.other = (p.SourceSupport(**source) for source in g.INDEPENDENT_SUPPORT)

    def test_independent_sources_saturate_at_three_additional_origins(self):
        support = [replace(self.other, evidence_id=g.EVIDENCE_IDS[index + 1],
                           origin_id=f"independent-{index}", sha256=str(index + 2) * 64,
                           record_sha256=None) for index in range(4)]
        for count, expected in ((0, 0), (1, 1 / 3), (2, 2 / 3), (3, 1), (4, 1)):
            self.assertEqual(p.corroboration(self.target, support[:count]), expected)
        self.assertEqual(p.corroboration(self.target, [self.other] * 100), 1 / 3)

    def test_canonical_false_corroboration_and_media_derivative_controls(self):
        for control in (g.FALSE_CORROBORATION_CONTROL, g.MEDIA_DERIVATIVE_CONTROL):
            sources = [p.SourceSupport(**source) for source in control["sources"]]
            value = p.corroboration(sources[0], sources[1:])
            self.assertEqual(value, control["expected_value"])
            result = score({"corroboration": value})
            self.assertEqual(result.score, control["expected_score"])
            self.assertEqual(result.priority, control["expected_priority"])

    def test_each_independence_key_is_sufficient_without_other_matches(self):
        variants = (
            replace(self.other, evidence_id=self.target.evidence_id),
            replace(self.other, origin_id=self.target.origin_id),
            replace(self.other, sha256=self.target.sha256),
            replace(self.other, record_sha256=self.target.record_sha256),
        )
        for duplicate in variants:
            self.assertEqual(p.corroboration(self.target, [duplicate]), 0)

    def test_transitive_duplicates_are_order_independent(self):
        # A -> B through bytes; B -> C through origin; C -> D through record.
        b = replace(self.other, sha256=self.target.sha256)
        c = replace(self.other, evidence_id=g.EVIDENCE_IDS[2], sha256="c" * 64,
                    record_sha256="3" * 64)
        d = replace(c, evidence_id=g.EVIDENCE_IDS[3], origin_id="another-origin", sha256="d" * 64)
        for sources in permutations((b, c, d)):
            self.assertEqual(p.corroboration(self.target, sources), 0)

    def test_unknown_independence_cannot_add_corroboration(self):
        self.assertIsNone(p.corroboration(self.target, None))
        self.assertIsNone(p.corroboration(replace(self.target, origin_id=None), [self.other]))
        self.assertEqual(p.corroboration(self.target, [replace(self.other, origin_id=None)]), 0)

    def test_foreign_case_rejected_even_with_unknown_target(self):
        foreign = replace(self.other, case_id=g.OTHER_CASE_ID)
        for target in (self.target, replace(self.target, origin_id=None)):
            with self.assertRaises(ValueError):
                p.corroboration(target, [foreign])

    def test_invalid_lineage_digests_and_identifiers_fail_closed(self):
        for changes in ({"origin_id": " "}, {"sha256": None}, {"sha256": "a" * 63},
                        {"sha256": "A" * 64}, {"record_sha256": "bad"},
                        {"evidence_id": "not-a-uuid"}, {"case_id": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.target, **changes)


class ScoringPolicy(unittest.TestCase):
    def test_base_weights_exact_names_and_sum(self):
        self.assertEqual(tuple(p.BASE_WEIGHTS), g.FACTOR_NAMES)
        self.assertEqual(tuple(p.BASE_WEIGHTS.values()), g.WEIGHTS)
        self.assertAlmostEqual(sum(p.BASE_WEIGHTS.values()), 1)
        with self.assertRaises(TypeError):
            p.BASE_WEIGHTS["relevance"] = 0.5

    def test_initial_two_factors_proportional_normalization(self):
        result = score({"relevance": 0.8, "connectivity": 0.5})
        self.assertEqual([factor["weight"] for factor in result.factors], [0.25 / 0.45, 0.20 / 0.45])
        self.assertEqual([factor["contribution"] for factor in result.factors], [44.44, 22.22])
        self.assertEqual((result.score, result.priority), (66.66, "P2"))

    def test_absent_distinct_from_measured_zero_and_empty_is_unscored(self):
        self.assertEqual(score({"relevance": 1}).score, 100)
        self.assertEqual(score({"relevance": 1, "connectivity": 0}).score, 55.56)
        args = dict(evidence_id=g.EVIDENCE_IDS[0], observation_count=1,
                    case_evidence_ids=g.EVIDENCE_IDS)
        result = p.score_evidence(**args, factors={**inputs({"relevance": 1}), "connectivity": None})
        self.assertEqual(result.score, 100)
        self.assertEqual(len(result.factors), 1)
        self.assertIsNone(p.score_evidence(**args, factors={"source_quality": None}))
        self.assertIsNone(score({}))
        self.assertEqual(p.normalized_weights([]), {})

    def test_unprocessed_canonical_control_never_creates_p4(self):
        control = g.UNPROCESSED_CONTROL
        result = score(control["factor_values"], count=control["observation_count"],
                       evidence_id=control["evidence_id"])
        self.assertIs(result, control["expected_result"])

    def test_count_only_gates_and_extraction_confidence_cannot_be_passed_as_quality(self):
        self.assertEqual(score({"relevance": 0.5}, count=1), score({"relevance": 0.5}, count=1000))
        # No confidence/count multiplier or implicit source-quality assessment.
        for name in ("extraction_confidence", "observation_count", "anomaly"):
            with self.assertRaises(ValueError):
                score({name: 1})
        for count in (-1, 1.5, True, "1"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                score({"relevance": 1}, count=count)

    def test_priority_band_boundaries(self):
        for value, band in ((0, "P4"), (39.99, "P4"), (40, "P3"), (59.99, "P3"),
                            (60, "P2"), (79.99, "P2"), (80, "P1"), (100, "P1")):
            self.assertEqual(p.priority(value), band)
            self.assertEqual(score({"relevance": value / 100}).priority, band)
        for bad in (-0.01, 100.01, float("nan"), float("inf"), True, "80"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.priority(bad)

    def test_per_factor_rounding_and_final_cap_preserve_100_01_sum(self):
        control = g.ROUNDING_CAP_CONTROL
        result = score(control["factor_values"])
        self.assertEqual(tuple(factor["contribution"] for factor in result.factors),
                         control["expected_contributions"])
        self.assertEqual(round(sum(factor["contribution"] for factor in result.factors), 2), 100.01)
        self.assertEqual(result.score, control["expected_score"])
        self.assertIn("100.01 capped at 100.00", result.explanation)

    def test_every_factor_subset_normalizes_and_keeps_score_in_schema_range(self):
        for size in range(1, 8):
            for names in combinations(g.FACTOR_NAMES, size):
                with self.subTest(names=names):
                    result = score(dict.fromkeys(names, 1.0))
                    self.assertAlmostEqual(sum(factor["weight"] for factor in result.factors), 1)
                    self.assertLessEqual(result.score, 100)
                    self.assertGreaterEqual(result.score, 99.98)
                    for factor in result.factors:
                        self.assertEqual(factor["contribution"], round(factor["value"] * factor["weight"] * 100, 2))

    def test_input_mapping_order_does_not_change_summation_or_mutate_inputs(self):
        values = {name: 0.83 for name in reversed(g.FACTOR_NAMES)}
        original = deepcopy(values)
        self.assertEqual(score(values), score(dict(reversed(tuple(values.items())))))
        self.assertEqual(values, original)
        self.assertEqual(tuple(factor["name"] for factor in score(values).factors), g.FACTOR_NAMES)

    def test_invalid_values_and_new_names_fail_even_when_unprocessed(self):
        for bad in BAD_NUMBERS:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                score({"relevance": bad})
        for count in (0, 1):
            with self.assertRaises(ValueError):
                score({"fabricated": 0}, count=count)

    def test_factor_sources_and_target_are_same_case_unique_and_valid(self):
        target = g.EVIDENCE_IDS[0]
        for ids in ((), (target, target), ("bad-id",), (g.OTHER_CASE_ID,)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                p.score_evidence(evidence_id=target, observation_count=1,
                                 factors={"relevance": p.FactorValue(0.5, "Synthetic", ids)},
                                 case_evidence_ids=g.EVIDENCE_IDS)
        with self.assertRaises(ValueError):
            score({"relevance": 1}, evidence_id=g.OTHER_CASE_ID)
        with self.assertRaises(ValueError):
            p.score_evidence(evidence_id=target, observation_count=1,
                             factors={"relevance": p.FactorValue(0.5, " ", (target,))},
                             case_evidence_ids=g.EVIDENCE_IDS)

    def test_canonical_sort_ties_zero_and_unscored_last(self):
        control = g.TIE_BREAKING_CONTROL
        result = sorted(control["input"], key=lambda item: p.triage_sort_key(*item))
        self.assertEqual(tuple(identifier for identifier, _ in result), control["expected_order"])
        self.assertEqual(p.triage_sort_key(g.EVIDENCE_IDS[0].upper(), 60),
                         p.triage_sort_key(g.EVIDENCE_IDS[0], 60))
        for bad in (-1, 101, float("nan"), True):
            with self.assertRaises(ValueError):
                p.triage_sort_key(g.EVIDENCE_IDS[0], bad)
        with self.assertRaises(ValueError):
            p.triage_sort_key("not-a-uuid", 50)

    def test_synthetic_feedback_goldens_rerank_and_preserve_previous_output(self):
        competitor = score({"relevance": 0.5, "connectivity": 0.5}, evidence_id=g.EVIDENCE_IDS[1])
        self.assertEqual(competitor.score, 50)
        for control in g.FEEDBACK_CONTROLS:
            with self.subTest(path=control["path"]):
                before = score(dict(zip(("relevance", "connectivity"), control["before"])))
                frozen_before = deepcopy(before)
                after_values = dict(zip(("relevance", "connectivity"), control["after"]))
                if control["path"] == "detector":
                    mapped = p.anomaly_factor(potential_conflict=False, case_relevant=True)
                    after_values[mapped] = p.merge_anomaly(control["before"][0], after_values[mapped])
                after = score(after_values)
                self.assertEqual(before.score, control["expected_before_score"])
                self.assertEqual(after.score, control["expected_after_score"])
                self.assertEqual(after.priority, control["expected_after_priority"])
                self.assertLess(before.score, competitor.score)
                self.assertGreater(after.score, competitor.score)
                self.assertEqual(before, frozen_before)
                self.assertNotEqual(before.explanation, after.explanation)


class ContractGoldens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing env/bundle must fail; no skipped validation or handwritten schema.
        cls.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text(encoding="utf-8"))

    def validator(self, name):
        root = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                "$ref": f"#/components/schemas/{name}", "components": self.spec["components"]}
        Draft202012Validator.check_schema(root)
        return Draft202012Validator(root, format_checker=FORMATS)

    def test_all_canonical_positive_outputs_match_exactly_and_validate(self):
        for expected in g.POSITIVE_OUTPUTS:
            with self.subTest(priority=expected["priority"]):
                values = {factor["name"]: factor["value"] for factor in expected["factors"]}
                result = score(values, evidence_id=expected["evidence_id"])
                actual = wire_result(result, expected)
                self.assertEqual(actual, expected)
                self.validator("TriageResult").validate(actual)
                self.validator("Priority").validate(actual["priority"])
                for factor in actual["factors"]:
                    self.validator("TriageFactor").validate(factor)

    def test_cap_and_all_available_subsets_validate_against_real_bundle(self):
        for size in range(1, 8):
            for names in combinations(g.FACTOR_NAMES, size):
                self.validator("TriageResult").validate(wire_result(score(dict.fromkeys(names, 1))))

    def test_unprocessed_entry_schema_omits_score_and_priority(self):
        entry = g.UNPROCESSED_CONTROL["expected_entry"]
        self.validator("TriageEntry").validate(entry)
        self.assertNotIn("latest_result", entry)
        self.assertNotIn("effective_priority", entry)

    def test_schema_rejects_invalid_factor_ranges_names_ids_and_extra_fields(self):
        validator = self.validator("TriageFactor")
        for field, bad in (("name", "anomaly"), ("value", -0.01), ("value", 1.01),
                           ("weight", -0.01), ("weight", 1.01), ("contribution", 100.01),
                           ("contribution", -0.01), ("evidence_ids", ["bad"]),
                           ("evidence_ids", [g.EVIDENCE_IDS[0]] * 2), ("confidence", 0.8)):
            with self.subTest(field=field, bad=bad):
                factor = deepcopy(g.POSITIVE_OUTPUTS[0]["factors"][0])
                factor[field] = bad
                self.assertFalse(validator.is_valid(factor))

    def test_schema_rejects_invalid_result_and_priority(self):
        for field, bad in (("score", 100.01), ("score", -0.01), ("priority", "P5"),
                           ("evidence_id", "bad"), ("analysis_run_id", "bad"),
                           ("created_at", "not-time"), ("algorithm_version", p.POLICY_VERSION)):
            with self.subTest(field=field):
                result = deepcopy(g.POSITIVE_OUTPUTS[0])
                result[field] = bad
                self.assertFalse(self.validator("TriageResult").is_valid(result))
        self.assertFalse(self.validator("Priority").is_valid("P5"))
        for field in g.POSITIVE_OUTPUTS[0]:
            result = deepcopy(g.POSITIVE_OUTPUTS[0])
            del result[field]
            self.assertFalse(self.validator("TriageResult").is_valid(result))


if __name__ == "__main__":
    unittest.main()
