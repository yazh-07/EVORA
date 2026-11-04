"""I08 Comprehensive multi-modal evaluation suite across all supported modalities and explanations.

Aggregates:
- Extraction & entity/event metrics (I04)
- Detector finding precision/recall/F1 (I05B)
- Triage ranking, MRR, consistency, and weight sensitivity (I05)
- RAG grounding, citation precision, and rejection rates (I05C)
"""
import json
import os
from pathlib import Path
import unittest

from backend.evaluation import (
    calculate_metrics,
    evaluate_detector_findings,
    evaluate_rag_grounding,
    evaluate_triage_ranking,
    evaluate_weight_sensitivity,
    metrics_from_counts,
    rank_consistency_correlation,
)


class ComprehensiveEvaluationSuite(unittest.TestCase):
    def test_i08_multi_modal_extraction_metrics(self):
        # Multi-modal extraction benchmark
        entities = calculate_metrics(
            predicted=["device:D-7", "device:D-8", "ip:203.0.113.7", "account:AC-007"],
            expected=["device:D-7", "device:D-8", "ip:203.0.113.7", "account:AC-007"]
        )
        self.assertEqual(entities.precision, 1.0)
        self.assertEqual(entities.recall, 1.0)
        self.assertEqual(entities.f1, 1.0)

    def test_i08_detector_findings_evaluation(self):
        from backend.evaluation import detector_finding_label
        predicted = [
            {"kind": "conflict", "rule": "conflict_simultaneous_location:v1", "evidence_ids": ["e1", "e2"], "observation_ids": ["o1", "o2"], "entity_ids": [], "contradicting_evidence_ids": ["e2"]},
            {"kind": "gap", "rule": "gap_sequence_interval:v1", "evidence_ids": ["e1"], "observation_ids": ["o1"], "entity_ids": [], "contradicting_evidence_ids": []},
            {"kind": "cluster", "rule": "cluster_connected_component:v1", "evidence_ids": ["e1", "e2"], "observation_ids": ["o1", "o2"], "entity_ids": [], "contradicting_evidence_ids": []},
        ]
        expected = [detector_finding_label(p) for p in predicted]
        results = evaluate_detector_findings(predicted, expected)
        self.assertIn("conflict", results)
        self.assertIn("gap", results)
        self.assertIn("cluster", results)
        for kind in ("conflict", "gap", "cluster"):
            self.assertEqual(results[kind].precision, 1.0)
            self.assertEqual(results[kind].recall, 1.0)
            self.assertEqual(results[kind].f1, 1.0)

    def test_i08_triage_ranking_and_sensitivity(self):
        # Triage ranking evaluation
        ranking = ["ev-lead", "ev-corroborating", "ev-background"]
        relevant = {"ev-lead", "ev-corroborating"}
        triage_metrics = evaluate_triage_ranking(ranking, relevant, k=2)
        self.assertEqual(triage_metrics["top_k_recall"], 1.0)
        self.assertEqual(triage_metrics["precision_at_k"], 1.0)
        self.assertEqual(triage_metrics["reciprocal_rank"], 1.0)

        # Rank consistency
        correlation = rank_consistency_correlation(ranking, ranking)
        self.assertEqual(correlation, 1.0)

        # Weight sensitivity
        baseline = {"ev-lead": 45.0, "ev-corroborating": 30.0, "ev-background": 10.0}
        perturbed = {"ev-lead": 42.0, "ev-corroborating": 32.0, "ev-background": 10.0}
        sensitivity = evaluate_weight_sensitivity(baseline, perturbed)
        self.assertEqual(sensitivity["max_rank_drift"], 0)
        self.assertEqual(sensitivity["rank_correlation"], 1.0)

    def test_i08_rag_grounding_evaluation(self):
        benchmarks = [
            {"expected_supported": True, "supported": True, "citations": [{"evidence_id": "e1", "source_locator": "line 1"}]},
            {"expected_supported": False, "supported": False, "citations": []},
            {"expected_supported": True, "supported": True, "citations": [{"evidence_id": "e2", "source_locator": "row 5"}]},
        ]
        rag_metrics = evaluate_rag_grounding(benchmarks)
        self.assertEqual(rag_metrics["grounding_rate"], 1.0)
        self.assertEqual(rag_metrics["citation_precision"], 1.0)
        self.assertEqual(rag_metrics["unsupported_rejection_rate"], 1.0)
