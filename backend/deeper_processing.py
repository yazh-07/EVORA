"""P15 bounded internal message follow-up from completed same-case findings.

The first pass already extracts device mentions. A supported detector signal
permits an additional literal account/phone/IP scan of the same message bodies.
This never infers ownership, changes source bytes or increases parser limits.
There are no HTTP selectors. Acceptance freezes the decision and its source run.
"""
import json
from uuid import UUID, uuid4

from backend.observations import _utc_order
from backend.parsers.candidate_entities import CandidateEntity, CandidateObservation, CandidateProjection
from backend.parsers.normalization import NormalizationResult
from backend.parsers.text_entities import canonical, identifier_spans

POLICY_VERSION = 'deeper-message-identifiers/1'
ENTITY_VERSION = 'message-candidates/1;literal-identifiers/1'
CONFIG_FIELDS = frozenset(('deeper', 'deeper_policy', 'deeper_analysis_run_id', 'deeper_finding_ids'))
SIGNAL_KINDS = frozenset(('gap', 'conflict', 'anomaly', 'corroboration'))


def deeper_metadata(config):
    """Validate optional frozen policy fields for execution and provenance."""
    if not CONFIG_FIELDS.intersection(config):
        return None
    if (not CONFIG_FIELDS <= config.keys() or config['deeper'] is not True
            or config.get('kind') != 'message' or config['deeper_policy'] != POLICY_VERSION
            or config.get('entity_version') != ENTITY_VERSION):
        raise ValueError('Invalid deeper processing configuration')
    run_id, findings = config['deeper_analysis_run_id'], config['deeper_finding_ids']
    if (not isinstance(run_id, str) or str(UUID(run_id)) != run_id
            or not isinstance(findings, list) or not findings
            or any(not isinstance(fid, str) or str(UUID(fid)) != fid for fid in findings)
            or findings != sorted(set(findings))):
        raise ValueError('Invalid deeper processing signal references')
    return {key: config[key] for key in sorted(CONFIG_FIELDS)}


def select_deeper_processing(connection, case_id, evidence_id, kind):
    """Opt in only on reprocessing with an actual frozen detector signal.

    Ignore queued/failed runs. Carry an existing deeper selection forward to
    avoid silently downgrading subsequent processing when a signal disappears.
    Only signals from the latest completed analysis selecting the current output
    may start the deeper scan; foreign/stale findings cannot authorize it.
    Caller owns the acceptance transaction and performs idempotency replay first.
    """
    if kind != 'message':
        return {}
    connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
    previous = connection.execute("SELECT id,config_json FROM processing_runs WHERE case_id=? "
        "AND evidence_id=? AND status='completed' "
        'ORDER BY evora_utc_order(finished_at) DESC,id DESC LIMIT 1', (case_id, evidence_id)).fetchone()
    if previous is None:
        return {}
    prior_policy = deeper_metadata(json.loads(previous['config_json']))
    if prior_policy is not None:
        return prior_policy
    analysis = connection.execute('SELECT r.id,r.input_snapshot_json,o.findings_json FROM analysis_runs r '
        "JOIN analysis_outputs o ON o.run_id=r.id AND o.case_id=r.case_id "
        "WHERE r.case_id=? AND r.status='completed' "
        'ORDER BY evora_utc_order(r.created_at) DESC,r.id DESC LIMIT 1', (case_id,)).fetchone()
    if analysis is None:
        return {}
    snapshot = json.loads(analysis['input_snapshot_json'])
    if previous['id'] not in snapshot['processing_run_ids']:
        return {}
    observations = set(snapshot['observation_ids'])
    findings = sorted(finding['id'] for finding in json.loads(analysis['findings_json'])
        if finding['kind'] in SIGNAL_KINDS and finding['case_id'] == case_id
        and finding['analysis_run_id'] == analysis['id'] and evidence_id in finding['evidence_ids']
        and finding.get('observation_ids') and set(finding['observation_ids']) <= observations)
    if not findings:
        return {}
    return dict(deeper=True, deeper_policy=POLICY_VERSION,
                deeper_analysis_run_id=analysis['id'], deeper_finding_ids=findings)


def project_deeper_message_entities(base, *, max_mentions):
    """Append literal non-device candidates with exact decoded-body span locators.

    Reuse the established text identifier rules, preserving body/time context and
    the initial device projections. Bound total mentions by the frozen message
    mention limit; fail the whole run on overflow, leaving the last output usable.
    """
    observations, groups = list(base.observations), {}
    count = sum(item.observation.kind == 'message.device' for item in observations)
    for item in base.observations:
        body = item.observation
        if body.kind != 'message.body':
            continue
        for span in identifier_spans(body.raw_value):
            kind, start, end = span['kind'], span['start'], span['end']
            if kind == 'device':
                continue
            count += 1
            if count > max_mentions:
                raise ValueError('Deeper message mention limit')
            raw = body.raw_value[start:end]
            value = canonical(kind, raw)
            key = kind + ':' + value
            mention = CandidateObservation(id=uuid4(), case_id=body.case_id, evidence_id=body.evidence_id,
                processing_run_id=body.processing_run_id, kind='message.' + kind,
                source_locator=f'{body.source_locator}; chars={start}:{end}', raw_value=raw,
                normalized_value=value, observed_at_raw=body.observed_at_raw,
                observed_at_utc=body.observed_at_utc, extraction_confidence=0, entity_key=key)
            observations.append(NormalizationResult(mention, item.time, 'not_applicable'))
            refs = groups.setdefault((kind, value), (set(), set()))
            refs[0].add(body.evidence_id)
            # The exact-key span is the entity source. A generic message body
            # cannot justify a non-device co-mention under the existing rule.
            refs[1].add(mention.id)
    entities = tuple(CandidateEntity(uuid4(), observations[0].observation.case_id, kind, value,
        kind + ':' + value, tuple(sorted(evidence, key=str)), tuple(sorted(refs, key=str)))
        for (kind, value), (evidence, refs) in sorted(groups.items()))
    return CandidateProjection(tuple(observations), base.entities + entities, version=ENTITY_VERSION)
