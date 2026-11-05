import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { LocalUser } from '../api/client';
import { authMessage } from './LocalLogin';

export function PasswordChange({ required = false }: { required?: boolean }) {
  const client=useApiClient();
  const [current,setCurrent]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState('');
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  return <section className={required?'panel session-panel':'password-change'} aria-label="Change password">
    <h2>{required?'Choose your own password':'Change your password'}</h2><p>{required?'Your administrator supplied a temporary password. Replace it before opening your cases.':'Changing your password signs out other sessions for this account.'}</p>
    <form onSubmit={async event=>{event.preventDefault();if(password!==confirm){setMessage('The passwords do not match.');return;}setBusy(true);setMessage('');try{const result=await client.authRequest('post','/api/v1/auth/password',{body:{current_password:current,new_password:password}});client.activateUser(result.user);}catch(error){setMessage(authMessage(error));}finally{setBusy(false);}}}>
      <fieldset disabled={busy}>
        <label htmlFor="current-password">Current password</label><input id="current-password" type="password" autoComplete="current-password" required value={current} onChange={event=>setCurrent(event.target.value)} />
        <label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={256} value={password} onChange={event=>setPassword(event.target.value)} />
        <label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" type="password" autoComplete="new-password" required value={confirm} onChange={event=>setConfirm(event.target.value)} />
        <p className="scope-note">At least 12 characters.</p><button type="submit">{busy?'Changing password…':'Change password'}</button>
      </fieldset>
    </form>{message&&<p role="alert">{message}</p>}
  </section>;
}
export function AccountDialog({onClose}:{onClose:()=>void}) {
  const client=useApiClient(),dialog=useRef<HTMLDialogElement>(null);
  const [users,setUsers]=useState<LocalUser[]>([]),[cases,setCases]=useState<{id:string;title:string}[]>([]);
  const [selectedCase,setSelectedCase]=useState(''),[members,setMembers]=useState<string[]>([]);
  const memberScope=useRef('');
  const [membersLoading,setMembersLoading]=useState(false);
  const [username,setUsername]=useState(''),[name,setName]=useState(''),[password,setPassword]=useState('');
  const [role,setRole]=useState<LocalUser['role']>('investigator');
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false),[revision,setRevision]=useState(0);
  const [resetUser,setResetUser]=useState<LocalUser>(),[resetPassword,setResetPassword]=useState('');
  const [audit,setAudit]=useState<{id:string;action:string;actor_id:string|null;target_id:string|null;created_at:number}[]>([]);
  const isAdmin=client.getUser()?.role==='administrator';
  useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.showModal();return()=>{dialog.current?.close();previous?.focus();};},[]);
  useEffect(()=>{
    if(!isAdmin)return;
    const request=new AbortController();
    void (async()=>{
      const result=await client.request('get','/api/v1/accounts',{signal:request.signal});
      const all:{id:string;title:string}[]=[];
      do{const page=await client.request('get','/api/v1/cases',{query:{limit:100,offset:all.length},signal:request.signal});all.push(...page.items);if(all.length>=page.total||!page.items.length)break;}while(!request.signal.aborted);
      const history=await client.request('get','/api/v1/accounts/audit',{signal:request.signal});
      if(!request.signal.aborted){setUsers(result.items);setCases(all);setAudit(history.items);}
    })().catch(error=>{if(!request.signal.aborted)setMessage(authMessage(error));});
    return()=>request.abort();
  },[client,isAdmin,revision]);
  useEffect(()=>{
    if(memberScope.current!==selectedCase){setMembers([]);memberScope.current=selectedCase;}
    if(!selectedCase)return;setMembersLoading(true);
    const request=new AbortController();
    void client.request('get','/api/v1/cases/{caseId}/members',{path:{caseId:selectedCase},signal:request.signal}).then(result=>{if(!request.signal.aborted){setMembers(result.items.map(user=>user.id));setMembersLoading(false);}}).catch(error=>{if(!request.signal.aborted){setMessage(authMessage(error));setMembersLoading(false);}});
    return()=>request.abort();
  },[client,selectedCase,revision]);
  const update=async(user:LocalUser,body:{role?:LocalUser['role'];disabled?:boolean;new_password?:string})=>{
    setBusy(true);setMessage('');
    try{await client.request('put','/api/v1/accounts/{userId}',{path:{userId:user.id},body});if(user.id===client.getUser()?.id)client.clearToken();else {setRevision(value=>value+1);setMessage('Account updated. Existing sessions for this account were revoked.');setResetUser(undefined);setResetPassword('');}}catch(error){setMessage(authMessage(error));}finally{setBusy(false);}
  };
  return <dialog ref={dialog} className="account-dialog" aria-labelledby="accounts-title" onCancel={event=>{if(busy)event.preventDefault();else onClose();}}>
    <header className="section-heading"><div><span className="section-label">LOCAL WORKSTATION</span><h2 id="accounts-title">{isAdmin?'Accounts and case access':'Your account'}</h2></div><button type="button" disabled={busy} onClick={onClose}>Close accounts</button></header>
    {message&&<p role="status">{message}</p>}
    <PasswordChange />
    {isAdmin&&<>
      <section className="account-section"><h3>Add an investigator or reviewer</h3><p>Share the temporary password directly. The new user must replace it at first sign-in.</p>
        <form onSubmit={async event=>{event.preventDefault();setBusy(true);setMessage('');try{await client.request('post','/api/v1/accounts',{body:{username,display_name:name,password,role}});setUsername('');setName('');setPassword('');setRevision(value=>value+1);setMessage('Local account created. Assign case access below.');}catch(error){setMessage(authMessage(error));}finally{setBusy(false);}}}>
          <fieldset disabled={busy} className="account-grid">
            <label>Username<input required maxLength={64} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" autoComplete="off" value={username} onChange={event=>setUsername(event.target.value)} /></label>
            <label>Name<input required maxLength={120} value={name} onChange={event=>setName(event.target.value)} /></label>
            <label>Role<select aria-label="Role" value={role} onChange={event=>setRole(event.target.value as LocalUser['role'])}><option value="investigator">Investigator</option><option value="reviewer">Read-only reviewer</option><option value="administrator">Administrator</option></select></label>
            <label>Temporary password<input required type="password" minLength={12} maxLength={256} autoComplete="new-password" value={password} onChange={event=>setPassword(event.target.value)} /></label>
            <button type="submit">Create account</button>
          </fieldset>
        </form>
      </section>
      <section className="account-section"><h3>Local accounts</h3><p>Administrators manage every case. Investigators and reviewers need explicit case access.</p>
        <ul className="account-list">{users.map(user=><li key={user.id}><div><strong>{user.display_name}</strong><p>{user.username} · {user.role} · {user.disabled?'disabled':user.must_change_password?'temporary password':'active'}</p></div>
          <label>Role for {user.username}<select aria-label={`Role for ${user.username}`} value={user.role} disabled={busy} onChange={event=>{void update(user,{role:event.target.value as LocalUser['role']});}}><option value="administrator">Administrator</option><option value="investigator">Investigator</option><option value="reviewer">Read-only reviewer</option></select></label>
          <button type="button" disabled={busy} onClick={()=>{void update(user,{disabled:!user.disabled});}}>{user.disabled?'Enable':'Disable'} {user.username}</button>
          <button type="button" disabled={busy} onClick={()=>{setResetUser(user);setResetPassword('');}}>Reset password for {user.username}</button>
        </li>)}</ul>
        {resetUser&&<form onSubmit={event=>{event.preventDefault();void update(resetUser,{new_password:resetPassword});}}><label>New temporary password for {resetUser.username}<input type="password" autoComplete="new-password" minLength={12} maxLength={256} required value={resetPassword} onChange={event=>setResetPassword(event.target.value)} /></label><button type="submit" disabled={busy}>Set temporary password</button><button type="button" onClick={()=>{setResetUser(undefined);setResetPassword('');}}>Cancel reset</button></form>}
      </section>
      <section className="account-section"><h3>Assign case access</h3><label>Case<select aria-label="Case" value={selectedCase} disabled={busy} onChange={event=>setSelectedCase(event.target.value)}><option value="">Choose a case</option>{cases.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
        {selectedCase&&<ul className="membership-list">{users.filter(user=>user.role!=='administrator'&&!user.disabled).map(user=><li key={user.id}><label><input type="checkbox" checked={members.includes(user.id)} disabled={busy || membersLoading} onChange={async event=>{const grant=event.target.checked;const previous=members;setMembers(current=>grant?[...current,user.id]:current.filter(id=>id!==user.id));setBusy(true);setMessage('');try{await client.request('put','/api/v1/cases/{caseId}/members',{path:{caseId:selectedCase},body:{user_id:user.id,grant}});setRevision(value=>value+1);}catch(error){setMembers(previous);setMessage(authMessage(error));}finally{setBusy(false);}}} />{user.display_name} ({user.username})</label></li>)}</ul>}
      </section>
      <details className="account-section"><summary>Account activity · latest 100 events</summary><ol>{audit.map(item=><li key={item.id}>{new Date(item.created_at*1000).toLocaleString()} · {item.action} · {users.find(user=>user.id===item.actor_id)?.username??'Local account'}{item.target_id&&` → ${users.find(user=>user.id===item.target_id)?.username??'account'}`}</li>)}</ol></details>
    </>}
  </dialog>;
}
