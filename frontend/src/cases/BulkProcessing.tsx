import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import { useActivity } from './ActivityCenter';
import { useSettings } from '../settings/settings';
import { readBatchInventory, type BatchInventory, type BulkState } from './bulkProcessingController';

type Settings = components['schemas']['Settings'];
export function BulkProcessing({ caseId, caseTitle, evidenceIds = [], revision, onCompleted, onCount }: { onCount?: (count: number) => void; caseId: string; caseTitle?: string; evidenceIds?: string[]; revision?: unknown; onCompleted?: () => void }) {
  const client = useApiClient(), activity = useActivity(), preferences = useSettings();
  const controller = useMemo(() => activity.getBatch(caseId, caseTitle), [activity, caseId, caseTitle]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const [inventory, setInventory] = useState<BatchInventory>(), [error, setError] = useState(''), [reload, setReload] = useState(0);
  const [reprocess, setReprocess] = useState(false);
  const [vision, setVision] = useState(true), [consent, setConsent] = useState(false), [settings, setSettings] = useState<Settings>();
  const [optionsOpen, setOptionsOpen] = useState(false), [progressOpen, setProgressOpen] = useState(false);
  useEffect(() => {
    const request = new AbortController(); setError('');
    void readBatchInventory(client, caseId, request.signal, vision).then(value => { if (!request.signal.aborted) setInventory(value); }).catch(() => { if (!request.signal.aborted) setError('Could not check pending files.'); });
    return () => request.abort();
  }, [client, caseId, revision, reload, state.status, vision]);
  useEffect(() => {
    const request = new AbortController(); setConsent(false);
    void client.request('get', '/api/v1/settings', { signal: request.signal }).then(value => { if (!request.signal.aborted) { setSettings(value); setVision(value.qa_provider === 'ollama'); } }).catch(() => { if (!request.signal.aborted) setError('Could not load model settings.'); });
    return () => request.abort();
  }, [client, preferences.qa_provider, preferences.qa_model, preferences.vision_model, preferences.vision_use_qa_model, preferences.offline_mode, preferences.has_chatgpt_connection, preferences.has_openai_key, preferences.qa_url, preferences.openai_base_url]);
  const selected = new Set(evidenceIds);
  const scope = inventory?.filter(item => !selected.size || selected.has(item.evidence.id));
  const candidates = scope?.filter(item => item.status === 'pending' || (reprocess && item.status === 'ready') || (vision && ['image', 'video'].includes(item.evidence.kind) && item.status !== 'running' && !item.visionComplete));
  const hasMedia = !!candidates?.some(item => ['image', 'video'].includes(item.evidence.kind));
  const retryHasMedia = state.items.some(item => item.status === 'failed' && ['image', 'video'].includes(item.evidence.kind));
  useEffect(() => { onCount?.(candidates?.length ?? 0); }, [candidates?.length, onCount]);
  const busy = state.status === 'running';
  const settled = state.items.filter(item => ['completed', 'failed', 'skipped', 'unknown'].includes(item.status)).length;
  const failed = state.items.filter(item => item.status === 'failed');
  const unknown = state.items.filter(item => item.status === 'unknown').length;
  const ready = state.items.filter(item => item.status === 'completed' || item.status === 'skipped').length;
  const model = settings?.vision_use_qa_model ? settings.qa_model : settings?.vision_model;
  const hosted = settings?.qa_provider !== 'ollama';
  const endpoint = settings?.qa_provider === 'chatgpt' ? 'https://api.openai.com/v1' : hosted ? settings?.openai_base_url : settings?.qa_url;
  const destination = settings?.qa_provider === 'chatgpt' ? 'ChatGPT' : (() => { try { return new URL(endpoint ?? '').host; } catch { return 'the selected provider'; } })();
  const visionReady = !!settings && !!model && !!endpoint && (!hosted || (!settings.offline_mode && consent && (settings.qa_provider === 'chatgpt' ? settings.has_chatgpt_connection : settings.has_openai_key)));
  const submit = async (ids: string[], forceReprocess = false) => {
    const includesMedia = inventory?.some(item => ids.includes(item.evidence.id) && ['image', 'video'].includes(item.evidence.kind));
    if (vision && includesMedia && !visionReady) return;
    setOptionsOpen(false);
    await controller.submit({ evidenceIds: ids, reprocess: reprocess || forceReprocess, ...(vision && settings && model && endpoint ? { vision: { provider: settings.qa_provider, model, endpoint, consent } } : {}) });
    setConsent(false); if (hosted) setVision(false); onCompleted?.();
  };
  return <div className="batch-toolbar" aria-label="Evidence processing">
    <div className="batch-primary-row"><button type="button" className="button-primary batch-process" aria-label={busy ? 'Processing evidence' : selected.size ? 'Process selected files' : 'Process all files'} disabled={busy || !candidates?.length || (vision && hasMedia && !visionReady)} onClick={() => { if (candidates) void submit(candidates.map(item => item.evidence.id)); }}>{busy ? 'Processing…' : selected.size ? 'Process selected' : 'Process all'}<span aria-hidden="true" className="batch-count">{candidates?.length ?? 0}</span></button>
      {busy && <span className="batch-progress" role="status"><progress value={settled} max={Math.max(1, state.items.length)} aria-label="Evidence processing progress" /><span>{settled}/{state.items.length}</span></span>}
    </div>
    {(scope?.some(item => ['image', 'video'].includes(item.evidence.kind)) || retryHasMedia) && <div className="batch-media-options">
      <label><input type="checkbox" disabled={busy || !settings} checked={vision && (!hosted || consent)} onChange={event => { setVision(event.target.checked); setConsent(event.target.checked && hosted); }} /><span>{hosted ? `Analyze images and video · send to ${destination}` : 'Analyze images and video with Ollama'}</span></label>
      {vision && !model && <span role="status">Choose an image model in Settings.</span>}
    </div>}
    <details className="action-menu batch-options" open={optionsOpen} onToggle={event => setOptionsOpen(event.currentTarget.open)}><summary aria-label="Processing options" title="Processing options">⌄</summary><div className="action-popover">
      {busy ? <button type="button" onClick={controller.stop}>Stop queue</button> : <><label><input type="checkbox" checked={reprocess} onChange={event => setReprocess(event.target.checked)} /> Reprocess completed files</label>
      {!!scope?.filter(item => item.status === 'unavailable').length && <p>{scope.filter(item => item.status === 'unavailable').length} files support storage only.</p>}
      <button type="button" onClick={() => setReload(value => value + 1)}>Check files again</button></>}
      {!!state.items.length && <button type="button" onClick={() => { setProgressOpen(value => !value); setOptionsOpen(false); }}>Processing history</button>}
    </div></details>
    {!busy && state.items.length > 0 && <span className="batch-outcome" role="status">{ready} ready{failed.length > 0 ? ` · ${failed.length} failed` : ''}{unknown ? ` · ${unknown} unconfirmed` : ''}</span>}
    {!busy && failed.length > 0 && <button type="button" className="text-action" disabled={retryHasMedia && (state.visionRequested || vision) && !visionReady} onClick={() => { void submit(failed.map(item => item.evidence.id), true); }}>Retry failed</button>}
    {error && <span role="alert">{error}<button type="button" onClick={() => setReload(value => value + 1)}>Retry</button></span>}
    {progressOpen && <section className="batch-history"><div className="section-heading"><h3>Processing history</h3><button type="button" onClick={() => setProgressOpen(false)} aria-label="Close processing history">×</button></div><BulkProcessingResults state={state} /></section>}
  </div>;
}

export function BulkProcessingResults({ state }: { state: BulkState }) {
  const settled = state.items.filter(item => ['completed', 'failed', 'skipped', 'unknown'].includes(item.status)).length;
  const failed = state.items.filter(item => item.status === 'failed').length;
  return <div aria-busy={state.status === 'running'}>
    {state.status === 'error' || state.status === 'stopped' ? <p role="alert">{state.message}</p> : null}
    {!!state.items.length && <><progress value={settled} max={state.items.length} aria-label="Evidence processing progress" /><p role="status">{settled} of {state.items.length} checked · {failed} failed</p><ul>{state.items.map(item => <li key={item.evidence.id}><strong>{item.evidence.filename}</strong><span>{item.status}</span>{(item.status === 'failed' || item.status === 'unknown') && <p>{item.message}</p>}</li>)}</ul></>}
  </div>;
}
