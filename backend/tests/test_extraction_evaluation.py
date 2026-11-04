"""I04 independent gold labels against real committed synthetic producers.

No NER/parser/link doubles. CSV fixtures stay byte-for-byte unchanged. Mobile
and transaction SOURCE literals live in the existing committed parser tests.
"""
from dataclasses import FrozenInstanceError
from itertools import product
import json
import math
from pathlib import Path
import unittest
from uuid import uuid4

from backend.evaluation import calculate_metrics, metrics_from_counts
from backend.graph_links import derive_candidate_links
from backend.parsers.candidate_entities import project_candidate_entities
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.message_entities import project_message_entities
from backend.parsers.messages_csv import parse_messages_csv
from backend.parsers.mobile_csv import parse_mobile_csv
from backend.parsers.mobile_events import project_mobile_records
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.normalization import normalize_observations
from backend.parsers.source_events import project_source_events
from backend.parsers.text_document import parse_text_document
from backend.parsers.text_entities import project_text_entities
from backend.parsers.transaction_events import project_transaction_records
from backend.parsers.transactions_csv import parse_transactions_csv
from backend.tests.test_documents import SOURCE as DOCUMENT_SOURCE
from backend.tests.test_mobile import SOURCE as MOBILE_SOURCE
from backend.tests.test_transactions import SOURCE as TRANSACTION_SOURCE
from backend.text_ner import LocalWorker

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures'

# Source-specific candidates, not generated UUIDs. Gold labels are independent
# of actual parser/model output, including IPv6 normalization and negative prose.
ENTITY_GOLD = {
    'network.csv': ('device:D-7', 'device:D-9', 'ip:203.0.113.7', 'ip:203.0.113.9'),
    'gps.csv': ('device:D-8',),
    'messages.csv': ('device:D-7', 'device:D-8'),
    'mobile': ('device:D-007', 'device:D-8'),
    'transactions': ('account:AC-007', 'account:AC-8'),
    'names': ('person:Alice Smith', 'location:Paris', 'date:January 12, 2026'),
    'organization': ('person:Nora Reed', 'organization:Microsoft', 'location:London'),
    'identifiers': ('device:D-7', 'device:D-007', 'account:AC-007',
                    'phone:+15550101234', 'ip:192.0.2.1'),
    'ipv6': ('ip:2001:db8::1',),
    'near-misses': (), 'ambiguity': (), 'lowercase': ('person:quinn sample',), 'plain': (),
}


def link_label(kind, first, second):
    return kind, tuple(sorted((first, second)))


BASE_LINK_GOLD = (
    link_label('shared_identifier', ('network.csv', 'device:D-7'), ('messages.csv', 'device:D-7')),
    link_label('shared_identifier', ('gps.csv', 'device:D-8'), ('messages.csv', 'device:D-8')),
    link_label('co_mention', ('messages.csv', 'device:D-7'), ('messages.csv', 'device:D-8')),
)
ALL_LINK_GOLD = BASE_LINK_GOLD + (
    link_label('shared_identifier', ('network.csv', 'device:D-7'), ('identifiers', 'device:D-7')),
    link_label('shared_identifier', ('messages.csv', 'device:D-7'), ('identifiers', 'device:D-7')),
    link_label('shared_identifier', ('gps.csv', 'device:D-8'), ('mobile', 'device:D-8')),
    link_label('shared_identifier', ('messages.csv', 'device:D-8'), ('mobile', 'device:D-8')),
    link_label('shared_identifier', ('mobile', 'device:D-007'), ('identifiers', 'device:D-007')),
    link_label('shared_identifier', ('transactions', 'account:AC-007'), ('identifiers', 'account:AC-007')),
)


