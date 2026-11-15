"""Linux package installation, real supervised updates, and startup rollback."""
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest

import httpx
from backend import incremental as inc,updates
from backend.version import APP_VERSION
from scripts.build_linux_package import build

ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(sys.platform.startswith('linux'),'Linux lifecycle and executable modes')
class LinuxUpdates(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tools=TemporaryDirectory(prefix='evora-linux-tools-');cls.addClassCleanup(cls.tools.cleanup)
  cls.launcher=Path(cls.tools.name)/'evora';cls.helper=Path(cls.tools.name)/'evora-updater'
  for package,target in [('linux',cls.launcher),('updater',cls.helper)]:
   subprocess.run(['go','build','-C',str(ROOT/'desktop'),'-o',str(target),'./cmd/'+package],check=True,capture_output=True)

 def setUp(self):
  self.base=Path(self.enterContext(TemporaryDirectory(prefix='evora-linux-update-')))
  self.installed=self.base/'installed app';self.data=self.base/'case data';self.data.mkdir()
  self.fixture=self.base/'protocol';self.fixture.mkdir()
  self.port=self.free_port();self.url=f'http://127.0.0.1:{self.port}'
  self.credentials={'username':'linux-test','display_name':'Linux Test','password':'disposable linux update passphrase'}
  self.client=self.enterContext(httpx.Client(base_url=self.url,timeout=5,headers={'X-Evora-Request':'1'}))
  self.processes=[];self.addCleanup(self.stop_all)

 def free_port(self):
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

 def backend(self,path,version,fail=False):
  path.mkdir(parents=True)
  if fail:script='#!/bin/sh\nexit 7\n'
  else:
   script='#!/bin/sh\nexec '+shlex.join([sys.executable,str(ROOT/'backend/tests/linux_update_server.py'),'--fixture',str(self.fixture),'--release-version',version])+' "$@"\n'
  (path/'evora').write_text(script);(path/'evora').chmod(0o755)
  (path/'unchanged-library.so').write_bytes(b'unchanged synthetic dependency'*10000)
  (path/'unchanged-library.so').chmod(0o644)

 def package(self,backend,out,version):return build(backend,self.launcher,self.helper,out,version)

 def prepare(self,fail=False):
  old=self.base/'old-backend';new=self.base/'new-backend';self.backend(old,APP_VERSION);self.backend(new,'9.0.0',fail)
  package,_=self.package(old,self.base/'old',APP_VERSION);self.package(new,self.fixture/'next','9.0.0')
  env=dict(os.environ,EVORA_INSTALL_DIR=str(self.installed),EVORA_BIN_DIR=str(self.base/'bin'),
   EVORA_APPLICATIONS_DIR=str(self.base/'applications'),EVORA_ICON_DIR=str(self.base/'icons'))
  self.installed.mkdir();(self.installed/'evora_data').mkdir();(self.installed/'evora_data/keep.txt').write_text('legacy data')
  result=subprocess.run(['bash',str(package/'install.sh')],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual((self.installed/'evora_data/keep.txt').read_text(),'legacy data')
  self.assertTrue((self.base/'bin/evora').is_symlink())
  self.env=dict(os.environ,PYTHONPATH=str(ROOT),EVORA_TEST_INSTALL_ROOT=str(self.installed))
  args=[str(self.installed/'evora'),'--database',str(self.data/'cases.sqlite3'),'--storage',str(self.data/'vault'),
   '--port',str(self.port),'--no-browser','--graph-mode','external']
  log=self.enterContext((self.base/'supervisor.log').open('w'))
  process=subprocess.Popen(args,env=self.env,stdout=log,stderr=log,start_new_session=True)
  self.processes.append(process)
  self.wait(lambda:self.health()==APP_VERSION)
  response=self.client.post('/api/v1/auth/setup',json=self.credentials);self.assertEqual(response.status_code,200,response.text)
  case=self.client.post('/api/v1/cases',json={'title':'Preserved Linux case'});self.assertEqual(case.status_code,201,case.text)
  self.case_id=case.json()['id']
  self.evidence=b'Synthetic evidence retained across the Linux update.'
  upload=self.client.post(f'/api/v1/cases/{self.case_id}/evidence',data={'kind':'document','source_label':'fixture'},
   files={'file':('note.txt',self.evidence,'text/plain')})
  self.assertEqual(upload.status_code,201,upload.text);self.evidence_id=upload.json()['id']
  # A second process must not start another backend or replace the active one.
  duplicate=subprocess.run(args,env=self.env,capture_output=True,text=True,timeout=5)
  self.assertNotEqual(duplicate.returncode,0);self.assertIn('already running',duplicate.stderr)
  return env

 def health(self):
  try:
   response=self.client.get('/api/v1/updates/health');return response.json().get('version') if response.status_code==200 else None
  except (httpx.HTTPError,ValueError):return None

 def wait(self,predicate,timeout=35):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   if predicate():return
   time.sleep(.1)
  logs=''
  for path in [self.base/'supervisor.log',self.data/'evora.log']:
   if path.exists():logs+=path.read_text(errors='replace')[-3500:]
  self.fail('Linux update did not settle. '+logs)

 def start_update(self):
  self.assertEqual(self.client.post('/api/v1/updates/check',json={}).status_code,200)
  self.wait(lambda:self.client.get('/api/v1/updates').json()['status']=='available')
  status=self.client.get('/api/v1/updates').json()
  self.assertEqual(status['mode'],'incremental');self.assertTrue(status['can_install']);self.assertEqual(status['file_count'],1)
  self.assertTrue(status['download_url'].endswith(inc.LINUX_BUNDLE))
  self.assertEqual(self.client.post('/api/v1/updates/download').status_code,200)
  self.wait(lambda:self.client.get('/api/v1/updates').json()['status']=='ready')
  response=self.client.post('/api/v1/updates/install');self.assertEqual(response.status_code,200,response.text)
  return self.fixture/'cache/v9.0.0-incremental/result.json'

 def test_installed_linux_downloads_only_changed_file_and_restarts_preserving_data(self):
  self.prepare();result=self.start_update()
  self.wait(lambda:result.exists());self.assertTrue(json.loads(result.read_text())['success'])
  self.assertEqual(self.health(),'9.0.0')
  self.assertEqual(len((self.fixture/'requested-ranges').read_text().splitlines()),1)
  self.assertEqual((self.installed/'backend/evora').stat().st_mode & 0o777,0o755)
  self.assertEqual((self.installed/'backend/unchanged-library.so').stat().st_mode & 0o777,0o644)
  response=self.client.post('/api/v1/auth/login',json={'username':self.credentials['username'],'password':self.credentials['password']})
  self.assertEqual(response.status_code,200,response.text)
  response=self.client.get('/api/v1/cases/'+self.case_id);self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['title'],'Preserved Linux case')
  response=self.client.get(f'/api/v1/cases/{self.case_id}/evidence/{self.evidence_id}/content')
  self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.content,self.evidence)
  self.assertEqual((self.installed/'evora_data/keep.txt').read_text(),'legacy data')

 def test_failed_new_linux_backend_restores_old_files_and_restarts(self):
  self.prepare(fail=True);before=inc.digest(self.installed/'backend/evora');result=self.start_update()
  self.wait(lambda:result.exists());self.assertFalse(json.loads(result.read_text())['success'])
  self.wait(lambda:self.health()==APP_VERSION)
  self.assertEqual(inc.digest(self.installed/'backend/evora'),before)
  self.assertEqual((self.installed/'backend/evora').stat().st_mode & 0o777,0o755)
  self.assertFalse((self.installed/'.evora-update-journal').exists())

 def test_packaging_materializes_internal_library_links_and_rejects_external_links(self):
  backend=self.base/'backend';self.backend(backend,APP_VERSION)
  (backend/'alias.so').symlink_to('unchanged-library.so')
  package,manifest=self.package(backend,self.base/'good',APP_VERSION)
  self.assertFalse((package/'backend/alias.so').is_symlink())
  self.assertEqual(inc.digest(package/'backend/alias.so'),inc.digest(package/'backend/unchanged-library.so'))
  parsed=inc.parse_manifest((package/inc.INSTALLED).read_bytes(),APP_VERSION,'linux-x64')
  self.assertEqual(parsed['platform'],'linux-x64')
  invalid=json.loads((package/inc.INSTALLED).read_bytes())
  for mode in (0o644,0o4755):
   broken=json.loads(json.dumps(invalid))
   next(f for f in broken['files'] if f['path']=='evora-updater')['mode']=mode
   with self.assertRaises(inc.IncrementalError):inc.parse_manifest(json.dumps(broken).encode())
  with self.assertRaises(inc.IncrementalError):inc.parse_manifest((package/inc.INSTALLED).read_bytes(),APP_VERSION,'windows-x64')
  (backend/'external.so').symlink_to(self.data)
  with self.assertRaises(ValueError):self.package(backend,self.base/'bad',APP_VERSION)

 def test_unsupported_linux_updates_use_package_fallback(self):
  from types import SimpleNamespace
  from unittest.mock import patch
  service=updates.Updates(SimpleNamespace(state=SimpleNamespace(automatic_update_checks=True)),can_install=True,
   installed_root=self.installed,cache=self.fixture/'cache',target_platform='linux-x64')
  service.release={'newer':True,'asset':{'size':1000,'browser_download_url':updates.REPOSITORY+'/releases/download/v9.0.0/evora-linux-x86_64.tar.gz'}}
  service._fallback('Download the full Linux package to continue.')
  self.assertEqual(service.status()['mode'],'archive');self.assertFalse(service.status()['can_install'])
  from backend.errors import AccessError
  with self.assertRaises(AccessError):service.download()

 def test_installer_uninstaller_preserve_legacy_case_data(self):
  backend=self.base/'backend';self.backend(backend,APP_VERSION)
  package,_=self.package(backend,self.base/'package',APP_VERSION)
  env=dict(os.environ,EVORA_INSTALL_DIR=str(self.installed),EVORA_BIN_DIR=str(self.base/'bin'),
   EVORA_APPLICATIONS_DIR=str(self.base/'applications'),EVORA_ICON_DIR=str(self.base/'icons'))
  self.installed.mkdir();legacy=self.installed/'evora_data';legacy.mkdir();(legacy/'case.sqlite3').write_bytes(b'legacy database')
  result=subprocess.run(['bash',str(package/'install.sh')],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  (self.installed/'backend/private-case.bin').write_bytes(b'untracked evidence')
  result=subprocess.run(['bash',str(self.installed/'uninstall.sh')],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual((legacy/'case.sqlite3').read_bytes(),b'legacy database')
  self.assertEqual((self.installed/'backend/private-case.bin').read_bytes(),b'untracked evidence')
  self.assertFalse((self.installed/'backend/evora').exists())

 def stop_all(self):
  owner=self.fixture/'owner.pid'
  if owner.exists():
   try:os.kill(int(owner.read_text()),signal.SIGTERM)
   except ProcessLookupError:pass
  for process in self.processes:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=8)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
  end=time.monotonic()+8
  while self.health() is not None and time.monotonic()<end:time.sleep(.1)
