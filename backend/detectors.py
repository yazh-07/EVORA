"""Deterministic, source-cited candidate detectors over frozen same-case inputs.

Rules describe reported records, never verified identity, missing occurrences or
source falsity. UTC-only comparisons exclude raw dates and media offsets. Source
independence/reliability cannot be inferred from filenames or extraction scores.
Optional origin_id and coverage_start/end_utc are private, established metadata;
ordinary Evidence wire records do not assert either.
"""
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from itertools import combinations
import json
from statistics import median
from uuid import UUID, uuid5

from backend.graph_links import Finding, _references, _same_case
from backend.graph_nodes import _text, _uuid
from backend.parsers.transactions_csv import normalize_amount, validate_currency
from backend.triage.policy import SourceSupport, corroboration

DETECTOR_VERSION = 'multi-modal-detectors/1'
CONFLICT_LOCATION_RULE = 'conflict_simultaneous_location:v1'
CONFLICT_TIME_RULE = 'conflict_reported_event_time:v1'
GAP_RULE = 'gap_log_window:v1;threshold_seconds=3600'
CLUSTER_RULE = 'cluster_connected_components:v1'
ANOMALY_AMOUNT_RULE = 'anomaly_amount:v1;minimum_peers=4;median_multiple=10;mad_multiple=6'
ANOMALY_HOURS_RULE = 'anomaly_utc_hours:v1;outside=06:00-22:00'
CORROBORATION_RULE = 'corroboration_reported_claim:v1'
HYPOTHESIS_RULE = 'hypothesis_competing_source_reports:v1'


def _instant(value):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('Expected a normalized timestamp with timezone')
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError('Expected a normalized timestamp with timezone') from None
    if result.utcoffset() is None:
        raise ValueError('Expected a normalized timestamp with timezone')
    return result.astimezone(timezone.utc)


def _scoped(case_id, values, category):
    """Reject conflicting UUID reuse and foreign records before any early return."""
    _uuid(case_id, 'case_id')
    records = {}
    try:
        iterator = iter(() if values is None else values)
    except TypeError:
        raise ValueError(f'{category} records must be iterable') from None
    for value in iterator:
        record = value.to_wire() if hasattr(value, 'to_wire') else value
        if not isinstance(record, Mapping):
            raise ValueError(f'{category} must be a mapping or producer value')
        identifier = _same_case(record, case_id, category)
        if identifier in records and records[identifier] != record:
            raise ValueError(f'Conflicting {category} UUID')
        records[identifier] = dict(record)
    return records


def _observations(case_id, values):
    sources = _scoped(case_id, values, 'Observation')
    evidence_runs, run_evidence = {}, {}
    for source in sources.values():
        eid = _uuid(source.get('evidence_id'), 'Observation.evidence_id')
        run = _uuid(source.get('processing_run_id'), 'Observation.processing_run_id')
        _text(source.get('source_locator'), 'Observation.source_locator')
        _text(source.get('kind'), 'Observation.kind')
        if not isinstance(source.get('normalized_value'), str):
            raise ValueError('Observation.normalized_value must be text')
        if source.get('entity_key') is not None:
            _text(source['entity_key'], 'Observation.entity_key')
        if 'observed_at_utc' in source:
            _instant(source['observed_at_utc'])
        if (evidence_runs.setdefault(eid, run) != run or run_evidence.setdefault(run, eid) != eid):
            raise ValueError('Expected one selected processing run per evidence')
    return sources


