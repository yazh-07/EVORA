"""P07 synthetic plain text; real producers/SQL/API with explicit failure controls."""
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import logging
import io
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import Actor, CaseAccessGrant, SyntheticTokenVerifier
from backend.errors import AccessError
from backend.processing import process_run, initialize_processing, publish_outputs
from backend.processing_dispatch import adapter_for
from backend.processing_provenance import read_processing_provenance
from backend.parsers.text_document import (parse_text_document, TextDocumentError,
    MAX_SOURCE_BYTES, MAX_SOURCE_LINES)

ROOT = Path(__file__).resolve().parents[2]
TEXT = '😀 D-7  \r\n\rsecond\nsecond\n'
SOURCE = b'\xef\xbb\xbf' + TEXT.encode('utf-8')


class DocumentParserTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def parse(self, data=SOURCE):
        return parse_text_document(data, **self.context)

    def reject(self, data, code):
        with self.assertRaises(TextDocumentError) as caught:
            self.parse(data)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn('SECRET', str(caught.exception))

    def test_exact_line_text_unicode_offsets_blank_duplicates_and_context(self):
        rows = self.parse()
        self.assertEqual([x.observation.raw_value for x in rows], ['😀 D-7  ', '', 'second', 'second'])
        self.assertEqual([x.observation.source_locator for x in rows],
            ['line 1; chars=0:7', 'line 2; chars=9:9', 'line 3; chars=10:16', 'line 4; chars=17:23'])
        for row in rows:
            wire = row.observation.to_wire()
            start, end = map(int, wire['source_locator'].split('chars=')[1].split(':'))
            self.assertEqual(TEXT[start:end], wire['raw_value'])
            self.assertEqual(wire['raw_value'], wire['normalized_value'])
            self.assertEqual(wire['extraction_confidence'], 0)
            self.assertFalse({'observed_at_raw','observed_at_utc','entity_key'} & wire.keys())
            self.assertTrue(all(wire[k] == str(v) for k,v in self.context.items()))
        self.assertEqual(len({x.observation.id for x in rows}), 4)

    def test_empty_bom_only_final_separator_and_line_endings(self):
        for data, values in [(b'', []), (b'\xef\xbb\xbf', []), (b'\n', ['']),
                (b'\n\n', ['', '']), (b'x\n', ['x']), (b'x\r\n', ['x']),
                (b'x\r', ['x']), (b'x\ry', ['x','y']), (b' \t', [' \t'])]:
            self.assertEqual([x.observation.raw_value for x in self.parse(data)], values)

    def test_only_cr_lf_are_separators_and_only_initial_bom_is_removed(self):
        text = '\ufeffx\v\f\u0085\u2028\u2029\ufeff'
        self.assertEqual(self.parse(text.encode())[0].observation.raw_value, text[1:])
        self.assertEqual(len(self.parse(text.encode())), 1)

    def test_invalid_encoding_nul_source_and_context_are_safe_atomic_failures(self):
        for data, code in [(b'ok\nSECRET\xff','INVALID_UTF8'), (b'ok\nSECRET\x00','NUL_BYTE'),
                           ('SECRET','INVALID_SOURCE')]:
            self.reject(data, code)
        with self.assertRaises(TextDocumentError):
            parse_text_document(b'x', **dict(self.context, case_id='SECRET'))

    def test_immutable_records_wire_copies_and_new_ids(self):
        row = self.parse()[0]
        with self.assertRaises(FrozenInstanceError): row.observation.raw_value = 'changed'
        wire = row.observation.to_wire(); wire['raw_value'] = 'changed'
        self.assertEqual(row.observation.raw_value, '😀 D-7  ')
        self.assertNotEqual(row.observation.id, self.parse()[0].observation.id)

    def test_real_byte_limit_and_overflow(self):
        source = b'x' * MAX_SOURCE_BYTES
        self.assertEqual(len(self.parse(source)[0].observation.raw_value), MAX_SOURCE_BYTES)
        self.reject(source+b'x', 'BYTE_LIMIT')

    def test_real_line_limit_including_blanks_and_overflow(self):
        for source in (b'x\r\n'*MAX_SOURCE_LINES, b'\n'*MAX_SOURCE_LINES):
            self.assertEqual(len(self.parse(source)), 100000)
            self.reject(source+b'x', 'LINE_LIMIT')


class DocumentProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.app = create_app(self.root/'db.sqlite3', storage_dir=self.root/'private',
            token_verifier=SyntheticTokenVerifier({'p07-one':'investigator-1','p07-two':'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app); await self.life.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://test',
            headers={'Authorization':'Bearer p07-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title':'Synthetic P07'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose(); await self.life.__aexit__(None,None,None); self.temp.cleanup()

    def base(self, evidence):
        return f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/processing-runs"

    async def upload(self, data=SOURCE, kind='document'):
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence',
            data={'kind':kind,'source_label':'Synthetic P07'}, files={'file':('misleading.bin',data,'application/octet-stream')})
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

    async def test_real_publication_wire_source_spans_private_versions_and_original(self):
        run = await self.start(); complete = await self.poll(run)
        self.assertEqual((complete['status'],complete['processor_version']),('completed','processing-lifecycle/4'))
        self.validate('ProcessingRun',complete)
        page = await self.page('observations'); self.validate('ObservationPage',page)
        self.assertEqual(page['total'],4)
        self.assertEqual((await self.page('entities'))['total'],0)
        self.assertEqual((await self.page('events'))['total'],0)
        for row in page['items']:
            self.assertFalse({'observed_at_raw','observed_at_utc','entity_key'} & row.keys())
            self.assertEqual((row['kind'],row['evidence_id'],row['processing_run_id']),('text.line',self.evidence['id'],run['id']))
            start,end = map(int,row['source_locator'].split('chars=')[1].split(':'))
            self.assertEqual(TEXT[start:end],row['raw_value'])
        private = self.private(run)
        self.assertEqual(private['execution']['parameters'],{'max_source_bytes':52428800,'max_source_lines':100000})
        self.assertEqual(private['execution']['versions'],dict(parser_version='document-text/1',normalizer_version='not-used',
            entity_version='not-used',event_version='not-used',processor_version='processing-lifecycle/4'))
        self.assertIsNone(private['execution']['model']); self.assertEqual(private['outputs']['entity_ids'],[])
        self.assertEqual(private['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())
        self.assertEqual(set(private['outputs']['observation_ids']),{x['id'] for x in page['items']})
        original = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content,SOURCE)
        seen=[]
        for offset in range(4):
            seen.extend((await self.page('observations',limit=1,offset=offset))['items'])
        self.assertEqual(seen,page['items'])

    async def test_empty_bom_and_blank_lines_are_honest_successes(self):
        for source,count in ((b'',0),(b'\xef\xbb\xbf',0),(b'\n',1)):
            evidence=await self.upload(source); url=self.base(evidence); run=await self.start(str(uuid4()),url)
            self.assertEqual((await self.poll(run,url))['status'],'completed')
            self.assertEqual(len(self.private(run,evidence)['outputs']['observation_ids']),count)

    async def test_encoding_nul_and_actual_line_overflow_fail_without_partial_publication(self):
        for source,error in ((b'ok\nSECRET\xff','TEXT_INVALID_UTF8'),(b'ok\nSECRET\x00','TEXT_NUL_BYTE'),
                              (b'x\n'*100001,'TEXT_LINE_LIMIT')):
            evidence=await self.upload(source);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            failed=await self.poll(run,url)
            self.assertEqual((failed['status'],failed['error']),('failed',error))
            self.assertNotIn('SECRET',json.dumps(failed))
            with self.assertRaises(AccessError): self.private(run,evidence)
        self.assertEqual(self.rows('processing_outputs'),[]);self.assertEqual(self.rows('processing_provenance'),[])
        self.assertEqual((await self.page('observations'))['total'],0)

    async def test_replay_conflict_retry_and_historical_source_immutability(self):
        first=await self.start('same');private=self.private(first);outputs=self.rows('processing_outputs')
        with patch('backend.processing.process_run') as worker:
            replay=await self.start('same')
        worker.assert_not_called();self.assertEqual(replay,await self.poll(first))
        other=await self.upload(b'other')
        response=await self.client.post(self.base(other),headers={'Idempotency-Key':'same'})
        self.assertEqual(response.status_code,409)
        second=await self.start('new');self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(self.private(first),private)
        self.assertIn(outputs[0],self.rows('processing_outputs'))
        historical=await self.page('observations',processing_run_id=first['id'])
        self.assertEqual({x['id'] for x in historical['items']},set(private['outputs']['observation_ids']))

    async def test_changed_frozen_line_limit_and_verification_failure_preserve_old_output(self):
        good=await self.start('good');private=self.private(good)
        with patch('backend.processing.process_run'): queued=await self.start('changed')
        with patch('backend.processing.adapter_for',return_value=replace(adapter_for('document'),max_source_lines=99999)):
            process_run(self.app,queued['id'])
        self.assertEqual((await self.poll(queued))['error'],'PROCESSING_FAILED')
        with patch('backend.processing.verify_publication',side_effect=ValueError('SECRET')):
            failed=await self.start('verify-fail')
        self.assertEqual((await self.poll(failed))['error'],'PROCESSING_FAILED')
        self.assertEqual(self.private(good),private)
        self.assertEqual(len(self.rows('processing_outputs')),1);self.assertEqual(len(self.rows('processing_provenance')),1)
        self.assertEqual((await self.poll(await self.start('retry')))['status'],'completed')

    async def test_auth_case_revocation_missing_source_and_body_validation(self):
        for token,status in (('invalid',401),('Bearer p07-two',404)):
            response=await self.client.post(self.url,headers={'Authorization':token,'Idempotency-Key':'foreign'})
            self.assertEqual(response.status_code,status)
        self.assertEqual((await self.client.post(self.url,headers={'Idempotency-Key':'body'},json={})).status_code,400)
        self.assertEqual(self.rows('processing_runs'),[])
        with patch('backend.processing.process_run'): queued=await self.start('missing')
        with self.app.state.database.connect() as connection:
            path=connection.execute('SELECT storage_path FROM evidence WHERE id=?',(self.evidence['id'],)).fetchone()[0]
        Path(path).unlink();process_run(self.app,queued['id'])
        self.assertEqual((await self.poll(queued))['error'],'SOURCE_UNAVAILABLE')
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id=?',(self.case,))
        self.assertEqual((await self.client.get(self.url)).status_code,404)
        self.assertEqual(self.rows('processing_outputs'),[])

    async def test_restart_marks_held_runs_failed_then_replay_and_retry_are_safe(self):
        good=await self.start('good');private=self.private(good)
        with patch('backend.processing.process_run'): queued=await self.start('interrupted')
        initialize_processing(self.app.state.database)
        failed=await self.poll(queued);self.assertEqual(failed['error'],'PROCESSING_INTERRUPTED')
        self.assertEqual(await self.start('interrupted'),failed)
        self.assertEqual((await self.poll(await self.start('retry')))['status'],'completed')
        self.assertEqual(self.private(good),private)

    async def test_previous_adapter_records_survive_actual_old_guard_upgrade(self):
        saved=[]
        for kind,name in (('network_log','network.csv'),('gps','gps.csv'),('message','messages.csv')):
            evidence=await self.upload((ROOT/'fixtures/synthetic-case'/name).read_bytes(),kind)
            run=await self.start(kind,self.base(evidence));saved.append((run,evidence,self.private(run,evidence)))
        old_outputs=self.rows('processing_outputs');old_private=self.rows('processing_provenance')
        with self.app.state.database.connect() as connection:
            for name in ('processing_provenance_context','processing_completion_provenance'):
                sql=connection.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
                connection.execute('DROP TRIGGER '+name)
                connection.execute(sql.replace(",'processing-lifecycle/4'",''))
        initialize_processing(self.app.state.database)
        run=await self.start('after-upgrade');self.assertEqual((await self.poll(run))['status'],'completed')
        for old,evidence,private in saved:self.assertEqual(self.private(old,evidence),private)
        self.assertTrue(all(x in self.rows('processing_outputs') for x in old_outputs))
        self.assertTrue(all(x in self.rows('processing_provenance') for x in old_private))
        self.assertEqual(((await self.page('observations'))['total'],(await self.page('entities'))['total'],
                         (await self.page('events'))['total']),(18,7,3))

    async def test_document_version_requires_provenance_and_private_corruption_fails_closed(self):
        with patch('backend.processing.process_run'):queued=await self.start('no-private')
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='running' WHERE id=?",(queued['id'],))
                connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                    (queued['id'],self.case,self.evidence['id'],'[]','[]','[]','[]'))
                connection.execute("UPDATE processing_runs SET status='completed',finished_at='2099-01-01T00:00:00Z' WHERE id=?",(queued['id'],))
        good=await self.start('good')
        with self.app.state.database.connect() as connection:
            record=connection.execute('SELECT payload_json FROM processing_provenance WHERE run_id=?',(good['id'],)).fetchone()[0]
            payload=json.loads(record);payload['execution']['parameters']['max_source_lines']=1
            connection.execute('DROP TRIGGER processing_provenance_no_update')
            connection.execute('UPDATE processing_provenance SET payload_json=? WHERE run_id=?',(json.dumps(payload),good['id']))
        with self.assertRaises(AccessError) as caught:self.private(good)
        self.assertEqual(caught.exception.status_code,404)

    async def test_markup_and_date_like_prose_preserved_without_public_logs_or_inference(self):
        text='<script>SECRET_P07</script> D-7 2026-01-12T10:00:00Z'
        evidence=await self.upload(text.encode());log=io.StringIO();handler=logging.StreamHandler(log)
        logger=logging.getLogger();logger.addHandler(handler)
        try:run=await self.start('private-text',self.base(evidence))
        finally:logger.removeHandler(handler);handler.close()
        page=await self.page('observations',evidence_id=evidence['id'])
        self.assertEqual(page['items'][0]['raw_value'],text)
        self.assertNotIn('observed_at_utc',page['items'][0]);self.assertNotIn('observed_at_raw',page['items'][0])
        self.assertNotIn('SECRET_P07',json.dumps(run)+log.getvalue())
        self.assertEqual((await self.page('entities'))['total'],0)
        self.assertEqual((await self.page('events'))['total'],0)


class DocumentLoopbackTests(unittest.TestCase):
    def test_real_http_upload_process_sources_replay_and_invalid_encoding(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:
                listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            code=('from pathlib import Path;import sys,uvicorn;from backend.app import create_app;'
                  'from backend.auth import SyntheticTokenVerifier;p=Path(sys.argv[1]);'
                  'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                  'SyntheticTokenVerifier({"p07-http":"investigator-1"})),host="127.0.0.1",'
                  'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process=subprocess.Popen([sys.executable,'-c',code,directory,str(port)],cwd=ROOT,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer p07-http'},timeout=15) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code==200:break
                        except httpx.TransportError:pass
                        if process.poll() is not None:self.fail('Synthetic server stopped')
                        time.sleep(.1)
                    else:self.fail('Synthetic server startup timed out')
                    case=client.post('/api/v1/cases',json={'title':'Synthetic HTTP P07'}).json()['id']
                    for index,data in enumerate((SOURCE,b'ok\nSECRET\xff')):
                        evidence=client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'document','source_label':'Synthetic'},
                            files={'file':('text.bin',data,'application/octet-stream')}).json()
                        url=f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted=client.post(url,headers={'Idempotency-Key':str(index)});self.assertEqual(accepted.status_code,202)
                        for _ in range(100):
                            run=client.get(url+'/'+accepted.json()['id']).json()
                            if run['status'] in ('completed','failed'):break
                            time.sleep(.05)
                        self.assertEqual(run['status'],'completed' if index==0 else 'failed')
                        if index:self.assertEqual(run['error'],'TEXT_INVALID_UTF8')
                        self.assertEqual(client.post(url,headers={'Idempotency-Key':str(index)}).json(),run)
                    page=client.get(f'/api/v1/cases/{case}/observations').json();self.assertEqual(page['total'],4)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/entities').json()['total'],0)
                    self.assertEqual(client.get(f'/api/v1/cases/{case}/events').json()['total'],0)
                    with closing(sqlite3.connect(Path(directory)/'db.sqlite3')) as connection:
                        self.assertEqual(connection.execute('SELECT count(*) FROM processing_outputs').fetchone()[0],1)
                        payload=json.loads(connection.execute('SELECT payload_json FROM processing_provenance').fetchone()[0])
                        self.assertEqual(payload['execution']['parameters']['max_source_lines'],100000)
                        self.assertEqual(payload['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())
            finally:
                process.terminate()
                try:process.communicate(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=10)
