import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import httpx
from backend.app import create_app
from backend.runtime_settings import load

class RuntimeSettingsTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.root=Path(self.enterContext(TemporaryDirectory()))
  self.app=create_app(self.root/'cases.sqlite3',network_available=True,listen_port=8123)
  await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
  self.client=await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='http://192.168.1.42:8123',headers={'X-Evora-Request':'1','Origin':'http://192.168.1.42:8123'}))
  r=await self.client.post('/api/v1/auth/setup',json={'username':'admin','display_name':'Test','password':'disposable runtime test passphrase'});self.assertEqual(r.status_code,200,r.text)
 async def test_defaults_actual_port_persistence_and_restart_notice(self):
  r=await self.client.get('/api/v1/settings/runtime');self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['running_port'],8123);self.assertEqual(r.json()['port'],8123);self.assertTrue(r.json()['minimize_to_tray'])
  r=await self.client.put('/api/v1/settings/runtime',json={'port':8333,'network_available':False,'minimize_to_tray':False})
  self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['restart_required']);self.assertTrue(r.json()['network_active'])
  self.assertEqual(load(self.root/'cases.sqlite3').port,8333)
  for port in (0,65536,-1,'8000'):
   bad=await self.client.put('/api/v1/settings/runtime',json={'port':port,'network_available':True,'minimize_to_tray':True});self.assertEqual(bad.status_code,400)
  self.assertEqual(load(self.root/'cases.sqlite3').port,8333)
 async def test_lan_access_keeps_host_origin_and_auth_checks(self):
  r=await self.client.get('/api/v1/settings/runtime',headers={'Host':'attacker.example'});self.assertEqual(r.status_code,400)
  r=await self.client.put('/api/v1/settings/runtime',json={'port':8333},headers={'Origin':'http://attacker.example'});self.assertEqual(r.status_code,403)
  await self.client.post('/api/v1/auth/logout')
  r=await self.client.get('/api/v1/settings/runtime');self.assertEqual(r.status_code,401)
 async def test_loopback_mode_rejects_lan_host(self):
  app=create_app(self.root/'other.sqlite3')
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://192.168.1.42') as client:
   self.assertEqual((await client.get('/api/v1/auth/status')).status_code,400)

class RuntimeBindingTests(unittest.TestCase):
 def test_real_binding_port_change_and_loopback_restart(self):
  import subprocess,sys,socket,time
  from backend.runtime_settings import RuntimePreferences,save
  root=Path(self.enterContext(TemporaryDirectory()));db=root/'cases.sqlite3'
  def free_port():
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
  port=free_port();save(db,RuntimePreferences(network_available=True,port=port))
  processes=[]
  def start():
   process=subprocess.Popen([sys.executable,'-m','backend.run','--database',str(db),'--storage',str(root/'evidence')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   processes.append(process);return process
  def stop_all():
   for process in processes:
    if process.poll() is None:process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait()
  self.addCleanup(stop_all)
  def ready(client):
   for _ in range(100):
    try:
     if client.get('/api/v1/auth/status').status_code==200:return
    except httpx.HTTPError:pass
    time.sleep(.1)
   self.fail('configured listener did not start')
  process=start()
  with httpx.Client(base_url=f'http://127.0.0.2:{port}',trust_env=False,timeout=2,headers={'X-Evora-Request':'1'}) as client:
   ready(client)
   r=client.post('/api/v1/auth/setup',json={'username':'runtime','display_name':'Runtime Test','password':'disposable listener test passphrase'});self.assertEqual(r.status_code,200,r.text)
   self.assertEqual(client.get('/api/v1/settings/runtime').json()['running_port'],port)
   self.assertEqual(client.get('/api/v1/auth/status',headers={'Host':'attacker.example'}).status_code,400)
   next_port=free_port()
   r=client.put('/api/v1/settings/runtime',json={'port':next_port,'network_available':False,'minimize_to_tray':True});self.assertEqual(r.status_code,200,r.text)
  process.terminate();process.wait(timeout=10);start()
  with httpx.Client(base_url=f'http://127.0.0.1:{next_port}',trust_env=False,timeout=2,headers={'X-Evora-Request':'1'}) as client:
   ready(client)
   r=client.post('/api/v1/auth/login',json={'username':'runtime','password':'disposable listener test passphrase'});self.assertEqual(r.status_code,200,r.text)
   status=client.get('/api/v1/settings/runtime').json();self.assertEqual(status['running_port'],next_port);self.assertFalse(status['network_active']);self.assertFalse(status['restart_required'])
  with httpx.Client(trust_env=False,timeout=1) as client,self.assertRaises(httpx.ConnectError):client.get(f'http://127.0.0.2:{next_port}/api/v1/auth/status')
