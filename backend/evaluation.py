"""Exact labeled extraction, detector and triage evaluation, independent of storage.

Callers supply hashable semantic labels from one authorized case/snapshot, with
source identity included (and row/span for occurrence evaluation). Do not compare
generated record UUIDs or infer labels from the predictions. Link labels should
include the rule and sorted, source-specific endpoints. These pure calculators
neither select case data nor interpret candidate confidence as measured quality.
"""
from collections import Counter
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
import math

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


def _evidence_ids(values: Iterable[str], *, unique: bool = True) -> list[str]:
    identifiers = list(values)
    if any(not isinstance(value, str) or not value.strip() for value in identifiers):
        raise ValueError('Evaluation evidence IDs must be nonblank strings')
    if unique and len(set(identifiers)) != len(identifiers):
        raise ValueError('Rankings must contain unique evidence IDs')
    return identifiers


def evaluate_triage_ranking(
    ranked_evidence_ids: list[str], relevant_evidence_ids: set[str] | list[str], k: int = 5,
) -> dict:
    """Evaluate one caller-authorized ranking against independently authored gold.

    Recall divides relevant hits in the first k positions by ALL gold items,
    including missing predictions. Precision divides by k, even for short lists.
    Reciprocal rank uses the first relevant position in the FULL ranking; average
    it across cases/queries for MRR. Empty gold/predictions yield zero, never a
    passing quality gate. Duplicate predictions fail; duplicate gold labels count
    once. Unscored items should be omitted by the caller, not assigned scores.
    No universal threshold is implied: gates require predeclared scenario gold,
    k and targets, alongside unrelated/empty and feedback-path controls.
    """
    if type(k) is not int or k <= 0:
        raise ValueError('k must be a positive integer')
    ranked = _evidence_ids(ranked_evidence_ids)
    relevant = set(_evidence_ids(relevant_evidence_ids, unique=False))
    hits = len(set(ranked[:k]) & relevant)
    return dict(top_k_recall=hits / len(relevant) if relevant else 0.0,
                precision_at_k=hits / k,
                reciprocal_rank=next((1 / rank for rank, eid in enumerate(ranked, 1)
                                      if eid in relevant), 0.0))


def rank_consistency_correlation(ranking_a: list[str], ranking_b: list[str]) -> float:
    """Spearman rho on complete, unique rankings of the SAME evidence universe.

    Callers resolve ties consistently before supplying ranks. Different item sets
    fail rather than silently dropping missing evidence. For fewer than two
    items rho is undefined and reported as 0.0, not evidence of consistency.
    """
    first, second = _evidence_ids(ranking_a), _evidence_ids(ranking_b)
    if set(first) != set(second):
        raise ValueError('Rank consistency requires identical evidence membership')
    n = len(first)
    if n < 2:
        return 0.0
    positions = {eid: rank for rank, eid in enumerate(second)}
    squared_drift = sum((rank - positions[eid]) ** 2 for rank, eid in enumerate(first))
    return 1.0 - 6 * squared_drift / (n * (n * n - 1))


def evaluate_weight_sensitivity(
    baseline_scores: dict[str, float], perturbed_scores: dict[str, float],
) -> dict:
    """Measure supplied experimental scores; never infer weights or absent scores.

    Hold the scored evidence universe and frozen producer inputs fixed; callers
    compute both score sets with their declared factor weights. Scores must be
    finite. Rank by descending score then evidence ID ascending, matching triage
    tie ordering for canonical UUIDs. Positive rank_changes mean demotion, and
    score_changes are perturbed minus baseline. Report raw absolute drift and
    score movement without claiming statistical significance or real-world truth.
    Inputs are neither modified nor persisted; empty controls return zero metrics.
    """
    for scores in (baseline_scores, perturbed_scores):
        _evidence_ids(scores)
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in scores.values()):
            raise ValueError('Sensitivity scores must be finite numbers')
    baseline = sorted(baseline_scores, key=lambda eid: (-baseline_scores[eid], eid))
    perturbed = sorted(perturbed_scores, key=lambda eid: (-perturbed_scores[eid], eid))
    correlation = rank_consistency_correlation(baseline, perturbed)
    positions = {eid: rank for rank, eid in enumerate(perturbed)}
    rank_changes = {eid: positions[eid] - rank for rank, eid in enumerate(baseline)}
    score_changes = {eid: perturbed_scores[eid] - baseline_scores[eid] for eid in baseline}
    n = len(baseline)
    return dict(rank_correlation=correlation, rank_changes=rank_changes,
                mean_absolute_rank_drift=sum(map(abs, rank_changes.values())) / n if n else 0.0,
                max_rank_drift=max(map(abs, rank_changes.values()), default=0),
                score_changes=score_changes,
                mean_absolute_score_change=math.fsum(map(abs, score_changes.values())) / n if n else 0.0,
                max_absolute_score_change=max(map(abs, score_changes.values()), default=0.0))


def evaluate_rag_grounding(benchmark_results: Iterable[dict]) -> dict:
    """Evaluate grounding rate, citation correctness, and unsupported rejection accuracy (I05C)."""
    total = 0
    supported_total = 0
    grounded_supported = 0
    correct_citations = 0
    total_citations = 0
    unsupported_total = 0
    correct_unsupported = 0

    for result in benchmark_results:
        total += 1
        is_expected_supported = result.get("expected_supported", True)
        actual_supported = result.get("supported", False)
        citations = result.get("citations", [])

        if is_expected_supported:
            supported_total += 1
            if actual_supported and len(citations) > 0:
                grounded_supported += 1
                for cit in citations:
                    total_citations += 1
                    if cit.get("evidence_id") and cit.get("source_locator"):
                        correct_citations += 1
        else:
            unsupported_total += 1
            if not actual_supported and len(citations) == 0:
                correct_unsupported += 1

    return {
        "total_evaluations": total,
        "grounding_rate": grounded_supported / supported_total if supported_total else 1.0,
        "citation_precision": correct_citations / total_citations if total_citations else 1.0,
        "unsupported_rejection_rate": correct_unsupported / unsupported_total if unsupported_total else 1.0,
    }
