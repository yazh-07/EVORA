import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { ApiClient } from '../api/client';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import './Updates.css';
import { useActivity } from '../cases/ActivityCenter';

type Status = components['schemas']['UpdateStatus'];
type State = { data: Status | null; error: string; loading: boolean };
const initial = (): State => ({ data: null, error: '', loading: false });
const activeStates = ['checking', 'downloading', 'installing'];
const actions = { check: '/api/v1/updates/check', download: '/api/v1/updates/download', cancel: '/api/v1/updates/cancel', install: '/api/v1/updates/install' } as const;

export function createUpdatesController(client: ApiClient, pollMs = 1000) {
  let state = initial(), disposed = false, generation = client.getSessionVersion();
  let pending: AbortController | undefined, timer: ReturnType<typeof setTimeout> | undefined;
  let interval: ReturnType<typeof setInterval> | undefined, unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const active = () => !disposed && client.hasToken() && generation === client.getSessionVersion();
  const publish = (next: State) => { if (!disposed) { state = next; listeners.forEach(listener => listener()); } };
  function accept(data: Status) {
    if (!active()) return;
    if (typeof data.current_version !== 'string' || !Number.isSafeInteger(data.downloaded_bytes) || !Number.isSafeInteger(data.total_bytes) ||
        data.downloaded_bytes < 0 || data.total_bytes < 0 || data.downloaded_bytes > data.total_bytes ||
        !['idle', 'checking', 'available', 'up_to_date', 'downloading', 'ready', 'installing', 'error'].includes(data.status) ||
        !/^https:\/\/github\.com\/yazh-07\/EVORA\/releases\/(latest|tag\/v?\d+\.\d+\.\d+)$/.test(data.release_url) ||
        (data.download_url !== null && !/^https:\/\/github\.com\/yazh-07\/EVORA\/releases\/download\/v?\d+\.\d+\.\d+\/(EVORA-Setup-Windows-x64\.exe|evora-linux-x86_64\.tar\.gz)$/.test(data.download_url))) throw Error('Invalid update status');
    publish({ data, loading: false, error: '' });
    clearTimeout(timer);
    if (activeStates.includes(data.status)) timer = setTimeout(() => { void refresh(); }, pollMs);
  }
  function fail(error: unknown) {
    if (active()) publish({ ...state, loading: false, error: error instanceof ApiHttpError && error.apiError ? error.apiError.message : 'Could not read update status. Retry the check.' });
  }
  async function refresh(automatic = false) {
    if (!active()) return;
    pending?.abort(); const request = pending = new AbortController();
    try {
      const data = await client.request('get', '/api/v1/updates', { signal: request.signal });
      if (request.signal.aborted) return; accept(data);
      if (automatic && data.automatic && client.getUser()?.role === 'administrator') await action('check', true);
    } catch (error) { if (!request.signal.aborted) fail(error); }
  }
  async function action(which: keyof typeof actions, automatic = false) {
    if (!active()) return;
    pending?.abort(); clearTimeout(timer); const request = pending = new AbortController();
    publish({ ...state, loading: true, error: '' });
    try {
      const data = which === 'check' ? await client.request('post', actions.check, { body: { automatic }, signal: request.signal })
        : await client.request('post', actions[which], { signal: request.signal });
      if (!request.signal.aborted) accept(data);
    } catch (error) { if (!request.signal.aborted) fail(error); }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    refresh, action,
    start() {
      disposed = false; generation = client.getSessionVersion(); void refresh(true);
      unsubscribe = client.subscribeSession(() => {
        generation = client.getSessionVersion(); pending?.abort(); clearTimeout(timer); publish(initial()); void refresh(true);
      });
      interval = setInterval(() => { if (active() && state.data?.automatic && client.getUser()?.role === 'administrator') void action('check', true); }, 6 * 60 * 60 * 1000);
    },
    dispose() { disposed = true; pending?.abort(); clearTimeout(timer); clearInterval(interval); unsubscribe?.(); listeners.clear(); },
  };
}
const Context = createContext<ReturnType<typeof createUpdatesController> | null>(null);
export function UpdatesProvider({ children }: { children: ReactNode }) {
  const client = useApiClient(), controller = useMemo(() => createUpdatesController(client), [client]);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <Context.Provider value={controller}>{children}</Context.Provider>;
}
export function useUpdates() {
  const controller = useContext(Context);
  if (!controller) throw Error('UpdatesProvider is required');
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  return { controller, state };
}
export function UpdatesPanel() {
  const client = useApiClient(), { controller, state } = useUpdates();
  const [saving, setSaving] = useState(false), [error, setError] = useState('');
  const [automaticDraft, setAutomaticDraft] = useState<boolean | null>(null);
  const activity = useActivity();
  const batches = useSyncExternalStore(activity.subscribe, activity.getSnapshot, activity.getSnapshot);
  const processing = batches.some(entry => entry.state.status === 'running');
  const data = state.data, admin = !client.isLocalAuth() || client.getUser()?.role === 'administrator';
  const busy = state.loading || !!data && activeStates.includes(data.status);
  async function automatic(value: boolean) {
    setSaving(true); setAutomaticDraft(value); setError('');
    try { await client.request('put', '/api/v1/settings', { body: { automatic_update_checks: value } }); await controller.refresh(); }
    catch { setError('Could not save the update preference.'); }
    finally { setSaving(false); setAutomaticDraft(null); }
  }
  return <section className="updates-panel" aria-label="Application updates">
    <div className="updates-version"><img src="/brand/icon.png" alt="" width="40" height="40" /><div><h3>EVORA</h3><p>{data ? `Version ${data.current_version}` : 'Loading version…'}</p></div></div>
    {data?.status === 'up_to_date' && <p role="status">Up to date</p>}
    {data?.available && !['ready', 'installing'].includes(data.status) && <p role="status">Version {data.latest_version} available</p>}
    {data?.status === 'checking' && <p role="status">Checking for updates…</p>}
    {data?.status === 'downloading' && <div className="updates-progress"><progress aria-label="Update download" value={data.downloaded_bytes} max={data.total_bytes || 1} /><output>{data.total_bytes ? Math.floor(100 * data.downloaded_bytes / data.total_bytes) : 0}%</output></div>}
    {data?.status === 'ready' && <p role="status">Version {data.latest_version} ready to install</p>}
    {data?.status === 'installing' && <p role="status">Finish setup in the installer.</p>}
    {(error || state.error || data?.error) && <p role="alert">{error || state.error || data?.error}</p>}
    {admin && <div className="updates-actions">
      <button type="button" disabled={busy} onClick={() => void controller.action('check')}>Check for updates</button>
      {data?.available && data.can_install && data.download_url && ['available', 'error'].includes(data.status) && <button type="button" className="button-primary" disabled={state.loading} onClick={() => void controller.action('download')}>{data.downloaded_bytes > 0 ? 'Resume download' : 'Download update'}</button>}
      {data?.status === 'downloading' && <button type="button" disabled={state.loading} onClick={() => void controller.action('cancel')}>Cancel download</button>}
      {data?.status === 'ready' && <button type="button" className="button-primary" disabled={state.loading || processing} title={processing ? 'Wait for processing to finish' : undefined} onClick={() => void controller.action('install')}>Install update</button>}
      {data?.available && !data.can_install && <a className="updates-release" href={data.download_url ?? data.release_url} target="_blank" rel="noreferrer">Download update ↗</a>}
    </div>}
    {data && admin && <label className="settings-toggle"><span>Check automatically</span><input type="checkbox" role="switch" checked={automaticDraft ?? data.automatic} disabled={saving} onChange={event => void automatic(event.target.checked)} /></label>}
  </section>;
}
