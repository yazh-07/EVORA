"""Real OAuth state/PKCE, RSA JWT validation and loopback callback; OpenAI protocol doubles."""
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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

    def provider(self,scope='openid chatgpt.tokens.use.direct',nonce=None,stream=None,claims=None):
        requests=[];connection=self.app.state.chatgpt_connection
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));jwk.update(kid='test-key')
        def respond(request):
            requests.append(request)
            if request.url.path.endswith('/oauth/token'):
                body=parse_qs(request.content.decode())
                payload=dict(sub='test-subject',iss=cg.AUTH,aud='oaiapp_test',iat=int(time.time()),exp=int(time.time())+3600,
                    nonce=nonce or self.nonce,email='tester@example.test')
                payload.update(claims or {})
                identity=jwt.encode(payload,key,algorithm='RS256',headers={'kid':'test-key'})
                return httpx.Response(200,json=dict(access_token='private-access',refresh_token='private-refresh',id_token=identity,token_type='Bearer',expires_in=3600,scope=scope))
            if request.url.path.endswith('openid-configuration'):
                return httpx.Response(200,json=dict(issuer=cg.AUTH,jwks_uri=cg.AUTH+'/.well-known/jwks.json'))
            if request.url.path.endswith('jwks.json'):return httpx.Response(200,json={'keys':[jwk]})
            if request.url.path=='/v1/models':return httpx.Response(200,json={'models':[dict(slug='test-model',visibility='list'),dict(slug='hidden',visibility='hidden')]})
            if request.url.path=='/v1/responses':return httpx.Response(200,text=stream or '')
            raise AssertionError('Unexpected endpoint')
        real=httpx.Client
        return requests,patch.object(cg,'client',side_effect=lambda:real(transport=httpx.MockTransport(respond))),real,respond

    async def test_callback_returns_safe_exchange_failure_reason(self):
        url=await self.begin();connection=self.app.state.chatgpt_connection
        real=httpx.Client
        transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'error':'invalid_grant','error_description':'private-secret'}))
        with patch.object(cg,'client',side_effect=lambda:real(transport=transport)):
            async with httpx.AsyncClient(trust_env=False) as browser:
                response=await browser.get(parse_qs(urlsplit(url).query)['redirect_uri'][0],params={
                    'state':connection.pending['state'],'code':'private-code','client_id':'oaiapp_test'})
        self.assertEqual(response.status_code,400)
        self.assertIn('token exchange failed (HTTP 400; invalid_grant)',response.text)
        self.assertNotIn('private-secret',response.text)
        self.assertNotIn('private-code',response.text)
        self.assertEqual(connection.status()['error'],response.text)

    async def authorized(self,scope='openid chatgpt.tokens.use.direct',claims=None):
        url=await self.begin();connection=self.app.state.chatgpt_connection;self.nonce=connection.pending['nonce']
        requests,mock,_,_=self.provider(scope,claims=claims)
        query=dict(state=connection.pending['state'],code='test-code',client_id='oaiapp_test')
        with mock:
            async with httpx.AsyncClient(trust_env=False) as http:
                response=await http.get(parse_qs(urlsplit(url).query)["redirect_uri"][0],params=query)
                self.assertEqual(response.status_code,200,response.text)
        return connection,requests,url

    async def test_callback_accepts_small_clock_drift_in_issued_and_not_before_times(self):
        now=int(time.time())
        connection,_,_=await self.authorized(claims=dict(iat=now+30,nbf=now+30))
        self.assertTrue(connection.status()['connected'])

    async def test_callback_accepts_expiry_within_clock_tolerance(self):
        now=int(time.time())
        connection,_,_=await self.authorized(claims=dict(iat=now-3600,exp=now-30))
        self.assertTrue(connection.status()['connected'])

    async def test_callback_rejects_invalid_identity_and_preserves_saved_credentials(self):
        connection,_,_=await self.authorized()
        saved=connection._read()
        now=int(time.time())
        cases=[
            (dict(iat=now+120),'not valid yet'),
            (dict(nbf=now+120),'not valid yet'),
            (dict(iat=now-3600,exp=now-120),'has expired'),
            (dict(iat=now+120,nonce='wrong-nonce'),'identity validation failed'),
            (dict(iat=now+120,aud='wrong-client'),'identity validation failed'),
            (dict(iat=now+120,iss='https://example.invalid'),'identity validation failed'),
        ]
        for claims,message in cases:
            with self.subTest(claims=claims):
                result=await self.client.post('/api/v1/chatgpt/connect',json={'offline_mode':False})
                self.assertEqual(result.status_code,200,result.text)
                self.nonce=connection.pending['nonce']
                _,mock,_,_=self.provider(claims=claims)
                with mock:
                    async with httpx.AsyncClient(trust_env=False) as browser:
                        response=await browser.get(parse_qs(urlsplit(result.json()['authorization_url']).query)['redirect_uri'][0],
                            params=dict(state=connection.pending['state'],code='private-code',client_id='oaiapp_test'))
                self.assertEqual(response.status_code,400)
                self.assertIn(message,response.text)
                self.assertNotIn('private-code',response.text)
                self.assertNotIn('private-access',response.text)
                self.assertEqual(connection._read(),saved)
                self.assertFalse(connection.status()['pending'])

    async def test_callback_verifies_identity_saves_private_tokens_and_models(self):
        connection,requests,url=await self.authorized()
        authorization=parse_qs(urlsplit(url).query)
        self.assertEqual(authorization['client_id'],['dynamic_agent_client'])
        self.assertEqual(authorization['code_challenge_method'],['S256'])
        token=parse_qs(requests[0].content.decode())
        self.assertEqual(token['client_id'],['oaiapp_test'])
        self.assertEqual(token['redirect_uri'],authorization['redirect_uri'])
        if os.name != 'nt':self.assertEqual(connection.path.stat().st_mode&0o777,0o600)
        else:assert_windows_private(self,connection.path)
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

    async def test_restarting_sign_in_preserves_host_and_can_reread_its_own_file(self):
        await self.begin()
        connection=self.app.state.chatgpt_connection
        host=connection._read()['host_id']
        response=await self.client.post('/api/v1/chatgpt/connect',json={'offline_mode':False})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(connection._read()['host_id'],host)
        self.assertTrue(connection.status()['pending'])
        self.assertEqual(connection.status()['error'],'')

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


