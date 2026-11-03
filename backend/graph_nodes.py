"""A01 source-record nodes; pure construction, without persistence or inference."""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from uuid import UUID


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

    def __post_init__(self) -> None:
        _uuid(self.id, "id")
        _uuid(self.case_id, "case_id")
        _text(self.kind, "kind")
        _text(self.label, "label")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ValueError("evidence_ids must be a nonempty tuple")
        for identifier in self.evidence_ids:
            _uuid(identifier, "evidence_ids item")
        if tuple(sorted(set(self.evidence_ids))) != self.evidence_ids:
            raise ValueError("evidence_ids must be unique and sorted")

    def to_wire(self) -> dict:
        return {"id": self.id, "case_id": self.case_id, "kind": self.kind,
                "label": self.label, "evidence_ids": list(self.evidence_ids)}


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
        identifier = _uuid(record.get("id"), f"{category}.id")
        source_case = _uuid(record.get("case_id"), f"{category}.case_id")
        if source_case != case_id:
            raise ValueError(f"{category}.case_id does not match requested case")
        node = GraphNode(id=identifier, case_id=case_id, kind=kind,
                         label=label, evidence_ids=evidence_ids)
        if identifier in nodes:
            previous_category, previous = nodes[identifier]
            if (category, node.kind, node.label) != (previous_category, previous.kind, previous.label):
                raise ValueError("Duplicate source UUID has conflicting category, kind or label")
            node = replace(previous, evidence_ids=tuple(sorted(set(previous.evidence_ids) | set(evidence_ids))))
        nodes[identifier] = category, node

    for record in _records(evidence_records, "evidence"):
        identifier = _uuid(record.get("id"), "evidence.id")
        add(record, "evidence", "evidence", record.get("filename", record.get("label")), (identifier,))
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

    return sorted((node for _, node in nodes.values()), key=lambda node: (node.kind, node.id))
