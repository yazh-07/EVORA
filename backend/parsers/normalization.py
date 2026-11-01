"""P03 source-normalization/1: exact, immutable, pre-publication transforms.

Internal uncertainty envelope is not a new wire schema. No I/O, identity
inference, machine-timezone fallback or stored-output updates.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID

from backend.parsers.network_csv import NetworkObservation
from backend.parsers.gps_csv import GPSObservation

NORMALIZER_VERSION = "source-normalization/1"
PLAIN_COORDINATE_CHARS = 64
_TIME = re.compile(r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[Tt ](?P<clock>[0-9]{2}:[0-9]{2}:[0-9]{2})(?P<fraction>\.[0-9]+)?(?P<zone>.*)")
_OFFSET = re.compile(r"[+-][0-9]{2}:[0-9]{2}")
_NAMED_ZONE = re.compile(r"(?:[A-Za-z][A-Za-z0-9_ /+-]*|\[[A-Za-z][A-Za-z0-9_ /+-]*\])")
_COORDINATE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_KINDS = frozenset({'network.device','network.ip','network.event','gps.device','gps.latitude','gps.longitude'})


class NormalizationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Source normalization rejected: {code}.")


@dataclass(frozen=True, slots=True)
class TimeNormalization:
    raw_value: str
    utc_value: str | None
    status: str
    source_offset: str | None


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    kind: str
    source_locator: str
    raw_value: str
    normalized_value: str
    observed_at_raw: str
    extraction_confidence: float
    observed_at_utc: str | None = None

    def to_wire(self) -> dict:
        wire = {"id": str(self.id), "case_id": str(self.case_id), "evidence_id": str(self.evidence_id),
                "processing_run_id": str(self.processing_run_id), "kind": self.kind,
                "source_locator": self.source_locator, "raw_value": self.raw_value,
                "normalized_value": self.normalized_value, "observed_at_raw": self.observed_at_raw,
                "extraction_confidence": self.extraction_confidence}
        if self.observed_at_utc is not None:
            wire['observed_at_utc'] = self.observed_at_utc
        return wire


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    observation: NormalizedObservation
    time: TimeNormalization
    coordinate_status: str
    version: str = NORMALIZER_VERSION


def normalize_timestamp(raw: str) -> TimeNormalization:
    """Resolve only known explicit offsets, preserving every fractional digit."""
    if not isinstance(raw, str):
        raise NormalizationError('INVALID_TIMESTAMP_TYPE')
    match = _TIME.fullmatch(raw)
    if not match:
        return TimeNormalization(raw, None, 'invalid_timestamp', None)
    zone = match['zone']
    try:
        year, month, day = map(int, match['date'].split('-'))
        hour, minute, second = map(int, match['clock'].split(':'))
        # Constructor rejects 24:00 even on runtimes accepting it in fromisoformat.
        base = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return TimeNormalization(raw, None, 'invalid_timestamp', zone or None)
    if not zone:
        return TimeNormalization(raw, None, 'missing_timezone', None)
    if zone == '-00:00':
        return TimeNormalization(raw, None, 'unknown_offset', zone)
    if zone in ('Z', 'z'):
        minutes = 0
    elif _OFFSET.fullmatch(zone):
        hours, part = int(zone[1:3]), int(zone[4:6])
        if hours > 23 or part > 59:
            return TimeNormalization(raw, None, 'invalid_timezone', zone)
        minutes = (hours * 60 + part) * (-1 if zone[0] == '-' else 1)
    else:
        status = 'ambiguous_timezone' if _NAMED_ZONE.fullmatch(zone.strip()) else 'invalid_timezone'
        return TimeNormalization(raw, None, status, zone)
    try:
        utc = base - timedelta(minutes=minutes)
    except OverflowError:
        return TimeNormalization(raw, None, 'utc_out_of_range', zone)
    value = (f'{utc.year:04d}-{utc.month:02d}-{utc.day:02d}T'
             f'{utc.hour:02d}:{utc.minute:02d}:{utc.second:02d}'
             f"{match['fraction'] or ''}Z")
    return TimeNormalization(raw, value, 'resolved', zone)


def normalize_coordinate(raw: str, maximum: int) -> str:
    """Canonical exact decimal; scientific form bounds exponent expansion."""
    if not isinstance(raw, str) or not _COORDINATE.fullmatch(raw):
        raise NormalizationError('INVALID_COORDINATE')
    try:
        number = Decimal(raw)
        valid = number.is_finite() and -maximum <= number <= maximum
    except InvalidOperation:
        valid = False
    if not valid:
        raise NormalizationError('INVALID_COORDINATE')
    sign, digits, exponent = number.as_tuple()
    coefficient = ''.join(str(digit) for digit in digits).lstrip('0')
    if not coefficient:
        return '0'
    trimmed = coefficient.rstrip('0')
    exponent += len(coefficient) - len(trimmed)
    coefficient = trimmed
    prefix = '-' if sign else ''
    point = len(coefficient) + exponent
    plain_length = len(prefix) + (point if exponent >= 0 else
                    len(coefficient) + 1 if point > 0 else 2 - point + len(coefficient))
    if plain_length <= PLAIN_COORDINATE_CHARS:
        if exponent >= 0:
            return prefix + coefficient + '0' * exponent
        if point > 0:
            return prefix + coefficient[:point] + '.' + coefficient[point:]
        return prefix + '0.' + '0' * (-point) + coefficient
    mantissa = coefficient[0] + ('.' + coefficient[1:] if len(coefficient) > 1 else '')
    return prefix + mantissa + f'e{point - 1:+d}'


def normalize_observations(observations) -> tuple[NormalizationResult, ...]:
    """Keep source context/IDs; no access grant, joins or persistence implied."""
    results = []
    for source in observations:
        if not isinstance(source, (NetworkObservation, GPSObservation, NormalizedObservation)):
            raise NormalizationError('INVALID_OBSERVATION')
        if any(not isinstance(value, UUID) for value in
               (source.id, source.case_id, source.evidence_id, source.processing_run_id)):
            raise NormalizationError('INVALID_CONTEXT')
        if source.kind not in _KINDS:
            raise NormalizationError('UNSUPPORTED_KIND')
        time = normalize_timestamp(source.observed_at_raw)
        value = source.normalized_value
        coordinate_status = 'not_applicable'
        if source.kind in ('gps.latitude', 'gps.longitude'):
            value = normalize_coordinate(source.raw_value, 90 if source.kind == 'gps.latitude' else 180)
            coordinate_status = 'normalized'
        result = NormalizedObservation(source.id, source.case_id, source.evidence_id,
            source.processing_run_id, source.kind, source.source_locator, source.raw_value,
            value, source.observed_at_raw, source.extraction_confidence, time.utc_value)
        results.append(NormalizationResult(result, time, coordinate_status))
    return tuple(results)
