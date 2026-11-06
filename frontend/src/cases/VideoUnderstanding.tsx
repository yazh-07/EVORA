import { useCallback, useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import { useSettings } from '../settings/settings';
import { ProcessingStatus } from './ProcessingStatus';
import { validRun, type ProcessingRun } from './processingController';
import { parseMediaLocator } from './mediaLocators';
import type { Evidence } from './evidenceStore';

type Observation = components['schemas']['Observation'];
export function VideoUnderstanding({ item, observations, onCompleted, onSeek }: {
  item: Evidence; observations: Observation[]; onCompleted?: (id: string) => void; onSeek: (seconds: number) => void;
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
  }, [client, refresh, preferences.qa_provider, preferences.qa_model, preferences.vision_model, preferences.vision_use_qa_model, preferences.openai_base_url, preferences.qa_url, preferences.offline_mode]);
  useEffect(() => () => request.current?.abort(), []);
  const complete = useCallback((id: string) => {
    if (finished.current === id) return;
    finished.current = id;setStatus('completed');onCompleted?.(id);
  }, [onCompleted]);
  const updateStatus = useCallback((value: ProcessingRun) => { if (value.id === run?.id) setStatus(value.status); }, [run?.id]);
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
  const scenes = observations.filter(item => item.kind === 'video.scene');
  const tracks = observations.filter(item => item.kind === 'video.track');
  const provenance = observations.find(item => item.kind === 'video.provenance');
  return <section className="image-understanding" aria-label="Video scene analysis">
    <h3>Video scenes, text and speech</h3>
    <p>Inspect sampled frames with an image-capable model. Events between samples can be missed. Results require comparison with the original.</p>
    <p>Image model: <strong>{model || 'Not configured'}</strong></p>
    {!model && <p>Choose an image-capable model in Settings, or fetch one separately for video frames.</p>}
    {allowed && <>
      <label>Frame sampling interval (seconds)<input type="number" min="1" max="60" value={interval} disabled={busy} onChange={event => setInterval(Number(event.target.value))} /></label>
      <label>Maximum frames to describe<input type="number" min="1" max="60" value={maxFrames} disabled={busy} onChange={event => setMaxFrames(Number(event.target.value))} /></label>
      <p>Long clips use evenly spaced frames when the cap is reached. Each selected frame uses one model request.</p>
      <label><input type="checkbox" checked={speech} disabled={busy || !speechReady} onChange={event => setSpeech(event.target.checked)} />Transcribe speech locally</label>
      {!speechReady && <p>Speech requires ffmpeg, ffprobe, the optional faster-whisper package and a downloaded model configured with EVORA_SPEECH_MODEL_PATH.</p>}
      {hosted && <label><input type="checkbox" checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />Send up to {maxFrames} sampled frames to {destination} using {model || 'the configured image model'}. Provider charges may apply. Audio stays local.</label>}
      <button type="button" disabled={busy || !model || !validSampling || (hosted && (!consent || !authorized))} onClick={() => void start()}>{busy ? 'Analyzing video…' : 'Analyze video scenes and text'}</button>
    </>}
    {message && <p role="alert">{message}</p>}
    {status === 'failed' && <p role="alert">Video analysis failed. Check the model, media decoder and speech configuration. Earlier completed results remain available.</p>}
    <button type="button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh video settings</button>
    {run && <ProcessingStatus run={run} onCompleted={complete} onStatusChange={updateStatus} />}
    {scenes.map(scene => {
      const seconds = parseMediaLocator(scene.source_locator).seconds ?? 0;
      const text = observations.find(item => item.kind === 'video.ocr' && item.source_locator === scene.source_locator);
      const limitations = observations.find(item => item.kind === 'video.limitations' && item.source_locator === scene.source_locator);
      return <article key={scene.id}><h4><button type="button" onClick={() => onSeek(seconds)}>At {seconds.toFixed(2)}s</button> <span className="kind-badge">Model-generated</span></h4>
        <p>{scene.raw_value}</p>{text?.raw_value && <><h4>Visible text</h4><pre tabIndex={0}>{text.raw_value}</pre></>}
        {limitations && <p>Limitations: {limitations.raw_value}</p>}</article>;
    })}
    {!!tracks.length && <details><summary>{tracks.length} candidate tracks across sampled detections</summary><p>Geometric box associations within this clip. Tracks can fragment or switch subjects and do not verify identity.</p>{tracks.map(track => <pre key={track.id}>{track.raw_value}</pre>)}</details>}
    {provenance && <details><summary>Video-processing provenance and sampled coverage</summary><pre>{provenance.raw_value}</pre></details>}
    <p>Speech segments appear in the transcript viewer. Run case analysis again to include these new observations.</p>
  </section>;
}
