"""P04B real processing/output reads; labeled metadata/corruption/race fixtures."""
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
from backend.observations import _page
from backend.processing import process_run

ROOT = Path(__file__).resolve().parents[2]


class ObservationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p04b-synthetic-one': 'investigator-1', 'p04b-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p04b-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P04B case'})).json()['id']
        self.url = f'/api/v1/cases/{self.case}/observations'
        self.network = await self.upload()
        self.run = await self.process(self.network)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    async def upload(self, kind='network_log', data=None, case=None):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / ('gps.csv' if kind == 'gps' else 'network.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence', data={'kind': kind, 'source_label': 'Synthetic P04B'},
            files={'file': ('source.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201)
        return response.json()

    async def process(self, evidence, key=None):
        response = await self.client.post(f"/api/v1/cases/{evidence['case_id']}/evidence/{evidence['id']}/processing-runs",
                                          headers={'Idempotency-Key': key or str(uuid4())})
        self.assertEqual(response.status_code, 202)
        return response.json()

    def output(self, run):
        with self.app.state.database.connect() as connection:
            return dict(connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone())

    async def page(self, **params):
        response = await self.client.get(self.url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def validate(self, name, value):
        Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': self.bundle['components']},
                             format_checker=FormatChecker()).validate(value)

    def completed_fixture(self, finished_at, integer_id, observations=None):
        """Selection-only SQL fixture over real source values, not a processor double."""
        run_id = str(UUID(int=integer_id))
        original = self.output(self.run)
        observations = observations if observations is not None else json.loads(original['observations_json'])
        values = [dict(value, id=str(uuid4()), processing_run_id=run_id) for value in observations]
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
                'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run_id, self.case, self.network['id'], 'investigator-1', str(uuid4()), 'synthetic-fixture', '{}',
                 'P04B-selection-fixture/1', '2099-01-01T00:00:00Z', 'queued'))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (run_id, self.case, self.network['id'], json.dumps(values), '[]', '[]', '[]'))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (finished_at, run_id))
        return run_id, values

    async def test_real_network_gps_schema_and_exact_stored_wire_source_readback(self):
        gps = await self.upload('gps', b'timestamp,device_id,latitude,longitude\n2026-01-12T15:32:00.123456789+05:30,D-8,+12.9716000,7.75946e1\n')
        gps_run = await self.process(gps)
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        page = response.json()
        self.validate('ObservationPage', page)
        self.assertEqual((page['total'], page['limit'], page['offset']), (9, 20, 0))
        expected = json.loads(self.output(self.run)['observations_json']) + json.loads(self.output(gps_run)['observations_json'])
        self.assertEqual(page['items'], sorted(expected, key=lambda x: (x['evidence_id'], x['id'])))
        latitude = next(x for x in page['items'] if x['kind'] == 'gps.latitude')
        self.assertEqual(latitude['raw_value'], '+12.9716000')
        self.assertEqual(latitude['normalized_value'], '12.9716')
        self.assertEqual(latitude['observed_at_utc'], '2026-01-12T10:02:00.123456789Z')
        for item in page['items']:
            self.assertEqual(item['case_id'], self.case)
            self.assertTrue(item['source_locator'])
            for private in ['config_json', 'uncertainty_json', 'time', 'status', 'actor_id']:
                self.assertNotIn(private, item)

    async def test_latest_per_evidence_and_exact_historical_filters(self):
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        old = await self.page(processing_run_id=self.run['id'])
        fresh = await self.process(self.network)
        latest = await self.page()
        self.assertEqual({x['processing_run_id'] for x in latest['items']}, {fresh['id'], gps_run['id']})
        # Actual supported input/pipeline with a publication fault: latest completed must survive a failed retry.
        with patch('backend.processing.publish_outputs', side_effect=RuntimeError('Synthetic publication failure')):
            await self.process(self.network)
        self.assertEqual(await self.page(), latest)
        self.assertEqual(await self.page(processing_run_id=self.run['id']), old)
        self.assertEqual(await self.page(evidence_id=self.network['id'], processing_run_id=self.run['id']), old)
        self.assertEqual((await self.page(evidence_id=self.network['id']))['total'], 6)
        self.assertEqual((await self.page(processing_run_id=gps_run['id']))['total'], 3)

    async def test_pending_running_failed_outputs_hidden_and_prior_completed_remains(self):
        # Scheduler gate only; actual persisted pending/running rows and partial SQL output are inspected.
        with patch('backend.processing.process_run'):
            queued = await self.process(self.network)
            running = await self.process(self.network)
            failed = await self.process(self.network)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running['id'],))
            partial = json.loads(self.output(self.run)['observations_json'])
            partial = [dict(x, processing_run_id=running['id']) for x in partial]
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (running['id'], self.case, self.network['id'], json.dumps(partial), '[]', '[]', '[]'))
            connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='SYNTHETIC_FAILURE' WHERE id=?",
                ('2099-01-12T00:00:00Z', failed['id']))
        self.assertEqual({x['processing_run_id'] for x in (await self.page())['items']}, {self.run['id']})
        for run in [queued, running, failed]:
            response = await self.client.get(self.url, params={'processing_run_id': run['id']})
            self.assertEqual(response.status_code, 404)

    async def test_pagination_totals_boundaries_huge_offset_and_no_duplicates(self):
        rows = b'timestamp,device_id,ip_address,event\n' + b'2026-01-12T10:00:00Z,D-7,203.0.113.7,connected\n' * 9
        evidence = await self.upload(data=rows); run = await self.process(evidence)
        combined = []
        for offset in range(0, 28, 7):
            page = await self.page(evidence_id=evidence['id'], limit=7, offset=offset)
            self.assertEqual((page['total'], page['limit'], page['offset']), (27, 7, offset))
            combined.extend(page['items'])
        self.assertEqual(len(combined), 27)
        self.assertEqual(len({x['id'] for x in combined}), 27)
        self.assertEqual(combined, sorted(json.loads(self.output(run)['observations_json']), key=lambda x: x['id']))
        for offset in [27, 100, 10 ** 100]:
            page = await self.page(evidence_id=evidence['id'], offset=offset)
            self.assertEqual(page['items'], [])
            self.assertEqual((page['total'], page['offset']), (27, offset))
        self.assertEqual(len((await self.page(evidence_id=evidence['id']))['items']), 20)
        self.assertEqual(len((await self.page(evidence_id=evidence['id'], limit=100))['items']), 27)

    async def test_pinned_pages_unchanged_across_new_completion(self):
        stored_before = self.output(self.run)
        old = await self.page(processing_run_id=self.run['id'], limit=100)
        first = await self.page(processing_run_id=self.run['id'], limit=2)
        await self.process(self.network)
        rest = await self.page(processing_run_id=self.run['id'], limit=100, offset=2)
        self.assertEqual(first['items'] + rest['items'], old['items'])
        self.assertTrue(all(x['processing_run_id'] == self.run['id'] for x in old['items']))
        self.assertEqual(self.output(self.run), stored_before)

    async def test_empty_unprocessed_header_only_and_no_completed_case(self):
        unprocessed = await self.upload('document')
        self.assertEqual((await self.page(evidence_id=unprocessed['id']))['total'], 0)
        empty = await self.upload(data=b'timestamp,device_id,ip_address,event\n')
        run = await self.process(empty)
        for params in [{'evidence_id': empty['id']}, {'processing_run_id': run['id']}]:
            self.assertEqual((await self.page(**params))['items'], [])
        # A selected empty completed output replaces older nonempty output; it must not fall back.
        self.completed_fixture('2099-01-12T00:00:00Z', 1234, [])
        self.assertEqual((await self.page(evidence_id=self.network['id']))['total'], 0)
        self.assertEqual((await self.page(processing_run_id=self.run['id']))['total'], 6)
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic empty case'})).json()['id']
        response = await self.client.get(f'/api/v1/cases/{case}/observations')
        self.assertEqual(response.json(), {'items': [], 'total': 0, 'limit': 20, 'offset': 0})

    async def test_auth_foreign_missing_mismatched_and_revoked_filters_same_safe_errors(self):
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic second'})).json()['id']
        foreign = await self.upload(case=other_case); foreign_run = await self.process(foreign)
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        invalid = [{'evidence_id': str(uuid4())}, {'evidence_id': foreign['id']}, {'processing_run_id': str(uuid4())},
                   {'processing_run_id': foreign_run['id']}, {'evidence_id': gps['id'], 'processing_run_id': self.run['id']},
                   {'evidence_id': self.network['id'], 'processing_run_id': gps_run['id']}]
        bodies = []
        for params in invalid:
            response = await self.client.get(self.url, params=params)
            self.assertEqual(response.status_code, 404)
            bodies.append(response.json())
        self.assertTrue(all(body == bodies[0] for body in bodies))
        for headers, expected in [({}, 401), ({'Authorization': 'invalid'}, 401),
                                  ({'Authorization': 'Bearer p04b-synthetic-two'}, 404),
                                  ([('Authorization', 'Bearer p04b-synthetic-one')] * 2, 401)]:
            async with AsyncClient(transport=ASGITransport(self.app), base_url='http://test') as client:
                self.assertEqual((await client.get(self.url, headers=headers)).status_code, expected)
        self.assertEqual((await self.client.get(self.url.replace(self.case, str(uuid4())))).status_code, 404)
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.assertEqual((await self.client.get(self.url, params={'processing_run_id': self.run['id']})).status_code, 404)

    async def test_invalid_query_path_duplicate_unknown_and_pagination_safe_400(self):
        for params in [{'evidence_id': 'SECRET'}, {'processing_run_id': 'SECRET'}, {'limit': 0}, {'limit': 101},
                       {'limit': -1}, {'limit': 'SECRET'}, {'offset': -1}, {'offset': 'SECRET'}, {'SECRET': 'value'},
                       [('limit', '1'), ('limit', '2')], [('evidence_id', self.network['id'])] * 2]:
            response = await self.client.get(self.url, params=params)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('SECRET', response.text)
            self.validate('ApiError', response.json())
        self.assertEqual((await self.client.get(self.url.replace(self.case, 'SECRET'))).status_code, 400)

    async def test_exact_fraction_utc_offset_equivalence_and_uuid_tiebreak(self):
        # Controlled terminal metadata fixtures are needed to test equal/near-equal completion instants.
        early, _ = self.completed_fixture('2099-01-12T10:00:00.0000000001Z', 900)
        late, _ = self.completed_fixture('2099-01-12T10:00:00.0000000002Z', 1)
        self.assertEqual({x['processing_run_id'] for x in (await self.page())['items']}, {late})
        low, _ = self.completed_fixture('2099-01-12T16:30:00.100000+05:30', 2)
        high, _ = self.completed_fixture('2099-01-12T11:00:00.1Z', 901)
        self.assertEqual({x['processing_run_id'] for x in (await self.page())['items']}, {high})
        zero, _ = self.completed_fixture('2099-01-12T12:00:00Z', 902)
        fraction, _ = self.completed_fixture('2099-01-12T12:00:00.000001Z', 3)
        self.assertEqual({x['processing_run_id'] for x in (await self.page())['items']}, {fraction})
        self.assertEqual((await self.page(processing_run_id=early))['total'], 6)

    async def test_corrupt_selected_output_fails_whole_page_without_content_leak(self):
        gps = await self.upload('gps'); await self.process(gps)
        original = json.loads(self.output(self.run)['observations_json'])
        corrupt = ['SECRET not JSON', '{}', '["SECRET"]', json.dumps(original + [original[0]]),
                   json.dumps([dict(original[0], id='SECRET')]),
                   json.dumps([dict(original[0], case_id=str(uuid4()))]),
                   json.dumps([dict(original[0], evidence_id=str(uuid4()))]),
                   json.dumps([dict(original[0], processing_run_id=str(uuid4()))]),
                   json.dumps([dict(original[0], private_SECRET='not public')]),
                   json.dumps([dict(original[0], extraction_confidence=2)]),
                   json.dumps([dict(original[0], extraction_confidence=True)]),
                   json.dumps([dict(original[0], entity_key=None)]),
                   json.dumps([dict(original[0], observed_at_utc='SECRET')]),
                   json.dumps([dict(original[0], observed_at_utc='0')]),
                   json.dumps([dict(original[0], transcript_revision_id=str(uuid4()))]),
                   json.dumps([dict(original[0], source_observation_id=str(uuid4()))]),
                   json.dumps([dict(original[0], kind='transcript.segment', source_locator='SECRET')]),
                   json.dumps([dict(original[0], kind='transcript.status', normalized_value='SECRET')])]
        # Test-only corruption bypass, never application migration/behavior.
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_update')
        for value in corrupt:
            with self.app.state.database.connect() as connection:
                connection.execute('UPDATE processing_outputs SET observations_json=? WHERE run_id=?', (value, self.run['id']))
            response = await self.client.get(self.url)
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn('SECRET', response.text)
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_outputs SET observations_json=?,case_id=? WHERE run_id=?',
                               (json.dumps(original), str(uuid4()), self.run['id']))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)

    async def test_missing_latest_output_no_silent_fallback_but_old_pin_stays_valid(self):
        old = await self.page(processing_run_id=self.run['id'])
        fresh = await self.process(self.network)
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_delete')
            connection.execute('DELETE FROM processing_outputs WHERE run_id=?', (fresh['id'],))
        self.assertEqual((await self.client.get(self.url)).status_code, 404)
        self.assertEqual(await self.page(processing_run_id=self.run['id']), old)

    async def test_invalid_selected_completion_time_fails_closed(self):
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_run_terminal')
            connection.execute("UPDATE processing_runs SET finished_at='SECRET' WHERE id=?", (self.run['id'],))
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('SECRET', response.text)

    async def test_existing_transcript_wire_compatibility_is_schema_fixture_not_transcription(self):
        item = dict(id=str(uuid4()), case_id=self.case, evidence_id=self.network['id'], processing_run_id=self.run['id'],
            kind='transcript.segment', source_locator='media:start_ms=0;end_ms=1000', raw_value='Synthetic machine text',
            normalized_value='Synthetic corrected text', extraction_confidence=0, source_observation_id=str(uuid4()),
            transcript_revision_id=str(uuid4()))
        run_id, values = self.completed_fixture('2099-01-12T00:00:00Z', 4, [item])
        self.validate('Observation', values[0])
        page = await self.page(processing_run_id=run_id)
        self.assertEqual(page['items'], values)
        self.assertNotIn('observed_at_utc', page['items'][0])
        self.validate('ObservationPage', page)

    async def test_read_snapshot_stays_coherent_during_real_publication_attempt(self):
        old = await self.page()
        with patch('backend.processing.process_run'):
            queued = await self.process(self.network)
        entered = threading.Event()
        def publish():
            entered.set(); process_run(self.app, queued['id'])
        thread = threading.Thread(target=publish)
        def during_page(connection, parameters, limit, offset):
            thread.start()
            self.assertTrue(entered.wait(5))
            # Scheduling delay lets the real writer attempt its transaction while this read snapshot is held.
            time.sleep(0.1)
            return _page(connection, parameters, limit, offset)
        try:
            with patch('backend.observations._page', side_effect=during_page):
                observed = await self.page()
        finally:
            if thread.ident is not None:
                await asyncio.to_thread(thread.join, 10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, old)
        newer = await self.page()
        self.assertEqual({x['processing_run_id'] for x in newer['items']}, {queued['id']})

    async def test_repeated_reads_do_not_mutate_outputs_runs_originals_or_schedule_jobs(self):
        def snapshot():
            with self.app.state.database.connect() as connection:
                return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')]
                        for table in ('processing_runs', 'processing_outputs', 'evidence', 'audit_events')}
        before = snapshot()
        with patch('backend.processing.process_run') as job:
            await self.page(); await self.page(processing_run_id=self.run['id']); await self.page(offset=10 ** 100)
        job.assert_not_called()
        self.assertEqual(snapshot(), before)
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.network['id']}/content")
        self.assertEqual(original.content, (ROOT / 'fixtures/synthetic-case/network.csv').read_bytes())


