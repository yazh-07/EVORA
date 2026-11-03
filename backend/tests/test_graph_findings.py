"""A05B HTTP/SQLite reads using real A05/processing, explicit Neo4j double."""
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import analysis
from backend.graph_db import Neo4jGraphDatabase
from backend import graph_projection as projection
from backend.tests import test_analysis as lifecycle
from backend.tests.test_graph_nodes import validator


class GraphFindingsTests(unittest.IsolatedAsyncioTestCase):
    # Reuse lifecycle harness/helpers without inheriting its unrelated test cases.
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll

    async def read(self, endpoint, params=None, base=None):
        response = await self.client.get((base or self.base) + '/' + endpoint, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        validator('Graph' if endpoint == 'graph' else 'FindingPage').validate(response.json())
        return response.json()

    async def populated(self):
        await self.upload()
        await self.upload()
        await self.upload('gps.csv', 'gps')
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'completed')
        with self.app.state.database.connect() as connection:
            row = connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (run['id'],)).fetchone()
        return run, json.loads(row['graph_json']), json.loads(row['findings_json'])

    def assert_missing(self, response):
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json(), {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
        validator('ApiError').validate(response.json())

    async def test_no_completed_run(self):
        self.assertEqual(await self.read('graph'), dict(case_id=self.case, nodes=[], edges=[]))
        self.assertEqual(await self.read('findings'), dict(items=[], total=0, limit=20, offset=0))
        self.assertEqual(await self.read('findings', {'limit': 100, 'offset': 200}),
                         dict(items=[], total=0, limit=100, offset=200))

    async def test_completed_graph_and_paginated_findings_match_sql(self):
        run, graph, findings = await self.populated()
        self.assertTrue(graph['nodes'])
        self.assertTrue(graph['edges'])
        self.assertGreater(len(findings), 1)
        self.assertEqual(await self.read('graph'), graph)
        for offset in (0, 1, len(findings), len(findings) + 100):
            with self.subTest(offset=offset):
                self.assertEqual(await self.read('findings', {'limit': 1, 'offset': offset}),
                    dict(items=findings[offset:offset + 1], total=len(findings), limit=1,
                         offset=offset, analysis_run_id=run['id']))

    async def test_completed_empty_snapshot_keeps_run_id(self):
        run = await self.start()
        self.assertEqual(await self.read('graph'),
                         dict(case_id=self.case, nodes=[], edges=[], analysis_run_id=run['id']))
        self.assertEqual(await self.read('findings', {'offset': 30}),
                         dict(items=[], total=0, limit=20, offset=30, analysis_run_id=run['id']))

    async def test_historical_pin_and_pages_survive_new_upload_and_publication(self):
        old, graph, findings = await self.populated()
        first = await self.read('findings', {'analysis_run_id': old['id'], 'limit': 1})
        await self.upload()
        new = await self.start()
        self.assertNotEqual(new['id'], old['id'])
        self.assertEqual((await self.read('graph'))['analysis_run_id'], new['id'])
        self.assertEqual((await self.read('findings'))['analysis_run_id'], new['id'])
        self.assertEqual(await self.read('graph', {'analysis_run_id': old['id']}), graph)
        items = first['items']
        for offset in range(1, len(findings)):
            page = await self.read('findings', {'analysis_run_id': old['id'], 'limit': 1, 'offset': offset})
            self.assertEqual((page['total'], page['analysis_run_id']), (len(findings), old['id']))
            items.extend(page['items'])
        self.assertEqual(items, findings)

    async def test_invalid_selectors_and_case_access(self):
        completed = await self.start()
        with patch.object(analysis, 'run_analysis_job'):
            queued = await self.start()
            running = await self.start()
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE analysis_runs SET status='running' WHERE id=?", (running['id'],))
        await self.upload()  # Property corruption needs a nonempty partition.
        self.neo.corrupt = 'property'
        failed = await self.poll(await self.start())
        self.assertEqual(failed['status'], 'failed')
        other = (await self.client.post('/api/v1/cases', json={'title': 'Other owned case'})).json()['id']
        for endpoint in ('graph', 'findings'):
            for run_id in (queued['id'], running['id'], failed['id'], str(uuid4())):
                self.assert_missing(await self.client.get(self.base + '/' + endpoint,
                                                          params={'analysis_run_id': run_id}))
            self.assert_missing(await self.client.get(f'/api/v1/cases/{other}/{endpoint}',
                                                      params={'analysis_run_id': completed['id']}))
            self.assert_missing(await self.client.get(self.base + '/' + endpoint,
                                                      headers={'Authorization': 'Bearer other'}))
            self.assert_missing(await self.client.get(f'/api/v1/cases/{uuid4()}/{endpoint}'))
            response = await self.client.get(self.base + '/' + endpoint, headers={'Authorization': 'bad'})
            self.assertEqual(response.status_code, 401)
            validator('ApiError').validate(response.json())
            # More recent pending/failed rows do not displace the completed run.
            self.assertEqual((await self.read(endpoint))['analysis_run_id'], completed['id'])

    async def test_persisted_unverified_partition_hidden_until_sql_publication(self):
        with patch.object(analysis, 'run_analysis_job'):
            run = await self.start()
        def crash():
            raise SystemExit('Synthetic crash after graph commit')
        self.neo.after_commit = crash
        self.app.state.graph_database = self.neo
        with self.assertRaises(SystemExit):
            analysis.process_analysis_run(self.app, run['id'])
        self.neo.after_commit = None
        with self.app.state.database.connect() as connection:
            self.assertIsNotNone(connection.execute('SELECT 1 FROM analysis_outputs WHERE run_id=?',
                                                    (run['id'],)).fetchone())
        await self.test_no_completed_run()
        for endpoint in ('graph', 'findings'):
            self.assert_missing(await self.client.get(self.base + '/' + endpoint,
                                                      params={'analysis_run_id': run['id']}))
        await analysis.recover_analysis_runs(self.app)
        self.assertEqual((await self.read('graph'))['analysis_run_id'], run['id'])

    async def test_latest_orders_by_created_utc_then_uuid_not_finish_time(self):
        first = await self.start()
        second = await self.start()
        async def set_times(a, b):
            with self.app.state.database.connect() as connection:
                # Controlled fixture mutation only; production history stays immutable.
                connection.execute('DROP TRIGGER IF EXISTS analysis_run_frozen')
                connection.execute('DROP TRIGGER IF EXISTS analysis_run_terminal')
                for run, timestamp in ((first, a), (second, b)):
                    connection.execute('UPDATE analysis_runs SET created_at=? WHERE id=?', (timestamp, run['id']))
        for a, b, expected in (
            ('2026-11-03T23:00:00-02:00', '2026-11-04T00:00:00Z', first['id']),
            ('2026-11-03T12:00:00Z', '2026-11-03T13:00:00+01:00', max(first['id'], second['id'])),
        ):
            await set_times(a, b)
            for endpoint in ('graph', 'findings'):
                self.assertEqual((await self.read(endpoint))['analysis_run_id'], expected)

    async def test_invalid_input_is_safe_400(self):
        for endpoint, queries in (
            ('graph', ['analysis_run_id=bad', 'analysis_run_id=', 'limit=1', 'extra=private',
                       f'analysis_run_id={uuid4()}&analysis_run_id={uuid4()}']),
            ('findings', ['analysis_run_id=bad', 'limit=0', 'limit=101', 'limit=x', 'offset=-1',
                          'offset=x', 'extra=private', 'limit=1&limit=2', 'offset=0&offset=1']),
        ):
            for query in queries:
                with self.subTest(endpoint=endpoint, query=query):
                    response = await self.client.get(self.base + '/' + endpoint + '?' + query)
                    self.assertEqual(response.status_code, 400, response.text)
                    validator('ApiError').validate(response.json())
                    self.assertEqual(response.json()['message'], 'Invalid request input.')
            response = await self.client.get('/api/v1/cases/bad/' + endpoint)
            self.assertEqual(response.status_code, 400)

    @unittest.skipUnless(os.environ.get('EVORA_NEO4J_INTEGRATION') == '1', 'Opt-in disposable real Neo4j')
    async def test_real_neo4j_publication_and_http_readback(self):
        self.neo = Neo4jGraphDatabase()
        self.app.state.graph_database = self.neo
        try:
            run, graph, findings = await self.populated()
            self.assertEqual(projection.get_projected_graph(self.app.state.database, self.neo,
                case_id=self.case, analysis_run_id=run['id']), graph)
            self.assertEqual(await self.read('graph'), graph)
            self.assertEqual((await self.read('findings'))['items'], findings)
        finally:
            with self.app.state.database.connect() as connection:
                runs = [row['id'] for row in connection.execute('SELECT id FROM analysis_runs')]
            with self.neo.get_driver().session(database=self.neo.config.database) as session:
                for run_id in runs:
                    for query in (projection._DELETE_EDGES, projection._DELETE_NODES):
                        session.run(query, case_id=self.case, run_id=run_id).consume()
