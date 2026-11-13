"""Explicit one-time model installation. Never called by evidence processing."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil


def main():
    from fast_alpr import ALPR
    ALPR(detector_model='yolo-v9-t-640-license-plate-end2end',ocr_model='cct-s-v2-global-model',ocr_device='cpu',detector_providers=['CPUExecutionProvider'],ocr_providers=['CPUExecutionProvider'])
    cache=Path.home()/'.cache'
    sources={
        'detector.onnx':cache/'open-image-models/yolo-v9-t-640-license-plate-end2end/yolo-v9-t-640-license-plates-end2end.onnx',
        'recognizer.onnx':cache/'fast-plate-ocr/cct-s-v2-global-model/cct_s_v2_global.onnx',
        'recognizer.yaml':cache/'fast-plate-ocr/cct-s-v2-global-model/cct_s_v2_global_plate_config.yaml',
    }
    expected={
        'detector.onnx':'c3c1026ca7d0585dd88084d68182dd897113712fa734ae1557ca70174440c076',
        'recognizer.onnx':'384bbbd2cea3ef54761d3df70822ef3a349ee1a112aeafddbe0e3ba06bc6e47b',
    }
    root=Path(__file__).resolve().parents[1]/'storage/models/plates';root.mkdir(parents=True,exist_ok=True)
    files={}
    for name,path in sources.items():
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if name in expected and digest!=expected[name]:raise ValueError('Unexpected plate model artifact')
        shutil.copyfile(path,root/name);files[name]=digest
    manifest=dict(version='local-plate-model/1',detector='yolo-v9-t-640-license-plate-end2end',recognizer='cct-s-v2-global-model',files=files,
        packages={name:version(name) for name in ('fast-alpr','fast-plate-ocr','open-image-models','onnxruntime','numpy','opencv-python-headless')},
        detector_threshold=.4,method='local_onnx_cpu',score_kind='uncalibrated_model_scores')
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Local plate detector and OCR installed. Restart EVORA and reprocess the selected images/videos.')


if __name__=='__main__':main()
