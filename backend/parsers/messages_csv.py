"""P06 pure bounded message rows and literal candidate spans, not identities."""
from dataclasses import dataclass
import re
from uuid import UUID

from backend.parsers.network_csv import MAX_SOURCE_BYTES, MAX_DATA_ROWS, NetworkCSVError, _records

PARSER_VERSION = 'messages-csv/1'
HEADER = ('message_id', 'timestamp', 'sender', 'body')
MAX_DEVICE_MENTIONS = 100000
_DEVICE = re.compile(r'(?<![\w-])D-[0-9]+(?![\w-])')


class MessageCSVError(ValueError):
    def __init__(self, code, line=None):
        self.code, self.line = code, line
        super().__init__('Message CSV rejected: ' + code + '.')


@dataclass(frozen=True, slots=True)
class DeviceMention:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class MessageRow:
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    message_id: str
    timestamp: str
    sender: str
    body: str
    start_line: int
    end_line: int
    mentions: tuple[DeviceMention, ...]


def device_mentions(body):
    for match in _DEVICE.finditer(body):
        yield DeviceMention(match.start(), match.end(), match.group())


def parse_messages_csv(source: bytes, *, case_id: UUID, evidence_id: UUID, processing_run_id: UUID):
    """Return all immutable source rows, or raise with no partial result."""
    if not isinstance(source, bytes): raise MessageCSVError('INVALID_SOURCE')
    if any(not isinstance(x, UUID) for x in (case_id, evidence_id, processing_run_id)):
        raise MessageCSVError('INVALID_CONTEXT')
    if len(source) > MAX_SOURCE_BYTES: raise MessageCSVError('BYTE_LIMIT')
    try:
        text = source.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise MessageCSVError('INVALID_UTF8') from None
    if '\x00' in text: raise MessageCSVError('MALFORMED_CSV')
    rows, count = [], 0
    try:
        records = iter(_records(text))
        first = next(records, None)
        if first is None or first[0] != HEADER: raise MessageCSVError('INVALID_HEADER', 1)
        for index, (values, start, end) in enumerate(records, 1):
            if index > MAX_DATA_ROWS: raise MessageCSVError('ROW_LIMIT', start)
            if len(values) != 4 or any(not value.strip() for value in values):
                raise MessageCSVError('INVALID_ROW', start)
            found = []
            for mention in device_mentions(values[3]):
                count += 1
                if count > MAX_DEVICE_MENTIONS: raise MessageCSVError('MENTION_LIMIT', start)
                found.append(mention)
            rows.append(MessageRow(case_id, evidence_id, processing_run_id, *values, start, end, tuple(found)))
    except NetworkCSVError as error:
        raise MessageCSVError(error.code, error.line) from None
    return tuple(rows)