def _joined(case_id, observations, entities, events):
    sources = _observations(case_id, observations)
    candidates = _scoped(case_id, entities, 'Entity')
    records = _scoped(case_id, events, 'Event')
    for category, values in (('Entity', candidates), ('Event', records)):
        for record in values.values():
            eids, oids = _references(record, 'evidence_ids'), _references(record, 'observation_ids')
            if not set(oids) <= sources.keys() or set(eids) != {sources[oid]['evidence_id'] for oid in oids}:
                raise ValueError(f'{category} citations must resolve to their exact observation sources')
            _text(record.get('kind'), f'{category}.kind')
            if category == 'Entity':
                key = _text(record.get('candidate_key'), 'Entity.candidate_key')
                if key != f"{record['kind']}:{_text(record.get('canonical_label'), 'Entity.canonical_label')}":
                    raise ValueError('Entity candidate key disagrees with kind and label')
                if any(sources[oid].get('entity_key') not in (None, key) for oid in oids):
                    raise ValueError('Entity candidate key disagrees with source')
            else:
                _text(record.get('summary'), 'Event.summary')
                participants = record.get('entity_ids', [])
                if not isinstance(participants, (list, tuple)) or len(set(participants)) != len(participants):
                    raise ValueError('Event.entity_ids must be unique')
                if not set(participants) <= candidates.keys():
                    raise ValueError('Event cites an unknown entity')
                if 'observed_at_utc' in record:
                    instant = _instant(record['observed_at_utc'])
                    if any('observed_at_utc' not in sources[oid]
                           or _instant(sources[oid]['observed_at_utc']) != instant for oid in oids):
                        raise ValueError('Event time disagrees with its source observations')
    return sources, candidates, records


def _evidence(case_id, evidence, sources):
    records = _scoped(case_id, evidence, 'Evidence')
    if any(source['evidence_id'] not in records for source in sources.values()):
        raise ValueError('Observation cites evidence outside the selected case')
    for record in records.values():
        # Validate any supplied independence metadata, even on negative paths.
        if any(field in record for field in ('sha256', 'origin_id', 'record_sha256')):
            SourceSupport(case_id, record['id'], record.get('origin_id'), record.get('sha256'),
                          record.get('record_sha256'))
        for field in ('coverage_start_utc', 'coverage_end_utc'):
            if field in record:
                _instant(record[field])
        if ('coverage_start_utc' in record) != ('coverage_end_utc' in record):
            raise ValueError('Coverage needs both bounds')
        if 'coverage_start_utc' in record and _instant(record['coverage_end_utc']) <= _instant(record['coverage_start_utc']):
            raise ValueError('Coverage end must follow start')
    return records


def _finding(case_id, run_id, kind, rule, summary, sources, *, entities=(), contradicting=(),
             missing=(), coverage_matches=(), conflict_strength=None):
    _uuid(run_id, 'analysis_run_id')
    oids = tuple(sorted({source['id'] for source in sources}))
    eids = tuple(sorted({source['evidence_id'] for source in sources}))
    if not oids:
        raise ValueError('A finding requires source observations')
    identity = json.dumps([run_id, rule, oids, summary], separators=(',', ':'))
    return Finding(id=str(uuid5(UUID(case_id), identity)), case_id=case_id, analysis_run_id=run_id,
        kind=kind, rule=rule, summary=summary, evidence_ids=eids, observation_ids=oids,
        entity_ids=tuple(sorted(set(entities))), contradicting_evidence_ids=tuple(sorted(set(contradicting))),
        missing_information=tuple(missing), coverage_matches=tuple(sorted(coverage_matches)),
        conflict_strength=conflict_strength, confidence=0.0)


def _context(case_id, run_id):
    _uuid(case_id, 'case_id')
    _uuid(run_id, 'analysis_run_id')


def _rows(sources):
    rows = defaultdict(list)
    for source in sources.values():
        # CSV row identity includes evidence/run; columns can never join across sources.
        locator = source['source_locator'].split(', ', 1)[0]
        rows[(source['evidence_id'], source['processing_run_id'], locator)].append(source)
    return rows


def _claim_groups(entities, events):
    """Exact reported identifier claims and event reports; no fuzzy identity join."""
    groups = defaultdict(list)
    for entity in entities.values():
        groups[('identifier', entity['candidate_key'])].append(entity)
    for event in events.values():
        if 'observed_at_utc' not in event:
            continue
        keys = tuple(sorted(entities[eid]['candidate_key'] for eid in event.get('entity_ids', ())))
        groups[('event', event['kind'], event['summary'], keys,
                _instant(event['observed_at_utc']).isoformat())].append(event)
    return groups


