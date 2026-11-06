"""Vision protocol doubles plus real image decoding, SQL publication, and source provenance."""
import base64
from io import BytesIO
import json
import hashlib
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image
from backend import image_understanding as vision
from backend.tests import test_processing_dispatch as dispatch


def picture():
    output=BytesIO();Image.new('RGB',(2600,400),'white').save(output,format='PNG');return output.getvalue()


class VisionProcessingTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=dispatch.DispatchTests.asyncSetUp
    asyncTearDown=dispatch.DispatchTests.asyncTearDown
    upload=dispatch.DispatchTests.upload
    base=dispatch.DispatchTests.base
    read=dispatch.DispatchTests.read
    validate=dispatch.DispatchTests.validate
    rows=dispatch.DispatchTests.rows

    def settings(self,provider='ollama'):
        self.app.state.vision_model='test-vision'
        self.app.state.qa_provider=provider
        self.app.state.qa_url='http://127.0.0.1:11434'
        self.app.state.openai_base_url='https://vision.test/v1'
        self.app.state.openai_api_key='synthetic-key'
        self.app.state.offline_mode=provider=='ollama'
        return dict(expected_provider=provider,expected_model='test-vision',expected_endpoint=self.app.state.qa_url if provider=='ollama' else self.app.state.openai_base_url,confirm_external_processing=provider=='openai')

    async def invoke(self,evidence,body,key=None):
        return await self.client.post(f'/api/v1/cases/{self.case}/evidence/{evidence["id"]}/image-analysis',json=body,headers={'Idempotency-Key':key or str(uuid4())})

    def transport(self,requests,provider='ollama',answer=None,finish='stop'):
        answer=answer or dict(description='A pale rectangular image.',visible_text='NOTICE\nRoom 12',limitations=['Synthetic protocol fixture; verify original.'])
        real=httpx.Client
        def respond(request):
            requests.append(request)
            if request.url.path=='/api/tags':
                return httpx.Response(200,json={'models':[{'name':'test-vision','capabilities':['vision'],'digest':'a'*64}]})
            if provider=='ollama':return httpx.Response(200,json={'done':True,'model':'test-vision','message':{'content':json.dumps(answer)}})
            return httpx.Response(200,json={'model':'actual-vision','choices':[{'finish_reason':finish,'message':{'content':json.dumps(answer)}}]})
        return patch.object(vision.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs))

    async def test_local_vision_publishes_caption_ocr_and_original_provenance(self):
        source=picture();evidence=await self.upload('image',source,filename='image.png',media='image/png');body=self.settings()
        requests=[]
        with self.transport(requests):response=await self.invoke(evidence,body)
        self.assertEqual(response.status_code,202,response.text)
        run=response.json()
        status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
        self.assertEqual(status['status'],'completed',status)
        observations=(await self.client.get(f'/api/v1/cases/{self.case}/observations',params={'evidence_id':evidence['id'],'processing_run_id':run['id'],'limit':100})).json()['items']
        by_kind={item['kind']:item for item in observations}
        self.assertEqual(by_kind['image.ocr']['raw_value'],'NOTICE\nRoom 12')
        metadata=json.loads(by_kind['image.provenance']['raw_value'])
        self.assertEqual(metadata['original_sha256'],hashlib.sha256(source).hexdigest())
        self.assertEqual(metadata['model_digest'],'a'*64)
        self.assertEqual(metadata['submitted_dimensions'][0],2048)
        payload=json.loads(next(request for request in requests if request.url.path=='/api/chat').content)
        decoded=base64.b64decode(payload['messages'][1]['images'][0])
        self.assertEqual(hashlib.sha256(decoded).hexdigest(),metadata['submitted_sha256'])
        self.assertNotIn('filename',payload['messages'][1])
        provenance=self.read(run,evidence)
        self.assertEqual(provenance['execution']['image_understanding']['prompt_sha256'],vision.PROMPT_HASH)
        for record in observations:self.validate('Observation',record)
        from backend.analysis import freeze_analysis_input_snapshot, _outputs
        snapshot=freeze_analysis_input_snapshot(self.app.state.database,self.case)
        self.assertIn(by_kind['image.description']['id'],snapshot['observation_ids'])
        with self.app.state.database.connect() as c:
            context={}
            fake_run=dict(id=str(uuid4()),case_id=self.case,input_snapshot_json=json.dumps(snapshot),created_at=status['created_at'])
            _outputs(c,fake_run,context)
            self.assertIn('image.description',{item['kind'] for item in context['observations']})

    async def test_hosted_request_is_explicit_and_uses_image_content_blocks(self):
        evidence=await self.upload('image',picture(),filename='image.png',media='image/png');body=self.settings('openai')
        requests=[]
        with self.transport(requests,'openai'):
            denied=await self.invoke(evidence,{**body,'confirm_external_processing':False})
            self.assertEqual(denied.status_code,400);self.assertEqual(requests,[])
            response=await self.invoke(evidence,body)
        run=response.json();status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
        self.assertEqual(status['status'],'completed',status)
        payload=json.loads(requests[0].content)
        self.assertEqual(requests[0].headers['authorization'],'Bearer synthetic-key')
        self.assertTrue(payload['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertEqual(self.read(run,evidence)['execution']['image_understanding']['provider'],'openai')
        with self.app.state.database.connect() as c:
            self.assertNotIn('synthetic-key',c.execute('SELECT config_json FROM processing_runs WHERE id=?',(run['id'],)).fetchone()[0])

    async def test_offline_mode_wrong_destination_and_nonimages_never_transmit(self):
        evidence=await self.upload('image',picture(),filename='image.png',media='image/png');body=self.settings('openai');requests=[]
        with self.transport(requests,'openai'):
            self.app.state.offline_mode=True
            self.assertEqual((await self.invoke(evidence,body)).status_code,400)
            self.app.state.offline_mode=False
            self.assertEqual((await self.invoke(evidence,{**body,'expected_endpoint':'https://other.test'})).status_code,409)
            self.assertEqual((await self.invoke(self.evidence,body)).status_code,415)
        self.assertEqual(requests,[])

    async def test_incomplete_or_malformed_output_fails_without_replacing_previous_results(self):
        evidence=await self.upload('image',picture(),filename='image.png',media='image/png');body=self.settings('openai')
        for answer,finish in [(dict(description='x',visible_text=42,limitations=[]),'stop'),(dict(description='x',visible_text='',limitations=[]),'length')]:
            requests=[]
            with self.transport(requests,'openai',answer,finish):response=await self.invoke(evidence,body)
            run=response.json();status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
            self.assertEqual(status['status'],'failed')
            self.assertEqual(status['error'],'IMAGE_UNDERSTANDING_FAILED')
            with self.app.state.database.connect() as c:
                self.assertIsNone(c.execute('SELECT 1 FROM processing_outputs WHERE run_id=?',(run['id'],)).fetchone())

    async def test_idempotent_replay_and_changed_consent_do_not_generate_twice(self):
        evidence=await self.upload('image',picture(),filename='image.png',media='image/png');body=self.settings();requests=[];key=str(uuid4())
        with self.transport(requests):
            one=await self.invoke(evidence,body,key);two=await self.invoke(evidence,body,key)
            conflict=await self.invoke(evidence,{**body,'confirm_external_processing':True},key)
        self.assertEqual(one.json()['id'],two.json()['id']);self.assertEqual(conflict.status_code,409)
        self.assertEqual(len([r for r in requests if r.url.path=='/api/chat']),1)

    async def test_ollama_remote_alias_never_receives_image_pixels(self):
        evidence=await self.upload('image',picture(),filename='image.png',media='image/png');body=self.settings()
        requests=[];real=httpx.Client
        def respond(request):
            requests.append(request)
            return httpx.Response(200,json={'models':[{'name':'test-vision','capabilities':['vision'],'digest':'a'*64,'remote_host':'https://cloud.example','remote_model':'vision'}]})
        with patch.object(vision.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)):
            response=await self.invoke(evidence,body)
        run=response.json();status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
        self.assertEqual(status['status'],'failed')
        self.assertTrue(all(request.method=='GET' for request in requests))


class ImagePreparationTests(unittest.TestCase):
    def test_invalid_animated_and_remote_local_endpoints_rejected(self):
        with self.assertRaises(Exception):vision.prepare_image(b'not an image')
        for endpoint,provider in [('http://example.com','openai'),('https://example.com','ollama')]:
            with self.assertRaises(Exception):vision.safe_endpoint(endpoint,provider)
        self.assertEqual(vision.safe_endpoint('https://provider.example/v1/','openai'),'https://provider.example/v1')

    def test_transparent_pixels_are_composited_and_normalization_is_recorded(self):
        source=BytesIO();Image.new('RGBA',(100,100),(255,0,0,0)).save(source,format='PNG')
        normalized,metadata=vision.prepare_image(source.getvalue())
        with Image.open(BytesIO(normalized)) as image:
            self.assertEqual(image.getpixel((0,0)),(255,255,255))
        self.assertEqual(metadata['alpha_background'],'white')
