"""Exact labeled extraction and detector evaluation, independent of storage.

Callers supply hashable semantic labels from one authorized case/snapshot, with
source identity included (and row/span for occurrence evaluation). Do not compare
generated record UUIDs or infer labels from the predictions. Link labels should
include the rule and sorted, source-specific endpoints. These pure calculators
neither select case data nor interpret candidate confidence as measured quality.
"""
from collections import Counter
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

from backend.graph_links import Finding


DETECTOR_KINDS = ('conflict', 'gap', 'anomaly', 'cluster', 'corroboration', 'hypothesis')
_DETECTOR_REFERENCES = ('evidence_ids', 'observation_ids', 'entity_ids',
                        'contradicting_evidence_ids')


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


def _detector_label(parts: tuple) -> tuple:
    if len(parts) != 6:
        raise ValueError('Detector labels must contain kind, rule and four reference tuples')
    kind, rule, *references = parts
    if not isinstance(kind, str) or kind not in DETECTOR_KINDS:
        raise ValueError('Unsupported detector kind')
    if not isinstance(rule, str) or not rule.strip():
        raise ValueError('Detector rule must be nonempty text')
    normalized = []
    for field, values in zip(_DETECTOR_REFERENCES, references):
        if (not isinstance(values, (list, tuple))
                or any(not isinstance(value, str) or not value.strip() for value in values)):
            raise ValueError(f'{field} must contain text references')
        if (field == 'evidence_ids' and not values) or len(set(values)) != len(values):
            raise ValueError(f'{field} must contain unique references; evidence_ids cannot be empty')
        normalized.append(tuple(sorted(values)))
    if not set(normalized[3]) <= set(normalized[0]):
        raise ValueError('Contradicting evidence must be cited by the finding')
    return (kind, rule, *normalized)


def detector_finding_label(finding: dict | Finding) -> tuple:
    """Return a hashable detector label for one frozen input snapshot.

    Layout: (kind, rule, sorted evidence IDs, sorted observation IDs, sorted
    entity IDs, sorted contradicting evidence IDs), with each ID group a tuple.
    Observation citations distinguish intervals/rows; entity membership separates
    components; opposition separates competing hypotheses. Finding/run UUIDs,
    prose (which can embed parent finding UUIDs), confidence and private factor
    assessments are excluded. Missing optional reference groups become ().

    Source observation/entity IDs must refer to the same frozen snapshot on both
    sides. Re-extracted snapshots need caller-supplied stable source mappings.
    The evaluation unit is the rule/citation/membership group, with multiplicity;
    it does not grade free-text explanations or identify an outlier within a
    shared cited baseline. Unsupported kinds, including relationship, fail.
    """
    if isinstance(finding, Finding):
        finding = finding.to_wire()
    if not isinstance(finding, dict):
        raise ValueError('Detector finding must be a dict or Finding')
    return _detector_label((finding.get('kind'), finding.get('rule'),
        finding.get('evidence_ids'), *(finding.get(field, ()) for field in _DETECTOR_REFERENCES[1:])))


def evaluate_detector_findings(
    predicted_findings: Iterable[dict | Finding],
    expected_findings: Iterable[Hashable | tuple],
) -> dict[str, EvaluationMetrics]:
    """Evaluate independently labeled detector groups per kind, including empties.

    Expected values use detector_finding_label's six-element tuple layout. Gold
    labels must be authored from inputs, not derived from predicted findings.
    Reference order is ignored, but rule versions, citations, membership and
    opposition match exactly. Duplicate predictions/labels retain multiplicity.
    Iterables are consumed once without mutation. Callers authorize and select
    one case/snapshot and filter out non-detector findings before calling.
    """
    predictions = {kind: [] for kind in DETECTOR_KINDS}
    labels = {kind: [] for kind in DETECTOR_KINDS}
    for finding in predicted_findings:
        label = detector_finding_label(finding)
        predictions[label[0]].append(label)
    for expected in expected_findings:
        if not isinstance(expected, tuple):
            raise ValueError('Expected detector finding must be a semantic label tuple')
        label = _detector_label(expected)
        labels[label[0]].append(label)
    return {kind: calculate_metrics(predictions[kind], labels[kind]) for kind in DETECTOR_KINDS}