def detect_corroboration_findings(case_id, analysis_run_id, observations, entities, events, evidence):
    """Repeated exact reports are candidates; explicit origins establish independence."""
    _context(case_id, analysis_run_id)
    sources, candidates, records = _joined(case_id, observations, entities, events)
    metadata = _evidence(case_id, evidence, sources)
    output = []
    for claim, members in sorted(_claim_groups(candidates, records).items()):
        eids = {eid for member in members for eid in member['evidence_ids']}
        if len(eids) < 2:
            continue
        cited = [sources[oid] for member in members for oid in member['observation_ids']]
        known = all(metadata[eid].get('origin_id') is not None for eid in eids)
        independent = False
        if known and all('sha256' in metadata[eid] for eid in eids):
            supports = [SourceSupport(case_id, eid, metadata[eid]['origin_id'], metadata[eid]['sha256'],
                                      metadata[eid].get('record_sha256')) for eid in sorted(eids)]
            independent = corroboration(supports[0], supports[1:]) > 0
            if not independent:
                continue
        output.append(_finding(case_id, analysis_run_id, 'corroboration', CORROBORATION_RULE,
            f"Potential corroboration of reported claim {claim!r} across {len(eids)} evidence items; "
            "requires human verification and does not establish identity or truth.", cited,
            entities=[m['id'] for m in members if m['id'] in candidates],
            missing=(() if independent else ('Underlying source independence is unverified.',))))
    return sorted(output, key=lambda item: item.id)


def detect_conflict_findings(case_id, analysis_run_id, observations, entities, events):
    """Exact-time GPS differences and differing UTC times for an exact event report.

    Temporal candidates require an exact shared report summary, kind and candidate
    keys across distinct sources; repeated ambiguous occurrences are excluded.
    Location candidates require both coordinates, one candidate key and identical
    normalized instants. Clock/precision/identity uncertainty remains explicit;
    these findings alone do not supply a supported conflict score.
    """
    _context(case_id, analysis_run_id)
    sources, candidates, records = _joined(case_id, observations, entities, events)
    locations = defaultdict(list)
    for row in _rows(sources).values():
        by_kind = {o['kind']: o for o in row}
        if not {'gps.device', 'gps.latitude', 'gps.longitude'} <= by_kind.keys():
            continue
        device = by_kind['gps.device']
        key = device.get('entity_key')
        if not key or any('observed_at_utc' not in o for o in row):
            continue
        instant = _instant(device['observed_at_utc'])
        if any(_instant(o['observed_at_utc']) != instant for o in row):
            continue
        try:
            coordinates = tuple(Decimal(by_kind[k]['normalized_value']) for k in ('gps.latitude', 'gps.longitude'))
        except InvalidOperation:
            raise ValueError('Invalid GPS coordinates') from None
        if any(not v.is_finite() or abs(v) > bound for v, bound in zip(coordinates, (90, 180))):
            raise ValueError('Invalid GPS coordinates')
        locations[(key, instant)].append((device['evidence_id'], coordinates, row))
    output = []
    for (key, instant), reports in sorted(locations.items()):
        for first, second in combinations(sorted(reports, key=lambda r: (r[0], r[2][0]['id'])), 2):
            if first[0] == second[0] or first[1] == second[1]:
                continue
            cited = first[2] + second[2]
            output.append(_finding(case_id, analysis_run_id, 'conflict', CONFLICT_LOCATION_RULE,
                f"Potential location contradiction for candidate {key!r} at {instant.isoformat()}: "
                f"reported coordinates {first[1]} and {second[1]} differ.", cited,
                entities=[e['id'] for e in candidates.values() if e['candidate_key'] == key],
                contradicting=[second[0]], conflict_strength=0.8,
                missing=('Candidate identity, clock alignment and coordinate precision require verification.',)))
    groups = defaultdict(list)
    for event in records.values():
        keys = tuple(sorted(candidates[eid]['candidate_key'] for eid in event.get('entity_ids', ())))
        if keys and 'observed_at_utc' in event:
            groups[(event['kind'], event['summary'], keys)].append(event)
    for claim, members in sorted(groups.items()):
        by_evidence = defaultdict(list)
        for member in members:
            for eid in member['evidence_ids']:
                by_evidence[eid].append(member)
        # Multiple matching reports per source cannot identify one occurrence.
        unambiguous = [values[0] for _, values in sorted(by_evidence.items()) if len(values) == 1]
        for first, second in combinations(unambiguous, 2):
            if (set(first['evidence_ids']) & set(second['evidence_ids'])
                    or _instant(first['observed_at_utc']) == _instant(second['observed_at_utc'])):
                continue
            cited = [sources[oid] for event in (first, second) for oid in event['observation_ids']]
            output.append(_finding(case_id, analysis_run_id, 'conflict', CONFLICT_TIME_RULE,
                f"Potential temporal contradiction for reported event {claim!r}: "
                f"{first['observed_at_utc']} versus {second['observed_at_utc']}.", cited,
                entities=first.get('entity_ids', []) + second.get('entity_ids', []),
                contradicting=second['evidence_ids'], conflict_strength=0.8,
                missing=('Whether reports describe the same occurrence and comparable clocks is unverified.',)))
    return sorted({finding.id: finding for finding in output}.values(), key=lambda item: item.id)


