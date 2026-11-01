"""P01 network-csv/1: bounded, pure parsing of immutable original bytes.

No HTTP/storage/run publication or identity inference. See approved policy in
COMMUNICATION. A local CSV scanner avoids changing csv.field_size_limit globally
or imposing its implicit 128 KiB cap on otherwise valid 50 MiB originals.
"""
from dataclasses import dataclass
from ipaddress import ip_address
import re
from uuid import UUID, uuid4

PARSER_VERSION = "network-csv/1"
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_DATA_ROWS = 100_000
HEADER = ("timestamp", "device_id", "ip_address", "event")
_UNQUOTED = re.compile('[,"\r\n]')
_QUOTED = re.compile('["\r\n]')


class NetworkCSVError(ValueError):
    """Safe diagnostic: never includes a source cell, filename or credential."""
    def __init__(self, code: str, line: int | None = None):
        self.code = code
        self.line = line
        super().__init__(f"Network CSV rejected: {code}" + (f" at line {line}." if line else "."))


@dataclass(frozen=True, slots=True)
class NetworkObservation:
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    kind: str
    source_locator: str
    raw_value: str
    normalized_value: str
    observed_at_raw: str
    extraction_confidence: float = 0.0  # unavailable-score sentinel, not a measurement

    def to_wire(self) -> dict:
        """Fresh schema-shaped copy; caller mutation cannot change this result."""
        return {"id": str(self.id), "case_id": str(self.case_id),
                "evidence_id": str(self.evidence_id), "processing_run_id": str(self.processing_run_id),
                "kind": self.kind, "source_locator": self.source_locator,
                "raw_value": self.raw_value, "normalized_value": self.normalized_value,
                "observed_at_raw": self.observed_at_raw,
                "extraction_confidence": self.extraction_confidence}


def _records(text: str):
    """Yield logical values and original 1-based physical record line spans."""
    fields, parts = [], []
    quoted = closed = False
    line = start = 1
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            if quoted:
                if index + 1 < len(text) and text[index + 1] == '"':
                    parts.append('"')
                    index += 2
                    continue
                quoted, closed = False, True
            elif parts or closed:
                raise NetworkCSVError("MALFORMED_CSV", line)
            else:
                quoted = True
            index += 1
        elif char in "\r\n":
            ending = "\r\n" if text[index:index + 2] == "\r\n" else char
            if quoted:
                parts.append(ending)
            else:
                fields.append("".join(parts))
                yield tuple(fields), start, line
                fields, parts, closed = [], [], False
                start = line + 1
            line += 1
            index += len(ending)
        elif char == "," and not quoted:
            fields.append("".join(parts))
            if len(fields) >= len(HEADER):
                raise NetworkCSVError("INVALID_HEADER" if start == 1 else "INVALID_ROW", start)
            parts, closed = [], False
            index += 1
        else:
            if closed:
                raise NetworkCSVError("MALFORMED_CSV", line)
            match = (_QUOTED if quoted else _UNQUOTED).search(text, index)
            end = match.start() if match else len(text)
            parts.append(text[index:end])
            index = end
    if quoted:
        raise NetworkCSVError("MALFORMED_CSV", line)
    if fields or parts or closed:
        fields.append("".join(parts))
        yield tuple(fields), start, line


def parse_network_csv(source: bytes, *, case_id: UUID, evidence_id: UUID,
                      processing_run_id: UUID) -> tuple[NetworkObservation, ...]:
    """Return all immutable observations, or raise without returning any output.

    Caller must authorize/download the same-case original and supply run context;
    this component has no DB knowledge and cannot establish those joins itself.
    """
    if not isinstance(source, bytes):
        raise NetworkCSVError("INVALID_SOURCE")
    if any(not isinstance(value, UUID) for value in (case_id, evidence_id, processing_run_id)):
        raise NetworkCSVError("INVALID_CONTEXT")
    if len(source) > MAX_SOURCE_BYTES:
        raise NetworkCSVError("BYTE_LIMIT")
    try:
        text = source.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise NetworkCSVError("INVALID_UTF8") from None
    if "\x00" in text:
        raise NetworkCSVError("MALFORMED_CSV")
    records = iter(_records(text))
    first = next(records, None)
    if first is None or first[0] != HEADER:
        raise NetworkCSVError("INVALID_HEADER", 1)
    observations = []
    for count, (values, start, end) in enumerate(records, 1):
        if count > MAX_DATA_ROWS:
            raise NetworkCSVError("ROW_LIMIT", start)
        if len(values) != len(HEADER) or any(not value.strip() for value in values):
            raise NetworkCSVError("INVALID_ROW", start)
        try:
            if "%" in values[2]:
                raise ValueError()
            ip_address(values[2])
        except ValueError:
            raise NetworkCSVError("INVALID_IP", start) from None
        location = f"row {start}" if start == end else f"rows {start}-{end}"
        for column, kind, value in zip(HEADER[1:], ("network.device", "network.ip", "network.event"), values[1:]):
            observations.append(NetworkObservation(uuid4(), case_id, evidence_id, processing_run_id,
                kind, f"{location}, {column}", value, value, values[0]))
    return tuple(observations)
