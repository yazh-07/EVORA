"""P02 gps-csv/1: pure bounded parsing; no time/coordinate normalization.

Uses P01's unchanged four-column CSV scanner, not its network validation.
See approved adapter policy in docs/COMMUNICATION.md. No I/O or run producer.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID, uuid4

from backend.parsers.network_csv import MAX_SOURCE_BYTES, MAX_DATA_ROWS, NetworkCSVError, _records

PARSER_VERSION = "gps-csv/1"
HEADER = ("timestamp", "device_id", "latitude", "longitude")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt ][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?P<offset>[Zz]|[+-][0-9]{2}:[0-9]{2})?")


class GPSCSVError(ValueError):
    def __init__(self, code: str, line: int | None = None):
        self.code, self.line = code, line
        super().__init__(f"GPS CSV rejected: {code}" + (f" at line {line}." if line else "."))


@dataclass(frozen=True, slots=True)
class GPSObservation:
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    kind: str
    source_locator: str
    raw_value: str
    normalized_value: str
    observed_at_raw: str
    extraction_confidence: float = 0.0  # unavailable score, not measured confidence

    def to_wire(self) -> dict:
        return {"id": str(self.id), "case_id": str(self.case_id), "evidence_id": str(self.evidence_id),
                "processing_run_id": str(self.processing_run_id), "kind": self.kind,
                "source_locator": self.source_locator, "raw_value": self.raw_value,
                "normalized_value": self.normalized_value, "observed_at_raw": self.observed_at_raw,
                "extraction_confidence": self.extraction_confidence}


def _timestamp(value: str, line: int) -> None:
    match = _TIMESTAMP.fullmatch(value)
    if not match:
        raise GPSCSVError("INVALID_TIMESTAMP", line)
    if int(value[11:13]) > 23 or int(value[14:16]) > 59 or int(value[17:19]) > 59:
        raise GPSCSVError("INVALID_TIMESTAMP", line)
    offset = match['offset']
    if offset and offset[0] in '+-' and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
        raise GPSCSVError("INVALID_TIMEZONE", line)
    try:
        # Validation only. Never emit or use the parsed datetime as normalized data.
        datetime.fromisoformat(value.replace('t', 'T').replace('z', 'Z'))
    except ValueError:
        raise GPSCSVError("INVALID_TIMESTAMP", line) from None


def _coordinate(value: str, maximum: int, line: int) -> None:
    if not _DECIMAL.fullmatch(value):
        raise GPSCSVError("INVALID_COORDINATE", line)
    try:
        coordinate = Decimal(value)
        valid = coordinate.is_finite() and -maximum <= coordinate <= maximum
    except InvalidOperation:
        valid = False
    if not valid:
        raise GPSCSVError("INVALID_COORDINATE", line)


def parse_gps_csv(source: bytes, *, case_id: UUID, evidence_id: UUID,
                  processing_run_id: UUID) -> tuple[GPSObservation, ...]:
    """All frozen observations or a safe error; caller authorizes source context."""
    if not isinstance(source, bytes):
        raise GPSCSVError("INVALID_SOURCE")
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise GPSCSVError("INVALID_CONTEXT")
    if len(source) > MAX_SOURCE_BYTES:
        raise GPSCSVError("BYTE_LIMIT")
    try:
        text = source.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise GPSCSVError("INVALID_UTF8") from None
    if '\x00' in text:
        raise GPSCSVError("MALFORMED_CSV")
    observations = []
    try:
        records = iter(_records(text))
        first = next(records, None)
        if first is None or first[0] != HEADER:
            raise GPSCSVError("INVALID_HEADER", 1)
        for count, (values, start, end) in enumerate(records, 1):
            if count > MAX_DATA_ROWS:
                raise GPSCSVError("ROW_LIMIT", start)
            if len(values) != 4 or any(not value.strip() for value in values):
                raise GPSCSVError("INVALID_ROW", start)
            _timestamp(values[0], start)
            _coordinate(values[2], 90, start)
            _coordinate(values[3], 180, start)
            location = f"row {start}" if start == end else f"rows {start}-{end}"
            for column, kind, value in zip(HEADER[1:], ('gps.device', 'gps.latitude', 'gps.longitude'), values[1:]):
                observations.append(GPSObservation(uuid4(), case_id, evidence_id, processing_run_id,
                    kind, f"{location}, {column}", value, value, values[0]))
    except NetworkCSVError as error:
        raise GPSCSVError(error.code, error.line) from None
    return tuple(observations)
