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
  const [databaseEncrypted, setDatabaseEncrypted] = useState(false);
  useEffect(() => {
    const request = new AbortController();
    setMode('loading'); setMessage('');
    void client.authRequest('get','/api/v1/auth/status',{signal:request.signal}).then(async status => {
      if(request.signal.aborted) return;
      setDatabaseEncrypted(status.database_encrypted ?? false);
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
    <span className="section-label">OFFLINE WORKSTATION ACCESS</span>
    <h2 id="session-heading">{recovery?'Save your recovery code':mode==='setup'?'Set up this workstation':mode==='recover'?'Recover administrator access':'Sign in to EVORA'}</h2>
    {mode==='loading' && <p role="status">Checking local accounts…</p>}
    {mode==='error' && <button type="button" onClick={()=>setRetry(value=>value+1)}>Retry connection</button>}
    {recovery ? <div className="recovery-code"><p>Keep this code somewhere safe outside this workstation. It recovers your password and unlocks the encrypted database without internet access. A replacement code also replaces any older code saved before database encryption. It is shown only once; recovery replaces the previous code.</p><pre tabIndex={0}>{recovery.code}</pre><button className="button-primary" type="button" onClick={()=>{const user=recovery.user;setRecovery(undefined);if(user)client.activateUser(user);else {setMode('login');setMessage('Password reset. Sign in with your new password.');}}}>I saved the recovery code</button></div> : ['setup','login','recover'].includes(mode) && <>
      <p>{mode==='setup'?'Create the first administrator account. Accounts and passwords stay on this workstation.':mode==='recover'?'Use the recovery code created during setup. Other investigators can ask an administrator to reset their password.':'Use the local account created for you on this workstation.'}</p>
      <p className="scope-note">{databaseEncrypted ? 'Your account password also unlocks the encrypted database. There is no separate database password.' : 'The database is encrypted during setup or your next administrator sign-in, using your account password. Original evidence files are stored separately.'}</p>
      <form onSubmit={event=>{event.preventDefault();void submit();}}>
        <fieldset disabled={busy}>
          <label htmlFor="login-username">Username</label><input id="login-username" required autoComplete="username" maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" value={username} onChange={event=>setUsername(event.target.value)} />
          {mode==='setup' && <><label htmlFor="login-name">Your name</label><input id="login-name" required maxLength={120} autoComplete="name" value={display} onChange={event=>setDisplay(event.target.value)} /></>}
          {mode==='recover' && <><label htmlFor="recovery-code">Recovery code</label><input id="recovery-code" type="password" autoComplete="off" required value={code} onChange={event=>setCode(event.target.value)} /></>}
          <label htmlFor="login-password">{mode==='recover'?'New password':'Password'}</label><input id="login-password" required type="password" minLength={mode==='login'?1:12} maxLength={256} autoComplete={mode==='login'?'current-password':'new-password'} value={password} onChange={event=>setPassword(event.target.value)} />
          {mode!=='login' && <><p className="scope-note">Use at least 12 characters. A long, unique passphrase works well.</p><label htmlFor="login-confirm">Confirm password</label><input id="login-confirm" type="password" autoComplete="new-password" required value={confirm} onChange={event=>setConfirm(event.target.value)} /></>}
          <button className="button-primary" type="submit">{busy?'Please wait…':mode==='setup'?'Create administrator':mode==='recover'?'Reset password':'Sign in'}</button>
        </fieldset>
      </form>
      {mode!=='setup' && <button type="button" disabled={busy} onClick={()=>{setMode(mode==='recover'?'login':'recover');setMessage('');setPassword('');setConfirm('');}}>{mode==='recover'?'Back to sign in':'Forgot password?'}</button>}
    </>}
    {message && <p role="alert">{message}</p>}
    <p className="scope-note">Local accounts work without an internet connection.</p>
  </section>;
}
