"""Real decoding/classification plus explicit failure and publication controls."""
from io import BytesIO
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

import cv2
from PIL import Image

from backend.parsers import media_detection as media
from backend.tests import test_processing_dispatch as dispatch

FACE = Path(__file__).resolve().parents[2] / 'fixtures/media/astronaut.png'


def video_bytes():
    with TemporaryDirectory() as directory:
        path = str(Path(directory) / 'frames.avi')
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 5, (512, 512))
        if not writer.isOpened():
            raise AssertionError('Test video encoder unavailable')
        try:
            for _ in range(11):
                writer.write(cv2.imread(str(FACE)))
        finally:
            writer.release()
        return Path(path).read_bytes()


class MediaDetectionTests(unittest.TestCase):
    def context(self):
        return dict(case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())

    def test_real_face_classifier_has_source_box_weight_and_unidentified_candidate(self):
        result = media.parse_image(FACE.read_bytes(), **self.context())
        faces = [x.observation for x in result.observations if x.observation.raw_value.startswith('person:face')]
        self.assertTrue(faces)
        face = faces[0]
        self.assertIn('frame=0; time_offset=0.000000s; box=', face.source_locator)
        self.assertTrue(math.isfinite(face.detector_weight))
        self.assertAlmostEqual(face.extraction_confidence, 1 / (1 + math.exp(-face.detector_weight)))
        self.assertIsNone(face.observed_at_utc)
        self.assertEqual(result.entities[0].kind, 'visual_candidate')
        self.assertTrue(face.raw_value.startswith('person:face'))
        self.assertEqual(result.events[0].event.entity_ids, (result.entities[0].id,))

    def test_real_video_samples_one_frame_per_second_with_original_frame_numbers(self):
        result = media.parse_video(video_bytes(), **self.context())
        locators = [x.observation.source_locator for x in result.observations]
        self.assertEqual({x.split(';')[0] for x in locators}, {'frame=0', 'frame=5', 'frame=10'})
        self.assertEqual({x.split(';')[1].strip() for x in locators},
                         {'time_offset=0.000000s', 'time_offset=1.000000s', 'time_offset=2.000000s'})
        self.assertTrue(all(x.time.status == 'relative_media_time' for x in result.observations))
        self.assertEqual(len({e.candidate_key for e in result.entities}), len(result.entities))

    def test_empty_image_corruption_limits_and_plate_projection(self):
        buf = BytesIO(); Image.new('RGB', (100, 100)).save(buf, format='PNG')
        self.assertEqual(media.parse_image(buf.getvalue(), **self.context()).observations, ())
        for parser in (media.parse_image, media.parse_video):
            with self.assertRaises(media.MediaDetectionError):
                parser(b'not media', **self.context())
        with patch.object(media, 'MAX_PIXELS', 1), self.assertRaisesRegex(media.MediaDetectionError, 'PIXEL_LIMIT'):
            media.parse_image(buf.getvalue(), **self.context())
        # A plate-shaped Haar response is not evidence of a plate.
        with patch.object(media.plates, 'model_info', return_value=None), patch.object(media, 'detect_frame', return_value=iter([
                ('vehicle:license_plate', (5, 10, 70, 25), 2.0, 'test-classifier')])):
            result = media.parse_image(buf.getvalue(), **self.context())
        self.assertEqual(result.observations, ())
        # The dedicated detector retains its box, reading and source lineage.
        hit=dict(box=[5,10,70,25],detector_score=.95,text='TEST42',ocr_score=.9)
        with patch.object(media.plates, 'model_info', return_value={'test':'fixture'}), patch.object(media.plates, 'detect', return_value=[hit]):
            result=media.parse_image(buf.getvalue(), **self.context())
        self.assertEqual(result.entities[0].kind,'visual_candidate')
        self.assertEqual(result.observations[1].observation.normalized_value,'TEST42')
        self.assertEqual(result.events[0].event.kind,'visual.detected')
        for weak in [dict(hit,detector_score=.45),dict(hit,box=[5,10,8,8]),dict(hit,box=[5,10,10,50])]:
            with patch.object(media.plates,'model_info',return_value={'test':'fixture'}),patch.object(media.plates,'detect',return_value=[weak]):
                rejected=media.parse_image(buf.getvalue(),**self.context())
            self.assertFalse(rejected.observations)



class MediaPublicationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = dispatch.DispatchTests.asyncSetUp
    asyncTearDown = dispatch.DispatchTests.asyncTearDown
    base = dispatch.DispatchTests.base
    upload = dispatch.DispatchTests.upload
    start = dispatch.DispatchTests.start
    poll = dispatch.DispatchTests.poll
    rows = dispatch.DispatchTests.rows
    read = dispatch.DispatchTests.read
    validate = dispatch.DispatchTests.validate

    async def test_image_video_complete_with_valid_public_outputs_and_private_model_provenance(self):
        for kind, data in [('image', FACE.read_bytes()), ('video', video_bytes())]:
            evidence = await self.upload(kind, data)
            url = self.base(self.case, evidence['id'])
            response = await self.start(str(uuid4()), url)
            self.assertEqual(response.status_code, 202, response.text)
            run = response.json()
            completed = await self.poll(run, url)
            self.assertEqual(completed['status'], 'completed', completed)
            self.assertEqual(self.read(run, evidence)['execution']['method'], 'local_opencv_haar_with_onnx_plates' if media.plates.model_info() else 'local_opencv_haar')
            self.assertIn('cascades', self.read(run, evidence)['execution']['model'])
            for route, schema in [('observations', 'Observation'), ('entities', 'Entity'), ('events', 'Event')]:
                page = (await self.client.get(f'/api/v1/cases/{self.case}/{route}', params={'limit': 100})).json()
                self.assertGreater(page['total'], 0)
                for item in page['items']:
                    self.validate(schema, item)
            content = await self.client.get(f"/api/v1/cases/{self.case}/evidence/{evidence['id']}/content")
            self.assertEqual(content.content, data)

    async def test_media_graph_preserves_detection_lineage_without_provenance_edges(self):
        from backend.tests.test_graph_projection import SyntheticNeo4j
        self.app.state.graph_database = SyntheticNeo4j()
        self.app.state.graph_database.close = lambda: None
        evidence = await self.upload('image', FACE.read_bytes())
        await self.start(str(uuid4()), self.base(self.case, evidence['id']))
        response = await self.client.post(f'/api/v1/cases/{self.case}/analysis-runs',
                                          headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        with self.app.state.database.connect() as connection:
            run = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (response.json()['id'],)).fetchone()
            self.assertEqual(run['status'], 'completed', dict(run))
            graph = json.loads(connection.execute('SELECT graph_json FROM analysis_outputs WHERE run_id=?',
                                                 (run['id'],)).fetchone()[0])
        self.validate('Graph', graph)
        # This fixture has detections but no relationship between distinct subjects.
        # The consumer draws source rays from node.evidence_ids, not graph.edges.
        self.assertEqual(graph['edges'],[])
        base=f'/api/v1/cases/{self.case}'
        entities=(await self.client.get(base+'/entities',params={'limit':100})).json()['items']
        observations={item['id']:item for item in (await self.client.get(base+'/observations',params={'limit':100})).json()['items']}
        nodes={item['id']:item for item in graph['nodes']}
        self.assertTrue(entities)
        for entity in entities:
            node=nodes[entity['id']]
            self.assertEqual(node['evidence_ids'],[evidence['id']])
            self.assertEqual(node['properties']['observation_ids'],entity['observation_ids'])
            for oid in entity['observation_ids']:
                source=observations[oid]
                self.assertEqual(source['evidence_id'],evidence['id'])
                self.assertEqual(source['entity_key'],entity['candidate_key'])
                self.assertEqual(source['kind'],'image.detection')
                self.assertIn('frame=0;',source['source_locator'])
                self.assertIn('box=',source['source_locator'])
        self.assertIn('visual_candidate', {n['entity_type'] for n in graph['nodes']})
        self.assertNotIn('person', {n['entity_type'] for n in graph['nodes']})

    async def test_corrupt_image_rejects_before_run_and_video_decode_failure_is_atomic(self):
        for kind in ('image', 'video'):
            evidence = await self.upload(kind, b'not valid media')
            url = self.base(self.case, evidence['id'])
            response = await self.start(str(uuid4()), url)
            if kind=='image':
                self.assertEqual(response.status_code,415,response.text)
                self.assertEqual(response.json()['code'],'UNSUPPORTED_MEDIA')
                self.assertEqual((await self.client.get(url)).json(),[])
                continue
            self.assertEqual(response.status_code, 202)
            failed = await self.poll(response.json(), url)
            self.assertEqual(failed['status'], 'failed')
            self.assertTrue(failed['error'].startswith('MEDIA_'))
        self.assertEqual(self.rows('processing_outputs'), [])
