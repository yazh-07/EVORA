"""Real encrypted workstation restart; no model-provider requests."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
from backend.app import create_app


class WorkstationSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.path=self.root/'case.sqlite'
        self.credentials=dict(username='admin',password='workstation persistence test passphrase',display_name='Test Admin')

    @asynccontextmanager
    async def station(self,**kwargs):
        with patch.dict(os.environ,{},clear=True):app=create_app(self.path,**kwargs)
        async with app.router.lifespan_context(app),httpx.AsyncClient(transport=httpx.ASGITransport(app),
                base_url='http://localhost',headers={'X-Evora-Request':'1'}) as client:
            yield app,client

    async def setup(self,client):
        result=await client.post('/api/v1/auth/setup',json=self.credentials)
        self.assertEqual(result.status_code,200,result.text)

    async def login(self,client):
        result=await client.post('/api/v1/auth/login',json={key:self.credentials[key] for key in ('username','password')})
        self.assertEqual(result.status_code,200,result.text)

    async def test_online_provider_and_vision_model_survive_encrypted_restart(self):
        secret='synthetic-persisted-api-key'
        async with self.station() as (app,client):
            await self.setup(client)
            response=await client.put('/api/v1/settings',json=dict(offline_mode=False,qa_provider='chatgpt',
                qa_model='test-vision',vision_use_qa_model=True,openai_api_key=secret,automatic_update_checks=False))
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(app.state.database.encrypted)
        self.assertNotIn(secret.encode(),self.path.read_bytes())
        async with self.station() as (app,client):
            self.assertTrue(app.state.database.locked)
            rejected=await client.post('/api/v1/auth/login',json={'username':'admin','password':'incorrect password'})
            self.assertEqual(rejected.status_code,401)
            self.assertTrue(app.state.database.locked)
            await self.login(client)
            saved=(await client.get('/api/v1/settings')).json()
            self.assertFalse(saved['offline_mode']);self.assertEqual(saved['qa_provider'],'chatgpt')
            self.assertEqual(saved['qa_model'],'test-vision');self.assertTrue(saved['vision_use_qa_model'])
            self.assertFalse(saved['automatic_update_checks']);self.assertTrue(saved['has_openai_key'])
            self.assertEqual(app.state.openai_api_key,secret)
            self.assertNotIn(secret,str(saved))

    async def test_local_choice_survives_restart_and_invalid_update_does_not_replace_it(self):
        async with self.station() as (_,client):
            await self.setup(client)
            self.assertEqual((await client.put('/api/v1/settings',json={'qa_model':'local-choice','offline_mode':True})).status_code,200)
            self.assertEqual((await client.put('/api/v1/settings',json={'qa_provider':'openai','offline_mode':True,'qa_model':'wrong'})).status_code,400)
        async with self.station() as (_,client):
            await self.login(client)
            saved=(await client.get('/api/v1/settings')).json()
            self.assertTrue(saved['offline_mode']);self.assertEqual(saved['qa_provider'],'ollama')
            self.assertEqual(saved['qa_model'],'local-choice')

    async def test_explicit_offline_start_overrides_saved_online_mode(self):
        async with self.station() as (_,client):
            await self.setup(client)
            self.assertEqual((await client.put('/api/v1/settings',json={'offline_mode':False,'qa_provider':'chatgpt'})).status_code,200)
        async with self.station(offline_mode=True) as (_,client):
            await self.login(client)
            saved=(await client.get('/api/v1/settings')).json()
            self.assertTrue(saved['offline_mode']);self.assertEqual(saved['qa_provider'],'ollama')

