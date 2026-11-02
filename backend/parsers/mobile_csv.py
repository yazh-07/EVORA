"""P11 pure exported-mobile activity CSV; never physical device acquisition."""
from dataclasses import dataclass
from uuid import UUID

from backend.parsers.network_csv import MAX_SOURCE_BYTES, MAX_DATA_ROWS, NetworkCSVError, _records

PARSER_VERSION = 'mobile-csv/1'
HEADER = ('timestamp', 'device_id', 'event', 'detail')


class MobileCSVError(ValueError):
    def __init__(self, code, line=None):
        self.code, self.line = code, line
        super().__init__('Mobile CSV rejected: ' + code + '.')


@dataclass(frozen=True, slots=True)
class MobileRow:
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    timestamp: str
    device_id: str
    event: str
    detail: str
    start_line: int
    end_line: int


def parse_mobile_csv(source: bytes, *, case_id: UUID, evidence_id: UUID,
                     processing_run_id: UUID) -> tuple[MobileRow, ...]:
    """Return complete immutable source rows, or reject without partial output."""
    if not isinstance(source, bytes):
        raise MobileCSVError('INVALID_SOURCE')
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise MobileCSVError('INVALID_CONTEXT')
    if len(source) > MAX_SOURCE_BYTES:
        raise MobileCSVError('BYTE_LIMIT')
    try:
        text = source.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise MobileCSVError('INVALID_UTF8') from None
    if '\x00' in text:
        raise MobileCSVError('MALFORMED_CSV')
    rows = []
    try:
        records = iter(_records(text))
        first = next(records, None)
        if first is None or first[0] != HEADER:
            raise MobileCSVError('INVALID_HEADER', 1)
        for count, (values, start, end) in enumerate(records, 1):
            if count > MAX_DATA_ROWS:
                raise MobileCSVError('ROW_LIMIT', start)
            if len(values) != len(HEADER) or any(not value.strip() for value in values):
                raise MobileCSVError('INVALID_ROW', start)
            rows.append(MobileRow(case_id, evidence_id, processing_run_id, *values, start, end))
    except NetworkCSVError as error:
        raise MobileCSVError(error.code, error.line) from None
    return tuple(rows)
