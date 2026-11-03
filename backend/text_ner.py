"""P13 one private, persistent local CPU worker per application process, bounded IPC."""
import atexit
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
import threading
import time

from backend.parsers.text_entities import validate_lines

MANIFEST_PATH=Path(__file__).with_name('models')/'text_ner.json'
_MANIFEST=json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
LIMITS=_MANIFEST['limits'].copy()
MODEL=_MANIFEST['model']
PROCESSOR_VERSION='processing-lifecycle/7'
_LOCK=threading.Lock()


class TextNERError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__('Local text extraction failed: '+code+'.')


def model_info():return json.loads(json.dumps(MODEL))


class LocalWorker:
    def __init__(self,manifest_path=MANIFEST_PATH,timeout=120):
        self.manifest_path=Path(manifest_path);self.timeout=timeout;self.process=None

    def close(self):
        process,self.process=self.process,None
        if process is None:return
        if process.poll() is None:process.kill()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for stream in (process.stdin,process.stdout):
            if stream is not None:stream.close()

    def _start(self):
        if self.process is not None and self.process.poll() is not None:self.close()
        if self.process is None:
            env=os.environ.copy()
            env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
            self.process=subprocess.Popen([sys.executable,'-m','backend.text_ner_worker',str(self.manifest_path)],
                cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,env=env)

    def request(self,lines):
        deadline=time.monotonic()+self.timeout
        if not _LOCK.acquire(timeout=max(0,deadline-time.monotonic())):raise TextNERError('TIMEOUT')
        thread=None
        try:
            self._start();results=Queue(maxsize=1);process=self.process
            payload=json.dumps({'lines':lines},ensure_ascii=False,separators=(',',':')).encode()+b'\n'
            def exchange():
                try:
                    process.stdin.write(payload);process.stdin.flush()
                    response=process.stdout.readline(32*1024*1024+1)
                    results.put(response)
                except (OSError,ValueError):results.put(None)
            thread=threading.Thread(target=exchange,daemon=True);thread.start()
            try:response=results.get(timeout=max(0,deadline-time.monotonic()))
            except Empty:raise TextNERError('TIMEOUT') from None
            if not response or len(response)>32*1024*1024:raise TextNERError('WORKER_FAILED')
            try:data=json.loads(response)
            except (ValueError,UnicodeError):raise TextNERError('WORKER_FAILED') from None
            if not isinstance(data,dict) or data.get('ok') is not True:
                code=data.get('error') if isinstance(data,dict) else None
                if code not in {'MODEL_UNAVAILABLE','MODEL_INVALID','INPUT_LIMIT','MENTION_LIMIT'}:code='WORKER_FAILED'
                raise TextNERError(code)
            if set(data)!={'ok','model','mentions'} or data['model']!=model_info() or not isinstance(data['mentions'],list):
                raise TextNERError('WORKER_FAILED')
            return data['mentions']
        except (TextNERError,OSError):
            self.close()
            raise
        finally:
            if thread is not None:thread.join(timeout=5)
            _LOCK.release()


_WORKER=LocalWorker(timeout=LIMITS['ner_timeout_seconds'])
atexit.register(_WORKER.close)


def extract_mentions(source,rows,*,case_id):
    locations=validate_lines(rows,case_id=case_id)
    try:text=source.decode('utf-8-sig',errors='strict')
    except (AttributeError,UnicodeDecodeError):raise TextNERError('INPUT_LIMIT') from None
    if len(text)>LIMITS['max_source_chars'] or any(len(row.observation.raw_value)>LIMITS['max_line_chars'] for row in rows):
        raise TextNERError('INPUT_LIMIT')
    previous = 0
    for row, (start, end) in zip(rows, locations):
        if text[previous:start] not in ('', '\r', '\n', '\r\n') or text[start:end] != row.observation.raw_value:
            raise TextNERError('SOURCE_MISMATCH')
        previous = end
    if text[previous:] not in ('', '\r', '\n', '\r\n'):
        raise TextNERError('SOURCE_MISMATCH')
    mentions=_WORKER.request([row.observation.raw_value for row in rows])
    if len(mentions)>LIMITS['max_mentions']:raise TextNERError('MENTION_LIMIT')
    return mentions
