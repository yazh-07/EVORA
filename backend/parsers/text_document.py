"""P07 strict plain UTF-8 text with immutable, source-located physical lines."""
from dataclasses import dataclass
import re
from uuid import UUID, uuid4

from backend.parsers.normalization import TimeNormalization

PARSER_VERSION = 'document-text/1'
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_SOURCE_LINES = 100000
_LINE = re.compile(r'[^\r\n]*(?:\r\n|\r|\n|$)')


class TextDocumentError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Text document rejected: ' + code + '.')


@dataclass(frozen=True, slots=True)
class TextObservation:
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    source_locator: str
    raw_value: str

    def to_wire(self):
        return dict(id=str(self.id), case_id=str(self.case_id), evidence_id=str(self.evidence_id),
            processing_run_id=str(self.processing_run_id), kind='text.line',
            source_locator=self.source_locator, raw_value=self.raw_value,
            normalized_value=self.raw_value, extraction_confidence=0)


@dataclass(frozen=True, slots=True)
class TextLineResult:
    observation: TextObservation
    time: TimeNormalization
    coordinate_status: str = 'not_applicable'
    version: str = PARSER_VERSION


def parse_text_document(source: bytes, *, case_id: UUID, evidence_id: UUID,
                        processing_run_id: UUID) -> tuple[TextLineResult, ...]:
    """Return all lines or reject without partial results; no timestamp inference."""
    if not isinstance(source, bytes):
        raise TextDocumentError('INVALID_SOURCE')
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise TextDocumentError('INVALID_CONTEXT')
    if len(source) > MAX_SOURCE_BYTES:
        raise TextDocumentError('BYTE_LIMIT')
    try:
        text = source.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise TextDocumentError('INVALID_UTF8') from None
    if '\x00' in text:
        raise TextDocumentError('NUL_BYTE')
    lines = []
    for match in _LINE.finditer(text):
        if match.start() == len(text):
            break
        if len(lines) >= MAX_SOURCE_LINES:
            raise TextDocumentError('LINE_LIMIT')
        value = match.group().rstrip('\r\n')
        observation = TextObservation(uuid4(), case_id, evidence_id, processing_run_id,
            f'line {len(lines) + 1}; chars={match.start()}:{match.start() + len(value)}', value)
        lines.append(TextLineResult(observation, TimeNormalization('', None, 'not_provided', None)))
    return tuple(lines)
