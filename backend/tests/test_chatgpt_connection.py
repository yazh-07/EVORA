"""Real OAuth state/PKCE, RSA JWT validation and loopback callback; OpenAI protocol doubles."""
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
import time
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from backend import chatgpt_connection as cg
from backend.tests import test_local_auth as local


class ChatGPTTests(unittest.IsolatedAsyncioTestCase):
    # Use only the common fixture, not inherited account-test cases.
    asyncSetUp=local.LocalAuthTests.asyncSetUp
    setup_admin=local.LocalAuthTests.setup_admin

    async def begin(self):
        await self.setup_admin()
        result=await self.client.post('/api/v1/chatgpt/connect',json={'offline_mode':False})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['authorization_url']

    def provider(self,scope='openid chatgpt.tokens.use.direct',nonce=None,stream=None):
        requests=[];connection=self.app.state.chatgpt_connection
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));jwk.update(kid='test-key')
        def respond(request):
            requests.append(request)
            if request.url.path.endswith('/oauth/token'):
                body=parse_qs(request.content.decode())
                identity=jwt.encode(dict(sub='test-subject',iss=cg.AUTH,aud='oaiapp_test',iat=int(time.time()),exp=int(time.time())+3600,
                    nonce=nonce or self.nonce,email='tester@example.test'),key,algorithm='RS256',headers={'kid':'test-key'})
                return httpx.Response(200,json=dict(access_token='private-access',refresh_token='private-refresh',id_token=identity,token_type='Bearer',expires_in=3600,scope=scope))
            if request.url.path.endswith('openid-configuration'):
                return httpx.Response(200,json=dict(issuer=cg.AUTH,jwks_uri=cg.AUTH+'/.well-known/jwks.json'))
            if request.url.path.endswith('jwks.json'):return httpx.Response(200,json={'keys':[jwk]})
            if request.url.path=='/v1/models':return httpx.Response(200,json={'models':[dict(slug='test-model',visibility='list'),dict(slug='hidden',visibility='hidden')]})
            if request.url.path=='/v1/responses':return httpx.Response(200,text=stream or '')
            raise AssertionError('Unexpected endpoint')
        real=httpx.Client
        return requests,patch.object(cg,'client',side_effect=lambda:real(transport=httpx.MockTransport(respond))),real,respond

    async def authorized(self,scope='openid chatgpt.tokens.use.direct'):
        url=await self.begin();connection=self.app.state.chatgpt_connection;self.nonce=connection.pending['nonce']
        requests,mock,_,_=self.provider(scope)
        query=dict(state=connection.pending['state'],code='test-code',client_id='oaiapp_test')
        with mock:
            async with httpx.AsyncClient(trust_env=False) as http:
                response=await http.get(parse_qs(urlsplit(url).query)["redirect_uri"][0],params=query)
                self.assertEqual(response.status_code,200,response.text)
        return connection,requests,url

    async def test_callback_verifies_identity_saves_private_tokens_and_models(self):
        connection,requests,url=await self.authorized()
        authorization=parse_qs(urlsplit(url).query)
        self.assertEqual(authorization['client_id'],['dynamic_agent_client'])
        self.assertEqual(authorization['code_challenge_method'],['S256'])
        token=parse_qs(requests[0].content.decode())
        self.assertEqual(token['client_id'],['oaiapp_test'])
        self.assertEqual(token['redirect_uri'],authorization['redirect_uri'])
        self.assertEqual(connection.path.stat().st_mode&0o777,0o600)
        status=(await self.client.get('/api/v1/chatgpt/status')).json()
        self.assertTrue(status['sharing']);self.assertNotIn('private-access',json.dumps(status))
        _,mock,_,_=self.provider()
        with mock:
            result=await self.client.post('/api/v1/settings/models',json={'qa_provider':'chatgpt','offline_mode':False})
        self.assertEqual(result.json(),{'models':['test-model']})
        self.assertTrue(self.app.state.offline_mode)

    async def test_wrong_state_and_nonce_never_save_credentials(self):
        await self.begin();connection=self.app.state.chatgpt_connection;self.nonce=connection.pending['nonce']
        with self.assertRaises(ValueError):connection.complete(dict(state='wrong',code='x',client_id='oaiapp_test'))
        requests,mock,_,_=self.provider(nonce='wrong-nonce')
        with mock,self.assertRaises(ValueError):connection.complete(dict(state=connection.pending['state'],code='x',client_id='oaiapp_test'))
        self.assertFalse(connection.status()['connected'])

    async def test_missing_plan_permission_and_offline_block_inference(self):
        connection,_,_=await self.authorized(scope='openid')
        self.app.state.offline_mode=False
        with self.assertRaises(ValueError):connection.token()
        self.assertFalse(connection.status()['sharing'])
        self.app.state.offline_mode=True
        with self.assertRaises(ValueError):connection.token()

    async def test_expired_session_rejects_callback(self):
        await self.begin();connection=self.app.state.chatgpt_connection
        query=dict(state=connection.pending['state'],code='x',client_id='oaiapp_test')
        await self.client.post('/api/v1/auth/logout')
        with self.assertRaises(ValueError):connection.complete(query)
        self.assertFalse(connection.status()['connected'])

    async def test_refresh_is_serialized_and_disconnect_clears_credentials(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        record=connection._read();record['expires_at']=0;connection._write(record)
        requests,mock,_,_=self.provider()
        with mock,ThreadPoolExecutor(2) as pool:
            tokens=list(pool.map(lambda _:connection.token(),range(2)))
        self.assertEqual(tokens,['private-access']*2)
        self.assertEqual(len(requests),1)
        self.app.state.offline_mode=True
        result=connection.disconnect()
        self.assertFalse(result['revoked']);self.assertFalse(connection.status()['connected'])
        self.assertNotIn('private-',connection.path.read_text())

    async def test_responses_stream_requires_completion_and_uses_contract(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        stream='data: '+json.dumps(dict(type='response.completed',response=dict(status='completed',model='actual-model',output=[dict(content=[dict(type='output_text',text='{"answer":"ok"}')])])) )+'\n\n'
        requests,_,real,respond=self.provider(stream=stream)
        with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)):
            raw,model=connection.infer('test-model','Return JSON',[dict(type='input_text',text='A test')])
        self.assertEqual(json.loads(raw),{'answer':'ok'});self.assertEqual(model,'actual-model')
        body=json.loads(requests[-1].content)
        self.assertFalse(body['store']);self.assertTrue(body['stream']);self.assertNotIn('temperature',body)
        requests,_,real,respond=self.provider(stream='data: {"type":"response.output_text.delta","delta":"{}"}\n\n')
        with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)),self.assertRaises(ValueError):
            connection.infer('test-model','Return JSON','test')

    async def test_plan_stream_uses_completed_items_when_terminal_output_is_empty(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        item=lambda text:dict(type='message',role='assistant',status='completed',content=[dict(type='output_text',text=text)])
        events=[dict(type='response.output_item.done',output_index=0,item=dict(type='reasoning',content=[],summary=[])),
            dict(type='response.output_text.delta',output_index=1,delta='must not duplicate deltas'),
            dict(type='response.output_item.done',output_index=2,item=item('42}')),
            dict(type='response.output_item.done',output_index=1,item=item('{"result":')),
            dict(type='response.completed',response=dict(status='completed',model='account-model',output=[]))]
        stream=''.join('data: '+json.dumps(event)+'\n\n' for event in events)
        _,_,real,respond=self.provider(stream=stream)
        with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)):
            raw,model=connection.infer('test-model','Return JSON','public arithmetic fixture')
        self.assertEqual(json.loads(raw),{'result':42});self.assertEqual(model,'account-model')

    async def test_terminal_output_does_not_duplicate_streamed_completed_items(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        item=dict(type='message',status='completed',content=[dict(type='output_text',text='{"result":42}')])
        events=[dict(type='response.output_item.done',output_index=0,item=item),
            dict(type='response.completed',response=dict(status='completed',output=[item]))]
        _,_,real,respond=self.provider(stream=''.join('data: '+json.dumps(event)+'\n\n' for event in events))
        with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)):
            raw,_=connection.infer('test-model','Return JSON','public arithmetic fixture')
        self.assertEqual(json.loads(raw),{'result':42})

    async def test_streamed_items_do_not_publish_failed_incomplete_or_interrupted_answers(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        item=dict(type='response.output_item.done',output_index=0,item=dict(type='message',status='completed',content=[dict(type='output_text',text='{"result":42}')]))
        for terminal in (None,'response.failed','response.incomplete','error'):
            with self.subTest(terminal=terminal):
                events=[item]+([dict(type=terminal)] if terminal else [])
                _,_,real,respond=self.provider(stream=''.join('data: '+json.dumps(event)+'\n\n' for event in events))
                with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)),self.assertRaises(ValueError):
                    connection.infer('test-model','Return JSON','public arithmetic fixture')

    async def test_empty_partial_or_refused_completed_output_is_rejected(self):
        connection,_,_=await self.authorized();self.app.state.offline_mode=False
        terminal=dict(type='response.completed',response=dict(status='completed',output=[]))
        for prefix in ([],[dict(type='response.output_text.delta',delta='partial')],
                [dict(type='response.output_item.done',output_index=0,item=dict(status='completed',content=[dict(type='refusal',refusal='Cannot answer')]))],
                [dict(type='response.output_item.done',output_index=0,item=dict(status='incomplete',content=[dict(type='output_text',text='partial')]))]):
            with self.subTest(prefix=prefix):
                _,_,real,respond=self.provider(stream=''.join('data: '+json.dumps(event)+'\n\n' for event in [*prefix,terminal]))
                with patch.object(cg.httpx,'Client',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(respond),**kwargs)),self.assertRaises(ValueError):
                    connection.infer('test-model','Return JSON','public arithmetic fixture')
