"""P03B exact candidate keys; immutable pre-publication values, no identity claim."""
from dataclasses import dataclass, replace
from ipaddress import ip_address
from math import isfinite
from uuid import UUID, uuid4

from backend.parsers.normalization import NormalizationResult, NormalizedObservation

PROJECTOR_VERSION = "candidate-identifiers/1"
_IDENTIFIERS = {"network.device": "device", "gps.device": "device", "network.ip": "ip"}
_KINDS = frozenset((*_IDENTIFIERS, "network.event", "gps.latitude", "gps.longitude"))


class CandidateEntityError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Candidate projection rejected: {code}.")


@dataclass(frozen=True, slots=True)
class CandidateObservation(NormalizedObservation):
    entity_key: str | None = None

    def to_wire(self) -> dict:
        wire = NormalizedObservation.to_wire(self)
        if self.entity_key is not None:
            wire["entity_key"] = self.entity_key
        return wire


@dataclass(frozen=True, slots=True)
class CandidateEntity:
    id: UUID
    case_id: UUID
    kind: str
    canonical_label: str
    candidate_key: str
    evidence_ids: tuple[UUID, ...]
    observation_ids: tuple[UUID, ...]
    confidence: float = 0

    def to_wire(self) -> dict:
        return {"id": str(self.id), "case_id": str(self.case_id), "kind": self.kind,
                "canonical_label": self.canonical_label, "candidate_key": self.candidate_key,
                "evidence_ids": [str(value) for value in self.evidence_ids],
                "observation_ids": [str(value) for value in self.observation_ids],
                "confidence": self.confidence}


@dataclass(frozen=True, slots=True)
class CandidateProjection:
    observations: tuple[NormalizationResult, ...]
    entities: tuple[CandidateEntity, ...]
    version: str = PROJECTOR_VERSION


def project_candidate_entities(results, *, case_id: UUID) -> CandidateProjection:
    """Project one explicitly chosen case/output set, without DB/auth assumptions.

    IDs are new record IDs, not verified identities or lifecycle replay keys.
    No partial result escapes on invalid input; no input value is modified.
    """
    if not isinstance(case_id, UUID):
        raise CandidateEntityError("INVALID_CASE")
    observations, groups = [], {}
    seen, evidence_runs, run_evidence = set(), {}, {}
    for result in results:
        if not isinstance(result, NormalizationResult) or not isinstance(result.observation, NormalizedObservation):
            raise CandidateEntityError("INVALID_OBSERVATION")
        source = result.observation
        if any(not isinstance(value, UUID) for value in
               (source.id, source.case_id, source.evidence_id, source.processing_run_id)):
            raise CandidateEntityError("INVALID_CONTEXT")
        if source.case_id != case_id:
            raise CandidateEntityError("CASE_MISMATCH")
        if source.id in seen:
            raise CandidateEntityError("DUPLICATE_OBSERVATION")
        seen.add(source.id)
        if (evidence_runs.setdefault(source.evidence_id, source.processing_run_id) != source.processing_run_id
                or run_evidence.setdefault(source.processing_run_id, source.evidence_id) != source.evidence_id):
            raise CandidateEntityError("CONFLICTING_RUN_CONTEXT")
        if not isinstance(source.kind, str) or source.kind not in _KINDS:
            raise CandidateEntityError("UNSUPPORTED_KIND")
        if (any(not isinstance(value, str) for value in
                (source.raw_value, source.normalized_value, source.observed_at_raw, source.source_locator))
                or not source.source_locator.strip()
                or (source.observed_at_utc is not None and not isinstance(source.observed_at_utc, str))
                or isinstance(source.extraction_confidence, bool)
                or not isinstance(source.extraction_confidence, (int, float))
                or not 0 <= source.extraction_confidence <= 1
                or not isfinite(source.extraction_confidence)):
            raise CandidateEntityError("INVALID_SOURCE")
        kind = _IDENTIFIERS.get(source.kind)
        key = None
        if kind is not None:
            value = source.normalized_value
            if not value.strip() or value != source.raw_value:
                raise CandidateEntityError("INVALID_IDENTIFIER")
            if kind == "ip":
                try:
                    if "%" in value:
                        raise ValueError()
                    ip_address(value)
                except ValueError:
                    raise CandidateEntityError("INVALID_IDENTIFIER") from None
            key = f"{kind}:{value}"
            group = groups.setdefault(key, (kind, value, set(), set()))
            group[2].add(source.evidence_id)
            group[3].add(source.id)
        if isinstance(source, CandidateObservation) and source.entity_key != key:
            raise CandidateEntityError("CONFLICTING_KEY")
        if kind is not None:
            # Preserve all fields and internal uncertainty; append only the existing key.
            fields = {name: getattr(source, name) for name in NormalizedObservation.__dataclass_fields__}
            source = CandidateObservation(**fields, entity_key=key)
        observations.append(replace(result, observation=source))
    entities = tuple(CandidateEntity(uuid4(), case_id, kind, label, key,
                     tuple(sorted(evidence, key=str)), tuple(sorted(observed, key=str)))
                     for key, (kind, label, evidence, observed) in sorted(groups.items()))
    return CandidateProjection(tuple(observations), entities)
