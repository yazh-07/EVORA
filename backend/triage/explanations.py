"""A15 deterministic explanations over authorized, frozen producer inputs.

Plain text only: consumers must render source strings as text. No SHAP/model
importance is computed for the selected G02 weighted rules. This module does
not authorize reads, publish runs, or change immutable historical results.
"""
from uuid import UUID, uuid5

from backend.graph_links import RULE, derive_candidate_links
from backend.graph_nodes import _text, _uuid, build_graph_nodes
from backend.triage.factors import calculate_connectivity_factor, calculate_relevance_factor
from backend.triage.policy import (
    ATTENTION_NOTICE, BASE_WEIGHTS, POLICY_VERSION, FactorValue, _number, score_evidence,
)


def _sources(observations_by_id, case_id):
    sources = {}
    runs, owners = {}, {}
    for oid, observation in observations_by_id.items():
        _uuid(oid, 'observation map key')
        if observation.get('id') != oid or observation.get('case_id') != case_id:
            raise ValueError('Observation ID/case must match selected inputs')
        eid = _uuid(observation.get('evidence_id'), 'Observation.evidence_id')
        run = _uuid(observation.get('processing_run_id'), 'Observation.processing_run_id')
        _text(observation.get('source_locator'), 'Observation.source_locator')
        if runs.setdefault(eid, run) != run or owners.setdefault(run, eid) != eid:
            raise ValueError('Expected one selected processing run per evidence')
        sources[oid] = observation
    return sources


def _citation(source):
    return (f"observation {source['id']} at {source['source_locator']} "
            f"in evidence {source['evidence_id']}")


def generate_triage_explanation(triage_result: dict, observations_by_id: dict | None = None) -> str:
    """Explain stored G02 arithmetic; reject inconsistent score/factor records.

    TriageFactor has no observation IDs. Optional locators are explicitly
    evidence context, never asserted to be the exact factor's supporting set.
    The caller must select the same frozen processing outputs as the result.
    """
    case_id = _uuid(triage_result['case_id'], 'case_id')
    _number(triage_result['score'], 0, 100)
    factors = triage_result['factors']
    values = {}
    for factor in factors:
        _number(factor['weight'], 0, 1)
        _number(factor['contribution'], 0, 100)
        name = factor['name']
        if name in values:
            raise ValueError('Duplicate factor name')
        values[name] = FactorValue(factor['value'], factor['explanation'], tuple(factor['evidence_ids']))
    allowed = {triage_result['evidence_id']} | {eid for f in factors for eid in f['evidence_ids']}
    scored = score_evidence(evidence_id=triage_result['evidence_id'], observation_count=1,
                            factors=values, case_evidence_ids=allowed)
    if scored is None:
        raise ValueError('Unscored evidence has no TriageResult explanation')
    if (list(scored.factors) != factors or scored.score != triage_result['score']
            or scored.priority != triage_result['priority']):
        raise ValueError('Result does not agree with G02 factor arithmetic/order/priority')
    sources = None if observations_by_id is None else _sources(observations_by_id, case_id)
    lines = [f"{POLICY_VERSION}: {scored.score:.2f} points, {scored.priority}. Available factors: "
             + ', '.join(values) + '. Absent factors omitted; evaluated zero retains its weight.']
    for factor in factors:
        name = factor['name']
        lines.append(
            f"{name}: base weight {BASE_WEIGHTS[name]!r}; normalized weight {factor['weight']!r}; "
            f"value {factor['value']!r}; contribution = round(100 × {factor['value']!r} × "
            f"{factor['weight']!r}, 2) = {factor['contribution']:.2f} points. "
            f"Producer basis: {factor['explanation']} Evidence IDs: " + ', '.join(factor['evidence_ids']) + '.')
        if sources is not None:
            context = [source for oid, source in sorted(sources.items())
                       if source['evidence_id'] in factor['evidence_ids']]
            lines.append('Evidence context only (factor-specific observation attribution unavailable): '
                         + ('; '.join(_citation(source) for source in context) if context else
                            'no source locators supplied for these evidence IDs') + '.')
    total = round(sum(f['contribution'] for f in factors), 2)
    lines.append(f"Rounded contribution sum {total:.2f}; score = min(100.00, {total:.2f}) = {scored.score:.2f}.")
    if total > 100:
        lines.append(f"Rounded contribution sum {total:.2f} capped at 100.00.")
    lines.append('Weights are experimental attention parameters. Extraction confidence, source reliability, '
                 'independent corroboration and conclusion uncertainty are separate; unavailable assessments '
                 'are not inferred. SHAP/learned feature importance is not applicable to this weighted rule. '
                 + ATTENTION_NOTICE)
    return '\n'.join(lines)


