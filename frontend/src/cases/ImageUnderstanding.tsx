import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import { useSettings } from '../settings/settings';
import { ProcessingStatus } from './ProcessingStatus';
import { validRun } from './processingController';
import type { ProcessingRun } from './processingController';
import type { Evidence } from './evidenceStore';

type Settings = components['schemas']['Settings'];
export function ImageUnderstanding({ item, onCompleted, onFailed }: {
  item: Evidence; onCompleted?: (id: string) => void; onFailed?: () => void;
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
  }, [client, refresh, preferences.vision_model, preferences.vision_use_qa_model, preferences.qa_model, preferences.qa_provider, preferences.qa_url, preferences.openai_base_url, preferences.offline_mode, preferences.has_chatgpt_connection, preferences.has_openai_key]);
  useEffect(() => () => pending.current?.abort(), []);
  const complete = useCallback((id: string) => {
    if (finished.current === id) return;
    finished.current = id; setRunStatus('completed'); onCompleted?.(id);
  }, [onCompleted]);
  const updateStatus = useCallback((value: ProcessingRun) => {
    if (value.id !== run?.id) return;
    setRunStatus(value.status);
    if (value.status === 'failed' && finished.current !== value.id) { finished.current = value.id; onFailed?.(); }
  }, [run?.id, onFailed]);
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
    <h3>Image analysis</h3>
    {settings && <div className="image-model-destination"><p><strong>{selectedModel || 'Choose an image model in Settings.'}</strong></p>
      {allowed && hosted && <label><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />Send this image to {destination?.replace(/^https?:\/\//, '').replace(/\/v1\/?$/, '')}.</label>}
      {allowed && <button type="button" disabled={busy || !selectedModel || (hosted && (!consent || !authorized))} onClick={() => { void start(); }}>{busy ? 'Analyzing image…' : 'Analyze image'}</button>}
      {hosted && !authorized && <p>Connect the selected provider in Settings before using it.</p>}
    </div>}
    {!allowed && <p className="scope-note">Read-only access. An investigator can generate a new description.</p>}
    {message && <p role="alert">{message}</p>}
    <button type="button" disabled={busy} onClick={() => setRefresh(value => value + 1)} aria-label="Refresh image settings">↻</button>
    {run && <><ProcessingStatus run={run} onCompleted={complete} onStatusChange={updateStatus} /></>}
  </section>;
}
