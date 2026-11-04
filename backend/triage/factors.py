"""Source-backed relevance/connectivity from authorized frozen inputs."""
from collections.abc import Iterable, Mapping
import math
from typing import Any

from backend.graph_links import GraphEdge, _message_body_contexts, _references, _same_case
from backend.graph_nodes import GraphNode, _records, _text, _uuid, build_graph_nodes
from backend.triage.policy import ATTENTION_NOTICE, BASE_WEIGHTS, connectivity, relevance


def calculate_connectivity_factor(
    *, evidence_id: str, case_id: str, target_nodes: Iterable[Any],
    edges: Iterable[Any], weight: float | None = None,
    observation_count: int | None = None,
) -> dict | None:
    """Bounded degree of the target evidence's node set, never neighbor scores.

    Supply the complete selected A01 graph nodes and A02 edges, as immutable
    values or wire mappings. Nodes citing evidence_id form the target set;
    links within that set (including self-loops) add no neighbors. Each distinct
    external endpoint counts once, in either direction, regardless of parallel
    edges, confidence or source repetition. Citations union incident edge and
    available neighbor-node evidence IDs plus the target Evidence.

    None nodes/edges or unknown/zero target observation_count means absent;
    evaluated empty edges with positive observations means zero. Validate all
    supplied records before returning absent. Endpoints must resolve whenever
    nodes are available. Caller must authorize and select coherent frozen inputs
    and verify Evidence/Observation ownership/locators via A01/A02: this narrow
    interface cannot independently join sources or prove observation_count.
    A04 normalizes weights; A05 owns snapshot selection/publication.
    """
    _uuid(case_id, "case_id")
    _uuid(evidence_id, "evidence_id")
    weight = BASE_WEIGHTS["connectivity"] if weight is None else weight
    if (isinstance(weight, bool) or not isinstance(weight, (int, float))
            or not math.isfinite(weight) or not 0 <= weight <= 1):
        raise ValueError("weight must be a finite number in [0,1]")
    if observation_count is not None and (type(observation_count) is not int or observation_count < 0):
        raise ValueError("observation_count must be a nonnegative integer or None")

    def records(values, value_type, category):
        try:
            iterator = iter(() if values is None else values)
        except TypeError:
            raise ValueError(f"{category} records must be iterable") from None
        for value in iterator:
            record = value.to_wire() if isinstance(value, value_type) else value
            if not isinstance(record, Mapping):
                raise ValueError(f"{category} must be a wire mapping or producer value")
            yield record

    nodes, links = {}, {}
    for record in records(target_nodes, GraphNode, "GraphNode"):
        identifier = _same_case(record, case_id, "GraphNode")
        _text(record.get("kind"), "GraphNode.kind")
        _text(record.get("label"), "GraphNode.label")
        _references(record, "evidence_ids")
        if identifier in nodes and nodes[identifier] != record:
            raise ValueError("Conflicting GraphNode UUID")
        nodes[identifier] = record
    targets = {identifier for identifier, node in nodes.items() if evidence_id in node["evidence_ids"]}
    neighbors, citations = set(), {evidence_id}
    for record in records(edges, GraphEdge, "GraphEdge"):
        identifier = _same_case(record, case_id, "GraphEdge")
        start = _uuid(record.get("from_id"), "GraphEdge.from_id")
        end = _uuid(record.get("to_id"), "GraphEdge.to_id")
        _text(record.get("kind"), "GraphEdge.kind")
        evidence_ids = _references(record, "evidence_ids")
        _references(record, "observation_ids")
        confidence = record.get("confidence")
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("GraphEdge.confidence must be finite in [0,1]")
        if identifier in links and links[identifier] != record:
            raise ValueError("Conflicting GraphEdge UUID")
        links[identifier] = record
        if target_nodes is not None and (start not in nodes or end not in nodes):
            raise ValueError("GraphEdge endpoint is outside the selected graph")
        for source, neighbor in ((start, end), (end, start)):
            if source in targets and neighbor not in targets:
                if evidence_id not in evidence_ids:
                    raise ValueError("Incident edge must cite target evidence")
                neighbors.add(neighbor)
                citations.update(evidence_ids)
                citations.update(nodes[neighbor]["evidence_ids"])
    if target_nodes is None or edges is None or observation_count in (None, 0):
        return None
    value = connectivity(neighbors)
    return {
        "name": "connectivity", "value": value, "weight": float(weight),
        "contribution": round(value * weight * 100, 2),
        "explanation": (f"Connected to {len(neighbors)} distinct case graph "
                        f"neighbor{'s' if len(neighbors) != 1 else ''} via candidate links. "
                        f"{ATTENTION_NOTICE}"),
        "evidence_ids": sorted(citations),
    }


