"""A06 real HTTP/SQLite/processing/analysis with an explicit Neo4j double."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import analysis
from backend.tests import test_analysis as lifecycle
from backend.tests.test_graph_nodes import validator


class TriageEndpointTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll

    async def triage(self, params=None, base=None):
        response = await self.client.get((base or self.base) + '/triage', params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        validator('TriagePage').validate(response.json())
        return response.json()

    async def history(self, eid):
        response = await self.client.get(self.base + f'/evidence/{eid}/triage-history')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertIsInstance(response.json(), list)
        for result in response.json():
            validator('TriageResult').validate(result)
        return response.json()

    def stored(self, run):
        with self.app.state.database.connect() as connection:
            row = connection.execute('SELECT triage_json FROM analysis_outputs WHERE run_id=?',
                                     (run['id'],)).fetchone()
        return json.loads(row['triage_json'])

    def assert_missing(self, response):
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json(), {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
        validator('ApiError').validate(response.json())

    async def test_before_completion_live_uploads_sorted_and_paginated(self):
        self.assertEqual(await self.triage(), dict(items=[], total=0, limit=20, offset=0))
        evidence = [(await self.upload(process=False))[0] for _ in range(3)]
        ids = sorted(e['id'] for e in evidence)
        self.assertEqual(await self.triage(), dict(items=[{'evidence_id': eid} for eid in ids],
                                                 total=3, limit=20, offset=0))
        self.assertEqual(await self.triage({'limit': 1, 'offset': 1}),
                         dict(items=[{'evidence_id': ids[1]}], total=3, limit=1, offset=1))
        self.assertEqual(await self.history(ids[0]), [])
        with patch.object(analysis, 'run_analysis_job'):
            await self.start()
        self.assertNotIn('analysis_run_id', await self.triage())

    async def test_real_completed_snapshot_membership_score_order_and_upload_between_pages(self):
        network = [(await self.upload())[0] for _ in range(2)]
        gps, _ = await self.upload('gps.csv', 'gps')
        unscored = [(await self.upload(process=False))[0] for _ in range(2)]
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'completed')
        results = self.stored(run)
        self.assertEqual(len(results), 3)
        # Duplicate network source content supplies an actual equal-score tie.
        self.assertEqual(len({r['score'] for r in results if r['evidence_id'] in
                              {e['id'] for e in network}}), 1)
        ordered = sorted(results, key=lambda r: (-r['score'], r['evidence_id']))
        expected = [dict(evidence_id=r['evidence_id'], latest_result=r,
                         effective_priority=r['priority']) for r in ordered]
        expected += [dict(evidence_id=eid) for eid in sorted(e['id'] for e in unscored)]
        self.assertEqual(set(run['input_snapshot']['evidence_ids']),
                         {e['id'] for e in network + [gps] + unscored})
        self.assertEqual(await self.triage(), dict(items=expected, total=5, limit=20,
                                                 offset=0, analysis_run_id=run['id']))
        pages = [(await self.triage({'limit': 1}))['items'][0]]
        later, _ = await self.upload()
        for offset in range(1, 5):
            page = await self.triage({'analysis_run_id': run['id'], 'limit': 1, 'offset': offset})
            self.assertEqual((page['total'], page['analysis_run_id']), (5, run['id']))
            pages.extend(page['items'])
        self.assertEqual(pages, expected)
        self.assertNotIn(later['id'], {e['evidence_id'] for e in pages})
        self.assertEqual((await self.triage())['total'], 5)
        self.assertEqual(await self.triage({'offset': 99}), dict(items=[], total=5,
                         limit=20, offset=99, analysis_run_id=run['id']))
        new = await self.poll(await self.start())
        self.assertEqual((await self.triage())['analysis_run_id'], new['id'])
        self.assertEqual((await self.triage())['total'], 6)
        self.assertEqual((await self.triage({'analysis_run_id': run['id']}))['items'], expected)
        self.assertEqual(self.stored(run), results)

    async def test_selected_empty_and_entirely_unscored_snapshots_keep_id(self):
        empty = await self.start()
        self.assertEqual(await self.triage(), dict(items=[], total=0, limit=20, offset=0,
                                                 analysis_run_id=empty['id']))
        evidence, _ = await self.upload(process=False)
        run = await self.start()
        self.assertEqual(await self.triage(), dict(items=[{'evidence_id': evidence['id']}],
                         total=1, limit=20, offset=0, analysis_run_id=run['id']))
        self.assertEqual((await self.triage({'analysis_run_id': empty['id']}))['total'], 0)
        self.assertEqual(await self.history(evidence['id']), [])
        await self.process(evidence['id'])
        scored = await self.start()
        self.assertEqual(await self.history(evidence['id']), self.stored(scored))
        self.assertNotIn('latest_result', (await self.triage({'analysis_run_id': run['id']}))['items'][0])

    async def test_history_real_results_append_without_rewriting_and_exclude_unpublished(self):
        evidence, _ = await self.upload()
        first = await self.start()
        original = self.stored(first)
        self.assertEqual(await self.history(evidence['id']), original)
        await self.upload('gps.csv', 'gps')
        second = await self.start()
        expected = original + [r for r in self.stored(second) if r['evidence_id'] == evidence['id']]
        self.assertEqual(await self.history(evidence['id']), expected)
        # Persist a real output and crash before publication: it must stay hidden.
        with patch.object(analysis, 'run_analysis_job'):
            pending = await self.start()
        self.app.state.graph_database = self.neo
        def crash():
            raise SystemExit('Synthetic crash')
        self.neo.after_commit = crash
        with self.assertRaises(SystemExit):
            analysis.process_analysis_run(self.app, pending['id'])
        self.neo.after_commit = None
        self.assertTrue(self.stored(pending))
        self.assertEqual(await self.history(evidence['id']), expected)
        self.assert_missing(await self.client.get(self.base + '/triage',
                           params={'analysis_run_id': pending['id']}))
        self.neo.corrupt = 'property'
        failed = await self.poll(await self.start())
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(await self.history(evidence['id']), expected)
        self.assertEqual(self.stored(first), original)
        self.neo.corrupt = None
        await analysis.recover_analysis_runs(self.app)
        self.assertEqual((await self.triage())['analysis_run_id'], pending['id'])
        self.assertEqual(await self.history(evidence['id']), expected +
                         [r for r in self.stored(pending) if r['evidence_id'] == evidence['id']])

    async def test_not_found_case_evidence_and_run_selectors(self):
        evidence, _ = await self.upload()
        completed = await self.start()
        with patch.object(analysis, 'run_analysis_job'):
            queued = await self.start()
            running = await self.start()
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE analysis_runs SET status='running' WHERE id=?", (running['id'],))
        self.neo.corrupt = 'property'
        failed = await self.poll(await self.start())
        self.assertEqual(failed['status'], 'failed')
        other = (await self.client.post('/api/v1/cases', json={'title': 'Other owned case'})).json()['id']
        for rid in (str(uuid4()), queued['id'], running['id'], failed['id']):
            self.assert_missing(await self.client.get(self.base + '/triage', params={'analysis_run_id': rid}))
        self.assert_missing(await self.client.get(f'/api/v1/cases/{other}/triage',
                           params={'analysis_run_id': completed['id']}))
        for base in (f'/api/v1/cases/{other}', f'/api/v1/cases/{uuid4()}'):
            self.assert_missing(await self.client.get(base + f'/evidence/{evidence["id"]}/triage-history'))
        self.assert_missing(await self.client.get(self.base + f'/evidence/{uuid4()}/triage-history'))
        for suffix in ('triage', f'evidence/{evidence["id"]}/triage-history'):
            self.assert_missing(await self.client.get(self.base + '/' + suffix,
                               headers={'Authorization': 'Bearer other'}))
            self.assert_missing(await self.client.get(f'/api/v1/cases/{uuid4()}/' + suffix))
            response = await self.client.get(self.base + '/' + suffix, headers={'Authorization': 'bad'})
            self.assertEqual(response.status_code, 401)
            validator('ApiError').validate(response.json())
        self.assertEqual((await self.triage())['analysis_run_id'], completed['id'])

    async def test_utc_then_uuid_order_for_latest_and_history(self):
        evidence, _ = await self.upload()
        first, second = await self.start(), await self.start()
        for a, b, ids in (
            ('2026-11-03T23:00:00-02:00', '2026-11-04T00:00:00Z', [second['id'], first['id']]),
            ('2026-11-03T12:00:00Z', '2026-11-03T13:00:00+01:00', sorted([first['id'], second['id']])),
        ):
            with self.app.state.database.connect() as connection:
                # Controlled ordering fixtures only; production timestamps stay immutable.
                connection.execute('DROP TRIGGER IF EXISTS analysis_run_frozen')
                connection.execute('DROP TRIGGER IF EXISTS analysis_run_terminal')
                for run, timestamp in ((first, a), (second, b)):
                    connection.execute('UPDATE analysis_runs SET created_at=? WHERE id=?', (timestamp, run['id']))
            self.assertEqual((await self.triage())['analysis_run_id'], ids[-1])
            self.assertEqual([r['analysis_run_id'] for r in await self.history(evidence['id'])], ids)

    async def test_live_overrides_preserve_pinned_pages_scores_and_history(self):
        scored, _ = await self.upload()
        unscored, _ = await self.upload(process=False)
        run = await self.start()
        original, history = await self.triage(), await self.history(scored['id'])
        other = (await self.client.post('/api/v1/cases', json={'title': 'Other owned case'})).json()['id']
        with self.app.state.database.connect() as connection:
            # Controlled timestamps exercise chronological and UUID tie ordering.
            rows = [
                (str(uuid4()), self.case, scored['id'], 'investigator-1', 'P1', 'Synthetic', '2026-11-03T23:00:00-02:00'),
                (str(uuid4()), self.case, scored['id'], 'investigator-1', 'P4', 'Synthetic', '2026-11-04T00:00:00Z'),
                (str(uuid4()), other, scored['id'], 'investigator-1', 'P2', 'Foreign', '2027-01-01T00:00:00Z'),
                ('00000000-0000-4000-8000-000000000001', self.case, unscored['id'], 'investigator-1', 'P4', 'Synthetic', '2026-11-03T12:00:00Z'),
                ('00000000-0000-4000-8000-000000000002', self.case, unscored['id'], 'investigator-1', 'P1', 'Synthetic', '2026-11-03T13:00:00+01:00'),
            ]
            connection.executemany('INSERT INTO priority_overrides VALUES (?,?,?,?,?,?,?)', rows)
        first = await self.triage({'analysis_run_id': run['id'], 'limit': 1})
        self.assertEqual(first['items'][0]['override']['id'], rows[0][0])
        self.assertEqual(first['items'][0]['effective_priority'], 'P1')
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO priority_overrides VALUES (?,?,?,?,?,?,?)',
                               (str(uuid4()), self.case, scored['id'], 'investigator-1', 'P4', 'Synthetic', '2028-01-01T00:00:00Z'))
        second = await self.triage({'analysis_run_id': run['id'], 'limit': 1, 'offset': 1})
        self.assertEqual(second['items'][0]['override']['id'], rows[-1][0])
        self.assertNotIn('latest_result', second['items'][0])
        self.assertEqual(second['items'][0]['effective_priority'], 'P1')
        updated = await self.triage({'analysis_run_id': run['id']})
        self.assertEqual(updated['items'][0]['effective_priority'], 'P4')
        self.assertEqual([e['evidence_id'] for e in updated['items']],
                         [e['evidence_id'] for e in original['items']])
        self.assertEqual(updated['items'][0]['latest_result'], original['items'][0]['latest_result'])
        self.assertEqual(await self.history(scored['id']), history)
        self.assertEqual(updated['total'], original['total'])

    async def test_invalid_input_safe_400(self):
        evidence, _ = await self.upload(process=False)
        for suffix, queries in (
            ('triage', ['analysis_run_id=bad', 'analysis_run_id=', 'limit=0', 'limit=101', 'limit=x',
                        'offset=-1', 'offset=x', 'extra=private', 'limit=1&limit=2',
                        'offset=0&offset=1', f'analysis_run_id={uuid4()}&analysis_run_id={uuid4()}']),
            (f'evidence/{evidence["id"]}/triage-history', ['extra=private', 'limit=1', f'analysis_run_id={uuid4()}']),
        ):
            for query in queries:
                response = await self.client.get(self.base + '/' + suffix + '?' + query)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()['message'], 'Invalid request input.')
                validator('ApiError').validate(response.json())
        for path in ('/api/v1/cases/bad/triage', self.base + '/evidence/bad/triage-history'):
            self.assertEqual((await self.client.get(path)).status_code, 400)
