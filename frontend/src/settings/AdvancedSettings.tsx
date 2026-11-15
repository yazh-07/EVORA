import {useEffect,useState} from 'react';
import {useApiClient} from '../api/ApiProvider';
import type {components} from '../api/schema';
type Runtime=components['schemas']['RuntimeSettings'];
export function AdvancedSettings(){
 const client=useApiClient();const [data,setData]=useState<Runtime|null>(null),[error,setError]=useState(''),[saving,setSaving]=useState(false),[saved,setSaved]=useState(false);
 useEffect(()=>{const request=new AbortController();void client.request('get','/api/v1/settings/runtime',{signal:request.signal}).then(setData).catch(()=>{if(!request.signal.aborted)setError('Could not load settings.');});return()=>request.abort();},[client]);
 async function save(){if(!data)return;setSaving(true);setError('');setSaved(false);try{setData(await client.request('put','/api/v1/settings/runtime',{body:{network_available:data.network_available,port:data.port,minimize_to_tray:data.minimize_to_tray}}));setSaved(true);}catch{setError('Could not save settings.');}finally{setSaving(false);}}
 return <form onSubmit={event=>{event.preventDefault();void save();}}><div className="settings-content">
 {error&&<p role="alert">{error}</p>}
 {!data&&!error&&<p role="status">Loading settings…</p>}
 {data&&<fieldset disabled={saving}><legend className="sr-only">Advanced</legend>
 {data.tray_supported&&<label className="settings-toggle"><span>Minimize to tray on close</span><input type="checkbox" role="switch" checked={data.minimize_to_tray} onChange={e=>{setData({...data,minimize_to_tray:e.target.checked});setSaved(false);}}/></label>}
 <label className="settings-toggle"><span>Make available on network</span><input type="checkbox" role="switch" checked={data.network_available} onChange={e=>{setData({...data,network_available:e.target.checked});setSaved(false);}}/></label>
 <label>Port<input type="number" min={1} max={65535} required value={data.port} onChange={e=>{setData({...data,port:Number(e.target.value)});setSaved(false);}}/></label>
 <p className="settings-running-port">Running on port {data.running_port}</p>
 {!saved&&data.restart_required&&<p role="status">Restart EVORA to apply.</p>}
 {saved&&<p role="status">{data.restart_required?'Saved. Restart EVORA to apply.':'Saved.'}</p>}
 </fieldset>}
 </div><footer className="settings-actions"><span/><button type="submit" className="settings-save" disabled={!data||saving}>{saving?'Saving…':'Save'}</button></footer></form>;
}
