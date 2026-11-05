import { useEffect, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { AccountDialog } from './AccountDialog';
import { authMessage } from './LocalLogin';

export function SessionControls() {
  const client=useApiClient();
  const user=client.getUser();
  const [open,setOpen]=useState(false),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{
    if(!user)return;
    let timer:ReturnType<typeof setTimeout>,lastTouch=0;
    const lock=()=>{void client.authRequest('post','/api/v1/auth/logout',{}).catch(()=>{}).finally(()=>client.clearToken());};
    const active=()=>{
      clearTimeout(timer);timer=setTimeout(lock,30*60*1000);
      if(Date.now()-lastTouch>60000){lastTouch=Date.now();void client.authRequest('post','/api/v1/auth/activity',{}).catch(()=>client.clearToken());}
    };
    const channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('evora-local-session'):null;
    if(channel)channel.onmessage=()=>client.clearToken();
    active();window.addEventListener('pointerdown',active);window.addEventListener('keydown',active);
    return()=>{clearTimeout(timer);channel?.close();window.removeEventListener('pointerdown',active);window.removeEventListener('keydown',active);};
  },[client,user]);
  if(!user)return <span className="session-pill">Local workstation</span>;
  return <div className="session-status"><span className="session-pill session-active">{user.display_name} · {user.role}</span><button type="button" onClick={()=>setOpen(true)}>Account</button><button type="button" disabled={busy} onClick={async()=>{setBusy(true);try{await client.authRequest('post','/api/v1/auth/logout',{});client.clearToken();}catch(error){setMessage(authMessage(error));}finally{setBusy(false);}}}>Sign out</button>{message&&<span role="alert">{message}</span>}{open&&<AccountDialog onClose={()=>setOpen(false)} />}</div>;
}