def assert_windows_private(test,path):
    from backend.windows_credentials import security_descriptor,current_user_sid
    sddl=security_descriptor(path)
    test.assertTrue(sddl.startswith('D:P'),'credential ACL inheritance must be disabled')
    entries=[entry.split(';') for entry in re.findall(r'\(([^)]+)\)',sddl)]
    user=current_user_sid()
    # Windows renders the RID-500 Administrator SID using its SDDL alias.
    # This is the same account, not an extra allowed principal.
    user_alias='LA' if re.fullmatch(r'S-1-5-21-\d+-\d+-\d+-500',user) else user
    test.assertEqual({entry[5] for entry in entries},{user_alias,'SY'})
    test.assertEqual(len(entries),2)
    for entry in entries:
        test.assertEqual(entry[0],'A')
        test.assertEqual(entry[2],'FA')


class CredentialFilesystemTests(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(TemporaryDirectory(prefix='evora-credentials-')))
        self.connection=cg.Connection(SimpleNamespace(),root/'workstation Ω.sqlite3')

    @unittest.skipUnless(os.name=='nt','Native Windows ACL regression')
    def test_windows_round_trip_and_atomic_replacement_use_private_acls(self):
        connection=self.connection
        for number in range(2):
            record={'host_id':'unchanged-host','test_sequence':number}
            connection._write(record)
            self.assertEqual(connection._read(),record)
            assert_windows_private(self,connection.directory)
            assert_windows_private(self,connection.path)
        self.assertEqual(list(connection.directory.glob('*.tmp')),[])

    @unittest.skipUnless(os.name=='nt','Native Windows legacy credential regression')
    def test_windows_repairs_legacy_acl_without_resetting_credentials(self):
        from backend.windows_credentials import set_dacl
        connection=self.connection
        record={'host_id':'preserved-host','access_token':'synthetic-test-only'}
        connection._write(record)
        set_dacl(connection.path,'D:P(A;;FA;;;WD)')
        self.assertNotEqual(connection.path.stat().st_mode&0o077,0,'Windows mode bits do not describe its DACL')
        self.assertEqual(connection._read(),record)
        assert_windows_private(self,connection.path)

    @unittest.skipIf(os.name=='nt','Unix permission regression')
    def test_unix_group_or_world_readable_credentials_remain_rejected(self):
        connection=self.connection;connection._write({'host_id':'private-host'})
        os.chmod(connection.path,0o644)
        with self.assertRaisesRegex(ValueError,'must be private'):connection._read()

