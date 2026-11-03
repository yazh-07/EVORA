"""A03 synthetic negatives and real merged processing/source API acceptance."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_links import derive_candidate_links
from backend.tests.test_graph_links import NETWORK, GPS_SHARED, projected
from backend.tests.test_graph_nodes import BAD_UUIDS, validator
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.gps_csv import parse_gps_csv
from backend.triage.factors import calculate_relevance_factor
from backend.triage.policy import FactorValue, score_evidence


class RelevanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = validator('TriageFactor')

    def setUp(self):
        case = uuid4()
        self.case = str(case)
        net, net_obs = projected(case, NETWORK, parse_network_csv)
        gps, gps_obs = projected(case, GPS_SHARED, parse_gps_csv)
        self.target = net[0]['evidence_ids'][0]
        self.entities, self.observations = net + gps, net_obs + gps_obs
        self.kw = dict(case_id=self.case, evidence_id=self.target,
                       target_entities=net, known_case_entities=self.entities,
                       observations=self.observations,
                       evidence_records=[dict(id=eid, case_id=self.case, filename='synthetic.csv')
                                         for eid in sorted({o['evidence_id'] for o in self.observations})])

    def factor(self, **changes):
        result = calculate_relevance_factor(**(self.kw | changes))
        if result is not None:
            self.schema.validate(result)
        return result

    def test_network_fixture_counts_source_keys_and_default_weight(self):
        factor = self.factor()
        target_keys = {e['candidate_key'] for e in self.kw['target_entities']}
        known_keys = {e['candidate_key'] for e in self.entities}
        self.assertEqual(factor['value'], len(target_keys) / len(known_keys))
        self.assertEqual((len(target_keys), len(known_keys)), (4, 5))
        self.assertEqual((factor['weight'], factor['contribution']), (.25, 20.0))
        self.assertEqual(factor['evidence_ids'], [self.target])
        self.assertIn('Matched 4 of 5', factor['explanation'])
        for key in target_keys:
            self.assertIn(key, factor['explanation'])
        self.assertNotIn('device:D-8', factor['explanation'])

    def test_partial_full_zero_matches(self):
        targets = self.kw['target_entities']
        for known, value, counts in ((targets[:2], .5, '1 of 2'),
                                     (targets[:1], 1., '1 of 1'),
                                     (targets[1:2], 0., '0 of 1')):
            with self.subTest(value=value):
                factor = self.factor(target_entities=targets[:1], known_case_entities=known)
                self.assertEqual(factor['value'], value)
                self.assertIn(counts, factor['explanation'])
                if value == 0:
                    self.assertIn('none', factor['explanation'])
        self.assertEqual(self.factor(target_entities=[])['value'], 0.)

    def test_missing_known_or_unanalyzed_or_no_observations_is_absent(self):
        for changes in ({'known_case_entities': None}, {'known_case_entities': []},
                        {'target_entities': None}):
            self.assertIsNone(self.factor(**changes))
        self.assertIsNone(self.factor(target_entities=[], known_case_entities=[], observations=[]))
        gps = [e for e in self.entities if self.target not in e['evidence_ids']]
        self.assertIsNone(self.factor(target_entities=[], known_case_entities=gps,
                                     observations=[o for o in self.observations if o['evidence_id'] != self.target]))

    def test_duplicates_permutations_generators_and_input_immutability(self):
        before = deepcopy(self.kw)
        expected = self.factor()
        self.assertEqual(self.factor(target_entities=iter(self.kw['target_entities'] * 2),
                                     known_case_entities=iter(reversed(self.entities * 3)),
                                     observations=iter(reversed(self.observations))), expected)
        self.assertEqual(self.kw, before)
        expected['evidence_ids'].clear()
        self.assertEqual(self.factor()['evidence_ids'], [self.target])

    def test_exact_fraction_and_contribution_weight_boundaries(self):
        for weight in (0, .3333, 1):
            factor = self.factor(target_entities=self.kw['target_entities'][:1],
                                 known_case_entities=self.kw['target_entities'][:3], weight=weight)
            self.assertEqual(factor['value'], 1 / 3)
            self.assertEqual(factor['contribution'], round(100 * (1 / 3) * weight, 2))

    def test_exact_namespaced_keys_and_confidence_do_not_change_matches(self):
        target = self.kw['target_entities'][0]
        for kind, label in (('account', target['canonical_label']),
                            (target['kind'], target['canonical_label'].lower()),
                            (target['kind'], ' ' + target['canonical_label'])):
            key = f'{kind}:{label}'
            changed = dict(target, id=str(uuid4()), kind=kind, canonical_label=label, candidate_key=key)
            changed_sources = [dict(o, entity_key=key) if o['id'] in target['observation_ids'] else o
                               for o in self.observations]
            self.assertEqual(self.factor(target_entities=[changed], known_case_entities=self.entities[1:],
                                         observations=changed_sources)['value'], 0.)
        before = self.factor()
        self.assertEqual(self.factor(target_entities=[dict(e, confidence=1.) for e in self.kw['target_entities']],
                                     known_case_entities=[dict(e, confidence=1.) for e in self.entities]), before)

    def test_invalid_weight_rejected_even_when_absent(self):
        for weight in (-.1, 1.1, float('nan'), float('inf'), True, '0.25'):
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                self.factor(weight=weight, target_entities=None)

    def test_uuid_context_and_reference_rejections(self):
        for bad in BAD_UUIDS:
            for field in ('case_id', 'evidence_id'):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    self.factor(**{field: bad})
        for field in ('id', 'case_id', 'evidence_ids', 'observation_ids'):
            entity = dict(self.entities[0], **{field: ['invalid'] if field.endswith('_ids') else 'invalid'})
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.factor(known_case_entities=[entity])

    def test_foreign_case_rejected_in_every_input_even_absent(self):
        foreign = str(uuid4())
        for field in ('target_entities', 'known_case_entities', 'evidence_records', 'observations'):
            record = dict(self.kw[field][0], case_id=foreign)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.factor(**{field: self.kw[field] + [record]})
        with self.assertRaises(ValueError):
            self.factor(target_entities=None, known_case_entities=[dict(self.entities[0], case_id=foreign)])
        with self.assertRaises(ValueError):
            self.factor(evidence_id=str(uuid4()))

    def test_unscoped_labels_and_wrong_target_evidence_rejected(self):
        with self.assertRaises(ValueError):
            self.factor(target_entities=['device:D-7'])
        gps = [e for e in self.entities if self.target not in e['evidence_ids']]
        with self.assertRaises(ValueError):
            self.factor(target_entities=gps)

    def test_broken_or_ambiguous_lineage_rejected(self):
        entity = self.entities[0]
        for changes in ({'candidate_key': 'device:forged'}, {'observation_ids': []},
                        {'observation_ids': entity['observation_ids'] * 2},
                        {'observation_ids': [str(uuid4())]},
                        {'evidence_ids': [str(uuid4())]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.factor(known_case_entities=[dict(entity, **changes)])
        for changes in ({'source_locator': ''}, {'entity_key': 'device:forged'},
                        {'evidence_id': str(uuid4())}, {'processing_run_id': str(uuid4())}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.factor(observations=[dict(self.observations[0], **changes)] + self.observations[1:])
        with self.assertRaises(ValueError):
            self.factor(observations=self.observations * 2)
        with self.assertRaises(ValueError):
            self.factor(known_case_entities=self.entities + [dict(entity, candidate_key='device:other')])

    def test_strict_schema_negatives(self):
        wire = self.factor()
        for field in wire:
            missing = dict(wire)
            del missing[field]
            self.assertFalse(self.schema.is_valid(missing), field)
        for field, value in (('extra', True), ('name', 'invented'), ('value', -1),
                             ('value', 2), ('value', True), ('weight', -1), ('weight', 2),
                             ('contribution', -1), ('contribution', 101), ('explanation', None),
                             ('evidence_ids', ['invalid']), ('evidence_ids', [self.target] * 2)):
            self.assertFalse(self.schema.is_valid(dict(wire, **{field: value})), field)

    def test_g02_aggregator_renormalizes_and_preserves_absent(self):
        factor = self.factor()
        result = score_evidence(evidence_id=self.target, observation_count=6,
                                factors={'relevance': FactorValue(factor['value'], factor['explanation'],
                                                                  tuple(factor['evidence_ids']))},
                                case_evidence_ids=[self.target])
        self.assertEqual((result.score, result.factors[0]['weight']), (80., 1.))
        self.assertIsNone(score_evidence(evidence_id=self.target, observation_count=0,
                                        factors={'relevance': None}, case_evidence_ids=[self.target]))


class RealProducerRelevanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_api_processing_a02_and_relevance_source_readback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'foreign': 'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
                    base_url='http://test', headers={'Authorization': 'Bearer local'}) as client:
                response = await client.post('/api/v1/cases', json={'title': 'Synthetic A03'})
                self.assertEqual(response.status_code, 201)
                case = response.json()['id']
                base = f'/api/v1/cases/{case}'
                originals = {}
                for name, kind, data in (('network.csv', 'network_log', NETWORK),
                                         ('gps-shared-synthetic.csv', 'gps', GPS_SHARED)):
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
                for path in ('evidence', 'entities', 'observations'):
                    response = await client.get(base + '/' + path, params={'limit': 100})
                    self.assertEqual(response.status_code, 200)
                    page = response.json()
                    self.assertEqual(len(page['items']), page['total'])
                    pages[path] = page['items']
                before = deepcopy(pages)
                edges, findings = derive_candidate_links(case, str(uuid4()), pages['entities'], pages['observations'])
                self.assertEqual((len(edges), len(findings)), (1, 1))
                expected = (.8, .4)
                for eid, value in zip(originals, expected):
                    target = [e for e in pages['entities'] if eid in e['evidence_ids']]
                    kwargs = dict(case_id=case, evidence_id=eid, target_entities=target,
                                  known_case_entities=pages['entities'], evidence_records=pages['evidence'],
                                  observations=pages['observations'])
                    factor = calculate_relevance_factor(**kwargs)
                    validator('TriageFactor').validate(factor)
                    self.assertEqual(factor['value'], value)
                    self.assertEqual(factor['evidence_ids'], [eid])
                    for entity in target:
                        self.assertIn(entity['candidate_key'], factor['explanation'])
                        for oid in entity['observation_ids']:
                            source = next(o for o in pages['observations'] if o['id'] == oid)
                            self.assertEqual(source['evidence_id'], eid)
                            row = int(source['source_locator'].split(', ')[0].removeprefix('row '))
                            self.assertIn(source['raw_value'].encode(), originals[eid].splitlines()[row - 1])
                    self.assertEqual(calculate_relevance_factor(**kwargs), factor)
                    self.assertEqual((await client.get(base + f'/evidence/{eid}/content')).content, originals[eid])
                    denied = await client.get(base + f'/evidence/{eid}', headers={'Authorization': 'Bearer foreign'})
                    self.assertEqual(denied.status_code, 404)
                self.assertEqual(pages, before)


if __name__ == '__main__':
    unittest.main()
