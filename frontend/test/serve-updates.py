"""Disposable release service: no external requests or executable launches."""
import hashlib
import os
import shutil
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import httpx
from fastapi.staticfiles import StaticFiles
import uvicorn
from backend.app import create_app
from backend import updates

root=Path(sys.argv[1]);port=int(sys.argv[2])
app=create_app(root/'case.sqlite',storage_dir=root/'evidence')
events={'checks':0,'downloads':[],'installs':0}
payload=b'MZ'+b'update-protocol-fixture'*65536
base=updates.REPOSITORY+'/releases/download/v9.0.0/'
from backend import incremental as inc
from backend.version import APP_VERSION
from scripts.build_incremental import build
incremental=os.environ.get('EVORA_TEST_INCREMENTAL')=='1'
installed=root/'installed'
if incremental:
    (installed/'backend').mkdir(parents=True,exist_ok=True)
    for name in ('EVORA.exe','evora-updater.exe','icon.ico','backend/evora.exe','backend/ui.js'):
        (installed/name).write_bytes(('fixture '+name).encode())
    build(installed/'backend',installed/'EVORA.exe',installed/'evora-updater.exe',installed/'icon.ico',root/'old',APP_VERSION)
    shutil.copyfile(root/'old'/inc.MANIFEST,installed/inc.INSTALLED)
    (installed/'backend/ui.js').write_bytes(b'new application interface')
    build(installed/'backend',installed/'EVORA.exe',installed/'evora-updater.exe',installed/'icon.ico',root/'new','9.0.0')
    (installed/'backend/ui.js').write_bytes(b'fixture backend/ui.js')
    manifest=(root/'new'/inc.MANIFEST).read_bytes();bundle=(root/'new'/inc.BUNDLE).read_bytes()


class Chunks(httpx.SyncByteStream):
    def __init__(self,data):self.data=data
    def __iter__(self):
        for start in range(0,len(self.data),32768):
            time.sleep(.06)
            yield self.data[start:start+32768]

def respond(request):
    if str(request.url)==updates.LATEST:
        events['checks']+=1
        return httpx.Response(200,json={'tag_name':'v9.0.0','assets':[
            {'name':updates.INSTALLER,'size':len(payload),'browser_download_url':base+updates.INSTALLER},
            {'name':'SHA256SUMS','size':256,'browser_download_url':base+'SHA256SUMS'},
            *([{'name':name,'size':len(data),'browser_download_url':base+name} for name,data in [(inc.MANIFEST,manifest),(inc.BUNDLE,bundle)]] if incremental else [])]})
    if str(request.url)==base+'SHA256SUMS':return httpx.Response(200,text=hashlib.sha256(payload).hexdigest()+'  '+updates.INSTALLER+'\n'+(hashlib.sha256(manifest).hexdigest()+'  '+inc.MANIFEST+'\n' if incremental else ''))
    if incremental and str(request.url)==base+inc.MANIFEST:return httpx.Response(200,content=manifest)
    if incremental and str(request.url)==base+inc.BUNDLE:
        start,end=map(int,request.headers['Range'][6:].split('-'));events['downloads'].append(start)
        return httpx.Response(206,stream=Chunks(bundle[start:end+1]),headers={'Content-Range':f'bytes {start}-{end}/{len(bundle)}'})
    if str(request.url)==base+updates.INSTALLER:
        start=int(request.headers.get('Range','bytes=0-')[6:-1]);events['downloads'].append(start)
        return httpx.Response(206 if start else 200,stream=Chunks(payload[start:]),headers={'Content-Range':f'bytes {start}-{len(payload)-1}/{len(payload)}'} if start else {})
    raise AssertionError('Unexpected update request')

real_client=httpx.Client
updates.client=lambda:real_client(transport=httpx.MockTransport(respond))
app.state.updates=updates.Updates(app,can_install=True,cache=root/'updates',installed_root=installed if incremental else None)
app.state.update_owner_pid=123
app.state.update_stop_marker=str(root/'stop-123.update')
def launch(*args,**kwargs):
    events['installs']+=1
    return SimpleNamespace(poll=lambda:None,returncode=None)
updates.subprocess.Popen=launch

@app.get('/test/update-events')
def recorded():return events

app.mount('/',StaticFiles(directory=Path(__file__).resolve().parents[1]/'dist',html=True))
uvicorn.run(app,host='127.0.0.1',port=port,access_log=False)
