"""P06 immutable source body/mention projection; no ownership or Event inference."""
from uuid import UUID, uuid4

from backend.parsers.messages_csv import MessageRow, DeviceMention, device_mentions, MAX_DATA_ROWS, MAX_DEVICE_MENTIONS
from backend.parsers.normalization import NormalizedObservation, NormalizationResult, normalize_timestamp
from backend.parsers.candidate_entities import CandidateObservation, CandidateEntity, CandidateProjection

PROJECTOR_VERSION = 'message-candidates/1'


class MessageProjectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Message projection rejected: ' + code + '.')


def project_message_entities(rows, *, case_id: UUID):
    if not isinstance(rows, tuple) or not isinstance(case_id, UUID):
        raise MessageProjectionError('INVALID_CONTEXT')
    if len(rows) > MAX_DATA_ROWS: raise MessageProjectionError('ROW_LIMIT')
    context, previous, total = None, 1, 0
    validated = []
    # Validate complete supplied rows before allocating output IDs.
    for row in rows:
        if (not isinstance(row, MessageRow) or any(not isinstance(x, UUID) for x in
                (row.case_id, row.evidence_id, row.processing_run_id)) or row.case_id != case_id):
            raise MessageProjectionError('INVALID_CONTEXT')
        current = (row.evidence_id, row.processing_run_id)
        if context is not None and current != context: raise MessageProjectionError('MIXED_RUN')
        context = current
        if (any(not isinstance(x, str) or not x.strip() for x in (row.message_id, row.timestamp, row.sender, row.body))
                or type(row.start_line) is not int or type(row.end_line) is not int
                or row.start_line <= previous or row.end_line < row.start_line or not isinstance(row.mentions, tuple)
                or any(not isinstance(m, DeviceMention) or type(m.start) is not int or type(m.end) is not int
                       or not isinstance(m.text, str) for m in row.mentions)):
            raise MessageProjectionError('INVALID_SOURCE')
        previous = row.end_line
        expected = []
        for mention in device_mentions(row.body):
            total += 1
            if total > MAX_DEVICE_MENTIONS: raise MessageProjectionError('MENTION_LIMIT')
            expected.append(mention)
        if tuple(expected) != row.mentions: raise MessageProjectionError('INVALID_SPAN')
        validated.append((row, normalize_timestamp(row.timestamp)))
    observations, groups = [], {}
    for row, time in validated:
        location = f'row {row.start_line}' if row.start_line == row.end_line else f'rows {row.start_line}-{row.end_line}'
        def observation(kind, value, locator, key=None):
            fields = dict(id=uuid4(), case_id=case_id, evidence_id=row.evidence_id,
                processing_run_id=row.processing_run_id, kind=kind, source_locator=locator,
                raw_value=value, normalized_value=value, observed_at_raw=row.timestamp,
                extraction_confidence=0, observed_at_utc=time.utc_value)
            source = CandidateObservation(**fields, entity_key=key) if key is not None else NormalizedObservation(**fields)
            observations.append(NormalizationResult(source, time, 'not_applicable'))
            return source
        observation('message.id', row.message_id, location + ', message_id')
        observation('message.sender', row.sender, location + ', sender')
        body = observation('message.body', row.body, location + ', body')
        for mention in row.mentions:
            key = 'device:' + mention.text
            source = observation('message.device', mention.text,
                f'{location}, body; chars={mention.start}:{mention.end}', key)
            group = groups.setdefault(mention.text, (set(), set()))
            group[0].add(row.evidence_id); group[1].update((body.id, source.id))
    entities = tuple(CandidateEntity(uuid4(), case_id, 'device', value, 'device:' + value,
        tuple(sorted(evidence, key=str)), tuple(sorted(refs, key=str)))
        for value, (evidence, refs) in sorted(groups.items()))
    return CandidateProjection(tuple(observations), entities, version=PROJECTOR_VERSION)
