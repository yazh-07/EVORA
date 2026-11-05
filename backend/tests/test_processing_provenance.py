"""P14 real private provenance pipeline; labeled scheduling and failure injections."""
import asyncio
from contextlib import closing
import hashlib
import io
import logging
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
from backend.parsers.network_csv import parse_network_csv

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class ProcessingProvenanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p14-synthetic-one': 'investigator-1', 'p14-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p14-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P14 case'})).json()['id']
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
            data={'kind': kind, 'source_label': 'Synthetic P14'}, files={'file': ('source.csv', data, 'text/csv')})
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

    async def test_actual_network_gps_exact_private_versions_inputs_manifests_digest_and_time(self):
        gps = await self.upload('gps')
        for evidence, counts in ((self.evidence, (6, 4, 2)), (gps, (3, 1, 1))):
            run = (await self.start(str(uuid4()), self.base(self.case, evidence['id']))).json()
            complete = await self.poll(run, self.base(self.case, evidence['id']))
            self.assertEqual(complete['status'], 'completed')
            payload = self.read(run, evidence)
            self.assertEqual(payload['record_version'], 'processing-provenance/1')
            self.assertEqual((payload['case_id'], payload['evidence_id'], payload['processing_run_id']),
                             (self.case, evidence['id'], run['id']))
            self.assertEqual(payload['input'], {key: evidence[key] for key in ('kind', 'sha256', 'size_bytes')})
            self.assertEqual(payload['finished_at'], complete['finished_at'])
            self.assertEqual(payload['accepted_at'], run['created_at'])
            config = json.loads(self.by_run('processing_runs', run)['config_json'])
            self.assertEqual(payload['execution']['versions'], {key: config[key] for key in (
                'parser_version', 'normalizer_version', 'entity_version', 'event_version', 'processor_version')})
            self.assertEqual(payload['execution']['versions']['processor_version'], 'processing-lifecycle/2')
            self.assertEqual(payload['execution']['parameters'], {'max_source_bytes': 50 * 1024 * 1024, 'max_data_rows': 100000})
            self.assertEqual(payload['execution']['method'], 'deterministic')
            self.assertIsNone(payload['execution']['model'])
            output = self.by_run('processing_outputs', run)
            fields = ('observations_json', 'entities_json', 'events_json', 'uncertainty_json')
            digest_input = json.dumps({key: output[key] for key in fields}, sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.assertEqual(payload['output_sha256'], hashlib.sha256(digest_input).hexdigest())
            for key, field, count in zip(('observation_ids', 'entity_ids', 'event_ids'), fields, counts):
                records = json.loads(output[field])
                self.assertEqual(len(records), count)
                self.assertEqual(payload['outputs'][key], sorted(x['id'] for x in records))
            for observation in json.loads(output['observations_json']):
                self.assertEqual((observation['case_id'], observation['evidence_id'], observation['processing_run_id']),
                                 (self.case, evidence['id'], run['id']))
                self.assertTrue(observation['source_locator'])
            self.validate('ProcessingRun', complete)

    async def test_empty_success_has_real_empty_manifests(self):
        evidence = await self.upload(data=b'timestamp,device_id,ip_address,event\n')
        run = (await self.start('empty', self.base(self.case, evidence['id']))).json()
        payload = self.read(run, evidence)
        self.assertEqual(payload['outputs'], dict(observation_ids=[], entity_ids=[], event_ids=[]))
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_replay_new_key_and_reads_preserve_original_provenance_and_source(self):
        run = (await self.start('same-key')).json(); first = self.read(run)
        snapshot = {name: self.rows(name) for name in ('processing_outputs', 'processing_provenance', 'evidence', 'audit_events')}
        with patch('backend.processing.process_run') as worker:
            replay = (await self.start('same-key')).json()
            self.assertEqual(replay['id'], run['id'])
            self.assertEqual(self.read(run), first)
        worker.assert_not_called()
        self.assertEqual({name: self.rows(name) for name in snapshot}, snapshot)
        fresh = (await self.start('new-key')).json(); second = self.read(fresh)
        self.assertNotEqual(first['processing_run_id'], second['processing_run_id'])
        self.assertTrue(set(first['outputs']['observation_ids']).isdisjoint(second['outputs']['observation_ids']))
        self.assertEqual(first['input'], second['input'])
        self.assertEqual(self.read(run), first)
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(hashlib.sha256(original.content).hexdigest(), first['input']['sha256'])

    async def test_provenance_failure_before_insert_publishes_no_outputs_or_completion(self):
        with patch('backend.processing.record_processing_provenance', side_effect=RuntimeError('SECRET provenance failure')):
            run = (await self.start()).json()
        complete = await self.poll(run)
        self.assertEqual((complete['status'], complete['error']), ('failed', 'PROCESSING_FAILED'))
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])
        self.denied(run)
        self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/events')).json()['total'], 0)
        fresh = (await self.start('retry')).json()
        self.assertEqual(self.read(fresh)['processing_run_id'], fresh['id'])
        self.assertEqual((await self.start()).json()['id'], run['id'])
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_failure_after_provenance_insert_rolls_back_entire_publication(self):
        def fail(connection, run, output, finished_at):
            record_processing_provenance(connection, run, output, finished_at)
            raise RuntimeError('SECRET after private insert')
        with patch('backend.processing.record_processing_provenance', side_effect=fail):
            run = (await self.start()).json()
        self.assertEqual((await self.poll(run))['status'], 'failed')
        self.assertEqual(self.rows('processing_provenance'), [])
        self.assertEqual(self.rows('processing_outputs'), [])
        self.denied(run)

    async def test_failure_after_completion_update_rolls_back_outputs_and_provenance(self):
        def fail(connection, run, output):
            publish_outputs(connection, run, output)
            raise RuntimeError('SECRET after completed pointer')
        with patch('backend.processing.publish_outputs', side_effect=fail):
            run = (await self.start()).json()
        self.assertEqual((await self.poll(run))['status'], 'failed')
        self.assertEqual(self.rows('processing_provenance'), [])
        self.assertEqual(self.rows('processing_outputs'), [])
        self.denied(run)

    async def test_invalid_output_manifest_or_source_refs_cannot_publish_provenance(self):
        # Fault injections after the real adapters; never substitute a producer.
        for fault in ('duplicate', 'foreign_run', 'missing_source', 'missing_participant'):
            def corrupt(connection, run, output):
                observations, entities, events = [json.loads(value) for value in output[:3]]
                if fault == 'duplicate': observations.append(observations[0])
                elif fault == 'foreign_run': observations[0]['processing_run_id'] = str(uuid4())
                elif fault == 'missing_source': entities[0]['observation_ids'] = [str(uuid4())]
                else: events[0]['entity_ids'] = [str(uuid4())]
                modified = tuple(json.dumps(values) for values in (observations, entities, events)) + (output[3],)
                publish_outputs(connection, run, modified)
            with patch('backend.processing.publish_outputs', side_effect=corrupt):
                run = (await self.start(fault)).json()
            self.assertEqual((await self.poll(run))['status'], 'failed')
            self.denied(run)
        self.assertEqual(self.rows('processing_provenance'), [])
        self.assertEqual(self.rows('processing_outputs'), [])

    async def test_pending_malformed_failed_and_unsupported_never_get_success_provenance(self):
        with patch('backend.processing.process_run'):
            pending = (await self.start()).json()
        self.denied(pending)
        malformed = await self.upload(data=b'bad header\n')
        failed = (await self.start('bad', self.base(self.case, malformed['id']))).json()
        self.assertEqual((await self.poll(failed, self.base(self.case, malformed['id'])))['status'], 'failed')
        self.denied(failed, evidence=malformed)
        unsupported = await self.upload('audio')
        self.assertEqual((await self.start('unsupported', self.base(self.case, unsupported['id']))).status_code, 415)
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_membership_rechecked_and_foreign_missing_mismatched_contexts_hidden(self):
        run = (await self.start()).json()
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic other'})).json()['id']
        other_evidence = await self.upload(case=other_case)
        other_run = (await self.start('other', self.base(other_case, other_evidence['id']))).json()
        self.denied(run, actor='investigator-2')
        self.denied(run, case=other_case)
        self.denied(run, evidence=other_evidence)
        self.denied(other_run, evidence=other_evidence)
        self.denied({'id': str(uuid4())})
        self.denied(run, evidence={'id': str(uuid4())})
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.denied(run)
        self.assertEqual(len(self.rows('processing_provenance')), 2)

    async def test_revoked_worker_publishes_neither_output_nor_provenance(self):
        with patch('backend.processing.process_run'):
            run = (await self.start()).json()
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        process_run(self.app, run['id'])
        self.assertEqual(self.rows('processing_runs')[0]['status'], 'failed')
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_sql_update_delete_replace_upsert_and_rowid_bypasses_rejected(self):
        run = (await self.start()).json(); before = self.read(run)
        row = self.by_run('processing_provenance', run)
        statements = [
            ('UPDATE processing_provenance SET payload_json=payload_json WHERE run_id=?', (run['id'],)),
            ('DELETE FROM processing_provenance WHERE run_id=?', (run['id'],)),
            ('INSERT OR REPLACE INTO processing_provenance VALUES (?,?,?,?,?,?)', tuple(row.values())),
            ('INSERT INTO processing_provenance VALUES (?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET payload_json=excluded.payload_json', tuple(row.values())),
        ]
        for statement, params in statements:
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection: connection.execute(statement, params)
        with self.assertRaises(sqlite3.OperationalError):
            with self.app.state.database.connect() as connection: connection.execute('SELECT rowid FROM processing_provenance')
        self.assertEqual(self.read(run), before)

    async def test_sql_completion_gate_requires_provenance_and_identical_time(self):
        valid = (await self.start()).json(); output_row = self.by_run('processing_outputs', valid)
        output = tuple(output_row[key] for key in ('observations_json', 'entities_json', 'events_json', 'uncertainty_json'))
        with patch('backend.processing.process_run'):
            pending = (await self.start('pending')).json()
        # Deliberate SQL fault fixture: bypass app publication, retain real transaction rules.
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (pending['id'],))
                connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                                   (pending['id'], self.case, self.evidence['id'], *output))
                connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?",
                                   (self.read(valid)['finished_at'], pending['id']))
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                row = dict(self.by_run('processing_provenance', valid)); row['run_id'] = pending['id']
                connection.execute('INSERT INTO processing_provenance VALUES (?,?,?,?,?,?)', tuple(row.values()))
        def wrong_time(connection, run, output, finished_at):
            record_processing_provenance(connection, run, output, '2099-01-01T00:00:00Z')
        with patch('backend.processing.record_processing_provenance', side_effect=wrong_time):
            wrong = (await self.start('wrong-time')).json()
        self.assertEqual((await self.poll(wrong))['status'], 'failed')
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_corrupt_private_payload_context_or_missing_record_is_safe_404(self):
        run = (await self.start()).json(); row = self.by_run('processing_provenance', run)
        payload = json.loads(row['payload_json'])
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic foreign context'})).json()['id']
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_provenance_no_update')
        # Temp-only corruption controls, not permissible production mutations.
        bad = ['SECRET invalid JSON', 'null', '{}']
        for change in (dict(record_version='unknown'), dict(output_sha256='0' * 64), dict(outputs={}),
                       dict(processing_run_id=str(uuid4())), dict(finished_at='SECRET'),
                       dict(execution=dict(payload['execution'], model={'version': 'SECRET'})),
                       dict(input=dict(payload['input'], size_bytes=True)), dict(private_SECRET='not real')):
            bad.append(json.dumps(dict(payload, **change)))
        for value in bad:
            with self.app.state.database.connect() as connection:
                connection.execute('UPDATE processing_provenance SET payload_json=? WHERE run_id=?', (value, run['id']))
            self.denied(run)
        with self.app.state.database.connect() as connection:
            connection.execute('UPDATE processing_provenance SET payload_json=?,case_id=? WHERE run_id=?',
                               (row['payload_json'], other_case, run['id']))
        self.denied(run)
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_provenance_no_delete')
            connection.execute('DELETE FROM processing_provenance WHERE run_id=?', (run['id'],))
        self.denied(run)

    async def test_corrupt_selected_output_digest_or_source_join_is_safe_404(self):
        run = (await self.start()).json(); row = self.by_run('processing_outputs', run)
        with self.app.state.database.connect() as connection: connection.execute('DROP TRIGGER processing_output_update')
        for column, value in [('observations_json', 'SECRET malformed'), ('entities_json', '[]'),
                              ('events_json', '[]'), ('uncertainty_json', '[{}]'),
                              ('case_id', str(uuid4())), ('evidence_id', str(uuid4()))]:
            with self.app.state.database.connect() as connection:
                connection.execute(f'UPDATE processing_outputs SET {column}=? WHERE run_id=?', (value, run['id']))
            self.denied(run)
            with self.app.state.database.connect() as connection:
                connection.execute(f'UPDATE processing_outputs SET {column}=? WHERE run_id=?', (row[column], run['id']))

    async def test_old_schema_upgrade_preserves_completed_history_without_fabricated_backfill(self):
        run = (await self.start()).json()
        # Explicit pre-P14 schema/version fixture built from real pipeline outputs.
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_completion_provenance')
            connection.execute('DROP TABLE processing_provenance')
            connection.execute('DROP TRIGGER processing_run_frozen')
            connection.execute('DROP TRIGGER processing_run_terminal')
            config = json.loads(self.by_run('processing_runs', run)['config_json'])
            config.pop('provenance_version'); config['processor_version'] = 'processing-lifecycle/1'
            connection.execute('UPDATE processing_runs SET config_json=?,processor_version=? WHERE id=?',
                               (json.dumps(config), 'processing-lifecycle/1', run['id']))
        snapshot = {name: self.rows(name) for name in ('processing_runs', 'processing_outputs', 'evidence', 'intake_provenance', 'audit_events')}
        initialize_processing(self.app.state.database)
        initialize_processing(self.app.state.database)
        self.assertEqual({name: self.rows(name) for name in snapshot}, snapshot)
        self.assertEqual(self.rows('processing_provenance'), [])
        self.denied(run)
        for endpoint, total in [('observations', 6), ('entities', 4), ('events', 2)]:
            self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/{endpoint}')).json()['total'], total)
        fresh = (await self.start('post-upgrade')).json()
        self.assertEqual(self.read(fresh)['processing_run_id'], fresh['id'])
        self.denied(run)

    async def test_restart_interrupted_job_has_no_fabricated_success_provenance(self):
        good = (await self.start()).json(); before = self.read(good)
        with patch('backend.processing.process_run'):
            pending = (await self.start('pending')).json()
        initialize_processing(self.app.state.database)
        self.assertEqual((await self.poll(pending))['error'], 'PROCESSING_INTERRUPTED')
        self.denied(pending)
        self.assertEqual(self.read(good), before)
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_public_run_audit_logs_and_private_manifest_do_not_leak_raw_content_or_credentials(self):
        marker = 'SENSITIVE_P14_SOURCE_SENTINEL'
        evidence = await self.upload(data=f'timestamp,device_id,ip_address,event\n2026-01-12T10:00:00Z,D-7,203.0.113.7,{marker}\n'.encode())
        log = io.StringIO(); handler = logging.StreamHandler(log); logger = logging.getLogger()
        logger.addHandler(handler); old_level = logger.level; logger.setLevel(logging.DEBUG)
        try:
            run = (await self.start('SENSITIVE_P14_KEY_SENTINEL', self.base(self.case, evidence['id']))).json()
            complete = await self.poll(run, self.base(self.case, evidence['id']))
            payload = self.read(run, evidence)
            with patch('backend.processing.record_processing_provenance', side_effect=RuntimeError(marker)):
                failed = (await self.start('failure', self.base(self.case, evidence['id']))).json()
            failed = await self.poll(failed, self.base(self.case, evidence['id']))
            audit = (await self.client.get(f'/api/v1/cases/{self.case}/audit-events')).json()
        finally:
            logger.setLevel(old_level); logger.removeHandler(handler); handler.close()
        public = json.dumps([run, complete, failed, audit]) + log.getvalue()
        for secret in (marker, 'SENSITIVE_P14_KEY_SENTINEL', 'p14-synthetic-one', str(self.root)):
            self.assertNotIn(secret, public)
            self.assertNotIn(secret, json.dumps(payload))
        for wire in (run, complete, failed): self.validate('ProcessingRun', wire)
        self.assertNotIn('execution', public)
        self.assertNotIn('output_sha256', public)
        self.assertEqual(failed['error'], 'PROCESSING_FAILED')



class ProvenanceLoopbackTests(unittest.TestCase):
    def test_real_localhost_public_processing_and_private_sql_provenance(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; root=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(root/"db.sqlite3",storage_dir=root/"private",token_verifier='
                    'SyntheticTokenVerifier({"p14-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([PYTHON, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p14-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            ready = client.get('/api/v1/cases')
                            if ready.status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P14 HTTP'}).json()['id']
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

            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
