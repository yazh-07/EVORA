"""Official-release protocol doubles, real downloads and installer preconditions."""
import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from backend.app import create_app
from backend import updates


class UpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.app=create_app(self.root/'case.sqlite')
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client=await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='http://localhost',headers={'X-Evora-Request':'1'}))
        account=await self.client.post('/api/v1/auth/setup',json={'username':'admin','display_name':'Update Tester','password':'disposable update test passphrase'})
        self.assertEqual(account.status_code,200,account.text)
        self.actor=account.json()['user']['id'] if 'user' in account.json() else account.json()['id']
        self.service=self.app.state.updates=updates.Updates(self.app,can_install=True,cache=self.root/'updates')
        self.payload=b'MZ'+b'synthetic installer protocol fixture'*2048
        self.digest=hashlib.sha256(self.payload).hexdigest()
        self.base=updates.REPOSITORY+'/releases/download/v9.0.0/'
        self.body={'tag_name':'v9.0.0','draft':False,'prerelease':False,'assets':[
            {'name':updates.INSTALLER,'size':len(self.payload),'browser_download_url':self.base+updates.INSTALLER},
            {'name':'SHA256SUMS','size':128,'browser_download_url':self.base+'SHA256SUMS'}]}
        self.calls=[];self.bad_checksum=False;self.evil_redirect=False
        def respond(request):
            self.calls.append(request)
            if str(request.url)==updates.LATEST:return httpx.Response(200,json=self.body)
            if str(request.url)==self.base+'SHA256SUMS':return httpx.Response(200,text=('0'*64 if self.bad_checksum else self.digest)+'  '+updates.INSTALLER+'\n')
            if str(request.url)==self.base+updates.INSTALLER:
                if self.evil_redirect:return httpx.Response(302,headers={'Location':'https://untrusted.example/installer.exe'})
                start=int(request.headers.get('Range','bytes=0-')[6:-1])
                return httpx.Response(206 if start else 200,content=self.payload[start:],
                    headers={'Content-Range':f'bytes {start}-{len(self.payload)-1}/{len(self.payload)}'} if start else {})
            raise AssertionError('Unexpected update URL')
        real=httpx.Client
        self.enterContext(patch.object(updates,'client',side_effect=lambda:real(transport=httpx.MockTransport(respond))))

    async def settled(self,status):
        for _ in range(500):
            data=(await self.client.get('/api/v1/updates')).json()
            if data['status']==status:return data
            if data['status']=='error':self.fail(data['error'])
            await asyncio.sleep(.01)
        self.fail('Update operation did not settle')

    async def checked(self):
        response=await self.client.post('/api/v1/updates/check',json={})
        self.assertEqual(response.status_code,200,response.text)
        return await self.settled('available')

    async def downloaded(self):
        await self.checked()
        response=await self.client.post('/api/v1/updates/download')
        self.assertEqual(response.status_code,200,response.text)
        return await self.settled('ready')

    async def test_checks_stable_version_and_never_sends_workstation_credentials(self):
        data=await self.checked()
        self.assertTrue(data['available']);self.assertEqual(data['latest_version'],'9.0.0')
        self.assertEqual(data['download_url'],self.base+updates.INSTALLER)
        self.assertTrue(all('Authorization' not in request.headers and 'Cookie' not in request.headers for request in self.calls))
        self.assertNotIn(str(self.root),str(data))

    async def test_automatic_checks_can_be_disabled_without_disabling_manual_checks(self):
        result=await self.client.put('/api/v1/settings',json={'automatic_update_checks':False})
        self.assertEqual(result.status_code,200,result.text)
        data=(await self.client.post('/api/v1/updates/check',json={'automatic':True})).json()
        self.assertEqual(data['status'],'idle');self.assertEqual(self.calls,[])
        await self.checked();self.assertTrue(self.calls)

    async def test_verified_download_and_resumed_partial_are_identical(self):
        await self.checked()
        target,partial=self.service._paths()
        partial.write_bytes(self.payload[:1234])
        await self.client.post('/api/v1/updates/download')
        data=await self.settled('ready')
        self.assertEqual(data['downloaded_bytes'],len(self.payload))
        self.assertEqual(target.read_bytes(),self.payload);self.assertFalse(partial.exists())
        self.assertIn('bytes=1234-',[request.headers.get('Range') for request in self.calls])

    async def test_bad_checksum_never_becomes_installable(self):
        await self.checked();self.bad_checksum=True
        await self.client.post('/api/v1/updates/download')
        for _ in range(500):
            data=(await self.client.get('/api/v1/updates')).json()
            if data['status']=='error':break
            await asyncio.sleep(.01)
        self.assertIn('verification failed',data['error'])
        with patch.object(updates.subprocess,'Popen') as execute:
            response=await self.client.post('/api/v1/updates/install')
        self.assertEqual(response.status_code,409);execute.assert_not_called()

    async def test_install_rehashes_the_file_and_blocks_active_work(self):
        await self.downloaded();target,_=self.service._paths()
        case=(await self.client.post('/api/v1/cases',json={'title':'Update precondition fixture'})).json()
        source=(await self.client.post(f"/api/v1/cases/{case['id']}/evidence",data={'kind':'document','source_label':'fixture'},files={'file':('note.txt',b'Synthetic update precondition fixture.','text/plain')})).json()
        run=str(uuid4())
        with self.app.state.database.connect() as connection:
            connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (run,case['id'],source['id'],self.actor,str(uuid4()),'fixture','{}','fixture','2026-01-01T00:00:00Z','queued'))
        with patch.object(updates.subprocess,'Popen') as execute:
            response=await self.client.post('/api/v1/updates/install')
            self.assertEqual(response.status_code,409);self.assertEqual(response.json()['code'],'PROCESSING_ACTIVE')
            execute.assert_not_called()
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='failed',finished_at='2026-01-01T00:00:01Z',error='PROCESSING_FAILED' WHERE id=?",(run,))
        target.write_bytes(b'tampered installer')
        with patch.object(updates.subprocess,'Popen') as execute:
            response=await self.client.post('/api/v1/updates/install')
            self.assertEqual(response.status_code,409);execute.assert_not_called()

    async def test_verified_installer_opens_with_fixed_arguments(self):
        await self.downloaded()
        process=SimpleNamespace(poll=lambda:None,returncode=None)
        with patch.object(updates.subprocess,'Popen',return_value=process) as execute:
            response=await self.client.post('/api/v1/updates/install')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'installing')
        arguments=execute.call_args.args[0]
        self.assertEqual(Path(arguments[0]).parent,self.service.cache)
        self.assertEqual(arguments[1:],['/NORESTART','/CLOSEAPPLICATIONS'])
        self.assertFalse(execute.call_args.kwargs.get('shell',False))

    async def test_update_actions_require_admin_and_same_origin(self):
        for endpoint in ('check','download','cancel','install'):
            response=await self.client.post('/api/v1/updates/'+endpoint,json={} if endpoint=='check' else None,headers={'X-Evora-Request':'0'})
            self.assertEqual(response.status_code,403,response.text)
        account=await self.client.post('/api/v1/accounts',json={'username':'viewer','display_name':'Viewer','password':'disposable viewer test passphrase','role':'investigator'})
        self.assertEqual(account.status_code,201,account.text)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE local_users SET must_change_password=0 WHERE username='viewer'")
        await self.client.post('/api/v1/auth/logout')
        self.assertEqual((await self.client.post('/api/v1/auth/login',json={'username':'viewer','password':'disposable viewer test passphrase'})).status_code,200)
        self.assertEqual((await self.client.get('/api/v1/updates')).status_code,200)
        for endpoint in ('check','download','cancel','install'):
            response=await self.client.post('/api/v1/updates/'+endpoint,json={} if endpoint=='check' else None)
            self.assertEqual(response.status_code,403,response.text)
        self.assertEqual(self.calls,[])

    async def test_untrusted_redirect_is_never_requested(self):
        await self.checked();self.evil_redirect=True
        await self.client.post('/api/v1/updates/download')
        for _ in range(500):
            data=(await self.client.get('/api/v1/updates')).json()
            if data['status']=='error':break
            await asyncio.sleep(.01)
        self.assertIn('not trusted',data['error'])
        self.assertTrue(all(request.url.host!='untrusted.example' for request in self.calls))


class ReleaseValidationTests(unittest.TestCase):
    def test_semantic_versions_do_not_downgrade_or_use_prereleases(self):
        self.assertGreater(updates.version('v1.10.0'),updates.version('1.9.9'))
        result=updates.parse_release({'tag_name':'v1.3.0','assets':[]},'1.3.8',updates.INSTALLER)
        self.assertFalse(result['newer'])
        for tag in ['v1.4.0-beta','../../installer','1.4','v01.4.0']:
            with self.subTest(tag=tag),self.assertRaises(updates.UpdateError):updates.version(tag)
        with self.assertRaises(updates.UpdateError):updates.parse_release({'tag_name':'v2.0.0','prerelease':True},'1.3.8',updates.INSTALLER)
