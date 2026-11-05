"""Source-backed shared-identifier and message co-mention candidate relationships."""
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from itertools import combinations
from math import isfinite
from uuid import UUID, uuid5

from backend.graph_nodes import _records, _text, _uuid, location_nodes, source_group

RULE = "candidate_link_shared_identifier:v1"
CO_MENTION_RULE = "candidate_link_co_mention:v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphEdge:
    id: str
    case_id: str
    from_id: str
    to_id: str
    evidence_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    kind: str = "shared_identifier"
    confidence: float = 0.0
    label: str = ""

    def to_wire(self) -> dict:
        wire = asdict(self)
        wire["label"] = self.label or self.kind.replace("_", " ")
        for field in ("evidence_ids", "observation_ids"):
            wire[field] = list(wire[field])
        return wire


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    id: str
    case_id: str
    analysis_run_id: str
    summary: str
    evidence_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    entity_ids: tuple[str, ...]
    # The draft FindingKind enum uses relationship, not candidate_match.
    kind: str = "relationship"
    missing_information: tuple[str, ...] = ("Real-world identity and source independence are unverified.",)
    rule: str = RULE
    confidence: float = 0.0
    contradicting_evidence_ids: tuple[str, ...] = ()
    # Private, documented coverage fractions; never an extra Finding wire field.
    coverage_matches: tuple[tuple[str, float], ...] = ()
    conflict_strength: float | None = None

    def to_wire(self) -> dict:
        wire = asdict(self)
        wire.pop("coverage_matches")
        wire.pop("conflict_strength")
        if not self.contradicting_evidence_ids:
            wire.pop("contradicting_evidence_ids")
        for field in ("evidence_ids", "observation_ids", "entity_ids", "missing_information",
                      "contradicting_evidence_ids"):
            if field not in wire:
                continue
            wire[field] = list(wire[field])
        return wire


def _same_case(record, case_id, category):
    identifier = _uuid(record.get("id"), f"{category}.id")
    if _uuid(record.get("case_id"), f"{category}.case_id") != case_id:
        raise ValueError(f"{category}.case_id does not match requested case")
    return identifier


def _references(record, field):
    values = record.get(field)
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{field} must be a nonempty list or tuple")
    for value in values:
        _uuid(value, field)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must be unique")
    return tuple(sorted(values))


def _message_body_contexts(cited_sources, key):
    """Join keyless bodies to the candidate's own cited spans in linear time."""
    mentions = {(source["evidence_id"], source["processing_run_id"],
                 source["source_locator"].partition("; chars=")[0])
                for source in cited_sources if source.get("kind") == "message.device"
                and source.get("entity_key") == key and "; chars=" in source["source_locator"]}
    return {source["id"] for source in cited_sources
            if source.get("kind") == "message.body" and "entity_key" not in source
            and (source["evidence_id"], source["processing_run_id"], source["source_locator"]) in mentions}


