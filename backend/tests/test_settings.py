"""Runtime workstation settings and provider connectivity, without live model servers."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend import qa_synthesis


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        with patch.dict(os.environ, {}, clear=True):
            self.app = create_app(self.root / 'settings.sqlite3', token_verifier=SyntheticTokenVerifier({
                'settings-test': 'investigator-1',
            }))
        self.client = await self.enterAsyncContext(httpx.AsyncClient(
            transport=httpx.ASGITransport(self.app), base_url='http://test',
            headers={'Authorization': 'Bearer settings-test'},
        ))

    async def test_defaults_and_environment(self):
        response = await self.client.get('/api/v1/settings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.json(), dict(qa_model='deepseek-r1:8b', qa_url='http://127.0.0.1:11434',
                                              qa_provider='ollama', openai_base_url='https://api.openai.com/v1',
                                              has_openai_key=False,
                                              detection_threshold=.7, show_provenance_rays=True))
        with patch.dict(os.environ, {'EVORA_QA_MODEL': 'custom:latest', 'EVORA_QA_URL': 'http://localhost:1234/'}):
            other = create_app(self.root / 'other.sqlite3')
        self.assertEqual(other.state.qa_model, 'custom:latest')
        self.assertEqual(other.state.qa_url, 'http://localhost:1234')

    async def test_put_updates_live_state_and_get_without_restart(self):
        settings = dict(qa_model='llama3.1:8b', qa_url='http://localhost:1234',
                        detection_threshold=.95, show_provenance_rays=False)
        response = await self.client.put('/api/v1/settings', json=settings)
        settings.update(qa_provider='ollama', openai_base_url='https://api.openai.com/v1', has_openai_key=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), settings)
        self.assertEqual((await self.client.get('/api/v1/settings')).json(), settings)
        for key, value in settings.items():
            if key != 'has_openai_key':
                self.assertEqual(getattr(self.app.state, key), value)
        for threshold in (.1, 1.0):
            response = await self.client.put('/api/v1/settings', json={'detection_threshold': threshold})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {**settings, 'detection_threshold': threshold})

    async def test_invalid_updates_are_atomic(self):
        before = (await self.client.get('/api/v1/settings')).json()
        for invalid in [
            {'detection_threshold': .09}, {'detection_threshold': 1.01}, {'detection_threshold': '0.7'},
            {'detection_threshold': True}, {'show_provenance_rays': 'false'}, {'qa_model': ''},
            {'qa_model': '  '}, {'qa_model': 123}, {'qa_model': 'model\nname'}, {'qa_model': None},
            {'qa_url': 'file:///tmp/private'}, {'qa_url': 'http://user:password@localhost'},
            {'qa_url': 'http://localhost:99999'}, {'qa_url': 'http://localhost/api/chat'},
            {'qa_url': 'http://localhost?key=private'}, {'unknown': True},
            {'qa_provider': 'invalid'}, {'qa_provider': None}, {'openai_api_key': 123},
            {'openai_api_key': 'sk-secret\nInjected: header'},
            {'openai_base_url': 'file:///tmp/private'}, {'openai_base_url': 'https://user:secret@api.test/v1'},
            {'openai_base_url': 'https://api.test/v1?key=secret'}, {'openai_base_url': 'https://api.test/v1#fragment'},
            {'openai_base_url': 'https://api.test:99999/v1'},
        ]:
            with self.subTest(invalid=invalid):
                response = await self.client.put('/api/v1/settings', json={'qa_model': 'changed:8b', **invalid})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual((await self.client.get('/api/v1/settings')).json(), before)
        response = await self.client.put('/api/v1/settings', content='{"detection_threshold": NaN}',
                                         headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 400)

    async def test_authentication_required_for_all_settings_routes(self):
        for method, path, body in [('GET', '/api/v1/settings', None), ('PUT', '/api/v1/settings', {'qa_model': 'changed'}),
                                   ('POST', '/api/v1/settings/models', {'qa_url': 'http://localhost:11434'})]:
            for authorization in ('', 'Bearer rejected'):
                response = await self.client.request(method, path, json=body, headers={'Authorization': authorization})
                self.assertEqual(response.status_code, 401)
        self.assertEqual(self.app.state.qa_model, 'deepseek-r1:8b')

    async def test_models_use_draft_url_without_mutating_settings(self):
        for models in ([], [{'name': 'qwen2.5-coder:7b'}, {'name': 'llama3.1:8b'}, {'name': 'llama3.1:8b'}]):
            remote = httpx.Response(200, json={'models': models}, request=httpx.Request('GET', 'http://localhost/api/tags'))
            with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock, return_value=remote) as get:
                response = await self.client.post('/api/v1/settings/models', json={'qa_url': 'http://localhost:1234/'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'models': sorted({m['name'] for m in models})})
            get.assert_awaited_once_with('http://localhost:1234/api/tags')
            self.assertEqual(self.app.state.qa_url, 'http://127.0.0.1:11434')

    async def test_models_failures_are_safe(self):
        for payload in ({}, {'models': None}, {'models': [{}]}, {'models': [42]}, []):
            remote = httpx.Response(200, json=payload, request=httpx.Request('GET', 'http://localhost/api/tags'))
            with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock, return_value=remote):
                response = await self.client.post('/api/v1/settings/models', json={'qa_url': 'http://localhost'})
            self.assertEqual(response.status_code, 502)
        with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock, side_effect=httpx.ConnectError('PRIVATE')):
            response = await self.client.post('/api/v1/settings/models', json={'qa_url': 'http://localhost'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('PRIVATE', response.text)

    async def test_openai_key_is_write_only_and_retained_on_partial_updates(self):
        response = await self.client.put('/api/v1/settings', json={
            'qa_provider': 'openai', 'openai_api_key': 'sk-private-key',
            'openai_base_url': 'https://provider.test/api/v1/', 'qa_model': 'custom-model',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['has_openai_key'])
        self.assertNotIn('openai_api_key', response.json())
        self.assertNotIn('sk-private-key', response.text)
        self.assertEqual(response.json()['openai_base_url'], 'https://provider.test/api/v1')
        for changes in ({}, {'openai_api_key': None}, {'openai_api_key': ''}, {'openai_api_key': '  '},
                        {'openai_api_key': 'sk-private-key'}, {'qa_provider': 'ollama'}):
            response = await self.client.put('/api/v1/settings', json=changes)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.app.state.openai_api_key, 'sk-private-key')
            self.assertTrue(response.json()['has_openai_key'])
            self.assertNotIn('sk-private-key', response.text)
        await self.client.put('/api/v1/settings', json={'openai_api_key': 'sk-replacement'})
        self.assertEqual(self.app.state.openai_api_key, 'sk-replacement')
        response = await self.client.get('/api/v1/settings')
        self.assertNotIn('sk-replacement', response.text)
        self.assertNotIn('openai_api_key', response.json())

    async def test_openai_models_use_draft_or_saved_credentials_without_mutation(self):
        await self.client.put('/api/v1/settings', json={
            'qa_provider': 'openai', 'openai_api_key': 'sk-saved',
            'openai_base_url': 'https://saved.test/api/v1',
        })
        before = (await self.client.get('/api/v1/settings')).json()
        for body, url, key in [
            ({}, 'https://saved.test/api/v1/models', 'sk-saved'),
            ({'qa_provider': 'openai', 'openai_base_url': 'https://draft.test/openai/v1/',
              'openai_api_key': 'sk-draft'}, 'https://draft.test/openai/v1/models', 'sk-draft'),
            ({'qa_provider': 'openai', 'openai_api_key': ''}, 'https://saved.test/api/v1/models', 'sk-saved'),
        ]:
            remote = httpx.Response(200, json={'data': [{'id': 'gpt-4o'}, {'id': 'custom'}, {'id': 'gpt-4o'}]},
                                    request=httpx.Request('GET', url))
            with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock, return_value=remote) as get:
                response = await self.client.post('/api/v1/settings/models', json=body)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'models': ['custom', 'gpt-4o']})
            get.assert_awaited_once_with(url, headers={'Authorization': f'Bearer {key}'})
            self.assertEqual((await self.client.get('/api/v1/settings')).json(), before)
            self.assertEqual(self.app.state.openai_api_key, 'sk-saved')

    async def test_openai_model_errors_do_not_leak_credentials(self):
        with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock) as get:
            response = await self.client.post('/api/v1/settings/models', json={'qa_provider': 'openai'})
        self.assertEqual(response.status_code, 400)
        get.assert_not_awaited()
        for status, payload in [(200, {}), (200, []), (200, {'data': None}), (200, {'data': [{}]}),
                                (401, {'error': 'sk-private'}), (429, {'error': 'sk-private'}),
                                (500, {'error': 'sk-private'}), (302, {})]:
            remote = httpx.Response(status, json=payload, request=httpx.Request('GET', 'https://provider.test/v1/models'))
            with patch('backend.app.httpx.AsyncClient.get', new_callable=AsyncMock, return_value=remote):
                response = await self.client.post('/api/v1/settings/models', json={
                    'qa_provider': 'openai', 'openai_api_key': 'sk-private',
                })
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()['code'], 'OPENAI_UNAVAILABLE')
            self.assertNotIn('sk-private', response.text)

    async def test_updated_endpoint_and_model_used_for_generation_and_verification(self):
        await self.client.put('/api/v1/settings', json={'qa_url': 'http://localhost:1234', 'qa_model': 'qwen2.5-coder:7b'})
        calls = []
        observation = dict(id='observation-1', evidence_id='evidence-1', source_locator='row 2', normalized_value='D-7')
        def respond(request):
            calls.append((str(request.url), json.loads(request.content)['model']))
            answer = (dict(supported=True, claims=[dict(text='Recorded D-7.', observation_ids=['observation-1'])])
                      if len(calls) == 1 else dict(supported=True))
            return httpx.Response(200, json=dict(done=True, message=dict(content=json.dumps(answer))))
        observation['kind'] = 'network.device'
        real_client = httpx.Client
        with patch('backend.qa_synthesis.httpx.Client', side_effect=lambda **kw: real_client(transport=httpx.MockTransport(respond))):
            qa_synthesis.synthesize('D-7?', {'observations': [observation]}, self.app.state.qa_model, qa_url=self.app.state.qa_url)
        self.assertEqual(calls, [('http://localhost:1234/api/chat', 'qwen2.5-coder:7b')] * 2)


class QuestionRuntimeSettingsTests(unittest.IsolatedAsyncioTestCase):
    from backend.tests import test_questions as _questions
    asyncSetUp = _questions.QuestionTests.asyncSetUp
    new_case = _questions.QuestionTests.new_case
    upload = _questions.QuestionTests.upload
    process = _questions.QuestionTests.process

    async def test_question_route_uses_updated_model_and_endpoint(self):
        response = await self.client.put('/api/v1/settings', json={
            'qa_model': 'llama3.1:8b', 'qa_url': 'http://localhost:1234',
        })
        self.assertEqual(response.status_code, 200)
        with patch('backend.questions.synthesize', return_value=([], 'llama3.1:8b', {'status': 'abstained'})) as synthesize:
            response = await self.client.post(self.url, json={'question': 'D-7?'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(synthesize.call_args.args[2], 'llama3.1:8b')
        self.assertEqual(synthesize.call_args.kwargs, {
            'qa_url': 'http://localhost:1234', 'qa_provider': 'ollama',
            'openai_api_key': None, 'openai_base_url': 'https://api.openai.com/v1',
        })

    async def test_question_route_passes_openai_settings_and_records_provider(self):
        await self.client.put('/api/v1/settings', json={
            'qa_provider': 'openai', 'qa_model': 'gpt-4o', 'openai_api_key': 'sk-private',
            'openai_base_url': 'https://provider.test/api/v1',
        })
        with patch('backend.questions.synthesize', return_value=([], 'gpt-4o-snapshot', {'status': 'abstained'})) as synthesize:
            response = await self.client.post(self.url, json={'question': 'D-7?'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(synthesize.call_args.args[2], 'gpt-4o')
        self.assertEqual(synthesize.call_args.kwargs, {
            'qa_provider': 'openai', 'qa_url': 'http://127.0.0.1:11434',
            'openai_api_key': 'sk-private', 'openai_base_url': 'https://provider.test/api/v1',
        })
        self.assertEqual(response.json()['model_version'], 'openai:gpt-4o-snapshot')
        self.assertNotIn('sk-private', response.text)
        with self.app.state.database.connect() as connection:
            payload = connection.execute('SELECT payload_json FROM qa_provenance WHERE id=?',
                                         (response.json()['provenance_id'],)).fetchone()[0]
        self.assertNotIn('sk-private', payload)
