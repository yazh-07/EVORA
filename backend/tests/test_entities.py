"""P05 actual source-backed Entity reads, with labeled selection/fault fixtures."""
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.entities import _page
from backend.processing import process_run

ROOT = Path(__file__).resolve().parents[2]


class EntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p05-synthetic-one': 'investigator-1', 'p05-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p05-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P05 case'})).json()['id']
        self.url = f'/api/v1/cases/{self.case}/entities'
        self.evidence = await self.upload()
        self.run = await self.process(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    async def upload(self, kind='network_log', data=None, case=None):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / ('gps.csv' if kind == 'gps' else 'network.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence', data={'kind': kind, 'source_label': 'Synthetic P05'},
            files={'file': ('source.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201)
        return response.json()

    async def process(self, evidence):
        response = await self.client.post(f"/api/v1/cases/{evidence['case_id']}/evidence/{evidence['id']}/processing-runs",
                                          headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202)
        return response.json()

    async def page(self, **params):
        response = await self.client.get(self.url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def output(self, run):
        with self.app.state.database.connect() as connection:
            return dict(connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone())

    def validate(self, name, value):
        Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': self.bundle['components']},
                             format_checker=FormatChecker()).validate(value)

    def fixture(self, finished_at, integer_id, observations=None, entities=None):
        """Selection/wire-only fixture; not a claim of another implemented producer."""
        original = self.output(self.run)
        observations = observations if observations is not None else json.loads(original['observations_json'])
        entities = entities if entities is not None else json.loads(original['entities_json'])
        run_id = str(UUID(int=integer_id))
        mapping = {x['id']: str(uuid4()) for x in observations}
        observations = [dict(x, id=mapping[x['id']], processing_run_id=run_id) for x in observations]
        entities = [dict(x, id=str(uuid4()), observation_ids=[mapping[oid] for oid in x['observation_ids']]) for x in entities]
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
                'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run_id, self.case, self.evidence['id'], 'investigator-1', str(uuid4()), 'synthetic-fixture', '{}',
                 'P05-selection-fixture/1', '2099-01-01T00:00:00Z', 'queued'))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (run_id, self.case, self.evidence['id'], json.dumps(observations), json.dumps(entities), '[]', '[]'))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (finished_at, run_id))
        return entities

    def allow_output_corruption(self):
        # Only temporary fixture DB: deliberately bypass immutable protection to test read guards.
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_update')

    async def test_real_network_gps_wire_sources_and_actual_event_participant_ids_preserved(self):
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        page = response.json(); self.validate('EntityPage', page)
        self.assertEqual((page['total'], page['limit'], page['offset']), (5, 20, 0))
        outputs = [self.output(self.run), self.output(gps_run)]
        expected = [x for output in outputs for x in json.loads(output['entities_json'])]
        self.assertEqual(page['items'], sorted(expected, key=lambda x: (x['candidate_key'], x['id'])))
        sources = (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()['items']
        by_id = {x['id']: x for x in sources}
        for entity in page['items']:
            self.assertEqual(entity['case_id'], self.case)
            self.assertEqual(entity['confidence'], 0)
            self.assertEqual(set(entity['evidence_ids']), {by_id[oid]['evidence_id'] for oid in entity['observation_ids']})
            self.assertTrue(all(by_id[oid]['source_locator'] for oid in entity['observation_ids']))
            self.assertTrue(all(by_id[oid]['entity_key'] == entity['candidate_key'] for oid in entity['observation_ids']))
        entity_ids = {x['id'] for x in page['items']}
        for output in outputs:
            for event in json.loads(output['events_json']):
                self.assertTrue(set(event['entity_ids']) <= entity_ids)
        self.assertTrue({'device:D-7', 'device:D-8', 'device:D-9'} <= {x['candidate_key'] for x in page['items']})

    async def test_identical_keys_from_distinct_evidence_remain_distinct_records_without_boost(self):
        second = await self.upload(); second_run = await self.process(second)
        page = await self.page()
        self.assertEqual(page['total'], 8)
        devices = [x for x in page['items'] if x['candidate_key'] == 'device:D-7']
        self.assertEqual(len(devices), 2)
        self.assertNotEqual(devices[0]['id'], devices[1]['id'])
        self.assertEqual({x['evidence_ids'][0] for x in devices}, {self.evidence['id'], second['id']})
        self.assertTrue(all(x['confidence'] == 0 for x in devices))
        self.assertEqual(devices, sorted(devices, key=lambda x: x['id']))
        expected = json.loads(self.output(self.run)['entities_json']) + json.loads(self.output(second_run)['entities_json'])
        self.assertEqual(page['items'], sorted(expected, key=lambda x: (x['candidate_key'], x['id'])))

    async def test_latest_per_evidence_new_ids_failed_retry_and_old_history_retained(self):
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        old_output = self.output(self.run)
        old_ids = {x['id'] for x in json.loads(old_output['entities_json'])}
        fresh = await self.process(self.evidence)
        page = await self.page()
        fresh_ids = {x['id'] for x in json.loads(self.output(fresh)['entities_json'])}
        gps_ids = {x['id'] for x in json.loads(self.output(gps_run)['entities_json'])}
        self.assertEqual({x['id'] for x in page['items']}, fresh_ids | gps_ids)
        self.assertTrue(old_ids.isdisjoint(fresh_ids))
        with patch('backend.processing.publish_outputs', side_effect=RuntimeError('Synthetic publication failure')):
            await self.process(self.evidence)
        self.assertEqual(await self.page(), page)
        self.assertEqual(self.output(self.run), old_output)

    async def test_pending_running_failed_partial_output_never_visible(self):
        before = await self.page()
        with patch('backend.processing.process_run'):
            queued = await self.process(self.evidence)
            running = await self.process(self.evidence)
            failed = await self.process(self.evidence)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running['id'],))
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (running['id'], self.case, self.evidence['id'], 'SECRET partial JSON', 'SECRET partial entities', '[]', '[]'))
            connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='SYNTHETIC_FAILURE' WHERE id=?",
                               ('2099-01-12T00:00:00Z', failed['id']))
        self.assertEqual(await self.page(), before)

    async def test_full_pagination_totals_order_and_huge_offsets(self):
        data = b'timestamp,device_id,ip_address,event\n' + b''.join(
            f'2026-01-12T10:00:00Z,D-{index:03d},198.51.100.{index+1},connected\n'.encode() for index in range(12))
        evidence = await self.upload(data=data); run = await self.process(evidence)
        expected = json.loads(self.output(self.run)['entities_json']) + json.loads(self.output(run)['entities_json'])
        expected.sort(key=lambda x: (x['candidate_key'], x['id']))
        self.assertEqual(len(expected), 28)
        seen = []
        for offset in range(0, 28, 7):
            page = await self.page(limit=7, offset=offset)
            self.assertEqual((page['total'], page['limit'], page['offset']), (28, 7, offset))
            seen.extend(page['items'])
        self.assertEqual(seen, expected)
        self.assertEqual(len({x['id'] for x in seen}), 28)
        self.assertEqual(len((await self.page())['items']), 20)
        self.assertEqual((await self.page(limit=100))['items'], expected)
        for offset in [28, 100, 10 ** 100]:
            page = await self.page(offset=offset)
            self.assertEqual((page['items'], page['total'], page['offset']), ([], 28, offset))

    async def test_empty_unprocessed_and_selected_empty_latest_no_older_fallback(self):
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic empty'})).json()['id']
        await self.upload('document', case=case)
        response = await self.client.get(f'/api/v1/cases/{case}/entities')
        self.assertEqual(response.json(), {'items': [], 'total': 0, 'limit': 20, 'offset': 0})
        empty = await self.upload(data=b'timestamp,device_id,ip_address,event\n'); await self.process(empty)
        self.assertEqual((await self.page())['total'], 4)
        self.fixture('2099-01-12T00:00:00Z', 100, [], [])
        self.assertEqual((await self.page())['total'], 0)
        old_observations = await self.client.get(f'/api/v1/cases/{self.case}/observations', params={'processing_run_id': self.run['id']})
        self.assertEqual(old_observations.json()['total'], 6)

    async def test_foreign_case_auth_revocation_and_no_cross_case_source_leak(self):
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic other'})).json()['id']
        evidence = await self.upload(case=case); run = await self.process(evidence)
        foreign_ids = {x['id'] for x in json.loads(self.output(run)['entities_json'])}
        self.assertTrue(foreign_ids.isdisjoint(x['id'] for x in (await self.page())['items']))
        for headers, expected in [({}, 401), ({'Authorization': 'invalid'}, 401),
                                 ({'Authorization': 'Bearer p05-synthetic-two'}, 404),
                                 ([('Authorization', 'Bearer p05-synthetic-one')] * 2, 401)]:
            async with AsyncClient(transport=ASGITransport(self.app), base_url='http://test') as client:
                response = await client.get(self.url, headers=headers)
                self.assertEqual(response.status_code, expected)
                self.validate('ApiError', response.json())
        self.assertEqual((await self.client.get(self.url.replace(self.case, str(uuid4())))).status_code, 404)
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)

    async def test_bad_query_limits_duplicates_and_unsupported_selectors_safe_400(self):
        for params in [{'limit': 0}, {'limit': 101}, {'limit': -1}, {'limit': 'SECRET'}, {'offset': -1},
                       {'offset': 'SECRET'}, {'evidence_id': self.evidence['id']}, {'processing_run_id': self.run['id']},
                       {'analysis_run_id': str(uuid4())}, [('limit', '1'), ('limit', '2')]]:
            response = await self.client.get(self.url, params=params)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('SECRET', response.text)
            self.validate('ApiError', response.json())
        self.assertEqual((await self.client.get(self.url.replace(self.case, 'SECRET'))).status_code, 400)

    async def test_corrupt_entity_shape_uuid_context_score_keys_and_refs_fail_whole_read(self):
        original = json.loads(self.output(self.run)['entities_json'])
        item = original[0]
        bad = ['SECRET not JSON', '{}', '["SECRET"]', json.dumps(original + [item])]
        for changes in [dict(id='SECRET'), dict(case_id=str(uuid4())), dict(confidence=2), dict(confidence=True),
                        dict(evidence_ids=[]), dict(observation_ids=[]), dict(observation_ids=item['observation_ids'] * 2),
                        dict(evidence_ids=item['evidence_ids'] * 2), dict(observation_ids=[str(uuid4())]),
                        dict(evidence_ids=[str(uuid4())]), dict(evidence_ids=item['evidence_ids'] + [str(uuid4())]),
                        dict(candidate_key='SECRET'), dict(canonical_label={}), dict(private_SECRET='not public')]:
            bad.append(json.dumps([dict(item, **changes)]))
        self.allow_output_corruption()
        for value in bad:
            with self.app.state.database.connect() as connection:
                connection.execute('UPDATE processing_outputs SET entities_json=? WHERE run_id=?', (value, self.run['id']))
            response = await self.client.get(self.url)
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn('SECRET', response.text)

    async def test_foreign_and_stale_observation_refs_fail_without_exposing_old_or_other_case(self):
        old = json.loads(self.output(self.run)['entities_json'])
        fresh = await self.process(self.evidence)
        fresh_entities = json.loads(self.output(fresh)['entities_json'])
        self.allow_output_corruption()
        corrupted = dict(fresh_entities[0], observation_ids=old[0]['observation_ids'])
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_outputs SET entities_json=? WHERE run_id=?', (json.dumps([corrupted]), fresh['id']))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic foreign source'})).json()['id']
        foreign_evidence = await self.upload(case=case); foreign_run = await self.process(foreign_evidence)
        foreign_obs = json.loads(self.output(foreign_run)['observations_json'])[0]['id']
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_outputs SET entities_json=? WHERE run_id=?',
                (json.dumps([dict(fresh_entities[0], observation_ids=[foreign_obs])]), fresh['id']))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)

    async def test_corrupt_source_observations_and_output_metadata_fail_closed(self):
        original = self.output(self.run)
        observations = json.loads(original['observations_json'])
        self.allow_output_corruption()
        for value in ['SECRET malformed observations', '{}', json.dumps([dict(observations[0], case_id=str(uuid4()))]),
                      json.dumps([dict(observations[0], source_locator='')]), json.dumps(observations + [observations[0]])]:
            with self.app.state.database.connect() as connection:
                connection.execute('UPDATE processing_outputs SET observations_json=? WHERE run_id=?', (value, self.run['id']))
            self.assertEqual((await self.client.get(self.url)).status_code, 404)
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_outputs SET observations_json=?,case_id=? WHERE run_id=?',
                               (original['observations_json'], str(uuid4()), self.run['id']))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)

    async def test_missing_latest_output_does_not_fall_back_and_duplicate_entity_ids_fail(self):
        fresh = await self.process(self.evidence)
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_delete')
            connection.execute('DELETE FROM processing_outputs WHERE run_id=?', (fresh['id'],))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)
        # An actual new-key retry restores latest selected output; old immutable output survives.
        newer = await self.process(self.evidence)
        other = await self.upload(); other_run = await self.process(other)
        entities = json.loads(self.output(other_run)['entities_json'])
        entities[0]['id'] = json.loads(self.output(newer)['entities_json'])[0]['id']
        self.allow_output_corruption()
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_outputs SET entities_json=? WHERE run_id=?', (json.dumps(entities), other_run['id']))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)

    async def test_exact_completion_time_fraction_offset_and_uuid_selection(self):
        self.fixture('2099-01-12T10:00:00.0000000001Z', 900)
        later = self.fixture('2099-01-12T10:00:00.0000000002Z', 1)
        self.assertEqual((await self.page())['items'], sorted(later, key=lambda x: (x['candidate_key'], x['id'])))
        self.fixture('2099-01-12T16:30:00.100000+05:30', 2)
        tied_high = self.fixture('2099-01-12T11:00:00.1Z', 901)
        self.assertEqual((await self.page())['items'], sorted(tied_high, key=lambda x: (x['candidate_key'], x['id'])))
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_run_terminal')
            connection.execute("UPDATE processing_runs SET finished_at='SECRET' WHERE id=?", (str(UUID(int=901)),))
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('SECRET', response.text)

    async def test_generic_wire_fixture_keeps_kind_label_score_without_invented_key_requirement(self):
        output = self.output(self.run)
        observation = json.loads(output['observations_json'])[0]
        entity = json.loads(output['entities_json'])[0]
        # Schema-only future-adapter compatibility; not a document/account extraction claim.
        observation = dict(observation, kind='text.mention', raw_value='Synthetic candidate', normalized_value='Synthetic candidate')
        observation.pop('entity_key', None)
        entity = dict(entity, kind='account', candidate_key='account:synthetic', canonical_label='<b>Synthetic candidate</b>',
                      confidence=0.25, observation_ids=[observation['id']])
        expected = self.fixture('2099-01-12T00:00:00Z', 4, [observation], [entity])
        page = await self.page()
        self.assertEqual(page['items'], expected)
        self.validate('EntityPage', page)

    async def test_single_read_snapshot_is_coherent_during_actual_publication(self):
        old = await self.page()
        with patch('backend.processing.process_run'):
            queued = await self.process(self.evidence)
        entered = threading.Event()
        def publish():
            entered.set(); process_run(self.app, queued['id'])
        thread = threading.Thread(target=publish)
        def during_page(connection, case_id, limit, offset):
            thread.start(); self.assertTrue(entered.wait(5)); time.sleep(0.1)
            return _page(connection, case_id, limit, offset)
        try:
            with patch('backend.entities._page', side_effect=during_page):
                observed = await self.page()
        finally:
            if thread.ident is not None: await asyncio.to_thread(thread.join, 10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, old)
        new = await self.page()
        self.assertTrue({x['id'] for x in old['items']}.isdisjoint(x['id'] for x in new['items']))
        self.assertEqual(new['total'], 4)

    async def test_repeated_reads_do_not_mutate_history_originals_audit_or_schedule_processing(self):
        def snapshot():
            with self.app.state.database.connect() as connection:
                return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')]
                        for table in ('processing_runs', 'processing_outputs', 'evidence', 'audit_events')}
        before = snapshot()
        with patch('backend.processing.process_run') as job:
            first = await self.page(); self.assertEqual(await self.page(), first); await self.page(offset=10 ** 100)
        job.assert_not_called()
        self.assertEqual(snapshot(), before)
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content, (ROOT/'fixtures/synthetic-case/network.csv').read_bytes())


