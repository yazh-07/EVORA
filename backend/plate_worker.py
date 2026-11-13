"""Isolated local ONNX plate detector/reader. Explicit model paths; no downloads."""
import contextlib
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import statistics
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    manifest = json.loads((root/'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        if name not in {'detector.onnx','recognizer.onnx','recognizer.yaml'} or hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Plate artifact changed')
    if any(version(name) != expected for name, expected in manifest['packages'].items()):
        raise ValueError('Plate runtime changed')
    with contextlib.redirect_stdout(sys.stderr):
        import cv2
        import onnxruntime as ort
        from fast_alpr import ALPR
        from fast_alpr.base import BaseDetector
        from fast_alpr.default_ocr import DefaultOCR
        from open_image_models.detection.core.yolo_v9.inference import YoloV9Detector
        options = ort.SessionOptions(); options.intra_op_num_threads=1; options.inter_op_num_threads=1
        class Detector(BaseDetector):
            def __init__(self):
                self.model=YoloV9Detector(root/'detector.onnx',class_labels=['license_plate'],conf_thresh=.4,providers=['CPUExecutionProvider'],sess_options=options)
            def predict(self, frame):return self.model.predict(frame)
        engine=ALPR(detector=Detector(),ocr=DefaultOCR(model_path=root/'recognizer.onnx',config_path=root/'recognizer.yaml',device='cpu',providers=['CPUExecutionProvider'],sess_options=options))
    for packet in sys.stdin:
        try:
            request=json.loads(packet);path=Path(request['path'])
            if path.stat().st_size>100*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=request['sha256']:raise ValueError()
            frame=cv2.imread(str(path));
            if frame is None or frame.shape[0]*frame.shape[1]>25000000:raise ValueError()
            with contextlib.redirect_stdout(sys.stderr):results=engine.predict(frame)
            items=[]
            for result in results[:100]:
                box=result.detection.bounding_box
                x,y=max(0,box.x1),max(0,box.y1);right,bottom=min(frame.shape[1],box.x2),min(frame.shape[0],box.y2)
                if right<=x or bottom<=y:continue
                ocr=result.ocr
                confidence=ocr.confidence if ocr else 0
                if isinstance(confidence,list):confidence=statistics.mean(confidence) if confidence else 0
                items.append(dict(box=[int(x),int(y),int(right-x),int(bottom-y)],detector_score=float(result.detection.confidence),text=ocr.text if ocr else '',ocr_score=float(confidence)))
            response=dict(ok=True,request_id=request['request_id'],items=items)
        except Exception:response=dict(ok=False,error='PLATE_EXTRACTION_FAILED')
        sys.stdout.write(json.dumps(response,allow_nan=False)+'\n');sys.stdout.flush()


if __name__=='__main__':main()
