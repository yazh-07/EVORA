"""A04 synthetic policy negatives and real network/GPS producer acceptance."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import re
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_links import derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend.tests.test_graph_nodes import BAD_UUIDS, validator
from backend.triage.aggregation import aggregate_triage_result, sort_triage_results
from backend.triage.factors import calculate_connectivity_factor, calculate_relevance_factor
from backend.triage.goldens import ROUNDING_CAP_CONTROL, TIE_BREAKING_CONTROL
from backend.triage.policy import BASE_WEIGHTS, FactorValue, POLICY_VERSION

ROOT = Path(__file__).resolve().parents[2]
CASE, RUN = str(uuid4()), str(uuid4())
IDS = tuple(f'eeeeeeee-0000-4000-8000-{i:012d}' for i in range(1, 7))
TIME = '2026-11-03T12:00:00Z'


def result_validator():
    schema = validator('TriageResult')
    # jsonschema's optional RFC3339 dependency is absent in the pinned baseline.
    # Explicitly check generated UTC date-times rather than silently skipping.
    @schema.format_checker.checks('date-time', raises=ValueError)
    def utc_datetime(value):
        if not isinstance(value, str):
            return True  # JSON Schema type validation owns non-string values.
        return (re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z', value) is not None
                and datetime.fromisoformat(value).utcoffset().total_seconds() == 0)
    return schema


def factor(name='relevance', value=.8, sources=(IDS[0],)):
    return dict(name=name, value=value, weight=BASE_WEIGHTS[name],
                contribution=round(value * BASE_WEIGHTS[name] * 100, 2),
                explanation='Synthetic supported observation, not verified identity.',
                evidence_ids=list(sources))


class AggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = result_validator()
        cls.entry_schema = validator('TriageEntry')

    def aggregate(self, **changes):
        kwargs = dict(case_id=CASE, analysis_run_id=RUN, evidence_id=IDS[0],
                      observation_count=1, factors=[factor(), factor('connectivity', .1)],
                      case_evidence_ids=IDS, created_at=TIME)
        result = aggregate_triage_result(**(kwargs | changes))
        if result is not None:
            self.schema.validate(result)
        return result

    def test_raw_producer_values_renormalized_without_mutation(self):
        factors = [factor(), factor('connectivity', .1)]
        before = deepcopy(factors)
        result = self.aggregate(factors=iter(reversed(factors)))
        self.assertEqual(result['score'], 48.88)
        self.assertEqual(result['priority'], 'P3')
        self.assertEqual([f['name'] for f in result['factors']], ['relevance', 'connectivity'])
        self.assertEqual([f['contribution'] for f in result['factors']], [44.44, 4.44])
        self.assertAlmostEqual(sum(f['weight'] for f in result['factors']), 1)
        self.assertAlmostEqual(result['factors'][0]['weight'], 5 / 9)
        self.assertAlmostEqual(result['factors'][1]['weight'], 4 / 9)
        for text in (POLICY_VERSION, '48.88', 'relevance', 'connectivity', 'not truth'):
            self.assertIn(text, result['explanation'])
        self.assertEqual(factors, before)
        result['factors'][0]['evidence_ids'].clear()
        self.assertEqual(factors, before)

    def test_bands_rounding_and_evaluated_zero(self):
        for value, score, band in ((1, 100., 'P1'), (.8, 80., 'P1'),
                (.7999, 79.99, 'P2'), (.6, 60., 'P2'), (.5999, 59.99, 'P3'),
                (.4, 40., 'P3'), (.3999, 39.99, 'P4'), (0, 0., 'P4'),
                (.79996, 80., 'P1'), (1 / 3, 33.33, 'P4')):
            with self.subTest(value=value):
                result = self.aggregate(factors=[factor(value=value)])
                self.assertEqual((result['score'], result['priority']), (score, band))
                self.assertIsInstance(result['score'], float)
                self.assertEqual(result['factors'][0]['weight'], 1.)
        result = self.aggregate(factors=[factor(value=1), factor('connectivity', 0)])
        self.assertEqual(result['score'], 55.56)
        self.assertEqual(len(result['factors']), 2)

    def test_explicit_other_factors_and_100_01_cap(self):
        result = self.aggregate(factors=[factor(name, value)
            for name, value in ROUNDING_CAP_CONTROL['factor_values'].items()])
        self.assertEqual(result['score'], 100.)
        self.assertEqual(tuple(f['contribution'] for f in result['factors']), (42.86, 42.86, 14.29))
        self.assertIn('100.01 capped at 100.00', result['explanation'])

    def test_missing_is_unscored_and_named_factorvalue_handoff(self):
        for factors in ([], {}, {'source_quality': None}):
            self.assertIsNone(self.aggregate(factors=factors))
        self.assertIsNone(self.aggregate(observation_count=0))
        self.assertIsNone(self.aggregate(observation_count=0, factors=[factor(value=0)]))
        result = self.aggregate(factors={'relevance': FactorValue(.8, 'Synthetic source', (IDS[0],)),
                                         'source_quality': None})
        self.assertEqual((result['score'], len(result['factors'])), (80., 1))
        self.assertEqual(result['factors'][0]['name'], 'relevance')

    def test_identity_time_and_determinism(self):
        result = self.aggregate()
        self.assertEqual(result, self.aggregate())
        self.assertEqual(UUID(result['id']).version, 5)
        for changes in ({'analysis_run_id': str(uuid4())}, {'case_id': str(uuid4())},
                        {'evidence_id': IDS[1]}):
            self.assertNotEqual(self.aggregate(**changes)['id'], result['id'])
        self.assertEqual(self.aggregate(created_at='2026-11-03T17:30:00+05:30')['created_at'], TIME)
        before = datetime.now(timezone.utc)
        generated = datetime.fromisoformat(self.aggregate(created_at=None)['created_at'])
        self.assertLessEqual(before, generated)
        self.assertLessEqual(generated, datetime.now(timezone.utc))

    def test_invalid_context_and_counts_even_when_unscored(self):
        for field in ('case_id', 'analysis_run_id', 'evidence_id'):
            for bad in BAD_UUIDS:
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    self.aggregate(**{field: bad, 'observation_count': 0})
        for count in (-1, True, 1., '1', None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.aggregate(observation_count=count)
        for timestamp in ('bad', '', '2026-11-03', '2026-11-03T12:00:00', 123):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.aggregate(created_at=timestamp)

    def test_foreign_sources_and_target_rejected_even_when_unscored(self):
        foreign = str(uuid4())
        for count in (0, 1):
            for changes in ({'evidence_id': foreign}, {'case_evidence_ids': [IDS[1]]},
                            {'factors': [factor(sources=(foreign,))]},
                            {'factors': {'relevance': FactorValue(.8, 'Synthetic', (foreign,))}}):
                with self.subTest(count=count, changes=changes), self.assertRaises(ValueError):
                    self.aggregate(observation_count=count, **changes)

    def test_invalid_factors_fail_closed_without_name_guessing(self):
        invalid = [[factor(), factor()], [FactorValue(.8, 'Synthetic', (IDS[0],))],
                   {'relevance': .8}, {'invented': None}, [dict(factor(), name='invented')]]
        for field, bad in (('value', -1), ('value', 1.1), ('value', float('nan')),
                           ('value', float('inf')), ('value', True), ('value', '0.8'),
                           ('explanation', ''), ('explanation', None),
                           ('evidence_ids', []), ('evidence_ids', [IDS[0]] * 2),
                           ('evidence_ids', [IDS[0].upper()]), ('extra', True)):
            invalid.append([dict(factor(), **{field: bad})])
        for field in ('name', 'value', 'explanation', 'evidence_ids'):
            broken = factor()
            del broken[field]
            invalid.append([broken])
        for factors in invalid:
            with self.subTest(factors=factors), self.assertRaises(ValueError):
                self.aggregate(factors=factors, observation_count=0)

    def test_canonical_sort_matches_g02_golden_and_includes_unscored(self):
        golden = TIE_BREAKING_CONTROL
        results = [self.aggregate(evidence_id=eid, case_evidence_ids=[e for e, _ in golden['input']],
                                 factors=[factor(value=score / 100, sources=(eid,))])
                   for eid, score in golden['input'] if score is not None]
        before = deepcopy(results)
        entries = sort_triage_results(results, iter(e for e, _ in golden['input']))
        self.assertEqual(tuple(e['evidence_id'] for e in entries), golden['expected_order'])
        for entry in entries:
            self.entry_schema.validate(entry)
        self.assertEqual(set(entries[-1]), {'evidence_id'})
        entries[0]['latest_result']['factors'].clear()
        self.assertEqual(results, before)
        self.assertEqual(sort_triage_results([], reversed(IDS)), [dict(evidence_id=e) for e in IDS])
        self.assertEqual(sort_triage_results([], []), [])

    def test_sort_rejects_duplicate_foreign_mixed_and_invalid_results(self):
        result = self.aggregate()
        for results in ([result, result], [dict(result, evidence_id=str(uuid4()))],
                [result, dict(result, evidence_id=IDS[1], analysis_run_id=str(uuid4()))],
                [result, dict(result, evidence_id=IDS[1], case_id=str(uuid4()))],
                [dict(result, score=None)], [dict(result, score=True)],
                [dict(result, score=float('nan'))], [dict(result, score=101)]):
            with self.subTest(results=results), self.assertRaises(ValueError):
                sort_triage_results(results, IDS)

    def test_strict_actual_schema_negatives(self):
        result = self.aggregate()
        for field in result:
            broken = dict(result)
            del broken[field]
            self.assertFalse(self.schema.is_valid(broken), field)
        for field, value in (('extra', True), ('score', None), ('score', True), ('score', 101),
                             ('priority', 'P5'), ('analysis_run_id', 'bad'), ('created_at', 'bad')):
            self.assertFalse(self.schema.is_valid(dict(result, **{field: value})), field)


class RealProducerAggregationTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_gps_processing_nodes_links_factors_and_aggregation(self):
        # Committed fixtures stay unrelated. The second run uses a clearly
        # labeled synthetic GPS variant to exercise a positive candidate edge.
        for shared in (False, True):
            with self.subTest(shared=shared), TemporaryDirectory() as directory:
                root = Path(directory)
                app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                    token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'foreign': 'investigator-2'}))
                async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
                        base_url='http://test', headers={'Authorization': 'Bearer local'}) as client:
                    response = await client.post('/api/v1/cases', json={'title': 'Synthetic A04'})
                    self.assertEqual(response.status_code, 201)
                    case = response.json()['id']
                    base = f'/api/v1/cases/{case}'
                    originals = {}
                    for name, kind in (('network.csv', 'network_log'), ('gps.csv', 'gps')):
                        data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
                        if shared and kind == 'gps':
                            data += b'2026-01-12T10:03:00Z,D-7,12.9716,77.5946\n'
                            name = 'gps-shared-synthetic.csv'
                        response = await client.post(base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic'},
                            files={'file': (name, data, 'text/csv')})
                        self.assertEqual(response.status_code, 201, response.text)
                        eid = response.json()['id']
                        originals[eid] = data
                        response = await client.post(base + f'/evidence/{eid}/processing-runs',
                            headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(response.status_code, 202, response.text)
                        response = await client.get(base + f"/evidence/{eid}/processing-runs/{response.json()['id']}")
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['status'], 'completed')
                    pages = {}
                    for path in ('evidence', 'entities', 'events', 'observations'):
                        response = await client.get(base + '/' + path, params={'limit': 100})
                        self.assertEqual(response.status_code, 200)
                        page = response.json()
                        self.assertEqual(len(page['items']), page['total'])
                        pages[path] = page['items']
                    before = deepcopy(pages)
                    nodes = build_graph_nodes(case, pages['evidence'], pages['entities'], pages['events'])
                    run = str(uuid4())  # Not persisted/published; A05 owns that lifecycle.
                    edges, findings = derive_candidate_links(case, run, pages['entities'], pages['observations'])
                    self.assertEqual((len(edges), len(findings)), (int(shared), int(shared)))
                    results = []
                    for index, eid in enumerate(originals):
                        count = sum(o['evidence_id'] == eid for o in pages['observations'])
                        relevance = calculate_relevance_factor(case_id=case, evidence_id=eid,
                            target_entities=[e for e in pages['entities'] if eid in e['evidence_ids']],
                            known_case_entities=pages['entities'], evidence_records=pages['evidence'],
                            observations=pages['observations'])
                        connectivity = calculate_connectivity_factor(case_id=case, evidence_id=eid,
                            target_nodes=nodes, edges=edges, observation_count=count)
                        self.assertEqual(relevance['value'], (.8, .4 if shared else .2)[index])
                        self.assertEqual(connectivity['value'], .1 if shared else 0.)
                        kwargs = dict(case_id=case, analysis_run_id=run, evidence_id=eid,
                            observation_count=count, factors=[relevance, connectivity],
                            case_evidence_ids=originals, created_at=TIME)
                        result = aggregate_triage_result(**kwargs)
                        result_validator().validate(result)
                        self.assertEqual(result['score'], ((48.88, 26.66) if shared else (44.44, 11.11))[index])
                        self.assertEqual(result['priority'], ('P3', 'P4')[index])
                        self.assertEqual(result, aggregate_triage_result(**kwargs))
                        results.append(result)
                        self.assertEqual((await client.get(base + f'/evidence/{eid}/content')).content, originals[eid])
                        self.assertEqual((await client.get(base + f'/evidence/{eid}',
                            headers={'Authorization': 'Bearer foreign'})).status_code, 404)
                    entries = sort_triage_results(list(reversed(results)), originals)
                    self.assertEqual([e['evidence_id'] for e in entries], list(originals))
                    for observation in pages['observations']:
                        row = int(observation['source_locator'].split(', ')[0].removeprefix('row '))
                        self.assertIn(observation['raw_value'].encode(),
                                      originals[observation['evidence_id']].splitlines()[row - 1])
                    self.assertEqual(pages, before)


if __name__ == '__main__':
    unittest.main()