class EntityLoopbackTests(unittest.TestCase):
    def test_real_http_processing_entity_pages_citations_duplicate_keys_and_failed_input(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:
                listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; p=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                    'SyntheticTokenVerifier({"p05-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([sys.executable, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p05-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P05 HTTP'}).json()['id']
                    for index, (kind, name) in enumerate([('network_log', 'network.csv'), ('gps', 'gps.csv'),
                                                        ('network_log', 'network.csv'), ('network_log', None)]):
                        data = (ROOT/'fixtures/synthetic-case'/name).read_bytes() if name else b'bad header\n'
                        evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': kind, 'source_label': 'Synthetic HTTP'},
                            files={'file': ('source.csv', data, 'text/csv')}).json()
                        run_url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted = client.post(run_url, headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(accepted.status_code, 202)
                        for _ in range(100):
                            status = client.get(run_url + '/' + accepted.json()['id']).json()['status']
                            if status in ('completed', 'failed'): break
                            time.sleep(0.05)
                        self.assertEqual(status, 'completed' if name else 'failed')
                        response = client.get(f'/api/v1/cases/{case}/entities')
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['total'], [4, 5, 9, 9][index])
                    url = f'/api/v1/cases/{case}/entities'
                    page = client.get(url, params={'limit': 2, 'offset': 2}).json()
                    self.assertEqual((len(page['items']), page['total'], page['offset']), (2, 9, 2))
                    entities = client.get(url).json()['items']
                    observations = client.get(f'/api/v1/cases/{case}/observations').json()['items']
                    sources = {x['id']: x for x in observations}
                    for entity in entities:
                        self.assertEqual(set(entity['evidence_ids']), {sources[oid]['evidence_id'] for oid in entity['observation_ids']})
                    self.assertEqual(len([x for x in entities if x['candidate_key'] == 'device:D-7']), 2)
                    self.assertEqual(client.get(url, params={'processing_run_id': str(uuid4())}).status_code, 400)
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
