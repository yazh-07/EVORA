"""ChatGPT plan OAuth: separate from local accounts; fixed official endpoints only."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit, parse_qs
from uuid import uuid4

import httpx
import jwt
from filelock import FileLock, Timeout as FileLockTimeout
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from backend.auth import authenticated_actor
from backend.errors import AccessError

AUTH='https://auth.openai.com'
BASE='https://api.openai.com/v1'
TOKEN=AUTH+'/api/accounts/oauth/token'
SCOPE='openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
router=APIRouter(prefix='/api/v1/chatgpt')


def client():
    return httpx.Client(timeout=httpx.Timeout(20,connect=5),trust_env=False,follow_redirects=False)


class Connection:
    def __init__(self,app,path):
        self.app=app;self.directory=Path(str(path)+'.chatgpt');self.path=self.directory/'credentials.json'
        self.lock=threading.RLock();self.pending=None;self.listener=None;self.error=''

    def _read(self):
        if not self.path.exists():return {}
        if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
            raise ValueError('Credential file must be private')
        record=json.loads(self.path.read_text())
        if not isinstance(record,dict):raise ValueError('Invalid credential record')
        return record

    def _write(self,record):
        if self.directory.is_symlink():raise ValueError('Credential directory must not be a symlink')
        self.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
        os.chmod(self.directory,0o700)
        temporary=self.directory/(secrets.token_hex(16)+'.tmp')
        try:
            with os.fdopen(os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:
                json.dump(record,stream);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:temporary.unlink(missing_ok=True)

    def status(self):
        with self.lock:
            try:
                record=self._read();sharing=bool(record.get('access_token') and 'chatgpt.tokens.use.direct' in record.get('scopes',[]))
                return dict(connected=bool(record.get('access_token')),sharing=sharing,email=record.get('email',''),
                    pending=self.pending is not None,error=self.error)
            except (OSError,ValueError):
                return dict(connected=False,sharing=False,email='',pending=False,error='Could not read the protected ChatGPT connection file.')

    def binding(self):
        with self.lock:
            record=self._read()
            if not record.get('subject'):raise ValueError('Connect ChatGPT first')
            return hashlib.sha256((record['client_id']+'\0'+record['subject']).encode()).hexdigest()

    def cancel(self):
        with self.lock:
            self.pending=None
            listener=self.listener;self.listener=None
        if listener:
            listener.shutdown();listener.server_close()

    def close_listener(self,listener):
        with self.lock:
            if self.listener is not listener:return
            self.listener=None
        listener.shutdown();listener.server_close()

    def start(self,actor,session,new_account=False):
        self.cancel()
        with self.lock:
            record=self._read()
            if not record.get('host_id'):
                record['host_id']='urn:uuid:'+str(uuid4());self._write(record)
            registration=record.get('pending_registration') if new_account or not record.get('client_id') else record.get('client_id')
            pending=dict(state=secrets.token_urlsafe(32),nonce=secrets.token_urlsafe(32),verifier=secrets.token_urlsafe(48),
                actor=actor,session=hashlib.sha256(session.encode()).hexdigest(),expires=time.time()+300,
                client_id=registration,subject=record.get('subject') if registration==record.get('client_id') and not new_account else None)
            connection=self
            class Callback(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    valid=False
                    try:
                        url=urlsplit(self.path)
                        if url.path!='/auth/callback':raise ValueError('Callback path')
                        query=parse_qs(url.query,keep_blank_values=True)
                        if any(len(values)!=1 for values in query.values()):raise ValueError('Duplicate callback parameters')
                        connection.complete({key:values[0] for key,values in query.items()});valid=True
                    except Exception:
                        with connection.lock:
                            connection.error='ChatGPT sign-in did not complete. Check plan permissions or retry.'
                    self.send_response(200 if valid else 400)
                    self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store')
                    self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'")
                    self.end_headers();self.wfile.write(('Connected. Close this window and return to EVORA.' if valid else 'Sign-in could not complete. Return to EVORA and retry.').encode())
                    if connection.pending is None:
                        threading.Thread(target=connection.close_listener,args=(self.server,),daemon=True).start()
            listener=ThreadingHTTPServer(('127.0.0.1',0),Callback);listener.daemon_threads=True
            pending['redirect_uri']=f'http://127.0.0.1:{listener.server_port}/auth/callback'
            self.pending=pending;self.listener=listener;self.error=''
            threading.Thread(target=listener.serve_forever,daemon=True).start()
            def expire():
                with self.lock:active=self.pending is pending
                if active:self.cancel()
            timer=threading.Timer(300,expire);timer.daemon=True;timer.start()
            query=dict(client_id=pending['client_id'] or 'dynamic_agent_client',ext_agent_host_id=record['host_id'],
                response_type='code',redirect_uri=pending['redirect_uri'],scope=SCOPE,resource=BASE,state=pending['state'],nonce=pending['nonce'],
                code_challenge_method='S256',code_challenge=base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).decode().rstrip('='))
            if pending['subject'] and record.get('id_token'):query['id_token_hint']=record['id_token']
            elif not pending['client_id']:query['agent_name_hint']='EVORA'
            return AUTH+'/api/accounts/authorize?'+urlencode(query)

    def complete(self,query):
        with self.lock:
            pending=self.pending
            if not pending or pending['expires']<time.time() or not secrets.compare_digest(query.get('state',''),pending['state']):
                raise ValueError('Invalid callback state')
            self.pending=None
            if query.get('error'):raise ValueError('Authorization denied')
            issued=query.get('client_id') or pending['client_id']
            if not issued or issued=='dynamic_agent_client' or (pending['client_id'] and pending['client_id']!=issued):raise ValueError('Invalid issued client')
            with self.app.state.database.connect() as c:
                session=c.execute('SELECT s.* FROM local_sessions s JOIN local_users u ON u.id=s.user_id WHERE s.digest=? AND u.id=? AND u.role=\'administrator\' AND u.disabled=0',
                    (pending['session'],pending['actor'])).fetchone()
                from backend.local_auth import IDLE_SECONDS,ABSOLUTE_SECONDS
                if not session or time.time()-session['last_seen']>IDLE_SECONDS or time.time()-session['created_at']>ABSOLUTE_SECONDS:
                    raise ValueError('Local session expired')
            if not pending['client_id']:
                record=self._read();record['pending_registration']=issued;self._write(record)
            with client() as http:
                response=http.post(TOKEN,data=dict(grant_type='authorization_code',client_id=issued,code=query['code'],code_verifier=pending['verifier'],redirect_uri=pending['redirect_uri'],resource=BASE))
                response.raise_for_status();body=response.json()
                discovery=http.get(AUTH+'/.well-known/openid-configuration');discovery.raise_for_status();metadata=discovery.json()
                if metadata['issuer']!=AUTH or metadata['jwks_uri']!=AUTH+'/.well-known/jwks.json':raise ValueError('Unexpected identity issuer')
                keys=http.get(metadata['jwks_uri']);keys.raise_for_status()
            header=jwt.get_unverified_header(body['id_token'])
            if header.get('alg')!='RS256':raise ValueError('Unsupported identity signature')
            key=next(key for key in keys.json()['keys'] if key.get('kid')==header.get('kid') and key.get('kty')=='RSA')
            identity=jwt.decode(body['id_token'],jwt.PyJWK.from_dict(key).key,algorithms=['RS256'],issuer=AUTH,audience=issued,
                options={'require':['exp','iat','sub','iss','aud','nonce']})
            if not secrets.compare_digest(identity['nonce'],pending['nonce']) or (pending['subject'] and identity['sub']!=pending['subject']):raise ValueError('Account mismatch')
            record=self._read()
            if (record.get('client_id'),record.get('subject'))!=(issued,identity['sub']):record={'host_id':record['host_id']}
            record.update(client_id=issued,subject=identity['sub'],email=identity.get('email',''),id_token=body['id_token'])
            record.pop('pending_registration',None)
            self._tokens(record,body);self._write(record);self.error=''

    def _tokens(self,record,body):
        if not isinstance(body.get('access_token'),str) or not body['access_token'] or body.get('token_type','').lower()!='bearer':raise ValueError('Invalid token response')
        if type(body.get('expires_in')) is not int or body['expires_in']<=0:raise ValueError('Invalid token expiry')
        record.update(access_token=body['access_token'],expires_at=time.time()+min(3600,int(body['expires_in'])),scopes=body.get('scope',' '.join(record.get('scopes',[]))).split())
        if body.get('refresh_token'):record['refresh_token']=body['refresh_token']

    def token(self,allow_offline=False):
        try:return self._token(allow_offline)
        except (KeyError,OSError,FileLockTimeout):raise ValueError('Could not renew the protected ChatGPT connection; reconnect and retry.') from None

    def _token(self,allow_offline=False):
        if self.app.state.offline_mode and not allow_offline:raise ValueError('Offline mode blocks ChatGPT')
        with self.lock:
            self.directory.mkdir(parents=True,mode=0o700,exist_ok=True)
            with FileLock(str(self.directory/'refresh.lock'),timeout=25):
                record=self._read()
                if 'chatgpt.tokens.use.direct' not in record.get('scopes',[]) or not record.get('access_token'):
                    raise ValueError('Connect ChatGPT and authorize plan usage first')
                if record['expires_at']<time.time()+30:
                    with client() as http:
                        result=http.post(TOKEN,data=dict(grant_type='refresh_token',client_id=record['client_id'],refresh_token=record['refresh_token'],resource=BASE))
                        result.raise_for_status();self._tokens(record,result.json());self._write(record)
                    if 'chatgpt.tokens.use.direct' not in record['scopes']:raise ValueError('Plan usage permission was removed')
                return record['access_token']

    def disconnect(self):
        self.cancel()
        with self.lock:
            record=self._read();revoked=False
            if record.get('refresh_token') and not self.app.state.offline_mode:
                try:
                    with client() as http:
                        discovery=http.get(AUTH+'/.well-known/openid-configuration');discovery.raise_for_status()
                        endpoint=discovery.json()['revocation_endpoint']
                        if urlsplit(endpoint).scheme!='https' or urlsplit(endpoint).netloc!='auth.openai.com':raise ValueError('Invalid revocation endpoint')
                        result=http.post(endpoint,data=dict(token=record['refresh_token'],client_id=record['client_id'],token_type_hint='refresh_token'))
                        result.raise_for_status();revoked=True
                except Exception:pass
            self._write({key:value for key,value in record.items() if key in ('host_id','client_id','subject','email')})
            self.error='';return dict(disconnected=True,revoked=revoked)

    def models(self,allow_offline=False):
        with client() as http:
            result=http.get(BASE+'/models',headers={'Authorization':'Bearer '+self.token(allow_offline)});result.raise_for_status()
        rows=result.json()['models']
        if not isinstance(rows,list) or any(not isinstance(item,dict) or not isinstance(item.get('slug'),str) or not item['slug'].strip() for item in rows):
            raise ValueError('Invalid model catalog')
        rows=[item for item in rows if item.get('visibility')=='list']
        return dict(models=[item['slug'] for item in rows])

    def infer(self,model,instructions,content,timeout=180,connection_id=None):
        with self.lock:
            if connection_id is not None and connection_id!=self.binding():raise ValueError('ChatGPT account changed')
            token=self.token()
        start=time.monotonic();size=0;completion=None;streamed_output={}
        with httpx.Client(timeout=httpx.Timeout(timeout,connect=5),trust_env=False,follow_redirects=False) as http:
            with http.stream('POST',BASE+'/responses',headers={'Authorization':'Bearer '+token},json=dict(model=model,instructions=instructions+'\nReturn only valid JSON.',
                input=[dict(role='user',content=content)],store=False,stream=True)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    size+=len(line)
                    if size>2*1024*1024 or time.monotonic()-start>timeout:raise ValueError('Response limit exceeded')
                    if not line.startswith('data:'):continue
                    raw=line[5:].strip()
                    if raw=='[DONE]':break
                    event=json.loads(raw);kind=event.get('type')
                    if kind in ('error','response.failed','response.incomplete'):raise ValueError('ChatGPT request failed or was incomplete')
                    if kind=='response.output_item.done':
                        index,item=event.get('output_index'),event.get('item')
                        if type(index) is not int or index<0 or not isinstance(item,dict) or item.get('status') not in (None,'completed'):
                            raise ValueError('Invalid completed output item')
                        if index in streamed_output and streamed_output[index]!=item:raise ValueError('Conflicting completed output item')
                        streamed_output[index]=item
                    if kind=='response.completed':
                        completion=event['response']
                        break
        if not completion or completion.get('status')!='completed':raise ValueError('Interrupted ChatGPT response')
        # Plan streams can finish with output: []; completed items were sent earlier.
        # Never publish deltas or completed items without the terminal success event.
        output=completion.get('output',[])
        if not isinstance(output,list):raise ValueError('Invalid completed output')
        if not output:output=[streamed_output[index] for index in sorted(streamed_output)]
        parts=[]
        for item in output:
            for part in item.get('content',[]):
                if part.get('type')=='refusal':raise ValueError('Refused response')
                if part.get('type')=='output_text':parts.append(part['text'])
        text=''.join(parts)
        if not text.strip():raise ValueError('ChatGPT response contained no answer text')
        return text,completion.get('model',model)


def administrator(request:Request):
    from backend.local_auth import admin
    actor=authenticated_actor(request)
    if not request.app.state.local_auth:raise AccessError(400,'LOCAL_ACCOUNT_REQUIRED','Use a local administrator account to connect ChatGPT.')
    admin(actor);return actor


class Start(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    offline_mode:bool=True
    new_account:bool=False


@router.get('/status')
def status(request:Request,actor=Depends(administrator)):
    return request.app.state.chatgpt_connection.status()


@router.post('/connect')
def connect(body:Start,request:Request,actor=Depends(administrator)):
    if body.offline_mode:raise AccessError(400,'OFFLINE_MODE','Turn off Offline mode before connecting ChatGPT.')
    from backend.local_auth import COOKIE
    try:return dict(authorization_url=request.app.state.chatgpt_connection.start(actor.id,request.cookies.get(COOKIE,''),body.new_account))
    except (OSError,ValueError):raise AccessError(400,'CHATGPT_CONNECT_FAILED','Could not start the protected ChatGPT connection. Check local file permissions.') from None


@router.post('/disconnect')
def disconnect(request:Request,actor=Depends(administrator)):
    return request.app.state.chatgpt_connection.disconnect()
