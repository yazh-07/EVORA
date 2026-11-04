"""A07 source-exact co-mentions and immutable analysis/triage reruns.

HTTP/SQLite/parsers/scoring are real; Neo4j uses an explicit transactional double.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_links import CO_MENTION_RULE, RULE, derive_candidate_links
from backend.parsers.candidate_entities import project_candidate_entities
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.message_entities import project_message_entities
from backend.parsers.messages_csv import parse_messages_csv
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.normalization import normalize_observations
from backend.tests.test_graph_projection import SyntheticNeo4j
from backend.tests.test_graph_nodes import validator
from backend.triage.factors import calculate_relevance_factor
from backend.triage.policy import POLICY_VERSION

ROOT = Path(__file__).resolve().parents[2]
NETWORK = (ROOT / 'fixtures/synthetic-case/network.csv').read_bytes()
GPS = (ROOT / 'fixtures/synthetic-case/gps.csv').read_bytes()
MESSAGES = (ROOT / 'fixtures/synthetic-case/messages.csv').read_bytes()


def project(case_id, data=MESSAGES, parser=parse_messages_csv):
    rows = parser(data, case_id=case_id, evidence_id=uuid4(), processing_run_id=uuid4())
    result = (project_message_entities(rows, case_id=case_id) if parser is parse_messages_csv
              else project_candidate_entities(normalize_observations(rows), case_id=case_id))
    return ([entity.to_wire() for entity in result.entities],
            [item.observation.to_wire() for item in result.observations])


def assert_links(test, edges, findings, entities, expected_pairs):
    """Assert every endpoint, rule and complete source citation, including controls."""
    by_id = {entity['id']: entity for entity in entities}
    actual_pairs = set()
    for edge in edges:
        wire = edge.to_wire() if hasattr(edge, 'to_wire') else edge
        validator('GraphEdge').validate(wire)
        endpoints = [by_id[wire['from_id']], by_id[wire['to_id']]]
        actual_pairs.add((wire['kind'], frozenset(entity['id'] for entity in endpoints)))
        expected_evidence = sorted({eid for entity in endpoints for eid in entity['evidence_ids']})
        expected_observations = sorted({oid for entity in endpoints for oid in entity['observation_ids']})
        test.assertEqual(wire['evidence_ids'], expected_evidence)
        test.assertEqual(wire['observation_ids'], expected_observations)
        test.assertEqual(wire['confidence'], 0.0)
        related = [finding.to_wire() if hasattr(finding, 'to_wire') else finding for finding in findings]
        related = [finding for finding in related if set(finding['entity_ids']) == {e['id'] for e in endpoints}]
        test.assertEqual(len(related), 1)
        finding = related[0]
        validator('Finding').validate(finding)
        test.assertEqual(finding['evidence_ids'], expected_evidence)
        test.assertEqual(finding['observation_ids'], expected_observations)
        test.assertEqual(finding['kind'], 'relationship')
        test.assertEqual(finding['confidence'], 0.0)
        test.assertEqual(finding['rule'], CO_MENTION_RULE if wire['kind'] == 'co_mention' else RULE)
    test.assertEqual(len(edges), len(expected_pairs))
    test.assertEqual(len(findings), len(expected_pairs))
    test.assertEqual(actual_pairs, expected_pairs)


def three_pairs(network, gps, messages):
    def device(entities, label):
        return next(e['id'] for e in entities if e['canonical_label'] == label)
    return {
        ('shared_identifier', frozenset((device(network, 'D-7'), device(messages, 'D-7')))),
        ('shared_identifier', frozenset((device(gps, 'D-8'), device(messages, 'D-8')))),
        ('co_mention', frozenset((device(messages, 'D-7'), device(messages, 'D-8')))),
    }


class CoMentionLinkTests(unittest.TestCase):
    def setUp(self):
        self.case, self.run = uuid4(), uuid4()
        self.entities, self.observations = project(self.case)

    def derive(self, entities=None, observations=None, run=None):
        return derive_candidate_links(str(self.case), str(run or self.run),
                                      self.entities if entities is None else entities,
                                      self.observations if observations is None else observations)

    def relevance(self, entities=None, observations=None):
        entities = self.entities if entities is None else entities
        observations = self.observations if observations is None else observations
        eid = self.entities[0]['evidence_ids'][0]
        return calculate_relevance_factor(case_id=str(self.case), evidence_id=eid,
            target_entities=entities, known_case_entities=entities, observations=observations,
            evidence_records=[dict(id=eid, case_id=str(self.case), filename='messages.csv')])

    def test_message_alone_produces_co_mention_edge_and_finding(self):
        edges, findings = self.derive()
        assert_links(self, edges, findings, self.entities,
                     {('co_mention', frozenset(e['id'] for e in self.entities))})
        body = next(o for o in self.observations if o['kind'] == 'message.body')
        self.assertTrue(all(body['id'] in entity['observation_ids'] for entity in self.entities))
        self.assertIn(body['id'], edges[0].observation_ids)
        self.assertIn('Candidate co-mention', findings[0].summary)
        self.assertIn('device:D-7', findings[0].summary)
        self.assertIn('device:D-8', findings[0].summary)
        self.assertIn('requires human verification', findings[0].summary)
        factor = self.relevance()
        validator('TriageFactor').validate(factor)
        self.assertEqual(factor['value'], 1.0)

    def test_three_modalities_have_exactly_three_links_and_d9_is_unlinked(self):
        network, net_obs = project(self.case, NETWORK, parse_network_csv)
        gps, gps_obs = project(self.case, GPS, parse_gps_csv)
        entities = network + gps + self.entities
        edges, findings = self.derive(entities, net_obs + gps_obs + self.observations)
        assert_links(self, edges, findings, entities, three_pairs(network, gps, self.entities))
        d9 = next(e['id'] for e in network if e['canonical_label'] == 'D-9')
        self.assertTrue(all(d9 not in (edge.from_id, edge.to_id) for edge in edges))
        self.assertTrue(all(d9 not in finding.entity_ids for finding in findings))

    def test_distinct_message_rows_do_not_link_and_repeated_pairs_are_deduplicated(self):
        data = (b'message_id,timestamp,sender,body\n'
                b'M1,t,s,D-7 D-8 D-7\nM2,t,s,D-8 D-9\nM3,t,s,D-7 D-8\n')
        entities, observations = project(self.case, data)
        edges, findings = self.derive(entities, observations)
        ids = {entity['canonical_label']: entity['id'] for entity in entities}
        assert_links(self, edges, findings, entities, {
            ('co_mention', frozenset((ids['D-7'], ids['D-8']))),
            ('co_mention', frozenset((ids['D-8'], ids['D-9']))),
        })
        entities, observations = project(self.case, b'message_id,timestamp,sender,body\nM1,t,s,D-7\nM2,t,s,D-8\n')
        self.assertEqual(self.derive(entities, observations), ([], []))

    def test_shared_generic_observation_and_duplicate_key_are_not_co_mentions(self):
        observations = [dict(o, kind='text.body') if o['kind'] == 'message.body' else o
                        for o in self.observations]
        self.assertEqual(self.derive(observations=observations), ([], []))
        duplicate = dict(self.entities[0], id=str(uuid4()))
        self.assertEqual(self.derive([self.entities[0], duplicate]), ([], []))
        self.assertEqual(self.derive([]), ([], []))

    def test_determinism_duplicates_run_partition_and_immutability(self):
        before = deepcopy((self.entities, self.observations))
        expected = self.derive()
        self.assertEqual(self.derive(iter(reversed(self.entities * 2)), iter(reversed(self.observations))), expected)
        self.assertEqual((self.entities, self.observations), before)
        newer = self.derive(run=uuid4())
        for old, new in zip(expected, newer):
            self.assertTrue({x.id for x in old}.isdisjoint(x.id for x in new))
            with self.assertRaises(FrozenInstanceError):
                old[0].confidence = 1
            wire = old[0].to_wire()
            wire['observation_ids'].clear()
            self.assertTrue(old[0].observation_ids)

    def test_relevance_requires_matching_mention_for_each_body_context(self):
        body = next(o for o in self.observations if o['kind'] == 'message.body')
        for changes in ({'source_locator': 'row 999, body'}, {'entity_key': 'device:D-7'},
                        {'kind': 'message.sender'}):
            observations = [dict(o, **changes) if o['id'] == body['id'] else o for o in self.observations]
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.relevance(observations=observations)
        body_only = [dict(entity, observation_ids=[body['id']]) for entity in self.entities]
        with self.assertRaises(ValueError):
            self.relevance(entities=body_only)
        self.assertEqual(self.derive(body_only), ([], []))
        for category in ('entities', 'observations'):
            entities, observations = deepcopy((self.entities, self.observations))
            (entities if category == 'entities' else observations)[0]['case_id'] = str(uuid4())
            with self.subTest(category=category), self.assertRaises(ValueError):
                self.derive(entities, observations)


class GraphDouble(SyntheticNeo4j):
    def close(self):
        pass


class CoMentionAnalysisLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        neo = GraphDouble()
        factory = patch.object(analysis, 'Neo4jGraphDatabase', return_value=neo)
        factory.start()
        self.addCleanup(factory.stop)
        self.app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'a07-user': 'investigator-1'}))
        life = self.app.router.lifespan_context(self.app)
        await life.__aenter__()
        self.addAsyncCleanup(life.__aexit__, None, None, None)
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
                                  headers={'Authorization': 'Bearer a07-user'})
        self.addAsyncCleanup(self.client.aclose)
        response = await self.client.post('/api/v1/cases', json={'title': 'Synthetic A07'})
        self.assertEqual(response.status_code, 201, response.text)
        self.base = f"/api/v1/cases/{response.json()['id']}"

    async def get(self, suffix):
        response = await self.client.get(self.base + suffix)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def upload(self, name, kind, data):
        response = await self.client.post(self.base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic'},
                                          files={'file': (name, data, 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        eid = response.json()['id']
        path = f'/evidence/{eid}/processing-runs'
        response = await self.client.post(self.base + path, headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        run = await self.get(path + '/' + response.json()['id'])
        self.assertEqual(run['status'], 'completed', run)
        return eid

    async def start(self, key):
        response = await self.client.post(self.base + '/analysis-runs', headers={'Idempotency-Key': key})
        self.assertEqual(response.status_code, 202, response.text)
        run = await self.get('/analysis-runs/' + response.json()['id'])
        self.assertEqual(run['status'], 'completed', run)
        self.assertEqual(run['algorithm_version'], f'evora-analysis/1;{RULE};{CO_MENTION_RULE};{POLICY_VERSION}')
        validator('AnalysisRun').validate(run)
        return run

    async def outputs(self, run):
        return {name: await self.get(f'/{name}?analysis_run_id={run["id"]}')
                for name in ('graph', 'findings', 'triage')}

    def stored(self, run):
        with self.app.state.database.connect() as connection:
            return dict(connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (run['id'],)).fetchone())

    @staticmethod
    def results(outputs):
        return {item['evidence_id']: item['latest_result'] for item in outputs['triage']['items']}

    async def test_message_only_analysis_publishes_graph_findings_and_triage(self):
        eid = await self.upload('messages.csv', 'message', MESSAGES)
        run = await self.start(str(uuid4()))
        outputs = await self.outputs(run)
        entities = (await self.get('/entities'))['items']
        assert_links(self, outputs['graph']['edges'], outputs['findings']['items'], entities,
                     {('co_mention', frozenset(entity['id'] for entity in entities))})
        result = self.results(outputs)[eid]
        validator('TriageResult').validate(result)
        self.assertEqual({f['name']: f['value'] for f in result['factors']},
                         {'relevance': 1.0, 'connectivity': 0.0})

    async def test_three_modality_rerun_recalculates_factors_and_preserves_history(self):
        net_id = await self.upload('network.csv', 'network_log', NETWORK)
        gps_id = await self.upload('gps.csv', 'gps', GPS)
        key1 = str(uuid4())
        run1 = await self.start(key1)
        self.assertEqual(run1['trigger'], 'initial')
        before = await self.outputs(run1)
        stored_before = self.stored(run1)
        self.assertEqual(before['graph']['edges'], [])
        self.assertEqual(before['findings']['items'], [])
        results1 = self.results(before)
        for eid in (net_id, gps_id):
            self.assertEqual(next(f['value'] for f in results1[eid]['factors'] if f['name'] == 'connectivity'), 0.0)

        msg_id = await self.upload('messages.csv', 'message', MESSAGES)
        run2 = await self.start(str(uuid4()))
        self.assertNotEqual(run2['id'], run1['id'])
        self.assertEqual(run2['trigger'], 'new_observations')
        self.assertEqual(set(run2['input_snapshot']['evidence_ids']), {net_id, gps_id, msg_id})
        self.assertTrue(set(run1['input_snapshot']['observation_ids']) < set(run2['input_snapshot']['observation_ids']))
        after = await self.outputs(run2)
        validator('Graph').validate(after['graph'])
        entities = (await self.get('/entities'))['items']
        groups = [[entity for entity in entities if eid in entity['evidence_ids']] for eid in (net_id, gps_id, msg_id)]
        assert_links(self, after['graph']['edges'], after['findings']['items'], entities, three_pairs(*groups))
        d9 = next(entity['id'] for entity in entities if entity['canonical_label'] == 'D-9')
        self.assertTrue(all(d9 not in (edge['from_id'], edge['to_id']) for edge in after['graph']['edges']))
        self.assertTrue(all(d9 not in finding['entity_ids'] for finding in after['findings']['items']))

        results2 = self.results(after)
        for eid, relevance, connectivity in ((net_id, 4/5, .1), (gps_id, 1/5, .1), (msg_id, 2/5, .2)):
            result = results2[eid]
            validator('TriageResult').validate(result)
            self.assertEqual(result['analysis_run_id'], run2['id'])
            factors = {factor['name']: factor for factor in result['factors']}
            self.assertEqual(factors['connectivity']['value'], connectivity)
            self.assertEqual(factors['relevance']['value'], relevance)
            self.assertEqual(factors['relevance']['evidence_ids'], [eid])
            if eid != msg_id:
                self.assertNotEqual(result['id'], results1[eid]['id'])
                self.assertGreater(result['score'], results1[eid]['score'])
                self.assertEqual(set(factors['connectivity']['evidence_ids']), {eid, msg_id})
                # Existing keys are repeated: relevance is recomputed, with no repetition boost.
                self.assertEqual(factors['relevance'], next(f for f in results1[eid]['factors'] if f['name'] == 'relevance'))
        self.assertEqual(await self.get('/triage'), after['triage'])

        # Compare complete persisted bytes and every historical API output after publication and replay.
        self.assertEqual(await self.start(key1), run1)
        self.assertEqual(await self.outputs(run1), before)
        self.assertEqual(self.stored(run1), stored_before)
        for eid in (net_id, gps_id):
            history = await self.get(f'/evidence/{eid}/triage-history')
            self.assertEqual(history, [results1[eid], results2[eid]])
        self.assertEqual(await self.get(f'/evidence/{msg_id}/triage-history'), [results2[msg_id]])

    async def test_new_message_key_recalculates_network_and_gps_relevance(self):
        net_id = await self.upload('network.csv', 'network_log', NETWORK)
        gps_id = await self.upload('gps.csv', 'gps', GPS)
        run1 = await self.start(str(uuid4()))
        before = self.results(await self.outputs(run1))
        # A new key expands the denominator without changing the frozen triage policy.
        await self.upload('messages.csv', 'message', MESSAGES + b'MSG-2,2026-01-12T10:04:00Z,s,D-10\n')
        run2 = await self.start(str(uuid4()))
        after = self.results(await self.outputs(run2))
        for eid, expected in ((net_id, 4/6), (gps_id, 1/6)):
            factor = next(f for f in after[eid]['factors'] if f['name'] == 'relevance')
            old = next(f for f in before[eid]['factors'] if f['name'] == 'relevance')
            self.assertEqual(factor['value'], expected)
            self.assertLess(factor['value'], old['value'])


if __name__ == '__main__':
    unittest.main()
