import { createContext, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createActivityStore } from './activityStore';
import type { ActivityEntry } from './activityStore';

const ActivityContext = createContext<ReturnType<typeof createActivityStore> | null>(null);
export function ActivityProvider({ children }: { children: ReactNode }) {
  const client = useApiClient();
  const store = useMemo(() => createActivityStore(client), [client]);
  useEffect(() => { store.start(); return () => store.dispose(); }, [store]);
  return <ActivityContext.Provider value={store}>{children}</ActivityContext.Provider>;
}
export function useActivity() {
  const store = useContext(ActivityContext);
  if (!store) throw Error('Activity consumers require ActivityProvider.');
  return store;
}

export function ActivityCenter() {
  const store = useActivity();
  const entries = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null), button = useRef<HTMLButtonElement>(null);
  const running = entries.filter(entry => entry.state.status === 'running').length;
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); button.current?.focus(); } };
    document.addEventListener('pointerdown', closeOutside); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', closeOutside); document.removeEventListener('keydown', escape); };
  }, [open]);
  return <div className="activity-center" ref={root}>
    <button ref={button} type="button" className="activity-trigger" aria-label={`Activity${running ? ` (${running} running)` : ''}`} aria-expanded={open} aria-controls="activity-panel" onClick={() => setOpen(value => !value)} title="Processing activity">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" /><path d="M10 21h4M12 2V1" /></svg>
      {running > 0 && <span className="activity-count" aria-hidden="true">{running}</span>}
    </button>
    {open && <section id="activity-panel" className="activity-popover panel" aria-label="Processing activity">
      <div className="section-heading"><h2>Activity</h2><button type="button" aria-label="Close activity" onClick={() => { setOpen(false); button.current?.focus(); }}>×</button></div>
      <p role="status">{running ? `${running} evidence ${running === 1 ? 'batch' : 'batches'} running` : 'No evidence batches running'}</p>
      {!entries.length && <p>Start Process all in a case's Evidence tab. Progress will appear here while you work elsewhere.</p>}
      {entries.map(entry => <ActivityEntryPanel key={entry.caseId} entry={entry} stop={() => store.stop(entry.caseId)} />)}
      <p className="scope-note">This panel tracks Process all batches in this window. Stop queue prevents the remaining files from starting. A server job already accepted may still finish; this does not cancel that job.</p>
    </section>}
  </div>;
}

export function ActivityEntryPanel({ entry, stop }: { entry: ActivityEntry; stop: () => void }) {
  const { state } = entry;
  const current = state.items.find(item => ['checking', 'queued', 'running'].includes(item.status));
  const settled = state.items.filter(item => ['completed', 'failed', 'skipped', 'unknown'].includes(item.status)).length;
  const failed = state.items.filter(item => item.status === 'failed' || item.status === 'unknown').length;
  const waiting = state.items.filter(item => item.status === 'waiting').length;
  return <article className="activity-entry">
    <h3>{entry.title}</h3><p><strong>{state.status === 'running' ? 'Running' : state.status === 'done' ? 'Finished' : state.status === 'stopped' ? 'Queue stopped' : 'Needs attention'}</strong></p>
    {state.status === 'running' && <p>Current: {current ? `${current.evidence.filename} · ${current.status}` : 'Loading evidence…'}</p>}
    {!!state.items.length && <><progress value={settled} max={state.items.length} aria-label={`${entry.title} progress`} /><p>{settled} of {state.items.length} checked · {waiting} waiting · {failed} need attention</p></>}
    {state.status === 'running' && <button type="button" onClick={stop}>Stop queue</button>}
    {state.message && <p className="scope-note">{state.message}</p>}
  </article>;
}