def detect_gap_findings(case_id, analysis_run_id, observations, evidence):
    """Bound adjacent reported times by candidate and log family, across sources.

    A >1 hour interval is a request for coverage, never proof of lost records.
    Only explicit established coverage intervals supply overlap/gap fractions.
    """
    _context(case_id, analysis_run_id)
    sources = _observations(case_id, observations)
    metadata = _evidence(case_id, evidence, sources)
    streams = defaultdict(lambda: defaultdict(list))
    for source in sources.values():
        family = source['kind'].partition('.')[0]
        if family not in ('gps', 'network', 'mobile') or 'observed_at_utc' not in source or not source.get('entity_key'):
            continue
        streams[(family, source['entity_key'])][_instant(source['observed_at_utc'])].append(source)
    output = []
    for (family, key), times in sorted(streams.items()):
        ordered = sorted(times)
        for start, end in zip(ordered, ordered[1:]):
            duration = (end - start).total_seconds()
            if duration <= 3600:
                continue
            matches, cited = [], list(times[start] + times[end])
            for eid, record in sorted(metadata.items()):
                if 'coverage_start_utc' not in record:
                    continue
                coverage_sources = [o for o in sources.values() if o['evidence_id'] == eid]
                if not coverage_sources:
                    continue
                overlap = max(0., (min(end, _instant(record['coverage_end_utc'])) -
                                    max(start, _instant(record['coverage_start_utc']))).total_seconds())
                matches.append((eid, overlap / duration))
                if overlap:
                    cited.extend(coverage_sources)
            output.append(_finding(case_id, analysis_run_id, 'gap', GAP_RULE,
                f"Unobserved {family} log interval for candidate {key!r}: "
                f"{start.isoformat()} to {end.isoformat()} ({duration:g} seconds). "
                "Records within this interval and continuous source coverage are unknown.", cited,
                missing=(f'Obtain surveillance or log coverage between {start.isoformat()} and {end.isoformat()}.',),
                coverage_matches=matches))
    return sorted(output, key=lambda item: item.id)


