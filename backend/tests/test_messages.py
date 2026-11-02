"""P06 actual message sources and candidate mentions; labeled scheduling and failure injections."""
import asyncio
from contextlib import closing
import hashlib
import io
import csv
from dataclasses import FrozenInstanceError, replace
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
from backend.processing_dispatch import adapter_for
from backend.parsers.messages_csv import (parse_messages_csv, MessageCSVError, DeviceMention, MAX_SOURCE_BYTES, MAX_DATA_ROWS, MAX_DEVICE_MENTIONS)
from backend.parsers.message_entities import project_message_entities, MessageProjectionError

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class MessageProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root / 'db.sqlite3', storage_dir=self.root / 'private',
            token_verifier=SyntheticTokenVerifier({'p06-synthetic-one': 'investigator-1', 'p06-synthetic-two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer p06-synthetic-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Synthetic P06 case'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.case, self.evidence['id'])
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    def base(self, case, evidence):
        return f'/api/v1/cases/{case}/evidence/{evidence}/processing-runs'

    async def upload(self, kind='message', data=None, case=None):
        if data is None:
            data = (ROOT / 'fixtures/synthetic-case' / {'gps': 'gps.csv', 'message': 'messages.csv', 'network_log': 'network.csv'}.get(kind, 'messages.csv')).read_bytes()
        response = await self.client.post(f'/api/v1/cases/{case or self.case}/evidence',
            data={'kind': kind, 'source_label': 'Synthetic P06'}, files={'file': ('source.csv', data, 'text/csv')})
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

    async def test_real_message_fixture_publication_source_spans_entities_and_private_parameters(self):
        accepted = (await self.start()).json(); complete = await self.poll(accepted)
        self.assertEqual((complete['status'], complete['processor_version']), ('completed', 'processing-lifecycle/3'))
        self.validate('ProcessingRun', complete)
        observations = (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()
        entities = (await self.client.get(f'/api/v1/cases/{self.case}/entities')).json()
        events = (await self.client.get(f'/api/v1/cases/{self.case}/events')).json()
        self.assertEqual((observations['total'], entities['total'], events['total']), (5, 2, 0))
        self.validate('ObservationPage', observations); self.validate('EntityPage', entities); self.validate('EventPage', events)
        by_id = {x['id']: x for x in observations['items']}
        body = next(x for x in observations['items'] if x['kind'] == 'message.body')
        for entity in entities['items']:
            self.assertEqual(entity['confidence'], 0)
            self.assertEqual(entity['evidence_ids'], [self.evidence['id']])
            self.assertIn(body['id'], entity['observation_ids'])
            source = next(by_id[oid] for oid in entity['observation_ids'] if oid != body['id'])
            span = source['source_locator'].split('chars=')[1].split(':')
            self.assertEqual(body['raw_value'][int(span[0]):int(span[1])], source['raw_value'])
            self.assertEqual(entity['candidate_key'], 'device:' + source['raw_value'])
        self.assertEqual({x['candidate_key'] for x in entities['items']}, {'device:D-7', 'device:D-8'})
        self.assertEqual(next(x['raw_value'] for x in observations['items'] if x['kind'] == 'message.sender'), 'synthetic-sender')
        self.assertTrue(all(x['processing_run_id'] == accepted['id'] for x in observations['items']))
        private = self.read(accepted)
        self.assertEqual(private['execution']['parameters']['max_device_mentions'], 100000)
        self.assertEqual(private['execution']['versions']['parser_version'], 'messages-csv/1')
        self.assertEqual(private['execution']['versions']['entity_version'], 'message-candidates/1')
        self.assertEqual(private['execution']['versions']['event_version'], 'not-used')
        self.assertIsNone(private['execution']['model'])
        self.assertEqual(private['outputs']['event_ids'], [])
        self.assertEqual(set(private['outputs']['observation_ids']), set(by_id))
        self.assertEqual(private['input']['sha256'], self.evidence['sha256'])
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content, (ROOT/'fixtures/synthetic-case/messages.csv').read_bytes())

    async def test_network_gps_and_message_outputs_remain_separate_source_records(self):
        old = []
        for kind in ('network_log', 'gps'):
            evidence = await self.upload(kind); url = self.base(self.case, evidence['id'])
            run = (await self.start(kind, url)).json()
            self.assertEqual((await self.poll(run, url))['processor_version'], 'processing-lifecycle/2')
            old.append((run, evidence, self.read(run, evidence), self.by_run('processing_outputs', run)))
        message = (await self.start('message')).json()
        observations = (await self.client.get(f'/api/v1/cases/{self.case}/observations')).json()
        entities = (await self.client.get(f'/api/v1/cases/{self.case}/entities')).json()
        events = (await self.client.get(f'/api/v1/cases/{self.case}/events')).json()
        self.assertEqual((observations['total'], entities['total'], events['total']), (14, 7, 3))
        for key in ('device:D-7', 'device:D-8'):
            matches = [x for x in entities['items'] if x['candidate_key'] == key]
            self.assertEqual(len(matches), 2)
            self.assertEqual(len({x['id'] for x in matches}), 2)
            self.assertTrue(all(x['confidence'] == 0 for x in matches))
        initialize_processing(self.app.state.database)
        for run, evidence, private, output in old:
            self.assertEqual(self.read(run, evidence), private)
            self.assertEqual(self.by_run('processing_outputs', run), output)
        self.assertEqual(self.read(message)['processing_run_id'], message['id'])

    async def test_existing_processor2_version_guards_upgrade_without_rewriting_history(self):
        evidence = await self.upload('network_log'); url = self.base(self.case, evidence['id'])
        old = (await self.start('old-network', url)).json()
        private = self.read(old, evidence); output = self.by_run('processing_outputs', old)
        # Recreate the actual pre-P06 version guards in this temporary database.
        with self.app.state.database.connect() as connection:
            connection.executescript("""
                DROP TRIGGER processing_provenance_context;
                CREATE TRIGGER processing_provenance_context BEFORE INSERT ON processing_provenance
                WHEN NOT EXISTS(SELECT 1 FROM processing_runs r JOIN processing_outputs o ON o.run_id=r.id
                    WHERE r.id=NEW.run_id AND r.status='running' AND r.processor_version='processing-lifecycle/2'
                    AND r.case_id=NEW.case_id AND r.evidence_id=NEW.evidence_id
                    AND o.case_id=r.case_id AND o.evidence_id=r.evidence_id)
                BEGIN SELECT RAISE(ABORT,'Invalid processing provenance context'); END;
                DROP TRIGGER processing_completion_provenance;
                CREATE TRIGGER processing_completion_provenance BEFORE UPDATE OF status ON processing_runs
                WHEN NEW.status='completed' AND NEW.processor_version='processing-lifecycle/2' AND NOT EXISTS(
                    SELECT 1 FROM processing_provenance p WHERE p.run_id=NEW.id AND p.case_id=NEW.case_id
                    AND p.evidence_id=NEW.evidence_id AND p.record_version='processing-provenance/1'
                    AND p.finished_at=NEW.finished_at)
                BEGIN SELECT RAISE(ABORT,'Missing processing provenance'); END;
            """)
        initialize_processing(self.app.state.database)
        message = (await self.start('after-upgrade')).json()
        self.assertEqual((await self.poll(message))['status'], 'completed')
        self.assertEqual(self.read(message)['execution']['versions']['processor_version'], 'processing-lifecycle/3')
        self.assertEqual(self.read(old, evidence), private)
        self.assertEqual(self.by_run('processing_outputs', old), output)

    async def test_message_replay_new_key_and_historical_observations_are_immutable(self):
        first = (await self.start('same')).json(); private = self.read(first)
        old = self.by_run('processing_outputs', first)
        with patch('backend.processing.process_run') as worker:
            replay = (await self.start('same')).json()
        worker.assert_not_called(); self.assertEqual(replay['id'], first['id'])
        fresh = (await self.start('new')).json()
        self.assertNotEqual(fresh['id'], first['id'])
        self.assertEqual(self.read(first), private); self.assertEqual(self.by_run('processing_outputs', first), old)
        self.assertTrue(set(private['outputs']['observation_ids']).isdisjoint(self.read(fresh)['outputs']['observation_ids']))
        historical = (await self.client.get(f'/api/v1/cases/{self.case}/observations', params={'processing_run_id': first['id']})).json()
        self.assertEqual(set(x['id'] for x in historical['items']), set(private['outputs']['observation_ids']))

    async def test_no_mentions_and_header_only_are_genuine_empty_candidate_successes(self):
        for data, count in [(b'message_id,timestamp,sender,body\n', 0),
                            (b'message_id,timestamp,sender,body\nM,bad-time,D-7,no identifiers here\n', 3)]:
            evidence = await self.upload(data=data); url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json()
            self.assertEqual((await self.poll(run, url))['status'], 'completed')
            private = self.read(run, evidence)
            self.assertEqual(len(private['outputs']['observation_ids']), count)
            self.assertEqual(private['outputs']['entity_ids'], [])
            self.assertEqual(private['outputs']['event_ids'], [])

    async def test_message_malformed_or_late_invalid_input_publishes_nothing(self):
        samples = [(b'bad header\n', 'CSV_INVALID_HEADER'), (b'\xffSECRET', 'CSV_INVALID_UTF8'),
                   (b'message_id,timestamp,sender,body\nM,t,s,D-7\nM,t,s,\n', 'CSV_INVALID_ROW'),
                   ((ROOT/'fixtures/synthetic-case/network.csv').read_bytes(), 'CSV_INVALID_HEADER')]
        for data, error in samples:
            evidence = await self.upload(data=data); url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json(); failed = await self.poll(run, url)
            self.assertEqual((failed['status'], failed['error']), ('failed', error))
            self.assertNotIn('SECRET', json.dumps(failed)); self.denied(run, evidence=evidence)
        self.assertEqual(self.rows('processing_outputs'), []); self.assertEqual(self.rows('processing_provenance'), [])

    async def test_actual_mention_and_row_overflow_fail_atomically_through_processing(self):
        header = b'message_id,timestamp,sender,body\n'
        for data, error in [(header + b'M,t,s,' + b'D-7 ' * 100001 + b'\n', 'CSV_MENTION_LIMIT'),
                            (header + b'M,t,s,none\n' * 100001, 'CSV_ROW_LIMIT')]:
            evidence = await self.upload(data=data); url = self.base(self.case, evidence['id'])
            run = (await self.start(str(uuid4()), url)).json()
            failed = await self.poll(run, url)
            self.assertEqual((failed['status'], failed['error']), ('failed', error))
        self.assertEqual(self.rows('processing_outputs'), []); self.assertEqual(self.rows('processing_provenance'), [])

    async def test_message_frozen_mention_limit_and_publication_failure_preserve_old_success(self):
        first = (await self.start('good')).json(); original = self.read(first)
        with patch('backend.processing.process_run'):
            queued = (await self.start('changed')).json()
        with patch('backend.processing.adapter_for', return_value=replace(adapter_for('message'), max_device_mentions=99999)):
            process_run(self.app, queued['id'])
        self.assertEqual((await self.poll(queued))['status'], 'failed')
        with patch('backend.processing.verify_publication', side_effect=ValueError('SECRET message verification')):
            failed = (await self.start('failed')).json()
        self.assertEqual((await self.poll(failed))['error'], 'PROCESSING_FAILED')
        def forbidden_event(connection, run, output):
            body = next(x for x in json.loads(output[0]) if x['kind'] == 'message.body')
            event = dict(id=str(uuid4()), case_id=self.case, kind='message.sent', summary='Synthetic forbidden inference',
                         evidence_ids=[self.evidence['id']], observation_ids=[body['id']], entity_ids=[], confidence=0)
            publish_outputs(connection, run, (output[0], output[1], json.dumps([event]), output[3]))
        with patch('backend.processing.publish_outputs', side_effect=forbidden_event):
            forbidden = (await self.start('forbidden-event')).json()
        self.assertEqual((await self.poll(forbidden))['error'], 'PROCESSING_FAILED')
        self.assertEqual(self.read(first), original)
        self.assertEqual(len(self.rows('processing_outputs')), 1)
        self.assertEqual(len(self.rows('processing_provenance')), 1)

    async def test_message_version_requires_provenance_and_checks_frozen_mention_parameters(self):
        good = (await self.start('good')).json()
        source = self.by_run('processing_outputs', good)
        output = tuple(source[key] for key in ('observations_json','entities_json','events_json','uncertainty_json'))
        with patch('backend.processing.process_run'):
            queued = (await self.start('missing-private')).json()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (queued['id'],))
                connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                                   (queued['id'], self.case, self.evidence['id'], *output))
                connection.execute("UPDATE processing_runs SET status='completed',finished_at='2099-01-01T00:00:00Z' WHERE id=?", (queued['id'],))
        self.assertEqual((await self.poll(queued))['status'], 'queued')
        private = self.by_run('processing_provenance', good)
        payload = json.loads(private['payload_json']); payload['execution']['parameters']['max_device_mentions'] = 1
        # Explicit corruption in this test's temporary database only.
        with self.app.state.database.connect() as connection:
            connection.execute('DROP TRIGGER processing_provenance_no_update')
            connection.execute('UPDATE processing_provenance SET payload_json=? WHERE run_id=?', (json.dumps(payload), good['id']))
        self.denied(good)

    async def test_message_auth_case_revocation_and_selector_denials(self):
        for headers, status in [({'Authorization': 'invalid'}, 401), ({'Authorization': 'Bearer p06-synthetic-two'}, 404)]:
            response = await self.client.post(self.url, headers=dict(headers, **{'Idempotency-Key': str(uuid4())}))
            self.assertEqual(response.status_code, status)
        self.assertEqual(self.rows('processing_runs'), [])
        run = (await self.start()).json()
        self.denied(run, actor='investigator-2')
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?', (self.case,))
        self.denied(run)
        self.assertEqual((await self.start()).status_code, 404)
        self.assertEqual((await self.client.get(f'/api/v1/cases/{self.case}/observations')).status_code, 404)

    async def test_message_body_markup_is_preserved_without_logs_or_sender_identity(self):
        marker = 'SENSITIVE_P06_SENTINEL'
        data = f'message_id,timestamp,sender,body\nM,unresolved,D-9,<script>{marker}</script> D-7\n'.encode()
        evidence = await self.upload(data=data); url = self.base(self.case, evidence['id'])
        log = io.StringIO(); handler = logging.StreamHandler(log); root = logging.getLogger()
        root.addHandler(handler); level = root.level; root.setLevel(logging.INFO)
        try:
            run = (await self.start('SENSITIVE_P06_KEY', url)).json()
            complete = await self.poll(run, url)
            audit = (await self.client.get(f'/api/v1/cases/{self.case}/audit-events')).json()
        finally:
            root.setLevel(level); root.removeHandler(handler); handler.close()
        self.assertNotIn(marker, json.dumps([run, complete, audit]) + log.getvalue())
        self.assertNotIn('SENSITIVE_P06_KEY', log.getvalue())
        output = self.by_run('processing_outputs', run)
        observations = json.loads(output['observations_json'])
        self.assertEqual(next(x['raw_value'] for x in observations if x['kind'] == 'message.body'), f'<script>{marker}</script> D-7')
        self.assertEqual([x['candidate_key'] for x in json.loads(output['entities_json'])], ['device:D-7'])
        self.assertTrue(all('observed_at_utc' not in x for x in observations))


