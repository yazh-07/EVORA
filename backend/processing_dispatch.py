"""P14B registered first layouts; content validation stays with actual adapters."""
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from backend.parsers import media_detection, gps_csv, network_csv, messages_csv, text_document, mobile_csv, transactions_csv


@dataclass(frozen=True, slots=True)
class Adapter:
    kind: str
    parser_version: str
    parse: Callable[..., tuple]
    max_source_bytes: int
    max_data_rows: int | None
    max_device_mentions: int | None = None
    max_source_lines: int | None = None
    max_amount_chars: int | None = None


# Import actual producer metadata rather than a parallel format/version definition.
# No runtime registration or filename/MIME fallback changes an accepted selection.
ADAPTERS = MappingProxyType({
    'image': Adapter('image', media_detection.PARSER_VERSION, media_detection.parse_image,
                     media_detection.MAX_SOURCE_BYTES, media_detection.MAX_DATA_ROWS),
    'video': Adapter('video', media_detection.PARSER_VERSION, media_detection.parse_video,
                     media_detection.MAX_SOURCE_BYTES, media_detection.MAX_DATA_ROWS),
    'transaction': Adapter('transaction', transactions_csv.PARSER_VERSION, transactions_csv.parse_transactions_csv,
                           transactions_csv.MAX_SOURCE_BYTES, transactions_csv.MAX_DATA_ROWS,
                           max_amount_chars=transactions_csv.MAX_AMOUNT_CHARS),
    'mobile_log': Adapter('mobile_log', mobile_csv.PARSER_VERSION, mobile_csv.parse_mobile_csv,
                          mobile_csv.MAX_SOURCE_BYTES, mobile_csv.MAX_DATA_ROWS),
    'document': Adapter('document', text_document.PARSER_VERSION, text_document.parse_text_document,
                        text_document.MAX_SOURCE_BYTES, None, max_source_lines=text_document.MAX_SOURCE_LINES),
    'network_log': Adapter('network_log', network_csv.PARSER_VERSION, network_csv.parse_network_csv,
                           network_csv.MAX_SOURCE_BYTES, network_csv.MAX_DATA_ROWS),
    'gps': Adapter('gps', gps_csv.PARSER_VERSION, gps_csv.parse_gps_csv,
                   gps_csv.MAX_SOURCE_BYTES, gps_csv.MAX_DATA_ROWS),
    'message': Adapter('message', messages_csv.PARSER_VERSION, messages_csv.parse_messages_csv,
                       messages_csv.MAX_SOURCE_BYTES, messages_csv.MAX_DATA_ROWS, messages_csv.MAX_DEVICE_MENTIONS),
})


def adapter_for(kind: str) -> Adapter | None:
    """Select declared kind only; invoking its parser verifies actual content."""
    return ADAPTERS.get(kind)
