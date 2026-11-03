"""A02 synthetic controls, strict bundled schemas and real merged API producers."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_links import RULE, derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend.parsers.candidate_entities import project_candidate_entities
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.normalization import normalize_observations
from backend.tests.test_graph_nodes import validator

ROOT = Path(__file__).resolve().parents[2]
NETWORK = (ROOT / 'fixtures/synthetic-case/network.csv').read_bytes()
GPS = (ROOT / 'fixtures/synthetic-case/gps.csv').read_bytes()
# Explicit positive variant: preserve the committed D-8 row and prepend D-7.
# The committed fixture itself intentionally has no initial cross-source match.
GPS_SHARED = GPS.splitlines(keepends=True)[0] + GPS.splitlines(keepends=True)[1].replace(b'D-8', b'D-7') + GPS.splitlines(keepends=True)[1]


def projected(case, data, parser):
    result = project_candidate_entities(normalize_observations(parser(
        data, case_id=case, evidence_id=uuid4(), processing_run_id=uuid4())), case_id=case)
    return ([entity.to_wire() for entity in result.entities],
            [item.observation.to_wire() for item in result.observations])


class CandidateLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edge_schema = validator('GraphEdge')
        cls.finding_schema = validator('Finding')

    def setUp(self):
        self.case, self.run = uuid4(), uuid4()
        net_entities, net_observations = projected(self.case, NETWORK, parse_network_csv)
        gps_entities, gps_observations = projected(self.case, GPS_SHARED, parse_gps_csv)
        self.entities = net_entities + gps_entities
        self.observations = net_observations + gps_observations

    def derive(self, entities=None, observations=None):
        result = derive_candidate_links(str(self.case), str(self.run),
                                        self.entities if entities is None else entities,
                                        self.observations if observations is None else observations)
        for schema, records in zip((self.edge_schema, self.finding_schema), result):
            for record in records:
                schema.validate(record.to_wire())
        return result

    def test_shared_d7_cites_both_sources_and_d9_d8_remain_unlinked(self):
        edges, findings = self.derive()
        self.assertEqual((len(edges), len(findings)), (1, 1))
        edge, finding = edges[0], findings[0]
        matching = [entity for entity in self.entities if entity['candidate_key'] == 'device:D-7']
        expected_entities = {entity['id'] for entity in matching}
        expected_observations = {oid for entity in matching for oid in entity['observation_ids']}
        expected_evidence = {eid for entity in matching for eid in entity['evidence_ids']}
        self.assertEqual(len(expected_evidence), 2)
        self.assertEqual({edge.from_id, edge.to_id}, expected_entities)
        self.assertEqual(set(finding.entity_ids), expected_entities)
        by_id = {observation['id']: observation for observation in self.observations}
        for record in (edge, finding):
            self.assertEqual(set(record.evidence_ids), expected_evidence)
            self.assertEqual(set(record.observation_ids), expected_observations)
            self.assertEqual(record.case_id, str(self.case))
            self.assertEqual(record.confidence, 0.0)
            for oid in record.observation_ids:
                self.assertEqual(by_id[oid]['case_id'], str(self.case))
                self.assertIn(by_id[oid]['evidence_id'], expected_evidence)
                self.assertTrue(by_id[oid]['source_locator'])
                self.assertEqual(by_id[oid]['entity_key'], 'device:D-7')
        for entity in self.entities:
            if entity['canonical_label'] in ('D-9', 'D-8'):
                self.assertNotIn(entity['id'], expected_entities)
                self.assertTrue(set(entity['observation_ids']).isdisjoint(expected_observations))
        self.assertEqual(finding.kind, 'relationship')
        self.assertEqual(finding.rule, RULE)
        self.assertEqual(finding.analysis_run_id, str(self.run))
        self.assertIn('Candidate match', finding.summary)
        self.assertIn('device:D-7', finding.summary)
        self.assertIn('requires human verification', finding.summary)

    def test_committed_network_gps_fixtures_have_no_shared_identifier(self):
        entities, observations = projected(self.case, GPS, parse_gps_csv)
        network_entities = [e for e in self.entities if e['candidate_key'] != 'device:D-8'
                            and e['evidence_ids'] == self.entities[0]['evidence_ids']]
        network_ids = {oid for e in network_entities for oid in e['observation_ids']}
        network_observations = [o for o in self.observations if o['id'] in network_ids]
        self.assertEqual(self.derive(network_entities + entities, network_observations + observations), ([], []))

    def test_empty_and_singleton_and_missing_sources(self):
        self.assertEqual(derive_candidate_links(str(self.case), str(self.run), []), ([], []))
        self.assertEqual(self.derive([]), ([], []))
        self.assertEqual(self.derive(self.entities[:1]), ([], []))
        for sources in (None, []):
            with self.assertRaises(ValueError):
                derive_candidate_links(str(self.case), str(self.run), self.entities, sources)

    def test_exact_key_spelling_and_namespaces_are_not_merged(self):
        target = next(e for e in self.entities if e['candidate_key'] == 'device:D-7')
        remaining = [e for e in self.entities if e is not target]
        for kind, label in (('device', 'd-7'), ('device', ' D-7 '), ('device', 'D–7'), ('account', 'D-7')):
            key = kind + ':' + label
            changed = dict(target, kind=kind, canonical_label=label, candidate_key=key)
            observations = [dict(o, entity_key=key) if o['id'] in target['observation_ids'] else o
                            for o in self.observations]
            self.assertEqual(self.derive(remaining + [changed], observations), ([], []))

    def test_same_evidence_records_do_not_link_and_single_multi_source_has_no_self_edge(self):
        target = next(e for e in self.entities if e['candidate_key'] == 'device:D-7')
        duplicate = dict(target, id=str(uuid4()))
        self.assertEqual(self.derive([target, duplicate]), ([], []))
        matching = [e for e in self.entities if e['candidate_key'] == 'device:D-7']
        combined = dict(target, evidence_ids=sorted({eid for e in matching for eid in e['evidence_ids']}),
                        observation_ids=sorted({oid for e in matching for oid in e['observation_ids']}))
        self.assertEqual(self.derive([combined]), ([], []))

    def test_reordering_duplicate_entities_sorted_ids_and_run_partition(self):
        third, observations = projected(self.case, GPS_SHARED, parse_gps_csv)
        members = [e for e in self.entities + third if e['candidate_key'] == 'device:D-7']
        sources = self.observations + observations
        expected = self.derive(members, sources)
        self.assertEqual(tuple(map(len, expected)), (3, 3))
        for records in permutations(members):
            self.assertEqual(self.derive(iter(records), iter(reversed(sources))), expected)
        self.assertEqual(self.derive(members * 2, sources), expected)
        for records in expected:
            ids = [record.id for record in records]
            self.assertEqual(ids, sorted(set(ids)))
            self.assertEqual(len(ids), 3)
        new = derive_candidate_links(str(self.case), str(uuid4()), members, sources)
        for before, after in zip(expected, new):
            self.assertTrue({x.id for x in before}.isdisjoint(x.id for x in after))

    def test_inputs_results_and_wire_containers_are_immutable(self):
        before = deepcopy((self.entities, self.observations))
        result = self.derive()
        self.assertEqual(before, (self.entities, self.observations))
        for records in result:
            for record in records:
                with self.assertRaises(FrozenInstanceError):
                    record.confidence = 1
                wire = record.to_wire()
                wire['evidence_ids'].clear()
                wire['observation_ids'].clear()
                self.assertTrue(record.evidence_ids)
                self.assertTrue(record.observation_ids)
        self.assertEqual(self.derive(), result)

    def test_foreign_case_entity_and_observation_fail_even_when_unrelated_or_duplicate(self):
        foreign = str(uuid4())
        for entity in self.entities:
            with self.assertRaisesRegex(ValueError, 'case_id does not match'):
                self.derive(self.entities + [dict(entity, case_id=foreign)])
        for observation in self.observations:
            with self.assertRaisesRegex(ValueError, 'case_id does not match'):
                self.derive(observations=[dict(observation, case_id=foreign)] + self.observations)

    def test_missing_foreign_forged_observation_and_evidence_joins_rejected(self):
        entity = self.entities[0]
        for changes in ({'observation_ids': [str(uuid4())]}, {'evidence_ids': [str(uuid4())]},
                        {'evidence_ids': entity['evidence_ids'] + [str(uuid4())]}):
            with self.assertRaises(ValueError):
                self.derive([dict(entity, **changes)])
        oid = entity['observation_ids'][0]
        for changes in ({'source_locator': ''}, {'source_locator': ' \t'},
                        {'entity_key': 'device:foreign'}, {'evidence_id': str(uuid4())}):
            with self.assertRaises(ValueError):
                self.derive(observations=[dict(o, **changes) if o['id'] == oid else o for o in self.observations])
        # Optional entity_key is not mandatory for generic future observations.
        self.assertEqual(self.derive(observations=[{k: v for k, v in o.items() if k != 'entity_key'}
                                                  for o in self.observations]), self.derive())

    def test_duplicate_observations_conflicting_entities_and_mixed_runs_fail(self):
        with self.assertRaises(ValueError):
            self.derive(observations=self.observations + [self.observations[0]])
        for field, value in (('confidence', .5), ('candidate_key', 'device:other')):
            with self.assertRaises(ValueError):
                self.derive(self.entities + [dict(self.entities[0], **{field: value})])
        changed = dict(self.observations[0], processing_run_id=str(uuid4()))
        with self.assertRaisesRegex(ValueError, 'processing run'):
            self.derive(observations=[changed] + self.observations[1:])

    def test_invalid_context_references_records_and_confidence_fail_cleanly(self):
        for field in ('case_id', 'analysis_run_id'):
            for bad in ('invalid', str(self.case).upper(), None, True):
                arguments = dict(case_id=str(self.case), analysis_run_id=str(self.run), entities=[])
                arguments[field] = bad
                with self.assertRaises(ValueError):
                    derive_candidate_links(**arguments)
        for field in ('id', 'case_id', 'kind', 'canonical_label', 'candidate_key', 'evidence_ids', 'observation_ids', 'confidence'):
            entity = dict(self.entities[0])
            del entity[field]
            with self.assertRaises(ValueError):
                self.derive([entity])
        for field in ('evidence_ids', 'observation_ids'):
            for bad in ([], None, 'invalid', ['invalid'], self.entities[0][field] * 2):
                with self.assertRaises(ValueError):
                    self.derive([dict(self.entities[0], **{field: bad})])
        for bad in (float('nan'), float('inf'), True, -.1, 1.1, '0.5'):
            with self.assertRaises(ValueError):
                self.derive([dict(self.entities[0], confidence=bad)])
        for bad in (None, [None], [1], ['invalid']):
            with self.assertRaises(ValueError):
                derive_candidate_links(str(self.case), str(self.run), bad, self.observations)

    def test_strict_schema_negative_controls(self):
        for schema, records in zip((self.edge_schema, self.finding_schema), self.derive()):
            wire = records[0].to_wire()
            for field in schema.schema['components']['schemas']['GraphEdge' if 'from_id' in wire else 'Finding']['required']:
                missing = dict(wire)
                del missing[field]
                self.assertFalse(schema.is_valid(missing), field)
            for field, value in (('extra', True), ('id', 'invalid'), ('case_id', 'invalid'),
                                 ('confidence', -1), ('confidence', 2), ('confidence', True),
                                 ('evidence_ids', []), ('observation_ids', []),
                                 ('observation_ids', ['invalid']),
                                 ('observation_ids', wire['observation_ids'] * 2),
                                 ('evidence_ids', wire['evidence_ids'] * 2)):
                self.assertFalse(schema.is_valid(dict(wire, **{field: value})), field)
        self.assertFalse(self.finding_schema.is_valid(dict(self.derive()[1][0].to_wire(), kind='candidate_match')))


class RealProducerLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_upload_processing_api_nodes_links_source_readback_and_case_isolation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'a02-local': 'investigator-1',
                                                                    'a02-foreign': 'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
                    base_url='http://test', headers={'Authorization': 'Bearer a02-local'}) as client:
                case = (await client.post('/api/v1/cases', json={'title': 'Synthetic A02'})).json()['id']
                base = f'/api/v1/cases/{case}'
                originals = {}
                for name, kind, data in (('network.csv', 'network_log', NETWORK),
                                         ('gps-shared-synthetic.csv', 'gps', GPS_SHARED)):
                    response = await client.post(base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic A02'},
                                                 files={'file': (name, data, 'text/csv')})
                    self.assertEqual(response.status_code, 201, response.text)
                    evidence = response.json()
                    originals[evidence['id']] = data
                    response = await client.post(base + f"/evidence/{evidence['id']}/processing-runs",
                                                 headers={'Idempotency-Key': str(uuid4())})
                    self.assertEqual(response.status_code, 202, response.text)
                    run = response.json()['id']
                    response = await client.get(base + f"/evidence/{evidence['id']}/processing-runs/{run}")
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['status'], 'completed', response.text)
                pages = {}
                for path in ('evidence', 'entities', 'events', 'observations'):
                    response = await client.get(base + '/' + path, params={'limit': 100})
                    self.assertEqual(response.status_code, 200, response.text)
                    page = response.json()
                    self.assertEqual(len(page['items']), page['total'])
                    pages[path] = page['items']
                before = deepcopy(pages)
                nodes = build_graph_nodes(case, pages['evidence'], pages['entities'], pages['events'])
                # Unpersisted analysis UUID: this checks the rule, not A05 lifecycle.
                analysis = str(uuid4())
                edges, findings = derive_candidate_links(case, analysis, pages['entities'], pages['observations'])
                self.assertEqual((len(edges), len(findings)), (1, 1))
                node_ids = {node.id for node in nodes}
                observations = {o['id']: o for o in pages['observations']}
                entities = {e['id']: e for e in pages['entities']}
                for schema, record in (('GraphEdge', edges[0]), ('Finding', findings[0])):
                    validator(schema).validate(record.to_wire())
                    self.assertEqual(set(record.evidence_ids), originals.keys())
                    self.assertEqual({observations[oid]['evidence_id'] for oid in record.observation_ids}, originals.keys())
                    for oid in record.observation_ids:
                        source = observations[oid]
                        self.assertEqual(source['case_id'], case)
                        location, column = source['source_locator'].split(', ')
                        self.assertEqual(column, 'device_id')
                        row = int(location.removeprefix('row '))
                        self.assertIn(b'D-7', originals[source['evidence_id']].splitlines()[row - 1])
                self.assertTrue({edges[0].from_id, edges[0].to_id} <= node_ids)
                self.assertEqual({entities[eid]['candidate_key'] for eid in findings[0].entity_ids}, {'device:D-7'})
                self.assertTrue(all(e['id'] not in findings[0].entity_ids for e in pages['entities']
                                    if e['canonical_label'] in ('D-9', 'D-8')))
                for eid, data in originals.items():
                    response = await client.get(base + f'/evidence/{eid}/content')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, data)
                foreign_headers = {'Authorization': 'Bearer a02-foreign'}
                foreign_case = (await client.post('/api/v1/cases', json={'title': 'Synthetic foreign'},
                                                  headers=foreign_headers)).json()['id']
                for path in ('entities', 'observations'):
                    self.assertEqual((await client.get(f'/api/v1/cases/{foreign_case}/{path}')).status_code, 404)
                for category in ('entities', 'observations'):
                    changed = dict(pages)
                    changed[category] = pages[category] + [dict(pages[category][0], case_id=foreign_case)]
                    with self.assertRaises(ValueError):
                        derive_candidate_links(case, analysis, changed['entities'], changed['observations'])
                self.assertEqual(pages, before)
                self.assertEqual((edges, findings), derive_candidate_links(case, analysis, pages['entities'], pages['observations']))


if __name__ == '__main__':
    unittest.main()
