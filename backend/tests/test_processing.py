"""P04 real HTTP/SQL/original pipeline; labeled scheduling and failure injections."""
import asyncio
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.processing import process_run, publish_outputs, run_job
from backend.parsers.network_csv import parse_network_csv
from backend.processing_dispatch import adapter_for

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p04-synthetic-one': 'investigator-1', 'p04-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p04-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P04 case'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.case, self.evidence['id'])
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    def base(self, case, evidence):
        return f'/api/v1/cases/{case}/evidence/{evidence}/processing-runs'

    async def upload(self, kind='network_log', data=None, case=None):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / ('gps.csv' if kind == 'gps' else 'network.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence',
            data={'kind': kind, 'source_label': 'Synthetic P04'}, files={'file': ('source.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201)
        return response.json()

    async def start(self, key='synthetic-key', url=None, **kwargs):
        response = await self.client.post(url or self.url, headers={'Idempotency-Key': key}, **kwargs)
        return response

    async def poll(self, run, url=None):
        response = await self.client.get((url or self.url) + '/' + run['id'])
        self.assertEqual(response.status_code, 200)
        return response.json()

    def rows(self, table):
        with self.app.state.database.connect() as connection:
            return [dict(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')]

    def validate(self, name, value):
        Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': self.bundle['components']},
                             format_checker=FormatChecker()).validate(value)

    async def test_actual_network_and_gps_complete_with_immutable_source_joined_outputs(self):
        gps = await self.upload('gps')
        original_rows = self.rows('evidence')
        for evidence, count in [(self.evidence, 6), (gps, 3)]:
            url = self.base(self.case, evidence['id'])
            response = await self.start(evidence['id'], url)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            accepted = response.json()
            self.assertEqual(accepted['status'], 'queued')
            self.assertNotIn('finished_at', accepted)
            self.validate('ProcessingRun', accepted)
            complete = await self.poll(accepted, url)
            self.assertEqual(complete['status'], 'completed')
            self.assertIn('finished_at', complete)
            self.assertNotIn('error', complete)
            self.validate('ProcessingRun', complete)
            stored = next(x for x in self.rows('processing_outputs') if x['run_id'] == accepted['id'])
            observations, entities, events = [json.loads(stored[field]) for field in ('observations_json', 'entities_json', 'events_json')]
            self.assertEqual(len(observations), count)
            self.assertEqual(len(events), count // 3)
            by_id = {x['id']: x for x in observations}
            for observation in observations:
                self.validate('Observation', observation)
                self.assertEqual(observation['processing_run_id'], accepted['id'])
                self.assertEqual(observation['case_id'], self.case)
                self.assertEqual(observation['evidence_id'], evidence['id'])
            for entity in entities:
                self.validate('Entity', entity)
                self.assertTrue(set(entity['observation_ids']) <= set(by_id))
            for event in events:
                self.validate('Event', event)
                self.assertTrue(set(event['observation_ids']) <= set(by_id))
                self.assertTrue(set(event['entity_ids']) <= {x['id'] for x in entities})
            self.assertEqual(len(json.loads(stored['uncertainty_json'])), count)
            listed = await self.client.get(url)
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json(), [complete])
            original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/content")
            self.assertEqual(hashlib.sha256(original.content).hexdigest(), evidence['sha256'])
        self.assertEqual(self.rows('evidence'), original_rows)

    async def test_replay_before_current_snapshot_and_new_key_preserves_completed_history(self):
        accepted = (await self.start()).json()
        original = await self.poll(accepted)
        before = self.rows('processing_outputs')
        # Mutable server state is deliberately corrupted; original-key replay must not resnapshot/read it.
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE evidence SET kind='audio',sha256=? WHERE id=?", ('0' * 64, self.evidence['id']))
        with patch('backend.processing.process_run') as job:
            replay = await self.start()
        self.assertEqual(replay.json(), original)
        job.assert_not_called()
        self.assertEqual((await self.start('new-key')).status_code, 415)
        self.assertEqual(self.rows('processing_outputs'), before)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE evidence SET kind='network_log',sha256=? WHERE id=?", (self.evidence['sha256'], self.evidence['id']))
        fresh = (await self.start('new-key')).json()
        self.assertNotEqual(fresh['id'], original['id'])
        self.assertEqual((await self.poll(fresh))['status'], 'completed')
        self.assertEqual(next(x for x in self.rows('processing_outputs') if x['run_id'] == original['id']), before[0])

    async def test_frozen_configuration_and_public_wire_privacy(self):
        accepted = (await self.start('p04-private-synthetic-key')).json()
        row = self.rows('processing_runs')[0]
        config = json.loads(row['config_json'])
        self.assertEqual(config['sha256'], self.evidence['sha256'])
        self.assertEqual(config['size_bytes'], self.evidence['size_bytes'])
        self.assertEqual(config['parser_version'], 'network-csv/1')
        self.assertEqual(config['normalizer_version'], 'source-normalization/1')
        self.assertEqual(config['entity_version'], 'candidate-identifiers/1')
        self.assertEqual(config['event_version'], 'source-events/1')
        self.assertEqual(row['key_digest'], hashlib.sha256(b'p04-private-synthetic-key').hexdigest())
        for wire in [accepted, await self.poll(accepted)]:
            for private in ['actor_id', 'key_digest', 'fingerprint', 'config_json', 'sha256', 'observations_json']:
                self.assertNotIn(private, wire)
            self.assertNotIn('p04-private-synthetic-key', json.dumps(wire))

    async def test_malformed_supported_file_failed_replay_and_new_key_retry(self):
        malformed = await self.upload(data=b'timestamp,device_id,ip_address,event\n2026-01-12T10:01:00Z,D-7,SECRET,connected\n')
        url = self.base(self.case, malformed['id'])
        response = await self.start('failed-key', url)
        self.assertEqual(response.status_code, 202)
        failed = await self.poll(response.json(), url)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error'], 'CSV_INVALID_IP')
        self.validate('ProcessingRun', failed)
        self.assertNotIn('SECRET', json.dumps(failed))
        self.assertEqual(self.rows('processing_outputs'), [])
        with patch('backend.processing.process_run') as job:
            self.assertEqual((await self.start('failed-key', url)).json(), failed)
        job.assert_not_called()
        retry = (await self.start('retry', url)).json()
        self.assertNotEqual(retry['id'], failed['id'])
        self.assertEqual((await self.poll(retry, url))['status'], 'failed')

    async def test_unsupported_kind_has_no_run_or_consumed_key(self):
        unsupported = await self.upload('audio')
        url = self.base(self.case, unsupported['id'])
        response = await self.start('free-key', url)
        self.assertEqual(response.status_code, 415)
        self.validate('ApiError', response.json())
        self.assertEqual(self.rows('processing_runs'), [])
        self.assertEqual((await self.start('free-key')).status_code, 202)

    async def test_key_scope_same_target_replay_other_target_conflict_actor_case_isolation(self):
        original = (await self.start()).json()
        other = await self.upload('gps')
        conflict = await self.start(url=self.base(self.case, other['id']))
        self.assertEqual(conflict.status_code, 409)
        self.validate('ApiError', conflict.json())
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic second case'})).json()['id']
        evidence = await self.upload(case=other_case)
        self.assertEqual((await self.start(url=self.base(other_case, evidence['id']))).status_code, 202)
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO case_members VALUES (?,?)', (self.case, 'investigator-2'))
        response = await self.client.post(self.url, headers={'Authorization': 'Bearer p04-synthetic-two', 'Idempotency-Key': 'synthetic-key'})
        self.assertEqual(response.status_code, 202)
        self.assertNotEqual(response.json()['id'], original['id'])

    async def test_invalid_keys_body_queries_and_ids_are_safe_400_without_runs(self):
        for headers in [{}, {'Idempotency-Key': ''}, {'Idempotency-Key': 'x' * 129},
                        [('Idempotency-Key', 'one'), ('Idempotency-Key', 'two')]]:
            response = await self.client.post(self.url, headers=headers)
            self.assertEqual(response.status_code, 400)
            self.validate('ApiError', response.json())
        for kwargs in [{'content': b'{}'}, {'content': b' '}, {'json': {'SECRET': 'not allowed'}}, {'params': {'SECRET': 'not allowed'}}]:
            response = await self.start(**kwargs)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('SECRET', response.text)
        for path in [self.url.replace(self.case, 'SECRET'), self.url.replace(self.evidence['id'], 'SECRET')]:
            self.assertEqual((await self.start(url=path)).status_code, 400)
        self.assertEqual(self.rows('processing_runs'), [])
        # The exact schema permits 1–128 characters; no hidden trimming/shorter cap.
        self.assertEqual((await self.start('x' * 128)).status_code, 202)

    async def test_access_matrix_and_revocation_on_replay_and_all_reads(self):
        run = (await self.start()).json()
        for suffix, method in [('', 'POST'), ('', 'GET'), ('/' + run['id'], 'GET')]:
            for auth in ['Bearer p04-synthetic-two', 'invalid', None]:
                headers = {'Idempotency-Key': 'synthetic-key'}
                if auth is not None: headers['Authorization'] = auth
                # Separate client prevents default Authorization for the missing-token case.
                async with AsyncClient(transport=ASGITransport(self.app), base_url='http://test') as client:
                    response = await client.request(method, self.url + suffix, headers=headers)
                self.assertEqual(response.status_code, 404 if auth == 'Bearer p04-synthetic-two' else 401)
                self.validate('ApiError', response.json())
        before = self.rows('processing_runs')
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        for method, path in [('POST', self.url), ('GET', self.url), ('GET', self.url + '/' + run['id'])]:
            response = await self.client.request(method, path, headers={'Idempotency-Key': 'synthetic-key'})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.rows('processing_runs'), before)

    async def test_missing_foreign_and_mismatched_run_joins_same_404(self):
        run = (await self.start()).json()
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic other'})).json()['id']
        other = await self.upload(case=other_case)
        paths = [self.base(self.case, uuid4()), self.base(other_case, self.evidence['id'])]
        for path in paths:
            self.assertEqual((await self.client.get(path)).status_code, 404)
            self.assertEqual((await self.start('missing', path)).status_code, 404)
        missing = await self.client.get(self.url + '/' + str(uuid4()))
        mismatch = await self.client.get(self.base(other_case, other['id']) + '/' + run['id'])
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(mismatch.json(), missing.json())
        self.assertEqual((await self.client.get(self.url + '/SECRET')).status_code, 400)

    async def test_queued_running_completed_poll_and_no_job_on_get(self):
        jobs = []
        # Scheduling double only: hold actual job so queued/running can be observed.
        with patch('backend.processing.process_run', side_effect=lambda app, rid: jobs.append((app, rid))):
            run = (await self.start()).json()
            self.assertEqual((await self.poll(run))['status'], 'queued')
            self.assertEqual((await self.client.get(self.url)).json()[0]['status'], 'queued')
            self.assertEqual(len(jobs), 1)
            self.assertEqual((await self.start()).json()['id'], run['id'])
            self.assertEqual(len(jobs), 1)
        entered, release = threading.Event(), threading.Event()
        def gated_parser(*args, **kwargs):
            entered.set()
            if not release.wait(10): raise RuntimeError('test gate timed out')
            return parse_network_csv(*args, **kwargs)
        with patch('backend.processing.adapter_for', return_value=replace(adapter_for('network_log'), parse=gated_parser)):
            task = asyncio.create_task(asyncio.to_thread(process_run, *jobs[0]))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 10))
                self.assertEqual((await self.poll(run))['status'], 'running')
                self.assertEqual(self.rows('processing_outputs'), [])
            finally:
                release.set()
                await task
        self.assertEqual((await self.poll(run))['status'], 'completed')
        process_run(*jobs[0])
        self.assertEqual(len(self.rows('processing_outputs')), 1)

    async def test_concurrent_same_key_accepts_one_job_and_one_run(self):
        jobs = []
        with patch('backend.processing.process_run', side_effect=lambda app, rid: jobs.append((app, rid))):
            responses = await asyncio.gather(*(self.start('concurrent') for _ in range(6)))
        self.assertTrue(all(response.status_code == 202 for response in responses))
        self.assertEqual(len({response.json()['id'] for response in responses}), 1)
        self.assertEqual(len(jobs), 1)
        await asyncio.to_thread(process_run, *jobs[0])
        self.assertEqual(len(self.rows('processing_runs')), 1)
        self.assertEqual(len(self.rows('processing_outputs')), 1)

    async def test_local_background_jobs_serialize_without_blocking_event_loop(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def held_job(app, identifier):
            calls.append(identifier)
            entered.set()
            if not release.wait(10): raise RuntimeError('test gate timed out')
        with patch('backend.processing.process_run', side_effect=held_job):
            first = asyncio.create_task(run_job(self.app, 'synthetic-one'))
            second = asyncio.create_task(run_job(self.app, 'synthetic-two'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 10))
                self.assertEqual(calls, ['synthetic-one'])
                # Real API read remains responsive while the worker is occupied.
                self.assertEqual((await self.client.get(self.url)).status_code, 200)
            finally:
                release.set()
                await asyncio.gather(first, second)
        self.assertEqual(calls, ['synthetic-one', 'synthetic-two'])

    async def test_publication_failure_rolls_back_then_new_key_retry_succeeds(self):
        def fail_after_insert(connection, run, output):
            publish_outputs(connection, run, output)
            raise RuntimeError('SECRET synthetic failure after output/pointer updates')
        with patch('backend.processing.publish_outputs', side_effect=fail_after_insert):
            run = (await self.start()).json()
        failed = await self.poll(run)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error'], 'PROCESSING_FAILED')
        self.assertNotIn('SECRET', json.dumps(failed))
        self.assertEqual(self.rows('processing_outputs'), [])
        retry = (await self.start('new-key')).json()
        self.assertEqual((await self.poll(retry))['status'], 'completed')
        self.assertEqual((await self.poll(run)), failed)

    async def test_source_integrity_missing_or_unsafe_original_fails_without_outputs(self):
        evidence = self.rows('evidence')[0]
        original_path = Path(evidence['storage_path'])
        original = original_path.read_bytes()
        original_path.write_bytes(b'SECRET tampered original')
        run = (await self.start('tampered')).json()
        self.assertEqual((await self.poll(run))['status'], 'failed')
        original_path.write_bytes(original)
        original_path.unlink()
        missing = (await self.start('missing')).json()
        self.assertEqual((await self.poll(missing))['error'], 'SOURCE_UNAVAILABLE')
        outside = self.root / 'SECRET.csv'; outside.write_bytes(original)
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE evidence SET storage_path=? WHERE id=?', (str(outside), self.evidence['id']))
        unsafe = (await self.start('unsafe')).json()
        self.assertEqual((await self.poll(unsafe))['error'], 'SOURCE_UNAVAILABLE')
        self.assertEqual(self.rows('processing_outputs'), [])

    async def test_revoked_job_cannot_publish(self):
        jobs = []
        with patch('backend.processing.process_run', side_effect=lambda app, rid: jobs.append((app, rid))):
            await self.start()
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        process_run(*jobs[0])
        self.assertEqual(self.rows('processing_runs')[0]['status'], 'failed')
        self.assertEqual(self.rows('processing_outputs'), [])

    async def test_revocation_during_actual_parse_prevents_publication(self):
        def revoke_after_parse(*args, **kwargs):
            observations = parse_network_csv(*args, **kwargs)
            with self.app.state.database.connect() as connection:
                connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
            return observations
        with patch('backend.processing.adapter_for', return_value=replace(adapter_for('network_log'), parse=revoke_after_parse)):
            await self.start()
        self.assertEqual(self.rows('processing_runs')[0]['status'], 'failed')
        self.assertEqual(self.rows('processing_runs')[0]['error'], 'SOURCE_UNAVAILABLE')
        self.assertEqual(self.rows('processing_outputs'), [])

    async def test_frozen_queued_configuration_cannot_execute_changed_version(self):
        jobs = []
        with patch('backend.processing.process_run', side_effect=lambda app, rid: jobs.append((app, rid))):
            accepted = (await self.start()).json()
        with patch('backend.processing.PROCESSOR_VERSION', 'synthetic-new-version'):
            process_run(*jobs[0])
        self.assertEqual((await self.poll(accepted))['status'], 'failed')
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(json.loads(self.rows('processing_runs')[0]['config_json'])['max_data_rows'], 100000)

    async def test_restart_fails_interrupted_runs_and_preserves_terminal_history(self):
        complete = (await self.start('complete')).json()
        completed = await self.poll(complete)
        output = self.rows('processing_outputs')
        jobs = []
        with patch('backend.processing.process_run', side_effect=lambda app, rid: jobs.append((app, rid))):
            queued = (await self.start('queued')).json()
            running = (await self.start('running')).json()
        # Fault fixture: persisted interrupted claim; startup recovery is actual SQL code.
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running['id'],))
        second = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private')
        async with second.router.lifespan_context(second):
            for run in [queued, running]:
                failed = await self.poll(run)
                self.assertEqual(failed['status'], 'failed')
                self.assertEqual(failed['error'], 'PROCESSING_INTERRUPTED')
                self.assertEqual((await self.start('queued' if run == queued else 'running')).json(), failed)
        self.assertEqual(await self.poll(complete), completed)
        self.assertEqual(self.rows('processing_outputs'), output)
        self.assertEqual((await self.poll((await self.start('fresh')).json()))['status'], 'completed')

    async def test_terminal_config_outputs_and_completion_pointer_protected_by_sql(self):
        run = (await self.start()).json()
        statements = [
            ("UPDATE processing_runs SET config_json='{}' WHERE id=?", run['id']),
            ("UPDATE processing_runs SET status='failed',error='x' WHERE id=?", run['id']),
            ("DELETE FROM processing_runs WHERE id=?", run['id']),
            ("UPDATE processing_outputs SET observations_json='[]' WHERE run_id=?", run['id']),
            ("DELETE FROM processing_outputs WHERE run_id=?", run['id']),
        ]
        for sql, identifier in statements:
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection: connection.execute(sql, (identifier,))
        with patch('backend.processing.process_run'):
            pending = (await self.start('pending')).json()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (pending['id'],))
                connection.execute("UPDATE processing_runs SET status='completed',finished_at='2026-01-12T00:00:00Z' WHERE id=?", (pending['id'],))

    async def test_empty_csv_is_real_completed_empty_output_and_list_order_is_oldest_first(self):
        empty = await self.upload(data=b'timestamp,device_id,ip_address,event\n')
        url = self.base(self.case, empty['id'])
        first = (await self.start('first', url)).json()
        second = (await self.start('second', url)).json()
        self.assertEqual((await self.poll(first, url))['status'], 'completed')
        self.assertEqual([x['id'] for x in (await self.client.get(url)).json()], [first['id'], second['id']])
        for output in self.rows('processing_outputs'):
            self.assertEqual(json.loads(output['observations_json']), [])
            self.assertEqual(json.loads(output['entities_json']), [])
            self.assertEqual(json.loads(output['events_json']), [])


