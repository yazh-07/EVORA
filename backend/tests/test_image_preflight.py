"""Storage accepts originals; image-run acceptance validates actual bytes atomically."""
from io import BytesIO
import unittest
from unittest.mock import patch
from uuid import uuid4
from PIL import Image

from backend.tests import test_processing_dispatch as dispatch
from backend.tests.test_media_detection import FACE


class ImagePreflightTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=dispatch.DispatchTests.asyncSetUp
    asyncTearDown=dispatch.DispatchTests.asyncTearDown
    upload=dispatch.DispatchTests.upload
    base=dispatch.DispatchTests.base

    async def test_invalid_bytes_are_stored_but_both_image_actions_reject_before_acceptance(self):
        png=FACE.read_bytes()
        for media,data in [('application/octet-stream',b'unsupported synthetic bytes'),
                           ('image/png',b'not an image'),('image/png',png[:80]),
                           ('application/pdf',b'%PDF-1.7 unsupported image input')]:
            evidence=await self.upload('image',data,filename='source.bin',media=media)
            # The original remains retrievable, even though neither image processor accepts it.
            response=await self.client.get(f'/api/v1/cases/{self.case}/evidence/{evidence["id"]}/content')
            self.assertEqual(response.content,data)
            for route,body in [('processing-runs',None),('image-analysis',dict(expected_provider='ollama',expected_model='unused',expected_endpoint='http://127.0.0.1:11434'))]:
                response=await self.client.post(f'/api/v1/cases/{self.case}/evidence/{evidence["id"]}/{route}',
                    headers={'Idempotency-Key':str(uuid4())},**({'json':body} if body else {}))
                self.assertEqual(response.status_code,415,response.text)
                self.assertEqual(response.json()['code'],'UNSUPPORTED_MEDIA')
            self.assertEqual((await self.client.get(self.base(self.case,evidence['id']))).json(),[])
            with self.app.state.database.connect() as c:
                for table in ['processing_runs','processing_outputs','processing_provenance']:
                    self.assertEqual(c.execute(f'SELECT count(*) FROM {table} WHERE evidence_id=?',(evidence['id'],)).fetchone()[0],0)

    async def test_valid_image_works_even_with_generic_mime_and_filename(self):
        evidence=await self.upload('image',FACE.read_bytes(),filename='source.bin',media='application/octet-stream')
        key=str(uuid4());url=self.base(self.case,evidence['id'])
        response=await self.client.post(url,headers={'Idempotency-Key':key})
        self.assertEqual(response.status_code,202,response.text)
        run=response.json()
        terminal=(await self.client.get(url+'/'+run['id'])).json()
        self.assertEqual(terminal['status'],'completed',terminal)
        self.assertEqual((await self.client.post(url,headers={'Idempotency-Key':key})).json()['id'],run['id'])

    async def test_limits_and_animated_vision_are_rejected_without_a_run(self):
        evidence=await self.upload('image',FACE.read_bytes(),filename='photo.png',media='image/png')
        with patch('backend.processing.media_detection.MAX_PIXELS',100):
            response=await self.client.post(self.base(self.case,evidence['id']),headers={'Idempotency-Key':str(uuid4())})
        self.assertEqual(response.status_code,415)
        output=BytesIO();Image.new('RGB',(5,5),'red').save(output,format='GIF',save_all=True,append_images=[Image.new('RGB',(5,5),'blue')])
        evidence=await self.upload('image',output.getvalue(),filename='animated.gif',media='image/gif')
        response=await self.client.post(f'/api/v1/cases/{self.case}/evidence/{evidence["id"]}/image-analysis',headers={'Idempotency-Key':str(uuid4())},json=dict(expected_provider='ollama',expected_model='unused',expected_endpoint='http://127.0.0.1:11434'))
        self.assertEqual(response.status_code,415,response.text)
        self.assertEqual((await self.client.get(self.base(self.case,evidence['id']))).json(),[])