class ObservationLoopbackTests(unittest.TestCase):
    def test_real_http_process_then_default_filtered_pinned_pages_and_failure_selector(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:
                listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; p=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                    'SyntheticTokenVerifier({"p04b-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([sys.executable, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p04b-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P04B HTTP'}).json()['id']
                    runs = []
                    for kind, name in [('network_log', 'network.csv'), ('gps', 'gps.csv'), ('network_log', None)]:
                        data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes() if name else b'bad header\n'
                        evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': kind, 'source_label': 'Synthetic HTTP'},
                            files={'file': ('source.csv', data, 'text/csv')}).json()
                        url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted = client.post(url, headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(accepted.status_code, 202)
                        run = accepted.json()
                        for _ in range(100):
                            status = client.get(url + '/' + run['id']).json()['status']
                            if status in ('completed', 'failed'): break
                            time.sleep(0.05)
                        self.assertEqual(status, 'completed' if name else 'failed')
                        runs.append((evidence, run))
                    url = f'/api/v1/cases/{case}/observations'
                    response = client.get(url)
                    self.assertEqual(response.status_code, 200, response.text)
                    page = response.json()
                    self.assertEqual(page['total'], 9)
                    filtered = client.get(url, params={'evidence_id': runs[0][0]['id'], 'limit': 2, 'offset': 2}).json()
                    self.assertEqual((len(filtered['items']), filtered['total'], filtered['offset']), (2, 6, 2))
                    pinned = client.get(url, params={'processing_run_id': runs[1][1]['id']}).json()
                    self.assertEqual(pinned['total'], 3)
                    self.assertEqual(client.get(url, params={'processing_run_id': runs[2][1]['id']}).status_code, 404)
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
