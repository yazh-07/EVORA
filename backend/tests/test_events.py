"""P05B actual source-backed Event reads, with labeled selection/fault fixtures."""
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import socket
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
from backend.auth import SyntheticTokenVerifier
from backend.events import _page
from backend.processing import process_run

ROOT = Path(__file__).resolve().parents[2]


class EventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p05b-synthetic-one': 'investigator-1', 'p05b-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p05b-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P05B case'})).json()['id']
        self.url = f'/api/v1/cases/{self.case}/events'
        self.evidence = await self.upload()
        self.run = await self.process(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    async def upload(self, kind='network_log', data=None, case=None):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / ('gps.csv' if kind == 'gps' else 'network.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence', data={'kind': kind, 'source_label': 'Synthetic P05B'},
            files={'file': ('source.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201)
        return response.json()

    async def process(self, evidence):
        response = await self.client.post(f"/api/v1/cases/{evidence['case_id']}/evidence/{evidence['id']}/processing-runs",
                                          headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202)
        return response.json()

    async def page(self, **params):
        response = await self.client.get(self.url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def output(self, run):
        with self.app.state.database.connect() as connection:
            return dict(connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone())

    def validate(self, name, value):
        Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': self.bundle['components']},
                             format_checker=FormatChecker()).validate(value)

    def fixture(self, finished_at, integer_id, observations=None, entities=None, events=None):
        """Controlled selection/schema fixture; not another implemented adapter."""
        original = self.output(self.run)
        observations = observations if observations is not None else json.loads(original['observations_json'])
        entities = entities if entities is not None else json.loads(original['entities_json'])
        events = events if events is not None else json.loads(original['events_json'])
        run_id = str(UUID(int=integer_id))
        obs_map = {x['id']: str(uuid4()) for x in observations}
        entity_map = {x['id']: str(uuid4()) for x in entities}
        observations = [dict(x, id=obs_map[x['id']], processing_run_id=run_id) for x in observations]
        entities = [dict(x, id=entity_map[x['id']], observation_ids=[obs_map[oid] for oid in x['observation_ids']]) for x in entities]
        events = [dict(x, id=str(uuid4()), observation_ids=[obs_map[oid] for oid in x['observation_ids']],
                       entity_ids=[entity_map[eid] for eid in x['entity_ids']]) for x in events]
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
                'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run_id, self.case, self.evidence['id'], 'investigator-1', str(uuid4()), 'synthetic-fixture', '{}',
                 'P05B-selection-fixture/1', '2099-01-01T00:00:00Z', 'queued'))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (run_id, self.case, self.evidence['id'], json.dumps(observations), json.dumps(entities), json.dumps(events), '[]'))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (finished_at, run_id))
        return events

    def allow_corruption(self):
        # Explicit fault fixture in temporary DB only: bypass immutable protection.
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_update')

    def corrupt(self, run, column, value):
        assert column in {'events_json', 'entities_json', 'observations_json', 'case_id', 'evidence_id'}
        with self.app.state.database.connect() as connection:
            connection.execute(f'UPDATE processing_outputs SET {column}=? WHERE run_id=?', (value, run['id']))

    async def denied(self):
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json(), {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.validate('ApiError', response.json())

    async def test_real_network_gps_exact_wire_source_time_and_participant_joins(self):
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        page = response.json(); self.validate('EventPage', page)
        self.assertEqual((page['total'], page['limit'], page['offset']), (3, 20, 0))
        outputs = [self.output(self.run), self.output(gps_run)]
        expected = [(output['evidence_id'], event) for output in outputs for event in json.loads(output['events_json'])]
        self.assertEqual(page['items'], [event for _, event in sorted(expected, key=lambda pair: (pair[0], pair[1]['id']))])
        sources = {x['id']: x for x in (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()['items']}
        participants = {x['id']: x for x in (await self.client.get(f'/api/v1/cases/{self.case}/entities')).json()['items']}
        for event in page['items']:
            self.assertEqual(event['case_id'], self.case)
            self.assertEqual(event['confidence'], 0)
            self.assertEqual(set(event['evidence_ids']), {sources[oid]['evidence_id'] for oid in event['observation_ids']})
            self.assertEqual(len(event['observation_ids']), 3)
            for oid in event['observation_ids']:
                self.assertTrue(sources[oid]['source_locator'])
                self.assertEqual(sources[oid]['observed_at_raw'], event['observed_at_raw'])
                self.assertEqual(sources[oid]['observed_at_utc'], event['observed_at_utc'])
            for eid in event['entity_ids']:
                self.assertEqual(participants[eid]['case_id'], self.case)
                self.assertTrue(set(participants[eid]['observation_ids']) & set(event['observation_ids']))
        gps_event = next(x for x in page['items'] if x['kind'] == 'gps.location')
        self.assertEqual([participants[eid]['candidate_key'] for eid in gps_event['entity_ids']], ['device:D-8'])

    async def test_duplicate_source_rows_and_evidence_remain_distinct_without_boost(self):
        row = b'2026-01-12T10:00:00Z,D-7,203.0.113.7,connected\n'
        evidence = await self.upload(data=b'timestamp,device_id,ip_address,event\n' + row * 2)
        run = await self.process(evidence)
        events = json.loads(self.output(run)['events_json'])
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]['id'], events[1]['id'])
        self.assertTrue(set(events[0]['observation_ids']).isdisjoint(events[1]['observation_ids']))
        self.assertEqual(events[0]['entity_ids'], events[1]['entity_ids'])
        self.assertTrue(all(event['confidence'] == 0 for event in events))
        second = await self.upload(); await self.process(second)
        page = await self.page()
        self.assertEqual(page['total'], 6)
        self.assertEqual(len({x['id'] for x in page['items']}), 6)

    async def test_raw_invalid_missing_zone_ambiguous_and_fractional_times_preserved(self):
        times = ['2026-01-12T10:00:00.123456789Z', '2026-01-12T15:30:00+05:30',
                 'not-a-time', '2026-01-12T10:00:00', '2026-01-12T10:00:00-00:00']
        data = ('timestamp,device_id,ip_address,event\n' + ''.join(
            f'{raw},D-{i},198.51.100.{i+1},<script>synthetic</script>\n' for i, raw in enumerate(times))).encode()
        evidence = await self.upload(data=data); run = await self.process(evidence)
        selected = {x['id']: x for x in (await self.page())['items']}
        expected = json.loads(self.output(run)['events_json'])
        self.assertEqual({x['observed_at_raw'] for x in expected}, set(times))
        for event in expected:
            self.assertEqual(selected[event['id']], event)
            self.assertEqual(event['summary'], 'Network log reports: <script>synthetic</script>')
            if event['observed_at_raw'] in times[2:]: self.assertNotIn('observed_at_utc', event)
        self.assertEqual(next(x['observed_at_utc'] for x in expected if x['observed_at_raw'] == times[0]), times[0])

    async def test_blank_required_csv_time_fails_processing_without_publishing_events(self):
        before = await self.page()
        evidence = await self.upload(data=b'timestamp,device_id,ip_address,event\n,D-7,203.0.113.7,connected\n')
        run = await self.process(evidence)
        response = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/processing-runs/{run['id']}")
        self.assertEqual(response.json()['status'], 'failed')
        self.assertEqual(response.json()['error'], 'CSV_INVALID_ROW')
        self.assertEqual(await self.page(), before)

    async def test_latest_per_evidence_failed_retry_retains_immutable_history(self):
        gps = await self.upload('gps'); gps_run = await self.process(gps)
        old = self.output(self.run)
        fresh = await self.process(self.evidence)
        expected = json.loads(self.output(fresh)['events_json']) + json.loads(self.output(gps_run)['events_json'])
        page = await self.page()
        self.assertEqual({x['id'] for x in page['items']}, {x['id'] for x in expected})
        self.assertTrue({x['id'] for x in json.loads(old['events_json'])}.isdisjoint(x['id'] for x in page['items']))
        with patch('backend.processing.publish_outputs', side_effect=RuntimeError('Synthetic publication failure')):
            await self.process(self.evidence)
        self.assertEqual(await self.page(), page)
        self.assertEqual(self.output(self.run), old)
        historical = await self.client.get(f'/api/v1/cases/{self.case}/observations', params={'processing_run_id': self.run['id']})
        self.assertEqual(historical.json()['total'], 6)

    async def test_pending_running_failed_partial_outputs_never_visible(self):
        before = await self.page()
        with patch('backend.processing.process_run'):
            queued = await self.process(self.evidence)
            running = await self.process(self.evidence)
            failed = await self.process(self.evidence)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running['id'],))
            connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                (running['id'], self.case, self.evidence['id'], 'SECRET partial', 'SECRET partial', 'SECRET partial', '[]'))
            connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='SYNTHETIC_FAILURE' WHERE id=?",
                               ('2099-01-12T00:00:00Z', failed['id']))
        self.assertEqual(await self.page(), before)

    async def test_all_page_order_totals_limits_and_huge_offsets(self):
        data = b'timestamp,device_id,ip_address,event\n' + b''.join(
            f'2026-01-12T10:00:00Z,D-{i},198.51.100.{i+1},connected\n'.encode() for i in range(25))
        evidence = await self.upload(data=data); run = await self.process(evidence)
        expected = [(output['evidence_id'], event) for output in (self.output(self.run), self.output(run))
                    for event in json.loads(output['events_json'])]
        expected = [event for _, event in sorted(expected, key=lambda pair: (pair[0], pair[1]['id']))]
        seen = []
        for offset in range(0, 27, 7):
            page = await self.page(limit=7, offset=offset)
            self.assertEqual((page['total'], page['limit'], page['offset']), (27, 7, offset))
            seen.extend(page['items'])
        self.assertEqual(seen, expected)
        self.assertEqual(len({x['id'] for x in seen}), 27)
        self.assertEqual(len((await self.page())['items']), 20)
        self.assertEqual((await self.page(limit=100))['items'], expected)
        for offset in (27, 100, 10 ** 100):
            self.assertEqual(await self.page(offset=offset), dict(items=[], total=27, limit=20, offset=offset))

    async def test_empty_unprocessed_header_only_and_empty_latest_no_fallback(self):
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic empty'})).json()['id']
        await self.upload('document', case=case)
        self.assertEqual((await self.client.get(f'/api/v1/cases/{case}/events')).json(),
                         dict(items=[], total=0, limit=20, offset=0))
        empty = await self.upload(data=b'timestamp,device_id,ip_address,event\n'); await self.process(empty)
        self.assertEqual((await self.page())['total'], 2)
        self.fixture('2099-01-12T00:00:00Z', 100, [], [], [])
        self.assertEqual((await self.page())['total'], 0)

    async def test_auth_case_isolation_and_revocation(self):
        case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic other'})).json()['id']
        evidence = await self.upload(case=case); run = await self.process(evidence)
        foreign = {x['id'] for x in json.loads(self.output(run)['events_json'])}
        self.assertTrue(foreign.isdisjoint(x['id'] for x in (await self.page())['items']))
        for headers, expected in [({}, 401), ({'Authorization': 'invalid'}, 401),
                                 ({'Authorization': 'Bearer p05b-synthetic-two'}, 404),
                                 ([('Authorization', 'Bearer p05b-synthetic-one')] * 2, 401)]:
            async with AsyncClient(transport=ASGITransport(self.app), base_url='http://test') as client:
                response = await client.get(self.url, headers=headers)
                self.assertEqual(response.status_code, expected)
                self.validate('ApiError', response.json())
        self.assertEqual((await self.client.get(self.url.replace(self.case, str(uuid4())))).status_code, 404)
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        await self.denied()

    async def test_bad_queries_duplicates_uuid_and_unavailable_selectors(self):
        for params in [{'limit': 0}, {'limit': 101}, {'limit': -1}, {'limit': 'SECRET'}, {'offset': -1},
                       {'offset': 'SECRET'}, {'evidence_id': self.evidence['id']}, {'processing_run_id': self.run['id']},
                       {'analysis_run_id': str(uuid4())}, [('limit', '1'), ('limit', '2')], [('offset', '0'), ('offset', '1')]]:
            response = await self.client.get(self.url, params=params)
            self.assertEqual(response.status_code, 400, response.text)
            self.assertNotIn('SECRET', response.text)
            self.validate('ApiError', response.json())
        self.assertEqual((await self.client.get(self.url.replace(self.case, 'SECRET'))).status_code, 400)

    async def test_corrupt_event_wire_uuid_time_score_and_reference_shape_fail_whole_read(self):
        original = json.loads(self.output(self.run)['events_json']); item = original[0]
        bad = ['SECRET not JSON', '{}', '["SECRET"]', '[null]', '[1]', json.dumps(original + [item])]
        changes = [dict(id='SECRET'), dict(case_id=str(uuid4())), dict(confidence=2), dict(confidence=True),
                   dict(evidence_ids=[]), dict(observation_ids=[]), dict(entity_ids=None), dict(entity_ids={}),
                   dict(observation_ids=item['observation_ids'] * 2), dict(evidence_ids=item['evidence_ids'] * 2),
                   dict(entity_ids=item['entity_ids'] * 2), dict(summary={}), dict(kind=False),
                   dict(observed_at_raw=None), dict(observed_at_utc=None), dict(observed_at_utc=123),
                   dict(observed_at_utc='2026-01-12'), dict(observed_at_utc='2026-02-30T10:00:00Z'),
                   dict(observed_at_utc='2026-01-12T10:00:00'), dict(private_SECRET='not public')]
        bad.extend(json.dumps([dict(item, **change)]) for change in changes)
        for key in item.keys() - {'observed_at_raw', 'observed_at_utc'}:
            bad.append(json.dumps([{k: v for k, v in item.items() if k != key}]))
        self.allow_corruption()
        for value in bad:
            with self.subTest(value=value):
                self.corrupt(self.run, 'events_json', value)
                await self.denied()

    async def test_corrupt_observation_entity_and_output_context_fail_closed(self):
        original = self.output(self.run)
        observations = json.loads(original['observations_json']); entities = json.loads(original['entities_json'])
        self.allow_corruption()
        values = [('observations_json', 'SECRET broken'), ('observations_json', '{}'),
                  ('observations_json', json.dumps(observations + [observations[0]])),
                  ('observations_json', json.dumps([dict(observations[0], source_locator='')])),
                  ('observations_json', json.dumps([dict(observations[0], processing_run_id=str(uuid4()))])),
                  ('entities_json', 'SECRET broken'), ('entities_json', '{}'),
                  ('entities_json', json.dumps(entities + [entities[0]])),
                  ('entities_json', json.dumps([dict(entities[0], confidence=True)])),
                  ('entities_json', json.dumps([dict(entities[0], candidate_key='SECRET')])),
                  ('case_id', str(uuid4())), ('evidence_id', str(uuid4()))]
        for column, value in values:
            with self.subTest(column=column, value=value):
                self.corrupt(self.run, column, value); await self.denied()
                self.corrupt(self.run, column, original[column])

    async def test_missing_stale_foreign_and_mismatched_event_sources_fail_safe_404(self):
        old = self.output(self.run)
        fresh = await self.process(self.evidence); item = json.loads(self.output(fresh)['events_json'])[0]
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic foreign'})).json()['id']
        foreign_evidence = await self.upload(case=other_case); foreign_run = await self.process(foreign_evidence)
        foreign_obs = json.loads(self.output(foreign_run)['observations_json'])[0]['id']
        self.allow_corruption()
        for change in [dict(observation_ids=[str(uuid4())]), dict(evidence_ids=[str(uuid4())]),
                       dict(evidence_ids=item['evidence_ids'] + [str(uuid4())]),
                       dict(observation_ids=[json.loads(old['observations_json'])[0]['id']]),
                       dict(observation_ids=[foreign_obs]), dict(evidence_ids=[foreign_evidence['id']])]:
            self.corrupt(fresh, 'events_json', json.dumps([dict(item, **change)])); await self.denied()

    async def test_missing_stale_foreign_and_unrelated_participants_fail_safe_404(self):
        old = self.output(self.run)
        fresh = await self.process(self.evidence); output = self.output(fresh)
        item = json.loads(output['events_json'])[0]
        unrelated = next(x for x in json.loads(output['entities_json']) if not set(x['observation_ids']) & set(item['observation_ids']))
        other_case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic foreign'})).json()['id']
        foreign_evidence = await self.upload(case=other_case); foreign_run = await self.process(foreign_evidence)
        foreign = json.loads(self.output(foreign_run)['entities_json'])[0]['id']
        self.allow_corruption()
        for participant in (str(uuid4()), json.loads(old['entities_json'])[0]['id'], foreign, unrelated['id']):
            self.corrupt(fresh, 'events_json', json.dumps([dict(item, entity_ids=[participant])]))
            await self.denied()

    async def test_missing_latest_output_and_duplicate_event_uuid_never_fall_back(self):
        fresh = await self.process(self.evidence)
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_output_delete')
            connection.execute('DELETE FROM processing_outputs WHERE run_id=?', (fresh['id'],))
        await self.denied()
        newer = await self.process(self.evidence)
        other = await self.upload(); other_run = await self.process(other)
        events = json.loads(self.output(other_run)['events_json'])
        events[0]['id'] = json.loads(self.output(newer)['events_json'])[0]['id']
        self.allow_corruption()
        self.corrupt(other_run, 'events_json', json.dumps(events)); await self.denied()

    async def test_exact_completion_fractions_offset_equivalence_and_uuid_ties(self):
        self.fixture('2099-01-12T10:00:00.0000000001Z', 900)
        later = self.fixture('2099-01-12T10:00:00.0000000002Z', 1)
        self.assertEqual((await self.page())['items'], sorted(later, key=lambda x: x['id']))
        self.fixture('2099-01-12T16:30:00.100000+05:30', 2)
        high = self.fixture('2099-01-12T11:00:00.1Z', 901)
        self.assertEqual((await self.page())['items'], sorted(high, key=lambda x: x['id']))
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_run_terminal')
            connection.execute("UPDATE processing_runs SET finished_at='SECRET' WHERE id=?", (str(UUID(int=901)),))
        await self.denied()

    async def test_generic_schema_fixture_optional_times_and_no_participant_allowed(self):
        # Schema-only compatibility, not an implemented text/account producer.
        output = self.output(self.run)
        observation = json.loads(output['observations_json'])[0]
        observation.pop('entity_key', None)
        observation = dict(observation, kind='text.event', raw_value='Synthetic mention', normalized_value='Synthetic mention')
        event = json.loads(output['events_json'])[0]
        event = {key: value for key, value in event.items() if key not in {'observed_at_raw', 'observed_at_utc'}}
        event = dict(event, kind='text.event', summary='<b>Synthetic mention</b>', confidence=0.25,
                     observation_ids=[observation['id']], entity_ids=[])
        expected = self.fixture('2099-01-12T00:00:00Z', 4, [observation], [], [event])
        page = await self.page()
        self.assertEqual(page['items'], expected)
        self.validate('EventPage', page)

    async def test_single_snapshot_during_real_writer_publication(self):
        old = await self.page()
        with patch('backend.processing.process_run'):
            queued = await self.process(self.evidence)
        entered = threading.Event()
        def publish():
            entered.set(); process_run(self.app, queued['id'])
        thread = threading.Thread(target=publish)
        def during_page(connection, case_id, limit, offset):
            thread.start(); self.assertTrue(entered.wait(5)); time.sleep(0.1)
            return _page(connection, case_id, limit, offset)
        try:
            with patch('backend.events._page', side_effect=during_page): observed = await self.page()
        finally:
            if thread.ident is not None: await asyncio.to_thread(thread.join, 10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, old)
        new = await self.page()
        self.assertEqual(new['total'], 2)
        self.assertTrue({x['id'] for x in old['items']}.isdisjoint(x['id'] for x in new['items']))

    async def test_repeated_reads_preserve_history_audit_and_original_and_schedule_no_work(self):
        def snapshot():
            with self.app.state.database.connect() as connection:
                return {table: [tuple(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1')]
                        for table in ('processing_runs', 'processing_outputs', 'evidence', 'audit_events')}
        before = snapshot()
        with patch('backend.processing.process_run') as job:
            first = await self.page(); self.assertEqual(await self.page(), first); await self.page(offset=10 ** 100)
        job.assert_not_called(); self.assertEqual(snapshot(), before)
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content, (ROOT/'fixtures/synthetic-case/network.csv').read_bytes())



class EventLoopbackTests(unittest.TestCase):
    def test_real_http_processing_event_pages_sources_participants_and_failed_input(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:
                listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; p=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                    'SyntheticTokenVerifier({"p05b-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([sys.executable, '-c', code, directory, str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization': 'Bearer p05b-http-synthetic'}, timeout=10) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases', json={'title': 'Synthetic P05B HTTP'}).json()['id']
                    for index, (kind, name) in enumerate([('network_log', 'network.csv'), ('gps', 'gps.csv'),
                                                        ('network_log', 'network.csv'), ('network_log', None)]):
                        data = (ROOT/'fixtures/synthetic-case'/name).read_bytes() if name else b'bad header\n'
                        evidence = client.post(f'/api/v1/cases/{case}/evidence', data={'kind': kind, 'source_label': 'Synthetic HTTP'},
                            files={'file': ('source.csv', data, 'text/csv')}).json()
                        run_url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted = client.post(run_url, headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(accepted.status_code, 202)
                        for _ in range(100):
                            status = client.get(run_url + '/' + accepted.json()['id']).json()['status']
                            if status in ('completed', 'failed'): break
                            time.sleep(0.05)
                        self.assertEqual(status, 'completed' if name else 'failed')
                        response = client.get(f'/api/v1/cases/{case}/events')
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['total'], [2, 3, 5, 5][index])
                    url = f'/api/v1/cases/{case}/events'
                    page = client.get(url, params={'limit': 2, 'offset': 2}).json()
                    self.assertEqual((len(page['items']), page['total'], page['offset']), (2, 5, 2))
                    events = client.get(url).json()['items']
                    entities = {x['id']: x for x in client.get(f'/api/v1/cases/{case}/entities').json()['items']}
                    observations = client.get(f'/api/v1/cases/{case}/observations').json()['items']
                    sources = {x['id']: x for x in observations}
                    for event in events:
                        self.assertEqual(set(event['evidence_ids']), {sources[oid]['evidence_id'] for oid in event['observation_ids']})
                        for eid in event['entity_ids']:
                            self.assertTrue(set(entities[eid]['observation_ids']) & set(event['observation_ids']))
                    self.assertEqual(len([x for x in events if x['kind'] == 'network.activity']), 4)
                    self.assertEqual(client.get(url, params={'processing_run_id': str(uuid4())}).status_code, 400)
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=10)
