"""Seven source-backed G02 factors from authorized, frozen same-case inputs."""
from bisect import bisect_left
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


def _factor_context(name, evidence_id, case_id, weight):
    _uuid(case_id, 'case_id')
    _uuid(evidence_id, 'evidence_id')
    weight = BASE_WEIGHTS[name] if weight is None else weight
    if (isinstance(weight, bool) or not isinstance(weight, (int, float))
            or not math.isfinite(weight) or not 0 <= weight <= 1):
        raise ValueError('weight must be a finite number in [0,1]')
    return float(weight)


def _factor(name, value, weight, explanation, evidence_ids):
    if value is None:
        return None
    return dict(name=name, value=value, weight=weight, contribution=round(value * weight * 100, 2),
                explanation=f'{explanation} {ATTENTION_NOTICE}', evidence_ids=sorted(set(evidence_ids)))


def calculate_temporal_proximity_factor(*, evidence_id, case_id, observations,
                                        reference_timestamps=None, weight=None):
    """Nearest normalized target UTC to supplied case times or other-source UTC.

    Explicit reference strings are caller-established comparable case instants;
    mapping references additionally retain their source citations. Raw/naive
    dates, media offsets and Evidence acquisition time are never substituted.
    No target UTC or no comparable references is absent, not a negative score.
    """
    from backend.detectors import _instant, _observations
    from backend.triage.policy import temporal_proximity

    name = 'temporal_proximity'
    weight = _factor_context(name, evidence_id, case_id, weight)
    sources = _observations(case_id, observations)
    targets = [o for o in sources.values() if o['evidence_id'] == evidence_id and 'observed_at_utc' in o]
    references = []
    if reference_timestamps is None:
        references = [(_instant(o['observed_at_utc']), o['evidence_id']) for o in sources.values()
                      if o['evidence_id'] != evidence_id and 'observed_at_utc' in o]
    else:
        if isinstance(reference_timestamps, (str, bytes, Mapping)):
            raise ValueError('Reference timestamps must be an iterable of instants or observations')
        try:
            iterator = iter(reference_timestamps)
        except TypeError:
            raise ValueError('Reference timestamps must be iterable') from None
        for reference in iterator:
            if isinstance(reference, Mapping):
                checked = _observations(case_id, [reference])[reference['id']]
                if 'observed_at_utc' in checked:
                    references.append((_instant(checked['observed_at_utc']), checked['evidence_id']))
            else:
                references.append((_instant(reference), None))
    if not targets or not references:
        return None
    # One deterministic source per instant, with only the nearest two reference
    # times considered per target. Avoid a quadratic all-observation cross join.
    by_time = {}
    for instant, eid in references:
        by_time[instant] = min(by_time.get(instant, eid or ''), eid or '')
    times = sorted(by_time)
    nearest = []
    for target_time in sorted({_instant(o['observed_at_utc']) for o in targets}):
        position = bisect_left(times, target_time)
        for index in (position - 1, position):
            if 0 <= index < len(times):
                instant = times[index]
                nearest.append((abs((target_time - instant).total_seconds()), target_time, instant, by_time[instant]))
    delta, target_time, reference_time, ref_eid = min(nearest)
    return _factor(name, temporal_proximity(delta), weight,
        f'Nearest comparable reported UTC instants {target_time.isoformat()} and '
        f'{reference_time.isoformat()} are {delta:g} seconds apart (86400-second policy window).',
        [evidence_id] + ([ref_eid] if ref_eid else []))


def calculate_corroboration_factor(*, evidence_id, case_id, entities, events, evidence_records, weight=None):
    """Strongest ONE exact reported claim supported by established independent origins.

    Caller supplies frozen source-backed entities/events. Private origin_id is
    required; Evidence UUID, source_label and modality never establish an origin.
    Byte/origin/record duplicates collapse transitively using the existing policy.
    Missing origin or claim evaluation stays absent. Identifier support concerns
    only the literal reported key, never real-world identity.
    """
    from backend.detectors import _claim_groups, _evidence, _instant, _scoped
    from backend.triage.policy import SourceSupport, corroboration

    name = 'corroboration'
    weight = _factor_context(name, evidence_id, case_id, weight)
    metadata = _evidence(case_id, evidence_records, {})
    if evidence_id not in metadata:
        raise ValueError('Target evidence must belong to the authorized case')
    candidates, records = _scoped(case_id, entities, 'Entity'), _scoped(case_id, events, 'Event')
    # A01 checks source ownership and basic entity/event shape before absent paths.
    build_graph_nodes(case_id, metadata.values(), candidates.values(), records.values())
    for category, values in (('Entity', candidates), ('Event', records)):
        for record in values.values():
            _references(record, 'observation_ids')
            if category == 'Entity':
                if record.get('candidate_key') != f"{record['kind']}:{record['canonical_label']}":
                    raise ValueError('Entity candidate_key must agree with kind and label')
            else:
                if not set(record.get('entity_ids', ())) <= candidates.keys():
                    raise ValueError('Event cites an unknown entity')
                if 'observed_at_utc' in record:
                    _instant(record['observed_at_utc'])
    supports = {eid: SourceSupport(case_id, eid, record.get('origin_id'), record.get('sha256'),
                                  record.get('record_sha256')) for eid, record in metadata.items()}
    if entities is None or events is None or supports[evidence_id].origin_id is None:
        return None
    evaluated = []
    for claim, members in sorted(_claim_groups(candidates, records).items()):
        eids = {eid for member in members for eid in member['evidence_ids']}
        if evidence_id in eids:
            value = corroboration(supports[evidence_id], [supports[eid] for eid in sorted(eids - {evidence_id})])
            evaluated.append((value, repr(claim), sorted(eids)))
    if not evaluated:
        return None
    value, claim, citations = max(evaluated, key=lambda item: (item[0], item[1]))
    return _factor(name, value, weight,
        f'Independent-source support for one reported claim {claim}: additional distinct origin groups '
        'divided by 3, capped at 1; duplicate bytes/origins/records collapse. This does not verify identity.', citations)


