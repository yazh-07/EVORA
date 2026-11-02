"""P14B actual registered dispatch; labeled scheduling and failure injections."""
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import httpx
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import Actor, CaseAccessGrant, SyntheticTokenVerifier
from backend.errors import AccessError
from backend.processing_provenance import read_processing_provenance
from backend.processing import process_run
from backend.processing_dispatch import ADAPTERS, adapter_for
from backend.parsers import gps_csv, network_csv, messages_csv

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p14b-synthetic-one': 'investigator-1', 'p14b-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p14b-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P14B case'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.case, self.evidence['id'])
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    def base(self, case, evidence):
        return f'/api/v1/cases/{case}/evidence/{evidence}/processing-runs'

    async def upload(self, kind='network_log', data=None, case=None, filename='source.csv', media='text/csv'):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / ('gps.csv' if kind == 'gps' else 'network.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence',
            data={'kind': kind, 'source_label': 'Synthetic P14B'}, files={'file': (filename, data, media)})
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

    async def test_actual_kinds_use_registered_parser_despite_misleading_filename_and_mime(self):
        for kind, filename, media, expected in (
                ('network_log', 'gps.csv', 'image/png', (6, 4, 2)),
                ('gps', 'network.bin', 'application/pdf', (3, 1, 1))):
            evidence = await self.upload(kind, filename=filename, media=media)
            url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json()
            complete = await self.poll(run, url)
            self.assertEqual(complete['status'], 'completed')
            adapter = adapter_for(kind)
            config = json.loads(self.by_run('processing_runs', run)['config_json'])
            self.assertEqual((config['kind'], config['parser_version']), (kind, adapter.parser_version))
            self.assertEqual((config['max_source_bytes'], config['max_data_rows']), (50 * 1024 * 1024, 100000))
            private = self.read(run, evidence)
            self.assertEqual(private['execution']['versions']['parser_version'], adapter.parser_version)
            self.assertEqual(private['execution']['parameters'], dict(max_source_bytes=adapter.max_source_bytes, max_data_rows=adapter.max_data_rows))
            self.assertEqual(private['input']['sha256'], evidence['sha256'])
            self.assertEqual(private['finished_at'], complete['finished_at'])
            for field, count in zip(('observations_json', 'entities_json', 'events_json'), expected):
                self.assertEqual(len(json.loads(self.by_run('processing_outputs', run)[field])), count)
            stored = next(x for x in self.rows('evidence') if x['id'] == evidence['id'])
            self.assertEqual((stored['filename'], stored['media_type']), (filename, media))
            self.validate('ProcessingRun', complete)

    async def test_wrong_layout_never_silently_dispatches_to_other_kind(self):
        for kind, source in [('network_log', 'gps.csv'), ('gps', 'network.csv')]:
            evidence = await self.upload(kind, (ROOT/'fixtures/synthetic-case'/source).read_bytes(), filename=source)
            url = self.base(self.case, evidence['id']); run = (await self.start(str(uuid4()), url)).json()
            self.assertEqual(run['status'], 'queued')
            failed = await self.poll(run, url)
            self.assertEqual((failed['status'], failed['error']), ('failed', 'CSV_INVALID_HEADER'))
            self.denied(run, evidence=evidence)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_every_other_declared_kind_415_before_run_key_or_output_creation(self):
        for kind in ('document', 'image', 'video', 'audio', 'mobile_log', 'transaction'):
            evidence = await self.upload(kind, filename='network.csv')
            response = await self.start('reusable-key', self.base(self.case, evidence['id']))
            self.assertEqual(response.status_code, 415)
            self.validate('ApiError', response.json())
        self.assertEqual(self.rows('processing_runs'), [])
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])
        # Rejection did not reserve this actor/case key; supported target can use it.
        run = (await self.start('reusable-key')).json()
        self.assertEqual(self.read(run)['processing_run_id'], run['id'])

    async def test_malformed_supported_content_fails_with_safe_parser_errors(self):
        network_header = b'timestamp,device_id,ip_address,event\n'
        gps_header = b'timestamp,device_id,latitude,longitude\n'
        samples = [
            ('network_log', b'\xffSECRET', 'CSV_INVALID_UTF8'),
            ('gps', b'\xffSECRET', 'CSV_INVALID_UTF8'),
            ('network_log', network_header + b't,D,SECRET,connected\n', 'CSV_INVALID_IP'),
            ('network_log', network_header + b't,D,127.0.0.1,"SECRET', 'CSV_MALFORMED_CSV'),
            ('gps', gps_header + b'2026-01-12T10:00:00Z,D,91,2\n', 'CSV_INVALID_COORDINATE'),
            ('gps', gps_header + b'SECRET,D,1,2\n', 'CSV_INVALID_TIMESTAMP'),
            ('network_log', network_header + b't,D,127.0.0.1,SECRET\x00\n', 'CSV_MALFORMED_CSV'),
        ]
        for kind, data, error in samples:
            with self.subTest(kind=kind, error=error):
                evidence = await self.upload(kind, data); url = self.base(self.case, evidence['id'])
                run = (await self.start(str(uuid4()), url)).json(); failed = await self.poll(run, url)
                self.assertEqual((failed['status'], failed['error']), ('failed', error))
                self.assertNotIn('SECRET', json.dumps(failed)); self.validate('ProcessingRun', failed)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_bom_multiline_quotes_raw_source_locators_and_hash_preserved(self):
        samples = [
            ('network_log', b'\xef\xbb\xbftimestamp,device_id,ip_address,event\r\n2026-01-12T10:00:00.123456789Z,"D-7\r\nsynthetic",203.0.113.7,"reported, ""quoted"""\r\n'),
            ('gps', b'\xef\xbb\xbftimestamp,device_id,latitude,longitude\r\n2026-01-12T10:00:00,"D-8\r\nsynthetic",+12.971600,7.75946e1\r\n')]
        for kind, data in samples:
            evidence = await self.upload(kind, data); url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json()
            self.assertEqual((await self.poll(run, url))['status'], 'completed')
            output = self.by_run('processing_outputs', run)
            observations = json.loads(output['observations_json'])
            self.assertEqual(len(observations), 3)
            self.assertTrue(all(x['source_locator'].startswith('rows 2-3, ') for x in observations))
            self.assertIn('\r\nsynthetic', observations[0]['raw_value'])
            self.assertEqual(len(json.loads(output['events_json'])), 1)
            if kind == 'gps': self.assertTrue(all('observed_at_utc' not in x for x in observations))
            original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/content")
            self.assertEqual(original.content, data)
            self.assertEqual(self.read(run, evidence)['input']['sha256'], hashlib.sha256(data).hexdigest())

    async def test_header_only_registered_layouts_complete_with_empty_provenance_manifests(self):
        for kind, header in [('network_log', network_csv.HEADER), ('gps', gps_csv.HEADER)]:
            evidence = await self.upload(kind, (','.join(header) + '\n').encode())
            url = self.base(self.case, evidence['id']); run = (await self.start(str(uuid4()), url)).json()
            self.assertEqual((await self.poll(run, url))['status'], 'completed')
            self.assertEqual(self.read(run, evidence)['outputs'], dict(observation_ids=[], entity_ids=[], event_ids=[]))

    async def test_upload_alone_is_not_processing_success_or_derived_output(self):
        self.assertEqual(self.rows('processing_runs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])
        for name in ('observations', 'entities', 'events'):
            self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/{name}')).json()['total'], 0)
        run = (await self.start()).json()
        self.assertEqual((await self.poll(run))['status'], 'completed')
        self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()['total'], 6)

    async def test_replay_precedes_current_selection_and_retains_original_private_record(self):
        run = (await self.start('replay')).json(); private = self.read(run)
        before = {name: self.rows(name) for name in ('processing_runs', 'processing_outputs', 'processing_provenance')}
        with patch('backend.processing.adapter_for', return_value=None) as selection:
            replay = await self.start('replay')
            self.assertEqual(replay.json()['id'], run['id'])
            selection.assert_not_called()
            self.assertEqual((await self.start('new-key')).status_code, 415)
        self.assertEqual({name: self.rows(name) for name in before}, before)
        fresh = (await self.start('new-key')).json()
        self.assertNotEqual(fresh['id'], run['id'])
        self.assertEqual(self.read(run), private)
        self.assertEqual(len(self.rows('processing_provenance')), 2)

    async def test_worker_rejects_changed_registered_version_or_limits_before_parser(self):
        original = adapter_for('network_log')
        for changed in (dict(parser_version='synthetic-new-version'), dict(max_source_bytes=original.max_source_bytes-1),
                        dict(max_data_rows=original.max_data_rows-1)):
            with patch('backend.processing.process_run'):
                run = (await self.start(str(uuid4()))).json()
            parser = Mock(side_effect=AssertionError('Changed selection must not execute'))
            with patch('backend.processing.adapter_for', return_value=replace(original, parse=parser, **changed)):
                process_run(self.app, run['id'])
            parser.assert_not_called()
            self.assertEqual((await self.poll(run))['status'], 'failed')
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])
        retry = (await self.start('fresh')).json()
        self.assertEqual(self.read(retry)['execution']['versions']['parser_version'], original.parser_version)

    async def test_real_row_overflow_on_both_registered_adapters_fails_without_partial_prefix(self):
        for kind, header, row in (
                ('network_log', network_csv.HEADER, b'2026-01-12T10:00:00Z,D-7,203.0.113.7,connected\n'),
                ('gps', gps_csv.HEADER, b'2026-01-12T10:00:00Z,D-8,12,77\n')):
            data = (','.join(header) + '\n').encode() + row * 100001
            evidence = await self.upload(kind, data); url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json(); failed = await self.poll(run, url)
            self.assertEqual((failed['status'], failed['error']), ('failed', 'CSV_ROW_LIMIT'))
            self.denied(run, evidence=evidence)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_bad_late_row_and_new_key_failure_preserve_prior_successful_sources(self):
        good = (await self.start('good')).json(); original = self.read(good)
        data = (ROOT/'fixtures/synthetic-case/network.csv').read_bytes() + b'2026-01-12T10:03:00Z,D-7,SECRET,connected\n'
        evidence = await self.upload(data=data); url = self.base(self.case, evidence['id'])
        failed = (await self.start('bad', url)).json()
        replay = (await self.start('bad', url)).json()
        self.assertEqual(failed['id'], replay['id'])
        retry = (await self.start('bad-retry', url)).json()
        self.assertEqual((await self.poll(retry, url))['status'], 'failed')
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)
        self.assertEqual(self.read(good), original)
        self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()['total'], 6)

    async def test_case_and_actor_denials_happen_before_selection_or_run_creation(self):
        before = self.rows('processing_runs')
        with patch('backend.processing.adapter_for', side_effect=AssertionError('No denied selection')):
            for headers, status in [({'Authorization': 'Bearer p14b-synthetic-two'}, 404), ({'Authorization': 'invalid'}, 401)]:
                response = await self.client.post(self.url, headers=dict(headers, **{'Idempotency-Key': str(uuid4())}))
                self.assertEqual(response.status_code, status)
                self.validate('ApiError', response.json())
            response = await self.start('foreign', self.base(str(uuid4()), self.evidence['id']))
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.rows('processing_runs'), before)


