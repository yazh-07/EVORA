"""A01 source-record nodes; pure construction, without persistence or inference."""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from uuid import UUID, uuid5
from types import MappingProxyType
import json
import math


def _uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a lowercase canonical UUID string")
    try:
        canonical = str(UUID(value))
    except ValueError:
        raise ValueError(f"{field} must be a lowercase canonical UUID string") from None
    if value != canonical:
        raise ValueError(f"{field} must be a lowercase canonical UUID string")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")
    return value


def _freeze_properties(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_properties(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_properties(item) for item in value)
    return value


def _wire_properties(value):
    if isinstance(value, Mapping):
        return {key: _wire_properties(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_wire_properties(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphNode:
    """Immutable GraphNode value; to_wire returns only the contract's fields.

    Labels and kinds retain source text. Nonblank text and canonical UUIDs are
    stricter internal acceptance rules than the draft's unconstrained strings.
    Case membership is checked by build_graph_nodes, using caller-selected inputs.
    """

    id: str
    case_id: str
    kind: str
    label: str
    evidence_ids: tuple[str, ...]
    entity_type: str = ""
    properties: Mapping = field(default_factory=dict)

    def __post_init__(self) -> None:
        _uuid(self.id, "id")
        _uuid(self.case_id, "case_id")
        _text(self.kind, "kind")
        _text(self.label, "label")
        _text(self.entity_type or self.kind, "entity_type")
        if not isinstance(self.properties, Mapping):
            raise ValueError("properties must be a mapping")
        json.dumps(_wire_properties(self.properties), allow_nan=False)
        object.__setattr__(self, "properties", _freeze_properties(self.properties))
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ValueError("evidence_ids must be a nonempty tuple")
        for identifier in self.evidence_ids:
            _uuid(identifier, "evidence_ids item")
        if tuple(sorted(set(self.evidence_ids))) != self.evidence_ids:
            raise ValueError("evidence_ids must be unique and sorted")

    def to_wire(self) -> dict:
        return {"id": self.id, "case_id": self.case_id, "kind": self.kind,
                "label": self.label, "evidence_ids": list(self.evidence_ids),
                "entity_type": self.entity_type or self.kind, "properties": _wire_properties(self.properties)}


def _records(values: Iterable[Mapping[str, object]], category: str):
    try:
        iterator = iter(values)
    except TypeError:
        raise ValueError(f"{category} records must be an iterable of mappings") from None
    for record in iterator:
        if not isinstance(record, Mapping):
            raise ValueError(f"{category} record must be a mapping")
        yield record


def build_graph_nodes(
    case_id: str,
    evidence_records: Iterable[Mapping[str, object]],
    entity_records: Iterable[Mapping[str, object]],
    event_records: Iterable[Mapping[str, object]],
    observations: Iterable[Mapping[str, object]] = (),
) -> list[GraphNode]:
    """Build nodes from selected Evidence/Entity/Event wire mappings.

    The caller authorizes/selects a coherent input set; evidence_records is its
    complete evidence allowlist. Missing/foreign sources fail closed, even when
    another duplicate is valid. All inputs are read-only and every call is atomic.
    Repeated UUIDs merge source evidence only when category, kind and label agree;
    ambiguous identity is rejected rather than resolved by iteration order.
    """
    _uuid(case_id, "case_id")
    nodes: dict[str, tuple[str, GraphNode]] = {}

    def add(record, category, kind, label, evidence_ids):
        _text(kind, f"{category}.kind")
        identifier = _uuid(record.get("id"), f"{category}.id")
        source_case = _uuid(record.get("case_id"), f"{category}.case_id")
        if source_case != case_id:
            raise ValueError(f"{category}.case_id does not match requested case")
        node = GraphNode(id=identifier, case_id=case_id, kind=kind,
                         label=label, evidence_ids=evidence_ids, entity_type={"phone": "device"}.get(kind, kind),
                         properties={key: record[key] for key in ("sha256", "size_bytes", "filename", "source_label",
                             "candidate_key", "confidence", "observed_at_utc", "observed_at_raw", "kind",
                             "observation_ids", "entity_ids")
                             if key in record})
        if identifier in nodes:
            previous_category, previous = nodes[identifier]
            if (category, node.kind, node.label) != (previous_category, previous.kind, previous.label):
                raise ValueError("Duplicate source UUID has conflicting category, kind or label")
            node = replace(previous, evidence_ids=tuple(sorted(set(previous.evidence_ids) | set(evidence_ids))))
        nodes[identifier] = category, node

    for record in _records(evidence_records, "evidence"):
        identifier = _uuid(record.get("id"), "evidence.id")
        kind = {"document": "document", "image": "camera", "video": "camera"}.get(record.get("kind"), "evidence")
        add(record, "evidence", kind, record.get("filename", record.get("label")), (identifier,))
    case_evidence_ids = frozenset(nodes)

    for category, records, label_field in (("entity", entity_records, "canonical_label"),
                                          ("event", event_records, "summary")):
        for record in _records(records, category):
            references = record.get("evidence_ids")
            if not isinstance(references, (list, tuple)) or not references:
                raise ValueError(f"{category}.evidence_ids must be a nonempty list or tuple")
            for reference in references:
                _uuid(reference, f"{category}.evidence_ids item")
                if reference not in case_evidence_ids:
                    raise ValueError(f"{category}.evidence_ids references evidence outside the supplied case")
            add(record, category, record.get("kind"), record.get(label_field), tuple(sorted(set(references))))

    for location in location_nodes(case_id, observations):
        if not set(location.evidence_ids) <= case_evidence_ids or location.id in nodes:
            raise ValueError("Invalid location source")
        nodes[location.id] = "location", location
    return sorted((node for _, node in nodes.values()), key=lambda node: (node.kind, node.id))


def source_group(observation):
    """Only join fields from the same physical source row and processing run."""
    locator = observation["source_locator"].split("; chars=")[0]
    if locator.startswith(("row ", "rows ")):
        locator = locator.split(", ", 1)[0]
    return observation["evidence_id"], observation["processing_run_id"], locator


def location_nodes(case_id, observations):
    from collections import defaultdict
    groups = defaultdict(dict)
    for item in observations:
        if item["case_id"] != case_id:
            raise ValueError("Foreign location observation")
        if item.get("kind") in ("gps.latitude", "gps.longitude"):
            group = groups[source_group(item)]
            if item["kind"] in group:
                raise ValueError("Duplicate coordinate field")
            group[item["kind"]] = item
    result = []
    for group, values in sorted(groups.items()):
        if set(values) != {"gps.latitude", "gps.longitude"}:
            continue
        lat, lon = values["gps.latitude"]["normalized_value"], values["gps.longitude"]["normalized_value"]
        if not (math.isfinite(float(lat)) and math.isfinite(float(lon)) and
                -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
            raise ValueError("Invalid graph coordinate")
        result.append(GraphNode(id=str(uuid5(UUID(case_id), "location:" + ":".join(group))),
            case_id=case_id, kind="location", entity_type="location", label=f"{lat}, {lon}",
            evidence_ids=(group[0],), properties=dict(latitude=lat, longitude=lon,
                observation_ids=sorted(item["id"] for item in values.values()))))
    return result
