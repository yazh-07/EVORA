"""Real SQLCipher at rest, password/recovery unlocking and transactional key lifecycle."""
import os
import asyncio
import threading
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
from backend.app import create_app
from backend.database import SQLiteDatabase, HEADER
from backend.database_keys import atomic_json, user_key
from backend.local_auth import COOKIE, HASHER


class DatabaseEncryptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.path = self.root/'case.sqlite3'
        self.credentials = dict(username='admin',password='correct horse battery staple',display_name='Admin')
        self.app,self.client = await self.start()

    async def start(self):
        app=create_app(self.path,storage_dir=self.root/'evidence')
        await self.enterAsyncContext(app.router.lifespan_context(app))
        client=await self.enterAsyncContext(httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://localhost',headers={'X-Evora-Request':'1'}))
        return app,client

    async def setup(self):
        response=await self.client.post('/api/v1/auth/setup',json=self.credentials)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def sign_in(self,client=None,password=None,username='admin'):
        return await (client or self.client).post('/api/v1/auth/login',json=dict(username=username,password=password or self.credentials['password']))

    def assert_encrypted(self):
        self.assertNotEqual(self.path.read_bytes()[:16],HEADER)
        with closing(sqlite3.connect(self.path)) as plain:
            with self.assertRaises(sqlite3.DatabaseError):plain.execute('SELECT * FROM local_users')
        for path in self.root.glob('case.sqlite3*'):
            if path.is_file():
                raw=path.read_bytes()
                self.assertNotIn(b'Sensitive synthetic investigation',raw,path.name)
                self.assertNotIn(self.credentials['password'].encode(),raw,path.name)

    async def test_setup_encrypts_rows_and_wal_without_plaintext_key_or_password(self):
        await self.setup()
        response=await self.client.post('/api/v1/cases',json={'title':'Sensitive synthetic investigation'})
        self.assertEqual(response.status_code,201,response.text)
        self.assert_encrypted()
        keys=self.app.state.database.keys.read()
        self.assertEqual(set(keys['users']),{user_key('admin')})
        if os.name!='nt':self.assertEqual(self.app.state.database.keys.path.stat().st_mode & 0o777,0o600)
        with self.app.state.database.connect() as connection:
            self.assertTrue(connection.execute('PRAGMA cipher_version').fetchone()[0])
            self.assertEqual(connection.execute('PRAGMA temp_store').fetchone()[0],2)

    async def test_restart_requires_password_even_with_prior_browser_cookie(self):
        await self.setup()
        await self.client.post('/api/v1/cases',json={'title':'Preserved'})
        old_cookie=self.client.cookies[COOKIE]
        app,client=await self.start()
        status=(await client.get('/api/v1/auth/status')).json()
        self.assertTrue(status['database_encrypted']);self.assertTrue(status['database_locked'])
        client.cookies.set(COOKIE,old_cookie)
        self.assertEqual((await client.get('/api/v1/cases')).status_code,401)
        bad=await self.sign_in(client,password='wrong password')
        self.assertEqual(bad.status_code,401);self.assertTrue(app.state.database.locked)
        good=await self.sign_in(client)
        self.assertEqual(good.status_code,200,good.text)
        self.assertEqual((await client.get('/api/v1/cases')).json()['total'],1)
        self.assertFalse(app.state.database.locked)
        self.client.cookies.clear();self.client.cookies.set(COOKIE,old_cookie)
        self.assertEqual((await self.client.get('/api/v1/cases')).status_code,401)

    async def test_password_change_rewraps_key_and_old_password_cannot_unlock(self):
        await self.setup()
        before=self.app.state.database.keys.path.read_bytes()
        change=await self.client.post('/api/v1/auth/password',json=dict(current_password=self.credentials['password'],new_password='replacement password phrase'))
        self.assertEqual(change.status_code,200,change.text)
        self.assertNotEqual(before,self.app.state.database.keys.path.read_bytes())
        app,client=await self.start()
        self.assertEqual((await self.sign_in(client)).status_code,401)
        self.assertTrue(app.state.database.locked)
        self.assertEqual((await self.sign_in(client,password='replacement password phrase')).status_code,200)
        self.assert_encrypted()

    async def test_recovery_unlocks_a_cold_database_and_rotates_both_credentials(self):
        setup=await self.setup()
        app,client=await self.start()
        self.assertEqual((await client.post('/api/v1/auth/recover',json=dict(username='admin',recovery_code='invalid recovery',new_password='recovered password phrase'))).status_code,400)
        self.assertTrue(app.state.database.locked)
        response=await client.post('/api/v1/auth/recover',json=dict(username='admin',recovery_code=setup['recovery_code'],new_password='recovered password phrase'))
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotEqual(response.json()['recovery_code'],setup['recovery_code'])
        app2,client2=await self.start()
        self.assertEqual((await self.sign_in(client2)).status_code,401)
        self.assertEqual((await client2.post('/api/v1/auth/recover',json=dict(username='admin',recovery_code=setup['recovery_code'],new_password='other password phrase'))).status_code,400)
        self.assertEqual((await self.sign_in(client2,password='recovered password phrase')).status_code,200)

    async def test_new_account_and_admin_password_reset_unlock_after_restart(self):
        await self.setup()
        response=await self.client.post('/api/v1/accounts',json=dict(username='investigator',password='initial user passphrase',display_name='Investigator',role='investigator'))
        self.assertEqual(response.status_code,201,response.text)
        uid=response.json()['user']['id']
        app,client=await self.start()
        response=await self.sign_in(client,username='investigator',password='initial user passphrase')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual((await self.sign_in()).status_code,200)
        response=await self.client.put('/api/v1/accounts/'+uid,json={'new_password':'reset user passphrase'})
        self.assertEqual(response.status_code,200,response.text)
        app2,client2=await self.start()
        self.assertEqual((await self.sign_in(client2,username='investigator',password='initial user passphrase')).status_code,401)
        self.assertEqual((await self.sign_in(client2,username='investigator',password='reset user passphrase')).status_code,200)

    async def test_duplicate_account_rolls_back_staged_wraps(self):
        await self.setup()
        before=self.app.state.database.keys.read()
        response=await self.client.post('/api/v1/accounts',json={**self.credentials,'role':'investigator'})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(before,self.app.state.database.keys.read())

    async def test_disabled_account_cannot_unlock_or_leave_a_key_in_memory(self):
        await self.setup()
        response=await self.client.post('/api/v1/accounts',json=dict(username='disabled',password='disabled user phrase',display_name='Disabled',role='investigator'))
        await self.client.put('/api/v1/accounts/'+response.json()['user']['id'],json={'disabled':True})
        app,client=await self.start()
        self.assertEqual((await self.sign_in(client,username='disabled',password='disabled user phrase')).status_code,401)
        self.assertTrue(app.state.database.locked)

    async def test_plaintext_migration_preserves_all_rows_and_supplies_new_recovery_code(self):
        # Build the same legacy account store before setup encryption existed.
        import time
        from backend.local_auth import digest
        with self.app.state.database.connect() as c:
            c.execute('INSERT INTO local_users VALUES (?,?,?,?,?,0,0,?,?)',('00000000-0000-4000-8000-000000000001','admin','Admin',HASHER.hash(self.credentials['password']),'administrator',digest('old recovery'),time.time()))
            c.execute('INSERT INTO cases VALUES (?,?,?,?)',('00000000-0000-4000-8000-000000000002','Sensitive synthetic investigation',None,'2026-11-07T00:00:00Z'))
        with self.app.state.database.connect() as c:
            old=dict(c.execute('SELECT * FROM cases').fetchone())
        case='00000000-0000-4000-8000-000000000002'
        # Simulate a session issued by the old unencrypted app, then use real producers.
        with self.app.state.database.connect() as c:
            c.execute('INSERT INTO case_members VALUES (?,?)',(case,'00000000-0000-4000-8000-000000000001'))
            c.execute('INSERT INTO local_sessions VALUES (?,?,?,?)',(digest('synthetic-legacy-session'),'00000000-0000-4000-8000-000000000001',time.time(),time.time()))
        self.client.cookies.set(COOKIE,'synthetic-legacy-session')
        csv=b'timestamp,device_id,ip_address,event\n2026-01-12T10:00:00Z,D-7,192.0.2.7,connected\n'
        evidence=await self.client.post(f'/api/v1/cases/{case}/evidence',data={'kind':'network_log','source_label':'Legacy gateway'},files={'file':('gateway.csv',csv,'text/csv')})
        self.assertEqual(evidence.status_code,201,evidence.text)
        eid=evidence.json()['id']
        response=await self.client.post(f'/api/v1/cases/{case}/evidence/{eid}/processing-runs',headers={'Idempotency-Key':'00000000-0000-4000-8000-000000000003'})
        self.assertEqual(response.status_code,202,response.text)
        rid=response.json()['id']
        run=(await self.client.get(f'/api/v1/cases/{case}/evidence/{eid}/processing-runs/{rid}')).json()
        self.assertEqual(run['status'],'completed',run)
        before=(await self.client.get(f'/api/v1/cases/{case}/observations')).json()
        self.assertTrue(before['items'])
        self.assertEqual(self.path.read_bytes()[:16],HEADER)
        response=await self.sign_in()
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['recovery_code'])
        with self.app.state.database.connect() as c:self.assertEqual(old,dict(c.execute('SELECT * FROM cases').fetchone()))
        self.assert_encrypted()
        app,client=await self.start()
        self.assertEqual((await self.sign_in(client)).status_code,200)
        self.assertEqual((await client.get(f'/api/v1/cases/{case}/observations')).json(),before)
        self.assertEqual((await client.get(f'/api/v1/cases/{case}/evidence/{eid}/content')).content,csv)
        # Analysis acceptance must use the SQLCipher connection's existing transaction.
        from backend import analysis
        from backend.tests.test_analysis import GraphDouble
        app.state.qa_model=''
        with patch.object(analysis,'Neo4jGraphDatabase',return_value=GraphDouble()):
            accepted=await client.post(f'/api/v1/cases/{case}/analysis-runs',headers={'Idempotency-Key':'00000000-0000-4000-8000-000000000004'})
        self.assertEqual(accepted.status_code,202,accepted.text)
        completed=(await client.get(f"/api/v1/cases/{case}/analysis-runs/{accepted.json()['id']}")).json()
        self.assertEqual(completed['status'],'completed',completed)
        self.assertEqual(set(completed['input_snapshot']['observation_ids']),{o['id'] for o in before['items']})


    async def test_failed_key_file_write_keeps_original_database_readable(self):
        with patch('backend.database_keys.atomic_json',side_effect=OSError('synthetic permission failure')):
            response=await self.client.post('/api/v1/auth/setup',json=self.credentials)
        self.assertEqual(response.status_code,500,response.text)
        self.assertEqual(list(self.root.glob('*.encrypted.tmp')),[])
        self.assertEqual(self.path.read_bytes()[:16],HEADER)
        with closing(sqlite3.connect(self.path)) as c:self.assertEqual(c.execute('SELECT count(*) FROM local_users').fetchone()[0],1)
        response=await self.sign_in()
        self.assertEqual(response.status_code,200,response.text)
        self.assert_encrypted()

    async def test_staged_but_uncommitted_password_does_not_unlock(self):
        await self.setup()
        db=self.app.state.database
        with db.guard():
            for candidate in ['uncommitted replacement phrase','another uncommitted phrase','third uncommitted phrase']:
                db.keys.stage(db._key,'admin',password=candidate)
        app,client=await self.start()
        self.assertEqual((await self.sign_in(client,password='uncommitted replacement phrase')).status_code,401)
        self.assertTrue(app.state.database.locked)
        self.assertEqual((await self.sign_in(client)).status_code,200)

    async def test_locked_login_throttles_without_opening_the_database(self):
        await self.setup();app,client=await self.start()
        for _ in range(8):self.assertEqual((await self.sign_in(client,password='wrong password')).status_code,401)
        self.assertEqual((await self.sign_in(client,password='wrong password')).status_code,429)
        self.assertTrue(app.state.database.locked)

    async def test_encrypted_reader_sees_prior_commit_while_writer_is_pending(self):
        await self.setup()
        await self.client.post('/api/v1/cases',json={'title':'Committed title'})
        entered, release = threading.Event(), threading.Event()
        def writer():
            with self.app.state.database.connect() as c:
                c.execute("UPDATE cases SET title='Uncommitted title'")
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('Writer release timed out')
        def reader():
            with self.app.state.database.connect() as c:
                return c.execute('SELECT title FROM cases').fetchone()[0]
        task=asyncio.create_task(asyncio.to_thread(writer))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait,2))
            self.assertEqual(await asyncio.wait_for(asyncio.to_thread(reader),2),'Committed title')
        finally:
            release.set();await task
