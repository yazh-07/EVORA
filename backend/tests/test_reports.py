"""Report HTTP integration uses real CSV processing and frozen analysis outputs."""
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from backend import analysis, reports, qa_synthesis
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.tests.test_analysis import GraphDouble
from backend.tests.test_graph_nodes import validator


class ReportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.object(analysis, 'Neo4jGraphDatabase', return_value=GraphDouble()))
        self.app = create_app(root/'case.sqlite3', storage_dir=root/'vault',
            token_verifier=SyntheticTokenVerifier({'local': 'investigator-1', 'other': 'investigator-2'}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.app.state.qa_model = ''
        self.client = await self.enterAsyncContext(AsyncClient(transport=ASGITransport(self.app),
            base_url='http://test', headers={'Authorization': 'Bearer local'}))
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Report regression'})).json()['id']
        self.base = f'/api/v1/cases/{self.case}'
        evidence = await self.client.post(self.base+'/evidence', data={'kind':'network_log','source_label':'Gateway'},
            files={'file':('network.csv',b'timestamp,device_id,ip_address,event\n2026-01-12T10:00:00Z,D-7,192.0.2.7,connected\n','text/csv')})
        self.assertEqual(evidence.status_code,201,evidence.text)
        self.evidence = evidence.json()
        self.process_path = self.base+f"/evidence/{self.evidence['id']}/processing-runs"
        await self.client.post(self.process_path, headers={'Idempotency-Key':str(uuid4())})
        run = (await self.client.post(self.base+'/analysis-runs', headers={'Idempotency-Key':str(uuid4())})).json()
        run = (await self.client.get(self.base+'/analysis-runs/'+run['id'])).json()
        self.assertEqual(run['status'],'completed',run)
        self.body = dict(analysis_run_id=run['id'],finding_ids=[],scope='Summarize recorded connections',notes='')
        self.app.state.qa_model = 'report-test'
        self.observations = self.context()['observations']
        self.device = next(o for o in self.observations if o['normalized_value']=='D-7')
        self.sections = [dict(heading=h,claims=[]) for h in reports.HEADINGS]
        self.sections[0]['claims'] = [dict(text='The gateway record mentions D-7.',observation_ids=[self.device['id']])]

    def context(self):
        with self.app.state.database.connect() as connection:
            return reports.load_context(connection,self.case,reports.ReportRequest.model_validate_json(json.dumps(self.body)))[0]

    def inference(self, **overrides):
        result = copy.deepcopy(dict(sections=self.sections)); result.update(overrides)
        self.enterContext(patch.object(reports,'_chat',return_value=(result,'actual-report-model')))
        return self.enterContext(patch.object(qa_synthesis,'_chat',return_value=({'supported':True},'verifier')))

    async def test_frozen_sources_contract_and_private_provenance(self):
        self.inference()
        # A newer processing run must not replace the selected analysis's citations.
        await self.client.post(self.process_path,headers={'Idempotency-Key':str(uuid4())})
        response = await self.client.post(self.base+'/reports',json=self.body)
        self.assertEqual(response.status_code,200,response.text)
        body = response.json(); validator('GeneratedReport').validate(body)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(body['citations'][0]['observation_id'],self.device['id'])
        self.assertEqual(body['citations'][0]['source_locator'],self.device['source_locator'])
        self.assertEqual(body['coverage']['observations_total'],len(self.observations))
        with self.app.state.database.connect() as connection:
            record = connection.execute('SELECT * FROM qa_provenance WHERE id=?',(body['provenance_id'],)).fetchone()
            payload=json.loads(record['payload_json'])
            self.assertEqual(payload['context']['analysis_run_id'],self.body['analysis_run_id'])
            self.assertEqual(payload['verification']['status'],'verified')
            self.assertTrue(connection.execute("SELECT 1 FROM audit_events WHERE action='generateReport'").fetchone())

    async def test_remote_requires_online_mode_and_explicit_consent_before_inference(self):
        self.app.state.qa_provider='chatgpt'
        with patch.object(reports,'_chat') as model:
            for offline,consent in [(True,True),(False,False)]:
                self.app.state.offline_mode=offline
                response=await self.client.post(self.base+'/reports',json={**self.body,'allow_remote':consent})
                self.assertEqual(response.status_code,400)
                self.assertEqual(response.json()['code'],'REMOTE_CONSENT_REQUIRED')
            model.assert_not_called()
        self.app.state.offline_mode=False
        self.inference()
        with patch.object(reports,'_chat',return_value=({'sections':copy.deepcopy(self.sections)},'chat-test')) as write:
            response=await self.client.post(self.base+'/reports',json={**self.body,'allow_remote':True})
            self.assertEqual(response.status_code,200,response.text)
            self.assertIs(write.call_args.kwargs['chatgpt_connection'],self.app.state.chatgpt_connection)

    async def test_unknown_sources_wrong_identifiers_and_unsupported_claims_fail_closed(self):
        for mutation in ['unknown','device','unverified','invalid-section']:
            with self.subTest(mutation=mutation):
                result=copy.deepcopy(dict(sections=self.sections))
                if mutation=='unknown': result['sections'][0]['claims'][0]['observation_ids']=[str(uuid4())]
                if mutation=='device': result['sections'][0]['claims'][0]['text']='Device D-8 connected.'
                if mutation=='invalid-section': result['sections'][1]['heading']='Conclusive guilt'
                with patch.object(reports,'_chat',return_value=(result,'model')), patch.object(qa_synthesis,'_chat',return_value=({'supported':mutation!='unverified'},'model')):
                    response=await self.client.post(self.base+'/reports',json=self.body)
                self.assertEqual(response.status_code,400,response.text)
        with self.app.state.database.connect() as connection:
            self.assertFalse(connection.execute("SELECT 1 FROM audit_events WHERE action='generateReport'").fetchone())

    async def test_case_access_unknown_run_and_foreign_findings(self):
        with patch.object(reports,'_chat') as model:
            response=await self.client.post(self.base+'/reports',json=self.body,headers={'Authorization':'Bearer other'})
            self.assertEqual(response.status_code,404)
            for body in [{**self.body,'analysis_run_id':str(uuid4())},{**self.body,'finding_ids':[str(uuid4())]}]:
                response=await self.client.post(self.base+'/reports',json=body)
                self.assertIn(response.status_code,[400,404])
            model.assert_not_called()

    async def test_access_revocation_during_inference_does_not_publish(self):
        self.inference()
        original = reports.write_report
        def revoke(*args):
            result=original(*args)
            with self.app.state.database.connect() as connection:
                connection.execute('DELETE FROM case_members WHERE case_id=?',(self.case,))
            return result
        with patch.object(reports,'write_report',side_effect=revoke):
            response=await self.client.post(self.base+'/reports',json=self.body)
        self.assertEqual(response.status_code,404,response.text)

    async def test_context_limit_and_no_model_return_clear_failure(self):
        self.app.state.qa_model=''
        response=await self.client.post(self.base+'/reports',json=self.body)
        self.assertEqual(response.json()['code'],'MODEL_REQUIRED')
        self.app.state.qa_model='report-test'
        with patch.object(reports,'MAX_CONTEXT_CHARS',1), patch.object(reports,'_chat') as model:
            response=await self.client.post(self.base+'/reports',json=self.body)
            self.assertEqual(response.json()['code'],'REPORT_UNAVAILABLE');model.assert_not_called()

    async def test_model_derived_records_labelled_unverified(self):
        self.inference()
        context=self.context(); context['observations'][0].update(kind='image.ocr')
        oid=context['observations'][0]['id']
        sections=copy.deepcopy(self.sections)
        sections[0]['claims']=[dict(text='The source records a value.',observation_ids=[oid])]
        with patch.object(reports,'_chat',return_value=({'sections':sections},'model')):
            result=reports.write_report(context,'','', 'model',dict(qa_provider='ollama'))
        self.assertTrue(result[0][0]['claims'][0]['text'].startswith('Model-derived, unverified:'))
