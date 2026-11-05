"""F08 terminal audit against real processing, SQLite and case-scoped HTTP APIs."""
import asyncio
from datetime import datetime
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.processing import initialize_processing, process_run, publish_outputs


class ProcessingAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.app = create_app(self.root / 'audit.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({
                'f08-synthetic-one': 'investigator-1', 'f08-synthetic-two': 'investigator-2'}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(transport=ASGITransport(self.app),
            base_url='http://test', headers={'Authorization': 'Bearer f08-synthetic-one'}))
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic F08'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.case, self.evidence['id'])
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    def base(self, case, evidence):
        return f'/api/v1/cases/{case}/evidence/{evidence}/processing-runs'

    async def upload(self, data=None, kind='network_log', case=None, headers=None):
        if data is None:
            data = (Path(__file__).resolve().parents[2] / 'fixtures/synthetic-case/network.csv').read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence',
            headers=headers, data={'kind': kind, 'source_label': 'SYNTHETIC_PRIVATE_SOURCE'},
            files={'file': ('SYNTHETIC_PRIVATE_FILENAME.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def start(self, key='f08-key', url=None, headers=None):
        response = await self.client.post(url or self.url,
            headers={'Idempotency-Key': key, **(headers or {})})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    async def poll(self, run, url=None):
        response = await self.client.get((url or self.url) + '/' + run['id'])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def rows(self, table):
        with self.app.state.database.connect() as connection:
            return [dict(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')]

    def events(self):
        return [row for row in self.rows('audit_events') if row['action'] == 'startProcessing']

    def validate(self, name, value):
        Draft202012Validator({'$ref': '#/components/schemas/' + name,
            'components': self.bundle['components']}, format_checker=FormatChecker()).validate(value)

    def assert_event(self, run, actor='investigator-1'):
        [event] = [event for event in self.events() if f"run:{run['id']};" in event['reason']]
        UUID(event['id'])
        reason = f"run:{run['id']};status:{run['status']};version:{run['processor_version']}"
        if run['status'] == 'failed':
            reason += ';error:' + run['error']
        self.assertEqual(event, dict(id=event['id'], case_id=run['case_id'], actor_id=actor,
            action='startProcessing', target_id=run['evidence_id'], created_at=run['finished_at'], reason=reason))
        self.validate('AuditEvent', event)
        self.assertEqual(datetime.fromisoformat(event['created_at']).utcoffset().total_seconds(), 0)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(event))
        return event

    async def test_completed_run_links_safe_audit_to_private_versioned_provenance(self):
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'completed')
        event = self.assert_event(run)
        self.assertEqual(len(self.events()), 1)
        [private] = self.rows('processing_provenance')
        self.assertEqual(private['run_id'], run['id'])
        self.assertEqual(private['finished_at'], event['created_at'])
        self.assertEqual(private['evidence_id'], event['target_id'])
        self.assertEqual(private['case_id'], event['case_id'])
        payload = json.loads(private['payload_json'])
        self.assertEqual(payload['execution']['versions']['processor_version'], run['processor_version'])
        self.assertNotIn('parameters', event['reason'])

    async def test_parser_failure_records_only_safe_diagnostic_and_no_partial_outputs(self):
        evidence = await self.upload(b'timestamp,device_id,ip_address,event\n'
            b'2026-01-01T00:00:00Z,D-7,SYNTHETIC_PRIVATE_CELL,connected\n')
        url = self.base(self.case, evidence['id'])
        run = await self.poll(await self.start(url=url), url)
        self.assertEqual((run['status'], run['error']), ('failed', 'CSV_INVALID_IP'))
        self.assert_event(run)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_completed_and_failed_key_replay_and_duplicate_worker_do_not_duplicate_events(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                key = str(failure)
                if failure:
                    with patch('backend.processing.process_run'):
                        accepted = await self.start(key)
                    with patch('backend.processing.adapter_for', side_effect=ValueError('SYNTHETIC_PRIVATE_ERROR')):
                        await asyncio.to_thread(process_run, self.app, accepted['id'])
                else:
                    accepted = await self.start(key)
                run = await self.poll(accepted)
                self.assertEqual(run['status'], 'failed' if failure else 'completed')
                self.assert_event(run)
                before = self.rows('audit_events')
                self.assertEqual(await self.start(key), run)
                await asyncio.to_thread(process_run, self.app, run['id'])
                initialize_processing(self.app.state.database)
                self.assertEqual(self.rows('audit_events'), before)
        self.assertEqual(len(self.events()), 2)

    async def test_concurrent_same_key_starts_and_workers_append_one_event(self):
        with patch('backend.processing.process_run'):
            runs = await asyncio.gather(*(self.start() for _ in range(4)))
        self.assertEqual(len({run['id'] for run in runs}), 1)
        self.assertEqual(self.events(), [])
        await asyncio.gather(*(asyncio.to_thread(process_run, self.app, runs[0]['id']) for _ in range(3)))
        self.assert_event(await self.poll(runs[0]))
        self.assertEqual(len(self.events()), 1)

    async def test_audit_listing_utc_order_pagination_and_case_actor_isolation(self):
        # Whole-second and fractional UTC values must sort chronologically.
        ordered = []
        for index, stamp in enumerate(('2099-01-01T00:00:00Z', '2099-01-01T00:00:00.000001Z',
                                       '2099-01-01T00:00:00.1Z')):
            with patch('backend.processing._now', return_value=stamp):
                run = await self.poll(await self.start(str(index)))
            ordered.append(self.assert_event(run))
        path = f'/api/v1/cases/{self.case}/audit-events'
        response = await self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        page = response.json()
        self.validate('AuditPage', page)
        listed = [item for item in page['items'] if item['action'] == 'startProcessing']
        self.assertEqual([item['id'] for item in listed], [item['id'] for item in ordered])
        self.assertEqual([datetime.fromisoformat(item['created_at']) for item in listed],
                         [datetime.fromisoformat(item['created_at']) for item in ordered])
        paginated = []
        for offset in range(page['total']):
            result = (await self.client.get(path, params={'limit': 1, 'offset': offset})).json()
            self.validate('AuditPage', result)
            paginated.extend(result['items'])
        self.assertEqual(paginated, page['items'])
        headers = {'Authorization': 'Bearer f08-synthetic-two'}
        case_b = (await self.client.post('/api/v1/cases', headers=headers,
            json={'title': 'Synthetic other actor'})).json()['id']
        evidence_b = await self.upload(case=case_b, headers=headers)
        await self.start(url=self.base(case_b, evidence_b['id']), headers=headers)
        own_b = await self.client.get(f'/api/v1/cases/{case_b}/audit-events', headers=headers)
        self.validate('AuditPage', own_b.json())
        self.assertTrue(all(item['actor_id'] == 'investigator-2' and item['case_id'] == case_b
                            for item in own_b.json()['items']))
        self.assertEqual(sum(item['action'] == 'startProcessing' for item in own_b.json()['items']), 1)
        for case, auth in ((self.case, headers), (case_b, None), (str(uuid4()), None)):
            denied = await self.client.get(f'/api/v1/cases/{case}/audit-events', headers=auth)
            self.assertEqual(denied.status_code, 404)
            self.validate('ApiError', denied.json())
            self.assertEqual(denied.json(), {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.assertEqual((await self.client.get(path)).status_code, 404)

    async def test_processing_events_are_append_only_including_replace_and_upsert(self):
        event = self.assert_event(await self.poll(await self.start()))
        original = self.rows('audit_events')
        columns, values = ','.join(event), tuple(event.values())
        placeholders = ','.join('?' for _ in values)
        for statement, args in (
            ('UPDATE audit_events SET reason=? WHERE id=?', ('changed', event['id'])),
            ('DELETE FROM audit_events WHERE id=?', (event['id'],)),
            (f'INSERT OR REPLACE INTO audit_events ({columns}) VALUES ({placeholders})', values),
            (f'INSERT INTO audit_events ({columns}) VALUES ({placeholders}) '
             'ON CONFLICT(id) DO UPDATE SET reason=excluded.reason', values),
        ):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
                    with self.app.state.database.connect() as connection:
                        connection.execute(statement, args)
                self.assertEqual(self.rows('audit_events'), original)

    async def test_rollback_after_completed_audit_leaves_only_failed_event(self):
        def fail_after_publication(connection, run, output):
            publish_outputs(connection, run, output)
            raise RuntimeError('SYNTHETIC_PRIVATE_AFTER_AUDIT')
        with patch('backend.processing.publish_outputs', side_effect=fail_after_publication):
            accepted = await self.start()
        run = await self.poll(accepted)
        self.assertEqual((run['status'], run['error']), ('failed', 'PROCESSING_FAILED'))
        self.assert_event(run)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_completion_audit_insert_failure_rolls_back_outputs_and_success(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_completed_audit BEFORE INSERT ON audit_events "
                "WHEN NEW.action='startProcessing' AND NEW.reason LIKE '%;status:completed;%' "
                "BEGIN SELECT RAISE(ABORT,'Synthetic audit failure'); END")
        run = await self.poll(await self.start())
        self.assertEqual((run['status'], run['error']), ('failed', 'PROCESSING_FAILED'))
        self.assert_event(run)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.rows('processing_outputs'), [])
        self.assertEqual(self.rows('processing_provenance'), [])

    async def test_commit_failure_rolls_back_completed_event_output_and_provenance(self):
        with self.app.state.database.connect() as connection:
            connection.execute('CREATE TABLE fail_commit (case_id TEXT REFERENCES cases(id) '
                               'DEFERRABLE INITIALLY DEFERRED)')
            connection.execute("CREATE TRIGGER fail_completion_commit AFTER INSERT ON audit_events "
                "WHEN NEW.action='startProcessing' AND NEW.reason LIKE '%;status:completed;%' "
                "BEGIN INSERT INTO fail_commit VALUES ('synthetic-missing-case'); END")
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'failed')
        self.assert_event(run)
        self.assertEqual(len(self.events()), 1)
        for table in ('processing_outputs', 'processing_provenance', 'fail_commit'):
            self.assertEqual(self.rows(table), [])

    async def test_failure_audit_failure_leaves_nonterminal_run_for_audited_recovery(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_terminal_audit BEFORE INSERT ON audit_events "
                "WHEN NEW.action='startProcessing' BEGIN SELECT RAISE(ABORT,'Synthetic failure'); END")
        # Intake needs the real registry; hold the job before injecting rejection.
        with patch('backend.processing.process_run'):
            accepted = await self.start()
        with patch('backend.processing.adapter_for', side_effect=ValueError('SYNTHETIC_PRIVATE_ERROR')):
            await asyncio.to_thread(process_run, self.app, accepted['id'])
        run = await self.poll(accepted)
        self.assertEqual(run['status'], 'running')
        self.assertNotIn('finished_at', run)
        self.assertEqual(self.events(), [])
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER fail_terminal_audit')
        initialize_processing(self.app.state.database)
        failed = await self.poll(accepted)
        self.assertEqual(failed['error'], 'PROCESSING_INTERRUPTED')
        self.assert_event(failed)
        self.assertEqual(len(self.events()), 1)

    async def test_startup_recovery_audits_queued_and_running_once_and_rolls_back_on_failure(self):
        with patch('backend.processing.process_run'):
            queued, running = await self.start('queued'), await self.start('running')
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running['id'],))
            connection.execute("CREATE TRIGGER fail_recovery BEFORE INSERT ON audit_events "
                "WHEN NEW.action='startProcessing' AND NEW.target_id IS NOT NULL "
                "BEGIN SELECT RAISE(ABORT,'Synthetic recovery failure'); END")
        before = self.rows('processing_runs')
        with self.assertRaises(sqlite3.IntegrityError):
            initialize_processing(self.app.state.database)
        self.assertEqual(self.rows('processing_runs'), before)
        self.assertEqual(self.events(), [])
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER fail_recovery')
        initialize_processing(self.app.state.database)
        for accepted in (queued, running):
            failed = await self.poll(accepted)
            self.assertEqual(failed['error'], 'PROCESSING_INTERRUPTED')
            self.assert_event(failed)
        before = self.rows('audit_events')
        initialize_processing(self.app.state.database)
        self.assertEqual(self.rows('audit_events'), before)
        self.assertEqual(len(self.events()), 2)

    async def test_unknown_diagnostic_and_exception_text_never_enter_public_audit_or_logs(self):
        from backend.parsers.network_csv import NetworkCSVError
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        logger = logging.getLogger()
        previous = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            await self.start('SYNTHETIC_PRIVATE_KEY')
            malformed = await self.upload(b'timestamp,device_id,ip_address,event\n'
                b'2026-01-01T00:00:00Z,D-7,SYNTHETIC_PRIVATE_CELL,connected\n')
            url = self.base(self.case, malformed['id'])
            self.assert_event(await self.poll(await self.start('malformed', url), url))
            with patch('backend.processing.process_run'):
                accepted = await self.start('failure')
            with patch('backend.processing.adapter_for',
                       side_effect=NetworkCSVError('SYNTHETIC_PRIVATE_CODE;/private/file;token=secret')):
                await asyncio.to_thread(process_run, self.app, accepted['id'])
            failed = await self.poll(accepted)
            self.assertEqual(failed['status'], 'failed')
            [event] = [event for event in self.events() if f"run:{accepted['id']};" in event['reason']]
            self.assertTrue(event['reason'].endswith(';error:PROCESSING_FAILED'))
            await self.client.get(f'/api/v1/cases/{self.case}/audit-events')
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous)
            handler.close()
        public = json.dumps(self.rows('audit_events'))
        for value in ('SYNTHETIC_PRIVATE', '/private/file', 'token=secret', str(self.root)):
            self.assertNotIn(value, captured.getvalue())
            self.assertNotIn(value, public)

    async def test_pre_intake_adapter_rejection_produces_no_processing_event(self):
        evidence = await self.upload(kind='audio')
        response = await self.client.post(self.base(self.case, evidence['id']),
                                          headers={'Idempotency-Key': 'unsupported'})
        self.assertEqual(response.status_code, 415)
        self.validate('ApiError', response.json())
        self.assertEqual(self.rows('processing_runs'), [])
        self.assertEqual(self.events(), [])
