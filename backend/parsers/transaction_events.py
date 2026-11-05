"""P12 source transactions, exact account candidates and reported amounts."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.parsers.transactions_csv import (TransactionRow, MAX_DATA_ROWS, TransactionCSVError,
    normalize_amount, validate_currency)
from backend.parsers.normalization import NormalizedObservation, NormalizationResult, normalize_timestamp
from backend.parsers.candidate_entities import CandidateObservation, CandidateEntity
from backend.parsers.source_events import SourceEvent, SourceEventResult

ENTITY_VERSION = 'transaction-identifiers/2'
EVENT_VERSION = 'transaction-source-events/2'


class TransactionProjectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Transaction projection rejected: ' + code + '.')


@dataclass(frozen=True, slots=True)
class TransactionProjection:
    observations: tuple[NormalizationResult, ...]
    entities: tuple[CandidateEntity, ...]
    events: tuple[SourceEventResult, ...]


def project_transaction_records(rows: tuple[TransactionRow, ...], *, case_id: UUID) -> TransactionProjection:
    """Validate one supplied case/run before allocating any derived records."""
    if not isinstance(rows, tuple) or not isinstance(case_id, UUID):
        raise TransactionProjectionError('INVALID_CONTEXT')
    if len(rows) > MAX_DATA_ROWS:
        raise TransactionProjectionError('ROW_LIMIT')
    context, previous, validated = None, 1, []
    for row in rows:
        if (not isinstance(row, TransactionRow) or row.case_id != case_id or
                any(not isinstance(value, UUID) for value in
                    (row.case_id, row.evidence_id, row.processing_run_id))):
            raise TransactionProjectionError('INVALID_CONTEXT')
        current = (row.evidence_id, row.processing_run_id)
        if context is not None and current != context:
            raise TransactionProjectionError('MIXED_RUN')
        context = current
        if (any(not isinstance(value, str) or not value.strip() or '\x00' in value
                for value in (row.timestamp, row.account_id, row.amount, row.currency)) or
                type(row.start_line) is not int or type(row.end_line) is not int or
                row.start_line <= previous or row.end_line < row.start_line):
            raise TransactionProjectionError('INVALID_SOURCE')
        try:
            normalize_amount(row.amount)
            validate_currency(row.currency)
        except TransactionCSVError as error:
            raise TransactionProjectionError(error.code) from None
        previous = row.end_line
        validated.append((row, normalize_timestamp(row.timestamp)))
    observations, groups, event_rows = [], {}, []
    for row, time in validated:
        location = f'row {row.start_line}' if row.start_line == row.end_line else f'rows {row.start_line}-{row.end_line}'
        sources = []
        for column, kind, value in (('account_id', 'transaction.account', row.account_id),
                ('amount', 'transaction.amount', row.amount), ('currency', 'transaction.currency', row.currency)):
            fields = dict(id=uuid4(), case_id=case_id, evidence_id=row.evidence_id,
                processing_run_id=row.processing_run_id, kind=kind, source_locator=location + ', ' + column,
                raw_value=value, normalized_value=normalize_amount(value) if kind == 'transaction.amount' else value, observed_at_raw=row.timestamp,
                observed_at_utc=time.utc_value, extraction_confidence=0)
            source = (CandidateObservation(**fields, entity_key='account:' + value)
                      if kind == 'transaction.account' else NormalizedObservation(**fields))
            sources.append(source)
            observations.append(NormalizationResult(source, time, 'not_applicable'))
        groups.setdefault(row.account_id, []).append(sources[0])
        if row.recipient is not None:
            if not isinstance(row.recipient, str) or not row.recipient.strip():
                raise TransactionProjectionError('INVALID_SOURCE')
            target = CandidateObservation(id=uuid4(), case_id=case_id, evidence_id=row.evidence_id,
                processing_run_id=row.processing_run_id, kind='transaction.recipient',
                source_locator=location + ', recipient_account_id', raw_value=row.recipient,
                normalized_value=row.recipient, observed_at_raw=row.timestamp,
                observed_at_utc=time.utc_value, extraction_confidence=0, entity_key='account:' + row.recipient)
            sources.append(target)
            observations.append(NormalizationResult(target, time, 'not_applicable'))
            groups.setdefault(row.recipient, []).append(target)
        event_rows.append((row, time, tuple(source.id for source in sources)))
    by_account = {account: CandidateEntity(uuid4(), case_id, 'account', account, 'account:' + account,
                    (sources[0].evidence_id,), tuple(sorted((source.id for source in sources), key=str)))
                 for account, sources in sorted(groups.items())}
    events = tuple(SourceEventResult(SourceEvent(uuid4(), case_id, 'transaction.record',
        'Source transaction record reports: ' + row.amount + ' ' + row.currency, (row.evidence_id,), refs,
        tuple(dict.fromkeys([by_account[row.account_id].id] +
            ([by_account[row.recipient].id] if row.recipient else []))), row.timestamp, time.utc_value), time, version=EVENT_VERSION)
        for row, time, refs in event_rows)
    return TransactionProjection(tuple(observations), tuple(by_account.values()), events)
