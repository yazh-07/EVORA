"""I04 exact labeled evaluation, independent of storage and extraction producers.

Callers supply hashable semantic labels from one authorized case/snapshot, with
source identity included (and row/span for occurrence evaluation). Do not compare
generated record UUIDs or infer labels from the predictions. Link labels should
include the rule and sorted, source-specific endpoints. These pure calculators
neither select case data nor interpret candidate confidence as measured quality.
"""
from collections import Counter
from collections.abc import Hashable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def metrics_from_counts(
    true_positives: int, false_positives: int, false_negatives: int,
) -> EvaluationMetrics:
    """Calculate micro metrics; undefined precision/recall/F1 are 0.0.

    Empty controls therefore cannot satisfy a positive quality gate. Counts must
    be nonnegative integers, excluding booleans. No smoothing or rounding applies.
    """
    counts = (true_positives, false_positives, false_negatives)
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("Evaluation counts must be nonnegative integers")
    predicted = true_positives + false_positives
    expected = true_positives + false_negatives
    denominator = 2 * true_positives + false_positives + false_negatives
    return EvaluationMetrics(
        true_positives, false_positives, false_negatives,
        true_positives / predicted if predicted else 0.0,
        true_positives / expected if expected else 0.0,
        2 * true_positives / denominator if denominator else 0.0,
    )


def calculate_metrics(
    predicted: Iterable[Hashable], expected: Iterable[Hashable],
) -> EvaluationMetrics:
    """Match exact labels one-to-one, preserving duplicate multiplicity.

    Each prediction consumes at most one gold occurrence. Extra duplicates are
    false positives, missing duplicates are false negatives. Inputs may be
    generators and are consumed once without modification. Use this separately
    for entities, events, links, source strata or exact text mention spans; sum
    TP/FP/FN before calling metrics_from_counts for a micro aggregate.
    """
    predictions, labels = Counter(predicted), Counter(expected)
    true_positives = sum((predictions & labels).values())
    return metrics_from_counts(
        true_positives,
        sum(predictions.values()) - true_positives,
        sum(labels.values()) - true_positives,
    )
