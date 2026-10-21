"""G02 experimental policy, not a forensic standard or a truth probability.

Only completed, frozen, same-case producer inputs may reach this boundary.
Producers must retain observation IDs/source locators and justify entity matches,
graph neighbors, independent origins, quality assessments and detector strengths.
These pure functions neither extract those inputs nor publish analysis results.

None means unavailable/not evaluated; an evaluated negative is zero and keeps its
weight. No available factors means no result, even with observations. Observation
count only gates scoring (>0); repetitions never directly increase a score.
Extraction confidence (including the media unavailable-score sentinel 0) is an
uncalibrated diagnostic, never source reliability or a score multiplier. Neither
count nor confidence is an eighth factor. Unknown source quality stays absent.
Association/conclusion uncertainty remains separate; co-mentions, spoken claims,
anomalies and high attention scores establish neither identity nor guilt.

Changing any formula/constant requires a new policy version and reviewed goldens.
Store this version in later AnalysisRun.algorithm_version/private provenance,
not an extra TriageResult wire field. A04/A17 own real producer aggregation.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from uuid import UUID


POLICY_VERSION = "g02-triage-v1"
BASE_WEIGHTS = MappingProxyType({
    "relevance": 0.25,
    "connectivity": 0.20,
    "corroboration": 0.15,
    "gap_relevance": 0.15,
    "source_quality": 0.10,
    "conflict_relevance": 0.10,
    "temporal_proximity": 0.05,
})
CONNECTIVITY_SATURATION = 10
CORROBORATION_SATURATION = 3
TEMPORAL_WINDOW_SECONDS = 86400.0
ATTENTION_NOTICE = "Investigative attention only; not truth, identity or guilt."


def _number(value: float, lower: float, upper: float) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not lower <= value <= upper):
        raise ValueError("Expected a finite number in the policy range")
    return float(value)


def _uuid(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a UUID string")
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError("Expected a UUID string") from None


def _keys(values: Iterable[str]) -> set[str]:
    result = set(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError("Expected nonblank source-backed keys")
    return result


def relevance(matched_entities: Iterable[str] | None,
              known_case_entities: Iterable[str] | None) -> float | None:
    """Unique matched known entities / unique known entities, in [0,1].

    Missing evaluation or an empty known set is absent, not unrelatedness.
    Duplicated mentions have no extra effect; unknown matches are input errors.
    """
    if matched_entities is None or known_case_entities is None:
        return None
    matched, known = _keys(matched_entities), _keys(known_case_entities)
    if not matched <= known:
        raise ValueError("Matched entities must belong to the known case set")
    return len(matched) / len(known) if known else None


def connectivity(supported_neighbor_ids: Iterable[str] | None) -> float | None:
    """min(unique supported non-self graph neighbors / 10, 1).

    Caller excludes the target itself and unsupported edges. This is a bounded
    degree measure, independent of scores, never evidence of culpability.
    """
    if supported_neighbor_ids is None:
        return None
    neighbors = {_uuid(identifier) for identifier in supported_neighbor_ids}
    return min(len(neighbors) / CONNECTIVITY_SATURATION, 1.0)


@dataclass(frozen=True)
class SourceSupport:
    """Internal private lineage for one claim's source-backed observation.

    origin_id is an established underlying source origin, never source_label,
    filename, modality or Evidence UUID. None means independence is unknown.
    sha256 is the immutable original Evidence hash. Optional record_sha256 is a
    producer-verified duplicate-record fingerprint (not merely a shared claim).
    Visual/audio/transcript/corrected/reprocessed derivatives inherit origin_id.
    """

    case_id: str
    evidence_id: str
    origin_id: str | None
    sha256: str
    record_sha256: str | None = None

    def __post_init__(self):
        _uuid(self.case_id)
        _uuid(self.evidence_id)
        if self.origin_id is not None and (
                not isinstance(self.origin_id, str) or not self.origin_id.strip()):
            raise ValueError("Origin must be established or explicitly unknown")
        for digest in (self.sha256, self.record_sha256):
            if digest is not None and (not isinstance(digest, str)
                                       or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
                raise ValueError("Expected a lowercase SHA-256 digest")
        if self.sha256 is None:
            raise ValueError("Original evidence hash is required")


def corroboration(target: SourceSupport,
                  supporting_sources: Iterable[SourceSupport] | None) -> float | None:
    """min(additional independent source groups / 3, 1), for ONE claim.

    Count the target once. Collapse transitively on Evidence UUID, established
    origin, original byte hash OR duplicate-record hash. Unknown-origin sources
    never add independence; they can still connect duplicate groups. If target
    origin or evaluation is unknown, return absent. Same-case joins are checked
    even when target independence is unknown. Producers establish that sources
    actually support the same claim; this helper does not infer corroboration
    from an arbitrary collection of evidence or from extraction confidence.
    """
    if supporting_sources is None:
        return None
    sources = [target, *supporting_sources]
    if any(_uuid(source.case_id) != _uuid(target.case_id) for source in sources):
        raise ValueError("Corroboration sources must belong to the same case")
    parents = list(range(len(sources)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    seen = {}
    for index, source in enumerate(sources):
        keys = [("evidence", _uuid(source.evidence_id)), ("bytes", source.sha256)]
        if source.origin_id is not None:
            keys.append(("origin", source.origin_id))
        if source.record_sha256 is not None:
            keys.append(("record", source.record_sha256))
        for key in keys:
            if key in seen:
                parents[root(index)] = root(seen[key])
            else:
                seen[key] = index
    if target.origin_id is None:
        return None
    independent_groups = {root(index) for index, source in enumerate(sources)
                          if source.origin_id is not None}
    return min((len(independent_groups) - 1) / CORROBORATION_SATURATION, 1.0)


def _strongest(strengths: Iterable[float] | None) -> float | None:
    if strengths is None:
        return None
    return max((_number(value, 0, 1) for value in strengths), default=0.0)


def gap_relevance(supported_coverage_matches: Iterable[float] | None) -> float | None:
    """Maximum supported [0,1] coverage match to an identified bounded gap.

    Producer supplies documented overlap fraction (overlap / gap duration) for
    known coverage, or 1/0 for a supported non-temporal information match. No
    candidate coverage/evaluation is None; evaluated no match is zero. Missing
    records alone never prove non-occurrence or a coverage match. No count boost.
    """
    return _strongest(supported_coverage_matches)


def conflict_relevance(supported_conflict_strengths: Iterable[float] | None) -> float | None:
    """Maximum supported potential-conflict relevance in [0,1], no count boost.

    Producer uses 1 for direct participation in a supported unresolved conflict,
    0 for an evaluated nonconflict; time/clock/location-uncertain candidates are
    absent until that rule's uncertainty controls pass. Not source falsity.
    """
    return _strongest(supported_conflict_strengths)


def source_quality(assessed_reliability: float | None) -> float | None:
    """Explicit versioned source-reliability assessment [0,1], unknown absent.

    No default and no inference from label/type, extraction score, count or
    corroboration. A09 must persist the private assessment basis/version; this
    policy does not invent reliability for an uploaded artifact.
    """
    return None if assessed_reliability is None else _number(assessed_reliability, 0, 1)


def temporal_proximity(delta_seconds: float | None, *,
                       comparable: bool = True) -> float | None:
    """max(0, 1 - abs(delta_seconds)/86400), using nearest supported case time.

    Delta is between normalized UTC instants with compatible documented precision
    and resolved timezone/clock mapping. Missing/ambiguous time => absent via
    None or comparable=False. Media offsets, acquisition and processing time do
    not supply event UTC. Both before/after are symmetric; 24h or more => zero.
    """
    if not isinstance(comparable, bool):
        raise ValueError("Time comparability must be explicit boolean")
    if delta_seconds is None:
        return None
    delta = _number(delta_seconds, -float("inf"), float("inf"))
    return max(0.0, 1.0 - abs(delta) / TEMPORAL_WINDOW_SECONDS) if comparable else None


def anomaly_factor(*, potential_conflict: bool, case_relevant: bool) -> str | None:
    """Map a supported anomaly once: conflict first, otherwise case relevance.

    No case relevance and no supported conflict => no score effect. Uncertain or
    false-positive anomalies must be filtered by A13 before this mapping. Merge
    with an existing factor using max (merge_anomaly), never add a new factor or
    count the same anomaly in both factors. Abnormality is not criminality.
    """
    if not isinstance(potential_conflict, bool) or not isinstance(case_relevant, bool):
        raise ValueError("Anomaly mapping requires boolean decisions")
    return "conflict_relevance" if potential_conflict else "relevance" if case_relevant else None


def merge_anomaly(existing: float | None, anomaly_strength: float) -> float:
    """Idempotent max merge of a supported signal into its one mapped factor."""
    strength = _number(anomaly_strength, 0, 1)
    return strength if existing is None else max(_number(existing, 0, 1), strength)


def normalized_weights(available: Iterable[str]) -> dict[str, float]:
    """Proportionally redistribute absent weights; retain evaluated zero values.

    No intermediate rounding. Stable factor order is BASE_WEIGHTS order, which
    is also the serialization/summation order used for reproducible rounding.
    """
    names = set(available)
    if names - BASE_WEIGHTS.keys():
        raise ValueError("Unknown triage factor")
    total = sum(weight for name, weight in BASE_WEIGHTS.items() if name in names)
    return {name: weight / total for name, weight in BASE_WEIGHTS.items() if name in names}


def priority(score: float) -> str:
    """P1 [80,100], P2 [60,80), P3 [40,60), P4 [0,40)."""
    score = _number(score, 0, 100)
    return "P1" if score >= 80 else "P2" if score >= 60 else "P3" if score >= 40 else "P4"


@dataclass(frozen=True)
class FactorValue:
    """Internal producer handoff; None is represented by omission in score input."""

    value: float
    explanation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScoredEvidence:
    score: float
    priority: str
    factors: tuple[dict, ...]
    explanation: str


def score_evidence(*, evidence_id: str, observation_count: int,
                   factors: Mapping[str, FactorValue | None],
                   case_evidence_ids: Iterable[str]) -> ScoredEvidence | None:
    """Policy calculation only; IDs/time/persistence/publication belong to A04+.

    Explicitly authorized same-case evidence set must include target and every
    factor source. Invalid inputs fail closed; zero observations/zero available
    factors returns None, never a fabricated P4. Round individual contributions
    with Python round(..., 2); final score is min(100, round(sum, 2)). Preserve
    contributions even if their rounded sum exceeds 100; disclose cap in reason.
    """
    if type(observation_count) is not int or observation_count < 0:
        raise ValueError("Observation count must be a nonnegative integer")
    target = _uuid(evidence_id)
    allowed = {_uuid(identifier) for identifier in case_evidence_ids}
    if target not in allowed:
        raise ValueError("Target evidence must belong to the authorized case")
    # Check names even if absent or unprocessed; never silently accept new enums.
    normalized_weights(factors)
    available = {name: factor for name, factor in factors.items() if factor is not None}
    for factor in available.values():
        _number(factor.value, 0, 1)
        if not isinstance(factor.explanation, str) or not factor.explanation.strip():
            raise ValueError("Factor explanation is required")
        ids = [_uuid(identifier) for identifier in factor.evidence_ids]
        if not ids or len(set(ids)) != len(ids) or not set(ids) <= allowed:
            raise ValueError("Factor sources must be nonempty, unique and same-case")
    if observation_count == 0 or not available:
        return None
    weights = normalized_weights(available)
    output = tuple({
        "name": name, "value": float(available[name].value), "weight": weight,
        "contribution": round(available[name].value * weight * 100, 2),
        "explanation": available[name].explanation,
        "evidence_ids": sorted(_uuid(identifier) for identifier in available[name].evidence_ids),
    } for name, weight in weights.items())
    total = round(sum(factor["contribution"] for factor in output), 2)
    score = min(100.0, total)
    explanation = f"{POLICY_VERSION}: {score:.2f} from available factors; absent factors omitted."
    if total > 100:
        explanation += f" Rounded contribution sum {total:.2f} capped at 100.00."
    return ScoredEvidence(score, priority(score), output, f"{explanation} {ATTENTION_NOTICE}")


def triage_sort_key(evidence_id: str, score: float | None) -> tuple[bool, float, str]:
    """Computed score descending, canonical UUID ascending; unscored last.

    Does not inspect live effective_priority/overrides. Sort full membership
    before pagination in A06. None and scored zero are distinct.
    """
    return (score is None, -_number(score, 0, 100) if score is not None else 0.0,
            _uuid(evidence_id))
