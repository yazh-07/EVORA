"""Checkpoint 4A: policy, lineage, uncertainty and real publication controls."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from uuid import uuid4

from backend import analysis, detectors as d
from backend.graph_links import Finding, derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend.tests import test_analysis as analysis_tests
from backend.tests.test_graph_nodes import validator
from backend.triage import factors as f
from backend.triage.aggregation import aggregate_triage_result
from backend.triage.policy import BASE_WEIGHTS


def uid():
    return str(uuid4())


class Inputs(unittest.TestCase):
    def setUp(self):
        self.case, self.run = uid(), uid()
        self.evidence, self.observations, self.entities, self.events = [], [], [], []
        self.first = self.add_evidence('source-1')
        self.second = self.add_evidence('source-2')
        self.a = self.add_observation(self.first, time='2026-01-01T10:00:00Z')
        self.b = self.add_observation(self.second, time='2026-01-01T11:00:00Z')
        self.ea = self.add_entity(self.a)
        self.eb = self.add_entity(self.b)

    def add_evidence(self, origin):
        record = dict(id=uid(), case_id=self.case, filename=f'{origin}.csv', origin_id=origin,
                      sha256=hashlib.sha256(origin.encode()).hexdigest())
        self.evidence.append(record)
        return record

    def add_observation(self, evidence, *, kind='network.device', key='device:D-7', value='D-7',
                        time=None, locator=None):
        existing = next((o for o in self.observations if o['evidence_id'] == evidence['id']), None)
        record = dict(id=uid(), case_id=self.case, evidence_id=evidence['id'],
            processing_run_id=existing['processing_run_id'] if existing else uid(), kind=kind,
            normalized_value=value, raw_value=value, source_locator=locator or f'row {len(self.observations) + 2}, device_id',
            extraction_confidence=0.)
        if key is not None:
            record['entity_key'] = key
        if time is not None:
            record['observed_at_utc'] = time
        self.observations.append(record)
        return record

    def add_entity(self, observation):
        kind, _, label = observation['entity_key'].partition(':')
        record = dict(id=uid(), case_id=self.case, kind=kind, canonical_label=label,
            candidate_key=observation['entity_key'], evidence_ids=[observation['evidence_id']],
            observation_ids=[observation['id']], confidence=0.)
        self.entities.append(record)
        return record

    def add_event(self, observation, entity, summary='Source reports unique event X'):
        record = dict(id=uid(), case_id=self.case, kind='network.activity', summary=summary,
            evidence_ids=[observation['evidence_id']], observation_ids=[observation['id']],
            entity_ids=[entity['id']], observed_at_utc=observation['observed_at_utc'], confidence=0.)
        self.events.append(record)
        return record

    def finding(self, kind, **changes):
        return Finding(id=uid(), case_id=self.case, analysis_run_id=self.run, kind=kind,
            rule='synthetic_supported_assessment:v1', summary='Explicit synthetic assessed finding',
            evidence_ids=tuple(sorted([self.first['id'], self.second['id']])),
            observation_ids=tuple(sorted([self.a['id'], self.b['id']])), entity_ids=(), **changes)

    def factor(self, function, **changes):
        result = function(evidence_id=self.first['id'], case_id=self.case, **changes)
        if result is not None:
            validator('TriageFactor').validate(result)
        return result

    def validate_findings(self, findings):
        for finding in findings:
            self.assertIsInstance(finding, Finding)
            wire = finding.to_wire()
            validator('Finding').validate(wire)
            sources = [o for o in self.observations if o['id'] in wire['observation_ids']]
            self.assertEqual(set(wire['evidence_ids']), {o['evidence_id'] for o in sources})
        return findings


class FactorTests(Inputs):
    def temporal(self, **changes):
        return self.factor(f.calculate_temporal_proximity_factor,
                           **(dict(observations=self.observations) | changes))

    def corroboration(self, **changes):
        return self.factor(f.calculate_corroboration_factor, **(dict(entities=self.entities,
            events=self.events, evidence_records=self.evidence) | changes))

    def test_temporal_nearest_other_source_and_utc_equivalence(self):
        factor = self.temporal()
        self.assertEqual(factor['value'], 1 - 3600 / 86400)
        self.assertEqual(factor['weight'], .05)
        self.assertEqual(factor['contribution'], round(factor['value'] * 5, 2))
        self.assertEqual(set(factor['evidence_ids']), {self.first['id'], self.second['id']})
        self.b['observed_at_utc'] = '2026-01-01T11:00:00+01:00'
        self.assertEqual(self.temporal()['value'], 1.)

    def test_temporal_explicit_nearest_reference_symmetric_and_zero(self):
        for reference in ('2026-01-01T09:00:00Z', '2026-01-01T11:00:00Z'):
            self.assertEqual(self.temporal(reference_timestamps=[reference])['value'], 1 - 3600 / 86400)
        self.assertEqual(self.temporal(reference_timestamps=['2026-01-02T10:00:00Z'])['value'], 0.)
        self.assertEqual(self.temporal(reference_timestamps=['2026-01-03T10:00:00Z',
                                                            '2026-01-01T10:00:00Z'])['value'], 1.)
        self.assertEqual(self.temporal(reference_timestamps=[self.b]), self.temporal())

    def test_temporal_absent_raw_time_media_offsets_and_single_source(self):
        for changes in (dict(observations=[]), dict(observations=None), dict(observations=[self.a]),
                        dict(reference_timestamps=[])):
            self.assertIsNone(self.temporal(**changes))
        self.a.pop('observed_at_utc')
        self.a['observed_at_raw'] = '2026-01-01 10:00:00'
        self.assertIsNone(self.temporal())
        self.a['kind'] = 'transcript.segment'
        self.a['source_locator'] = 'media:start_ms=0;end_ms=1000'
        self.assertIsNone(self.temporal())

    def test_temporal_invalid_timestamps_references_and_foreign_sources(self):
        for value in ('bad', '2026-01-01T10:00:00', 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.temporal(reference_timestamps=[value])
        for value in ('2026-01-01T10:00:00Z', {}, b'bad'):
            with self.assertRaises(ValueError):
                self.temporal(reference_timestamps=value)
        with self.assertRaises(ValueError):
            self.temporal(observations=[dict(self.b, case_id=uid())], reference_timestamps=[])
        with self.assertRaises(ValueError):
            self.temporal(observations=[dict(self.a, observed_at_utc='bad')])

    def test_corroboration_additional_origins_saturation_and_no_mention_boost(self):
        self.assertEqual(self.corroboration()['value'], 1 / 3)
        self.assertEqual(self.corroboration(entities=self.entities * 3), self.corroboration())
        for origin in ('third', 'fourth', 'fifth'):
            evidence = self.add_evidence(origin)
            self.add_entity(self.add_observation(evidence))
        factor = self.corroboration()
        self.assertEqual(factor['value'], 1.)
        self.assertEqual(len(factor['evidence_ids']), 5)

    def test_corroboration_zero_duplicates_unknown_and_no_matching_claim(self):
        for field in ('origin_id', 'sha256'):
            original = self.second[field]
            self.second[field] = self.first[field]
            self.assertEqual(self.corroboration()['value'], 0.)
            self.second[field] = original
        self.first['record_sha256'] = self.second['record_sha256'] = 'f' * 64
        self.assertEqual(self.corroboration()['value'], 0.)
        self.first.pop('record_sha256')
        self.second.pop('record_sha256')
        self.second['origin_id'] = None
        self.assertEqual(self.corroboration()['value'], 0.)
        self.first['origin_id'] = None
        self.assertIsNone(self.corroboration())
        self.assertIsNone(self.corroboration(entities=None))
        self.assertIsNone(self.corroboration(events=None))

    def test_corroboration_never_unions_unrelated_claims(self):
        self.eb.update(candidate_key='device:D-8', canonical_label='D-8')
        self.assertEqual(self.corroboration()['value'], 0.)
        factor = self.corroboration()
        self.assertEqual(factor['evidence_ids'], [self.first['id']])
        self.assertIsNone(self.corroboration(entities=[], events=[]))

    def test_corroboration_uses_max_one_claim_and_transitive_duplicate_groups(self):
        third = self.add_evidence('third')
        third['sha256'] = self.second['sha256']
        self.add_entity(self.add_observation(third))
        self.assertEqual(self.corroboration()['value'], 1 / 3)
        self.second['origin_id'] = self.first['origin_id']
        self.assertEqual(self.corroboration()['value'], 0.)

    def test_corroboration_invalid_lineage_hashes_keys_and_ownership(self):
        for changes in (dict(evidence_records=[dict(self.first, case_id=uid()), self.second]),
                        dict(evidence_records=[dict(self.first, sha256='bad'), self.second]),
                        dict(entities=[dict(self.ea, evidence_ids=[uid()])]),
                        dict(entities=[dict(self.ea, candidate_key='device:wrong')]),
                        dict(entities=[dict(self.ea, observation_ids=[])]),
                        dict(events=[dict(id=uid(), case_id=self.case, kind='network.activity', summary='x',
                                         evidence_ids=[self.first['id']], observation_ids=[self.a['id']], entity_ids=[uid()])])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.corroboration(**changes)

    def test_source_quality_positive_zero_absent_and_invalid(self):
        for value in (0, .7, 1):
            factor = self.factor(f.calculate_source_quality_factor, reliability_score=value)
            self.assertEqual(factor['value'], value)
            self.assertEqual(factor['contribution'], round(value * 10, 2))
        self.assertIsNone(self.factor(f.calculate_source_quality_factor))
        for bad in (True, '0.5', -.1, 1.1, float('nan'), float('inf')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.factor(f.calculate_source_quality_factor, reliability_score=bad)

    def test_conflict_max_strength_zero_absent_and_contradicting_side(self):
        findings = [self.finding('conflict', conflict_strength=.4), self.finding('conflict', conflict_strength=1.,
                    contradicting_evidence_ids=(self.first['id'],))]
        factor = self.factor(f.calculate_conflict_relevance_factor, conflict_findings=findings)
        self.assertEqual(factor['value'], 1.)
        self.assertEqual(factor['contribution'], 10.)
        self.assertEqual(self.factor(f.calculate_conflict_relevance_factor, conflict_findings=[])['value'], 0.)
        self.assertIsNone(self.factor(f.calculate_conflict_relevance_factor, conflict_findings=None))
        self.assertIsNone(self.factor(f.calculate_conflict_relevance_factor,
                                     conflict_findings=[self.finding('conflict')]))
        for strength in (True, -.1, 1.1, float('nan')):
            with self.assertRaises(ValueError):
                self.factor(f.calculate_conflict_relevance_factor,
                            conflict_findings=[self.finding('conflict', conflict_strength=strength)])

    def test_gap_max_overlap_zero_absent_and_no_endpoint_inference(self):
        gap = self.finding('gap', coverage_matches=((self.first['id'], .75), (self.second['id'], 0.)))
        self.assertEqual(self.factor(f.calculate_gap_relevance_factor, gap_findings=[gap])['value'], .75)
        self.assertEqual(self.factor(f.calculate_gap_relevance_factor,
            gap_findings=[replace(gap, coverage_matches=((self.first['id'], 0.),))])['value'], 0.)
        self.assertEqual(self.factor(f.calculate_gap_relevance_factor, gap_findings=[])['value'], 0.)
        self.assertIsNone(self.factor(f.calculate_gap_relevance_factor, gap_findings=None))
        self.assertIsNone(self.factor(f.calculate_gap_relevance_factor, gap_findings=[gap.to_wire()]))
        self.assertNotIn('coverage_matches', gap.to_wire())
        for match in ((self.first['id'], 2), ('bad', .5), (uid(), .5), (self.first['id'], True)):
            with self.assertRaises(ValueError):
                self.factor(f.calculate_gap_relevance_factor,
                            gap_findings=[replace(gap, coverage_matches=(match,))])

    def test_finding_factors_validate_foreign_cases_kinds_ids_and_private_duplicates(self):
        for function, kind, argument in ((f.calculate_conflict_relevance_factor, 'conflict', 'conflict_findings'),
                                         (f.calculate_gap_relevance_factor, 'gap', 'gap_findings')):
            finding = self.finding(kind)
            for change in (dict(case_id=uid()), dict(kind='anomaly'), dict(id='bad'),
                           dict(observation_ids=()), dict(contradicting_evidence_ids=(uid(),))):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    self.factor(function, **{argument: [replace(finding, **change)]})
        conflict = self.finding('conflict')
        with self.assertRaises(ValueError):
            self.factor(f.calculate_conflict_relevance_factor,
                        conflict_findings=[conflict, replace(conflict, conflict_strength=1.)])

    def test_all_new_factor_weights_ids_and_contributions(self):
        calls = [(f.calculate_temporal_proximity_factor, dict(observations=self.observations)),
                 (f.calculate_corroboration_factor, dict(entities=self.entities, events=[], evidence_records=self.evidence)),
                 (f.calculate_source_quality_factor, dict(reliability_score=.6)),
                 (f.calculate_conflict_relevance_factor, dict(conflict_findings=[])),
                 (f.calculate_gap_relevance_factor, dict(gap_findings=[]))]
        for function, kwargs in calls:
            for weight in (0, .3333, 1):
                factor = self.factor(function, **kwargs, weight=weight)
                self.assertEqual(factor['weight'], weight)
                self.assertEqual(factor['contribution'], round(factor['value'] * weight * 100, 2))
            for bad in (True, '0.5', -.1, 1.1, float('nan'), float('inf')):
                with self.subTest(function=function.__name__, bad=bad), self.assertRaises(ValueError):
                    self.factor(function, **kwargs, weight=bad)
            for field in ('case_id', 'evidence_id'):
                with self.assertRaises(ValueError):
                    function(**(dict(case_id=self.case, evidence_id=self.first['id']) | kwargs | {field: 'bad'}))

    def test_all_seven_factors_aggregate_normalized_weights_and_contract(self):
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, [])
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        factors = [self.factor(f.calculate_relevance_factor, target_entities=[self.ea],
            known_case_entities=self.entities, evidence_records=self.evidence, observations=self.observations),
            self.factor(f.calculate_connectivity_factor, target_nodes=nodes, edges=edges, observation_count=1),
            self.temporal(), self.corroboration(), self.factor(f.calculate_source_quality_factor, reliability_score=.8),
            self.factor(f.calculate_conflict_relevance_factor, conflict_findings=[self.finding('conflict', conflict_strength=1.)]),
            self.factor(f.calculate_gap_relevance_factor,
                        gap_findings=[self.finding('gap', coverage_matches=((self.first['id'], .5),))])]
        result = aggregate_triage_result(case_id=self.case, analysis_run_id=self.run,
            evidence_id=self.first['id'], observation_count=1, factors=factors,
            case_evidence_ids=[e['id'] for e in self.evidence], created_at='2026-01-01T10:00:00Z')
        validator('TriageResult').validate(result)
        self.assertEqual({factor['name'] for factor in result['factors']}, set(BASE_WEIGHTS))
        self.assertAlmostEqual(sum(factor['weight'] for factor in result['factors']), 1.)
        self.assertEqual(result['score'], round(sum(factor['contribution'] for factor in result['factors']), 2))

    def test_factor_order_duplicate_invariance_and_input_immutability(self):
        before = deepcopy((self.observations, self.entities, self.evidence))
        self.assertEqual(self.temporal(observations=reversed(self.observations * 2)), self.temporal())
        self.assertEqual(self.corroboration(entities=reversed(self.entities * 2),
                                          evidence_records=reversed(self.evidence)), self.corroboration())
        conflict = self.finding('conflict', conflict_strength=.8)
        self.assertEqual(self.factor(f.calculate_conflict_relevance_factor, conflict_findings=[conflict] * 3),
                         self.factor(f.calculate_conflict_relevance_factor, conflict_findings=[conflict]))
        self.assertEqual((self.observations, self.entities, self.evidence), before)

    def test_finding_factor_mixed_runs_and_malformed_collections(self):
        for function, kind, argument in ((f.calculate_conflict_relevance_factor, 'conflict', 'conflict_findings'),
                                         (f.calculate_gap_relevance_factor, 'gap', 'gap_findings')):
            finding = self.finding(kind)
            for values in (1, [finding, replace(finding, id=uid(), analysis_run_id=uid())]):
                with self.assertRaises(ValueError):
                    self.factor(function, **{argument: values})
        with self.assertRaises(ValueError):
            self.temporal(reference_timestamps=1)


class DetectorTests(Inputs):
    def conflicts(self):
        return self.validate_findings(d.detect_conflict_findings(self.case, self.run,
            self.observations, self.entities, self.events))

    def gaps(self):
        return self.validate_findings(d.detect_gap_findings(self.case, self.run, self.observations, self.evidence))

    def anomalies(self):
        return self.validate_findings(d.detect_anomaly_findings(self.case, self.run, self.observations, self.evidence))

    def gps(self, evidence, time, latitude, longitude, row=20):
        device = self.add_observation(evidence, kind='gps.device', time=time, locator=f'row {row}, device_id')
        self.add_entity(device)
        for column, value in (('latitude', latitude), ('longitude', longitude)):
            self.add_observation(evidence, kind='gps.' + column, key=None, value=value, time=time,
                                 locator=f'row {row}, {column}')

    def test_location_conflict_distinct_sources_citations_and_competing_hypotheses(self):
        self.gps(self.first, '2026-01-01T10:00:00Z', '12', '77')
        self.gps(self.second, '2026-01-01T11:00:00+01:00', '13', '77')
        conflicts = self.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].rule, d.CONFLICT_LOCATION_RULE)
        self.assertEqual(len(conflicts[0].contradicting_evidence_ids), 1)
        self.assertEqual(len(conflicts[0].observation_ids), 6)
        hypotheses = self.validate_findings(d.detect_hypothesis_findings(self.case, self.run, self.observations, conflicts))
        self.assertEqual(len(hypotheses), 2)
        self.assertEqual({h.contradicting_evidence_ids for h in hypotheses},
                         {(self.first['id'],), (self.second['id'],)})
        self.assertIsNone(self.factor(f.calculate_conflict_relevance_factor, conflict_findings=conflicts))

    def test_location_conflict_excludes_same_source_same_coordinates_and_different_times(self):
        self.gps(self.first, '2026-01-01T10:00:00Z', '12', '77')
        self.gps(self.first, '2026-01-01T10:00:00Z', '13', '77', row=21)
        self.gps(self.second, '2026-01-01T10:00:00Z', '12.0', '77.000')
        self.gps(self.second, '2026-01-01T11:00:00Z', '14', '77', row=21)
        # Only first-source row 21 vs second-source row 20 differs at the same UTC.
        self.assertEqual(len(self.conflicts()), 1)
        self.observations[:] = [o for o in self.observations if not
            (o['evidence_id'] == self.first['id'] and o['source_locator'].startswith('row 21,'))]
        self.entities[:] = [e for e in self.entities if all(oid in {o['id'] for o in self.observations} for oid in e['observation_ids'])]
        self.assertEqual(self.conflicts(), [])

    def test_temporal_conflict_exact_report_same_key_and_no_repeat_ambiguity(self):
        self.add_event(self.a, self.ea)
        self.add_event(self.b, self.eb)
        conflict = self.conflicts()
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].rule, d.CONFLICT_TIME_RULE)
        self.add_event(self.a, self.ea)  # Cannot identify a unique occurrence in source 1.
        self.assertEqual(self.conflicts(), [])

    def test_temporal_conflict_no_shared_claim_or_normalized_time(self):
        self.add_event(self.a, self.ea, summary='report A')
        second = self.add_event(self.b, self.eb, summary='report B')
        self.assertEqual(self.conflicts(), [])
        second.pop('observed_at_utc')
        self.assertEqual(self.conflicts(), [])

    def test_gap_bounded_threshold_and_coverage_overlap(self):
        self.b['observed_at_utc'] = '2026-01-01T14:00:00Z'
        gap = self.gaps()
        self.assertEqual(len(gap), 1)
        self.assertIn('14400 seconds', gap[0].summary)
        self.assertTrue(gap[0].missing_information)
        self.assertIsNone(self.factor(f.calculate_gap_relevance_factor, gap_findings=gap))
        coverage = self.add_evidence('documented-coverage')
        coverage.update(coverage_start_utc='2026-01-01T11:00:00Z', coverage_end_utc='2026-01-01T13:00:00Z')
        self.add_observation(coverage, kind='video.frame', key=None, value='frame')
        gaps = self.gaps()
        factor = f.calculate_gap_relevance_factor(case_id=self.case, evidence_id=coverage['id'], gap_findings=gaps)
        validator('TriageFactor').validate(factor)
        self.assertEqual(factor['value'], .5)
        self.assertEqual(set(factor['evidence_ids']), {e['id'] for e in self.evidence})

    def test_gap_threshold_unknown_times_other_keys_and_families(self):
        self.assertEqual(self.gaps(), [])  # Exactly one hour is not > one hour.
        self.b['observed_at_utc'] = '2026-01-01T14:00:00Z'
        self.b['entity_key'] = 'device:D-8'
        self.assertEqual(self.gaps(), [])
        self.b['entity_key'] = self.a['entity_key']
        self.b['kind'] = 'gps.device'
        self.assertEqual(self.gaps(), [])
        self.b['kind'] = self.a['kind']
        self.b.pop('observed_at_utc')
        self.assertEqual(self.gaps(), [])

    def test_gap_combines_sources_and_deduplicates_times(self):
        self.b['observed_at_utc'] = '2026-01-01T14:00:00Z'
        self.add_observation(self.second, time='2026-01-01T12:00:00Z')
        gaps = self.gaps()
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all('7200 seconds' in gap.summary for gap in gaps))
        self.assertEqual(len(d.detect_gap_findings(self.case, self.run, self.observations * 2, self.evidence)), 2)

    def test_cluster_connected_components_reverse_edges_and_isolates(self):
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, [])
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        clusters = self.validate_findings(d.detect_cluster_findings(self.case, self.run, nodes, edges))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(set(clusters[0].entity_ids), {self.ea['id'], self.eb['id']})
        reversed_edges = [replace(edge, from_id=edge.to_id, to_id=edge.from_id) for edge in edges]
        self.assertEqual(d.detect_cluster_findings(self.case, self.run, nodes, reversed_edges), clusters)
        self.assertEqual(d.detect_cluster_findings(self.case, self.run, nodes, []), [])
        with self.assertRaises(ValueError):
            d.detect_cluster_findings(self.case, self.run, nodes, [replace(edges[0], to_id=uid())])

    def test_cluster_multiple_components_and_no_self_loop_cluster(self):
        for metadata in self.evidence:
            self.add_entity(self.add_observation(metadata, key='device:D-8', value='D-8'))
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, [])
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        self.assertEqual(len(self.validate_findings(d.detect_cluster_findings(self.case, self.run, nodes, edges))), 2)
        self.assertEqual(d.detect_cluster_findings(self.case, self.run, nodes,
            [replace(edges[0], to_id=edges[0].from_id)]), [])

    def test_anomaly_utc_hours_boundaries_and_unknown_local_hours(self):
        for instant, count in (('05:59:59', 1), ('06:00:00', 0), ('21:59:59', 0), ('22:00:00', 1)):
            self.a['observed_at_utc'] = '2026-01-01T' + instant + 'Z'
            findings = self.anomalies()
            self.assertEqual(len(findings), count)
            if count:
                self.assertEqual(findings[0].rule, d.ANOMALY_HOURS_RULE)
        self.a.pop('observed_at_utc')
        self.a['observed_at_raw'] = '2026-01-01 02:00:00'
        self.assertEqual(self.anomalies(), [])

    def transaction(self, amount, row, currency='USD', account='AC-1'):
        for column, value in (('account', account), ('amount', amount), ('currency', currency)):
            self.add_observation(self.first, kind='transaction.' + column, key=None, value=value,
                locator=f'row {row}, {column}', time='2026-01-01T12:00:00Z')

    def test_anomaly_amount_peer_statistics_signed_values_and_citations(self):
        for row, value in enumerate(('10', '11', '9', '10', '-1000'), 30):
            self.transaction(value, row)
        findings = self.anomalies()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, d.ANOMALY_AMOUNT_RULE)
        self.assertEqual(len(findings[0].observation_ids), 15)  # Includes baseline sources.
        self.assertIn('median 10', findings[0].summary)
        self.assertIn('does not establish criminality', findings[0].summary)

    def test_anomaly_amount_no_small_sample_currency_or_account_mixing(self):
        for row in range(30, 34):
            self.transaction('10', row)
        self.transaction('1000', 34, currency='EUR')
        self.transaction('1000', 35, account='AC-2')
        self.assertEqual(self.anomalies(), [])
        self.transaction('10', 36)
        self.assertEqual(self.anomalies(), [])

    def test_corroboration_candidates_missing_independence_and_duplicate_negatives(self):
        detect = lambda: self.validate_findings(d.detect_corroboration_findings(self.case, self.run,
            self.observations, self.entities, self.events, self.evidence))
        self.assertEqual(len(detect()), 1)
        self.first.pop('origin_id')
        self.assertTrue(detect()[0].missing_information)
        self.first['origin_id'] = self.second['origin_id']
        self.assertEqual(detect(), [])

    def test_hypotheses_require_conflict_validate_run_and_lineage(self):
        self.assertEqual(d.detect_hypothesis_findings(self.case, self.run, self.observations, []), [])
        self.assertEqual(d.detect_hypothesis_findings(self.case, self.run, self.observations,
            [self.finding('anomaly')]), [])
        for finding in (replace(self.finding('conflict'), analysis_run_id=uid()),
                        replace(self.finding('conflict'), observation_ids=(uid(),)),
                        self.finding('conflict', contradicting_evidence_ids=(uid(),))):
            with self.assertRaises(ValueError):
                d.detect_hypothesis_findings(self.case, self.run, self.observations, [finding])

    def test_all_observation_detectors_empty_inputs_and_invalid_cases_runs_sources(self):
        functions = [(d.detect_conflict_findings, ([], [], [])),
                     (d.detect_gap_findings, ([], [])), (d.detect_cluster_findings, ([], [])),
                     (d.detect_anomaly_findings, ([], [])), (d.detect_hypothesis_findings, ([], [])),
                     (d.detect_corroboration_findings, ([], [], [], []))]
        for function, arguments in functions:
            self.assertEqual(function(self.case, self.run, *arguments), [])
            for case, run in (('bad', self.run), (self.case, 'bad')):
                with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                    function(case, run, *arguments)
        for function in (d.detect_gap_findings, d.detect_anomaly_findings):
            with self.assertRaises(ValueError):
                function(self.case, self.run, [dict(self.a, case_id=uid())], self.evidence)
            with self.assertRaises(ValueError):
                function(self.case, self.run, self.observations, [dict(self.first, case_id=uid()), self.second])

    def test_invalid_sources_conflicting_ids_and_clock_joins(self):
        for source in (dict(self.a, observed_at_utc='bad'), dict(self.a, source_locator=''),
                       dict(self.a, processing_run_id='bad'), dict(self.a, evidence_id=uid())):
            with self.assertRaises(ValueError):
                d.detect_gap_findings(self.case, self.run, [source], self.evidence)
        with self.assertRaises(ValueError):
            d.detect_gap_findings(self.case, self.run, [self.a, dict(self.a, normalized_value='different')], self.evidence)
        with self.assertRaises(ValueError):
            d.detect_gap_findings(self.case, self.run, [self.a, dict(self.b, processing_run_id=self.a['processing_run_id'])], self.evidence)
        self.add_event(self.a, self.ea)['observed_at_utc'] = self.b['observed_at_utc']
        with self.assertRaises(ValueError):
            self.conflicts()

    def test_determinism_order_generators_run_ids_and_input_immutability(self):
        self.add_event(self.a, self.ea)
        self.add_event(self.b, self.eb)
        before = deepcopy((self.observations, self.entities, self.events, self.evidence))
        expected = self.conflicts()
        self.assertEqual(d.detect_conflict_findings(self.case, self.run, iter(reversed(self.observations)),
            iter(reversed(self.entities)), iter(reversed(self.events))), expected)
        self.assertEqual((self.observations, self.entities, self.events, self.evidence), before)
        rerun = d.detect_conflict_findings(self.case, uid(), self.observations, self.entities, self.events)
        self.assertNotEqual(rerun[0].id, expected[0].id)
        wire = expected[0].to_wire()
        wire['evidence_ids'].clear()
        self.assertTrue(expected[0].evidence_ids)

    def test_all_detectors_order_invariance(self):
        self.gps(self.first, '2026-01-01T00:00:00Z', '12', '77')
        self.gps(self.second, '2026-01-01T00:00:00Z', '13', '77')
        self.b['observed_at_utc'] = '2026-01-01T14:00:00Z'
        for row, amount in enumerate(('10', '11', '9', '10', '1000'), 30):
            self.transaction(amount, row)
        before = deepcopy((self.observations, self.entities, self.events, self.evidence))
        for function, arguments in (
                (d.detect_gap_findings, (self.observations, self.evidence)),
                (d.detect_anomaly_findings, (self.observations, self.evidence)),
                (d.detect_corroboration_findings, (self.observations, self.entities, self.events, self.evidence))):
            self.assertEqual(function(self.case, self.run, *arguments),
                             function(self.case, self.run, *(iter(reversed(values)) for values in arguments)))
        conflicts = self.conflicts()
        self.assertEqual(d.detect_hypothesis_findings(self.case, self.run, self.observations, conflicts),
                         d.detect_hypothesis_findings(self.case, self.run, reversed(self.observations), reversed(conflicts)))
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, self.events)
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        self.assertEqual(d.detect_cluster_findings(self.case, self.run, nodes, edges),
                         d.detect_cluster_findings(self.case, self.run, reversed(nodes), reversed(edges)))
        self.assertEqual((self.observations, self.entities, self.events, self.evidence), before)

    def test_invalid_coverage_and_transaction_inputs(self):
        for bounds in (dict(coverage_start_utc='2026-01-01T10:00:00Z'),
                       dict(coverage_start_utc='2026-01-01T10:00:00Z', coverage_end_utc='bad'),
                       dict(coverage_start_utc='2026-01-01T10:00:00Z', coverage_end_utc='2026-01-01T09:00:00Z')):
            with self.assertRaises(ValueError):
                d.detect_gap_findings(self.case, self.run, self.observations,
                                     [self.first | bounds, self.second])
        for amount in ('NaN', 'Infinity', '1e1000000000', 'bad'):
            self.transaction(amount, 30)
            with self.assertRaises(ValueError):
                self.anomalies()
            self.observations[:] = [o for o in self.observations if not o['source_locator'].startswith('row 30,')]

    def test_cluster_rejects_foreign_and_unsupported_edge_sources(self):
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, [])
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        for edge in (replace(edges[0], case_id=uid()), replace(edges[0], evidence_ids=(uid(),)),
                     replace(edges[0], evidence_ids=(self.first['id'],))):
            with self.assertRaises(ValueError):
                d.detect_cluster_findings(self.case, self.run, nodes, [edge])

    def test_anomaly_preserves_large_decimal_threshold_and_does_not_use_confidence(self):
        # The last value exceeds 10x the exact peer median by one unit, even
        # beyond Decimal's default precision. It must remain an outlier.
        base = '100000000000000000000000000000'
        for row, amount in enumerate((base, base, base, base, str(int(base) * 10 + 1)), 30):
            self.transaction(amount, row)
        findings = self.anomalies()
        self.assertEqual(len(findings), 1)
        for source in self.observations:
            source['extraction_confidence'] = 1.
        self.assertEqual(self.anomalies(), findings)


class FullAnalysisTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the real HTTP/SQLite/Neo4j-double harness without duplicating its tests.
    asyncSetUp = analysis_tests.AnalysisTests.asyncSetUp
    start = analysis_tests.AnalysisTests.start
    poll = analysis_tests.AnalysisTests.poll
    process = analysis_tests.AnalysisTests.process

    async def test_process_analysis_run_full_findings_triage_and_frozen_replay(self):
        evidence = []
        for name, rows in (('gps-a.csv', '2026-01-01T00:00:00Z,D-7,12,77\n2026-01-01T04:00:00Z,D-7,12,77\n'),
                           ('gps-b.csv', '2026-01-01T00:00:00Z,D-7,13,77\n')):
            response = await self.client.post(self.base + '/evidence', data={'kind': 'gps', 'source_label': name},
                files={'file': (name, ('timestamp,device_id,latitude,longitude\n' + rows).encode(), 'text/csv')})
            self.assertEqual(response.status_code, 201, response.text)
            evidence.append(response.json())
            await self.process(evidence[-1]['id'])
        response = await self.client.post(self.base + '/evidence', data={'kind': 'gps', 'source_label': 'unprocessed'},
            files={'file': ('unprocessed.csv', b'timestamp,device_id,latitude,longitude\n', 'text/csv')})
        unprocessed = response.json()['id']
        with unittest.mock.patch.object(analysis, 'run_analysis_job'):
            accepted = await self.start()
        analysis.process_analysis_run(self.app, accepted['id'])
        completed = await self.poll(accepted)
        self.assertEqual(completed['status'], 'completed', completed)
        self.assertIn(d.DETECTOR_VERSION, completed['algorithm_version'])
        with self.app.state.database.connect() as connection:
            output = dict(connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (accepted['id'],)).fetchone())
            run = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (accepted['id'],)).fetchone()
            graph, findings, triage = analysis._outputs(connection, run)
        self.assertEqual(json.loads(output['graph_json']), graph)
        self.assertEqual(json.loads(output['findings_json']), findings)
        self.assertEqual(json.loads(output['triage_json']), triage)
        self.assertEqual({finding['kind'] for finding in findings},
                         {'relationship', 'corroboration', 'conflict', 'gap', 'cluster', 'anomaly', 'hypothesis'})
        for finding in findings:
            validator('Finding').validate(finding)
            self.assertEqual(finding['analysis_run_id'], accepted['id'])
            self.assertTrue(set(finding['observation_ids']) <= set(completed['input_snapshot']['observation_ids']))
        self.assertEqual({r['evidence_id'] for r in triage}, {e['id'] for e in evidence})
        self.assertNotIn(unprocessed, {r['evidence_id'] for r in triage})
        for result in triage:
            validator('TriageResult').validate(result)
            self.assertEqual({factor['name'] for factor in result['factors']},
                             {'relevance', 'connectivity', 'temporal_proximity'})
            self.assertAlmostEqual(sum(factor['weight'] for factor in result['factors']), 1.)
        analysis.process_analysis_run(self.app, accepted['id'])
        with self.app.state.database.connect() as connection:
            self.assertEqual(dict(connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?',
                                                    (accepted['id'],)).fetchone()), output)