class MetricTests(unittest.TestCase):
    def test_known_nonperfect_arithmetic_and_harmonic_mean(self):
        result = calculate_metrics(['a', 'b', 'extra'], ['a', 'b', 'miss', 'miss2'])
        self.assertEqual((result.true_positives, result.false_positives, result.false_negatives), (2, 1, 2))
        self.assertAlmostEqual(result.precision, 2 / 3)
        self.assertEqual(result.recall, .5)
        self.assertAlmostEqual(result.f1, 4 / 7)
        self.assertAlmostEqual(result.f1, 2 * result.precision * result.recall / (result.precision + result.recall))

    def test_empty_one_sided_disjoint_and_perfect(self):
        for predicted, expected, counts in (
            ([], [], (0, 0, 0)), (['a'], [], (0, 1, 0)),
            ([], ['a'], (0, 0, 1)), (['a'], ['b'], (0, 1, 1)),
        ):
            with self.subTest(predicted=predicted, expected=expected):
                self.assertEqual(calculate_metrics(predicted, expected), metrics_from_counts(*counts))
                result = calculate_metrics(predicted, expected)
                self.assertEqual((result.precision, result.recall, result.f1), (0., 0., 0.))
        perfect = calculate_metrics(['a'], ['a'])
        self.assertEqual((perfect.precision, perfect.recall, perfect.f1), (1., 1., 1.))

    def test_duplicate_predictions_and_gold_are_matched_once(self):
        self.assertEqual(calculate_metrics(['a', 'a'], ['a']), metrics_from_counts(1, 1, 0))
        self.assertEqual(calculate_metrics(['a'], ['a', 'a']), metrics_from_counts(1, 0, 1))
        self.assertEqual(calculate_metrics(['a', 'a'], ['a', 'a']), metrics_from_counts(2, 0, 0))

    def test_bounds_over_count_grid(self):
        for counts in product(range(5), repeat=3):
            result = metrics_from_counts(*counts)
            for value in (result.precision, result.recall, result.f1):
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0.)
                self.assertLessEqual(value, 1.)

    def test_invalid_counts_fail(self):
        for value in (-1, 1.5, True, '1', None, float('nan'), float('inf')):
            for index in range(3):
                counts = [1, 1, 1]
                counts[index] = value
                with self.subTest(value=value, index=index), self.assertRaises(ValueError):
                    metrics_from_counts(*counts)

    def test_generators_order_immutability_and_exact_source_labels(self):
        predicted = [('source1', 'device:D-7'), ('source2', 'device:D-007')]
        expected = [('source2', 'device:D-7'), ('source1', 'device:D-7')]
        before = predicted.copy(), expected.copy()
        result = calculate_metrics(iter(reversed(predicted)), iter(expected))
        self.assertEqual(result, metrics_from_counts(1, 1, 1))
        self.assertEqual((predicted, expected), before)
        with self.assertRaises(FrozenInstanceError):
            result.f1 = 0

    def test_micro_aggregation_uses_counts(self):
        first = metrics_from_counts(1, 0, 0)
        second = metrics_from_counts(1, 8, 2)
        micro = metrics_from_counts(
            first.true_positives + second.true_positives,
            first.false_positives + second.false_positives,
            first.false_negatives + second.false_negatives,
        )
        self.assertEqual(micro.precision, .2)
        self.assertEqual(micro.recall, .5)


class FixtureEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = uuid4()
        cls.entities, cls.observations, cls.events = [], [], []
        cls.source_names = {}

        def context(name):
            evidence = uuid4()
            cls.source_names[str(evidence)] = name
            return dict(case_id=cls.case, evidence_id=evidence, processing_run_id=uuid4())

        def collect(projection, events=()):
            cls.entities.extend(item.to_wire() for item in projection.entities)
            cls.observations.extend(item.observation.to_wire() for item in projection.observations)
            cls.events.extend(item.event.to_wire() for item in events)

        for name, parser in (('network.csv', parse_network_csv), ('gps.csv', parse_gps_csv)):
            rows = parser((FIXTURES / 'synthetic-case' / name).read_bytes(), **context(name))
            projection = project_candidate_entities(normalize_observations(rows), case_id=cls.case)
            collect(projection, project_source_events(projection, case_id=cls.case))
        rows = parse_messages_csv((FIXTURES / 'synthetic-case/messages.csv').read_bytes(), **context('messages.csv'))
        collect(project_message_entities(rows, case_id=cls.case))
        for name, source, parser, projector in (
            ('mobile', MOBILE_SOURCE, parse_mobile_csv, project_mobile_records),
            ('transactions', TRANSACTION_SOURCE, parse_transactions_csv, project_transaction_records),
        ):
            projection = projector(parser(source, **context(name)), case_id=cls.case)
            collect(projection, projection.events)

        cls.text_cases = json.loads((FIXTURES / 'text-entities/labeled.json').read_text(encoding='utf-8'))
        worker = LocalWorker()
        try:
            cls.mentions = worker.request([item['text'] for item in cls.text_cases])
        finally:
            worker.close()
        for index, item in enumerate(cls.text_cases):
            lines = parse_text_document(item['text'].encode(), **context(item['id']))
            mentions = [dict(mention, line=0) for mention in cls.mentions if mention['line'] == index]
            collect(project_text_entities(lines, mentions, case_id=cls.case))

        cls.by_entity = {item['id']: item for item in cls.entities}
        cls.by_observation = {item['id']: item for item in cls.observations}

    def entity_label(self, entity):
        self.assertEqual(entity['case_id'], str(self.case))
        self.assertEqual(len(entity['evidence_ids']), 1)
        return self.source_names[entity['evidence_ids'][0]], entity['candidate_key']

    def assert_quality(self, result):
        self.assertGreaterEqual(result.precision, .80)
        self.assertGreaterEqual(result.recall, .80)
        for value in (result.precision, result.recall, result.f1):
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, 0.)
            self.assertLessEqual(value, 1.)

    def test_committed_candidate_entities_meet_gate(self):
        predicted = [self.entity_label(entity) for entity in self.entities]
        expected = [(source, key) for source, keys in ENTITY_GOLD.items() for key in keys]
        result = calculate_metrics(predicted, expected)
        self.assert_quality(result)
        self.assertEqual(result, metrics_from_counts(23, 2, 1))
        for source in ('network.csv', 'gps.csv', 'messages.csv', 'mobile', 'transactions'):
            with self.subTest(source=source):
                self.assert_quality(calculate_metrics(
                    [label for label in predicted if label[0] == source],
                    [label for label in expected if label[0] == source],
                ))
        print('I04_ENTITIES ' + repr(result))

    def test_real_ner_exact_mentions_meet_gate_and_report_errors(self):
        predicted = [(m['line'], m['start'], m['end'], m['kind']) for m in self.mentions]
        expected = [(i, m['start'], m['end'], m['kind'])
                    for i, item in enumerate(self.text_cases) for m in item['mentions']]
        result = calculate_metrics(predicted, expected)
        self.assert_quality(result)
        self.assertEqual(result, metrics_from_counts(13, 2, 1))
        def describe(labels):
            return sorted((self.text_cases[i]['id'], self.text_cases[i]['text'][start:end], kind)
                          for i, start, end, kind in labels)
        self.assertEqual(describe(set(predicted) - set(expected)),
                         [('ambiguity', 'May', 'date'), ('near-misses', 'd-7', 'person')])
        self.assertEqual(describe(set(expected) - set(predicted)), [('lowercase', 'quinn sample', 'person')])
        print('I04_TEXT_SPANS ' + repr(result))

    def event_label(self, event):
        self.assertEqual(event['case_id'], str(self.case))
        sources = [self.by_observation[oid] for oid in event['observation_ids']]
        self.assertTrue(sources)
        self.assertEqual({source['evidence_id'] for source in sources}, set(event['evidence_ids']))
        rows = {source['source_locator'].split(', ')[0] for source in sources}
        self.assertEqual(len(rows), 1)
        return (self.source_names[event['evidence_ids'][0]], rows.pop(), event['kind'], event['summary'],
                event['observed_at_raw'], event.get('observed_at_utc'),
                tuple(sorted(self.by_entity[eid]['candidate_key'] for eid in event['entity_ids'])))

    def test_network_gps_mobile_transaction_event_labels_meet_gate(self):
        expected = [
            ('network.csv', 'row 2', 'network.activity', 'Network log reports: connected',
             '2026-01-12T10:01:00Z', '2026-01-12T10:01:00Z', ('device:D-7', 'ip:203.0.113.7')),
            ('network.csv', 'row 3', 'network.activity', 'Network log reports: connected',
             '2026-01-12T10:02:00Z', '2026-01-12T10:02:00Z', ('device:D-9', 'ip:203.0.113.9')),
            ('gps.csv', 'row 2', 'gps.location',
             'GPS record reports device D-8 at latitude 12.9716, longitude 77.5946',
             '2026-01-12T10:02:00Z', '2026-01-12T10:02:00Z', ('device:D-8',)),
            ('mobile', 'row 2', 'mobile.activity', 'Source mobile log reports: authentication.success',
             '2026-01-12T15:30:00.123456789+05:30', '2026-01-12T10:00:00.123456789Z', ('device:D-007',)),
            ('mobile', 'row 3', 'mobile.activity', 'Source mobile log reports: app.open',
             '2026-01-12T10:00:00', None, ('device:D-8',)),
            ('transactions', 'row 2', 'transaction.record',
             'Source transaction record reports: 000123456789012345678901234567890.1200 USD',
             '2026-01-12T15:30:00.123456789+05:30', '2026-01-12T10:00:00.123456789Z', ('account:AC-007',)),
            ('transactions', 'row 3', 'transaction.record', 'Source transaction record reports: -001.2300 EUR',
             '2026-01-12T10:00:00', None, ('account:AC-8',)),
        ]
        predicted = [self.event_label(event) for event in self.events]
        result = calculate_metrics(predicted, expected)
        self.assertEqual(result, metrics_from_counts(7, 0, 0))
        self.assert_quality(result)
        for kind in ('network.activity', 'gps.location', 'mobile.activity', 'transaction.record'):
            with self.subTest(kind=kind):
                self.assert_quality(calculate_metrics([x for x in predicted if x[2] == kind],
                                                     [x for x in expected if x[2] == kind]))
        # A duplicate, a missed row and altered event content must lower metrics.
        self.assertEqual(calculate_metrics(predicted + predicted[:1], expected), metrics_from_counts(7, 1, 0))
        self.assertEqual(calculate_metrics(predicted[1:], expected), metrics_from_counts(6, 0, 1))
        altered = [predicted[0][:3] + ('wrong summary',) + predicted[0][4:]] + predicted[1:]
        self.assertEqual(calculate_metrics(altered, expected), metrics_from_counts(6, 1, 1))
        print('I04_EVENTS ' + repr(result))

    def links(self, source_names):
        entities = [entity for entity in self.entities if self.entity_label(entity)[0] in source_names]
        evidence = {eid for entity in entities for eid in entity['evidence_ids']}
        observations = [source for source in self.observations if source['evidence_id'] in evidence]
        edges, findings = derive_candidate_links(str(self.case), str(uuid4()), entities, observations)
        labels = []
        for edge in edges:
            endpoints = [self.by_entity[edge.from_id], self.by_entity[edge.to_id]]
            self.assertEqual(edge.case_id, str(self.case))
            self.assertEqual(set(edge.evidence_ids), {eid for entity in endpoints for eid in entity['evidence_ids']})
            self.assertEqual(set(edge.observation_ids), {oid for entity in endpoints for oid in entity['observation_ids']})
            self.assertEqual(edge.confidence, 0.)
            labels.append(link_label(edge.kind, *(self.entity_label(entity) for entity in endpoints)))
        self.assertEqual(len(edges), len(findings))
        return labels

    def test_committed_d7_d8_links_and_d9_isolation(self):
        labels = self.links({'network.csv', 'gps.csv', 'messages.csv'})
        self.assertEqual(calculate_metrics(labels, BASE_LINK_GOLD), metrics_from_counts(3, 0, 0))
        self.assertEqual(set(labels), set(BASE_LINK_GOLD))
        self.assertFalse(any('device:D-9' == key for _, endpoints in labels for _, key in endpoints))
        self.assert_quality(calculate_metrics(labels, BASE_LINK_GOLD))

    def test_cross_source_links_include_text_mobile_and_transactions(self):
        labels = self.links(set(ENTITY_GOLD))
        result = calculate_metrics(labels, ALL_LINK_GOLD)
        self.assertEqual(result, metrics_from_counts(9, 0, 0))
        self.assert_quality(result)
        for kind in ('shared_identifier', 'co_mention'):
            self.assert_quality(calculate_metrics([x for x in labels if x[0] == kind],
                                                 [x for x in ALL_LINK_GOLD if x[0] == kind]))
        self.assertEqual(calculate_metrics(labels + labels[:1], ALL_LINK_GOLD), metrics_from_counts(9, 1, 0))
        print('I04_LINKS ' + repr(result))

    def test_network_gps_alone_are_negative_link_control(self):
        self.assertEqual(self.links({'network.csv', 'gps.csv'}), [])

    def test_foreign_case_cannot_enter_link_evaluation(self):
        entities = [dict(entity) for entity in self.entities]
        entities[0]['case_id'] = str(uuid4())
        with self.assertRaises(ValueError):
            derive_candidate_links(str(self.case), str(uuid4()), entities, self.observations)
        observations = [dict(source) for source in self.observations]
        observations[0]['case_id'] = str(uuid4())
        with self.assertRaises(ValueError):
            derive_candidate_links(str(self.case), str(uuid4()), self.entities, observations)

    def test_p07_committed_unicode_bom_and_duplicate_line_fixture(self):
        rows = parse_text_document(DOCUMENT_SOURCE, case_id=self.case, evidence_id=uuid4(), processing_run_id=uuid4())
        predicted = [(row.observation.source_locator, row.observation.raw_value) for row in rows]
        expected = [('line 1; chars=0:7', '😀 D-7  '), ('line 2; chars=9:9', ''),
                    ('line 3; chars=10:16', 'second'), ('line 4; chars=17:23', 'second')]
        self.assertEqual(calculate_metrics(predicted, expected), metrics_from_counts(4, 0, 0))

    def test_mobile_call_sms_source_reports_keep_generic_activity_kind(self):
        # Additional labeled controls: P11 preserves event text rather than
        # classifying calls/SMS or extracting an inferred correspondent.
        source = (b'timestamp,device_id,event,detail\n'
                  b'2026-01-12T10:00:00Z,D-7,call,Synthetic call report\n'
                  b'2026-01-12T10:01:00Z,D-8,sms,Synthetic SMS report\n')
        projection = project_mobile_records(parse_mobile_csv(source, case_id=self.case,
            evidence_id=uuid4(), processing_run_id=uuid4()), case_id=self.case)
        entities = {entity.id: entity.candidate_key for entity in projection.entities}
        predicted = [(item.event.kind, item.event.summary,
                      tuple(entities[eid] for eid in item.event.entity_ids)) for item in projection.events]
        expected = [('mobile.activity', 'Source mobile log reports: call', ('device:D-7',)),
                    ('mobile.activity', 'Source mobile log reports: sms', ('device:D-8',))]
        self.assertEqual(calculate_metrics(predicted, expected), metrics_from_counts(2, 0, 0))
        self.assert_quality(calculate_metrics(predicted, expected))
