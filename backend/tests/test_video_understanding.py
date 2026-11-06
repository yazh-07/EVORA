"""Real video decoding/publication and explicit protocol doubles; no accuracy claim."""
import hashlib
import json
import os
from unittest.mock import patch
import unittest
from uuid import uuid4

from backend.tests import test_image_understanding as image_tests
from backend.tests.test_media_detection import video_bytes
from backend import video_understanding as video


class VideoProcessingTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=image_tests.VisionProcessingTests.asyncSetUp
    asyncTearDown=image_tests.VisionProcessingTests.asyncTearDown
    upload=image_tests.VisionProcessingTests.upload
    base=image_tests.VisionProcessingTests.base
    read=image_tests.VisionProcessingTests.read
    rows=image_tests.VisionProcessingTests.rows
    validate=image_tests.VisionProcessingTests.validate
    settings=image_tests.VisionProcessingTests.settings
    transport=image_tests.VisionProcessingTests.transport

    async def invoke(self,evidence,body,key=None):
        return await self.client.post(f'/api/v1/cases/{self.case}/evidence/{evidence["id"]}/video-analysis',
            json=body,headers={'Idempotency-Key':key or str(uuid4())})

    async def test_video_scenes_text_tracks_provenance_and_snapshot(self):
        source=video_bytes();evidence=await self.upload('video',source,filename='clip.avi',media='video/x-msvideo')
        body={**self.settings(),'max_frames':2,'sample_interval_seconds':1}
        requests=[];key=str(uuid4())
        with self.transport(requests):
            response=await self.invoke(evidence,body,key)
            replay=await self.invoke(evidence,body,key)
        self.assertEqual(response.status_code,202,response.text)
        run=response.json();self.assertEqual(replay.json()['id'],run['id'])
        status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
        self.assertEqual(status['status'],'completed',status)
        records=(await self.client.get(f'/api/v1/cases/{self.case}/observations',params={'evidence_id':evidence['id'],'limit':100})).json()['items']
        scenes=[item for item in records if item['kind']=='video.scene']
        self.assertEqual(len(scenes),2)
        self.assertEqual(len({item['id'] for item in records}),len(records))
        metadata=json.loads(next(item['raw_value'] for item in records if item['kind']=='video.provenance'))
        self.assertEqual(metadata['original_sha256'],hashlib.sha256(source).hexdigest())
        self.assertEqual([frame['frame'] for frame in metadata['sampled_frames']],[0,10])
        self.assertTrue(any(item['kind']=='video.track' for item in records))
        self.assertEqual(len([req for req in requests if req.url.path=='/api/chat']),2)
        provenance=self.read(run,evidence)
        self.assertIn('video_understanding',provenance['execution'])
        for item in records:self.validate('Observation',item)
        from backend.analysis import freeze_analysis_input_snapshot
        snapshot=freeze_analysis_input_snapshot(self.app.state.database,self.case)
        self.assertTrue({item['id'] for item in scenes} <= set(snapshot['observation_ids']))

    async def test_explicit_hosted_consent_and_video_kind_required(self):
        evidence=await self.upload('video',video_bytes(),filename='clip.avi',media='video/x-msvideo')
        body=self.settings('openai')
        self.assertEqual((await self.invoke(evidence,{**body,'confirm_external_processing':False})).status_code,400)
        self.assertEqual((await self.invoke(self.evidence,body)).status_code,415)
        self.assertEqual((await self.invoke(evidence,{**body,'max_frames':61})).status_code,400)

    async def test_speech_requires_configured_local_engine(self):
        evidence=await self.upload('video',video_bytes(),filename='clip.avi',media='video/x-msvideo')
        with patch.dict(os.environ,{'EVORA_SPEECH_MODEL_PATH':''}):
            response=await self.invoke(evidence,{**self.settings(),'transcribe_speech':True})
        self.assertEqual(response.status_code,400,response.text)
        self.assertEqual(response.json()['code'],'SPEECH_NOT_CONFIGURED')

    async def test_failed_frame_never_publishes_partial_output(self):
        evidence=await self.upload('video',video_bytes(),filename='clip.avi',media='video/x-msvideo')
        with patch.object(video.vision,'extract',side_effect=ValueError('private failure')):
            response=await self.invoke(evidence,self.settings())
        run=response.json()
        status=(await self.client.get(self.base(self.case,evidence['id'])+'/'+run['id'])).json()
        self.assertEqual(status['error'],'VIDEO_UNDERSTANDING_FAILED')
        with self.app.state.database.connect() as c:
            self.assertIsNone(c.execute('SELECT 1 FROM processing_outputs WHERE run_id=?',(run['id'],)).fetchone())

    async def test_revoked_access_stops_later_frame_requests(self):
        evidence=await self.upload('video',video_bytes(),filename='clip.avi',media='video/x-msvideo')
        body={**self.settings(),'sample_interval_seconds':1,'max_frames':2}
        original=video.vision.extract
        def revoke(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.app.state.database.connect() as c:
                c.execute('DELETE FROM case_members WHERE case_id=?',(self.case,))
            return result
        requests=[]
        with self.transport(requests),patch.object(video.vision,'extract',side_effect=revoke):
            response=await self.invoke(evidence,body)
        self.assertEqual(len([item for item in requests if item.url.path=='/api/chat']),1)
        with self.app.state.database.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM processing_runs WHERE id=?',(response.json()['id'],)).fetchone()[0],'failed')
            self.assertIsNone(c.execute('SELECT 1 FROM processing_outputs WHERE run_id=?',(response.json()['id'],)).fetchone())

    async def test_no_audio_is_explicit_not_an_invented_transcript(self):
        evidence=await self.upload('video',video_bytes(),filename='clip.avi',media='video/x-msvideo')
        speech=dict(path='/unused',artifact_sha256='a'*64,engine='faster-whisper',runtime_version='1.2.1')
        with patch.object(video,'speech_config',return_value=speech),self.transport([]):
            response=await self.invoke(evidence,{**self.settings(),'max_frames':1,'transcribe_speech':True})
        run=response.json()
        records=(await self.client.get(f'/api/v1/cases/{self.case}/observations',params={'processing_run_id':run['id'],'limit':100})).json()['items']
        self.assertTrue(any(item['kind']=='transcript.status' and item['normalized_value']=='no_audio' for item in records))


class CandidateTrackingTests(unittest.TestCase):
    def test_tracks_keep_same_frame_candidates_separate_and_stop_at_gaps(self):
        context=dict(case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())
        def detection(frame,seconds,x,label='person:face'):
            return video.observation('video.frame_detection',label+' [box]',
                f'frame={frame}; time_offset={seconds:.6f}s; box={x},0,20,20',offset=seconds,**context)
        groups=video.tracks([detection(0,0,0),detection(0,0,100),detection(5,1,1),detection(5,1,101),
            detection(10,2,2,'person:upperbody'),detection(30,6,3)])
        self.assertEqual(len(groups),2)
        self.assertEqual([len(group) for group in groups],[2,2])
        self.assertEqual({group[0]['box'][0] for group in groups},{0,100})