def calculate_source_quality_factor(*, evidence_id, case_id, reliability_score=None, weight=None):
    """Explicit caller-owned, versioned source assessment; unknown remains absent.

    The caller must retain its assessment basis/version privately. Extraction
    confidence is not a reliability assessment and is never read here.
    """
    from backend.triage.policy import source_quality

    name = 'source_quality'
    weight = _factor_context(name, evidence_id, case_id, weight)
    return _factor(name, source_quality(reliability_score), weight,
        f'Explicit source-reliability assessment: {reliability_score}; basis/version retained by the assessor.',
        [evidence_id])


def _finding_factor_inputs(case_id, values, kind):
    from backend.detectors import _scoped
    from backend.graph_links import Finding

    try:
        original = [] if values is None else list(values)
    except TypeError:
        raise ValueError('Findings must be iterable') from None
    records = _scoped(case_id, original, 'Finding')
    private, runs = {}, set()
    for value in original:
        record = value.to_wire() if isinstance(value, Finding) else value
        identifier = record['id']
        runs.add(_uuid(record.get('analysis_run_id'), 'Finding.analysis_run_id'))
        if len(runs) > 1:
            raise ValueError('Findings must belong to one selected analysis run')
        if record.get('kind') != kind:
            raise ValueError(f'Expected {kind} findings')
        _references(record, 'evidence_ids')
        _references(record, 'observation_ids')
        _text(record.get('rule'), 'Finding.rule')
        _text(record.get('summary'), 'Finding.summary')
        contradicting = record.get('contradicting_evidence_ids', ())
        if not isinstance(contradicting, (list, tuple)):
            raise ValueError('Contradicting evidence IDs must be a list or tuple')
        for eid in contradicting:
            _uuid(eid, 'Finding.contradicting_evidence_ids')
        if len(set(contradicting)) != len(contradicting) or not set(contradicting) <= set(record['evidence_ids']):
            raise ValueError('Contradicting evidence must also be cited by finding')
        strength = value.conflict_strength if isinstance(value, Finding) else record.get('conflict_strength')
        matches = value.coverage_matches if isinstance(value, Finding) else record.get('coverage_matches', ())
        if identifier in private and private[identifier] != (strength, matches):
            raise ValueError('Conflicting private finding assessments')
        private[identifier] = strength, matches
    return records, private


def calculate_conflict_relevance_factor(*, evidence_id, case_id, conflict_findings, weight=None):
    """Max explicit supported conflict strength; uncertain detector candidates absent.

    Finding.conflict_strength is a private assessment after clock, precision and
    candidate-identity controls pass. It is never inferred from confidence. An
    evaluated no-conflict list produces zero; None means no evaluation.
    """
    from backend.triage.policy import conflict_relevance

    name = 'conflict_relevance'
    weight = _factor_context(name, evidence_id, case_id, weight)
    records, private = _finding_factor_inputs(case_id, conflict_findings, 'conflict')
    strengths, citations, uncertain = [], {evidence_id}, False
    for identifier, record in records.items():
        strength = private[identifier][0]
        # Validate all assessments even for unrelated/absent inputs.
        conflict_relevance(None if strength is None else [strength])
        if evidence_id in record['evidence_ids']:
            if strength is None:
                uncertain = True
            else:
                strengths.append(strength)
                citations.update(record['evidence_ids'])
    value = conflict_relevance(None if conflict_findings is None or (uncertain and not strengths) else strengths)
    return _factor(name, value, weight,
        f'Maximum supported unresolved-conflict relevance across {len(strengths)} assessed findings; '
        'uncertain candidate conflicts do not supply strengths.', citations)


def calculate_gap_relevance_factor(*, evidence_id, case_id, gap_findings, weight=None):
    """Max documented overlap/gap-duration fraction, never gap endpoint participation.

    Finding.coverage_matches carries private (evidence_id, fraction) assessments.
    Missing coverage is absent. An evaluated empty gap set is zero. Wire-only gap
    findings cannot reconstruct a coverage assessment and therefore stay absent.
    """
    from backend.triage.policy import gap_relevance

    name = 'gap_relevance'
    weight = _factor_context(name, evidence_id, case_id, weight)
    records, private = _finding_factor_inputs(case_id, gap_findings, 'gap')
    strengths, citations = [], {evidence_id}
    for identifier, record in records.items():
        matches = private[identifier][1]
        if not isinstance(matches, (list, tuple)):
            raise ValueError('Coverage matches must be evidence/fraction pairs')
        seen = set()
        for match in matches:
            if not isinstance(match, (list, tuple)) or len(match) != 2:
                raise ValueError('Coverage matches must be evidence/fraction pairs')
            eid, strength = match
            _uuid(eid, 'Coverage evidence_id')
            if eid in seen:
                raise ValueError('Duplicate coverage assessment')
            seen.add(eid)
            gap_relevance([strength])
            if strength > 0 and eid not in record['evidence_ids']:
                raise ValueError('Positive coverage match must cite its evidence')
            if eid == evidence_id:
                strengths.append(strength)
                citations.update(record['evidence_ids'])
    value = gap_relevance(None if gap_findings is None or (records and not strengths) else strengths)
    return _factor(name, value, weight,
        f'Maximum documented coverage overlap / bounded gap duration across {len(strengths)} assessments; '
        'missing records alone do not establish a coverage match.', citations)
