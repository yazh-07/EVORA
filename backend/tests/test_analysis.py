"""A05 real HTTP/SQLite/processing tests; explicit transactional Neo4j double."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.graph_db import Neo4jGraphDatabase
from backend import graph_projection as projection
from backend.tests.test_graph_nodes import validator
from backend.tests.test_graph_projection import SyntheticNeo4j

ROOT = Path(__file__).resolve().parents[2]


class GraphDouble(SyntheticNeo4j):
    def close(self):
        pass


class AnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.neo = GraphDouble()
        self.factory = patch.object(analysis, 'Neo4jGraphDatabase', return_value=self.neo)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
            token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'other': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.addAsyncCleanup(self.life.__aexit__, None, None, None)
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
                                  headers={'Authorization': 'Bearer local'})
        self.addAsyncCleanup(self.client.aclose)
        response = await self.client.post('/api/v1/cases', json={'title': 'Synthetic A05'})
        self.case = response.json()['id']
        self.base = f'/api/v1/cases/{self.case}'
        self.path = self.base + '/analysis-runs'

    async def upload(self, name='network.csv', kind='network_log', process=True):
        data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
        if kind == 'gps':
            # Permitted extra row supplies the shared D-7 positive control.
            data += b'2026-01-12T10:03:00Z,D-7,12.9716,77.5946\n'
        response = await self.client.post(self.base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic'},
            files={'file': (name, data, 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        evidence = response.json()
        run = await self.process(evidence['id']) if process else None
        return evidence, run

    async def process(self, eid):
        path = self.base + f'/evidence/{eid}/processing-runs'
        response = await self.client.post(path, headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        run = (await self.client.get(path + '/' + response.json()['id'])).json()
        self.assertEqual(run['status'], 'completed', run)
        return run

    async def start(self, key=None):
        response = await self.client.post(self.path, headers={'Idempotency-Key': key or str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        validator('AnalysisRun').validate(response.json())
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    async def poll(self, run):
        response = await self.client.get(self.path + '/' + run['id'])
        self.assertEqual(response.status_code, 200, response.text)
        validator('AnalysisRun').validate(response.json())
        return response.json()

    async def test_real_network_gps_pipeline_and_exact_snapshot(self):
        evidence = [await self.upload(), await self.upload('gps.csv', 'gps'), await self.upload(process=False)]
        accepted = await self.start()
        self.assertEqual((accepted['status'], accepted['trigger']), ('queued', 'initial'))
        completed = await self.poll(accepted)
        self.assertEqual(completed['status'], 'completed', completed)
        self.assertIn('finished_at', completed)
        snap = completed['input_snapshot']
        self.assertEqual(snap, analysis.freeze_analysis_input_snapshot(self.app.state.database, self.case))
        self.assertEqual(snap['evidence_ids'], sorted(e['id'] for e, _ in evidence))
        self.assertEqual(snap['processing_run_ids'], sorted(r['id'] for _, r in evidence if r))
        with self.app.state.database.connect() as connection:
            oids = [o['id'] for row in connection.execute('SELECT observations_json FROM processing_outputs')
                    for o in json.loads(row['observations_json'])]
            output = connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (accepted['id'],)).fetchone()
            graph, findings, triage = [json.loads(output[key]) for key in ('graph_json', 'findings_json', 'triage_json')]
        self.assertEqual(snap['observation_ids'], sorted(oids))
        self.assertEqual(snap['sha256'], hashlib.sha256(json.dumps({k: v for k, v in snap.items() if k != 'sha256'},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest())
        validator('Graph').validate(graph)
        self.assertTrue(graph['edges'])
        self.assertTrue(findings)
        self.assertEqual({r['evidence_id'] for r in triage}, {e['id'] for e, r in evidence if r})
        for finding in findings:
            validator('Finding').validate(finding)
        for result in triage:
            validator('TriageResult').validate(result)
            self.assertEqual(result['analysis_run_id'], accepted['id'])
        self.assertEqual(projection.get_projected_graph(self.app.state.database, self.neo,
            case_id=self.case, analysis_run_id=accepted['id']), graph)

    async def test_replay_before_freeze_new_key_and_all_triggers(self):
        eid, _ = await self.upload()
        key = str(uuid4())
        initial = await self.start(key)
        original = await self.poll(initial)
        manual = await self.start()
        self.assertEqual(manual['trigger'], 'manual')
        await self.process(eid['id'])  # Same counts, different immutable run/observation IDs.
        with patch.object(analysis, 'freeze_analysis_input_snapshot', side_effect=AssertionError('resnapshot')):
            self.assertEqual(await self.start(key), original)
        changed = await self.start()
        self.assertEqual(changed['trigger'], 'new_observations')
        self.assertNotEqual(changed['input_snapshot']['sha256'], initial['input_snapshot']['sha256'])
        await self.upload(process=False)
        self.assertEqual((await self.start())['trigger'], 'new_observations')
        self.assertEqual(await self.poll(initial), original)

    async def test_publication_verification_failure_and_new_key_retry(self):
        await self.upload()
        self.neo.corrupt = 'property'
        key = str(uuid4())
        accepted = await self.start(key)
        failed = await self.poll(accepted)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error'], 'GRAPH_PROJECTION_FAILED')
        self.assertNotIn('synthetic-private', json.dumps(failed))
        self.assertEqual(await self.start(key), failed)
        with self.assertRaises(Exception):
            projection.get_projected_graph(self.app.state.database, self.neo,
                case_id=self.case, analysis_run_id=accepted['id'])
        self.neo.corrupt = None
        retry = await self.start()
        self.assertEqual((await self.poll(retry))['status'], 'completed')
        self.assertEqual(retry['trigger'], 'initial')  # No previous completed analysis.

    async def test_pipeline_failure_sanitized_without_outputs(self):
        with patch.object(analysis, 'build_graph_nodes', side_effect=ValueError('private detail')):
            failed = await self.poll(await self.start())
        self.assertEqual(failed['error'], 'ANALYSIS_FAILED')
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM analysis_outputs').fetchone()[0], 0)

    async def test_invalid_input_and_case_isolation(self):
        for headers, content, suffix in (({}, None, ''), ({'Idempotency-Key': 'bad'}, None, ''),
                ({'Idempotency-Key': str(uuid4())}, b'{}', ''),
                ({'Idempotency-Key': str(uuid4())}, None, '?extra=1'),
                ([('Idempotency-Key', str(uuid4())), ('Idempotency-Key', str(uuid4()))], None, '')):
            response = await self.client.post(self.path + suffix, headers=headers, content=content)
            self.assertEqual(response.status_code, 400, response.text)
            validator('ApiError').validate(response.json())
        run = await self.start()
        other = (await self.client.post('/api/v1/cases', json={'title': 'Other owned case'})).json()['id']
        for path in (self.path, self.path + '/' + run['id']):
            response = await self.client.get(path, headers={'Authorization': 'Bearer other'})
            self.assertEqual(response.status_code, 404)
        for path in (f'/api/v1/cases/{other}/analysis-runs/{run["id"]}', self.path + '/' + str(uuid4())):
            self.assertEqual((await self.client.get(path)).status_code, 404)
        self.assertEqual((await self.client.get(self.path + '/bad')).status_code, 400)
        self.assertEqual((await self.client.get(self.path, headers={'Authorization': 'bad'})).status_code, 401)

    async def test_concurrent_same_key_creates_one_run(self):
        key = str(uuid4())
        async def submit():
            async with AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
                    headers={'Authorization': 'Bearer local'}) as client:
                response = await client.post(self.path, headers={'Idempotency-Key': key})
                self.assertEqual(response.status_code, 202, response.text)
                return response.json()
        # Separate event loops/threads exercise independent SQLite writers.
        with patch.object(analysis, 'run_analysis_job'):
            runs = await asyncio.gather(*(asyncio.to_thread(asyncio.run, submit()) for _ in range(6)))
        self.assertEqual(len({r['id'] for r in runs}), 1)
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM analysis_runs').fetchone()[0], 1)
        await analysis.recover_analysis_runs(self.app)
        self.assertEqual((await self.poll(runs[0]))['status'], 'completed')

    async def test_queued_snapshot_survives_later_upload_and_startup_recovery(self):
        with patch.object(analysis, 'run_analysis_job'):
            accepted = await self.start()
        await self.upload()
        await analysis.recover_analysis_runs(self.app)
        completed = await self.poll(accepted)
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['input_snapshot'], accepted['input_snapshot'])
        self.assertEqual(completed['input_snapshot']['evidence_ids'], [])

    async def test_crash_after_graph_commit_resumes_persisted_outputs_on_restart(self):
        await self.upload()
        with patch.object(analysis, 'run_analysis_job'):
            accepted = await self.start()
        def crash():
            raise SystemExit('Synthetic crash')
        self.app.state.graph_database = self.neo
        self.neo.after_commit = crash
        with self.assertRaises(SystemExit):
            analysis.process_analysis_run(self.app, accepted['id'])
        self.neo.after_commit = None
        self.assertEqual((await self.poll(accepted))['status'], 'running')
        with patch.object(analysis, '_outputs', side_effect=AssertionError('recompute')):
            async with self.app.router.lifespan_context(self.app):
                self.assertEqual((await self.poll(accepted))['status'], 'completed')

    async def test_revoked_membership_fails_queued_run(self):
        with patch.object(analysis, 'run_analysis_job'):
            accepted = await self.start()
        with patch.object(self.app.state.case_access, 'allows', return_value=False):
            analysis.process_analysis_run(self.app, accepted['id'])
        self.assertEqual((await self.poll(accepted))['status'], 'failed')

    async def test_latest_processing_run_uses_utc_then_uuid_tie(self):
        evidence, first = await self.upload()
        second = await self.process(evidence['id'])
        with self.app.state.database.connect() as connection:
            # Synthetic equal instants with different timezone representations.
            connection.execute('DROP TRIGGER processing_run_terminal')
            connection.execute('UPDATE processing_runs SET finished_at=? WHERE id=?',
                ('2026-11-03T12:00:00Z', first['id']))
            connection.execute('UPDATE processing_runs SET finished_at=? WHERE id=?',
                ('2026-11-03T13:00:00+01:00', second['id']))
        snap = analysis.freeze_analysis_input_snapshot(self.app.state.database, self.case)
        self.assertEqual(snap['processing_run_ids'], [max(first['id'], second['id'])])

    @unittest.skipUnless(os.environ.get('EVORA_NEO4J_INTEGRATION') == '1', 'Opt-in disposable real Neo4j')
    async def test_real_neo4j_http_processing_analysis_and_readback(self):
        self.neo = Neo4jGraphDatabase()
        self.app.state.graph_database = self.neo
        try:
            await self.test_real_network_gps_pipeline_and_exact_snapshot()
        finally:
            with self.app.state.database.connect() as connection:
                runs = [row['id'] for row in connection.execute('SELECT id FROM analysis_runs')]
            with self.neo.get_driver().session(database=self.neo.config.database) as session:
                for run in runs:
                    for query in (projection._DELETE_EDGES, projection._DELETE_NODES):
                        session.run(query, case_id=self.case, run_id=run).consume()

    async def test_snapshot_freeze_failure_rolls_back_acceptance(self):
        with patch.object(analysis, 'freeze_analysis_input_snapshot', side_effect=ValueError('Internal source failure')):
            with self.assertRaises(ValueError):
                await self.start()
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM analysis_runs').fetchone()[0], 0)

    async def test_algorithm_and_trigger_are_frozen_even_before_execution(self):
        import sqlite3
        with patch.object(analysis, 'run_analysis_job'):
            accepted = await self.start()
        for field in ('trigger', 'algorithm_version', 'input_snapshot_json'):
            with self.subTest(field=field), self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(f'UPDATE analysis_runs SET {field}=? WHERE id=?', ('manual', accepted['id']))
        await analysis.recover_analysis_runs(self.app)
        self.assertEqual((await self.poll(accepted))['status'], 'completed')

    async def test_list_analysis_runs_returns_array_in_creation_order(self):
        first = await self.start()
        second = await self.start(str(uuid4()))
        response = await self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)
        self.assertEqual([item['id'] for item in items], [first['id'], second['id']])
