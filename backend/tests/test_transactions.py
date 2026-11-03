"""P12 synthetic transaction exports; exact strings and actual producer/API read-back."""
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
from backend.parsers.transactions_csv import (parse_transactions_csv, TransactionCSVError, MAX_SOURCE_BYTES,
    MAX_DATA_ROWS, MAX_AMOUNT_CHARS, normalize_amount, validate_currency)
from backend.parsers.transaction_events import project_transaction_records, TransactionProjectionError

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (b'timestamp,account_id,amount,currency\n'
    b'2026-01-12T15:30:00.123456789+05:30,AC-007,000123456789012345678901234567890.1200,USD\n'
    b'2026-01-12T10:00:00,AC-8,-001.2300,EUR\n')


class TransactionParserProjectionTests(unittest.TestCase):
    def setUp(self):
        self.context=dict(case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())

    def parse(self, source=SOURCE):return parse_transactions_csv(source,**self.context)

    def project(self, rows=None):
        return project_transaction_records(self.parse() if rows is None else rows,case_id=self.context['case_id'])

    def csv(self, rows):
        output=io.StringIO(newline='');writer=csv.writer(output)
        writer.writerow(['timestamp','account_id','amount','currency']);writer.writerows(rows)
        return output.getvalue().encode()

    def reject(self, source, code):
        with self.assertRaises(TransactionCSVError) as caught:self.parse(source)
        self.assertEqual(caught.exception.code,code);self.assertNotIn('SECRET',str(caught.exception))

    def test_fixture_exact_values_context_row_spans_and_immutability(self):
        rows=self.parse();self.assertEqual(len(rows),2)
        self.assertEqual((rows[0].account_id,rows[0].amount,rows[0].currency),
                         ('AC-007','000123456789012345678901234567890.1200','USD'))
        self.assertEqual([(x.start_line,x.end_line) for x in rows],[(2,2),(3,3)])
        for row in rows:self.assertEqual((row.case_id,row.evidence_id,row.processing_run_id),tuple(self.context.values()))
        with self.assertRaises(FrozenInstanceError):rows[0].amount='changed'

    def test_bom_quoted_account_unicode_whitespace_multiline_and_line_endings(self):
        account=' 😀 account, "literal"\r\nsecond '
        row=self.parse(b'\xef\xbb\xbf'+self.csv([[' time ',account,'-001.2300','ZZZ']]))[0]
        self.assertEqual((row.timestamp,row.account_id,row.amount,row.currency),(' time ',account,'-001.2300','ZZZ'))
        self.assertEqual((row.start_line,row.end_line),(2,3))
        for ending in (b'\n',b'\r',b'\r\n'):
            self.assertEqual(len(self.parse(b'timestamp,account_id,amount,currency'+ending+b't,AC-7,1,USD'+ending)),1)

    def test_header_only_duplicate_rows_and_all_required_cells(self):
        self.assertEqual(self.parse(b'timestamp,account_id,amount,currency\n'),())
        rows=self.parse(b'timestamp,account_id,amount,currency\nt,AC-7,1,USD\nt,AC-7,1,USD\n')
        self.assertEqual([x.start_line for x in rows],[2,3])
        for index in range(4):
            values=['t','AC-7','1','USD'];values[index]=' '
            self.reject(self.csv([values]),'INVALID_ROW')

    def test_bad_header_layout_encoding_quotes_nul_source_and_context(self):
        for data,code in [(b'','INVALID_HEADER'),(b'account_id,timestamp,amount,currency\n','INVALID_HEADER'),
            (b'\xef\xbb\xbf\xef\xbb\xbftimestamp,account_id,amount,currency\n','INVALID_HEADER'),
            (b'\xffSECRET','INVALID_UTF8'),(b'timestamp,account_id,amount,currency\nt,SECRET\x00,1,USD','MALFORMED_CSV'),
            (b'timestamp,account_id,amount,currency\nt,"SECRET','MALFORMED_CSV'),
            (b'timestamp,account_id,amount,currency\nt,AC-7,1','INVALID_ROW'),
            (b'timestamp,account_id,amount,currency\nt,AC-7,1,USD,extra','INVALID_ROW'),('SECRET','INVALID_SOURCE')]:
            self.reject(data,code)
        with self.assertRaises(TransactionCSVError):parse_transactions_csv(SOURCE,**dict(self.context,case_id='SECRET'))

    def test_exact_signed_zero_large_and_fractional_amounts_without_context_rounding(self):
        expected={'00012.3400':'12.34','-001.2300':'-1.23','0':'0','000':'0','-0.00':'0','0.0000100':'0.00001',
            '000123456789012345678901234567890.1200':'123456789012345678901234567890.12',
            '-0000.00000000000000000000000000000000000100':'-0.000000000000000000000000000000000001'}
        from decimal import localcontext
        with localcontext() as context:
            context.prec=2
            for raw,normal in expected.items():
                self.assertEqual(normalize_amount(raw),normal)
                result=self.project(self.parse(self.csv([['t','AC-7',raw,'USD']])))
                amount=next(x.observation for x in result.observations if x.observation.kind=='transaction.amount')
                self.assertEqual((amount.raw_value,amount.normalized_value),(raw,normal))
                self.assertEqual(result.events[0].event.summary,'Source transaction record reports: '+raw+' USD')

    def test_invalid_amount_literals_rejected_without_float_or_separator_fallback(self):
        for amount in ('NaN','Infinity','-Infinity','1e3','1E-9','+1','1,000','1 000',' 1','1 ','1.','.5','--1','１','1\n','-'):
            self.reject(self.csv([['t','AC-7',amount,'USD']]),'INVALID_AMOUNT')
        with self.assertRaises(TransactionCSVError):normalize_amount(1.2)

    def test_actual_128_character_amount_limit_both_sign_and_fraction_and_overflow(self):
        for raw in ('9'*128,'-'+'9'*127,'0.'+'1'*126):
            self.assertEqual(self.parse(self.csv([['t','AC-7',raw,'USD']]))[0].amount,raw)
            self.reject(self.csv([['t','AC-7',raw+'1','USD']]),'AMOUNT_LIMIT')

    def test_currency_label_shape_only_no_iso_minor_unit_or_conversion_claim(self):
        for currency in ('USD','EUR','ZZZ'):
            self.assertEqual(self.parse(self.csv([['t','AC-7','-1.123456789',currency]]))[0].currency,currency)
        for currency in ('usd','Usd','US','USDD','123','ＵＳＤ',' USD','USD ','U\nD'):
            self.reject(self.csv([['t','AC-7','1',currency]]),'INVALID_CURRENCY')
        with self.assertRaises(TransactionCSVError):validate_currency(None)

    def test_real_byte_limit_and_overflow(self):
        prefix=b'timestamp,account_id,amount,currency\nt,';suffix=b',1,USD'
        data=prefix+b'x'*(MAX_SOURCE_BYTES-len(prefix)-len(suffix))+suffix
        self.assertEqual(len(self.parse(data)[0].account_id),MAX_SOURCE_BYTES-len(prefix)-len(suffix))
        self.reject(data+b'x','BYTE_LIMIT')

    def test_real_row_limit_and_atomic_overflow(self):
        data=b'timestamp,account_id,amount,currency\n'+b't,AC-7,1,USD\n'*MAX_DATA_ROWS
        self.assertEqual(len(self.parse(data)),100000)
        self.reject(data+b't,AC-8,-1,EUR\n','ROW_LIMIT')

    def test_complete_source_participant_joins_and_unavailable_confidence(self):
        rows=self.parse();result=self.project(rows)
        self.assertEqual((len(result.observations),len(result.entities),len(result.events)),(6,2,2))
        sources={x.observation.id:x.observation for x in result.observations};entities={x.id:x for x in result.entities}
        for wrapper in result.events:
            event=wrapper.event;entity=entities[event.entity_ids[0]]
            self.assertEqual((event.kind,event.confidence),('transaction.record',0))
            self.assertEqual(event.evidence_ids,(self.context['evidence_id'],))
            self.assertEqual({sources[oid].kind for oid in event.observation_ids},
                {'transaction.account','transaction.amount','transaction.currency'})
            self.assertTrue(set(entity.observation_ids)&set(event.observation_ids))
            self.assertEqual((entity.kind,entity.candidate_key,entity.confidence),('account','account:'+entity.canonical_label,0))
            for oid in event.observation_ids:
                self.assertEqual((sources[oid].observed_at_raw,sources[oid].observed_at_utc),
                                 (event.observed_at_raw,event.observed_at_utc))
                self.assertEqual(sources[oid].extraction_confidence,0)
        with self.assertRaises(FrozenInstanceError):result.events[0].event.confidence=1
        wire=result.observations[0].observation.to_wire();wire['raw_value']='changed'
        self.assertNotEqual(result.observations[0].observation.raw_value,'changed')
        self.assertTrue(set(sources).isdisjoint(x.observation.id for x in self.project(rows).observations))

    def test_identical_account_grouping_preserves_case_zeros_whitespace_and_duplicates(self):
        result=self.project(self.parse(self.csv([['t',account,'1','USD'] for account in ('AC-7','AC-7','ac-7','AC-007',' AC-7 ')])))
        by_key={x.candidate_key:x for x in result.entities}
        self.assertEqual(set(by_key),{'account:AC-7','account:ac-7','account:AC-007','account: AC-7 '})
        self.assertEqual((len(result.observations),len(result.entities),len(result.events)),(15,4,5))
        self.assertEqual(len(by_key['account:AC-7'].observation_ids),2)
        self.assertEqual(sum(x.event.entity_ids==(by_key['account:AC-7'].id,) for x in result.events),2)

    def test_raw_precise_invalid_unknown_and_ambiguous_source_time_retained(self):
        for raw,utc in [('2026-01-12T15:30:00.123456789+05:30','2026-01-12T10:00:00.123456789Z'),
                       ('2026-01-12T10:00:00',None),('2026-01-12T10:00:00-00:00',None),
                       ('2026-01-12T10:00:00 IST',None),('SECRET invalid',None)]:
            result=self.project(self.parse(self.csv([[raw,'AC-7','1','USD']])))
            for wire in [x.observation.to_wire() for x in result.observations]+[result.events[0].event.to_wire()]:
                self.assertEqual(wire['observed_at_raw'],raw)
                if utc is None:self.assertNotIn('observed_at_utc',wire)
                else:self.assertEqual(wire['observed_at_utc'],utc)
        empty=self.project(());self.assertEqual((empty.observations,empty.entities,empty.events),((),(),()))

    def test_mixed_context_overlapping_rows_or_forged_invalid_values_rejected_atomically(self):
        row=self.parse()[0]
        for rows in [(replace(row,case_id=uuid4()),),(replace(row,processing_run_id='SECRET'),),(row,row),
            (replace(row,start_line=True),),(replace(row,end_line=1),),(replace(row,amount='NaN'),),
            (replace(row,currency='usd'),),(replace(row,account_id='SECRET\x00'),),
            (row,replace(row,start_line=3,end_line=3,evidence_id=uuid4())),
            (row,replace(row,start_line=3,end_line=3,processing_run_id=uuid4()))]:
            with self.assertRaises(TransactionProjectionError):self.project(rows)
        self.assertEqual(len(self.project((row,)).events),1)


class TransactionProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.app = create_app(self.root/'db.sqlite3', storage_dir=self.root/'private',
            token_verifier=SyntheticTokenVerifier({'p12-one':'investigator-1','p12-two':'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app); await self.life.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://test',
            headers={'Authorization':'Bearer p12-one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title':'Synthetic P12'})).json()['id']
        self.evidence = await self.upload()
        self.url = self.base(self.evidence)
        self.bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))

    async def asyncTearDown(self):
        await self.client.aclose(); await self.life.__aexit__(None,None,None); self.temp.cleanup()

    def base(self, evidence):
        return f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/processing-runs"

    async def upload(self, data=SOURCE, kind='transaction'):
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence',
            data={'kind':kind,'source_label':'Synthetic P12'}, files={'file':('misleading.bin',data,'application/octet-stream')})
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
        self.assertEqual((complete['status'],complete['processor_version']),('completed','processing-lifecycle/6'))
        self.validate('ProcessingRun',complete)
        pages={name:await self.page(name) for name in ('observations','entities','events')}
        for name,schema in [('observations','ObservationPage'),('entities','EntityPage'),('events','EventPage')]:self.validate(schema,pages[name])
        self.assertEqual(tuple(pages[name]['total'] for name in ('observations','entities','events')),(6,2,2))
        sources={x['id']:x for x in pages['observations']['items']};entities={x['id']:x for x in pages['entities']['items']}
        for event in pages['events']['items']:
            self.assertEqual((event['kind'],event['confidence']),('transaction.record',0))
            self.assertEqual(event['evidence_ids'],[self.evidence['id']])
            self.assertEqual(len(event['observation_ids']),3)
            entity=entities[event['entity_ids'][0]]
            self.assertTrue(set(entity['observation_ids'])&set(event['observation_ids']))
            account=next(sources[oid] for oid in event['observation_ids'] if sources[oid]['kind']=='transaction.account')
            self.assertEqual(account['entity_key'],entity['candidate_key'])
            self.assertEqual(entity['canonical_label'],account['raw_value'])
            for oid in event['observation_ids']:
                self.assertEqual(sources[oid]['processing_run_id'],run['id'])
                self.assertEqual(sources[oid]['observed_at_raw'],event['observed_at_raw'])
                self.assertEqual(sources[oid].get('observed_at_utc'),event.get('observed_at_utc'))
        private=self.private(run)
        self.assertEqual(private['execution']['parameters'],{'max_source_bytes':52428800,'max_data_rows':100000,'max_amount_chars':128})
        self.assertEqual(private['execution']['versions'],dict(parser_version='transactions-csv/1',normalizer_version='source-normalization/1',
            entity_version='transaction-identifiers/1',event_version='transaction-source-events/1',processor_version='processing-lifecycle/6'))
        self.assertIsNone(private['execution']['model'])
        for name,field in [('observations','observation_ids'),('entities','entity_ids'),('events','event_ids')]:
            self.assertEqual(set(private['outputs'][field]),{x['id'] for x in pages[name]['items']})
            seen=[]
            for offset in range(pages[name]['total']):seen.extend((await self.page(name,limit=1,offset=offset))['items'])
            self.assertEqual(seen,pages[name]['items'])
        self.assertEqual(private['input']['sha256'],hashlib.sha256(SOURCE).hexdigest())
        original=await self.client.get(f"/api/v1/cases/{self.case}/evidence/{self.evidence['id']}/content")
        self.assertEqual(original.content,SOURCE)

    async def test_header_empty_duplicate_rows_and_exact_account_grouping_through_actual_apis(self):
        for data,counts in [(b'timestamp,account_id,amount,currency\n',(0,0,0)),
            (b'timestamp,account_id,amount,currency\nt,AC-7,1,USD\nt,AC-7,1,USD\nt,ac-7,1,USD\nt,AC-007,1,USD\n',(12,3,4))]:
            evidence=await self.upload(data);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            self.assertEqual((await self.poll(run,url))['status'],'completed')
            private=self.private(run,evidence)
            self.assertEqual(tuple(len(private['outputs'][name]) for name in ('observation_ids','entity_ids','event_ids')),counts)
        entities=await self.page('entities')
        self.assertEqual({x['candidate_key'] for x in entities['items']},{'account:AC-7','account:ac-7','account:AC-007'})
        self.assertEqual(len(next(x for x in entities['items'] if x['candidate_key']=='account:AC-7')['observation_ids']),2)

    async def test_malformed_wrong_layout_encoding_late_row_and_actual_overflow_publish_nothing(self):
        for data,error in [(b'', 'CSV_INVALID_HEADER'),(b'\xffSECRET','CSV_INVALID_UTF8'),
            (b'timestamp,account_id,amount,currency\nt,AC-7,1,USD\nt,AC-8,1,\n','CSV_INVALID_ROW'),
            ((ROOT/'fixtures/synthetic-case/network.csv').read_bytes(),'CSV_INVALID_HEADER'),
            (b'timestamp,account_id,amount,currency\n'+b't,AC-7,1,USD\n'*100001,'CSV_ROW_LIMIT')]:
            evidence=await self.upload(data);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            failed=await self.poll(run,url);self.assertEqual((failed['status'],failed['error']),('failed',error))
            self.assertNotIn('SECRET',json.dumps(failed))
            with self.assertRaises(AccessError):self.private(run,evidence)
        self.assertEqual(self.rows('processing_outputs'),[]);self.assertEqual(self.rows('processing_provenance'),[])
        self.assertEqual((await self.page('observations'))['total'],0)
        self.assertEqual((await self.page('entities'))['total'],0);self.assertEqual((await self.page('events'))['total'],0)

    async def test_signed_zero_and_128_character_amounts_publish_without_rounding(self):
        values=[('00012.3400','12.34'),('-001.2300','-1.23'),('-0.00','0'),
                ('9'*128,'9'*128),('0.'+'1'*126,'0.'+'1'*126)]
        source=TransactionParserProjectionTests.csv(self,[['t','AC-7',raw,'ZZZ'] for raw,_ in values])
        evidence=await self.upload(source);url=self.base(evidence);run=await self.start('exact-amounts',url)
        self.assertEqual((await self.poll(run,url))['status'],'completed')
        observations=await self.page('observations',evidence_id=evidence['id'])
        amounts={x['raw_value']:x['normalized_value'] for x in observations['items'] if x['kind']=='transaction.amount'}
        self.assertEqual(amounts,dict(values))
        self.assertTrue(all(x['kind']=='account' and x['confidence']==0 for x in (await self.page('entities'))['items']))
        self.assertEqual(len(self.private(run,evidence)['outputs']['event_ids']),5)

    async def test_invalid_amount_currency_length_and_changed_frozen_amount_cap_fail_atomically(self):
        for amount,currency,error in [('NaN','USD','CSV_INVALID_AMOUNT'),('1','usd','CSV_INVALID_CURRENCY'),
                                       ('1'*129,'USD','CSV_AMOUNT_LIMIT'),('1e3','USD','CSV_INVALID_AMOUNT')]:
            source=TransactionParserProjectionTests.csv(self,[['t','AC-7','1','USD'],['t','AC-8',amount,currency]])
            evidence=await self.upload(source);url=self.base(evidence);run=await self.start(str(uuid4()),url)
            self.assertEqual((await self.poll(run,url))['error'],error)
        self.assertEqual(self.rows('processing_outputs'),[]);self.assertEqual(self.rows('processing_provenance'),[])
        good=await self.start('good');before=self.private(good)
        with patch('backend.processing.process_run'):queued=await self.start('changed-amount-cap')
        with patch('backend.processing.adapter_for',return_value=replace(adapter_for('transaction'),max_amount_chars=127)):
            process_run(self.app,queued['id'])
        self.assertEqual((await self.poll(queued))['error'],'PROCESSING_FAILED')
        self.assertEqual(self.private(good),before);self.assertEqual(len(self.rows('processing_outputs')),1)

    async def test_identical_account_keys_from_separate_evidence_keep_distinct_source_records(self):
        first=await self.start();other=await self.upload(SOURCE);second=await self.start('other-original',self.base(other))
        entities=(await self.page('entities'))['items']
        for key in ('account:AC-007','account:AC-8'):
            matches=[x for x in entities if x['candidate_key']==key]
            self.assertEqual(len(matches),2);self.assertEqual(len({x['id'] for x in matches}),2)
            self.assertEqual({x['evidence_ids'][0] for x in matches},{self.evidence['id'],other['id']})
            self.assertTrue(all(x['confidence']==0 for x in matches))
        self.assertEqual(tuple([(await self.page(name))['total'] for name in ('observations','entities','events')]),(12,4,4))
        self.assertTrue(set(self.private(first)['outputs']['entity_ids']).isdisjoint(self.private(second,other)['outputs']['entity_ids']))

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
        with patch('backend.processing.adapter_for',return_value=replace(adapter_for('transaction'),max_data_rows=99999)):
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
        for token,status in [('invalid',401),('Bearer p12-two',404)]:
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

    async def test_old_versions_guard_upgrade_preserves_all_five_real_adapters_and_no_identity_merging(self):
        saved=[]
        samples=[('network_log',(ROOT/'fixtures/synthetic-case/network.csv').read_bytes()),
                 ('gps',(ROOT/'fixtures/synthetic-case/gps.csv').read_bytes()),
                 ('message',(ROOT/'fixtures/synthetic-case/messages.csv').read_bytes()),
                 ('document',b'Synthetic note\nSecond line\n'),
                 ('mobile_log',b'timestamp,device_id,event,detail\nt,D-007,e,d\nt,D-8,e,d\n')]
        for kind,data in samples:
            evidence=await self.upload(data,kind);run=await self.start(kind,self.base(evidence))
            saved.append((run,evidence,self.private(run,evidence)))
        old_outputs=self.rows('processing_outputs');old_private=self.rows('processing_provenance')
        with self.app.state.database.connect() as connection:
            for name in ('processing_provenance_context','processing_completion_provenance'):
                sql=connection.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0]
                connection.execute('DROP TRIGGER '+name)
                connection.execute(sql.replace(",'processing-lifecycle/6'",'').replace(",'processing-lifecycle/7'",''))
        initialize_processing(self.app.state.database)
        transaction=await self.start('after-upgrade');self.assertEqual((await self.poll(transaction))['status'],'completed')
        for run,evidence,private in saved:self.assertEqual(self.private(run,evidence),private)
        self.assertTrue(all(x in self.rows('processing_outputs') for x in old_outputs))
        self.assertTrue(all(x in self.rows('processing_provenance') for x in old_private))
        self.assertEqual(tuple([(await self.page(name))['total'] for name in ('observations','entities','events')]),(28,11,7))
        matching=[x for x in (await self.page('entities'))['items'] if x['candidate_key']=='device:D-8']
        self.assertEqual(len(matching),3);self.assertEqual(len({x['id'] for x in matching}),3)
        self.assertTrue(all(x['confidence']==0 for x in matching))

    async def test_transactions_version_requires_private_record_and_corrupt_parameters_fail_closed(self):
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
        source=TransactionParserProjectionTests.csv(self,[['invalid time','<script>SECRET_P12</script>','-0.00','ZZZ']])
        evidence=await self.upload(source);log=io.StringIO();handler=logging.StreamHandler(log);logger=logging.getLogger()
        logger.addHandler(handler);level=logger.level;logger.setLevel(logging.INFO)
        try:
            run=await self.start('SENSITIVE_P12_KEY',self.base(evidence))
            audit=(await self.client.get(f'/api/v1/cases/{self.case}/audit-events')).json()
        finally:logger.setLevel(level);logger.removeHandler(handler);handler.close()
        self.assertNotIn('SECRET_P12',json.dumps([run,audit])+log.getvalue())
        self.assertNotIn('SENSITIVE_P12_KEY',log.getvalue())
        event=(await self.page('events'))['items'][0]
        self.assertEqual(event['summary'],'Source transaction record reports: -0.00 ZZZ')
        self.assertEqual(event['observed_at_raw'],'invalid time');self.assertNotIn('observed_at_utc',event)
        self.assertEqual(event['confidence'],0)


