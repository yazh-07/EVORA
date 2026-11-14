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

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
binary = Path(sys.argv[1]).resolve()
if sys.platform == 'win32':
    import pefile
    with pefile.PE(str(binary)) as image:
        resource_types = {entry.id for entry in image.DIRECTORY_ENTRY_RESOURCE.entries}
        assert {3, 14, 16}.issubset(resource_types), 'Windows EXE must contain icons and version metadata'
subprocess.run([str(binary), '--help'], check=True, timeout=60)
manifest = binary.parent / '_internal/backend/models/text_ner.json'
worker = subprocess.run([str(binary), '-m', 'backend.text_ner_worker', str(manifest)],
    input='{"lines": ["Alice Smith visited London."]}\n', text=True, capture_output=True, timeout=120)
assert worker.returncode == 0, worker.stderr[-2000:]
assert json.loads(worker.stdout)['ok'] is True, worker.stdout
subprocess.run([str(binary), '--check-oauth-tls'], check=True, timeout=60)
runtime = binary.parent / '_internal/graph-runtime'
if runtime.is_dir():
    assert not (runtime / 'java/bin/javac.exe').exists(), 'Compiler must stay build-only'
    assert not (runtime / 'java/jmods').exists(), 'Development modules must stay build-only'
    assert not (runtime / 'java/lib/src.zip').exists(), 'Duplicate Java source archive must not ship'
    assert not (runtime / 'neo4j/web').exists(), 'Unused Neo4j Browser must not ship'
    assert (runtime / 'java/legal').is_dir()
    assert (runtime / 'sources/java-source.tar.gz').is_file()
    assert (runtime / 'sources/neo4j-source.tar.gz').is_file()
