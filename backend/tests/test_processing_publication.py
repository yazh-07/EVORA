"""P14C real SQL publication/crash/retry; labeled scheduling and failure injections."""
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
from uuid import UUID, uuid4

import httpx
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import Actor, CaseAccessGrant, SyntheticTokenVerifier
from backend.errors import AccessError
from backend.processing_provenance import read_processing_provenance, record_processing_provenance
from backend.processing import initialize_processing
from backend.processing import process_run, publish_outputs, run_job
from backend.processing_dispatch import adapter_for
from backend.processing_publication import verify_publication

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class PublicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p14c-synthetic-one': 'investigator-1', 'p14c-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p14c-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P14C case'})).json()['id']
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
            data={'kind': kind, 'source_label': 'Synthetic P14C'}, files={'file': ('source.csv', data, 'text/csv')})
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

    def read(self, run, evidence=None, actor='investigator-1', case=None):
        return read_processing_provenance(self.app,
            CaseAccessGrant(Actor(actor), UUID(case or self.case)),
            UUID((evidence or self.evidence)['id']), UUID(run['id']))

    def denied(self, run, **kwargs):
        with self.assertRaises(AccessError) as error: self.read(run, **kwargs)
        self.assertEqual((error.exception.status_code, error.exception.code, str(error.exception)),
                         (404, 'NOT_FOUND', 'Resource not found.'))

    def by_run(self, table, run):
        return next(row for row in self.rows(table) if row.get('run_id', row.get('id')) == run['id'])

    async def test_actual_sql_readback_precedes_completed_pointer_with_real_sources(self):
        observed = []
        def inspected(connection, run, output, finished_at):
            stored = connection.execute('SELECT status,finished_at FROM processing_runs WHERE id=?', (run['id'],)).fetchone()
            self.assertEqual((stored['status'], stored['finished_at']), ('running', None))
            self.assertEqual(connection.execute('SELECT count(*) FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT count(*) FROM processing_provenance WHERE run_id=?', (run['id'],)).fetchone()[0], 1)
            verify_publication(connection, run, output, finished_at)
            observed.append(run['id'])
        gps = await self.upload('gps')
        with patch('backend.processing.verify_publication', side_effect=inspected):
            for evidence, counts in ((self.evidence, (6, 4, 2)), (gps, (3, 1, 1))):
                url = self.base(self.case, evidence['id']); run = (await self.start(str(uuid4()), url)).json()
                complete = await self.poll(run, url)
                self.assertEqual(complete['status'], 'completed')
                private = self.read(run, evidence)
                self.assertEqual(private['finished_at'], complete['finished_at'])
                self.assertEqual(tuple(len(private['outputs'][key]) for key in ('observation_ids','entity_ids','event_ids')), counts)
                self.assertEqual(private['input']['sha256'], evidence['sha256'])
                self.validate('ProcessingRun', complete)
        self.assertEqual(len(observed), 2)

    async def test_sql_output_or_private_corruption_is_rejected_before_completion(self):
        # Only temporary DB: faults occur after real producers and private insert.
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic other'})).json()['id']
        for fault in ('missing_output', 'output_bytes', 'output_context', 'missing_private', 'private_payload',
                      'private_context', 'private_time', 'frozen_run'):
            def corrupt(connection, run, output, finished_at):
                record_processing_provenance(connection, run, output, finished_at)
                if fault == 'missing_output':
                    connection.execute('DROP TRIGGER processing_output_delete')
                    connection.execute('DELETE FROM processing_outputs WHERE run_id=?', (run['id'],))
                elif fault in ('output_bytes', 'output_context'):
                    connection.execute('DROP TRIGGER processing_output_update')
                    if fault == 'output_bytes':
                        connection.execute("UPDATE processing_outputs SET uncertainty_json='[{}]' WHERE run_id=?", (run['id'],))
                    else:
                        connection.execute('UPDATE processing_outputs SET case_id=? WHERE run_id=?', (other_case, run['id']))
                elif fault == 'missing_private':
                    connection.execute('DROP TRIGGER processing_provenance_no_delete')
                    connection.execute('DELETE FROM processing_provenance WHERE run_id=?', (run['id'],))
                elif fault.startswith('private_'):
                    connection.execute('DROP TRIGGER processing_provenance_no_update')
                    column, value = {'private_payload': ('payload_json', '{"SECRET":"bad"}'),
                                     'private_context': ('case_id', other_case), 'private_time': ('finished_at', '2099-01-01T00:00:00Z')}[fault]
                    connection.execute(f'UPDATE processing_provenance SET {column}=? WHERE run_id=?', (value, run['id']))
                else:
                    connection.execute('DROP TRIGGER processing_run_frozen')
                    connection.execute("UPDATE processing_runs SET config_json='{}' WHERE id=?", (run['id'],))
            with patch('backend.processing.record_processing_provenance', side_effect=corrupt):
                run = (await self.start(fault)).json()
            failed = await self.poll(run)
            self.assertEqual((failed['status'], failed['error']), ('failed', 'PROCESSING_FAILED'), fault)
            self.assertNotIn('SECRET', json.dumps(failed)); self.denied(run)
            self.assertEqual(self.rows('processing_outputs'), [])
            self.assertEqual(self.rows('processing_provenance'), [])
        # DDL fault controls themselves rolled back; normal publication still works.
        fresh = (await self.start('normal')).json()
        self.assertEqual(self.read(fresh)['processing_run_id'], fresh['id'])

    async def test_verification_failure_rolls_back_and_replay_keeps_original_failed_run(self):
        good = (await self.start('good')).json(); old_private = self.read(good)
        old_output = self.by_run('processing_outputs', good)
        with patch('backend.processing.verify_publication', side_effect=ValueError('SECRET verification failure')):
            failed = (await self.start('bad')).json()
        first = await self.poll(failed)
        self.assertEqual((first['status'], first['error']), ('failed', 'PROCESSING_FAILED'))
        with patch('backend.processing.process_run') as worker:
            replay = (await self.start('bad')).json()
        worker.assert_not_called(); self.assertEqual(replay, first)
        self.assertEqual(self.by_run('processing_outputs', good), old_output)
        self.assertEqual(self.read(good), old_private)
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)
        retry = (await self.start('retry')).json()
        self.assertNotEqual(retry['id'], failed['id'])
        self.assertEqual(self.read(retry)['processing_run_id'], retry['id'])
        self.assertEqual(self.read(good), old_private)

    async def test_completion_must_update_exactly_one_running_row(self):
        def changed_state(connection, run, output, finished_at):
            verify_publication(connection, run, output, finished_at)
            connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='SYNTHETIC' WHERE id=?",
                               (finished_at, run['id']))
        with patch('backend.processing.verify_publication', side_effect=changed_state):
            run = (await self.start()).json()
        failed = await self.poll(run)
        self.assertEqual((failed['status'], failed['error']), ('failed', 'PROCESSING_FAILED'))
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_staged_sql_output_and_private_record_are_invisible_until_verified_commit(self):
        old = (await self.start('old')).json(); old_private = self.read(old)
        before = {name: (await self.client.get(f'/api/v1/cases/{self.case}/{name}')).json() for name in ('observations','entities','events')}
        entered, release = threading.Event(), threading.Event()
        def held(connection, run, output, finished_at):
            verify_publication(connection, run, output, finished_at)
            entered.set()
            if not release.wait(10): raise RuntimeError('Synthetic verification gate timed out')
        with patch('backend.processing.verify_publication', side_effect=held):
            task = asyncio.create_task(self.start('new'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 10))
                rows = self.rows('processing_runs'); pending = next(x for x in rows if x['id'] != old['id'])
                self.assertEqual(pending['status'], 'running')
                self.assertEqual(len(self.rows('processing_outputs')), 1)
                self.assertEqual(len(self.rows('processing_provenance')), 1)
                self.denied(pending)
                for name, page in before.items():
                    self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/{name}')).json(), page)
            finally:
                release.set(); response = await task
        new = response.json()
        self.assertEqual((await self.poll(new))['status'], 'completed')
        self.assertEqual(len(self.rows('processing_outputs')), 2)
        self.assertEqual(len(self.rows('processing_provenance')), 2)
        self.assertEqual(self.read(old), old_private)
        observations = (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()['items']
        self.assertEqual({x['processing_run_id'] for x in observations}, {new['id']})

    async def test_concurrent_same_key_acceptance_executes_and_publishes_once(self):
        adapter = adapter_for('network_log'); lock = threading.Lock(); calls = []
        def counted(*args, **kwargs):
            with lock: calls.append(kwargs['processing_run_id'])
            time.sleep(0.1)
            return adapter.parse(*args, **kwargs)
        with patch('backend.processing.adapter_for', return_value=replace(adapter, parse=counted)):
            responses = await asyncio.gather(*(self.start('concurrent') for _ in range(8)))
        self.assertTrue(all(x.status_code == 202 for x in responses))
        ids = {x.json()['id'] for x in responses}; self.assertEqual(len(ids), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.rows('processing_runs')), 1)
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)
        self.assertEqual((await self.poll(responses[0].json()))['status'], 'completed')

    async def test_concurrent_same_key_different_targets_conflict_without_mixed_output(self):
        gps = await self.upload('gps'); gps_url = self.base(self.case, gps['id'])
        requests = [(self.url, self.evidence), (gps_url, gps)] * 4
        responses = await asyncio.gather(*(self.start('same-key', url) for url, _ in requests))
        self.assertEqual({x.status_code for x in responses}, {202, 409})
        accepted = [(r.json(), evidence) for r, (_, evidence) in zip(responses, requests) if r.status_code == 202]
        self.assertEqual(len({run['id'] for run, _ in accepted}), 1)
        winner, evidence = accepted[0]
        self.assertEqual(self.read(winner, evidence)['evidence_id'], evidence['id'])
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_concurrent_new_keys_and_duplicate_worker_claim_preserve_every_history(self):
        responses = await asyncio.gather(*(self.start(f'new-{i}') for i in range(4)))
        self.assertTrue(all(x.status_code == 202 for x in responses))
        records = {x.json()['id']: self.read(x.json()) for x in responses}
        self.assertEqual(len(records), 4)
        self.assertEqual(len(self.rows('processing_outputs')), 4)
        self.assertEqual(len(self.rows('processing_provenance')), 4)
        with patch('backend.processing.process_run'):
            queued = (await self.start('claim')).json()
        await asyncio.gather(*(asyncio.to_thread(process_run, self.app, queued['id']) for _ in range(3)))
        self.assertEqual((await self.poll(queued))['status'], 'completed')
        self.assertEqual(len(self.rows('processing_outputs')), 5)
        self.assertEqual(len(self.rows('processing_provenance')), 5)
        for identifier, private in records.items(): self.assertEqual(self.read({'id': identifier}), private)

    async def test_sql_replace_upsert_key_and_hidden_rowid_collisions_cannot_rewrite_history(self):
        good = (await self.start('good')).json(); private = self.read(good)
        with self.app.state.database.connect() as connection:
            row = dict(connection.execute('SELECT rowid,* FROM processing_runs WHERE id=?', (good['id'],)).fetchone())
        fields = [key for key in row if key != 'rowid']
        variants = [dict(row), dict(row, id=str(uuid4())), dict(row, id=str(uuid4()), key_digest=str(uuid4()))]
        for index, variant in enumerate(variants):
            columns = (['rowid'] if index == 2 else []) + fields
            statement = f"INSERT OR REPLACE INTO processing_runs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(statement, [variant[key] for key in columns])
        with self.app.state.database.connect() as connection:
            output = dict(connection.execute('SELECT rowid,* FROM processing_outputs WHERE run_id=?', (good['id'],)).fetchone())
        with patch('backend.processing.process_run'):
            pending = (await self.start('pending')).json()
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (pending['id'],))
        # A new running target would pass the old context-only INSERT guard.
        for replace_rowid in (False, True):
            columns = [key for key in output if key != 'rowid' or replace_rowid]
            changed = dict(output, run_id=pending['id']) if replace_rowid else output
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(f"INSERT OR REPLACE INTO processing_outputs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                                       [changed[key] for key in columns])
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("INSERT INTO processing_runs (" + ','.join(fields) + ') VALUES (' + ','.join('?' for _ in fields) +
                    ') ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json', [row[key] for key in fields])
        self.assertEqual(self.read(good), private)

    async def test_failed_history_also_survives_hidden_rowid_replacement(self):
        bad = await self.upload(data=b'bad header\n'); url = self.base(self.case, bad['id'])
        failed = (await self.start('bad', url)).json(); before = await self.poll(failed, url)
        with self.app.state.database.connect() as connection:
            row = dict(connection.execute('SELECT rowid,* FROM processing_runs WHERE id=?', (failed['id'],)).fetchone())
        changed = dict(row, id=str(uuid4()), key_digest=str(uuid4()), status='queued', finished_at=None, error=None)
        columns = list(changed)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute(f"INSERT OR REPLACE INTO processing_runs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                                   [changed[key] for key in columns])
        self.assertEqual(await self.poll(failed, url), before)

    async def test_no_false_completion_during_failed_verification_with_revoked_or_foreign_reads(self):
        with patch('backend.processing.verify_publication', side_effect=ValueError('SECRET')):
            failed = (await self.start('failed')).json()
        self.denied(failed)
        self.denied(failed, actor='investigator-2')
        response = await self.client.get(self.url + '/' + failed['id'], headers={'Authorization': 'Bearer p14c-synthetic-two'})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('SECRET', response.text)
        for endpoint in ('observations', 'entities', 'events'):
            self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/{endpoint}')).json()['total'], 0)

    async def test_real_child_crashes_rollback_or_preserve_commit_then_restart_replay_and_retry(self):
        baseline = (await self.start('baseline')).json(); original_private = self.read(baseline)
        code = r'''
import os, sys
from pathlib import Path
from unittest.mock import patch
from backend.app import create_app
from backend.processing import process_run, publish_outputs
from backend.processing_publication import verify_publication
root, run_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
app = create_app(root/'db.sqlite3', storage_dir=root/'private')
def stop(*args, **kwargs):
    (root/'p14c-crash-hit.txt').write_text(mode, encoding='utf-8')
    os._exit(97)
def after_verify(*args):
    verify_publication(*args); stop()
def after_pointer(*args):
    publish_outputs(*args); stop()
if mode == 'queued': stop()
targets = {
    'running': ('backend.processing.adapter_for', stop),
    'output': ('backend.processing.record_processing_provenance', stop),
    'provenance': ('backend.processing.verify_publication', stop),
    'verified': ('backend.processing.verify_publication', after_verify),
    'pointer': ('backend.processing.publish_outputs', after_pointer),
}
if mode == 'committed':
    process_run(app, run_id)
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT status FROM processing_runs WHERE id=?', (run_id,)).fetchone()[0] == 'completed'
    stop()
target, callback = targets[mode]
with patch(target, side_effect=callback): process_run(app, run_id)
raise RuntimeError('Synthetic crash boundary not reached')
'''
        for mode in ('queued', 'running', 'output', 'provenance', 'verified', 'pointer', 'committed'):
            with self.subTest(mode=mode):
                before = {name: self.rows(name) for name in ('processing_outputs', 'processing_provenance')}
                old_page = (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()
                with patch('backend.processing.process_run'):
                    run = (await self.start('crash-' + mode)).json()
                marker = self.root/'p14c-crash-hit.txt'
                if marker.exists(): marker.unlink()
                result = await asyncio.to_thread(subprocess.run, [PYTHON, '-c', code, str(self.root), run['id'], mode],
                    cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 97, result.stderr)
                self.assertEqual(marker.read_text(encoding='utf-8'), mode)
                raw = await self.poll(run)
                if mode != 'committed':
                    self.assertEqual(raw['status'], 'queued' if mode == 'queued' else 'running')
                    self.assertEqual({name: self.rows(name) for name in before}, before)
                    self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/observations')).json(), old_page)
                    self.denied(run)
                else:
                    self.assertEqual(raw['status'], 'completed')
                    self.assertEqual(self.read(run)['processing_run_id'], run['id'])
                restarted = create_app(self.root/'db.sqlite3', storage_dir=self.root/'private',
                    token_verifier=SyntheticTokenVerifier({'p14c-synthetic-one': 'investigator-1'}))
                async with restarted.router.lifespan_context(restarted):
                    async with AsyncClient(transport=ASGITransport(restarted), base_url='http://restart',
                                           headers={'Authorization': 'Bearer p14c-synthetic-one'}) as client:
                        recovered = (await client.get(self.url + '/' + run['id'])).json()
                        self.assertEqual(recovered['status'], 'completed' if mode == 'committed' else 'failed')
                        if mode != 'committed': self.assertEqual(recovered['error'], 'PROCESSING_INTERRUPTED')
                        replay = await client.post(self.url, headers={'Idempotency-Key': 'crash-' + mode})
                        self.assertEqual(replay.json(), recovered)
                        retry = (await client.post(self.url, headers={'Idempotency-Key': 'retry-' + mode})).json()
                        self.assertNotEqual(retry['id'], run['id'])
                        self.assertEqual((await client.get(self.url + '/' + retry['id'])).json()['status'], 'completed')
                self.assertEqual(self.read(baseline), original_private)
                with self.app.state.database.connect() as connection:
                    self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                    self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
        historical = await self.client.get(f'/api/v1/cases/{self.case}/observations', params={'processing_run_id': baseline['id']})
        self.assertEqual({x['id'] for x in historical.json()['items']}, set(original_private['outputs']['observation_ids']))



class PublicationLoopbackTests(unittest.TestCase):
    def test_real_http_verified_publication_and_failed_run_visibility(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; root=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(root/"db.sqlite3",storage_dir=root/"private",token_verifier='
                    'SyntheticTokenVerifier({"p14c-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([PYTHON, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p14c-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            ready = client.get('/api/v1/cases')
                            if ready.status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P14C HTTP'}).json()['id']
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
                        with closing(sqlite3.connect(Path(directory)/'db.sqlite3')) as connection:
                            connection.row_factory = sqlite3.Row
                            record = connection.execute('SELECT * FROM processing_provenance WHERE run_id=?', (run['id'],)).fetchone()
                            if expected == 'failed':
                                self.assertIsNone(record)
                            else:
                                self.assertIsNotNone(record)
                                payload = json.loads(record['payload_json'])
                                self.assertEqual((payload['case_id'], payload['evidence_id'], payload['processing_run_id']),
                                                 (case, evidence['id'], run['id']))
                                self.assertEqual(payload['input']['sha256'], hashlib.sha256(data).hexdigest())
                                self.assertEqual(payload['finished_at'], run['finished_at'])
                                self.assertIsNone(payload['execution']['model'])
                                self.assertEqual(len(payload['outputs']['observation_ids']), 6 if kind == 'network_log' else 3)
                        self.assertNotIn('output_sha256', run)
                        self.assertEqual(client.get(f'/api/v1/cases/{case}/processing-provenance').status_code, 404)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/observations').json()['total'], 9)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/entities').json()['total'], 5)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/events').json()['total'], 3)


            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