class TransactionLoopbackTests(unittest.TestCase):
    def test_real_http_transaction_upload_process_sources_participants_replay_and_failed_run(self):
        with TemporaryDirectory() as directory:
            with closing(socket.socket()) as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
            code=('from pathlib import Path;import sys,uvicorn;from backend.app import create_app;'
                  'from backend.auth import SyntheticTokenVerifier;p=Path(sys.argv[1]);'
                  'uvicorn.run(create_app(p/"db.sqlite3",storage_dir=p/"private",token_verifier='
                  'SyntheticTokenVerifier({"p12-http":"investigator-1"})),host="127.0.0.1",'
                  'port=int(sys.argv[2]),access_log=False,log_level="error")')
            process=subprocess.Popen([sys.executable,'-c',code,directory,str(port)],cwd=ROOT,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer p12-http'},timeout=15) as client:
                    for _ in range(100):
                        try:
                            if client.get('/api/v1/cases').status_code==200:break
                        except httpx.TransportError:pass
                        if process.poll() is not None:self.fail('Synthetic HTTP server stopped')
                        time.sleep(.1)
                    else:self.fail('Synthetic HTTP startup timed out')
                    case=client.post('/api/v1/cases',json={'title':'Synthetic HTTP P12'}).json()['id']
                    for index,data in enumerate((SOURCE,b'timestamp,account_id,amount,currency\nt,AC-7,1,\n')):
                        evidence=client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'transaction','source_label':'Synthetic'},
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
                        self.assertEqual(payload['execution']['versions']['event_version'],'transaction-source-events/1')
            finally:
                process.terminate()
                try:process.communicate(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=10)
