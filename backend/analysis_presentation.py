"""Consolidate redundant identifier findings; keep every underlying graph edge."""
from collections import defaultdict
from uuid import UUID, uuid5
from backend.graph_links import Finding, RULE

GROUP_RULE = 'candidate_identifier_group:v1'

def consolidate_identifiers(case_id, run_id, findings, entities):
    keys = {item['id']: item.get('candidate_key') for item in entities}
    groups, retained = defaultdict(list), []
    for finding in findings:
        candidates = {keys.get(identifier) for identifier in finding.entity_ids}
        if finding.rule == RULE and len(candidates) == 1 and None not in candidates:
            groups[next(iter(candidates))].append(finding)
        else:
            retained.append(finding)
    for key, items in sorted(groups.items()):
        if len(items) == 1:
            retained.extend(items); continue
        redundant = [finding for finding in retained
            if finding.kind in ('corroboration', 'cluster') and finding.entity_ids and
            {keys.get(identifier) for identifier in finding.entity_ids} == {key} and
            set(finding.entity_ids) <= {identifier for item in items for identifier in item.entity_ids} and
            (finding.kind == 'cluster' or 'Underlying source independence is unverified.' in finding.missing_information)]
        retained = [finding for finding in retained if finding not in redundant]
        items = items + redundant
        evidence = tuple(sorted({i for item in items for i in item.evidence_ids}))
        observations = tuple(sorted({i for item in items for i in item.observation_ids}))
        members = tuple(sorted({i for item in items for i in item.entity_ids}))
        retained.append(Finding(id=str(uuid5(UUID(case_id), f'{run_id}:{GROUP_RULE}:{key}:'+':'.join(members))),
            case_id=case_id, analysis_run_id=run_id, rule=GROUP_RULE,
            summary=f"Identifier {key!r} appears in {len(evidence)} sources ({len(members)} source candidates). "
                'Grouped mentions require verification; they do not establish one real-world identity or independent corroboration.',
            evidence_ids=evidence, observation_ids=observations, entity_ids=members))
    return retained