def detect_cluster_findings(case_id, analysis_run_id, graph_nodes, graph_edges):
    """Undirected connected components of actual edges, excluding isolated nodes.

    Observation citations come from component edges; evidence-only nodes cannot
    fabricate observations. Component membership is disclosed in the summary;
    entity_ids includes candidate endpoints, excluding evidence and event nodes.
    """
    _context(case_id, analysis_run_id)
    nodes = _scoped(case_id, graph_nodes, 'GraphNode')
    edges = _scoped(case_id, graph_edges, 'GraphEdge')
    adjacent = defaultdict(set)
    for node in nodes.values():
        _references(node, 'evidence_ids')
        _text(node.get('kind'), 'GraphNode.kind')
        _text(node.get('label'), 'GraphNode.label')
    allowed = {eid for node in nodes.values() for eid in node['evidence_ids']}
    for edge in edges.values():
        evidence_ids = set(_references(edge, 'evidence_ids'))
        _references(edge, 'observation_ids')
        if edge.get('from_id') not in nodes or edge.get('to_id') not in nodes:
            raise ValueError('Graph edge has an unknown endpoint')
        a, b = edge['from_id'], edge['to_id']
        if (not evidence_ids <= allowed or
                not (set(nodes[a]['evidence_ids']) | set(nodes[b]['evidence_ids'])) <= evidence_ids):
            raise ValueError('Graph edge must cite its endpoint evidence within the selected graph')
        if a != b:
            adjacent[a].add(b)
            adjacent[b].add(a)
    output, seen = [], set()
    for node in sorted(adjacent):
        if node in seen:
            continue
        component, pending = set(), [node]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacent[current] - component)
        seen.update(component)
        links = [edge for edge in edges.values() if edge['from_id'] in component and edge['to_id'] in component]
        eids = tuple(sorted({eid for edge in links for eid in edge['evidence_ids']}))
        oids = tuple(sorted({oid for edge in links for oid in edge['observation_ids']}))
        name = json.dumps([analysis_run_id, CLUSTER_RULE, sorted(component), sorted(e['id'] for e in links)])
        # A01/A02 validated graph producers own edge observation/evidence lineage.
        output.append(Finding(id=str(uuid5(UUID(case_id), name)), case_id=case_id,
            analysis_run_id=analysis_run_id, kind='cluster', rule=CLUSTER_RULE,
            summary=f"Linked component of {len(component)} nodes: {', '.join(sorted(component))}. "
                    "Candidate links do not establish identity or coordinated activity.",
            evidence_ids=eids, observation_ids=oids,
            entity_ids=tuple(sorted(n for n in component if nodes[n]['kind'] != 'evidence'
                                    and '.' not in nodes[n]['kind'])),
            missing_information=('Real-world association and source independence are unverified.',)))
    return sorted(output, key=lambda item: item.id)