class ProcessingLoopbackTests(unittest.TestCase):
    def test_real_localhost_start_poll_list_network_gps_and_failed_csv(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; root=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(root/"db.sqlite3",storage_dir=root/"private",token_verifier='
                    'SyntheticTokenVerifier({"p04-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([PYTHON, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p04-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            ready = client.get('/api/v1/cases')
                            if ready.status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P04 HTTP'}).json()['id']
                    for kind, data, expected in [('network_log', (ROOT/'fixtures/synthetic-case/network.csv').read_bytes(), 'completed'),
                                               ('gps', (ROOT/'fixtures/synthetic-case/gps.csv').read_bytes(), 'completed'),
                                               ('network_log', b'bad header\n', 'failed')]:
                        evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': kind, 'source_label': 'Synthetic HTTP'},
                                               files={'file': ('source.csv', data, 'text/csv')}).json()
                        url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted = client.post(url, headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(accepted.status_code, 202)
                        self.assertEqual(accepted.json()['status'], 'queued')
                        for _ in range(100):
                            run = client.get(url + '/' + accepted.json()['id']).json()
                            if run['status'] in ('completed', 'failed'): break
                            time.sleep(0.05)
                        self.assertEqual(run['status'], expected)
                        self.assertEqual(client.get(url).json(), [run])
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