def generate_finding_explanation(finding: dict, observations_by_id: dict) -> str:
    """Explain A02 only, failing closed on unsupported rules or broken joins."""
    case_id = _uuid(finding['case_id'], 'case_id')
    if finding['rule'] != RULE or finding['kind'] != 'relationship':
        raise ValueError('Unsupported finding rule/kind')
    sources = _sources(observations_by_id, case_id)
    oids, eids = finding['observation_ids'], finding['evidence_ids']
    if not oids or len(set(oids)) != len(oids) or len(set(eids)) != len(eids):
        raise ValueError('Finding sources must be nonempty and unique')
    if any(oid not in sources for oid in oids):
        raise ValueError('Missing supporting observation')
    cited = [sources[oid] for oid in sorted(oids)]
    if {source['evidence_id'] for source in cited} != set(eids) or len(eids) < 2:
        raise ValueError('Finding evidence must equal its cross-source observation sources')
    keys = {_text(source.get('entity_key'), 'Observation.entity_key') for source in cited}
    if len(keys) != 1:
        raise ValueError('Shared-identifier rule requires one exact candidate key')
    if finding['confidence'] != 0 or isinstance(finding['confidence'], bool):
        raise ValueError('A02 candidate confidence must be unassessed (0)')
    return (f"{RULE}: candidate match on exact namespaced identifier {next(iter(keys))!r} "
            'across distinct evidence items. Supported by '
            + '; '.join(_citation(source) for source in cited)
            + '. Confidence 0 is unassessed association, not a measured probability or extraction score. '
            'Real-world identity and source independence are unverified; human verification is required. '
            + ATTENTION_NOTICE)


def evaluate_counterfactual_sensitivity(
    evidence_id: str, case_id: str, entities: list, observations: list,
    removed_entity_key: str, all_case_entities: list, edges: list,
) -> tuple[dict, dict]:
    """Diagnostic target-key ablation using real A01/A02/A03/A03B/A04 producers.

    entities is the target evidence's selected entity list; all_case_entities is
    the complete selected case set. Hold the known-key denominator, observations
    and observation count fixed; remove matching target entities from the graph
    and rederive A02 links. Validate supplied baseline edges against A02 (IDs may
    come from another run). IDs/time below identify diagnostic, unpersisted runs.
    Evidence membership is inferred from caller-selected observations, not an
    authorization decision or a complete uploaded-evidence snapshot. An absent
    target key is an error; no-op score changes can occur at saturation/rounding.
    """
    from backend.triage.aggregation import aggregate_triage_result

    _uuid(case_id, 'case_id')
    _uuid(evidence_id, 'evidence_id')
    _text(removed_entity_key, 'removed_entity_key')
    by_id = {o['id']: o for o in observations}
    if len(by_id) != len(observations):
        raise ValueError('Duplicate observations')
    _sources(by_id, case_id)
    known = {entity['id']: entity for entity in all_case_entities}
    if any(known.get(entity['id']) != entity or evidence_id not in entity['evidence_ids'] for entity in entities):
        raise ValueError('Target entities must belong to target evidence and full case entity set')
    removed = {e['id'] for e in entities if e['candidate_key'] == removed_entity_key}
    if not removed:
        raise ValueError('Removed key is absent from target entities')
    evidence = [dict(id=eid, case_id=case_id, filename=eid)
                for eid in sorted({o['evidence_id'] for o in observations})]
    run = str(uuid5(UUID(case_id), f'a15:baseline:{evidence_id}:{removed_entity_key}'))
    expected, _ = derive_candidate_links(case_id, run, all_case_entities, observations)

    def content(edge):
        wire = edge.to_wire() if hasattr(edge, 'to_wire') else dict(edge)
        _uuid(wire.pop('id'), 'GraphEdge.id')
        for field in ('evidence_ids', 'observation_ids'):
            wire[field] = sorted(wire[field])
        return wire

    if sorted(map(content, edges), key=repr) != sorted(map(content, expected), key=repr):
        raise ValueError('Baseline edges must match actual A02 selected inputs')

    def compute(target, graph_entities, links, analysis_run_id):
        relevance = calculate_relevance_factor(
            evidence_id=evidence_id, case_id=case_id, target_entities=target,
            known_case_entities=all_case_entities, evidence_records=evidence, observations=observations)
        connectivity = calculate_connectivity_factor(
            evidence_id=evidence_id, case_id=case_id,
            target_nodes=build_graph_nodes(case_id, evidence, graph_entities, []), edges=links,
            observation_count=sum(o['evidence_id'] == evidence_id for o in observations))
        result = aggregate_triage_result(
            case_id=case_id, analysis_run_id=analysis_run_id, evidence_id=evidence_id,
            observation_count=sum(o['evidence_id'] == evidence_id for o in observations),
            factors=[f for f in (relevance, connectivity) if f is not None],
            case_evidence_ids=[e['id'] for e in evidence], created_at='2026-11-03T00:00:00Z')
        if result is None:
            raise ValueError('Counterfactual diagnostic requires scored target evidence')
        return result

    baseline = compute(entities, all_case_entities, expected, run)
    remaining = [entity for entity in all_case_entities if entity['id'] not in removed]
    counter_run = str(uuid5(UUID(run), 'target-key-ablation'))
    counter_edges, _ = derive_candidate_links(case_id, counter_run, remaining, observations)
    counterfactual = compute([e for e in entities if e['id'] not in removed], remaining,
                             counter_edges, counter_run)
    return baseline, counterfactual
