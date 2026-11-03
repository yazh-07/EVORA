import asyncio
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import Actor, CaseAccessGrant, SyntheticTokenVerifier
from backend.parsers.text_document import parse_text_document
from backend.parsers.text_entities import TextEntityError, identifier_spans, merge_spans, project_text_entities
from backend.processing import publish_outputs
from backend.processing_provenance import read_processing_provenance
from backend.text_ner import LIMITS, MANIFEST_PATH, LocalWorker, TextNERError, extract_mentions, model_info
from backend import text_ner

SOURCE = b'Alice Smith visited Paris. Device D-007 used AC-8.\r\n'
FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures/text-entities/labeled.json'


class TextEntityTests(unittest.TestCase):
    def test_labeled_exact_span_evaluation_with_real_model(self):
        cases = json.loads(FIXTURE.read_text(encoding='utf8'))
        worker = LocalWorker()
        self.addCleanup(worker.close)
        mentions = worker.request([case['text'] for case in cases])
        predicted = {(m['line'],m['start'],m['end'],m['kind']) for m in mentions}
        expected = {(i,m['start'],m['end'],m['kind'])
                    for i,case in enumerate(cases) for m in case['mentions']}
        correct = len(predicted & expected)
        false_positives = sorted(predicted - expected)
        misses = sorted(expected - predicted)
        print('P13_EVALUATION ' + json.dumps(dict(
            documents=len(cases), expected=len(expected), predicted=len(predicted), correct=correct,
            precision=correct/len(predicted), recall=correct/len(expected),
            false_positives=[(cases[i]['id'], cases[i]['text'][start:end], kind)
                             for i,start,end,kind in false_positives],
            misses=[(cases[i]['id'], cases[i]['text'][start:end], kind)
                    for i,start,end,kind in misses])))
        self.assertEqual({kind for _,_,_,kind in predicted & expected},
                         {'person','organization','location','date','device','account','phone','ip'})

    def test_identifier_boundaries_and_overlapping_model_spans(self):
        source = 'D-007 xD-7 d-7 AC-8-extra +12345 999.0.0.1'
        self.assertEqual(identifier_spans(source), [dict(kind='device',start=0,end=5)])
        self.assertEqual(merge_spans(source,[dict(kind='date',start=0,end=5)]),
                         [dict(kind='device',start=0,end=5)])

    def test_original_line_ids_and_global_unicode_offsets(self):
        source='x\r\n😀 D-007'.encode()
        case,evidence,run=uuid4(),uuid4(),uuid4()
        lines=parse_text_document(source,case_id=case,evidence_id=evidence,processing_run_id=run)
        mentions=[dict(line=1,start=2,end=7,kind='device')]
        projection=project_text_entities(lines,mentions,case_id=case)
        self.assertIs(projection.observations[1],lines[1])
        mention=projection.observations[-1].observation
        self.assertEqual((mention.source_locator,mention.raw_value),('line 2; chars=5:10','D-007'))
        self.assertEqual(set(projection.entities[0].observation_ids),{mention.id,lines[1].observation.id})
        with self.assertRaises(TextEntityError):
            project_text_entities(lines,mentions,case_id=uuid4())
        with self.assertRaises(TextEntityError):
            project_text_entities(lines,[dict(line=1,start=2,end=99,kind='device')],case_id=case)
        with self.assertRaises(TextEntityError):
            project_text_entities(lines,mentions*100001,case_id=case)

    def test_real_worker_timeout_and_queue_deadline(self):
        worker=LocalWorker(timeout=0.001)
        self.addCleanup(worker.close)
        with self.assertRaisesRegex(TextNERError,'TIMEOUT'):
            worker.request(['Alice Smith'])
        self.assertIsNone(worker.process)
        with text_ner._LOCK:
            with self.assertRaisesRegex(TextNERError,'TIMEOUT'):
                worker.request(['Alice Smith'])
        self.assertIsNone(worker.process)

    def test_source_character_limit_includes_line_separators(self):
        case=uuid4()
        data=b'\n'.join([b'x'*20000]*50)
        lines=parse_text_document(data,case_id=case,evidence_id=uuid4(),processing_run_id=uuid4())
        with self.assertRaisesRegex(TextNERError,'INPUT_LIMIT'):
            extract_mentions(data,lines,case_id=case)


class TextEntityProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.app = create_app(self.root/'db.sqlite3', storage_dir=self.root/'private',
            token_verifier=SyntheticTokenVerifier({'p13-one':'investigator-1','p13-two':'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app); await self.life.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://test',
            headers={'Authorization':'Bearer p13-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title':'Synthetic P13'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose(); await self.life.__aexit__(None,None,None); self.temp.cleanup()

    def base(self, evidence):
        return f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/processing-runs"

    async def upload(self, data=SOURCE, kind='document'):
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence',
            data={'kind':kind,'source_label':'Synthetic P13'}, files={'file':('misleading.bin',data,'application/octet-stream')})
        self.assertEqual(response.status_code, 201); return response.json()

    async def start(self, key='one', url=None):
        response = await self.client.post(url or self.url, headers={'Idempotency-Key':key})
        self.assertEqual(response.status_code,202); return response.json()

    async def poll(self, run, url=None):
        response = await self.client.get((url or self.url)+'/'+run['id'])
        self.assertEqual(response.status_code,200); return response.json()

    def rows(self, table):
        with self.app.state.database.connect() as connection:
            return [dict(x) for x in connection.execute('SELECT * FROM '+table+' ORDER BY 1')]

    def private(self, run, evidence=None, actor='investigator-1'):
        return read_processing_provenance(self.app, CaseAccessGrant(Actor(actor),UUID(self.case)),
            UUID((evidence or self.evidence)['id']),UUID(run['id']))

    def validate(self, name, value):
        Draft202012Validator({'$ref':'#/components/schemas/'+name,'components':self.bundle['components']},
            format_checker=FormatChecker()).validate(value)

    async def page(self, name, **params):
        response = await self.client.get(f'/api/v1/cases/{self.case}/'+name,params=params)
        self.assertEqual(response.status_code,200); return response.json()

    async def test_real_processing_and_private_model_provenance(self):
        run=await self.start()
        self.assertEqual((await self.poll(run))['status'],'completed')
        entities=await self.page('entities')
        self.validate('EntityPage',entities)
        self.assertEqual({x['candidate_key'] for x in entities['items']},
                         {'person:Alice Smith','location:Paris','device:D-007','account:AC-8'})
        observations=await self.page('observations')
        self.validate('ObservationPage',observations)
        self.assertEqual(observations['total'],5)
        self.assertEqual((await self.page('events'))['total'],0)
        self.assertTrue(all('observed_at_utc' not in x for x in observations['items']))
        whole=next(x for x in observations['items'] if x['kind']=='text.line')
        for entity in entities['items']:
            self.assertIn(whole['id'],entity['observation_ids'])
            self.assertEqual(entity['evidence_ids'],[self.evidence['id']])
        private=self.private(run)
        self.assertEqual(private['execution']['model'],model_info())
        self.assertEqual(private['execution']['parameters']['max_source_chars'],1000000)
        self.assertEqual(private['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())

    async def test_corrupt_manifest_fails_closed_then_real_retry(self):
        manifest=json.loads(MANIFEST_PATH.read_text(encoding='utf8'))
        manifest['files'][next(iter(manifest['files']))]='0'*64
        path=self.root/'corrupt.json'
        path.write_text(json.dumps(manifest),encoding='utf8')
        worker=LocalWorker(path)
        self.addCleanup(worker.close)
        with patch('backend.text_ner._WORKER',worker):
            failed=await self.start()
        self.assertEqual((await self.poll(failed))['error'],'NLP_MODEL_INVALID')
        self.assertEqual(self.rows('processing_outputs'),[])
        self.assertEqual(self.rows('processing_provenance'),[])
        retry=await self.start('retry')
        self.assertEqual((await self.poll(retry))['status'],'completed')

    async def test_legacy_document_history_and_replay(self):
        legacy=dict(parser_version='document-text/1',normalizer_version='not-used',entity_version='not-used',
                    event_version='not-used',processor_version='processing-lifecycle/4',
                    max_source_bytes=52428800,max_source_lines=100000,provenance_version='processing-provenance/1')
        with patch('backend.processing._versions',return_value=legacy), patch('backend.processing.process_run'):
            old=await self.start('old')
        rows=parse_text_document(SOURCE,case_id=UUID(self.case),evidence_id=UUID(self.evidence['id']),
                                 processing_run_id=UUID(old['id']))
        output=(json.dumps([line.observation.to_wire() for line in rows]),'[]','[]','[]')
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?",(old['id'],))
            running=connection.execute('SELECT * FROM processing_runs WHERE id=?',(old['id'],)).fetchone()
            publish_outputs(connection,running,output)
        before=self.private(old)
        self.assertIsNone(before['execution']['model'])
        latest=await self.start('new')
        self.assertEqual((await self.poll(latest))['status'],'completed')
        self.assertEqual((await self.start('old'))['id'],old['id'])
        self.assertEqual(self.private(old),before)
        self.assertEqual((await self.page('observations',processing_run_id=old['id']))['total'],1)
