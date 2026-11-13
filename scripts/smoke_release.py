"""Verify a newly frozen executable using an isolated local workstation."""
import json
import http.cookiejar
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4
from urllib.request import urlopen,build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError

binary = Path(sys.argv[1]).resolve()
subprocess.run([str(binary), '--help'], check=True, timeout=60)
manifest = binary.parent / '_internal/backend/models/text_ner.json'
worker = subprocess.run([str(binary), '-m', 'backend.text_ner_worker', str(manifest)],
    input='{"lines": []}\n', text=True, capture_output=True, timeout=120)
assert worker.returncode == 0, worker.stderr[-2000:]
assert json.loads(worker.stdout)['ok'] is True, worker.stdout
with TemporaryDirectory(prefix='evora-release-smoke-') as directory:
    root = Path(directory)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with (root / 'server.log').open('w+') as log:
        child = subprocess.Popen([str(binary), '--no-browser', '--port', str(port),
            '--database', str(root / 'case.sqlite3'), '--storage', str(root / 'evidence'),
            '--graph-data', str(root / 'graph'), '--shutdown-file', str(root / 'stop')],
            stdout=log, stderr=log)
        try:
            for attempt in range(360):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/v1/auth/status', timeout=2) as response:
                        assert json.load(response) == {'setup_required': True, 'offline_mode': True, 'database_encrypted': False, 'database_locked': False}
                    with urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                        assert response.status == 200
                    browser=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    def post(path,payload=None,extra_headers=None):
                        request=Request(f'http://127.0.0.1:{port}/api/v1'+path,
                            data=json.dumps(payload).encode() if payload is not None else b'',method='POST',
                            headers={'Content-Type':'application/json','X-Evora-Request':'1',**(extra_headers or {})})
                        try:
                            with browser.open(request,timeout=10) as result:
                                assert 200 <= result.status < 300, (path, result.status)
                                return json.load(result)
                        except HTTPError as error:
                            raise AssertionError(f'{path}: HTTP {error.code}: {error.read().decode()}') from None
                    post('/auth/setup',{'username':'release-smoke','display_name':'Release Smoke',
                        'password':'isolated release smoke passphrase'})
                    # No provider requests: prove the frozen Windows store can be
                    # reread on retry, using only the real local OAuth starter.
                    for _ in range(2):
                        result=post('/chatgpt/connect',{'offline_mode':False})
                        assert result['authorization_url'].startswith('https://auth.openai.com/')
                    if (binary.parent / '_internal/graph-runtime').is_dir():
                        case=post('/cases',{'title':'Bundled graph smoke'})
                        boundary='evora-smoke-boundary'
                        fields={'kind':'gps','source_label':'Synthetic GPS'}
                        multipart=''.join(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n' for key,value in fields.items())
                        multipart+=f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="gps.csv"\r\nContent-Type: text/csv\r\n\r\ntimestamp,device_id,latitude,longitude\n2026-01-01T00:00:00Z,D-1,12,77\n\r\n--{boundary}--\r\n'
                        base='/cases/'+case['id']
                        upload=Request(f'http://127.0.0.1:{port}/api/v1'+base+'/evidence',data=multipart.encode(),method='POST',headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-Evora-Request':'1'})
                        with browser.open(upload,timeout=10) as response:source=json.load(response)
                        path=base+'/evidence/'+source['id']+'/processing-runs'
                        run=post(path,extra_headers={'Idempotency-Key':str(uuid4())})
                        def completed(path):
                            for _ in range(240):
                                with browser.open(f'http://127.0.0.1:{port}/api/v1'+path,timeout=10) as response:state=json.load(response)
                                if state['status']=='completed':return
                                assert state['status']!='failed',state.get('error')
                                time.sleep(.5)
                            raise AssertionError('Bundled graph smoke timed out')
                        completed(path+'/'+run['id'])
                        run=post(base+'/analysis-runs',extra_headers={'Idempotency-Key':str(uuid4())})
                        completed(base+'/analysis-runs/'+run['id'])
                        with browser.open(f'http://127.0.0.1:{port}/api/v1'+base+'/graph?analysis_run_id='+run['id'],timeout=10) as response:
                            assert json.load(response)['nodes']
                        print('PASS frozen bundled graph: GPS processing, analysis publication and authenticated graph readback')
                    break
                except OSError:
                    if child.poll() is not None or attempt == 359:
                        log.seek(0)
                        raise RuntimeError(log.read()[-4000:])
                    time.sleep(.5)
        finally:
            (root / 'stop').touch()
            try:child.wait(timeout=75)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
                raise AssertionError('Frozen workstation did not shut down cleanly')
print('PASS frozen worker/model integrity, startup, local auth, frontend and repeated ChatGPT sign-in startup')
