"""P03C source reports, not verified occurrences or identities; no persistence."""
from dataclasses import dataclass
import re
from uuid import UUID, uuid4

from backend.parsers.candidate_entities import (
    PROJECTOR_VERSION as CANDIDATE_VERSION, CandidateEntity, CandidateEntityError,
    CandidateProjection, project_candidate_entities,
)
from backend.parsers.normalization import (
    NORMALIZER_VERSION, NormalizationError, TimeNormalization,
    normalize_coordinate, normalize_timestamp,
)

PROJECTOR_VERSION = "source-events/1"
_LOCATOR = re.compile(r"(?:row (?P<line>[1-9][0-9]*)|rows (?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*)), (?P<column>[a-z_]+)")
_COLUMNS = {"network.device": "device_id", "network.ip": "ip_address", "network.event": "event",
            "gps.device": "device_id", "gps.latitude": "latitude", "gps.longitude": "longitude"}
_REQUIRED = {"network": frozenset(("network.device", "network.ip", "network.event")),
             "gps": frozenset(("gps.device", "gps.latitude", "gps.longitude"))}


class SourceEventError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Source event projection rejected: {code}.")


@dataclass(frozen=True, slots=True)
class SourceEvent:
    id: UUID
    case_id: UUID
    kind: str
    summary: str
    evidence_ids: tuple[UUID, ...]
    observation_ids: tuple[UUID, ...]
    entity_ids: tuple[UUID, ...]
    observed_at_raw: str
    observed_at_utc: str | None
    confidence: float = 0

    def to_wire(self) -> dict:
        wire = {"id": str(self.id), "case_id": str(self.case_id), "kind": self.kind,
                "summary": self.summary, "evidence_ids": [str(x) for x in self.evidence_ids],
                "observation_ids": [str(x) for x in self.observation_ids],
                "entity_ids": [str(x) for x in self.entity_ids],
                "observed_at_raw": self.observed_at_raw, "confidence": self.confidence}
        if self.observed_at_utc is not None:
            wire["observed_at_utc"] = self.observed_at_utc
        return wire


@dataclass(frozen=True, slots=True)
class SourceEventResult:
    event: SourceEvent
    time: TimeNormalization
    version: str = PROJECTOR_VERSION


def _participants(projection: CandidateProjection, case_id: UUID) -> dict:
    # Reuse the real key/source validator. Its temporary record IDs are discarded;
    # event participants always refer to supplied, verified records below.
    try:
        expected = project_candidate_entities(projection.observations, case_id=case_id)
    except CandidateEntityError as error:
        raise SourceEventError(error.code) from None
    if any(source.observation.to_wire() != validated.observation.to_wire()
           for source, validated in zip(projection.observations, expected.observations)):
        raise SourceEventError("INVALID_PROJECTION")
    by_key, seen = {}, set()
    for entity in projection.entities:
        if (not isinstance(entity, CandidateEntity) or not isinstance(entity.id, UUID)
                or entity.case_id != case_id or not isinstance(entity.candidate_key, str)
                or entity.id in seen or entity.candidate_key in by_key):
            raise SourceEventError("INVALID_PARTICIPANT")
        by_key[entity.candidate_key] = entity
        seen.add(entity.id)
    if set(by_key) != {entity.candidate_key for entity in expected.entities}:
        raise SourceEventError("INVALID_PARTICIPANT")
    for entity in expected.entities:
        actual = by_key[entity.candidate_key]
        if (actual.kind, actual.canonical_label, actual.evidence_ids, actual.observation_ids, actual.confidence) != (
                entity.kind, entity.canonical_label, entity.evidence_ids, entity.observation_ids, entity.confidence):
            raise SourceEventError("INVALID_PARTICIPANT")
    return by_key


def project_source_events(projection: CandidateProjection, *, case_id: UUID) -> tuple[SourceEventResult, ...]:
    """Project complete source rows atomically; caller authorizes the output set."""
    if (not isinstance(projection, CandidateProjection)
            or not isinstance(projection.observations, tuple) or not isinstance(projection.entities, tuple)
            or projection.version != CANDIDATE_VERSION):
        raise SourceEventError("INVALID_PROJECTION")
    participants = _participants(projection, case_id)
    rows, families = {}, {}
    for result in projection.observations:
        source = result.observation
        match = _LOCATOR.fullmatch(source.source_locator)
        if not match or match["column"] != _COLUMNS[source.kind]:
            raise SourceEventError("INVALID_LOCATOR")
        try:
            start = int(match["line"] or match["start"])
            end = int(match["line"] or match["end"])
        except ValueError:
            raise SourceEventError("INVALID_LOCATOR") from None
        if start < 2 or end < start or (match["line"] is None and end == start):
            raise SourceEventError("INVALID_LOCATOR")
        family = source.kind.split('.')[0]
        if families.setdefault(source.evidence_id, family) != family:
            raise SourceEventError("MIXED_ADAPTER")
        if (result.version != NORMALIZER_VERSION
                or result.time != normalize_timestamp(source.observed_at_raw)
                or source.observed_at_utc != result.time.utc_value):
            raise SourceEventError("CONFLICTING_TIME")
        if source.kind in ("gps.latitude", "gps.longitude"):
            try:
                coordinate = normalize_coordinate(source.raw_value, 90 if source.kind == "gps.latitude" else 180)
            except NormalizationError:
                raise SourceEventError("INVALID_COORDINATE") from None
            if coordinate != source.normalized_value or result.coordinate_status != 'normalized':
                raise SourceEventError("INVALID_COORDINATE")
        elif result.coordinate_status != 'not_applicable':
            raise SourceEventError("INVALID_SOURCE")
        row = rows.setdefault((source.evidence_id, source.processing_run_id, start, end, family), {})
        if source.kind in row:
            raise SourceEventError("DUPLICATE_ROW_FIELD")
        row[source.kind] = result
    output, previous = [], {}
    for (evidence, run, start, end, family), row in sorted(rows.items(), key=lambda item: (
            str(item[0][0]), str(item[0][1]), item[0][2], item[0][3], item[0][4])):
        if set(row) != _REQUIRED[family]:
            raise SourceEventError("INCOMPLETE_ROW")
        if start <= previous.get(evidence, 0):
            raise SourceEventError("OVERLAPPING_ROWS")
        previous[evidence] = end
        device = row[family + '.device']
        if any(result.time != device.time for result in row.values()):
            raise SourceEventError("CONFLICTING_TIME")
        device_source = device.observation
        keys = [device_source.entity_key]
        if family == 'network':
            keys.append(row['network.ip'].observation.entity_key)
            summary = 'Network log reports: ' + row['network.event'].observation.raw_value
            kind = 'network.activity'
        else:
            summary = (f'GPS record reports device {device_source.raw_value} at latitude '
                       f'{row["gps.latitude"].observation.normalized_value}, longitude '
                       f'{row["gps.longitude"].observation.normalized_value}')
            kind = 'gps.location'
        event = SourceEvent(uuid4(), case_id, kind, summary, (evidence,),
                            tuple(sorted((result.observation.id for result in row.values()), key=str)),
                            tuple(sorted((participants[key].id for key in keys), key=str)),
                            device_source.observed_at_raw, device_source.observed_at_utc)
        output.append(SourceEventResult(event, device.time))
    return tuple(output)
