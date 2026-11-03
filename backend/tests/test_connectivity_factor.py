"""A03B synthetic topology controls and real merged source/API acceptance."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_links import derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend.tests.test_graph_links import NETWORK, GPS_SHARED
from backend.tests.test_graph_nodes import BAD_UUIDS, validator
from backend.triage.factors import calculate_connectivity_factor
from backend.triage.policy import FactorValue, score_evidence


def uid():
    return str(uuid4())


class ConnectivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = validator('TriageFactor')

    def setUp(self):
        self.case, self.target, self.other = uid(), uid(), uid()
        self.node = dict(id=uid(), case_id=self.case, kind='device', label='Synthetic D-7',
                         evidence_ids=[self.target])
        self.neighbor = dict(id=uid(), case_id=self.case, kind='device', label='Synthetic neighbor',
                             evidence_ids=[self.other])
        self.edge = dict(id=uid(), case_id=self.case, from_id=self.node['id'],
                         to_id=self.neighbor['id'], kind='shared_identifier',
                         evidence_ids=sorted([self.target, self.other]),
                         observation_ids=[uid()], confidence=0.)
        self.kw = dict(case_id=self.case, evidence_id=self.target,
                       target_nodes=[self.node, self.neighbor], edges=[self.edge], observation_count=1)

    def factor(self, **changes):
        result = calculate_connectivity_factor(**(self.kw | changes))
        if result is not None:
            self.schema.validate(result)
        return result

    def test_single_neighbor_default_weight_explanation_and_citations(self):
        factor = self.factor()
        self.assertEqual((factor['name'], factor['value'], factor['weight'], factor['contribution']),
                         ('connectivity', .1, .2, 2.))
        self.assertEqual(factor['evidence_ids'], sorted([self.target, self.other]))
        self.assertIn('1 distinct case graph neighbor via candidate links', factor['explanation'])
        self.assertIn('not truth, identity or guilt', factor['explanation'])

    def test_degree_and_saturation(self):
        for count in (2, 9, 10, 15):
            nodes = [dict(self.neighbor, id=uid(), evidence_ids=[uid()]) for _ in range(count)]
            edges = [dict(self.edge, id=uid(), to_id=n['id'],
                          evidence_ids=sorted([self.target, *n['evidence_ids']])) for n in nodes]
            factor = self.factor(target_nodes=[self.node, *nodes], edges=edges)
            self.assertEqual(factor['value'], min(count / 10., 1.))
            self.assertIn(f'{count} distinct', factor['explanation'])
            self.assertEqual(factor['evidence_ids'], sorted({self.target, *(n['evidence_ids'][0] for n in nodes)}))
        # Degree counts source node UUIDs, even when neighbors cite one Evidence.
        second = dict(self.neighbor, id=uid())
        factor = self.factor(target_nodes=[self.node, self.neighbor, second],
                             edges=[self.edge, dict(self.edge, id=uid(), to_id=second['id'])])
        self.assertEqual(factor['value'], .2)
        self.assertEqual(factor['evidence_ids'], sorted([self.target, self.other]))

    def test_analyzed_zero_and_missing_data(self):
        self.assertEqual(self.factor(edges=[])['value'], 0.)
        self.assertEqual(self.factor(target_nodes=[], edges=[])['value'], 0.)
        for changes in ({'observation_count': 0}, {'observation_count': None},
                        {'target_nodes': None}, {'edges': None}):
            self.assertIsNone(self.factor(**changes))
        kw = dict(self.kw)
        del kw['observation_count']
        self.assertIsNone(calculate_connectivity_factor(**kw))

    def test_self_internal_unrelated_and_reverse_edges(self):
        internal = dict(self.neighbor, evidence_ids=[self.target])
        self.assertEqual(self.factor(target_nodes=[self.node, internal])['value'], 0.)
        self.assertEqual(self.factor(edges=[dict(self.edge, to_id=self.node['id'])])['value'], 0.)
        unrelated = dict(self.edge, from_id=self.neighbor['id'], to_id=self.neighbor['id'])
        self.assertEqual(self.factor(edges=[unrelated])['value'], 0.)
        self.assertEqual(self.factor(edges=[dict(self.edge, from_id=self.neighbor['id'],
                                                to_id=self.node['id'])]), self.factor())

    def test_deduplicates_neighbors_across_target_nodes_and_parallel_edges(self):
        second_target = dict(self.node, id=uid())
        edges = [self.edge, dict(self.edge, id=uid(), from_id=second_target['id']),
                 dict(self.edge, id=uid())]
        self.assertEqual(self.factor(target_nodes=[self.node, second_target, self.neighbor], edges=edges), self.factor())

    def test_citations_union_neighbor_and_edge_sources_only(self):
        extra, unused = uid(), uid()
        neighbor = dict(self.neighbor, evidence_ids=[self.other, extra])
        unrelated = dict(self.neighbor, id=uid(), evidence_ids=[unused])
        factor = self.factor(target_nodes=[self.node, neighbor, unrelated])
        self.assertEqual(factor['evidence_ids'], sorted([self.target, self.other, extra]))

    def test_order_generators_duplicates_and_immutability(self):
        before = deepcopy(self.kw)
        expected = self.factor()
        self.assertEqual(self.factor(target_nodes=iter(reversed(self.kw['target_nodes'] * 2)),
                                     edges=iter([self.edge] * 3)), expected)
        self.assertEqual(self.kw, before)
        expected['evidence_ids'].clear()
        self.assertEqual(len(self.factor()['evidence_ids']), 2)

    def test_weights_rounding_and_no_score_confidence_or_count_dependency(self):
        for weight in (0, .3333, 1):
            factor = self.factor(weight=weight)
            self.assertEqual(factor['contribution'], round(.1 * weight * 100, 2))
        self.assertEqual(self.factor(observation_count=10000, edges=[dict(self.edge, confidence=1.)]), self.factor())
        factor = self.factor()
        scored = score_evidence(evidence_id=self.target, observation_count=1,
                                factors={'connectivity': FactorValue(factor['value'], factor['explanation'],
                                                                     tuple(factor['evidence_ids']))},
                                case_evidence_ids=[self.target, self.other])
        self.assertEqual((scored.score, scored.factors[0]['weight']), (10., 1.))

    def test_invalid_weights_and_observation_counts(self):
        for weight in (True, '0.2', float('nan'), float('inf'), -.1, 1.1):
            with self.assertRaises(ValueError):
                self.factor(weight=weight, observation_count=0)
        for count in (True, -1, 1., '1'):
            with self.assertRaises(ValueError):
                self.factor(observation_count=count)

    def test_foreign_cases_rejected_even_absent_or_unrelated(self):
        for count in (None, 0, 1):
            for changes in ({'target_nodes': [self.node, dict(self.neighbor, case_id=uid())]},
                            {'edges': [dict(self.edge, case_id=uid())]},
                            {'case_id': uid()}):
                with self.assertRaises(ValueError):
                    self.factor(**changes, observation_count=count)

    def test_invalid_uuids_and_references(self):
        for bad in BAD_UUIDS:
            for field in ('case_id', 'evidence_id'):
                with self.assertRaises(ValueError):
                    self.factor(**{field: bad})
            for field in ('id', 'case_id', 'from_id', 'to_id'):
                with self.assertRaises(ValueError):
                    self.factor(edges=[dict(self.edge, **{field: bad})])
            with self.assertRaises(ValueError):
                self.factor(target_nodes=[dict(self.node, id=bad)])
        for field in ('evidence_ids', 'observation_ids'):
            for bad in ([], None, 'bad', ['bad'], self.edge[field] * 2):
                with self.assertRaises(ValueError):
                    self.factor(edges=[dict(self.edge, **{field: bad})], observation_count=0)
        for bad in ([], ['bad'], [self.target, self.target]):
            with self.assertRaises(ValueError):
                self.factor(target_nodes=[dict(self.node, evidence_ids=bad)])

    def test_malformed_conflicting_dangling_and_unsupported_records(self):
        for changes in ({'target_nodes': [None]}, {'edges': [None]},
                        {'target_nodes': 1}, {'edges': True},
                        {'target_nodes': [self.node, dict(self.node, label='conflict')]},
                        {'edges': [self.edge, dict(self.edge, confidence=1.)]},
                        {'edges': [dict(self.edge, to_id=uid())]},
                        {'edges': [dict(self.edge, evidence_ids=[self.other])]},
                        {'edges': [dict(self.edge, confidence=True)]},
                        {'edges': [dict(self.edge, confidence=float('nan'))]}):
            with self.assertRaises(ValueError):
                self.factor(**changes)

    def test_strict_openapi_schema_negative_controls(self):
        wire = self.factor()
        for field in wire:
            changed = dict(wire)
            del changed[field]
            self.assertFalse(self.schema.is_valid(changed), field)
        for field, value in (('extra', True), ('name', 'degree'), ('value', -.1), ('value', 1.1),
                             ('value', True), ('weight', -1), ('weight', 2), ('contribution', -1),
                             ('contribution', 101), ('explanation', None), ('evidence_ids', ['bad']),
                             ('evidence_ids', wire['evidence_ids'] * 2)):
            self.assertFalse(self.schema.is_valid(dict(wire, **{field: value})), field)


class RealProducerConnectivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_api_processing_a01_a02_connectivity_and_source_readback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'foreign': 'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
                    base_url='http://test', headers={'Authorization': 'Bearer local'}) as client:
                response = await client.post('/api/v1/cases', json={'title': 'Synthetic A03B'})
                self.assertEqual(response.status_code, 201)
                case = response.json()['id']
                base = f'/api/v1/cases/{case}'
                originals = {}
                # Committed GPS has D-8 only; this labeled in-test variant adds D-7.
                for name, kind, data in (('network.csv', 'network_log', NETWORK),
                                         ('gps-shared-synthetic.csv', 'gps', GPS_SHARED)):
                    response = await client.post(base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic'},
                                                 files={'file': (name, data, 'text/csv')})
                    self.assertEqual(response.status_code, 201, response.text)
                    eid = response.json()['id']
                    originals[eid] = data
                    response = await client.post(base + f'/evidence/{eid}/processing-runs',
                                                 headers={'Idempotency-Key': uid()})
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
                # Unpersisted analysis UUID: no publication/lifecycle claim.
                edges, findings = derive_candidate_links(case, uid(), pages['entities'], pages['observations'])
                self.assertEqual((len(edges), len(findings)), (1, 1))
                for eid in originals:
                    kwargs = dict(case_id=case, evidence_id=eid, target_nodes=nodes, edges=edges,
                                  observation_count=sum(o['evidence_id'] == eid for o in pages['observations']))
                    factor = calculate_connectivity_factor(**kwargs)
                    validator('TriageFactor').validate(factor)
                    self.assertEqual((factor['value'], factor['contribution']), (.1, 2.))
                    self.assertEqual(factor['evidence_ids'], sorted(originals))
                    self.assertEqual(calculate_connectivity_factor(**kwargs), factor)
                    self.assertEqual(calculate_connectivity_factor(**(kwargs | {
                        'target_nodes': [n.to_wire() for n in nodes],
                        'edges': [e.to_wire() for e in edges]})), factor)
                    self.assertEqual((await client.get(base + f'/evidence/{eid}/content')).content, originals[eid])
                    self.assertEqual((await client.get(base + f'/evidence/{eid}',
                        headers={'Authorization': 'Bearer foreign'})).status_code, 404)
                sources = {o['id']: o for o in pages['observations']}
                for oid in edges[0].observation_ids:
                    source = sources[oid]
                    self.assertEqual(source['case_id'], case)
                    location, column = source['source_locator'].split(', ')
                    self.assertEqual(column, 'device_id')
                    row = int(location.removeprefix('row '))
                    self.assertIn(b'D-7', originals[source['evidence_id']].splitlines()[row - 1])
                self.assertEqual(pages, before)


if __name__ == '__main__':
    unittest.main()
