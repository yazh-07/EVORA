"""Real SQLite/cookie acceptance for local offline accounts; no live services."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

import httpx
from backend.app import create_app
from backend.local_auth import COOKIE, IDLE_SECONDS


class LocalAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = self.enterContext(TemporaryDirectory())
        self.app = create_app(Path(self.root)/'accounts.sqlite')
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(self.app), base_url='http://localhost', headers={'X-Evora-Request':'1'}))
        self.credentials = dict(username='admin',password='correct horse battery staple',display_name='Local Admin')

    async def setup_admin(self):
        response=await self.client.post('/api/v1/auth/setup',json=self.credentials)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def new_user(self,role='investigator',username='investigator'):
        response=await self.client.post('/api/v1/accounts',json=dict(username=username,password='temporary passphrase',display_name='Investigator',role=role))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['user']

    async def other(self,username='investigator'):
        client=await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='http://localhost',headers={'X-Evora-Request':'1'}))
        r=await client.post('/api/v1/auth/login',json=dict(username=username,password='temporary passphrase'))
        self.assertEqual(r.status_code,200,r.text)
        r=await client.post('/api/v1/auth/password',json=dict(current_password='temporary passphrase',new_password='new investigator passphrase'))
        self.assertEqual(r.status_code,200,r.text)
        return client

    async def test_setup_cookie_hashes_replay_and_login(self):
        self.assertTrue((await self.client.get('/api/v1/auth/status')).json()['setup_required'])
        result=await self.setup_admin()
        self.assertEqual((await self.client.post('/api/v1/auth/setup',json=self.credentials)).status_code,409)
        me=await self.client.get('/api/v1/auth/me')
        self.assertEqual(me.json()['user']['role'],'administrator')
        self.assertEqual(me.headers['cache-control'],'no-store')
        with self.app.state.database.connect() as c:
            user=c.execute('SELECT * FROM local_users').fetchone()
            session=c.execute('SELECT * FROM local_sessions').fetchone()
            self.assertTrue(user['password_hash'].startswith('$argon2id$'))
            self.assertNotEqual(user['recovery_hash'],result['recovery_code'])
            self.assertNotEqual(session['digest'],self.client.cookies[COOKIE])
        cookie=self.client.cookies[COOKIE]
        r=await self.client.post('/api/v1/auth/logout')
        self.assertEqual(r.status_code,200)
        self.assertEqual((await self.client.get('/api/v1/cases')).status_code,401)
        self.client.cookies.set(COOKIE,cookie)
        self.assertEqual((await self.client.get('/api/v1/auth/me')).status_code,401)
        self.client.cookies.clear()
        r=await self.client.post('/api/v1/auth/login',json={k:self.credentials[k] for k in ('username','password')})
        self.assertEqual(r.status_code,200)
        self.assertIn('httponly',r.headers['set-cookie'].lower())
        self.assertIn('samesite=strict',r.headers['set-cookie'].lower())
        self.assertNotEqual(self.client.cookies[COOKIE],cookie)

    async def test_csrf_host_and_local_mode_reject_bearer(self):
        await self.setup_admin()
        for headers in ({'X-Evora-Request':''},{'Origin':'http://evil.example'},{'Sec-Fetch-Site':'cross-site'}):
            r=await self.client.post('/api/v1/cases',json={'title':'Blocked'},headers=headers)
            self.assertEqual(r.status_code,403)
        self.assertEqual((await self.client.get('/api/v1/auth/status',headers={'Host':'evil.example'})).status_code,400)
        self.client.cookies.clear()
        self.assertEqual((await self.client.get('/api/v1/cases',headers={'Authorization':'Bearer anything'})).status_code,401)

    async def test_membership_roles_and_temporary_password(self):
        await self.setup_admin()
        user=await self.new_user()
        reviewer=await self.new_user('reviewer','reviewer')
        r=await self.client.post('/api/v1/cases',json={'title':'Restricted'})
        case=r.json()['id']
        blocked=await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='http://localhost',headers={'X-Evora-Request':'1'}))
        await blocked.post('/api/v1/auth/login',json=dict(username='investigator',password='temporary passphrase'))
        self.assertEqual((await blocked.get('/api/v1/cases')).status_code,403)
        investigator=await self.other()
        reader=await self.other('reviewer')
        self.assertEqual((await investigator.get(f'/api/v1/cases/{case}')).status_code,404)
        for member in (user,reviewer):
            self.assertEqual((await self.client.put(f'/api/v1/cases/{case}/members',json={'user_id':member['id'],'grant':True})).status_code,200)
        self.assertEqual((await investigator.get(f'/api/v1/cases/{case}')).status_code,200)
        self.assertEqual((await reader.get(f'/api/v1/cases/{case}')).status_code,200)
        self.assertEqual((await reader.post('/api/v1/cases',json={'title':'Forbidden'})).status_code,403)
        self.assertEqual((await investigator.get('/api/v1/accounts')).status_code,403)
        await self.client.put(f'/api/v1/cases/{case}/members',json={'user_id':user['id'],'grant':False})
        self.assertEqual((await investigator.get(f'/api/v1/cases/{case}')).status_code,404)
        with self.app.state.database.connect() as c:
            row=c.execute("SELECT actor_id FROM account_audit WHERE action='grantCaseAccess' LIMIT 1").fetchone()
            self.assertIsNotNone(row)

    async def test_reset_disable_and_last_admin_guard(self):
        result=await self.setup_admin();uid=result['user']['id']
        self.assertEqual((await self.client.put(f'/api/v1/accounts/{uid}',json={'disabled':True})).status_code,409)
        user=await self.new_user();other=await self.other()
        r=await self.client.put(f'/api/v1/accounts/{user["id"]}',json={'new_password':'reset password long enough'})
        self.assertEqual(r.status_code,200)
        self.assertEqual((await other.get('/api/v1/cases')).status_code,401)
        await self.client.put(f'/api/v1/accounts/{user["id"]}',json={'disabled':True})
        r=await other.post('/api/v1/auth/login',json={'username':user['username'],'password':'reset password long enough'})
        self.assertEqual(r.status_code,401)

    async def test_recovery_rotates_code_revokes_sessions_and_survives_restart(self):
        result=await self.setup_admin()
        await self.client.post('/api/v1/cases',json={'title':'Preserved'})
        body=dict(username='admin',recovery_code=result['recovery_code'],new_password='a replacement passphrase')
        r=await self.client.post('/api/v1/auth/recover',json=body)
        self.assertEqual(r.status_code,200)
        self.assertNotEqual(r.json()['recovery_code'],result['recovery_code'])
        self.assertEqual((await self.client.get('/api/v1/cases')).status_code,401)
        self.assertEqual((await self.client.post('/api/v1/auth/recover',json=body)).status_code,400)
        app=create_app(Path(self.root)/'accounts.sqlite')
        async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://localhost',headers={'X-Evora-Request':'1'}) as restarted:
            self.assertFalse((await restarted.get('/api/v1/auth/status')).json()['setup_required'])
            r=await restarted.post('/api/v1/auth/login',json={'username':'admin','password':'a replacement passphrase'})
            self.assertEqual(r.status_code,200)
            self.assertEqual((await restarted.get('/api/v1/cases')).json()['total'],1)

    async def test_idle_and_absolute_expiry_and_background_reads_do_not_extend_session(self):
        await self.setup_admin()
        with self.app.state.database.connect() as c:
            c.execute('UPDATE local_sessions SET last_seen=?',(time.time()-100,))
        await self.client.get('/api/v1/cases')
        with self.app.state.database.connect() as c:
            self.assertLess(c.execute('SELECT last_seen FROM local_sessions').fetchone()[0],time.time()-90)
        await self.client.post('/api/v1/auth/activity')
        with self.app.state.database.connect() as c:
            self.assertGreater(c.execute('SELECT last_seen FROM local_sessions').fetchone()[0],time.time()-5)
            c.execute('UPDATE local_sessions SET last_seen=?',(time.time()-IDLE_SECONDS-1,))
        self.assertEqual((await self.client.get('/api/v1/cases')).status_code,401)

    async def test_offline_configuration_blocks_external_provider_and_model_requests(self):
        await self.setup_admin()
        with patch('backend.app.httpx.AsyncClient.get') as outbound:
            for body in ({'qa_provider':'openai'},{'qa_url':'http://192.168.1.1:11434'},{'qa_url':'https://external.example'}):
                r=await self.client.put('/api/v1/settings',json=body)
                self.assertEqual(r.status_code,400)
                r=await self.client.post('/api/v1/settings/models',json=body)
                self.assertEqual(r.status_code,400)
            outbound.assert_not_called()
        self.assertEqual(self.app.state.qa_provider,'ollama')

    async def test_invalid_login_is_generic_and_throttled(self):
        await self.setup_admin()
        for _ in range(8):
            r=await self.client.post('/api/v1/auth/login',json={'username':'missing','password':'wrong'})
            self.assertEqual(r.status_code,401)
            self.assertEqual(r.json()['message'],'Username or password is incorrect.')
        self.assertEqual((await self.client.post('/api/v1/auth/login',json={'username':'missing','password':'wrong'})).status_code,429)

    async def test_simultaneous_first_launch_creates_one_administrator(self):
        responses=await asyncio.gather(*[self.client.post('/api/v1/auth/setup',json={**self.credentials,'username':name}) for name in ('admin-one','admin-two')])
        self.assertEqual(sorted(response.status_code for response in responses),[200,409])
        with self.app.state.database.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM local_users').fetchone()[0],1)

    async def test_https_cookie_is_secure_and_absolute_expiry_revokes_it(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='https://localhost',headers={'X-Evora-Request':'1'}) as secure:
            response=await secure.post('/api/v1/auth/setup',json=self.credentials)
            self.assertIn('secure',response.headers['set-cookie'].lower())
            with self.app.state.database.connect() as c:
                c.execute('UPDATE local_sessions SET created_at=?',(time.time()-12*60*60-1,))
            self.assertEqual((await secure.get('/api/v1/cases')).status_code,401)

    async def test_existing_cases_and_evidence_audit_keep_their_owners(self):
        with self.app.state.database.connect() as c:
            c.execute("INSERT INTO cases VALUES ('11111111-1111-4111-8111-111111111111','Existing case',NULL,'2026-01-01T00:00:00Z')")
            c.execute("INSERT INTO case_members VALUES ('11111111-1111-4111-8111-111111111111','investigator-1')")
        result=await self.setup_admin()
        cases=(await self.client.get('/api/v1/cases')).json()
        self.assertEqual(cases['total'],1)
        case=cases['items'][0]['id']
        response=await self.client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'document','source_label':'Local source'},files={'file':('notes.txt',b'Original source','text/plain')})
        self.assertEqual(response.status_code,201,response.text)
        with self.app.state.database.connect() as c:
            self.assertEqual(c.execute('SELECT actor_id FROM audit_events').fetchone()[0],result['user']['id'])
            self.assertIsNotNone(c.execute("SELECT 1 FROM case_members WHERE actor_id='investigator-1'").fetchone())

    async def test_administrator_can_enable_online_and_return_to_offline_mode(self):
        await self.setup_admin()
        response=await self.client.put('/api/v1/settings',json={'offline_mode':False,'qa_provider':'openai','openai_api_key':'synthetic-key','vision_model':'vision-capable-model'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['offline_mode'])
        self.assertEqual(response.json()['vision_model'],'vision-capable-model')
        response=await self.client.put('/api/v1/settings',json={'offline_mode':True,'qa_provider':'ollama'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['offline_mode'])

    async def test_saved_provider_key_cannot_be_redirected_to_another_url(self):
        await self.setup_admin()
        await self.client.put('/api/v1/settings',json={'offline_mode':False,'qa_provider':'openai','openai_api_key':'synthetic-key'})
        with patch('backend.app.httpx.AsyncClient.get') as outbound:
            response=await self.client.post('/api/v1/settings/models',json={'qa_provider':'openai','openai_base_url':'https://untrusted.example/v1'})
            self.assertEqual(response.status_code,400)
            response=await self.client.put('/api/v1/settings',json={'openai_base_url':'https://untrusted.example/v1'})
            self.assertEqual(response.status_code,400)
            outbound.assert_not_called()

    async def test_draft_online_connection_works_before_saving_offline_switch(self):
        await self.setup_admin()
        remote = httpx.Response(200, request=httpx.Request('GET', 'https://openrouter.ai/api/v1/models'),
            json={'data': [dict(id='provider/multimodal', architecture={'input_modalities':['text','image']}),
                           dict(id='provider/text', architecture={'input_modalities':['text']})]})
        with patch('backend.app.httpx.AsyncClient.get', return_value=remote) as outbound:
            response=await self.client.post('/api/v1/settings/models',json={
                'offline_mode':False,'qa_provider':'openai','openai_base_url':'https://openrouter.ai/api/v1/',
                'openai_api_key':'synthetic-key'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['vision_models'],['provider/multimodal'])
            outbound.assert_awaited_once_with('https://openrouter.ai/api/v1/models', headers={'Authorization':'Bearer synthetic-key'})
        self.assertTrue(self.app.state.offline_mode)
        self.assertEqual(self.app.state.qa_provider,'ollama')
        self.assertIsNone(self.app.state.openai_api_key)
        with patch('backend.app.httpx.AsyncClient.get') as outbound:
            response=await self.client.post('/api/v1/settings/models',json={
                'qa_provider':'openai','openai_api_key':'synthetic-key'})
            self.assertEqual(response.status_code,400)
            outbound.assert_not_called()

    async def test_investigator_cannot_override_offline_mode_for_connection_test(self):
        await self.setup_admin()
        await self.new_user()
        other=await self.other()
        with patch('backend.app.httpx.AsyncClient.get') as outbound:
            response=await other.post('/api/v1/settings/models',json={
                'offline_mode':False,'qa_provider':'openai','openai_api_key':'synthetic-key'})
            self.assertEqual(response.status_code,403)
            outbound.assert_not_called()
