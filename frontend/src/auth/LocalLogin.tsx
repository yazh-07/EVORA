import { useEffect, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { LocalUser } from '../api/client';

export function authMessage(error: unknown): string {
  return error instanceof ApiHttpError && error.apiError ? error.apiError.message : 'Could not connect to the local service. Check that EVORA is running and try again.';
}
export function LocalLogin() {
  const client = useApiClient();
  const [mode, setMode] = useState<'loading'|'setup'|'login'|'recover'|'error'>('loading');
  const [username, setUsername] = useState(''), [display, setDisplay] = useState('');
  const [password, setPassword] = useState(''), [confirm, setConfirm] = useState(''), [code, setCode] = useState('');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [recovery, setRecovery] = useState<{ code: string; user?: LocalUser }>();
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    setMode('loading'); setMessage('');
    void client.authRequest('get','/api/v1/auth/status',{signal:request.signal}).then(async status => {
      if(request.signal.aborted) return;
      if(status.setup_required) {setMode('setup');return;}
      try {
        const session = await client.authRequest('get','/api/v1/auth/me',{signal:request.signal});
        if(!request.signal.aborted) client.activateUser(session.user, false);
      } catch(error) {
        if(request.signal.aborted)return;
        if(error instanceof ApiHttpError && error.status===401)setMode('login');
        else throw error;
      }
    }).catch(error => {if(!request.signal.aborted){setMode('error');setMessage(authMessage(error));}});
    return()=>request.abort();
  },[client,retry]);
  const submit = async () => {
    if(busy) return;
    if(mode!=='login' && password!==confirm){setMessage('The passwords do not match.');return;}
    setBusy(true);setMessage('');
    try {
      if(mode==='setup') {
        const result=await client.authRequest('post','/api/v1/auth/setup',{body:{username,password,display_name:display}});
        setRecovery({code:result.recovery_code,user:result.user});
      } else if(mode==='recover') {
        const result=await client.authRequest('post','/api/v1/auth/recover',{body:{username,recovery_code:code,new_password:password}});
        setRecovery({code:result.recovery_code});
      } else {
        const result=await client.authRequest('post','/api/v1/auth/login',{body:{username,password}});
        if(result.recovery_code) setRecovery({code:result.recovery_code,user:result.user});
        else client.activateUser(result.user);
      }
      setPassword('');setConfirm('');setCode('');
    } catch(error){setMessage(authMessage(error));}finally{setBusy(false);}
  };
  return <section className="panel session-panel local-login" aria-labelledby="session-heading">
    <h1 id="session-heading">{recovery?'Save your recovery code':mode==='setup'?'Create account':mode==='recover'?'Reset password':'Sign in to EVORA'}</h1>
    {mode==='loading' && <p role="status">Checking local accounts…</p>}
    {mode==='error' && <button type="button" onClick={()=>setRetry(value=>value+1)}>Retry connection</button>}
    {recovery ? <div className="recovery-code"><p>Save this code outside EVORA. It restores access and is shown only once. Previous recovery codes no longer work.</p><pre tabIndex={0}>{recovery.code}</pre><button className="button-primary" type="button" onClick={()=>{const user=recovery.user;setRecovery(undefined);if(user)client.activateUser(user);else {setMode('login');setMessage('Password reset. Sign in with your new password.');}}}>I saved the recovery code</button></div> : ['setup','login','recover'].includes(mode) && <>
      <form onSubmit={event=>{event.preventDefault();void submit();}}>
        <fieldset disabled={busy}>
          <label htmlFor="login-username">Username</label><input id="login-username" required autoComplete="username" maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" value={username} onChange={event=>setUsername(event.target.value)} />
          {mode==='setup' && <><label htmlFor="login-name">Your name</label><input id="login-name" required maxLength={120} autoComplete="name" value={display} onChange={event=>setDisplay(event.target.value)} /></>}
          {mode==='recover' && <><label htmlFor="recovery-code">Recovery code</label><input id="recovery-code" type="password" autoComplete="off" required value={code} onChange={event=>setCode(event.target.value)} /></>}
          <label htmlFor="login-password">{mode==='recover'?'New password':'Password'}</label><input id="login-password" required type="password" minLength={mode==='login'?1:12} maxLength={256} placeholder={mode==='login' ? undefined : 'At least 12 characters'} autoComplete={mode==='login'?'current-password':'new-password'} value={password} onChange={event=>setPassword(event.target.value)} />
          {mode!=='login' && <><label htmlFor="login-confirm">Confirm password</label><input id="login-confirm" type="password" autoComplete="new-password" required value={confirm} onChange={event=>setConfirm(event.target.value)} /></>}
          <button className="button-primary" type="submit">{busy?'Please wait…':mode==='setup'?'Create administrator':mode==='recover'?'Reset password':'Sign in'}</button>
        </fieldset>
      </form>
      {mode!=='setup' && <button type="button" disabled={busy} onClick={()=>{setMode(mode==='recover'?'login':'recover');setMessage('');setPassword('');setConfirm('');}}>{mode==='recover'?'Back to sign in':'Forgot password?'}</button>}
    </>}
    {message && <p role="alert">{message}</p>}

  </section>;
}
