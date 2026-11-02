"""P11 synthetic exported activity; actual producers/SQL/HTTP with labeled fault controls."""
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
import csv
import hashlib
import io
import json
import logging
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
from backend.parsers.mobile_csv import parse_mobile_csv, MobileCSVError, MAX_SOURCE_BYTES, MAX_DATA_ROWS
from backend.parsers.mobile_events import project_mobile_records, MobileProjectionError

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (b'timestamp,device_id,event,detail\n'
    b'2026-01-12T15:30:00.123456789+05:30,D-007,authentication.success,"Synthetic login, not ownership"\n'
    b'2026-01-12T10:00:00,D-8,app.open,Synthetic application report\n')


class MobileParserProjectionTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def parse(self, source=SOURCE):
        return parse_mobile_csv(source, **self.context)

    def project(self, rows=None):
        return project_mobile_records(self.parse() if rows is None else rows, case_id=self.context['case_id'])

    def csv(self, rows):
        output=io.StringIO(newline='');writer=csv.writer(output)
        writer.writerow(['timestamp','device_id','event','detail']);writer.writerows(rows)
        return output.getvalue().encode()

    def reject(self, source, code):
        with self.assertRaises(MobileCSVError) as caught:self.parse(source)
        self.assertEqual(caught.exception.code,code);self.assertNotIn('SECRET',str(caught.exception))

    def test_exact_fixture_rows_original_values_context_and_immutability(self):
        rows=self.parse();self.assertEqual(len(rows),2)
        self.assertEqual((rows[0].device_id,rows[0].event,rows[0].detail),
                         ('D-007','authentication.success','Synthetic login, not ownership'))
        self.assertEqual([(x.start_line,x.end_line) for x in rows],[(2,2),(3,3)])
        for row in rows:self.assertEqual((row.case_id,row.evidence_id,row.processing_run_id),tuple(self.context.values()))
        with self.assertRaises(FrozenInstanceError):rows[0].device_id='changed'

    def test_bom_multiline_quotes_unicode_whitespace_and_line_endings(self):
        raw=' 😀 detail, "quoted"\r\nsecond line '
        rows=self.parse(b'\xef\xbb\xbf'+self.csv([[' time ',' D-7 ',' auth ',raw]]))
        self.assertEqual((rows[0].timestamp,rows[0].device_id,rows[0].event,rows[0].detail),(' time ',' D-7 ',' auth ',raw))
        self.assertEqual((rows[0].start_line,rows[0].end_line),(2,3))
        for ending in (b'\n',b'\r',b'\r\n'):
            rows=self.parse(b'timestamp,device_id,event,detail'+ending+b't,D-7,e,d'+ending)
            self.assertEqual((len(rows),rows[0].start_line,rows[0].end_line),(1,2,2))

    def test_header_only_and_duplicate_rows_are_preserved(self):
        self.assertEqual(self.parse(b'timestamp,device_id,event,detail\n'),())
        rows=self.parse(b'timestamp,device_id,event,detail\nt,D-7,e,d\nt,D-7,e,d\n')
        self.assertEqual([x.start_line for x in rows],[2,3]);self.assertEqual([x.device_id for x in rows],['D-7','D-7'])

    def test_bad_layout_cells_encoding_quotes_nul_source_and_context_fail_safely(self):
        for source,code in [(b'','INVALID_HEADER'),(b'device_id,timestamp,event,detail\n','INVALID_HEADER'),
            (b'\xef\xbb\xbf\xef\xbb\xbftimestamp,device_id,event,detail\n','INVALID_HEADER'),
            (b'\xffSECRET','INVALID_UTF8'),(b'timestamp,device_id,event,detail\nt,D-7,e,SECRET\x00','MALFORMED_CSV'),
            (b'timestamp,device_id,event,detail\nt,D-7,e,"SECRET','MALFORMED_CSV'),
            (b'timestamp,device_id,event,detail\nt,D-7,e','INVALID_ROW'),
            (b'timestamp,device_id,event,detail\nt,D-7,e,d,extra','INVALID_ROW'),('SECRET','INVALID_SOURCE')]:
            self.reject(source,code)
        for index in range(4):
            fields=['t','D-7','e','d'];fields[index]=' '
            self.reject(self.csv([fields]),'INVALID_ROW')
        with self.assertRaises(MobileCSVError):parse_mobile_csv(SOURCE,**dict(self.context,case_id='SECRET'))

    def test_real_byte_limit_and_overflow(self):
        prefix=b'timestamp,device_id,event,detail\nt,D-7,e,'
        source=prefix+b'x'*(MAX_SOURCE_BYTES-len(prefix))
        self.assertEqual(len(self.parse(source)[0].detail),MAX_SOURCE_BYTES-len(prefix))
        self.reject(source+b'x','BYTE_LIMIT')

    def test_real_row_limit_and_atomic_overflow(self):
        source=b'timestamp,device_id,event,detail\n'+b't,D-7,e,d\n'*MAX_DATA_ROWS
        self.assertEqual(len(self.parse(source)),100000)
        self.reject(source+b't,D-8,e,d\n','ROW_LIMIT')

    def test_source_projection_exact_joins_raw_values_keys_scores_and_frozen_records(self):
        rows=self.parse();projection=self.project(rows)
        self.assertEqual((len(projection.observations),len(projection.entities),len(projection.events)),(6,2,2))
        sources={x.observation.id:x.observation for x in projection.observations}
        entities={x.id:x for x in projection.entities}
        for result in projection.events:
            event=result.event;entity=entities[event.entity_ids[0]]
            self.assertEqual((event.kind,event.confidence),('mobile.activity',0))
            self.assertTrue(event.summary.startswith('Source mobile log reports: '))
            self.assertEqual(event.evidence_ids,(self.context['evidence_id'],))
            self.assertEqual(len(event.observation_ids),3)
            self.assertEqual({sources[x].kind for x in event.observation_ids},{'mobile.device','mobile.event','mobile.detail'})
            self.assertTrue(set(entity.observation_ids)&set(event.observation_ids))
            self.assertEqual(entity.candidate_key,'device:'+entity.canonical_label)
            self.assertEqual((entity.kind,entity.confidence),('device',0))
            for oid in event.observation_ids:
                self.assertEqual((sources[oid].observed_at_raw,sources[oid].observed_at_utc),
                                 (event.observed_at_raw,event.observed_at_utc))
                self.assertEqual(sources[oid].raw_value,sources[oid].normalized_value)
                self.assertEqual(sources[oid].extraction_confidence,0)
        with self.assertRaises(FrozenInstanceError):projection.entities[0].confidence=1
        with self.assertRaises(FrozenInstanceError):projection.events[0].event.summary='changed'
        before=projection.observations[0].observation.to_wire();before['raw_value']='changed'
        self.assertNotEqual(projection.observations[0].observation.raw_value,'changed')
        self.assertTrue(set(sources).isdisjoint(x.observation.id for x in self.project(rows).observations))

    def test_case_leading_zero_and_duplicate_keys_group_only_exact_devices(self):
        rows=self.parse(self.csv([['t',device,'e','d'] for device in ('D-7','D-7','d-7','D-007',' D-7 ')]))
        projection=self.project(rows)
        self.assertEqual((len(projection.observations),len(projection.entities),len(projection.events)),(15,4,5))
        by_key={x.candidate_key:x for x in projection.entities}
        self.assertEqual(set(by_key),{'device:D-7','device:d-7','device:D-007','device: D-7 '})
        self.assertEqual(len(by_key['device:D-7'].observation_ids),2)
        self.assertEqual(sum(x.event.entity_ids==(by_key['device:D-7'].id,) for x in projection.events),2)

    def test_precise_utc_unknown_invalid_and_ambiguous_time_never_invented(self):
        for raw,utc in [('2026-01-12T15:30:00.123456789+05:30','2026-01-12T10:00:00.123456789Z'),
                        ('2026-01-12T10:00:00',None),('2026-01-12T10:00:00-00:00',None),
                        ('2026-01-12T10:00:00 IST',None),('SECRET invalid',None)]:
            result=self.project(self.parse(self.csv([[raw,'D-7','e','d']])))
            for wire in [x.observation.to_wire() for x in result.observations]+[result.events[0].event.to_wire()]:
                self.assertEqual(wire['observed_at_raw'],raw)
                if utc is None:self.assertNotIn('observed_at_utc',wire)
                else:self.assertEqual(wire['observed_at_utc'],utc)
        empty=self.project(())
        self.assertEqual((empty.observations,empty.entities,empty.events),((),(),()))

    def test_mixed_case_evidence_runs_invalid_context_and_overlapping_rows_rejected_atomically(self):
        row=self.parse()[0]
        for rows in [(replace(row,case_id=uuid4()),),(replace(row,processing_run_id='SECRET'),),
                     (row,row),(replace(row,start_line=True),),(replace(row,end_line=1),),
                     (replace(row,event=' '),),(replace(row,detail='SECRET\x00'),),
                     (row,replace(row,start_line=3,end_line=3,evidence_id=uuid4())),
                     (row,replace(row,start_line=3,end_line=3,processing_run_id=uuid4()))]:
            with self.assertRaises(MobileProjectionError):self.project(rows)
        self.assertEqual(len(self.project((row,)).events),1)


class MobileProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.app = create_app(self.root/'db.sqlite3', storage_dir=self.root/'private',
            token_verifier=SyntheticTokenVerifier({'p11-one':'investigator-1','p11-two':'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app); await self.life.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://test',
            headers={'Authorization':'Bearer p11-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title':'Synthetic P11'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose(); await self.life.__aexit__(None,None,None); self.temp.cleanup()

    def base(self, evidence):
        return f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/processing-runs"

    async def upload(self, data=SOURCE, kind='mobile_log'):
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence',
            data={'kind':kind,'source_label':'Synthetic P11'}, files={'file':('misleading.bin',data,'application/octet-stream')})
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

    async def test_actual_source_entity_event_api_schema_joins_time_and_private_provenance(self):
        run=await self.start();complete=await self.poll(run)
        self.assertEqual((complete['status'],complete['processor_version']),('completed','processing-lifecycle/5'))
        self.validate('ProcessingRun',complete)
        pages={name:await self.page(name) for name in ('observations','entities','events')}
        for name,schema in [('observations','ObservationPage'),('entities','EntityPage'),('events','EventPage')]:self.validate(schema,pages[name])
        self.assertEqual(tuple(pages[name]['total'] for name in ('observations','entities','events')),(6,2,2))
        sources={x['id']:x for x in pages['observations']['items']};entities={x['id']:x for x in pages['entities']['items']}
        for event in pages['events']['items']:
            self.assertEqual((event['kind'],event['confidence']),('mobile.activity',0))
            self.assertEqual(event['evidence_ids'],[self.evidence['id']])
            self.assertEqual(len(event['observation_ids']),3)
            entity=entities[event['entity_ids'][0]]
            self.assertTrue(set(entity['observation_ids'])&set(event['observation_ids']))
            device=next(sources[oid] for oid in event['observation_ids'] if sources[oid]['kind']=='mobile.device')
            self.assertEqual(device['entity_key'],entity['candidate_key'])
            self.assertEqual(entity['canonical_label'],device['raw_value'])
            for oid in event['observation_ids']:
                self.assertEqual(sources[oid]['processing_run_id'],run['id'])
                self.assertEqual(sources[oid]['observed_at_raw'],event['observed_at_raw'])
                self.assertEqual(sources[oid].get('observed_at_utc'),event.get('observed_at_utc'))
        private=self.private(run)
        self.assertEqual(private['execution']['parameters'],{'max_source_bytes':52428800,'max_data_rows':100000})
        self.assertEqual(private['execution']['versions'],dict(parser_version='mobile-csv/1',normalizer_version='source-normalization/1',
            entity_version='mobile-identifiers/1',event_version='mobile-source-events/1',processor_version='processing-lifecycle/5'))
        self.assertIsNone(private['execution']['model'])
        for name,field in [('observations','observation_ids'),('entities','entity_ids'),('events','event_ids')]:
            self.assertEqual(set(private['outputs'][field]),{x['id'] for x in pages[name]['items']})
            seen=[]
            for offset in range(pages[name]['total']):seen.extend((await self.page(name,limit=1,offset=offset))['items'])
            self.assertEqual(seen,pages[name]['items'])
        self.assertEqual(private['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())
        original=await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content,SOURCE)

    async def test_header_empty_duplicate_rows_and_exact_device_grouping_through_actual_apis(self):
        for data,counts in [(b'timestamp,device_id,event,detail\n',(0,0,0)),
            (b'timestamp,device_id,event,detail\nt,D-7,e,d\nt,D-7,e,d\nt,d-7,e,d\nt,D-007,e,d\n',(12,3,4))]:
            evidence=await self.upload(data);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            self.assertEqual((await self.poll(run,url))['status'],'completed')
            private=self.private(run,evidence)
            self.assertEqual(tuple(len(private['outputs'][name]) for name in ('observation_ids','entity_ids','event_ids')),counts)
        entities=await self.page('entities')
        self.assertEqual({x['candidate_key'] for x in entities['items']},{'device:D-7','device:d-7','device:D-007'})
        self.assertEqual(len(next(x for x in entities['items'] if x['candidate_key']=='device:D-7')['observation_ids']),2)

    async def test_malformed_wrong_layout_encoding_late_row_and_actual_overflow_publish_nothing(self):
        for data,error in [(b'', 'CSV_INVALID_HEADER'),(b'\xffSECRET','CSV_INVALID_UTF8'),
            (b'timestamp,device_id,event,detail\nt,D-7,e,d\nt,D-8,e,\n','CSV_INVALID_ROW'),
            ((ROOT/'fixtures/synthetic-case/network.csv').read_bytes(),'CSV_INVALID_HEADER'),
            (b'timestamp,device_id,event,detail\n'+b't,D-7,e,d\n'*100001,'CSV_ROW_LIMIT')]:
            evidence=await self.upload(data);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            failed=await self.poll(run,url);self.assertEqual((failed['status'],failed['error']),('failed',error))
            self.assertNotIn('SECRET',json.dumps(failed))
            with self.assertRaises(AccessError):self.private(run,evidence)
        self.assertEqual(self.rows('processing_outputs'),[]);self.assertEqual(self.rows('processing_provenance'),[])
        self.assertEqual((await self.page('observations'))['total'],0)
        self.assertEqual((await self.page('entities'))['total'],0);self.assertEqual((await self.page('events'))['total'],0)

    async def test_replay_conflict_new_key_and_old_source_entity_event_history_unchanged(self):
        first=await self.start('same');private=self.private(first);output=self.rows('processing_outputs')[0]
        with patch('backend.processing.process_run') as worker:replay=await self.start('same')
        worker.assert_not_called();self.assertEqual(replay,await self.poll(first))
        other=await self.upload(SOURCE)
        self.assertEqual((await self.client.post(self.base(other),headers={'Idempotency-Key':'same'})).status_code,409)
        second=await self.start('new');self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(self.private(first),private);self.assertIn(output,self.rows('processing_outputs'))
        historical=await self.page('observations',processing_run_id=first['id'])
        self.assertEqual({x['id'] for x in historical['items']},set(private['outputs']['observation_ids']))
        fresh=self.private(second)
        for name in ('observation_ids','entity_ids','event_ids'):
            self.assertTrue(set(private['outputs'][name]).isdisjoint(fresh['outputs'][name]))

    async def test_concurrent_replay_and_duplicate_worker_claim_publish_once(self):
        import asyncio
        runs=await asyncio.gather(*(self.start('concurrent') for _ in range(8)))
        self.assertEqual(len({x['id'] for x in runs}),1)
        self.assertEqual((await self.poll(runs[0]))['status'],'completed')
        before=self.rows('processing_outputs');private=self.private(runs[0])
        process_run(self.app,runs[0]['id'])
        self.assertEqual(self.rows('processing_outputs'),before);self.assertEqual(self.private(runs[0]),private)
        for table in ('processing_runs','processing_outputs','processing_provenance'):self.assertEqual(len(self.rows(table)),1)

    async def test_changed_frozen_versions_and_verification_or_bad_participant_roll_back_atomically(self):
        good=await self.start('good');original=self.private(good)
        with patch('backend.processing.process_run'):queued=await self.start('changed')
        with patch('backend.processing.adapter_for',return_value=replace(adapter_for('mobile_log'),max_data_rows=99999)):
            process_run(self.app,queued['id'])
        self.assertEqual((await self.poll(queued))['error'],'PROCESSING_FAILED')
        with patch('backend.processing.verify_publication',side_effect=ValueError('SECRET')):failed=await self.start('verify-fail')
        self.assertEqual((await self.poll(failed))['error'],'PROCESSING_FAILED')
        def wrong_participant(connection,run,output):
            events=json.loads(output[2]);events[0]['entity_ids']=[str(uuid4())]
            publish_outputs(connection,run,(output[0],output[1],json.dumps(events),output[3]))
        with patch('backend.processing.publish_outputs',side_effect=wrong_participant):bad=await self.start('wrong-participant')
        self.assertEqual((await self.poll(bad))['error'],'PROCESSING_FAILED')
        self.assertEqual(self.private(good),original)
        self.assertEqual(len(self.rows('processing_outputs')),1);self.assertEqual(len(self.rows('processing_provenance')),1)
        self.assertEqual((await self.poll(await self.start('retry')))['status'],'completed')

    async def test_auth_missing_source_and_revocation_are_safe_before_publication(self):
        for token,status in [('invalid',401),('Bearer p11-two',404)]:
            self.assertEqual((await self.client.post(self.url,headers={'Authorization':token,'Idempotency-Key':'foreign'})).status_code,status)
        self.assertEqual((await self.client.post(self.url,headers={'Idempotency-Key':'body'},json={})).status_code,400)
        self.assertEqual(self.rows('processing_runs'),[])
        with patch('backend.processing.process_run'):queued=await self.start('missing')
        with self.app.state.database.connect() as connection:
            source=connection.execute('SELECT storage_path FROM evidence WHERE id=?',(self.evidence['id'],)).fetchone()[0]
        Path(source).unlink();process_run(self.app,queued['id'])
        self.assertEqual((await self.poll(queued))['error'],'SOURCE_UNAVAILABLE')
        with self.app.state.database.connect() as connection:connection.execute('DELETE FROM case_members WHERE case_id=?',(self.case,))
        self.assertEqual((await self.client.get(self.url)).status_code,404)
        self.assertEqual(self.rows('processing_outputs'),[])

    async def test_restart_interrupted_replay_and_retry_preserve_old_completed_outputs(self):
        good=await self.start('good');old=self.private(good)
        with patch('backend.processing.process_run'):queued=await self.start('interrupted')
        initialize_processing(self.app.state.database)
        failed=await self.poll(queued);self.assertEqual(failed['error'],'PROCESSING_INTERRUPTED')
        self.assertEqual(await self.start('interrupted'),failed)
        self.assertEqual((await self.poll(await self.start('retry')))['status'],'completed')
        self.assertEqual(self.private(good),old)

    async def test_old_versions_guard_upgrade_preserves_all_four_real_adapters_and_no_identity_merging(self):
        saved=[]
        samples=[('network_log',(ROOT/'fixtures/synthetic-case/network.csv').read_bytes()),
                 ('gps',(ROOT/'fixtures/synthetic-case/gps.csv').read_bytes()),
                 ('message',(ROOT/'fixtures/synthetic-case/messages.csv').read_bytes()),
                 ('document',b'Synthetic note\nSecond line\n')]
        for kind,data in samples:
            evidence=await self.upload(data,kind);run=await self.start(kind,self.base(evidence))
            saved.append((run,evidence,self.private(run,evidence)))
        old_outputs=self.rows('processing_outputs');old_private=self.rows('processing_provenance')
        with self.app.state.database.connect() as connection:
            for name in ('processing_provenance_context','processing_completion_provenance'):
                sql=connection.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
                connection.execute('DROP TRIGGER '+name)
                connection.execute(sql.replace(",'processing-lifecycle/5'",'').replace(",'processing-lifecycle/6'",''))
        initialize_processing(self.app.state.database)
        mobile=await self.start('after-upgrade');self.assertEqual((await self.poll(mobile))['status'],'completed')
        for run,evidence,private in saved:self.assertEqual(self.private(run,evidence),private)
        self.assertTrue(all(x in self.rows('processing_outputs') for x in old_outputs))
        self.assertTrue(all(x in self.rows('processing_provenance') for x in old_private))
        self.assertEqual(tuple([(await self.page(name))['total'] for name in ('observations','entities','events')]),(22,9,5))
        matching=[x for x in (await self.page('entities'))['items'] if x['candidate_key']=='device:D-8']
        self.assertEqual(len(matching),3);self.assertEqual(len({x['id'] for x in matching}),3)
        self.assertTrue(all(x['confidence']==0 for x in matching))

    async def test_mobile_version_requires_private_record_and_corrupt_parameters_fail_closed(self):
        with patch('backend.processing.process_run'):queued=await self.start('no-private')
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='running' WHERE id=?",(queued['id'],))
                connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                    (queued['id'],self.case,self.evidence['id'],'[]','[]','[]','[]'))
                connection.execute("UPDATE processing_runs SET status='completed',finished_at='2099-01-01T00:00:00Z' WHERE id=?",(queued['id'],))
        good=await self.start('good')
        with self.app.state.database.connect() as connection:
            payload=json.loads(connection.execute('SELECT payload_json FROM processing_provenance WHERE run_id=?',(good['id'],)).fetchone()[0])
            payload['execution']['parameters']['max_data_rows']=1
            connection.execute('DROP TRIGGER processing_provenance_no_update')
            connection.execute('UPDATE processing_provenance SET payload_json=? WHERE run_id=?',(json.dumps(payload),good['id']))
        with self.assertRaises(AccessError) as caught:self.private(good)
        self.assertEqual(caught.exception.status_code,404)

    async def test_untrusted_detail_and_labels_preserved_without_identity_truth_or_public_logging(self):
        source=MobileParserProjectionTests.csv(self,[['invalid time','D-007','<script>SECRET_P11</script>','raw detail']])
        evidence=await self.upload(source);log=io.StringIO();handler=logging.StreamHandler(log);logger=logging.getLogger()
        logger.addHandler(handler);level=logger.level;logger.setLevel(logging.INFO)
        try:
            run=await self.start('SENSITIVE_P11_KEY',self.base(evidence))
            audit=(await self.client.get(f'/api/v1/cases/{self.case}/audit-events')).json()
        finally:logger.setLevel(level);logger.removeHandler(handler);handler.close()
        self.assertNotIn('SECRET_P11',json.dumps([run,audit])+log.getvalue())
        self.assertNotIn('SENSITIVE_P11_KEY',log.getvalue())
        event=(await self.page('events'))['items'][0]
        self.assertEqual(event['summary'],'Source mobile log reports: <script>SECRET_P11</script>')
        self.assertEqual(event['observed_at_raw'],'invalid time');self.assertNotIn('observed_at_utc',event)
        self.assertEqual(event['confidence'],0)


class MobileLoopbackTests(unittest.TestCase):
    def test_real_http_mobile_upload_process_sources_participants_replay_and_failed_run(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            code=('from pathlib import Path;import sys,uvicorn;from backend.app import create_app;'
                  'from backend.auth import SyntheticTokenVerifier;p=Path(sys.argv[1]);'
                  'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                  'SyntheticTokenVerifier({"p11-http":"investigator-1"})),host="127.0.0.1",'
                  'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process=subprocess.Popen([sys.executable,'-c',code,directory,str(port)],cwd=ROOT,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer p11-http'},timeout=15) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code==200:break
                        except httpx.TransportError:pass
                        if process.poll() is not None:self.fail('Synthetic HTTP server stopped')
                        time.sleep(.1)
                    else:self.fail('Synthetic HTTP startup timed out')
                    case=client.post('/api/v1/cases',json={'title':'Synthetic HTTP P11'}).json()['id']
                    for index,data in enumerate((SOURCE,b'timestamp,device_id,event,detail\nt,D-7,e,\n')):
                        evidence=client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'mobile_log','source_label':'Synthetic'},
                            files={'file':('misleading.bin',data,'application/octet-stream')}).json()
                        url=f"/api/v1/cases/{case}/evidence/{evidence['id']}/processing-runs"
                        accepted=client.post(url,headers={'Idempotency-Key':str(index)});self.assertEqual(accepted.status_code,202)
                        for _ in range(100):
                            run=client.get(url+'/'+accepted.json()['id']).json()
                            if run['status'] in ('completed','failed'):break
                            time.sleep(.05)
                        self.assertEqual(run['status'],'completed' if index==0 else 'failed')
                        if index:self.assertEqual(run['error'],'CSV_INVALID_ROW')
                        self.assertEqual(client.post(url,headers={'Idempotency-Key':str(index)}).json(),run)
                        if not index:
                            self.assertEqual(client.get(f"/api/v1/cases/{case}/evidence/{evidence['id']}/content").content,SOURCE)
                    pages={name:client.get(f'/api/v1/cases/{case}/'+name).json() for name in ('observations','entities','events')}
                    self.assertEqual(tuple(pages[name]['total'] for name in ('observations','entities','events')),(6,2,2))
                    sources={x['id']:x for x in pages['observations']['items']};entities={x['id']:x for x in pages['entities']['items']}
                    for event in pages['events']['items']:
                        self.assertTrue(set(entities[event['entity_ids'][0]]['observation_ids'])&set(event['observation_ids']))
                        self.assertTrue(set(event['observation_ids'])<=sources.keys())
                    with closing(sqlite3.connect(Path(directory)/'db.sqlite3')) as connection:
                        self.assertEqual(connection.execute('SELECT count(*) FROM processing_outputs').fetchone()[0],1)
                        payload=json.loads(connection.execute('SELECT payload_json FROM processing_provenance').fetchone()[0])
                        self.assertEqual(payload['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())
                        self.assertEqual(payload['execution']['versions']['event_version'],'mobile-source-events/1')
            finally:
                process.terminate()
                try:process.communicate(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=10)
