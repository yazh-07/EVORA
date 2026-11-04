"""U14B HTTP/SQLite tests over explicit machine transcript publication fixtures.

No ASR adapter is present in this checkout. Fixtures certify correction behavior,
not speech recognition or model quality.
"""

import asyncio
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis, transcripts
from backend.analysis import freeze_analysis_input_snapshot
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.tests.test_analysis import GraphDouble
from backend.tests.test_graph_nodes import validator


class TranscriptTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'other': 'investigator-2'}))
        life = self.app.router.lifespan_context(self.app)
        await life.__aenter__()
        self.addAsyncCleanup(life.__aexit__, None, None, None)
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
                                  headers={'Authorization': 'Bearer local'})
        self.addAsyncCleanup(self.client.aclose)
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic U14B'})).json()['id']
        self.base = f'/api/v1/cases/{self.case}'
        response = await self.client.post(self.base + '/evidence', data={'kind': 'audio', 'source_label': 'Synthetic'},
            files={'file': ('fixture.wav', b'Synthetic immutable original bytes', 'audio/wav')})
        self.assertEqual(response.status_code, 201, response.text)
        self.evidence = response.json()
        self.run_id, observations = self.machine_fixture()
        self.source, self.other, self.visual = observations
        self.url = self.revision_url(self.source['id'])
        self.body = dict(processing_run_id=self.run_id, base_processing_run_id=self.run_id,
            expected_latest_revision_id=None, corrected_text='Corrected D-42 spoke.', reason='Checked original audio.')

    @classmethod
    def setUpClass(cls):
        cls.revision_schema = validator('TranscriptRevision')
        cls.page_schema = validator('TranscriptRevisionPage')
        cls.error_schema = validator('ApiError')

    def revision_url(self, source_id, case_id=None):
        return f'/api/v1/cases/{case_id or self.case}/observations/{source_id}/transcript-revisions'

    def machine_fixture(self, finished_at='2026-01-01T00:00:00Z', evidence_id=None):
        run_id = str(uuid4())
        evidence_id = evidence_id or self.evidence['id']
        observations = [dict(id=str(uuid4()), case_id=self.case, evidence_id=evidence_id, processing_run_id=run_id,
            kind='transcript.segment', source_locator=f'media:start_ms={i * 1000};end_ms={(i + 1) * 1000}',
            raw_value=text, normalized_value=text, extraction_confidence=0.4 + i / 10)
            for i, text in enumerate(('Machine D-7 spoke.', 'Other D-8 replied.'))]
        observations.append(dict(id=str(uuid4()), case_id=self.case, evidence_id=evidence_id, processing_run_id=run_id,
            kind='video.frame', source_locator='media:frame=0', raw_value='Original visual', normalized_value='Original visual',
            extraction_confidence=0.3))
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
                'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run_id, self.case, evidence_id, 'investigator-1', str(uuid4()), 'synthetic-machine-fixture', '{}',
                 'synthetic-asr-fixture/1', '2026-01-01T00:00:00Z', 'queued'))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            mentions = [dict(id=str(uuid4()), case_id=self.case, evidence_id=evidence_id, processing_run_id=run_id,
                kind='text.mention.device', source_locator=observations[i]['source_locator'], raw_value=label,
                normalized_value=label, entity_key='device:' + label, extraction_confidence=0)
                for i, label in enumerate(('D-7', 'D-8'))]
            entities = [dict(id=str(uuid4()), case_id=self.case, kind='device', canonical_label=label,
                candidate_key='device:' + label, evidence_ids=[evidence_id], observation_ids=[mentions[i]['id']], confidence=0)
                for i, label in enumerate(('D-7', 'D-8'))]
            events = [dict(id=str(uuid4()), case_id=self.case, kind='visual.detected', summary='Visual source candidate',
                evidence_ids=[evidence_id], observation_ids=[observations[2]['id']], entity_ids=[], confidence=0)]
            uncertainty = [dict(observation_id=item['id'], diagnostic='machine-fixture') for item in observations + mentions]
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (run_id, self.case, evidence_id, *[json.dumps(items) for items in (observations + mentions, entities, events, uncertainty)]))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (finished_at, run_id))
        return run_id, observations

    def snapshot(self):
        with self.app.state.database.connect() as connection:
            return {table: [dict(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY id')]
                    for table in ('transcript_revisions', 'processing_runs', 'evidence', 'audit_events')} | {
                        'outputs': [dict(row) for row in connection.execute('SELECT * FROM processing_outputs ORDER BY run_id')]}

    def output(self, run_id):
        with self.app.state.database.connect() as connection:
            row = connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run_id,)).fetchone()
            return {key: json.loads(row[key]) for key in transcripts._OUTPUTS}

    async def append(self, body=None, key=None, url=None, headers=None):
        return await self.client.post(url or self.url, json=self.body if body is None else body,
            headers={'Idempotency-Key': key or str(uuid4()), **(headers or {})})

    async def create(self, body=None, **kwargs):
        response = await self.append(body, **kwargs)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.revision_schema.validate(response.json())
        return response.json()

    async def page(self, url=None, **params):
        response = await self.client.get(url or self.url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.page_schema.validate(response.json())
        return response.json()

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.error_schema.validate(response.json())
        self.assertNotIn('SECRET', response.text)

    async def test_first_correction_publishes_complete_output_and_preserves_originals(self):
        before = self.snapshot()
        revision = await self.create()
        self.assertIsNone(revision['previous_revision_id'])
        self.assertEqual(revision['actor_id'], 'investigator-1')
        self.assertEqual(revision['processing_run_id'], self.run_id)
        self.assertEqual(revision['source_observation_id'], self.source['id'])
        output = self.output(revision['derived_processing_run_id'])
        derived = next(item for item in output['observations_json'] if item['id'] == revision['derived_observation_id'])
        self.assertEqual(derived, dict(self.source, id=revision['derived_observation_id'],
            processing_run_id=revision['derived_processing_run_id'], source_observation_id=self.source['id'],
            normalized_value=self.body['corrected_text'], transcript_revision_id=revision['id']))
        copied = next(item for item in output['observations_json'] if item.get('source_observation_id') == self.other['id'])
        self.assertEqual(copied['normalized_value'], self.other['normalized_value'])
        self.assertNotIn('transcript_revision_id', copied)
        self.assertTrue(any(item['kind'] == 'video.frame' for item in output['observations_json']))
        self.assertEqual(len(output['events_json']), 1)
        oids = {item['id'] for item in output['observations_json']}
        self.assertFalse(oids & {self.source['id'], self.other['id'], self.visual['id']})
        self.assertTrue(all(set(item['observation_ids']) <= oids for item in output['entities_json'] + output['events_json']))
        self.assertEqual({item['canonical_label'] for item in output['entities_json']}, {'D-8', 'D-42'})
        after = self.snapshot()
        for table in ('processing_runs', 'outputs', 'evidence'):
            for row in before[table]:
                self.assertIn(row, after[table])
        self.assertEqual((await self.page())['items'], [revision])
        response = await self.client.get(self.base + '/observations')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({item['processing_run_id'] for item in response.json()['items']}, {revision['derived_processing_run_id']})
        original = await self.client.get(self.base + '/observations', params={'processing_run_id': self.run_id})
        self.assertEqual({item['id'] for item in original.json()['items']},
                         {item['id'] for item in self.output(self.run_id)['observations_json']})
        download = await self.client.get(self.base + f"/evidence/{self.evidence['id']}/content")
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), self.evidence['sha256'])
        for path in ('entities', 'events'):
            response = await self.client.get(self.base + '/' + path)
            self.assertEqual(response.status_code, 200, response.text)
            validator('EntityPage' if path == 'entities' else 'EventPage').validate(response.json())

    async def test_second_correction_chains_to_first_and_paginates_oldest_first(self):
        first = await self.create()
        second = await self.create(dict(self.body, base_processing_run_id=first['derived_processing_run_id'],
            expected_latest_revision_id=first['id'], corrected_text='Second correction.'))
        self.assertEqual(second['previous_revision_id'], first['id'])
        self.assertEqual(second['processing_run_id'], self.run_id)
        self.assertEqual(second['source_observation_id'], self.source['id'])
        self.assertEqual((await self.page())['items'], [first, second])
        self.assertEqual(await self.page(limit=1, offset=1), dict(items=[second], total=2, limit=1, offset=1))
        self.assertEqual((await self.page(offset=10 ** 100))['items'], [])
        output = self.output(second['derived_processing_run_id'])
        self.assertNotIn('D-42', {item['canonical_label'] for item in output['entities_json']})
        with self.app.state.database.connect() as connection:
            times = [connection.execute('SELECT finished_at FROM processing_runs WHERE id=?', (run_id,)).fetchone()[0]
                     for run_id in (self.run_id, first['derived_processing_run_id'], second['derived_processing_run_id'])]
        self.assertEqual(sorted(times, key=transcripts._utc_order), times)
        self.assertEqual(len(set(times)), 3)

    async def test_correction_of_other_segment_carries_first_correction_and_visual_output(self):
        first = await self.create()
        second = await self.create(dict(self.body, base_processing_run_id=first['derived_processing_run_id'],
            corrected_text='Other D-99 replied.'), url=self.revision_url(self.other['id']))
        output = self.output(second['derived_processing_run_id'])
        segments = {item['source_observation_id']: item for item in output['observations_json'] if item['kind'] == 'transcript.segment'}
        self.assertEqual(segments[self.source['id']]['normalized_value'], self.body['corrected_text'])
        self.assertEqual(segments[self.source['id']]['transcript_revision_id'], first['id'])
        self.assertEqual(segments[self.other['id']]['transcript_revision_id'], second['id'])
        self.assertEqual({item['canonical_label'] for item in output['entities_json']}, {'D-42', 'D-99'})
        self.assertEqual(len(output['events_json']), 1)

    async def test_stale_base_and_revision_conflicts_leave_no_writes(self):
        first = await self.create()
        before = self.snapshot()
        bodies = [self.body, dict(self.body, expected_latest_revision_id=first['id']),
                  dict(self.body, base_processing_run_id=first['derived_processing_run_id']),
                  dict(self.body, base_processing_run_id=first['derived_processing_run_id'], expected_latest_revision_id=str(uuid4()))]
        for body in bodies:
            self.assert_error(await self.append(body), 409)
        self.assertEqual(self.snapshot(), before)

    async def test_retranscription_does_not_auto_rebase_old_machine_lineage(self):
        latest_id, _ = self.machine_fixture('2099-01-01T00:00:00Z')
        before = self.snapshot()
        self.assert_error(await self.append(), 409)
        self.assert_error(await self.append(dict(self.body, base_processing_run_id=latest_id)), 409)
        self.assertEqual(self.snapshot(), before)

    async def test_non_transcript_target_returns_400_for_both_routes(self):
        url = self.revision_url(self.visual['id'])
        self.assert_error(await self.append(url=url), 400)
        self.assert_error(await self.client.get(url), 400)

    async def test_missing_foreign_case_observation_runs_and_derived_path_return_404(self):
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Other owned case'})).json()['id']
        for url in (self.revision_url(str(uuid4())), self.revision_url(self.source['id'], other_case),
                    self.revision_url(self.source['id'], str(uuid4()))):
            self.assert_error(await self.append(url=url), 404)
            self.assert_error(await self.client.get(url), 404)
        for field in ('processing_run_id', 'base_processing_run_id'):
            self.assert_error(await self.append(dict(self.body, **{field: str(uuid4())})), 404)
        first = await self.create()
        derived_url = self.revision_url(first['derived_observation_id'])
        self.assert_error(await self.append(dict(self.body, processing_run_id=first['derived_processing_run_id']), url=derived_url), 404)
        self.assert_error(await self.client.get(derived_url), 404)

    async def test_same_case_wrong_evidence_run_and_revision_are_404(self):
        response = await self.client.post(self.base + '/evidence', data={'kind': 'audio', 'source_label': 'Other synthetic'},
            files={'file': ('other.wav', b'Other source', 'audio/wav')})
        other_run, other_obs = self.machine_fixture(evidence_id=response.json()['id'])
        self.assert_error(await self.append(dict(self.body, processing_run_id=other_run)), 404)
        self.assert_error(await self.append(dict(self.body, base_processing_run_id=other_run)), 404)
        other_revision = await self.create(dict(self.body, processing_run_id=other_run, base_processing_run_id=other_run),
                                           url=self.revision_url(other_obs[0]['id']))
        self.assert_error(await self.append(dict(self.body, expected_latest_revision_id=other_revision['id'])), 404)

    async def test_identical_idempotency_replay_before_stale_checks_and_conflicting_body_or_path(self):
        key = str(uuid4())
        first = await self.create(key=key)
        before = self.snapshot()
        self.assertEqual(await self.create(key=key), first)
        self.assertEqual(self.snapshot(), before)
        for field, value in (('reason', 'Changed reason'), ('corrected_text', 'Changed text'),
                             ('base_processing_run_id', first['derived_processing_run_id']),
                             ('expected_latest_revision_id', first['id'])):
            self.assert_error(await self.append(dict(self.body, **{field: value}), key=key), 409)
        self.assert_error(await self.append(key=key, url=self.revision_url(self.other['id'])), 409)
        self.assertEqual(self.snapshot(), before)

    async def test_replay_after_later_correction_rechecks_authorization(self):
        key = str(uuid4())
        first = await self.create(key=key)
        await self.create(dict(self.body, expected_latest_revision_id=first['id'], base_processing_run_id=first['derived_processing_run_id']))
        self.assertEqual(await self.create(key=key), first)
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.assert_error(await self.append(key=key), 404)
        self.assert_error(await self.client.get(self.url), 404)

    async def test_unauthenticated_and_unrelated_actor_rejected(self):
        for headers, status in (({'Authorization': ''}, 401), ({'Authorization': 'Bearer other'}, 404)):
            self.assert_error(await self.append(headers=headers), status)
            self.assert_error(await self.client.get(self.url, headers=headers), status)

    async def test_actor_scoped_keys_and_safe_exactly_once_audit(self):
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO case_members VALUES (?,?)', (self.case, 'investigator-2'))
        key = str(uuid4())
        first = await self.create(key=key)
        second = await self.create(dict(self.body, base_processing_run_id=first['derived_processing_run_id'],
            expected_latest_revision_id=first['id'], reason='SECRET correction reason', corrected_text='SECRET text'),
            key=key, headers={'Authorization': 'Bearer other'})
        self.assertEqual(second['actor_id'], 'investigator-2')
        await self.create(key=key)
        events = (await self.client.get(self.base + '/audit-events')).json()['items']
        events = [event for event in events if event['action'] == 'appendTranscriptRevision']
        self.assertEqual(len(events), 2)
        self.assertNotIn('SECRET', json.dumps(events))
        self.assertEqual({event['target_id'] for event in events}, {first['id'], second['id']})
        for revision in (first, second):
            [event] = [event for event in events if event['target_id'] == revision['id']]
            self.assertEqual(event['actor_id'], revision['actor_id'])
            self.assertEqual(event['created_at'], revision['created_at'])
            self.assertEqual(event['case_id'], self.case)
            self.assertNotIn('reason', event)

    async def test_invalid_bodies_headers_and_pagination_are_safe_400(self):
        before = self.snapshot()
        bodies = [{}, [], 'SECRET', None]
        bodies += [{k: v for k, v in self.body.items() if k != field} for field in self.body]
        bodies += [dict(self.body, **{field: value}) for field in ('corrected_text', 'reason')
                   for value in ('', ' \n\t', '\u2003', None, 123, True)]
        bodies += [dict(self.body, corrected_text='x' * 20001), dict(self.body, reason='x' * 2001)]
        bodies += [dict(self.body, **{field: 'SECRET'}) for field in ('actor_id', 'created_at', 'id', 'unknown')]
        bodies += [dict(self.body, **{field: 'SECRET'}) for field in ('processing_run_id', 'base_processing_run_id', 'expected_latest_revision_id')]
        for body in bodies:
            self.assert_error(await self.client.post(self.url, json=body, headers={'Idempotency-Key': str(uuid4())}), 400)
        for headers in ({}, {'Idempotency-Key': ''}, {'Idempotency-Key': 'SECRET'},
                        [('Idempotency-Key', str(uuid4())), ('Idempotency-Key', str(uuid4()))]):
            self.assert_error(await self.client.post(self.url, json=self.body, headers=headers), 400)
        for query in ('limit=0', 'limit=101', 'limit=SECRET', 'offset=-1', 'offset=1.5', 'unknown=SECRET', 'limit=1&limit=2'):
            self.assert_error(await self.client.get(self.url + '?' + query), 400)
        self.assert_error(await self.append(url=self.url + '?limit=1'), 400)
        self.assert_error(await self.client.get(self.revision_url('SECRET')), 400)
        self.assertEqual(self.snapshot(), before)

    async def test_length_boundaries_and_exact_whitespace_roundtrip(self):
        first = await self.create(dict(self.body, corrected_text='x' * 20000, reason='y' * 2000))
        self.assertEqual(len(first['corrected_text']), 20000)
        second = await self.create(dict(self.body, base_processing_run_id=first['derived_processing_run_id'],
            expected_latest_revision_id=first['id'], corrected_text='  café\n[unclear]  ', reason='  checked\n  '))
        self.assertEqual(second['corrected_text'], '  café\n[unclear]  ')
        self.assertEqual(second['reason'], '  checked\n  ')

    async def test_preparation_and_audit_failure_rollback_every_write(self):
        before = self.snapshot()
        for function in ('_materialize', 'record_audit_event'):
            with patch.object(transcripts, function, side_effect=RuntimeError('synthetic failure')):
                with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                    await self.append()
            self.assertEqual(self.snapshot(), before)
        await self.create()

    async def test_preconditions_checked_again_before_publication(self):
        before = self.snapshot()
        real = transcripts._preconditions
        calls = 0
        def recheck(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise transcripts._conflict()
            return real(*args)
        with patch.object(transcripts, '_preconditions', side_effect=recheck):
            self.assert_error(await self.append(), 409)
        self.assertEqual(calls, 2)
        self.assertEqual(self.snapshot(), before)

    async def test_concurrent_same_preconditions_allow_one_append(self):
        responses = await asyncio.gather(self.append(), self.append())
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        self.assertEqual((await self.page())['total'], 1)

    async def test_concurrent_same_key_returns_identical_201_and_one_audit(self):
        key = str(uuid4())
        responses = await asyncio.gather(self.append(key=key), self.append(key=key))
        self.assertEqual([response.status_code for response in responses], [201, 201])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual((await self.page())['total'], 1)
        self.assertEqual(len([event for event in self.snapshot()['audit_events'] if event['action'] == 'appendTranscriptRevision']), 1)

    async def test_sql_mutation_replace_and_restart_cannot_change_history(self):
        revision = await self.create()
        with self.app.state.database.connect() as connection:
            row = dict(connection.execute('SELECT * FROM transcript_revisions').fetchone())
        for statement, params in (
            ('UPDATE transcript_revisions SET reason=? WHERE id=?', ('changed', revision['id'])),
            ('DELETE FROM transcript_revisions WHERE id=?', (revision['id'],)),
            ('INSERT OR REPLACE INTO transcript_revisions (' + ','.join(row) + ') VALUES (' + ','.join('?' for _ in row) + ')', tuple(row.values())),
            ('INSERT OR REPLACE INTO transcript_revisions (rowid,' + ','.join(row) + ') VALUES (' + ','.join('?' for _ in range(len(row) + 1)) + ')',
             (1, *[str(uuid4()) if key in ('id', 'key_digest') else value for key, value in row.items()])),
        ):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(statement, params)
        before = self.snapshot()
        transcripts.initialize_transcripts(self.app.state.database)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((await self.page())['items'], [revision])

    async def test_utc_order_tiebreaker_before_pagination(self):
        revision = await self.create()
        with self.app.state.database.connect() as connection:
            row = dict(connection.execute('SELECT * FROM transcript_revisions').fetchone())
            for number, stamp in ((5, '2099-01-01T00:00:00.000001Z'), (4, '2099-01-01T00:00:00Z'),
                                  (3, '2099-01-01T01:00:00.000000+01:00')):
                fixture = dict(row, id=f'00000000-0000-4000-8000-{number:012d}', created_at=stamp, key_digest=str(uuid4()))
                connection.execute('INSERT INTO transcript_revisions (' + ','.join(fixture) + ') VALUES (' +
                                   ','.join('?' for _ in fixture) + ')', tuple(fixture.values()))
        page = await self.page(limit=2, offset=1)
        self.assertEqual([item['id'] for item in page['items']], [f'00000000-0000-4000-8000-{i:012d}' for i in (3, 4)])
        self.assertEqual(page['total'], 4)
        self.assertEqual((await self.page(limit=1))['items'], [revision])

    async def test_completion_strictly_after_future_submicrosecond_base(self):
        run_id, observations = self.machine_fixture('2099-01-01T00:00:00.999999999Z')
        revision = await self.create(dict(self.body, processing_run_id=run_id, base_processing_run_id=run_id),
                                     url=self.revision_url(observations[0]['id']))
        self.assertGreater(transcripts._utc_order(revision['created_at']), transcripts._utc_order('2099-01-01T00:00:00.999999999Z'))
        response = await self.client.get(self.base + '/observations')
        self.assertEqual({item['processing_run_id'] for item in response.json()['items']}, {revision['derived_processing_run_id']})

    async def test_new_analysis_snapshot_selects_derived_run_while_old_snapshot_stays_unchanged(self):
        original = freeze_analysis_input_snapshot(self.app.state.database, self.case)
        saved = deepcopy(original)
        revision = await self.create()
        corrected = freeze_analysis_input_snapshot(self.app.state.database, self.case)
        self.assertEqual(original, saved)
        self.assertNotEqual(original['sha256'], corrected['sha256'])
        self.assertEqual(corrected['processing_run_ids'], [revision['derived_processing_run_id']])
        self.assertIn(revision['derived_observation_id'], corrected['observation_ids'])
        self.assertEqual(original['processing_run_ids'], [self.run_id])
        self.assertIn(self.source['id'], original['observation_ids'])

    async def test_empty_history_read_only_and_missing_evidence_fails_closed(self):
        before = self.snapshot()
        self.assertEqual(await self.page(), dict(items=[], total=0, limit=20, offset=0))
        self.assertEqual(self.snapshot(), before)
        # Explicit corruption fixture; foreign keys cannot normally orphan a run.
        with closing(sqlite3.connect(self.app.state.database.path)) as connection, connection:
            connection.execute('DELETE FROM evidence WHERE id=?', (self.evidence['id'],))
        self.assert_error(await self.append(), 404)
        self.assert_error(await self.client.get(self.url), 404)

    async def test_real_analysis_lifecycle_keeps_old_key_and_stored_outputs_frozen(self):
        async def start(key):
            response = await self.client.post(self.base + '/analysis-runs', headers={'Idempotency-Key': key})
            self.assertEqual(response.status_code, 202, response.text)
            result = await self.client.get(self.base + '/analysis-runs/' + response.json()['id'])
            self.assertEqual(result.json()['status'], 'completed', result.text)
            return result.json()
        with patch.object(analysis, 'Neo4jGraphDatabase', return_value=GraphDouble()):
            key = str(uuid4())
            old = await start(key)
            with self.app.state.database.connect() as connection:
                stored = dict(connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (old['id'],)).fetchone())
            revision = await self.create()
            self.assertEqual(await start(key), old)
            new = await start(str(uuid4()))
        self.assertEqual(new['trigger'], 'new_observations')
        self.assertEqual(new['input_snapshot']['processing_run_ids'], [revision['derived_processing_run_id']])
        self.assertIn(revision['derived_observation_id'], new['input_snapshot']['observation_ids'])
        with self.app.state.database.connect() as connection:
            self.assertEqual(dict(connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (old['id'],)).fetchone()), stored)
