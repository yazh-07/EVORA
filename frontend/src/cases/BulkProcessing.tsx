import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import { useSettings } from '../settings/settings';
import { useActivity } from './ActivityCenter';
import type { BulkState } from './bulkProcessingController';

type Settings = components['schemas']['Settings'];
export function BulkProcessing({ caseId, caseTitle }: { caseId: string; caseTitle?: string }) {
  const client = useApiClient(), preferences = useSettings();
  const activity = useActivity();
  const controller = useMemo(() => activity.getBatch(caseId, caseTitle), [activity, caseId, caseTitle]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const [open, setOpen] = useState(false), [vision, setVision] = useState(false), [consent, setConsent] = useState(false);
  const [settings, setSettings] = useState<Settings>();
  const [message, setMessage] = useState(''), [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!open) return;
    const request = new AbortController(); setSettings(undefined); setConsent(false); setMessage('');
    void client.request('get', '/api/v1/settings', { signal: request.signal }).then(value => {
      if (!request.signal.aborted) setSettings(value);
    }).catch(() => { if (!request.signal.aborted) setMessage('Could not load vision settings. Retry, or leave image descriptions off to use basic processing.'); });
    return () => request.abort();
  }, [client, open, refresh, preferences.qa_provider, preferences.qa_model, preferences.qa_url, preferences.vision_model, preferences.vision_use_qa_model, preferences.openai_base_url, preferences.offline_mode]);
  const busy = state.status === 'running';
  const model = settings?.vision_use_qa_model ? settings.qa_model : settings?.vision_model;
  const hosted = settings?.qa_provider !== 'ollama';
  const endpoint = settings?.qa_provider === 'chatgpt' ? 'https://api.openai.com/v1' : hosted ? settings?.openai_base_url : settings?.qa_url;
  const authorized = !hosted || (settings?.qa_provider === 'chatgpt' ? settings.has_chatgpt_connection : settings?.has_openai_key);
  const visionReady = !!settings && !!model && !!endpoint && !!authorized && (!hosted || (!settings.offline_mode && consent));
  return <section className="panel bulk-processing" aria-label="Process all evidence">
    <button type="button" className="button-primary" aria-expanded={open} onClick={() => setOpen(value => !value)}>{busy ? 'View batch progress' : 'Process all'}</button>
    {open && <>
      <h3>Process all case evidence</h3>
      <p>Includes every page of this case, regardless of search filters. Completed files are skipped; existing runs are monitored. Files uploaded after the batch starts are included next time.</p>
      <label><input type="checkbox" checked={vision} disabled={busy} onChange={event => { setVision(event.target.checked); setConsent(false); }} />Include image descriptions, OCR and video scene analysis</label>
      {!vision && <p className="scope-note">Images and videos receive basic local detection only. Descriptions and OCR require the option above. Standalone audio uses the individual transcription workflow.</p>}
      {vision && <>
        <p>Image model: <strong>{model || 'Not configured'}</strong> · Destination: <strong>{endpoint || 'Not configured'}</strong></p>
        <p>Videos use frames sampled every 5 seconds, up to 12 frames per file. Speech transcription is off. Each frame uses a model request. Images and sampled frames require verification against the originals.</p>
        {!visionReady && <p>Configure an image-capable model and connect its provider in Settings. For an external provider, turn off Offline mode and confirm below.</p>}
        {hosted && <label><input type="checkbox" checked={consent} disabled={busy || !settings || !model || !endpoint} onChange={event => setConsent(event.target.checked)} />Send normalized copies of all pending images and sampled video frames in this case to {endpoint || 'the configured provider'} using {model || 'the selected model'}. Provider charges and usage limits may apply.</label>}
        {message && <p role="alert">{message}</p>}
        <button type="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh vision settings</button>
      </>}
      <div className="evidence-toolbar">
        <button type="button" disabled={busy || (vision && !visionReady)} onClick={() => {
          void controller.submit(vision && settings && model && endpoint ? { vision: { provider: settings.qa_provider, model, endpoint, consent } } : {});
        }}>{busy ? 'Processing…' : state.status === 'idle' ? 'Start batch' : 'Check remaining files'}</button>
        {busy && <button type="button" onClick={controller.stop}>Stop queue</button>}
      </div>
      <BulkProcessingResults state={state} />
      <p className="scope-note">You can switch tabs or cases while this queue runs. Use the header activity icon to check progress or stop the remaining queue. Keep this app window open; server work already started may continue after the queue stops. After processing, run case analysis to include the new outputs.</p>
    </>}
  </section>;
}

export function BulkProcessingResults({ state }: { state: BulkState }) {
  const settled = state.items.filter(item => ['completed', 'failed', 'skipped', 'unknown'].includes(item.status)).length;
  const completed = state.items.filter(item => item.status === 'completed').length;
  const failed = state.items.filter(item => item.status === 'failed').length;
  const skipped = state.items.filter(item => item.status === 'skipped').length;
  const unknown = state.items.filter(item => item.status === 'unknown').length;
  return <div aria-busy={state.status === 'running'}>
    {state.message && <p role={state.status === 'error' ? 'alert' : 'status'}>{state.message}</p>}
    {!!state.items.length && <>
      <progress value={settled} max={state.items.length} aria-label="Evidence processing progress" />
      <p role="status">{settled} of {state.items.length} checked · {completed} completed · {skipped} skipped · {failed} failed · {unknown} unconfirmed</p>
      <ul>{state.items.map(item => <li key={item.evidence.id}>
        <strong>{item.evidence.filename}</strong> — {item.status}{item.message && <span>: {item.message}</span>}
        {item.run && <details><summary>Run details</summary><p className="identifier">{item.run.id}</p></details>}
      </li>)}</ul>
    </>}
  </div>;
}