class MessageParserTests(unittest.TestCase):
    def setUp(self): self.context = dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def parse(self, data=None):
        return parse_messages_csv(data if data is not None else (ROOT/'fixtures/synthetic-case/messages.csv').read_bytes(), **self.context)

    def csv(self, body, timestamp='2026-01-12T10:03:00Z', sender='source', message='M'):
        buffer = io.StringIO(newline=''); writer = csv.writer(buffer)
        writer.writerow(['message_id','timestamp','sender','body']); writer.writerow([message,timestamp,sender,body])
        return buffer.getvalue().encode('utf-8')

    def rejected(self, data, code):
        with self.assertRaises(MessageCSVError) as caught: self.parse(data)
        self.assertEqual(caught.exception.code, code); self.assertNotIn('SECRET', str(caught.exception))

    def test_fixture_exact_tokens_spans_context_and_frozen_rows(self):
        rows = self.parse(); self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row.message_id, row.timestamp, row.sender), ('MSG-1','2026-01-12T10:03:00Z','synthetic-sender'))
        self.assertEqual([(x.start,x.end,x.text) for x in row.mentions], [(8,11,'D-7'),(16,19,'D-8')])
        self.assertEqual((row.case_id,row.evidence_id,row.processing_run_id), tuple(self.context.values()))
        with self.assertRaises(FrozenInstanceError): row.body = 'changed'
        with self.assertRaises(FrozenInstanceError): row.mentions[0].start = 0

    def test_literal_case_sensitive_unicode_word_and_hyphen_boundaries(self):
        body = 'D-7 D-8 D-70 D-007 d-7 XD-7 D-7x D-7_ D-7-8 _D-7 -D-7 D-7é éD-7 D-7١ ١D-7 D-７ D–7 (D-7),D-8.'
        row = self.parse(self.csv(body))[0]
        self.assertEqual([x.text for x in row.mentions], ['D-7','D-8','D-70','D-007','D-7','D-8'])
        self.assertTrue(all(body[x.start:x.end] == x.text for x in row.mentions))

    def test_bom_multiline_escaped_csv_and_codepoint_not_byte_spans(self):
        body = '😀 Devices D-7\r\nnot ownership D-8, "quoted"'
        row = self.parse(b'\xef\xbb\xbf' + self.csv(body, sender=' sender, "literal" '))[0]
        self.assertEqual(row.body, body); self.assertEqual(row.sender, ' sender, "literal" ')
        self.assertEqual((row.start_line,row.end_line), (2,3))
        self.assertEqual(row.mentions[0].start, body.index('D-7'))
        self.assertNotEqual(row.mentions[0].start, len(body[:row.mentions[0].start].encode('utf-8')))

    def test_line_endings_duplicate_rows_and_empty_layout(self):
        for ending in (b'\n',b'\r',b'\r\n'):
            data = b'message_id,timestamp,sender,body' + ending + (b'M,t,s,D-7' + ending) * 2
            rows = self.parse(data)
            self.assertEqual([x.start_line for x in rows], [2,3])
            self.assertEqual([x.message_id for x in rows], ['M','M'])
        self.assertEqual(self.parse(b'message_id,timestamp,sender,body\n'), ())

    def test_bad_headers_rows_encoding_quotes_and_context_fail_safely(self):
        for data, code in [(b'', 'INVALID_HEADER'), (b'body,sender,timestamp,message_id\n', 'INVALID_HEADER'),
                           (b'\xef\xbb\xbf\xef\xbb\xbfmessage_id,timestamp,sender,body\n', 'INVALID_HEADER'),
                           (b'\xffSECRET', 'INVALID_UTF8'), (self.csv('SECRET\x00'), 'MALFORMED_CSV'),
                           (b'message_id,timestamp,sender,body\nM,t,s,"SECRET', 'MALFORMED_CSV'),
                           (b'message_id,timestamp,sender,body\nM,t,s\n', 'INVALID_ROW'),
                           (b'message_id,timestamp,sender,body\nM,t,s,D-7,extra\n', 'INVALID_ROW')]:
            self.rejected(data, code)
        for index in range(4):
            fields = ['M','t','s','D-7']; fields[index] = ' '
            self.rejected(('message_id,timestamp,sender,body\n'+','.join(fields)+'\n').encode(), 'INVALID_ROW')
        self.rejected('SECRET', 'INVALID_SOURCE')
        with self.assertRaises(MessageCSVError): parse_messages_csv(b'', **dict(self.context, case_id='SECRET'))

    def test_real_byte_and_row_limits_and_overflow(self):
        prefix = b'message_id,timestamp,sender,body\nM,t,s,'
        data = prefix + b'x' * (MAX_SOURCE_BYTES-len(prefix))
        self.assertEqual(len(self.parse(data)[0].body), MAX_SOURCE_BYTES-len(prefix))
        self.rejected(data+b'x', 'BYTE_LIMIT'); del data
        data = b'message_id,timestamp,sender,body\n' + b'M,t,s,no mention\n' * MAX_DATA_ROWS
        rows = self.parse(data); self.assertEqual(len(rows), 100000); del rows
        self.rejected(data+b'M,t,s,no mention\n', 'ROW_LIMIT')

    def test_real_mention_limit_in_one_body_and_across_rows(self):
        header = b'message_id,timestamp,sender,body\n'
        data = header + b'M,t,s,' + b'D-7 ' * MAX_DEVICE_MENTIONS + b'\n'
        rows = self.parse(data); self.assertEqual(len(rows[0].mentions), 100000); del rows
        self.rejected(data.rstrip(b'\n')+b'D-8\n', 'MENTION_LIMIT')
        half = b'M,t,s,' + b'D-7 ' * 50000 + b'\n'
        rows = self.parse(header+half*2); self.assertEqual(sum(len(x.mentions) for x in rows), 100000); del rows
        self.rejected(header+half*2+b'M,t,s,D-8\n', 'MENTION_LIMIT')