def derive_candidate_links(
    case_id: str,
    analysis_run_id: str,
    entities: Iterable[Mapping[str, object]],
    observations: Iterable[Mapping[str, object]] | None = None,
) -> tuple[list[GraphEdge], list[Finding]]:
    """Derive candidate edges/findings between distinct source Entity IDs.

    Consume wire mappings from a coherent authorized input selection. Nonempty
    entities require observations: UUIDs alone cannot prove source/case joins.
    Evidence references must exactly equal each entity's cited observation sources.
    Keys retain P03B spelling, namespace, whitespace and case without normalization.
    Shared identifiers require distinct evidence items. Co-mentions require a
    shared message body with each candidate's own cited mention in that row.
    Singleton candidates (including multi-source entities) never self-link.
    Duplicate identical entities are idempotent;
    conflicting UUID reuse fails atomically. Outputs sort by UUID and stay frozen.

    confidence=0 means unassessed candidate association, never extraction quality,
    measured probability or independent corroboration. Caller owns authorization,
    Evidence metadata validation (A01), frozen snapshot selection and publication.
    This function neither persists nor completes an AnalysisRun.
    """
    _uuid(case_id, "case_id")
    _uuid(analysis_run_id, "analysis_run_id")
    sources, evidence_runs, run_evidence = {}, {}, {}
    for observation in _records(() if observations is None else observations, "observation"):
        oid = _same_case(observation, case_id, "observation")
        evidence = _uuid(observation.get("evidence_id"), "observation.evidence_id")
        run = _uuid(observation.get("processing_run_id"), "observation.processing_run_id")
        _text(observation.get("source_locator"), "observation.source_locator")
        if oid in sources:
            raise ValueError("Duplicate observation UUID")
        if (evidence_runs.setdefault(evidence, run) != run
                or run_evidence.setdefault(run, evidence) != evidence):
            raise ValueError("Conflicting processing run selection")
        sources[oid] = dict(observation)

    groups, seen = defaultdict(list), {}
    for entity in _records(entities, "entity"):
        identifier = _same_case(entity, case_id, "entity")
        kind = _text(entity.get("kind"), "entity.kind")
        label = _text(entity.get("canonical_label"), "entity.canonical_label")
        key = _text(entity.get("candidate_key"), "entity.candidate_key")
        if key != f"{kind}:{label}":
            raise ValueError("Candidate key does not match entity namespace/label")
        confidence = entity.get("confidence")
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("Entity confidence must be finite in [0,1]")
        evidence_ids = _references(entity, "evidence_ids")
        observation_ids = _references(entity, "observation_ids")
        cited = []
        for oid in observation_ids:
            if oid not in sources:
                raise ValueError("Entity references an observation outside the supplied case inputs")
            source = sources[oid]
            if "entity_key" in source and source["entity_key"] != key:
                raise ValueError("Observation entity key does not match candidate key")
            cited.append(source["evidence_id"])
        if set(cited) != set(evidence_ids):
            raise ValueError("Entity evidence_ids do not match cited observation sources")
        content = (key, evidence_ids, observation_ids, confidence)
        if identifier in seen:
            if seen[identifier] != content:
                raise ValueError("Conflicting duplicate entity UUID")
            continue
        seen[identifier] = content
        groups[key].append((identifier, evidence_ids, observation_ids))

    edges, findings = [], []
    for key, members in sorted(groups.items()):
        for first, second in combinations(sorted(members), 2):
            from_id, first_evidence, first_observations = first
            to_id, second_evidence, second_observations = second
            evidence_ids = tuple(sorted(set(first_evidence) | set(second_evidence)))
            if len(evidence_ids) < 2:
                continue
            observation_ids = tuple(sorted(set(first_observations) | set(second_observations)))
            # Include run and rule so recomputation is stable and versions stay distinct.
            name = f"{analysis_run_id}:{RULE}:{from_id}:{to_id}"
            edge_id = str(uuid5(UUID(case_id), "edge:" + name))
            finding_id = str(uuid5(UUID(case_id), "finding:" + name))
            edges.append(GraphEdge(id=edge_id, case_id=case_id, from_id=from_id, to_id=to_id,
                                   evidence_ids=evidence_ids, observation_ids=observation_ids))
            findings.append(Finding(id=finding_id, case_id=case_id, analysis_run_id=analysis_run_id,
                                    summary=f"Candidate match on shared identifier {key!r} across evidence items "
                                            + ", ".join(evidence_ids)
                                            + "; requires human verification and does not establish identity or guilt.",
                                    evidence_ids=evidence_ids, observation_ids=observation_ids,
                                    entity_ids=(from_id, to_id)))

    # Index by message body: sharing a file or a generic observation is insufficient.
    bodies = defaultdict(list)
    for identifier, (key, evidence_ids, observation_ids, _) in sorted(seen.items()):
        cited = [sources[oid] for oid in observation_ids]
        for oid in _message_body_contexts(cited, key):
            bodies[oid].append((identifier, key, evidence_ids, observation_ids))
    pairs = {pair for members in bodies.values() for pair in combinations(members, 2)}
    for first, second in sorted(pairs):
        from_id, first_key, first_evidence, first_observations = first
        to_id, second_key, second_evidence, second_observations = second
        if first_key == second_key:
            continue
        evidence_ids = tuple(sorted(set(first_evidence) | set(second_evidence)))
        observation_ids = tuple(sorted(set(first_observations) | set(second_observations)))
        name = f"{analysis_run_id}:{CO_MENTION_RULE}:{from_id}:{to_id}"
        edge_id = str(uuid5(UUID(case_id), "edge:" + name))
        finding_id = str(uuid5(UUID(case_id), "finding:" + name))
        edges.append(GraphEdge(id=edge_id, case_id=case_id, from_id=from_id, to_id=to_id,
                               evidence_ids=evidence_ids, observation_ids=observation_ids,
                               kind="co_mention", confidence=0.0))
        findings.append(Finding(id=finding_id, case_id=case_id, analysis_run_id=analysis_run_id,
                                summary=f"Candidate co-mention of {first_key!r} and {second_key!r} in evidence items "
                                        + ", ".join(evidence_ids)
                                        + "; requires human verification and does not establish identity or guilt.",
                                evidence_ids=evidence_ids, observation_ids=observation_ids,
                                entity_ids=(from_id, to_id), rule=CO_MENTION_RULE, confidence=0.0))

    return sorted(edges, key=lambda item: item.id), sorted(findings, key=lambda item: item.id)