class AdapterRegistryTests(unittest.TestCase):
    def test_registry_and_descriptors_are_immutable_and_use_real_parser_metadata(self):
        self.assertEqual(set(ADAPTERS), {'network_log', 'gps', 'message'})
        for kind, module in [('network_log', network_csv), ('gps', gps_csv), ('message', messages_csv)]:
            adapter = adapter_for(kind)
            parser_name = {'network_log': 'parse_network_csv', 'gps': 'parse_gps_csv', 'message': 'parse_messages_csv'}[kind]
            self.assertIs(adapter.parse, getattr(module, parser_name))
            self.assertEqual((adapter.kind, adapter.parser_version, adapter.max_source_bytes, adapter.max_data_rows),
                             (kind, module.PARSER_VERSION, module.MAX_SOURCE_BYTES, module.MAX_DATA_ROWS))
            with self.assertRaises(FrozenInstanceError): adapter.parser_version = 'changed'
        with self.assertRaises(TypeError): ADAPTERS['document'] = adapter_for('gps')
        for kind in ('document', 'GPS', 'network.csv', ''): self.assertIsNone(adapter_for(kind))



class DispatchLoopbackTests(unittest.TestCase):
    def test_real_http_dispatch_layout_mismatch_unsupported_and_private_provenance(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as port_socket:
                port_socket.bind(('127.0.0.1', 0))
                port = port_socket.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; root=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(root/"db.sqlite3",storage_dir=root/"private",token_verifier='
                    'SyntheticTokenVerifier({"p14b-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([PYTHON, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p14b-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            ready = client.get('/api/v1/cases')
                            if ready.status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P14B HTTP'}).json()['id']
                    for kind, data, expected in [('network_log', (ROOT/'fixtures/synthetic-case/network.csv').read_bytes(), 'completed'),
                                               ('gps', (ROOT/'fixtures/synthetic-case/gps.csv').read_bytes(), 'completed'),
                                               ('network_log', b'bad header\n', 'failed'),
                                               ('network_log', (ROOT/'fixtures/synthetic-case/gps.csv').read_bytes(), 'failed'),
                                               ('gps', (ROOT/'fixtures/synthetic-case/network.csv').read_bytes(), 'failed')]:
                        evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': kind, 'source_label': 'Synthetic HTTP'},
                                               files={'file': ('misleading.bin', data, 'application/octet-stream')}).json()
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
                    evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': 'document', 'source_label': 'Synthetic unsupported'},
                        files={'file': ('network.csv', (ROOT/'fixtures/synthetic-case/network.csv').read_bytes(), 'text/csv')}).json()
                    unsupported_url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                    self.assertEqual(client.post(unsupported_url, headers={'Idempotency-Key': str(uuid4())}).status_code, 415)
                    self.assertEqual(client.get(unsupported_url).json(), [])
                    with closing(sqlite3.connect(Path(directory)/'db.sqlite3')) as connection:
                        self.assertEqual(connection.execute('SELECT count(*) FROM processing_provenance').fetchone()[0], 2)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/observations').json()['total'], 9)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/entities').json()['total'], 5)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/events').json()['total'], 3)


            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