def detect_anomaly_findings(case_id, analysis_run_id, observations, evidence):
    """Amount outliers within one account/currency, plus explicit UTC off-hours.

    At least four distinct peer rows are required. Magnitude must exceed both
    10x peer median and median + 6 MAD. No currency mixing or confidence use.
    UTC off-hours is a candidate review rule, not an assertion of local hours.
    Anomalies do not automatically change triage without a relevance assessment.
    """
    _context(case_id, analysis_run_id)
    sources = _observations(case_id, observations)
    _evidence(case_id, evidence, sources)
    groups, output = defaultdict(list), []
    for row in _rows(sources).values():
        by_kind = {o['kind']: o for o in row}
        if {'transaction.account', 'transaction.amount', 'transaction.currency'} <= by_kind.keys():
            account, amount, currency = (by_kind['transaction.' + key] for key in ('account', 'amount', 'currency'))
            try:
                number = Decimal(normalize_amount(amount['normalized_value']))
            except InvalidOperation:
                raise ValueError('Invalid transaction amount') from None
            if not number.is_finite():
                raise ValueError('Invalid transaction amount')
            validate_currency(currency['normalized_value'])
            _text(account['normalized_value'], 'transaction.account')
            groups[(account['normalized_value'], currency['normalized_value'])].append((number.copy_abs(), row))
        timed = [o for o in row if 'observed_at_utc' in o]
        if timed and len({_instant(o['observed_at_utc']) for o in timed}) == 1:
            instant = _instant(timed[0]['observed_at_utc'])
            if instant.hour < 6 or instant.hour >= 22:
                output.append(_finding(case_id, analysis_run_id, 'anomaly', ANOMALY_HOURS_RULE,
                    f"Source record at {instant.isoformat()} falls outside 06:00–22:00 UTC; "
                    "local working hours and case relevance require review.", timed,
                    missing=('Local timezone, expected schedule and case relevance are unassessed.',)))
    for (account, currency), values in sorted(groups.items()):
        if len(values) < 5:
            continue
        values.sort(key=lambda item: (item[0], sorted(o['id'] for o in item[1])))
        # Preserve exact exported decimal magnitudes beyond the default 28 digits.
        with localcontext() as context:
            context.prec = max(len(number.as_tuple().digits) + abs(number.as_tuple().exponent)
                               for number, _ in values) + 10
            for index, (value, row) in enumerate(values):
                # Removing one sorted item gives the peer median in O(1).
                count = len(values) - 1
                def peer_at(position):
                    return values[position if position < index else position + 1][0]
                center = (peer_at(count // 2) if count % 2 else
                          (peer_at(count // 2 - 1) + peer_at(count // 2)) / 2)
                if value <= center * 10:
                    continue
                peers = [number for other, (number, _) in enumerate(values) if other != index]
                deviation = median([abs(number - center) for number in peers])
                if value <= center + deviation * 6:
                    continue
                cited = [o for _, group_row in values for o in group_row]
                amount = next(o for o in row if o['kind'] == 'transaction.amount')
                output.append(_finding(case_id, analysis_run_id, 'anomaly', ANOMALY_AMOUNT_RULE,
                    f"Reported transaction magnitude {value} {currency} for account candidate {account!r} "
                    f"at {amount['source_locator']} in evidence {amount['evidence_id']} "
                    f"exceeds peer median {center} by the versioned outlier rule. "
                    "Abnormality does not establish criminality or case relevance.", cited,
                    missing=('Transaction context and case relevance are unassessed.',)))
    return sorted(output, key=lambda item: item.id)


def detect_hypothesis_findings(case_id, analysis_run_id, observations, findings):
    """One competing explanation per side of a cited conflict, without truth ranking."""
    _context(case_id, analysis_run_id)
    sources = _observations(case_id, observations)
    records = _scoped(case_id, findings, 'Finding')
    output = []
    for finding in sorted(records.values(), key=lambda f: f['id']):
        if finding.get('analysis_run_id') != analysis_run_id:
            raise ValueError('Finding belongs to a different analysis run')
        eids, oids = _references(finding, 'evidence_ids'), _references(finding, 'observation_ids')
        if not set(oids) <= sources.keys() or set(eids) != {sources[oid]['evidence_id'] for oid in oids}:
            raise ValueError('Finding citations must resolve to source observations')
        contradicting = finding.get('contradicting_evidence_ids', [])
        if not isinstance(contradicting, (list, tuple)):
            raise ValueError('Contradicting sources must be a list or tuple')
        for eid in contradicting:
            _uuid(eid, 'Finding.contradicting_evidence_ids')
        if len(set(contradicting)) != len(contradicting) or not set(contradicting) <= set(eids):
            raise ValueError('Contradicting sources must be cited by the finding')
        if finding['kind'] != 'conflict' or not contradicting:
            continue
        sides = (set(eids) - set(contradicting), set(contradicting))
        if not all(sides):
            continue
        for support, opposition in (sides, sides[::-1]):
            output.append(_finding(case_id, analysis_run_id, 'hypothesis', HYPOTHESIS_RULE,
                f"Hypothesis for conflict {finding['id']}: report from {', '.join(sorted(support))} "
                f"reflects the occurrence; competing report from {', '.join(sorted(opposition))} "
                "may reflect clock, location, identity or reporting error. Neither explanation is established.",
                [sources[oid] for oid in oids], entities=finding.get('entity_ids', ()),
                contradicting=opposition,
                missing=('Independent verification is required to distinguish these competing explanations.',)))
    return sorted(output, key=lambda item: item.id)