class MessageProjectionTests(unittest.TestCase):
    setUp = MessageParserTests.setUp
    parse = MessageParserTests.parse
    csv = MessageParserTests.csv

    def test_fixture_projection_retains_body_metadata_span_refs_and_unavailable_scores(self):
        rows = self.parse(); before = rows
        projection = project_message_entities(rows, case_id=self.context['case_id'])
        self.assertEqual(projection.version, 'message-candidates/1')
        self.assertEqual((len(projection.observations), len(projection.entities)), (5,2))
        sources = {x.observation.id: x.observation for x in projection.observations}
        body = next(x for x in sources.values() if x.kind == 'message.body')
        self.assertEqual(body.raw_value, rows[0].body)
        self.assertEqual({x.candidate_key for x in projection.entities}, {'device:D-7','device:D-8'})
        for entity in projection.entities:
            self.assertEqual(entity.evidence_ids, (rows[0].evidence_id,))
            self.assertIn(body.id, entity.observation_ids)
            self.assertEqual(entity.confidence, 0)
        self.assertTrue(all(x.extraction_confidence == 0 and x.raw_value == x.normalized_value for x in sources.values()))
        self.assertEqual(rows, before)
        with self.assertRaises(FrozenInstanceError): projection.entities[0].canonical_label = 'changed'
        newer = project_message_entities(rows, case_id=self.context['case_id'])
        self.assertTrue(set(sources).isdisjoint(x.observation.id for x in newer.observations))

    def test_repeated_mentions_and_rows_group_exact_keys_with_all_context_refs(self):
        data = b'message_id,timestamp,sender,body\nM,t,s,D-7 D-7 D-8 D-007 D-70\nM,t,s,D-7\n'
        rows = self.parse(data); projection = project_message_entities(rows, case_id=self.context['case_id'])
        entities = {x.candidate_key: x for x in projection.entities}
        self.assertEqual(set(entities), {'device:D-7','device:D-8','device:D-007','device:D-70'})
        self.assertEqual(len(entities['device:D-7'].observation_ids), 5)  # two bodies, three occurrences
        by_id = {x.observation.id:x.observation for x in projection.observations}
        self.assertEqual(sum(by_id[x].kind == 'message.body' for x in entities['device:D-7'].observation_ids), 2)

    def test_no_body_match_does_not_identify_sender_or_metadata(self):
        rows = self.parse(self.csv('d-7 XD-7 D-7x', sender='D-7', message='D-8'))
        projection = project_message_entities(rows, case_id=self.context['case_id'])
        self.assertEqual((len(projection.observations), projection.entities), (3, ()))
        empty = project_message_entities((), case_id=self.context['case_id'])
        self.assertEqual((empty.observations,empty.entities), ((),()))

    def test_invalid_uncertain_and_precise_source_time_is_preserved_without_invention(self):
        for raw, utc in [('2026-01-12T15:30:00.123456789+05:30','2026-01-12T10:00:00.123456789Z'),
                         ('2026-01-12T10:00:00',None), ('2026-01-12T10:00:00-00:00',None), ('SECRET invalid',None)]:
            rows = self.parse(self.csv('D-7', timestamp=raw))
            projection = project_message_entities(rows, case_id=self.context['case_id'])
            for result in projection.observations:
                self.assertEqual(result.observation.observed_at_raw, raw)
                self.assertEqual(result.observation.observed_at_utc, utc)
                self.assertEqual(result.time.utc_value, utc)
                if utc is None: self.assertNotIn('observed_at_utc', result.observation.to_wire())

    def test_projection_rejects_mixed_context_overlaps_and_forged_spans_atomically(self):
        row = self.parse(self.csv('😀 D-7'))[0]
        bad = [(replace(row, case_id=uuid4()),), (replace(row, processing_run_id='SECRET'),),
               (row,row), (replace(row,start_line=1),), (replace(row,end_line=1),),
               (replace(row,mentions=()),), (replace(row,mentions=(DeviceMention(2.0,5,'D-7'),)),),
               (replace(row,mentions=(DeviceMention(2,5,'D-8'),)),), (replace(row,sender=' '),),
               (row, replace(row,start_line=3,end_line=3,processing_run_id=uuid4())),
               (row, replace(row,start_line=3,end_line=3,evidence_id=uuid4()))]
        for rows in bad:
            with self.assertRaises(MessageProjectionError): project_message_entities(rows, case_id=self.context['case_id'])
        self.assertEqual(project_message_entities((row,), case_id=self.context['case_id']).entities[0].candidate_key, 'device:D-7')