SEMANTIC_RULE = "source_semantic_relations/1"


def derive_semantic_links(case_id, analysis_run_id, evidence, entities, observations):
    """Directed relations from explicit row roles, never proximity or co-mention.

    Legacy transactions have only one account and messages have no recipient;
    those records intentionally cannot establish a transfer/communication pair.
    """
    _uuid(case_id, "case_id")
    _uuid(analysis_run_id, "analysis_run_id")
    allowed = {_same_case(item, case_id, "evidence"): item for item in evidence}
    # Reuse the strict entity/source/run validator even for standalone callers.
    derive_candidate_links(case_id, analysis_run_id, entities, observations)
    sources = {item["id"]: item for item in observations}
    if any(item["evidence_id"] not in allowed for item in observations):
        raise ValueError("Foreign semantic evidence")
    by_observation = defaultdict(list)
    for entity in entities:
        for oid in entity["observation_ids"]:
            if sources[oid].get("entity_key") == entity["candidate_key"]:
                by_observation[oid].append(entity["id"])
    edges = {}

    def add(kind, origin, target, cited):
        if origin == target:
            return
        ids = tuple(sorted({item["id"] for item in cited}))
        evidence_ids = tuple(sorted({item["evidence_id"] for item in cited}))
        name = f"{analysis_run_id}:{SEMANTIC_RULE}:{kind}:{origin}:{target}:" + ":".join(ids)
        identifier = str(uuid5(UUID(case_id), name))
        edges[identifier] = GraphEdge(id=identifier, case_id=case_id, kind=kind,
            label=kind.replace("_", " "), from_id=origin, to_id=target,
            evidence_ids=evidence_ids, observation_ids=ids)

    groups = defaultdict(list)
    for item in observations:
        groups[source_group(item)].append(item)
        if item["kind"] in ("image.detection", "video.frame_detection"):
            for target in by_observation[item["id"]]:
                add("detected_in_frame", item["evidence_id"], target, [item])
        if allowed[item["evidence_id"]].get("kind") == "document":
            for target in by_observation[item["id"]]:
                add("referenced_in", target, item["evidence_id"], [item])
    locations = {oid: node.id for node in location_nodes(case_id, observations)
                 for oid in node.properties["observation_ids"]}
    for items in groups.values():
        roles = defaultdict(list)
        for item in items:
            for eid in by_observation[item["id"]]:
                roles[item["kind"]].append((eid, item))
        coords = [item for item in items if item["id"] in locations]
        if coords:
            for eid, source in roles["gps.device"]:
                add("located_at", eid, locations[coords[0]["id"]], [source, *coords])
        pairs = [("message.sender", "message.recipient", "communicated_with"),
                 ("network.source", "network.destination", "communicated_with"),
                 ("transaction.account", "transaction.recipient", "transferred_to")]
        if any(item["kind"] == "network.event" and item["normalized_value"].casefold()
               in ("connected", "sent", "received") for item in items):
            pairs.append(("network.device", "network.ip", "assigned_ip"))
        for first, second, kind in pairs:
            for origin, a in roles[first]:
                for target, b in roles[second]:
                    add(kind, origin, target, items)
    return sorted(edges.values(), key=lambda edge: edge.id)
