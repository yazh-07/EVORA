import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4
from backend import plates
from backend.parsers.media_detection import parse_image
from backend.results import operation_for

class PlateTests(unittest.TestCase):
    @unittest.skipUnless(plates.model_info(), 'Install the local plate models with scripts/setup-plates.sh')
    def test_real_plate_sample_and_negative_image(self):
        root=Path(__file__).resolve().parents[2]
        result=parse_image((root/'fixtures/media/plates/sample.png').read_bytes(),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())
        readings=[x.observation for x in result.observations if x.observation.kind=='image.plate_reading']
        self.assertEqual([x.normalized_value for x in readings],['5AU5341'])
        self.assertIn('box=',readings[0].source_locator);self.assertEqual(operation_for(readings[0].kind),'plates')
        blank=parse_image((root/'fixtures/media/astronaut.png').read_bytes(),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())
        self.assertFalse(any(x.observation.kind=='image.plate_reading' for x in blank.observations))
    def test_changed_artifact_is_not_silently_accepted(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['detector.onnx','recognizer.onnx','recognizer.yaml']:(root/name).write_bytes(b'original')
            (root/'manifest.json').write_text(json.dumps({'files':{name:hashlib.sha256(b'original').hexdigest() for name in ['detector.onnx','recognizer.onnx','recognizer.yaml']}}))
            (root/'detector.onnx').write_bytes(b'changed')
            with patch.dict(os.environ,{'EVORA_PLATE_MODEL_DIR':directory}),self.assertRaises(ValueError):plates.model_info()
    @classmethod
    def tearDownClass(cls):plates.close()