class CallbackDiagnosticTests(unittest.TestCase):
    def test_status_code_is_safe_and_provider_descriptions_are_not_exposed(self):
        request=httpx.Request('POST',cg.TOKEN)
        response=httpx.Response(400,json={'error':'invalid_grant','error_description':'private-secret'},request=request)
        error=httpx.HTTPStatusError('private-secret',request=request,response=response)
        message=cg.callback_error(error,'token exchange')
        self.assertIn('HTTP 400; invalid_grant',message)
        self.assertNotIn('private-secret',message)
    def test_tls_stays_verified_and_clock_errors_are_actionable(self):
        import ssl
        context=cg.tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertIn('not valid yet',cg.callback_error(jwt.ImmatureSignatureError('private'),'identity validation'))
        self.assertNotIn('Sync',cg.callback_error(jwt.ImmatureSignatureError('private'),'identity validation'))
        self.assertNotIn('private',cg.callback_error(ValueError('private'),'credential storage'))


class IdentityTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)

    def identity(self,**claims):
        now=int(time.time())
        payload=dict(sub='private-subject',iss=cg.AUTH,aud='oaiapp_test',iat=now,exp=now+3600,
            nonce='private-nonce',email='private@example.test')
        payload.update(claims)
        return jwt.encode(payload,self.key,algorithm='RS256')

    def validate(self,token,date=None,received_at=None,key=None):
        response=httpx.Response(200,headers={'Date':date} if date is not None else {})
        return cg.validate_identity(token,key or self.key.public_key(),'oaiapp_test',
            dict(nonce='private-nonce',subject=None),response,received_at or time.time())

    def test_verified_time_failures_name_the_claim_and_response_clock_offset(self):
        now=int(time.time())
        for claim,value in [('iat',now+7200),('nbf',now+7200),('exp',now-7200)]:
            with self.subTest(claim=claim):
                token=self.identity(**{claim:value})
                with self.assertRaises(cg.IdentityTimeError) as failure:
                    self.validate(token,formatdate(now,usegmt=True),now+4)
                message=cg.callback_error(failure.exception,'identity validation')
                self.assertIn(claim,message)
                self.assertIn('device/OpenAI response offset +4s',message)
                self.assertIn('ago' if claim=='exp' else 'ahead',message)
                for private in [token,'private-subject','private-nonce','private@example.test']:
                    self.assertNotIn(private,message)
                self.assertNotIn('Sync',message)

    def test_missing_or_malformed_response_time_does_not_hide_the_token_failure(self):
        for date in [None,'private-malformed-date','Wed, 01 Jan 2025 00:00:00']:
            with self.subTest(date=date):
                with self.assertRaises(cg.IdentityTimeError) as failure:
                    self.validate(self.identity(iat=int(time.time())+7200),date)
                message=str(failure.exception)
                self.assertIn('iat',message)
                self.assertNotIn('offset',message)
                self.assertNotIn('private',message)

    def test_response_date_cannot_override_expiration_or_not_before(self):
        now=int(time.time())
        for claims,date in [
            (dict(iat=now-10800,exp=now-7200),now-7201),
            (dict(iat=now+7200,nbf=now+7200),now+7201),
        ]:
            with self.subTest(claims=claims):
                with self.assertRaises(cg.IdentityTimeError):
                    self.validate(self.identity(**claims),formatdate(date,usegmt=True))

    def test_bad_signature_never_becomes_a_verified_timing_diagnostic(self):
        wrong_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        with self.assertRaises(jwt.InvalidSignatureError):
            self.validate(self.identity(iat=int(time.time())+7200),key=wrong_key.public_key())
