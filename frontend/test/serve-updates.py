"""Disposable release service: no external requests or executable launches."""
import hashlib
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
            {'name':'SHA256SUMS','size':128,'browser_download_url':base+'SHA256SUMS'}]})
    if str(request.url)==base+'SHA256SUMS':return httpx.Response(200,text=hashlib.sha256(payload).hexdigest()+'  '+updates.INSTALLER+'\n')
    if str(request.url)==base+updates.INSTALLER:
        start=int(request.headers.get('Range','bytes=0-')[6:-1]);events['downloads'].append(start)
        return httpx.Response(206 if start else 200,stream=Chunks(payload[start:]),headers={'Content-Range':f'bytes {start}-{len(payload)-1}/{len(payload)}'} if start else {})
    raise AssertionError('Unexpected update request')

real_client=httpx.Client
updates.client=lambda:real_client(transport=httpx.MockTransport(respond))
app.state.updates=updates.Updates(app,can_install=True,cache=root/'updates')
def launch(*args,**kwargs):
    events['installs']+=1
    return SimpleNamespace(poll=lambda:None,returncode=None)
updates.subprocess.Popen=launch

@app.get('/test/update-events')
def recorded():return events

app.mount('/',StaticFiles(directory=Path(__file__).resolve().parents[1]/'dist',html=True))
uvicorn.run(app,host='127.0.0.1',port=port,access_log=False)
