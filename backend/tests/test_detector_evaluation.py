"""I05B exact detector evaluation over independent, synthetic source labels.

Real parsers, projections, detectors and factor calculators run without doubles.
Gold citations/membership come from selected input rows, never detector output.
Perfect scores here describe these fixtures, not population-level accuracy.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from uuid import UUID, uuid4

from backend import detectors as d
from backend.evaluation import (
    DETECTOR_KINDS, detector_finding_label, evaluate_detector_findings, metrics_from_counts,
)
from backend.graph_links import Finding, derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend.parsers.candidate_entities import project_candidate_entities
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.normalization import normalize_observations
from backend.parsers.source_events import project_source_events
from backend.parsers.transaction_events import project_transaction_records
from backend.parsers.transactions_csv import parse_transactions_csv
from backend.triage.aggregation import aggregate_triage_result
from backend.triage.factors import calculate_conflict_relevance_factor, calculate_gap_relevance_factor


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'synthetic-case'


def label(kind, rule, evidence, observations=(), entities=(), opposition=()):
    """Author a gold group from source references, independently of predictions."""
    return (kind, rule, *(tuple(sorted(values)) for values in
                         (evidence, observations, entities, opposition)))


class DetectorMetricTests(unittest.TestCase):
    def prediction(self, kind='conflict', **changes):
        return dict(kind=kind, rule='test:v1', evidence_ids=['source-b', 'source-a'],
                    observation_ids=['row-b', 'row-a'], entity_ids=['candidate'],
                    contradicting_evidence_ids=['source-b'], id=str(uuid4()),
                    analysis_run_id=str(uuid4()), summary='Candidate report', confidence=0.) | changes

    def gold(self, kind='conflict', rule='test:v1'):
        return label(kind, rule, ('source-a', 'source-b'), ('row-a', 'row-b'),
                     ('candidate',), ('source-b',))

    def test_all_six_kinds_have_independent_nonperfect_metrics(self):
        predictions, expected = [], []
        for kind in DETECTOR_KINDS:
            predictions.extend([self.prediction(kind), self.prediction(kind),
                                self.prediction(kind, rule='unexpected:v1')])
            expected.extend([self.gold(kind), self.gold(kind), self.gold(kind, 'missed:v1'),
                             self.gold(kind, 'another-miss:v1')])
        results = evaluate_detector_findings(predictions, expected)
        self.assertEqual(tuple(results), DETECTOR_KINDS)
        for kind, result in results.items():
            with self.subTest(kind=kind):
                self.assertEqual(result, metrics_from_counts(2, 1, 2))
                self.assertAlmostEqual(result.precision, 2 / 3)
                self.assertEqual(result.recall, .5)
                self.assertAlmostEqual(result.f1, 4 / 7)

    def test_empty_inputs_report_zero_for_every_kind(self):
        self.assertEqual(evaluate_detector_findings([], []),
                         {kind: metrics_from_counts(0, 0, 0) for kind in DETECTOR_KINDS})

    def test_one_sided_and_wrong_kind_findings_track_fp_fn(self):
        for predictions, expected, counts in (
                ([self.prediction()], [], (0, 1, 0)),
                ([], [self.gold()], (0, 0, 1)),
                ([self.prediction(rule='other:v1')], [self.gold()], (0, 1, 1))):
            with self.subTest(counts=counts):
                self.assertEqual(evaluate_detector_findings(predictions, expected)['conflict'],
                                 metrics_from_counts(*counts))
        result = evaluate_detector_findings([self.prediction('gap')], [self.gold()])
        self.assertEqual(result['gap'], metrics_from_counts(0, 1, 0))
        self.assertEqual(result['conflict'], metrics_from_counts(0, 0, 1))

    def test_duplicate_predictions_and_gold_keep_multiplicity(self):
        for predictions, expected, counts in (
                ([self.prediction()] * 2, [self.gold()], (1, 1, 0)),
                ([self.prediction()], [self.gold()] * 2, (1, 0, 1)),
                ([self.prediction()] * 2, [self.gold()] * 2, (2, 0, 0))):
            with self.subTest(counts=counts):
                self.assertEqual(evaluate_detector_findings(predictions, expected)['conflict'],
                                 metrics_from_counts(*counts))

    def test_finding_and_wire_inputs_ignore_run_ids_prose_scores_and_private_assessments(self):
        finding = Finding(id=str(uuid4()), case_id=str(uuid4()), analysis_run_id=str(uuid4()),
            kind='conflict', rule='test:v1', summary='Candidate conflict',
            evidence_ids=('source-a', 'source-b'), observation_ids=('row-a', 'row-b'),
            entity_ids=('candidate',), contradicting_evidence_ids=('source-b',))
        revised = replace(finding, id=str(uuid4()), analysis_run_id=str(uuid4()),
                          summary='Reworded explanation', confidence=.9, conflict_strength=.8)
        self.assertEqual(detector_finding_label(finding), self.gold())
        self.assertEqual(detector_finding_label(revised.to_wire()), self.gold())
        self.assertEqual(evaluate_detector_findings([finding, revised.to_wire()], [self.gold()] * 2)
                         ['conflict'], metrics_from_counts(2, 0, 0))

    def test_generators_reference_order_and_input_immutability(self):
        prediction = self.prediction()
        expected = ('conflict', 'test:v1', ('source-b', 'source-a'), ('row-b', 'row-a'),
                    ('candidate',), ('source-b',))
        before = deepcopy(prediction)
        self.assertEqual(evaluate_detector_findings(iter([prediction]), iter([expected]))['conflict'],
                         metrics_from_counts(1, 0, 0))
        self.assertEqual(prediction, before)
        self.assertEqual(hash(detector_finding_label(prediction)), hash(self.gold()))

    def test_missing_optional_groups_are_empty(self):
        prediction = dict(kind='gap', rule='gap:v1', evidence_ids=['source-a'])
        self.assertEqual(evaluate_detector_findings([prediction], [label('gap', 'gap:v1', ['source-a'])])
                         ['gap'], metrics_from_counts(1, 0, 0))

    def test_citations_membership_opposition_and_rule_versions_are_exact(self):
        for changes in (dict(evidence_ids=['source-b']), dict(observation_ids=['wrong-row']),
                        dict(entity_ids=['other-candidate']),
                        dict(contradicting_evidence_ids=['source-a']), dict(rule='test:v2')):
            with self.subTest(changes=changes):
                self.assertEqual(evaluate_detector_findings([self.prediction(**changes)], [self.gold()])
                                 ['conflict'], metrics_from_counts(0, 1, 1))

    def test_invalid_predictions_and_labels_fail_instead_of_inflating_metrics(self):
        for prediction in (None, (), self.prediction(kind='relationship'), self.prediction(kind='unknown'),
                           self.prediction(rule=' '), self.prediction(evidence_ids=[]),
                           self.prediction(evidence_ids='source-a'),
                           self.prediction(observation_ids=['row-a', 'row-a']),
                           self.prediction(entity_ids=[None]),
                           self.prediction(contradicting_evidence_ids=['uncited'])):
            with self.subTest(prediction=prediction), self.assertRaises(ValueError):
                evaluate_detector_findings([prediction], [])
        for expected in ('opaque-id', (), ('conflict', 'test:v1', ('source-a',)),
                         ('unknown', *self.gold()[1:]), ('conflict', '', *self.gold()[2:]),
                         ('conflict', 'test:v1', (), (), (), ()),
                         ('conflict', 'test:v1', ('source-a',), (), (), ('uncited',))):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                evaluate_detector_findings([], [expected])


class DetectorFixtureTests(unittest.TestCase):
    def setUp(self):
        self.case, self.run = str(uuid4()), str(uuid4())
        self.evidence, self.observations, self.entities, self.events = [], [], [], []
        self.sources = {}

    def add_source(self, name, family, rows):
        eid = str(uuid4())
        self.sources[name] = eid
        self.evidence.append(dict(id=eid, case_id=self.case, filename=name))
        context = dict(case_id=UUID(self.case), evidence_id=UUID(eid), processing_run_id=uuid4())
        headers = {'gps': 'timestamp,device_id,latitude,longitude\n',
                   'network': 'timestamp,device_id,ip_address,event\n',
                   'transactions': 'timestamp,account_id,amount,currency\n'}
        source = (headers[family] + rows).encode()
        if family == 'transactions':
            projection = project_transaction_records(parse_transactions_csv(source, **context),
                                                       case_id=UUID(self.case))
            events = projection.events
        else:
            parser = parse_gps_csv if family == 'gps' else parse_network_csv
            projection = project_candidate_entities(normalize_observations(parser(source, **context)),
                                                    case_id=UUID(self.case))
            events = project_source_events(projection, case_id=UUID(self.case))
        self.observations.extend(item.observation.to_wire() for item in projection.observations)
        self.entities.extend(item.to_wire() for item in projection.entities)
        self.events.extend(item.event.to_wire() for item in events)
        return eid

    def gold(self, kind, rule, source_rows, *, keys=(), opposition=(), kinds=()):
        """Select independent gold citations by source name and CSV row numbers."""
        eids = [self.sources[name] for name in source_rows]
        oids = [source['id'] for source in self.observations
                for name, rows in source_rows.items()
                if source['evidence_id'] == self.sources[name] and
                (not kinds or source['kind'] in kinds) and
                (rows is None or source['source_locator'].split(',')[0] in
                 {f'row {row}' for row in rows})]
        entities = [entity['id'] for entity in self.entities
                    if entity['candidate_key'] in keys and set(entity['evidence_ids']) <= set(eids)]
        return label(kind, rule, eids, oids, entities, [self.sources[name] for name in opposition])

    def conflicts(self, *, events=True, run=None):
        return d.detect_conflict_findings(self.case, run or self.run, self.observations,
                                          self.entities, self.events if events else [])

    def gaps(self):
        return d.detect_gap_findings(self.case, self.run, self.observations, self.evidence)

    def anomalies(self):
        return d.detect_anomaly_findings(self.case, self.run, self.observations, self.evidence)

    def assert_evaluation(self, predicted, expected, counts):
        results = evaluate_detector_findings(predicted, expected)
        for kind in DETECTOR_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(results[kind], metrics_from_counts(*counts.get(kind, (0, 0, 0))))
        return results

    def test_spatial_conflict_exact_utc_with_independent_citations(self):
        self.add_source('a', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n')
        self.add_source('b', 'gps', '2026-01-01T11:00:00+01:00,D-7,13,77\n')
        gold = self.gold('conflict', d.CONFLICT_LOCATION_RULE, {'a': (2,), 'b': (2,)},
                         keys=('device:D-7',), opposition=(max(self.sources, key=self.sources.get),))
        self.assert_evaluation(self.conflicts(), [gold], {'conflict': (1, 0, 0)})

    def test_spatial_nonconflict_controls(self):
        for second in ('2026-01-01T10:00:00Z,D-7,12.000,77.0\n',
                       '2026-01-01T10:01:00Z,D-7,13,77\n',
                       '2026-01-01T10:00:00Z,D-8,13,77\n'):
            with self.subTest(second=second):
                self.setUp()
                self.add_source('a', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n')
                self.add_source('b', 'gps', second)
                self.assert_evaluation(self.conflicts(events=False), [], {})

    def test_temporal_conflict_and_nonconflict_controls(self):
        for second, positive in (
                ('2026-01-01T11:00:00Z,D-7,203.0.113.7,unique-login\n', True),
                ('2026-01-01T11:00:00+01:00,D-7,203.0.113.7,unique-login\n', False),
                ('2026-01-01T11:00:00Z,D-7,203.0.113.7,different-event\n', False),
                ('2026-01-01T11:00:00Z,D-8,203.0.113.7,unique-login\n', False)):
            with self.subTest(second=second):
                self.setUp()
                self.add_source('a', 'network', '2026-01-01T10:00:00Z,D-7,203.0.113.7,unique-login\n')
                self.add_source('b', 'network', second)
                gold = [self.gold('conflict', d.CONFLICT_TIME_RULE, {'a': (2,), 'b': (2,)},
                        keys=('device:D-7', 'ip:203.0.113.7'),
                        opposition=(max(self.sources, key=self.sources.get),))] if positive else []
                self.assert_evaluation(self.conflicts(), gold, {'conflict': (1, 0, 0)} if positive else {})

    def test_gap_unobserved_interval_and_contiguous_coverage_control(self):
        self.add_source('sequence', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n'
                        '2026-01-01T10:30:00Z,D-7,12,77\n2026-01-01T13:00:00Z,D-7,12,77\n')
        gold = self.gold('gap', d.GAP_RULE, {'sequence': (3, 4)}, kinds=('gps.device',))
        self.assert_evaluation(self.gaps(), [gold], {'gap': (1, 0, 0)})
        self.setUp()
        self.add_source('contiguous', 'gps', ''.join(
            f'2026-01-01T{hour:02}:00:00Z,D-7,12,77\n' for hour in range(10, 14)))
        self.assert_evaluation(self.gaps(), [], {})

    def test_gap_intervals_in_same_evidence_are_not_interchangeable(self):
        self.add_source('sequence', 'gps', ''.join(
            f'2026-01-01T{hour:02}:00:00Z,D-7,12,77\n' for hour in (10, 12, 14)))
        expected = [self.gold('gap', d.GAP_RULE, {'sequence': rows}, kinds=('gps.device',))
                    for rows in ((2, 3), (3, 4))]
        predicted = self.gaps()
        self.assert_evaluation(predicted, expected, {'gap': (2, 0, 0)})
        self.assert_evaluation([predicted[0]] * 2, expected, {'gap': (1, 1, 1)})

    def test_anomaly_amount_outlier_and_normal_baseline(self):
        for amounts, positive in ((('9', '10', '10', '11', '-1000'), True),
                                   (('9', '10', '10', '11', '12'), False)):
            with self.subTest(amounts=amounts):
                self.setUp()
                self.add_source('payments', 'transactions', ''.join(
                    f'2026-01-01T12:00:00Z,AC-1,{value},USD\n' for value in amounts))
                expected = [self.gold('anomaly', d.ANOMALY_AMOUNT_RULE, {'payments': None})] if positive else []
                self.assert_evaluation(self.anomalies(), expected, {'anomaly': (1, 0, 0)} if positive else {})

    def test_anomaly_utc_hours_boundaries_offsets_and_unknown_local_time(self):
        for timestamp, positive in (('2026-01-01T05:59:59Z', True),
                                    ('2026-01-01T06:00:00Z', False),
                                    ('2026-01-01T21:59:59Z', False),
                                    ('2026-01-01T22:00:00Z', True),
                                    ('2026-01-01T03:00:00-07:00', False),
                                    ('2026-01-01T02:00:00', False)):
            with self.subTest(timestamp=timestamp):
                self.setUp()
                self.add_source('log', 'gps', f'{timestamp},D-7,12,77\n')
                expected = [self.gold('anomaly', d.ANOMALY_HOURS_RULE, {'log': (2,)})] if positive else []
                self.assert_evaluation(self.anomalies(), expected, {'anomaly': (1, 0, 0)} if positive else {})

    def test_cluster_components_membership_and_isolated_node(self):
        for name in ('a', 'b', 'c'):
            self.add_source(name, 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n'
                            '2026-01-01T10:30:00Z,D-8,12,77\n')
        self.add_source('isolated', 'gps', '2026-01-01T10:00:00Z,D-9,12,77\n')
        nodes = build_graph_nodes(self.case, self.evidence, self.entities, [])
        edges, _ = derive_candidate_links(self.case, self.run, self.entities, self.observations)
        # Keep a spanning path through each three-node component, so traversal
        # must find transitive connectivity rather than just pairwise groups.
        a, c = self.sources['a'], self.sources['c']
        edges = [edge for edge in edges if set(edge.evidence_ids) != {a, c}]
        expected = [self.gold('cluster', d.CLUSTER_RULE,
                    {name: (row,) for name in ('a', 'b', 'c')}, keys=(key,), kinds=('gps.device',))
                    for row, key in ((2, 'device:D-7'), (3, 'device:D-8'))]
        predicted = d.detect_cluster_findings(self.case, self.run, nodes, edges)
        self.assert_evaluation(predicted, expected, {'cluster': (2, 0, 0)})
        reversed_edges = [replace(edge, from_id=edge.to_id, to_id=edge.from_id) for edge in edges]
        self.assert_evaluation(d.detect_cluster_findings(self.case, self.run, reversed(nodes), reversed_edges),
                               expected, {'cluster': (2, 0, 0)})
        self.assert_evaluation([predicted[0]] * 2, expected, {'cluster': (1, 1, 1)})
        self.assert_evaluation(d.detect_cluster_findings(self.case, self.run, nodes, []), [], {})

    def test_corroboration_repeated_claims_and_single_source_control(self):
        for name in ('a', 'b'):
            self.add_source(name, 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n')
        # Entities alone represent one repeated exact identifier claim; event
        # corroboration is evaluated separately by detector policy tests.
        predicted = d.detect_corroboration_findings(self.case, self.run, self.observations,
                                                    self.entities, [], self.evidence)
        device_oids = [o['id'] for o in self.observations if o['kind'] == 'gps.device']
        expected = label('corroboration', d.CORROBORATION_RULE, self.sources.values(), device_oids,
                         [e['id'] for e in self.entities])
        self.assert_evaluation(predicted, [expected], {'corroboration': (1, 0, 0)})
        predicted = d.detect_corroboration_findings(self.case, self.run, self.observations,
                                                    self.entities[:1], [], self.evidence)
        self.assert_evaluation(predicted, [], {})

    def test_hypothesis_opposing_sides_and_analysis_run_replay(self):
        self.add_source('a', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n')
        self.add_source('b', 'gps', '2026-01-01T10:00:00Z,D-7,13,77\n')
        expected = [self.gold('hypothesis', d.HYPOTHESIS_RULE, {'a': (2,), 'b': (2,)},
                              keys=('device:D-7',), opposition=(side,)) for side in ('a', 'b')]
        conflicts = self.conflicts()
        predicted = d.detect_hypothesis_findings(self.case, self.run, self.observations, conflicts)
        self.assert_evaluation(predicted, expected, {'hypothesis': (2, 0, 0)})
        self.assert_evaluation([predicted[0]] * 2, expected, {'hypothesis': (1, 1, 1)})
        rerun = str(uuid4())
        replayed = d.detect_hypothesis_findings(self.case, rerun, self.observations, self.conflicts(run=rerun))
        self.assertTrue(set(f.id for f in predicted).isdisjoint(f.id for f in replayed))
        self.assertNotEqual({f.summary for f in predicted}, {f.summary for f in replayed})
        self.assert_evaluation(replayed, expected, {'hypothesis': (2, 0, 0)})

    def test_committed_gps_and_network_fixtures_are_negative_controls(self):
        for name, family in (('gps.csv', 'gps'), ('network.csv', 'network')):
            source = (FIXTURES / name).read_text(encoding='utf-8')
            self.add_source(name, family, source.split('\n', 1)[1])
        self.assert_evaluation(self.conflicts() + self.gaps() + self.anomalies(), [], {})

    def test_real_detector_mutations_report_false_positives_and_false_negatives(self):
        self.add_source('a', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n')
        self.add_source('b', 'gps', '2026-01-01T10:00:00Z,D-7,13,77\n')
        expected = [self.gold('conflict', d.CONFLICT_LOCATION_RULE, {'a': (2,), 'b': (2,)},
                    keys=('device:D-7',), opposition=(max(self.sources, key=self.sources.get),))]
        predicted = self.conflicts()
        self.assert_evaluation(predicted * 2, expected, {'conflict': (1, 1, 0)})
        self.assert_evaluation([], expected, {'conflict': (0, 0, 1)})
        self.assert_evaluation([replace(predicted[0], rule='wrong-rule:v1')], expected,
                               {'conflict': (0, 1, 1)})

    def test_detector_feedback_requires_assessments_and_populates_triage_factors(self):
        eid = self.add_source('a', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n'
                              '2026-01-01T14:00:00Z,D-7,12,77\n')
        self.add_source('b', 'gps', '2026-01-01T10:00:00Z,D-7,13,77\n')
        conflicts, gaps = self.conflicts(events=False), self.gaps()
        before = deepcopy((conflicts, gaps))
        # I07 supplies a bounded detector strength. An explicitly unassessed
        # candidate remains absent; wire findings also omit private strengths.
        self.assertIsNone(calculate_conflict_relevance_factor(
            case_id=self.case, evidence_id=eid,
            conflict_findings=[replace(finding, conflict_strength=None) for finding in conflicts]))
        self.assertIsNone(calculate_gap_relevance_factor(
            case_id=self.case, evidence_id=eid, gap_findings=gaps))
        conflict_factor = calculate_conflict_relevance_factor(
            case_id=self.case, evidence_id=eid, conflict_findings=conflicts)
        self.assertEqual(conflict_factor['name'], 'conflict_relevance')
        self.assertEqual(conflict_factor['value'], .8)
        self.assertEqual(conflict_factor['contribution'], 8.)
        self.assertEqual(set(conflict_factor['evidence_ids']), set(self.sources.values()))

        coverage = self.add_source('coverage', 'network',
            '2026-01-01T12:00:00Z,D-9,203.0.113.9,coverage-marker\n')
        self.evidence[-1].update(coverage_start_utc='2026-01-01T11:00:00Z',
                                 coverage_end_utc='2026-01-01T13:00:00Z')
        covered_gaps = self.gaps()
        gap_factor = calculate_gap_relevance_factor(
            case_id=self.case, evidence_id=coverage, gap_findings=covered_gaps)
        self.assertEqual(gap_factor['name'], 'gap_relevance')
        self.assertEqual(gap_factor['value'], .5)
        self.assertEqual(gap_factor['contribution'], 7.5)
        self.assertEqual(set(gap_factor['evidence_ids']), set(self.sources.values()))
        self.assertIsNone(calculate_gap_relevance_factor(
            case_id=self.case, evidence_id=coverage, gap_findings=[f.to_wire() for f in covered_gaps]))
        for target, factor in ((eid, conflict_factor), (coverage, gap_factor)):
            result = aggregate_triage_result(case_id=self.case, analysis_run_id=self.run,
                evidence_id=target, observation_count=3, factors=[factor],
                case_evidence_ids=self.sources.values(), created_at='2026-01-01T15:00:00Z')
            self.assertEqual(result['factors'][0]['name'], factor['name'])
            self.assertEqual(result['factors'][0]['value'], factor['value'])
            self.assertEqual(result['score'], factor['value'] * 100)
        self.assertEqual((conflicts, gaps), before)

    def test_evaluated_negative_feedback_produces_zero_while_unknown_is_absent(self):
        eid = self.add_source('normal', 'gps', '2026-01-01T10:00:00Z,D-7,12,77\n'
                              '2026-01-01T11:00:00Z,D-7,12,77\n')
        for calculator, argument, findings in (
                (calculate_conflict_relevance_factor, 'conflict_findings', self.conflicts()),
                (calculate_gap_relevance_factor, 'gap_findings', self.gaps())):
            with self.subTest(argument=argument):
                factor = calculator(case_id=self.case, evidence_id=eid, **{argument: findings})
                self.assertEqual(factor['value'], 0.)
                self.assertEqual(factor['contribution'], 0.)
                self.assertIsNone(calculator(case_id=self.case, evidence_id=eid, **{argument: None}))


if __name__ == '__main__':
    unittest.main()
