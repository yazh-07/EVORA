import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';

export function ChatGPTConnection({ onSharing }: { onSharing: (sharing: boolean) => void }) {
  const client=useApiClient(), callback=useRef(onSharing);callback.current=onSharing;
  const [status,setStatus]=useState<components['schemas']['ChatGPTStatus']>();
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{
    const controller=new AbortController();
    const refresh=()=>{void client.request('get','/api/v1/chatgpt/status',{signal:controller.signal}).then(value=>{
      if(!controller.signal.aborted){setStatus(value);callback.current(value.sharing);}
    }).catch(()=>{if(!controller.signal.aborted)setError('Could not read the ChatGPT connection. Sign in as a local administrator and retry.');});};
    refresh();const timer=status?.pending?window.setInterval(refresh,1500):undefined;
    return()=>{controller.abort();if(timer!==undefined)window.clearInterval(timer);};
  },[client,status?.pending]);
  async function connect(newAccount=false){
    const popup=window.open('about:blank','_blank');if(popup)popup.opener=null;
    if(!popup){setError('Allow pop-ups for EVORA, then try again.');return;}
    setBusy(true);setError('');
    try{
      const value=await client.request('post','/api/v1/chatgpt/connect',{body:{offline_mode:false,new_account:newAccount}});
      const url=new URL(value.authorization_url);
      if(url.origin!=='https://auth.openai.com')throw Error('Invalid sign-in destination');
      popup.location.href=url.href;
      setStatus(current=>({...current,connected:current?.connected??false,sharing:current?.sharing??false,email:current?.email??'',error:'',pending:true}));
    }catch(cause){popup.close();setError(cause instanceof ApiHttpError&&cause.apiError?cause.apiError.message:'Could not start ChatGPT sign-in.');}
    finally{setBusy(false);}
  }
  async function disconnect(){
    setBusy(true);setError('');
    try{
      const value=await client.request('post','/api/v1/chatgpt/disconnect',{});
      setStatus(undefined);callback.current(false);
      if(!value.revoked)setError('Disconnected locally. Review this app in ChatGPT Settings to revoke any remaining remote access.');
    }catch{setError('Could not disconnect. Retry or manage access in ChatGPT Settings.');}
    finally{setBusy(false);}
  }
  return <section aria-label="ChatGPT model connection">
    {status?.connected&&<p role="status">Connected{status.email?` as ${status.email}`:''}. {status.sharing?'Model access authorized.':'Model access not authorized. Reconnect.'}</p>}
    {status?.pending&&<p role="status">Finish sign-in in the browser window, then return here.</p>}
    <button type="button" disabled={busy||status?.pending} onClick={()=>void connect()}>Continue with ChatGPT</button>
    {status?.email&&<button type="button" disabled={busy||status.pending} onClick={()=>void connect(true)}>Use another ChatGPT account</button>}
    {(status?.connected||status?.pending)&&<button type="button" disabled={busy} onClick={()=>void disconnect()}>Disconnect ChatGPT</button>}
    {(error||status?.error)&&<p role="alert">{error||status?.error}</p>}
    <p><a href="https://chatgpt.com/settings/usage" target="_blank" rel="noreferrer">Manage ChatGPT usage and app access</a></p>
  </section>;
}
