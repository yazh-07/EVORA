"""Disposable real application backend for Linux updater lifecycle tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import httpx
import uvicorn
from backend import updates,incremental as inc
from backend.app import create_app

p=argparse.ArgumentParser()
p.add_argument('--fixture',required=True);p.add_argument('--release-version',required=True)
p.add_argument('--database',required=True);p.add_argument('--storage',required=True);p.add_argument('--port',type=int,required=True)
p.add_argument('--shutdown-file',required=True);p.add_argument('--parent-pid',type=int,required=True)
p.add_argument('--graph-mode');p.add_argument('--graph-data');p.add_argument('--no-browser',action='store_true')
a=p.parse_args();fixture=Path(a.fixture)
root=Path(os.environ['EVORA_TEST_INSTALL_ROOT'])
updates.APP_VERSION=a.release_version
app=create_app(a.database,storage_dir=a.storage)
app.state.updates=updates.Updates(app,current=a.release_version,can_install=True,cache=fixture/'cache',installed_root=root,target_platform='linux-x64')
app.state.update_owner_pid=a.parent_pid;app.state.update_stop_marker=a.shutdown_file+'.update'
app.state.update_launch_args=json.loads(os.environ['EVORA_UPDATE_LAUNCH_ARGS'])
(fixture/'owner.pid').write_text(str(a.parent_pid))
manifest=(fixture/'next'/inc.LINUX_MANIFEST).read_bytes();bundle=(fixture/'next'/inc.LINUX_BUNDLE).read_bytes()
base=updates.REPOSITORY+'/releases/download/v9.0.0/'
release={'tag_name':'v9.0.0','assets':[dict(name=name,size=size,browser_download_url=base+name) for name,size in
 [(inc.LINUX_MANIFEST,len(manifest)),(inc.LINUX_BUNDLE,len(bundle)),('evora-linux-x86_64.tar.gz',10000000),('SHA256SUMS',100)]]}
def response(request):
 if str(request.url)==updates.LATEST:return httpx.Response(200,json=release)
 if str(request.url)==base+'SHA256SUMS':return httpx.Response(200,text=hashlib.sha256(manifest).hexdigest()+'  '+inc.LINUX_MANIFEST+'\n')
 if str(request.url)==base+inc.LINUX_MANIFEST:return httpx.Response(200,content=manifest)
 if str(request.url)==base+inc.LINUX_BUNDLE:
  start,end=map(int,request.headers['Range'][6:].split('-'))
  with (fixture/'requested-ranges').open('a') as log:log.write(request.headers['Range']+'\n')
  return httpx.Response(206,content=bundle[start:end+1],headers={'Content-Range':f'bytes {start}-{end}/{len(bundle)}'})
 raise AssertionError('Unexpected fixture request')
real=httpx.Client
updates.client=lambda:real(transport=httpx.MockTransport(response))
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=a.port,access_log=False))
def stopping():
 while not server.should_exit:
  if Path(a.shutdown_file).exists():server.should_exit=True;return
  time.sleep(.1)
threading.Thread(target=stopping,daemon=True).start()
server.run()
