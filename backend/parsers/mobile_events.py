"""P11 immutable mobile-source observations, exact candidates and reported events."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.parsers.mobile_csv import MobileRow, MAX_DATA_ROWS
from backend.parsers.normalization import NormalizedObservation, NormalizationResult, normalize_timestamp
from backend.parsers.candidate_entities import CandidateObservation, CandidateEntity
from backend.parsers.source_events import SourceEvent, SourceEventResult

ENTITY_VERSION = 'mobile-identifiers/1'
EVENT_VERSION = 'mobile-source-events/1'


class MobileProjectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Mobile projection rejected: ' + code + '.')


@dataclass(frozen=True, slots=True)
class MobileProjection:
    observations: tuple[NormalizationResult, ...]
    entities: tuple[CandidateEntity, ...]
    events: tuple[SourceEventResult, ...]


def project_mobile_records(rows: tuple[MobileRow, ...], *, case_id: UUID) -> MobileProjection:
    """Validate one supplied case/run before allocating any derived records."""
    if not isinstance(rows, tuple) or not isinstance(case_id, UUID):
        raise MobileProjectionError('INVALID_CONTEXT')
    if len(rows) > MAX_DATA_ROWS:
        raise MobileProjectionError('ROW_LIMIT')
    context, previous, validated = None, 1, []
    for row in rows:
        if (not isinstance(row, MobileRow) or row.case_id != case_id or
                any(not isinstance(value, UUID) for value in
                    (row.case_id, row.evidence_id, row.processing_run_id))):
            raise MobileProjectionError('INVALID_CONTEXT')
        current = (row.evidence_id, row.processing_run_id)
        if context is not None and current != context:
            raise MobileProjectionError('MIXED_RUN')
        context = current
        if (any(not isinstance(value, str) or not value.strip() or '\x00' in value
                for value in (row.timestamp, row.device_id, row.event, row.detail)) or
                type(row.start_line) is not int or type(row.end_line) is not int or
                row.start_line <= previous or row.end_line < row.start_line):
            raise MobileProjectionError('INVALID_SOURCE')
        previous = row.end_line
        validated.append((row, normalize_timestamp(row.timestamp)))
    observations, groups, event_rows = [], {}, []
    for row, time in validated:
        location = f'row {row.start_line}' if row.start_line == row.end_line else f'rows {row.start_line}-{row.end_line}'
        sources = []
        for column, kind, value in (('device_id', 'mobile.device', row.device_id),
                ('event', 'mobile.event', row.event), ('detail', 'mobile.detail', row.detail)):
            fields = dict(id=uuid4(), case_id=case_id, evidence_id=row.evidence_id,
                processing_run_id=row.processing_run_id, kind=kind, source_locator=location + ', ' + column,
                raw_value=value, normalized_value=value, observed_at_raw=row.timestamp,
                observed_at_utc=time.utc_value, extraction_confidence=0)
            source = (CandidateObservation(**fields, entity_key='device:' + value)
                      if kind == 'mobile.device' else NormalizedObservation(**fields))
            sources.append(source)
            observations.append(NormalizationResult(source, time, 'not_applicable'))
        groups.setdefault(row.device_id, []).append(sources[0])
        event_rows.append((row, time, tuple(source.id for source in sources)))
    by_device = {device: CandidateEntity(uuid4(), case_id, 'device', device, 'device:' + device,
                    (sources[0].evidence_id,), tuple(sorted((source.id for source in sources), key=str)))
                 for device, sources in sorted(groups.items())}
    events = tuple(SourceEventResult(SourceEvent(uuid4(), case_id, 'mobile.activity',
        'Source mobile log reports: ' + row.event, (row.evidence_id,), refs,
        (by_device[row.device_id].id,), row.timestamp, time.utc_value), time, version=EVENT_VERSION)
        for row, time, refs in event_rows)
    return MobileProjection(tuple(observations), tuple(by_device.values()), events)
