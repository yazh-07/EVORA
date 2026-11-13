"""Optional pinned plate worker; isolated from the workstation's text runtime."""
import atexit
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
from tempfile import TemporaryDirectory
import threading
import uuid

import cv2

_ROOT=Path(__file__).resolve().parents[1]
_LOCK=threading.Lock()
_PROCESS=None
_MODEL_KEY=None


def configuration():
    root=Path(os.environ.get('EVORA_PLATE_MODEL_DIR',str(_ROOT/'storage/models/plates')))
    manifest=root/'manifest.json'
    if not manifest.is_file():return None
    data=json.loads(manifest.read_text())
    for name,digest in data['files'].items():
        if name not in {'detector.onnx','recognizer.onnx','recognizer.yaml'} or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Plate model changed')
    if set(data['files'])!={'detector.onnx','recognizer.onnx','recognizer.yaml'}:raise ValueError('Incomplete plate model')
    return root,data


def model_info():
    value=configuration()
    return value[1] if value else None


def close():
    global _PROCESS,_MODEL_KEY
    process,_PROCESS=_PROCESS,None;_MODEL_KEY=None
    if process is not None:
        if process.poll() is None:process.kill()
        process.wait(timeout=5)
        for stream in (process.stdin,process.stdout):
            if stream is not None:stream.close()


def detect(frame):
    global _PROCESS,_MODEL_KEY
    with _LOCK:
        value=configuration()
        if value is None:return []
        root,manifest=value;key=json.dumps(manifest,sort_keys=True)
        if _PROCESS is None or _PROCESS.poll() is not None or key!=_MODEL_KEY:
            close()
            python=os.environ.get('EVORA_PLATE_PYTHON',str(_ROOT/'.plate-venv/bin/python'))
            env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
            _PROCESS=subprocess.Popen([python,'-m','backend.plate_worker',str(root)],cwd=_ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
            _MODEL_KEY=key
        try:
            with TemporaryDirectory(prefix='evora-plate-') as directory:
                path=Path(directory)/'frame.png'
                if not cv2.imwrite(str(path),frame):raise ValueError()
                request_id=uuid.uuid4().hex
                packet=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),request_id=request_id)
                process=_PROCESS;responses=Queue(maxsize=1)
                def exchange():
                    try:process.stdin.write(json.dumps(packet).encode()+b'\n');process.stdin.flush();responses.put(process.stdout.readline(1024*1024))
                    except (OSError,ValueError):responses.put(b'')
                thread=threading.Thread(target=exchange,daemon=True);thread.start()
                try:response=json.loads(responses.get(timeout=45))
                except (Empty,ValueError):raise ValueError('Plate worker unavailable') from None
                if response.get('ok') is not True or response.get('request_id')!=request_id or not isinstance(response.get('items'),list):raise ValueError()
                for item in response['items']:
                    if set(item)!={'box','detector_score','text','ocr_score'} or len(item['box'])!=4 or not isinstance(item['text'],str) or len(item['text'])>100:raise ValueError()
                    for score in ('detector_score','ocr_score'):
                        if not isinstance(item[score],(float,int)) or not math.isfinite(item[score]) or not 0<=item[score]<=1:raise ValueError()
                return response['items']
        except Exception:
            close();raise ValueError('Plate extraction failed') from None


atexit.register(close)