def calculate_relevance_factor(
    *, evidence_id: str, case_id: str,
    target_entities: Iterable[Mapping] | None,
    known_case_entities: Iterable[Mapping] | None,
    evidence_records: Iterable[Mapping], observations: Iterable[Mapping],
    weight: float | None = None,
) -> dict | None:
    """Unique exact target/known key intersection divided by unique known keys.

    Entity inputs are P03B wire mappings, never unscoped labels. The complete
    same-case Evidence allowlist and source observations are required to check
    ownership/lineage, even on absent paths. Caller authorizes the case, selects
    completed immutable outputs and supplies the full known entity set. A04/A05
    own snapshot selection, normalization of aggregate weights and publication.
    Message body context must join a cited exact-key mention in that source row;
    a shared body need not carry a single entity_key for all its candidates.

    None target means unevaluated; [] means evaluated with no candidates.
    No target observations or no known keys means absent. Exact namespaced keys
    preserve case/spacing/Unicode; repeated mentions never boost relevance.
    Keep the exact policy float (no intermediate rounding); round contribution
    only. This does not establish source truth, identity or corroboration.
    """
    _uuid(case_id, "case_id")
    _uuid(evidence_id, "evidence_id")
    weight = BASE_WEIGHTS["relevance"] if weight is None else weight
    if (isinstance(weight, bool) or not isinstance(weight, (int, float))
            or not math.isfinite(weight) or not 0 <= weight <= 1):
        raise ValueError("weight must be a finite number in [0,1]")
    targets = None if target_entities is None else list(_records(target_entities, "Entity"))
    known = None if known_case_entities is None else list(_records(known_case_entities, "Entity"))
    entities = (targets or []) + (known or [])
    evidence = list(_records(evidence_records, "Evidence"))
    # A01 validates source UUIDs, case ownership and the Evidence allowlist.
    build_graph_nodes(case_id, evidence, entities, [])
    allowed = {record["id"] for record in evidence}
    if evidence_id not in allowed:
        raise ValueError("Target evidence must belong to the authorized case")
    sources, evidence_runs, run_evidence = {}, {}, {}
    for record in _records(observations, "Observation"):
        oid = _uuid(record.get("id"), "Observation.id")
        if _uuid(record.get("case_id"), "Observation.case_id") != case_id:
            raise ValueError("Observation.case_id does not match requested case")
        eid = _uuid(record.get("evidence_id"), "Observation.evidence_id")
        run = _uuid(record.get("processing_run_id"), "Observation.processing_run_id")
        _text(record.get("source_locator"), "Observation.source_locator")
        if eid not in allowed or oid in sources:
            raise ValueError("Observation must be unique and cite authorized evidence")
        if (evidence_runs.setdefault(eid, run) != run
                or run_evidence.setdefault(run, eid) != eid):
            raise ValueError("Expected one selected processing run per Evidence")
        sources[oid] = record

    seen = {}
    for entity in entities:
        key = _text(entity.get("candidate_key"), "Entity.candidate_key")
        kind = _text(entity.get("kind"), "Entity.kind")
        label = _text(entity.get("canonical_label"), "Entity.canonical_label")
        if key != f"{kind}:{label}":
            raise ValueError("Entity candidate_key must agree with kind and label")
        identifier = entity["id"]
        if identifier in seen and seen[identifier] != entity:
            raise ValueError("Conflicting Entity UUID")
        seen[identifier] = entity
        oids = entity.get("observation_ids")
        eids = entity.get("evidence_ids")
        if not isinstance(oids, (list, tuple)) or not oids:
            raise ValueError("Entity source IDs must be nonempty and unique")
        for oid in oids:
            _uuid(oid, "Entity.observation_ids item")
        if len(set(oids)) != len(oids) or len(set(eids)) != len(eids):
            raise ValueError("Entity source IDs must be nonempty and unique")
        cited_sources = [sources[oid] for oid in oids if oid in sources]
        body_contexts = _message_body_contexts(cited_sources, key)
        cited_evidence = set()
        for oid in oids:
            source = sources.get(oid)
            if source is None or (source.get("entity_key") != key and oid not in body_contexts and source.get("kind") != "text.line"):
                raise ValueError("Entity must resolve to a source observation with its exact key")
            cited_evidence.add(source["evidence_id"])
        if cited_evidence != set(eids):
            raise ValueError("Entity Evidence IDs must equal its observation sources")
    for entity in targets or []:
        if evidence_id not in entity["evidence_ids"] or not any(
                sources[oid]["evidence_id"] == evidence_id for oid in entity["observation_ids"]):
            raise ValueError("Target entity must be backed by target evidence")

    known_keys = None if known is None else {entity["candidate_key"] for entity in known}
    matched = None if targets is None or evidence_id not in evidence_runs else {
        entity["candidate_key"] for entity in targets
    } & (known_keys or set())
    value = relevance(matched, known_keys)
    if value is None:
        return None
    keys = ", ".join(sorted(matched)) if matched else "none"
    return {
        "name": "relevance", "value": value, "weight": float(weight),
        "contribution": round(value * weight * 100, 2),
        "explanation": (f"Matched {len(matched)} of {len(known_keys)} known case "
                        f"candidate entities: {keys}. {ATTENTION_NOTICE}"),
        "evidence_ids": [evidence_id],
    }
