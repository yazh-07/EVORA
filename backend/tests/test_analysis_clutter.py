"""Regression oracles for source-safe graph/brief de-noising."""
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from backend.brief_context import select_observations
from backend.parsers.text_entities import merge_spans
from backend.graph_links import derive_candidate_links
from backend.analysis_presentation import consolidate_identifiers, GROUP_RULE
from backend.tests import test_documents as documents


class BriefSelectionTests(unittest.TestCase):
    def test_complete_source_lines_and_ocr_precede_visual_noise_and_duplicate_mentions(self):
        eid=str(uuid4()); other=str(uuid4())
        def observation(kind,text,source=eid,locator='line 1'):
            return dict(id=str(uuid4()),evidence_id=source,kind=kind,raw_value=text,normalized_value=text,source_locator=locator)
        noise=[observation('video.frame_detection','vehicle:license_plate '+str(i)) for i in range(150)]
        records=noise+[observation('text.line','2026-11-05T09:12:00Z: booking BK-771 cancelled.',locator='line 4'),
            observation('text.line','USD 125.50 refunded.',locator='line 5'),observation('image.ocr','09:12 UTC - BK-771 CANCELLED',other),
            observation('text.mention.date','2026-11-05')]
        selected=select_observations(records)
        self.assertEqual({r['kind'] for r in selected},{'text.line','image.ocr'})
        self.assertIn('09:12',json.dumps(selected))
        self.assertEqual(select_observations(list(reversed(records))),selected)
        self.assertEqual([r['source_locator'] for r in selected if r['kind']=='text.line'],['line 4','line 5'])

    def test_identifiers_override_partial_dates_and_technical_or_filename_predictions_are_not_entities(self):
        text='2026-11-05 UTC IP see 08_dispatch_cancellation.txt D-101'
        spans=[]
        for raw,kind in [('2026-11','date'),('UTC','organization'),('IP','organization'),('08_dispatch_cancellation.txt','location')]:
            start=text.index(raw);spans.append(dict(start=start,end=start+len(raw),kind=kind))
        result=merge_spans(text,spans)
        self.assertEqual([(r['kind'],text[r['start']:r['end']]) for r in result],[('date','2026-11-05'),('device','D-101')])

    def test_explicit_person_roles_override_model_category_without_demo_name_rules(self):
        from backend.text_ner import _WORKER
        lines=['D-101: training handset allocated to Jordan Ellis.',
               'Casey Morrow uses device D-202.',
               'UTC IP 08_dispatch_cancellation.txt 2026-11-05',
               'D-303: device allocated to Microsoft Corporation.']
        mentions=_WORKER.request(lines)
        actual={(m['kind'],lines[m['line']][m['start']:m['end']]) for m in mentions}
        self.assertIn(('person','Jordan Ellis'),actual)
        self.assertIn(('person','Casey Morrow'),actual)
        self.assertNotIn(('person','Microsoft Corporation'),actual)
        self.assertFalse(any(value in {'UTC','IP','08_dispatch_cancellation.txt','2026-11'} for _,value in actual))

    def test_grouped_finding_retains_complete_pairwise_edge_and_observation_lineage(self):
        case,run=str(uuid4()),str(uuid4());entities=[];observations=[]
        for _ in range(4):
            eid,oid=str(uuid4()),str(uuid4())
            observations.append(dict(id=oid,case_id=case,evidence_id=eid,processing_run_id=str(uuid4()),kind='network.device',source_locator='row 2, device_id',raw_value='D-101',normalized_value='D-101',entity_key='device:D-101',extraction_confidence=0))
            entities.append(dict(id=str(uuid4()),case_id=case,kind='device',canonical_label='D-101',candidate_key='device:D-101',evidence_ids=[eid],observation_ids=[oid],confidence=0))
        edges,findings=derive_candidate_links(case,run,entities,observations)
        self.assertEqual(len(edges),6)
        grouped=consolidate_identifiers(case,run,findings,entities)
        self.assertEqual(len(grouped),1);self.assertEqual(grouped[0].rule,GROUP_RULE)
        self.assertEqual(set(grouped[0].observation_ids),{o['id'] for o in observations})
        self.assertEqual(set(grouped[0].evidence_ids),{o['evidence_id'] for o in observations})
        self.assertEqual(set(grouped[0].entity_ids),{o['id'] for o in entities})
        self.assertEqual(grouped,consolidate_identifiers(case,run,list(reversed(findings)),list(reversed(entities))))


class StructuredInterpretationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=documents.DocumentProcessingTests.asyncSetUp
    asyncTearDown=documents.DocumentProcessingTests.asyncTearDown
    upload=documents.DocumentProcessingTests.upload
    base=documents.DocumentProcessingTests.base
    poll=documents.DocumentProcessingTests.poll
    rows=documents.DocumentProcessingTests.rows
    private=documents.DocumentProcessingTests.private

    async def test_mobile_csv_interpretation_preserves_original_kind_bytes_and_old_outputs(self):
        data=b'timestamp,device_id,event,detail\n2026-11-05T09:13:00Z,D-101,notification,Cancellation delivered; reading unverified.\n'
        evidence=await self.upload(data)
        old=(await self.client.post(self.base(evidence),headers={'Idempotency-Key':'old-document'})).json()
        self.assertEqual((await self.poll(old,self.base(evidence)))['status'],'completed')
        previous=self.rows('processing_outputs')
        url=self.base(evidence)+'/interpret-as'
        response=await self.client.post(url,headers={'Idempotency-Key':'mobile-correction'},json={'kind':'mobile_log'})
        self.assertEqual(response.status_code,202,response.text)
        run=response.json();self.assertEqual((run['source_kind'],run['processing_kind']),('document','mobile_log'));self.assertEqual((await self.poll(run,self.base(evidence)))['status'],'completed')
        replay=(await self.client.post(url,headers={'Idempotency-Key':'mobile-correction'},json={'kind':'mobile_log'})).json()
        self.assertEqual(replay['id'],run['id']); self.assertEqual(replay['status'],'completed')
        conflict=await self.client.post(url,headers={'Idempotency-Key':'mobile-correction'},json={'kind':'gps'})
        self.assertEqual(conflict.status_code,409)
        with self.app.state.database.connect() as c:
            source=c.execute('select * from evidence where id=?',(evidence['id'],)).fetchone()
            self.assertEqual(source['kind'],'document')
            config=json.loads(c.execute('select config_json from processing_runs where id=?',(run['id'],)).fetchone()[0])
            self.assertEqual((config['source_kind'],config['kind']),('document','mobile_log'))
            output=json.loads(c.execute('select observations_json from processing_outputs where run_id=?',(run['id'],)).fetchone()[0])
            self.assertIn('mobile.device',{o['kind'] for o in output})
        current={r['run_id']:r for r in self.rows('processing_outputs')}
        for item in previous:self.assertEqual(current[item['run_id']],item)
        content=await self.client.get(f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/content")
        self.assertEqual(content.content,data)
        self.assertEqual(self.private(run,evidence)['execution']['versions']['parser_version'],'mobile-csv/1')

    async def test_interpretation_rejects_unsupported_kind_and_does_not_change_the_original(self):
        before=self.rows('processing_runs')
        for body in ({'kind':'audio'},{'kind':'mobile_log','unexpected':True},[]):
            response=await self.client.post(self.url+'/interpret-as',headers={'Idempotency-Key':str(uuid4())},json=body)
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.rows('processing_runs'),before)
