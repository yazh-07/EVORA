"""F08B real HTTP/SQLite/producers; explicit transactional Neo4j test double."""
import asyncio
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis, graph_projection
from backend.app import create_app
from backend.audit import record_analysis_event
from backend.auth import SyntheticTokenVerifier
from backend.tests.test_analysis import GraphDouble
from backend.tests.test_graph_nodes import validator


class AnalysisAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.neo = GraphDouble()
        self.enterContext(patch.object(analysis, 'Neo4jGraphDatabase', return_value=self.neo))
        self.app = create_app(root / 'audit.sqlite3', storage_dir=root / 'private',
            token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'other': 'investigator-2'}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(transport=ASGITransport(self.app),
            base_url='http://test', headers={'Authorization': 'Bearer local'}))
        response = await self.client.post('/api/v1/cases', json={'title': 'Synthetic F08B'})
        self.assertEqual(response.status_code, 201)
        self.case = response.json()['id']
        self.base = f'/api/v1/cases/{self.case}'

    async def start(self, key=None):
        response = await self.client.post(self.base + '/analysis-runs',
            headers={'Idempotency-Key': key or str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    async def poll(self, run):
        response = await self.client.get(self.base + '/analysis-runs/' + run['id'])
        self.assertEqual(response.status_code, 200, response.text)
        validator('AnalysisRun').validate(response.json())
        return response.json()

    def events(self):
        with self.app.state.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM audit_events WHERE action='startAnalysis' ORDER BY created_at,id")]

    def assert_event(self, run):
        [event] = [row for row in self.events() if row['target_id'] == run['id']]
        expected = f"run:{run['id']};status:{run['status']};version:{run['algorithm_version']}"
        if run['status'] == 'failed':
            expected += ';error:' + run['error']
        self.assertEqual(event, dict(id=event['id'], case_id=self.case, actor_id='investigator-1',
            action='startAnalysis', target_id=run['id'], reason=expected, created_at=run['finished_at']))
        validator('AuditEvent').validate(event)
        return event

    async def test_completed_real_sources_private_link_and_replay(self):
        for name, kind in [('network.csv', 'network_log'), ('gps.csv', 'gps')]:
            data = (Path(__file__).resolve().parents[2] / 'fixtures/synthetic-case' / name).read_bytes()
            response = await self.client.post(self.base + '/evidence',
                data={'kind': kind, 'source_label': 'SYNTHETIC_PRIVATE_SOURCE'},
                files={'file': ('SYNTHETIC_PRIVATE_FILENAME.csv', data, 'text/csv')})
            self.assertEqual(response.status_code, 201, response.text)
            eid = response.json()['id']
            response = await self.client.post(self.base + f'/evidence/{eid}/processing-runs',
                headers={'Idempotency-Key': str(uuid4())})
            self.assertEqual(response.status_code, 202, response.text)
        key = str(uuid4())
        run = await self.poll(await self.start(key))
        self.assertEqual(run['status'], 'completed')
        event = self.assert_event(run)
        with self.app.state.database.connect() as connection:
            private = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (event['target_id'],)).fetchone()
            output = connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (private['id'],)).fetchone()
            self.assertEqual(json.loads(private['input_snapshot_json']), run['input_snapshot'])
            self.assertEqual(len(run['input_snapshot']['processing_run_ids']), 2)
            self.assertTrue(json.loads(output['graph_json'])['nodes'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(event))
        self.assertNotIn('input_snapshot', event)
        self.assertEqual(await self.start(key), run)
        analysis.process_analysis_run(self.app, run['id'])
        graph_projection.rebuild_graph_partition(self.app.state.database, self.neo,
            case_id=self.case, analysis_run_id=run['id'])
        self.assertEqual(self.events(), [event])

    async def test_projection_failure_exactly_once_and_failed_replay(self):
        self.neo.fail = 'connect'
        key = str(uuid4())
        run = await self.poll(await self.start(key))
        self.assertEqual((run['status'], run['error']), ('failed', 'GRAPH_PROJECTION_FAILED'))
        event = self.assert_event(run)
        self.assertEqual(await self.start(key), run)
        analysis.process_analysis_run(self.app, run['id'])
        self.assertEqual(self.events(), [event])

    async def test_early_failure_safe_code_without_private_exception(self):
        with patch.object(analysis, '_outputs', side_effect=ValueError('SYNTHETIC_PRIVATE\n;error:secret')):
            run = await self.poll(await self.start())
        self.assertEqual(run['error'], 'ANALYSIS_FAILED')
        self.assert_event(run)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(self.events()))

    async def test_helper_rejects_nonterminal_and_sanitizes_unknown_error(self):
        accepted = await self.start()
        with self.app.state.database.connect() as connection:
            run = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (accepted['id'],)).fetchone()
            before = self.events()
            for status in ('queued', 'running', '', 'COMPLETED'):
                with self.assertRaises(ValueError):
                    record_analysis_event(connection, run=run, status=status, finished_at=run['created_at'])
            self.assertEqual(self.events(), before)
            # Roll back direct helper probes; production callers own transitions.
            connection.execute('BEGIN')
            for error in ('SYNTHETIC_PRIVATE;error:bad\n/path', None, 'NEW_UNREVIEWED_CODE'):
                record_analysis_event(connection, run=dict(run), status='failed',
                    finished_at=run['created_at'], error=error)
            rows = connection.execute("SELECT reason FROM audit_events WHERE reason LIKE '%;error:%'").fetchall()
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row['reason'].endswith(';error:ANALYSIS_FAILED') for row in rows))
            connection.rollback()
        self.assertEqual(self.events(), before)

    async def test_readback_sorted_paginated_with_fractional_times(self):
        # Mixed whole/fractional UTC controls prove chronological API ordering.
        for timestamp in ('2026-11-03T12:00:01Z', '2026-11-03T12:00:00.1Z', '2026-11-03T12:00:00Z'):
            with patch.object(graph_projection, '_now', return_value=timestamp):
                self.assert_event(await self.poll(await self.start()))
        items = []
        for offset in range(3):
            response = await self.client.get(self.base + '/audit-events', params={'limit': 1, 'offset': offset})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            page = response.json()
            validator('AuditPage').validate(page)
            self.assertEqual(page['total'], 3)
            items.extend(page['items'])
        timestamps = [datetime.fromisoformat(row['created_at']) for row in items]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual({row['id'] for row in items}, {row['id'] for row in self.events()})

    async def test_append_only_update_delete_replace_and_upsert(self):
        self.assert_event(await self.poll(await self.start()))
        before = self.events()
        for sql in ("UPDATE audit_events SET reason='changed'", 'DELETE FROM audit_events',
                'INSERT OR REPLACE INTO audit_events SELECT * FROM audit_events',
                'INSERT INTO audit_events SELECT * FROM audit_events WHERE 1 '
                "ON CONFLICT(id) DO UPDATE SET reason='changed'"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(sql)
        self.assertEqual(self.events(), before)

    async def test_foreign_case_and_actor_isolation(self):
        event = self.assert_event(await self.poll(await self.start()))
        response = await self.client.get(self.base + '/audit-events', headers={'Authorization': 'Bearer other'})
        self.assertEqual(response.status_code, 404)
        other = (await self.client.post('/api/v1/cases', json={'title': 'Other synthetic case'})).json()['id']
        response = await self.client.get(f'/api/v1/cases/{other}/audit-events')
        self.assertEqual(response.json()['items'], [])
        self.assertEqual(response.json()['total'], 0)
        self.assertNotIn(event['id'], response.text)
        response = await self.client.get(f'/api/v1/cases/{uuid4()}/audit-events')
        self.assertEqual(response.status_code, 404)

    async def test_completion_audit_insert_failure_rolls_back_success(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_completed_audit BEFORE INSERT ON audit_events "
                "WHEN NEW.action='startAnalysis' AND NEW.reason LIKE '%;status:completed;%' "
                "BEGIN SELECT RAISE(ABORT,'Synthetic audit failure'); END")
        run = await self.poll(await self.start())
        self.assertEqual((run['status'], run['error']), ('failed', 'GRAPH_PROJECTION_FAILED'))
        self.assert_event(run)
        self.assertIn((self.case, run['id']), self.neo.partitions)
        response = await self.client.get(self.base + '/graph', params={'analysis_run_id': run['id']})
        self.assertEqual(response.status_code, 404)

    async def test_all_audit_insert_failures_leave_run_pending_for_recovery(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_analysis_audit BEFORE INSERT ON audit_events "
                "WHEN NEW.action='startAnalysis' BEGIN SELECT RAISE(ABORT,'Synthetic audit failure'); END")
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'running')
        self.assertNotIn('finished_at', run)
        self.assertEqual(self.events(), [])
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER reject_analysis_audit')
        await analysis.recover_analysis_runs(self.app)
        run = await self.poll(run)
        self.assertEqual(run['status'], 'completed')
        self.assert_event(run)

    async def test_early_failure_audit_write_rollback_and_recovery(self):
        with patch.object(analysis, '_outputs', side_effect=ValueError('synthetic failure')), patch.object(
                analysis, 'record_analysis_event', side_effect=sqlite3.OperationalError('synthetic outage')):
            run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'queued')
        self.assertNotIn('finished_at', run)
        self.assertEqual(self.events(), [])
        await analysis.recover_analysis_runs(self.app)
        self.assertEqual((await self.poll(run))['status'], 'completed')
        self.assert_event(await self.poll(run))

    async def test_failure_status_write_rollback_prevents_audit(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_failed_status BEFORE UPDATE OF status ON analysis_runs "
                "WHEN NEW.status='failed' BEGIN SELECT RAISE(ABORT,'Synthetic status failure'); END")
        self.neo.fail = 'connect'
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'running')
        self.assertEqual(self.events(), [])
        self.neo.fail = None
        await analysis.recover_analysis_runs(self.app)
        self.assert_event(await self.poll(run))

    async def test_completion_status_write_failure_never_logs_completed(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_completed_status BEFORE UPDATE OF status ON analysis_runs "
                "WHEN NEW.status='completed' BEGIN SELECT RAISE(ABORT,'Synthetic status failure'); END")
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'failed')
        self.assert_event(run)

    async def test_sql_commit_failure_rolls_back_completed_event_and_status(self):
        original_db = self.app.state.database

        class CommitFailure:
            @contextmanager
            def connect(inner):
                with original_db.connect() as connection:
                    yield connection
                    if connection.execute("SELECT 1 FROM analysis_runs WHERE status='completed'").fetchone():
                        raise sqlite3.OperationalError('Synthetic SQL commit failure')

        self.app.state.database = CommitFailure()
        try:
            accepted = await self.start()
        finally:
            self.app.state.database = original_db
        run = await self.poll(accepted)
        self.assertEqual((run['status'], run['error']), ('failed', 'GRAPH_PROJECTION_FAILED'))
        self.assert_event(run)
        self.assertEqual(len(self.events()), 1)

    async def test_interruption_after_graph_commit_no_event_until_recovery(self):
        # Exercise the worker directly: SystemExit is the existing crash control.
        with patch.object(analysis, 'run_analysis_job'):
            run = await self.start()
        def crash():
            raise SystemExit('Synthetic interruption')
        self.neo.after_commit = crash
        with self.assertRaises(SystemExit):
            analysis.process_analysis_run(self.app, run['id'])
        self.assertEqual((await self.poll(run))['status'], 'running')
        self.assertEqual(self.events(), [])
        self.neo.after_commit = None
        await analysis.recover_analysis_runs(self.app)
        self.assert_event(await self.poll(run))

    async def test_concurrent_same_key_one_terminal_event(self):
        key = str(uuid4())
        runs = await asyncio.gather(self.start(key), self.start(key))
        self.assertEqual(runs[0]['id'], runs[1]['id'])
        self.assert_event(await self.poll(runs[0]))
        self.assertEqual(len(self.events()), 1)


if __name__ == '__main__':
    unittest.main()
