import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import { useSettings } from '../settings/settings';
import { ProcessingStatus } from './ProcessingStatus';
import { validRun } from './processingController';
import type { ProcessingRun } from './processingController';
import type { Evidence } from './evidenceStore';

type Observation = components['schemas']['Observation'];
type Settings = components['schemas']['Settings'];
export function ImageUnderstanding({ item, observations, onCompleted }: {
  item: Evidence; observations: Observation[]; onCompleted?: (id: string) => void;
}) {
  const client = useApiClient(), preferences = useSettings();
  const [settings, setSettings] = useState<Settings>();
  const [refresh, setRefresh] = useState(0), [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false), [message, setMessage] = useState('');
  const [run, setRun] = useState<ProcessingRun>();
  const [runStatus, setRunStatus] = useState<ProcessingRun['status']>();
  const pending = useRef<AbortController | undefined>(undefined);
  const finished = useRef<string | undefined>(undefined);
  const allowed = client.getUser()?.role !== 'reviewer';
  useEffect(() => {
    const request = new AbortController();
    setSettings(undefined); setConsent(false); setMessage('');
    void client.request('get', '/api/v1/settings', { signal: request.signal }).then(value => {
      if (!request.signal.aborted) setSettings(value);
    }).catch(() => { if (!request.signal.aborted) setMessage('Could not load vision settings. Refresh settings to retry.'); });
    return () => request.abort();
  }, [client, refresh, preferences.vision_model, preferences.vision_use_qa_model, preferences.qa_model, preferences.qa_provider, preferences.qa_url, preferences.openai_base_url, preferences.offline_mode]);
  useEffect(() => () => pending.current?.abort(), []);
  const complete = useCallback((id: string) => {
    if (finished.current === id) return;
    finished.current = id; setRunStatus('completed'); onCompleted?.(id);
  }, [onCompleted]);
  const updateStatus = useCallback((value: ProcessingRun) => { if (value.id === run?.id) setRunStatus(value.status); }, [run?.id]);
  const records = useMemo(() => new Map(observations.filter(record => record.kind.startsWith('image.')).map(record => [record.kind, record])), [observations]);
  const description = records.get('image.description'), text = records.get('image.ocr');
  const provenance = records.get('image.provenance');
  let model = '';
  if (provenance) { try { const parsed = JSON.parse(provenance.raw_value); if (typeof parsed.actual_model === 'string') model = parsed.actual_model; } catch { /* Raw provenance remains inspectable below. */ } }
  const hosted = settings !== undefined && settings.qa_provider !== 'ollama';
  const destination = settings?.qa_provider === 'chatgpt' ? 'https://api.openai.com/v1' : settings?.openai_base_url;
  const authorized = settings?.qa_provider === 'chatgpt' ? settings.has_chatgpt_connection : settings?.has_openai_key;
  const selectedModel = settings?.vision_use_qa_model ? settings.qa_model : settings?.vision_model;
  const status = runStatus ?? run?.status;
  const busy = submitting || status === 'queued' || status === 'running';
  const start = async () => {
    if (!settings || !selectedModel || busy || !allowed || (hosted && !consent)) return;
    setSubmitting(true); setMessage('');
    const request = pending.current = new AbortController();
    try {
      const result = await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/image-analysis', {
        path: { caseId: item.case_id, evidenceId: item.id }, header: { 'Idempotency-Key': crypto.randomUUID() }, signal: request.signal,
        body: { confirm_external_processing: consent, expected_provider: settings.qa_provider,
          expected_model: selectedModel, expected_endpoint: hosted ? destination! : settings.qa_url },
      });
      if (!request.signal.aborted) {
        if (!validRun(result, item.case_id, item.id)) throw Error('Invalid image analysis run');
        finished.current = undefined; setRunStatus(result.status); setRun(result);
      }
    } catch (error) {
      if (!request.signal.aborted) setMessage(error instanceof ApiHttpError && error.apiError ? error.apiError.message : 'Could not confirm image analysis. Refresh the source before trying again.');
    } finally { if (!request.signal.aborted) setSubmitting(false); }
  };
  return <section className="image-understanding" aria-label="Image description and OCR">
    <h3>Image description and visible text</h3>
    <p>Describe the scene and transcribe text using a vision-capable model. Both outputs require verification against the original.</p>
    {description && <article><h4>Scene description <span className="kind-badge">Model-generated</span></h4><p className="image-derived-text">{description.raw_value}</p></article>}
    {text && <article><h4>Visible text <span className="kind-badge">Model-assisted OCR</span></h4>{text.raw_value ? <pre tabIndex={0}>{text.raw_value}</pre> : <p>The model returned no readable text. This does not establish that the image contains no text.</p>}</article>}
    {records.get('image.limitations') && <p className="scope-note">Limitations: {records.get('image.limitations')!.raw_value}</p>}
    {provenance && <details className="technical-details"><summary>Image-processing provenance{model ? ` · ${model}` : ''}</summary><p className="identifier">Processing run: {provenance.processing_run_id}</p><pre>{provenance.raw_value}</pre></details>}
    {!description && !text && <p className="scope-note">No description or text extraction in the displayed processing output.</p>}
    {settings && <div className="image-model-destination"><p>Provider: <strong>{settings.qa_provider==='chatgpt'?'ChatGPT plan':hosted ? 'Hosted / OpenAI-compatible' : 'Local Ollama'}</strong> · Vision model: <strong>{selectedModel || 'Not configured'}</strong></p>
      {!selectedModel && <p>Ask an administrator to set a vision-capable model in Settings. A text-only chat model cannot inspect image pixels.</p>}
      {allowed && hosted && <label><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />Send a normalized copy of this image to {destination} using {selectedModel || 'the configured vision model'}. Provider usage charges may apply.</label>}
      {allowed && <button type="button" disabled={busy || !selectedModel || (hosted && (!consent || !authorized))} onClick={() => { void start(); }}>{busy ? 'Analyzing image…' : 'Describe image and extract text'}</button>}
      {hosted && !authorized && <p>Connect the selected provider in Settings before using it.</p>}
    </div>}
    {!allowed && <p className="scope-note">Read-only access. An investigator can generate a new description.</p>}
    {status === 'failed' && <p role="alert">Image understanding failed. Check that the selected model supports images and that its service and credentials are available. Earlier completed results remain available.</p>}
    {message && <p role="alert">{message}</p>}
    <button type="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh vision settings</button>
    {run && <><ProcessingStatus run={run} onCompleted={complete} onStatusChange={updateStatus} />{status !== 'failed' && <p className="scope-note">A successful run saves a new processing output. Run case analysis again to include its description and text. Historical citation views may continue to show their referenced output.</p>}</>}
  </section>;
}
