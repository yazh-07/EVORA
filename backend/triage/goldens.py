"""Canonical synthetic G02 vectors with independently fixed expected outputs.

Not extraction/detector/API results or benchmark measurements. UUIDs, origins,
hashes, timestamps and explanations are synthetic. Expected numbers are literal
review oracles, never calculated by importing the implementation under test.
The complete result wrappers exercise unchanged OpenAPI 0.3.0 wire schemas;
runtime result IDs/timestamps and publication remain later producer work.
"""

CASE_ID = "00000000-0000-4000-8000-000000000001"
OTHER_CASE_ID = "00000000-0000-4000-8000-000000000099"
EVIDENCE_IDS = tuple(f"00000000-0000-4000-8000-{index:012d}" for index in range(10, 17))
ANALYSIS_RUN_ID = "00000000-0000-4000-8000-000000000002"
CREATED_AT = "2026-10-21T12:00:00Z"
FACTOR_NAMES = (
    "relevance", "connectivity", "corroboration", "gap_relevance",
    "source_quality", "conflict_relevance", "temporal_proximity",
)
# Independent literal oracle: do not replace with BASE_WEIGHTS or policy calls.
WEIGHTS = (0.25, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05)
SYNTHETIC_REASON = "Synthetic supported policy input; producer integration pending."


def _result(index, score, band, value, contributions):
    """Assemble literal expected wire data; performs no scoring calculation."""
    return {
        "id": f"00000000-0000-4000-8000-{100 + index:012d}",
        "case_id": CASE_ID,
        "evidence_id": EVIDENCE_IDS[index],
        "analysis_run_id": ANALYSIS_RUN_ID,
        "score": score,
        "priority": band,
        "factors": [{
            "name": name, "value": value, "weight": weight,
            "contribution": contribution, "explanation": SYNTHETIC_REASON,
            "evidence_ids": [EVIDENCE_IDS[index]],
        } for name, weight, contribution in zip(FACTOR_NAMES, WEIGHTS, contributions)],
        "explanation": (
            f"g02-triage-v1: {score:.2f} from available factors; absent factors omitted. "
            "Investigative attention only; not truth, identity or guilt."
        ),
        "created_at": CREATED_AT,
    }


POSITIVE_OUTPUTS = (
    _result(0, 90.0, "P1", 0.9, (22.5, 18.0, 13.5, 13.5, 9.0, 9.0, 4.5)),
    _result(1, 70.0, "P2", 0.7, (17.5, 14.0, 10.5, 10.5, 7.0, 7.0, 3.5)),
    _result(2, 50.0, "P3", 0.5, (12.5, 10.0, 7.5, 7.5, 5.0, 5.0, 2.5)),
    _result(3, 20.0, "P4", 0.2, (5.0, 4.0, 3.0, 3.0, 2.0, 2.0, 1.0)),
)

# One independent additional source => 1/3; repeated records => no boost.
INDEPENDENT_SUPPORT = (
    {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[0], "origin_id": "synthetic-camera",
     "sha256": "a" * 64, "record_sha256": "1" * 64},
    {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[1], "origin_id": "synthetic-network",
     "sha256": "b" * 64, "record_sha256": "2" * 64},
)

FALSE_CORROBORATION_CONTROL = {
    "sources": (
        INDEPENDENT_SUPPORT[0],
        # Same original bytes uploaded under a different UUID/origin label.
        {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[1], "origin_id": "synthetic-copy",
         "sha256": "a" * 64, "record_sha256": "3" * 64},
        # Re-exported identical record with different bytes/origin declaration.
        {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[2], "origin_id": "synthetic-reexport",
         "sha256": "c" * 64, "record_sha256": "1" * 64},
    ),
    "expected_value": 0.0, "expected_score": 0.0, "expected_priority": "P4",
}

MEDIA_DERIVATIVE_CONTROL = {
    "sources": (
        INDEPENDENT_SUPPORT[0],  # Original video visual observation.
        {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[1], "origin_id": "synthetic-camera",
         "sha256": "d" * 64},  # Extracted audio has changed bytes, same origin.
        {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[2], "origin_id": "synthetic-camera",
         "sha256": "e" * 64},  # Machine transcript.
        {"case_id": CASE_ID, "evidence_id": EVIDENCE_IDS[3], "origin_id": "synthetic-camera",
         "sha256": "f" * 64},  # Human correction / reprocessed variant.
    ),
    "expected_value": 0.0, "expected_score": 0.0, "expected_priority": "P4",
}

UNPROCESSED_CONTROL = {
    "evidence_id": EVIDENCE_IDS[4], "observation_count": 0,
    "factor_values": {"relevance": 1.0, "connectivity": 1.0},
    "expected_result": None,  # Not a zero/P4 result, even with supplied factors.
    "expected_entry": {"evidence_id": EVIDENCE_IDS[4]},
}

TIE_BREAKING_CONTROL = {
    "input": ((EVIDENCE_IDS[2], 60.0), (EVIDENCE_IDS[4], None),
              (EVIDENCE_IDS[1], 60.0), (EVIDENCE_IDS[5], None),
              (EVIDENCE_IDS[0], 0.0), (EVIDENCE_IDS[3], 80.0)),
    "expected_order": (EVIDENCE_IDS[3], EVIDENCE_IDS[1], EVIDENCE_IDS[2],
                       EVIDENCE_IDS[0], EVIDENCE_IDS[4], EVIDENCE_IDS[5]),
}

# Regression for preserved per-factor rounding versus final schema score cap.
ROUNDING_CAP_CONTROL = {
    "factor_values": {"corroboration": 1.0, "gap_relevance": 1.0,
                      "temporal_proximity": 1.0},
    "expected_contributions": (42.86, 42.86, 14.29),
    "expected_score": 100.0,
}

# Policy-level rank expectations for later real feedback integration. Each input
# is a declared synthetic double, not a claim about the CSVs or a live detector.
FEEDBACK_CONTROLS = (
    {"path": "new_upload", "before": (0.2, 0.2), "after": (0.9, 0.8),
     "expected_before_score": 20.0, "expected_after_score": 85.56,
     "expected_after_priority": "P1"},
    {"path": "detector", "before": (0.2, 0.2), "after": (0.9, 0.2),
     "expected_before_score": 20.0, "expected_after_score": 58.89,
     "expected_after_priority": "P3"},
    {"path": "existing_evidence_reprocessing", "before": (0.2, 0.2), "after": (0.9, 0.8),
     "expected_before_score": 20.0, "expected_after_score": 85.56,
     "expected_after_priority": "P1"},
)
