import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import { useSettings } from '../settings/settings';
import { ProcessingStatus } from './ProcessingStatus';
import { validRun, type ProcessingRun } from './processingController';
import type { Evidence } from './evidenceStore';

export function VideoUnderstanding({ item, onCompleted, onFailed }: {
  item: Evidence; onCompleted?: (id: string) => void; onFailed?: () => void;
}) {
  const client = useApiClient(), preferences = useSettings();
  const [settings, setSettings] = useState<components['schemas']['Settings']>();
  const [speechReady, setSpeechReady] = useState(false);
  const [consent, setConsent] = useState(false), [speech, setSpeech] = useState(false);
  const [interval, setInterval] = useState(5), [maxFrames, setMaxFrames] = useState(12);
  const [message, setMessage] = useState(''), [refresh, setRefresh] = useState(0);
  const [run, setRun] = useState<ProcessingRun>(), [status, setStatus] = useState<ProcessingRun['status']>();
  const [submitting, setSubmitting] = useState(false);
  const request = useRef<AbortController | undefined>(undefined), finished = useRef<string | undefined>(undefined);
  const allowed = client.getUser()?.role !== 'reviewer';
  useEffect(() => {
    const controller = new AbortController();setSettings(undefined);setConsent(false);setSpeechReady(false);setSpeech(false);setMessage('');
    void client.request('get', '/api/v1/settings', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setSettings(value); })
      .catch(() => { if (!controller.signal.aborted) setMessage('Could not load video settings. Refresh to retry.'); });
    void client.request('get', '/api/v1/media-capabilities', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setSpeechReady(value.video_audio_tools && value.local_speech_ready);
    }).catch(() => { /* Visual processing can still run without speech tools. */ });
    return () => controller.abort();
  }, [client, refresh, preferences.qa_provider, preferences.qa_model, preferences.vision_model, preferences.vision_use_qa_model, preferences.openai_base_url, preferences.qa_url, preferences.offline_mode, preferences.has_chatgpt_connection, preferences.has_openai_key]);
  useEffect(() => () => request.current?.abort(), []);
  const complete = useCallback((id: string) => {
    if (finished.current === id) return;
    finished.current = id;setStatus('completed');onCompleted?.(id);
  }, [onCompleted]);
  const updateStatus = useCallback((value: ProcessingRun) => {
    if (value.id !== run?.id) return;
    setStatus(value.status);
    if (value.status === 'failed' && finished.current !== value.id) { finished.current = value.id; onFailed?.(); }
  }, [run?.id, onFailed]);
  const hosted = settings !== undefined && settings.qa_provider !== 'ollama';
  const destination = settings?.qa_provider === 'chatgpt' ? 'https://api.openai.com/v1' : settings?.openai_base_url;
  const authorized = settings?.qa_provider === 'chatgpt' ? settings.has_chatgpt_connection : settings?.has_openai_key;
  const model = settings?.vision_use_qa_model ? settings.qa_model : settings?.vision_model;
  const busy = submitting || status === 'queued' || status === 'running';
  const validSampling = Number.isInteger(interval) && interval >= 1 && interval <= 60 && Number.isInteger(maxFrames) && maxFrames >= 1 && maxFrames <= 60;
  async function start() {
    if (!settings || !model || !allowed || busy || !validSampling || (hosted && (!consent || !authorized))) return;
    const controller = request.current = new AbortController();setSubmitting(true);setMessage('');
    try {
      const value = await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/video-analysis', {
        path: { caseId: item.case_id, evidenceId: item.id }, header: { 'Idempotency-Key': crypto.randomUUID() }, signal: controller.signal,
        body: { expected_provider: settings.qa_provider, expected_model: model, expected_endpoint: hosted ? destination! : settings.qa_url,
          confirm_external_processing: consent, sample_interval_seconds: interval, max_frames: maxFrames, transcribe_speech: speech },
      });
      if (!controller.signal.aborted) {
        if (!validRun(value, item.case_id, item.id)) throw Error('Invalid processing run');
        finished.current = undefined;setRun(value);setStatus(value.status);
      }
    } catch (error) {
      if (!controller.signal.aborted) setMessage(error instanceof ApiHttpError && error.apiError ? error.apiError.message : 'Could not start video analysis. Refresh settings and retry.');
    } finally { if (!controller.signal.aborted) setSubmitting(false); }
  }
  return <section className="image-understanding" aria-label="Video scene analysis">
    <h3>Video analysis</h3>
    <p><strong>{model || 'Choose an image model in Settings.'}</strong></p>
    {allowed && <>
      <details className="media-sampling-options"><summary>Sampling</summary>
      <label>Frame sampling interval (seconds)<input type="number" min="1" max="60" value={interval} disabled={busy} onChange={event => setInterval(Number(event.target.value))} /></label>
      <label>Maximum frames to describe<input type="number" min="1" max="60" value={maxFrames} disabled={busy} onChange={event => setMaxFrames(Number(event.target.value))} /></label>
      <label><input type="checkbox" checked={speech} disabled={busy || !speechReady} onChange={event => setSpeech(event.target.checked)} />Transcribe speech locally</label>
      {!speechReady && <span className="scope-note">Local speech unavailable</span>}
      </details>
      {hosted && <label><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />Send up to {maxFrames} frames to {destination?.replace(/^https?:\/\//, '').replace(/\/v1\/?$/, '')}.</label>}
      <button type="button" disabled={busy || !model || !validSampling || (hosted && (!consent || !authorized))} onClick={() => void start()}>{busy ? 'Analyzing video…' : 'Analyze video'}</button>
    </>}
    {message && <p role="alert">{message}</p>}
    <button type="button" disabled={busy} onClick={() => setRefresh(value => value + 1)} aria-label="Refresh video settings">↻</button>
    {run && <ProcessingStatus run={run} onCompleted={complete} onStatusChange={updateStatus} />}
  </section>;
}