with TemporaryDirectory(prefix='evora-release-smoke-') as directory:
    root = Path(directory)
    if runtime.is_dir():
        # Exercise the CLI parser edge case deterministically in the actual bundle.
        (root/'graph').mkdir(mode=0o700)
        (root/'graph/credentials.json').write_text(json.dumps({'password':
            '-synthetic-release-parser-fixture-012345678901234567890123456789'}),encoding='utf-8')
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
                    def post(path,payload=None,extra_headers=None,method='POST'):
                        request=Request(f'http://127.0.0.1:{port}/api/v1'+path,
                            data=json.dumps(payload).encode() if payload is not None else b'',method=method,
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
                    def completed(path):
                        for _ in range(240):
                            with browser.open(f'http://127.0.0.1:{port}/api/v1'+path,timeout=10) as response:state=json.load(response)
                            if state['status']=='completed':return state
                            assert state['status']!='failed',state.get('error')
                            time.sleep(.5)
                        raise AssertionError('Frozen processing timed out')
                    case=post('/cases',{'title':'Release processing checks'})
                    base='/cases/'+case['id']
                    def upload_source(kind,filename,media_type,data):
                        boundary='evora-smoke-'+uuid4().hex
                        parts=[]
                        for key,value in {'kind':kind,'source_label':'Synthetic '+kind}.items():
                            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
                        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {media_type}\r\n\r\n'.encode())
                        parts.extend([data,f'\r\n--{boundary}--\r\n'.encode()])
                        upload=Request(f'http://127.0.0.1:{port}/api/v1'+base+'/evidence',data=b''.join(parts),method='POST',headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-Evora-Request':'1'})
                        with browser.open(upload,timeout=20) as response:return json.load(response)
                    def process_source(source):
                        path=base+'/evidence/'+source['id']+'/processing-runs'
                        run=post(path,extra_headers={'Idempotency-Key':str(uuid4())})
                        completed(path+'/'+run['id'])
                    # Exercise the installed classifiers and decoder, not the
                    # build host's OpenCV. Empty detections are valid; failure is not.
                    frame=np.zeros((96,128,3),dtype=np.uint8)
                    frame[:,64:]=255
                    encoded,png=cv2.imencode('.png',frame)
                    assert encoded
                    process_source(upload_source('image','smoke.png','image/png',png.tobytes()))
                    video=root/'smoke.mp4'
                    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),4,(128,96))
                    try:
                        assert writer.isOpened(),'Smoke MP4 encoder unavailable on the build host'
                        for number in range(8):
                            frame[16:32,16:32]=(0,number*20,200)
                            writer.write(frame)
                    finally:writer.release()
                    process_source(upload_source('video','smoke.mp4','video/mp4',video.read_bytes()))
                    print('PASS frozen image and MP4 extraction: installed classifier files and video decoding')
                    if (binary.parent / '_internal/graph-runtime').is_dir():
                        source=upload_source('gps','gps.csv','text/csv',b'timestamp,device_id,latitude,longitude\n2026-01-01T00:00:00Z,D-1,12,77\n')
                        process_source(source)
                        run=post(base+'/analysis-runs',extra_headers={'Idempotency-Key':str(uuid4())})
                        completed(base+'/analysis-runs/'+run['id'])
                        with browser.open(f'http://127.0.0.1:{port}/api/v1'+base+'/graph?analysis_run_id='+run['id'],timeout=10) as response:
                            assert json.load(response)['nodes']
                        print('PASS frozen bundled graph: GPS processing, analysis publication and authenticated graph readback')
                    saved=post('/settings',{'offline_mode':False,'qa_provider':'chatgpt',
                        'qa_model':'release-vision','vision_use_qa_model':True,'automatic_update_checks':False},method='PUT')
                    assert not saved['offline_mode'] and not saved['automatic_update_checks']
                    break
                except OSError:
                    if child.poll() is not None or attempt == 359:
                        log.seek(0)
                        raise RuntimeError(log.read()[-4000:])
                    time.sleep(.5)
        except BaseException:
            log.flush()
            log.seek(0)
            print(log.read()[-8000:])
            graph_log=root/'graph/runtime.log'
            if graph_log.is_file():
                print(graph_log.read_text(encoding='utf-8',errors='replace')[-4000:])
            raise
        finally:
            (root / 'stop').touch()
            try:child.wait(timeout=75)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
                raise AssertionError('Frozen workstation did not shut down cleanly')
    # A second actual executable startup catches launcher overrides that API-only
    # tests cannot see. The first run already exercises the bundled graph.
    with (root/'restart.log').open('w+') as log:
        child=subprocess.Popen([str(binary),'--no-browser','--port',str(port),
            '--database',str(root/'case.sqlite3'),'--storage',str(root/'evidence'),
            '--graph-mode','external','--shutdown-file',str(root/'restart-stop')],stdout=log,stderr=log)
        try:
            for attempt in range(360):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/v1/auth/status',timeout=2) as response:
                        assert json.load(response)['database_locked'] is True
                    break
                except OSError:
                    if child.poll() is not None or attempt==359:
                        log.seek(0);raise RuntimeError(log.read()[-4000:])
                    time.sleep(.5)
            browser=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
            post('/auth/login',{'username':'release-smoke','password':'isolated release smoke passphrase'})
            with browser.open(f'http://127.0.0.1:{port}/api/v1/settings',timeout=10) as response:saved=json.load(response)
            assert saved['offline_mode'] is False and saved['qa_provider']=='chatgpt'
            assert saved['qa_model']=='release-vision' and saved['vision_use_qa_model'] is True
            assert saved['automatic_update_checks'] is False
            from backend.version import APP_VERSION
            with browser.open(f'http://127.0.0.1:{port}/api/v1/updates',timeout=10) as response:status=json.load(response)
            assert status['current_version']==APP_VERSION and status['automatic'] is False
            print('PASS frozen encrypted restart: saved online mode, models and update preferences')
        finally:
            (root/'restart-stop').touch()
            try:child.wait(timeout=75)
            except subprocess.TimeoutExpired:
                child.kill();child.wait(timeout=10)
                raise AssertionError('Restarted workstation did not shut down cleanly')
print('PASS frozen worker/model integrity, startup, local auth, frontend and repeated ChatGPT sign-in startup')
