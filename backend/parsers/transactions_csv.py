"""P12 bounded exported transactions; exact signed decimal strings, no live banking."""
from dataclasses import dataclass
import re
from uuid import UUID

from backend.parsers.network_csv import MAX_SOURCE_BYTES, MAX_DATA_ROWS, NetworkCSVError, _records

PARSER_VERSION = 'transactions-csv/1'
HEADER = ('timestamp', 'account_id', 'amount', 'currency')
MAX_AMOUNT_CHARS = 128
_AMOUNT = re.compile(r'-?[0-9]+(?:\.[0-9]+)?')
_CURRENCY = re.compile(r'[A-Z]{3}')


class TransactionCSVError(ValueError):
    def __init__(self, code, line=None):
        self.code, self.line = code, line
        super().__init__('Transaction CSV rejected: ' + code + '.')


def normalize_amount(raw: str) -> str:
    """Canonicalize the approved literal without Decimal context or float rounding."""
    if not isinstance(raw, str):
        raise TransactionCSVError('INVALID_AMOUNT')
    if len(raw) > MAX_AMOUNT_CHARS:
        raise TransactionCSVError('AMOUNT_LIMIT')
    if not _AMOUNT.fullmatch(raw):
        raise TransactionCSVError('INVALID_AMOUNT')
    negative = raw.startswith('-')
    unsigned = raw[1:] if negative else raw
    integer, _, fraction = unsigned.partition('.')
    integer = integer.lstrip('0') or '0'
    fraction = fraction.rstrip('0')
    canonical = integer + ('.' + fraction if fraction else '')
    return ('-' if negative and canonical != '0' else '') + canonical


def validate_currency(raw: str) -> None:
    """Validate source-label shape only; no ISO currency or minor-unit assertion."""
    if not isinstance(raw, str) or not _CURRENCY.fullmatch(raw):
        raise TransactionCSVError('INVALID_CURRENCY')


@dataclass(frozen=True, slots=True)
class TransactionRow:
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    timestamp: str
    account_id: str
    amount: str
    currency: str
    start_line: int
    end_line: int


def parse_transactions_csv(source: bytes, *, case_id: UUID, evidence_id: UUID,
                     processing_run_id: UUID) -> tuple[TransactionRow, ...]:
    """Return complete immutable source rows, or reject without partial output."""
    if not isinstance(source, bytes):
        raise TransactionCSVError('INVALID_SOURCE')
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise TransactionCSVError('INVALID_CONTEXT')
    if len(source) > MAX_SOURCE_BYTES:
        raise TransactionCSVError('BYTE_LIMIT')
    try:
        text = source.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise TransactionCSVError('INVALID_UTF8') from None
    if '\x00' in text:
        raise TransactionCSVError('MALFORMED_CSV')
    rows = []
    try:
        records = iter(_records(text))
        first = next(records, None)
        if first is None or first[0] != HEADER:
            raise TransactionCSVError('INVALID_HEADER', 1)
        for count, (values, start, end) in enumerate(records, 1):
            if count > MAX_DATA_ROWS:
                raise TransactionCSVError('ROW_LIMIT', start)
            if len(values) != len(HEADER) or any(not value.strip() for value in values):
                raise TransactionCSVError('INVALID_ROW', start)
            normalize_amount(values[2])
            validate_currency(values[3])
            rows.append(TransactionRow(case_id, evidence_id, processing_run_id, *values, start, end))
    except NetworkCSVError as error:
        raise TransactionCSVError(error.code, error.line) from None
    return tuple(rows)