class MessageLoopbackTests(unittest.TestCase):
    def test_real_http_message_source_citations_replay_and_failed_publication(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:
                listener.bind(('127.0.0.1',0)); port = listener.getsockname()[1]
            code = ('from pathlib import Path; import sys,uvicorn; from backend.app import create_app; '
                    'from backend.auth import SyntheticTokenVerifier; p=Path(sys.argv[1]); '
                    'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                    'SyntheticTokenVerifier({"p06-http-synthetic":"investigator-1"})),host="127.0.0.1",'
                    'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process = subprocess.Popen([PYTHON,'-c',code,directory,str(port)], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer p06-http-synthetic'},timeout=15) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code == 200: break
                        except httpx.TransportError: pass
                        if process.poll() is not None: self.fail('Synthetic HTTP server stopped')
                        time.sleep(0.1)
                    else: self.fail('Synthetic HTTP server startup timed out')
                    case = client.post('/api/v1/cases',json={'title':'Synthetic P06 HTTP'}).json()['id']
                    good = (ROOT/'fixtures/synthetic-case/messages.csv').read_bytes()
                    for index,data in enumerate((good, b'message_id,timestamp,sender,body\nM,t,s,\n')):
                        evidence = client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'message','source_label':'Synthetic'},
                            files={'file':('misleading.bin',data,'application/octet-stream')}).json()
                        url = f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted = client.post(url,headers={'Idempotency-Key':str(index)})
                        self.assertEqual(accepted.status_code,202)
                        for _ in range(100):
                            run = client.get(url+'/'+accepted.json()['id']).json()
                            if run['status'] in ('completed','failed'): break
                            time.sleep(0.05)
                        self.assertEqual(run['status'], 'completed' if index == 0 else 'failed')
                        replay = client.post(url,headers={'Idempotency-Key':str(index)})
                        self.assertEqual(replay.json(), run)
                    sources = client.get(f'/api/v1/cases/{case}/observations').json()
                    entities = client.get(f'/api/v1/cases/{case}/entities').json()
                    events = client.get(f'/api/v1/cases/{case}/events').json()
                    self.assertEqual((sources['total'],entities['total'],events['total']), (5,2,0))
                    body = next(x for x in sources['items'] if x['kind'] == 'message.body')
                    self.assertTrue(all(body['id'] in x['observation_ids'] for x in entities['items']))
                    with closing(sqlite3.connect(Path(directory)/'db.sqlite3')) as connection:
                        self.assertEqual(connection.execute('SELECT count(*) FROM processing_outputs').fetchone()[0],1)
                        self.assertEqual(connection.execute('SELECT count(*) FROM processing_provenance').fetchone()[0],1)
                        payload = json.loads(connection.execute('SELECT payload_json FROM processing_provenance').fetchone()[0])
                        self.assertEqual(payload['execution']['parameters']['max_device_mentions'],100000)
                        self.assertEqual(payload['execution']['versions']['event_version'],'not-used')
                        self.assertEqual(payload['input']['sha256'],hashlib.sha256(good).hexdigest())
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.communicate(timeout=10)

