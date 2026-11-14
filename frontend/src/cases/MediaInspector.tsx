import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import type { Evidence } from './evidenceStore';
import { createOriginalDownload } from './downloadController';
import { resolveSourceObservations } from './sourceObservations';
import { detectionStyle, detectionVisible, parseMediaLocator, type SourceFocus } from './mediaLocators';
import './MediaInspector.css';
import { useSettings } from '../settings/settings';

type Observation = components['schemas']['Observation'];

function storedImageSize(image: HTMLImageElement) {
  // The detector uses stored pixels. Browsers report EXIF-oriented naturalWidth/Height,
  // even with image-orientation:none; measure an unscaled, unrotated copy instead.
  const probe = image.cloneNode(false) as HTMLImageElement;
  probe.setAttribute('aria-hidden', 'true');
  probe.style.cssText = 'position:fixed;visibility:hidden;pointer-events:none;width:auto;height:auto;max-width:none;max-height:none;image-orientation:none';
  document.body.append(probe);
  const size = { width: probe.width, height: probe.height };
  probe.remove();
  return size;
}
export function MediaInspector({ item, processingRunId, refreshKey, focus }: {
  item: Evidence; processingRunId?: string; refreshKey?: string; focus?: SourceFocus;
}) {
  const client = useApiClient();
  const [url, setUrl] = useState('');
  const [sessionVersion, setSessionVersion] = useState(client.getSessionVersion());
  const [decodeError, setDecodeError] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const download = useMemo(() => createOriginalDownload(client, item, blob => {
    const objectUrl = URL.createObjectURL(new Blob([blob], { type: item.media_type }));
    setUrl(objectUrl); setDecodeError(false);
    return () => { URL.revokeObjectURL(objectUrl); setUrl(''); };
  }), [client, item, sessionVersion]);
  const downloadState = useSyncExternalStore(download.subscribe, download.getSnapshot, download.getSnapshot);
  useEffect(() => { if (focus && downloadState.status === 'idle' && client.hasToken()) void download.download(); }, [focus, download, downloadState.status, client]);
  useEffect(() => {
    download.start();
    const unsubscribe = client.subscribeSession(() => { download.dispose(); setSessionVersion(client.getSessionVersion()); });
    return () => { unsubscribe(); download.dispose(); };
  }, [client, download]);
  const [observationState, setObservationState] = useState<{ items: Observation[]; loading: boolean; error: boolean }>({ items: [], loading: true, error: false });
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    setObservationState({ items: [], loading: true, error: false });
    const unsubscribe = client.subscribeSession(() => { request.abort(); setObservationState({ items: [], loading: false, error: true }); });
    void resolveSourceObservations(client, item.case_id, item.id, request.signal, processingRunId, focus).then(items => {
      if (!request.signal.aborted) setObservationState({ items, loading: false, error: false });
    }).catch(() => { if (!request.signal.aborted) setObservationState({ items: [], loading: false, error: true }); });
    return () => { request.abort(); unsubscribe(); };
  }, [client, item.case_id, item.id, processingRunId, refreshKey, focus, refresh]);
  return <section className={`media-inspector ${expanded ? 'media-expanded' : ''}`} aria-label="Interactive media inspector">
    <div className="section-heading"><div><h3>Media inspector</h3></div>
      <span className="kind-badge">{item.kind}</span><button type="button" aria-pressed={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Compact view' : 'Expand viewer'}</button></div>
    {!url && <button type="button" disabled={downloadState.status === 'loading' || !client.hasToken()} onClick={() => { void download.download(); }}>
      {downloadState.status === 'loading' ? 'Verifying original…' : 'Open media inspector'}</button>}
    {downloadState.status === 'error' && <p role="alert">{downloadState.message}</p>}
    {url && !decodeError && <MediaCanvas key={url} url={url} isVideo={item.kind === 'video'} label={item.source_label}
      observations={observationState.items} focus={focus} onError={() => setDecodeError(true)} />}
    {decodeError && <p role="alert">This browser cannot decode the original media. Use Download original to inspect it in a compatible viewer.</p>}
    <details className="context-help"><summary>Detection details</summary><p>Candidate detections use original pixel coordinates. Video offsets are relative, not capture times. Boxes appear near sampled timestamps and do not track subjects between samples.</p></details>
    {observationState.loading && <p role="status">Loading detection observations…</p>}
    {observationState.error && <p role="alert">Could not load the complete source observations. The cited output may be unavailable. Retry detections.</p>}
    {!observationState.loading && !observationState.error && <details className="technical-details"><summary>{observationState.items.length} observations</summary>{observationState.items[0] && <p className="identifier">Processing run: {observationState.items[0].processing_run_id}</p>}</details>}
    {observationState.error && <button type="button" onClick={() => setRefresh(value => value + 1)}>Retry detections</button>}
  </section>;
}

export function MediaCanvas({ url, isVideo, label, observations, focus, onError }: {
  url: string; isVideo: boolean; label: string; observations: Observation[]; focus?: SourceFocus; onError: () => void;
}) {
  const settings = useSettings();
  const canvas = useRef<HTMLCanvasElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [seconds, setSeconds] = useState(0);
  const [selected, setSelected] = useState<Observation>();
  const [overlays, setOverlays] = useState(settings.show_bounding_boxes);
  useEffect(() => setOverlays(settings.show_bounding_boxes), [settings.show_bounding_boxes]);
  const [fps, setFps] = useState('');
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playbackError, setPlaybackError] = useState(false);
  const frameRate = Number(fps) > 0 && Number.isFinite(Number(fps)) ? Number(fps) : undefined;
  const detections = useMemo(() => {
    const reading = observations.find(value => value.id === focus?.observation_id && value.kind.endsWith('.plate_reading'));
    return observations.map(observation => ({ observation, locator: parseMediaLocator(observation.source_locator),
      style: detectionStyle(observation.kind.endsWith('.plate_reading') ? 'license_plate' : observation.raw_value) })).filter(d => d.locator.box
        && (!d.observation.kind.endsWith('.plate_reading') || d.observation.id === focus?.observation_id)
        && !(reading && d.observation.kind.endsWith('detection') && /license_plate/.test(d.observation.raw_value) && d.observation.source_locator === reading.source_locator));
  }, [observations, focus?.observation_id]);
  const visible = detections.filter(d => (d.observation.extraction_confidence >= (/license_plate/.test(d.observation.raw_value) || d.observation.kind.endsWith('.plate_reading') ? settings.plate_detection_threshold ?? .4 : settings.detection_threshold) || d.observation.id === selected?.id || d.observation.id === focus?.observation_id) && detectionVisible(d.locator, seconds, isVideo, frameRate));
  const choose = (observation: Observation) => { setSelected(observation); video.current?.pause(); };
  const seek = (locator: ReturnType<typeof parseMediaLocator>) => {
    const at = locator.seconds ?? (frameRate && locator.frame !== undefined ? locator.frame / frameRate : undefined);
    if (video.current && at !== undefined) { video.current.pause(); video.current.currentTime = at; setSeconds(at); }
  };
  useEffect(() => {
    setSelected(undefined);
    if (focus) { seek(parseMediaLocator(focus.source_locator)); setSelected(observations.find(o => o.id === focus.observation_id)); }
  }, [focus, observations, frameRate]);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    let frame = 0;
    const update = () => { setSeconds(element.currentTime); frame = requestAnimationFrame(update); };
    const start = () => { setPlaying(true); cancelAnimationFrame(frame); frame = requestAnimationFrame(update); };
    const stop = () => { setPlaying(false); cancelAnimationFrame(frame); setSeconds(element.currentTime); };
    element.addEventListener('play', start); element.addEventListener('pause', stop);
    return () => { cancelAnimationFrame(frame); element.removeEventListener('play', start); element.removeEventListener('pause', stop); };
  }, []);
  useEffect(() => {
    const element = canvas.current;
    if (!element || !size.width) return;
    const draw = () => {
      const rect = element.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
      element.width = Math.round(rect.width * ratio); element.height = Math.round(rect.height * ratio);
      const ctx = element.getContext('2d'); if (!ctx) return;
      ctx.scale(ratio, ratio); ctx.clearRect(0, 0, rect.width, rect.height);
      if (!overlays) return;
      const sx = rect.width / size.width, sy = rect.height / size.height;
      for (const d of visible) {
        const box = d.locator.box!;
        const x = box.x * sx, y = box.y * sy, w = box.width * sx, h = box.height * sy;
        ctx.strokeStyle = d.style.color; ctx.lineWidth = selected?.id === d.observation.id ? 4 : 2;
        ctx.strokeRect(x, y, w, h); ctx.fillStyle = `${d.style.color}18`; ctx.fillRect(x, y, w, h);
        ctx.font = '600 11px system-ui';
        const badge = d.observation.kind.endsWith('.plate_reading') ? d.observation.normalized_value || 'Unreadable plate' : d.style.label;
        const width = ctx.measureText(badge).width + 12;
        const bx = Math.max(0, Math.min(x, rect.width - width)), by = Math.max(0, y - 22);
        ctx.fillStyle = d.style.color; ctx.fillRect(bx, by, width, 22); ctx.fillStyle = '#080d14'; ctx.fillText(badge, bx + 6, by + 15);
      }
    };
    draw(); const observer = new ResizeObserver(draw); observer.observe(element);
    return () => observer.disconnect();
  }, [size, seconds, detections, selected, overlays, frameRate, settings.detection_threshold, settings.plate_detection_threshold]);
  return <div className="media-viewer">
    <div className="media-stage" style={size.width ? { aspectRatio: `${size.width}/${size.height}` } : undefined}>
      {isVideo ? <video ref={video} src={url} preload="metadata" playsInline aria-label={label}
        onLoadedMetadata={event => { const v = event.currentTarget; setDuration(Number.isFinite(v.duration) ? v.duration : 0); setSize({ width: v.videoWidth, height: v.videoHeight }); if (focus) seek(parseMediaLocator(focus.source_locator)); }}
        onTimeUpdate={event => setSeconds(event.currentTarget.currentTime)} onSeeked={event => setSeconds(event.currentTarget.currentTime)} onError={onError} /> :
        <img src={url} alt={label} onLoad={event => setSize(storedImageSize(event.currentTarget))} onError={onError} />}
      <canvas ref={canvas} aria-hidden="true" />
      {overlays && size.width > 0 && visible.map(d => {
        const b = d.locator.box!;
        return <button className="media-box-hit" key={d.observation.id} type="button" aria-label={`Inspect ${d.style.label}: ${d.observation.raw_value}`}
          aria-pressed={selected?.id === d.observation.id} style={{ left: `${100 * b.x / size.width}%`, top: `${100 * b.y / size.height}%`, width: `${100 * b.width / size.width}%`, height: `${100 * b.height / size.height}%` }}
          onClick={() => choose(d.observation)} />;
      })}
    </div>
    {isVideo && <div className="media-playback" role="group" aria-label="Video playback controls">
      <button type="button" onClick={() => { const v = video.current; if (!v) return; if (v.paused) { setPlaybackError(false); void v.play().catch(() => setPlaybackError(true)); } else v.pause(); }}>{playing ? 'Pause' : 'Play'}</button>
      <label>Seek video<input type="range" min="0" max={duration} step="0.001" value={Math.min(seconds, duration)} disabled={!duration} onChange={event => { const at = Number(event.target.value); if (video.current) video.current.currentTime = at; setSeconds(at); }} /></label>
      <output>{seconds.toFixed(2)} / {duration.toFixed(2)}s</output>
    </div>}
    {playbackError && <p role="alert">Playback could not start. Try again or download the original.</p>}
    <div className="media-toolbar"><label><input type="checkbox" checked={overlays} onChange={e => setOverlays(e.target.checked)} /> Detection overlays</label>
      {isVideo && <output>Offset {seconds.toFixed(3)}s</output>}</div>
    {isVideo && detections.some(d => d.locator.seconds === undefined && d.locator.frame !== undefined) && <label>Frame rate for frame-only locators (fps)<input type="number" min="0.001" step="any" value={fps} onChange={e => setFps(e.target.value)} /></label>}
    <div className="media-detection-list" aria-label="Detection samples">{detections.length === 0 ? <p>No bounding boxes in this processing output.</p> : detections.map(d =>
      <button key={d.observation.id} type="button" aria-pressed={selected?.id === d.observation.id} onClick={() => { choose(d.observation); seek(d.locator); }}>
        <span><span style={{ color: d.style.color }} aria-hidden="true">●</span> {d.style.label}</span>{isVideo ? <span>Frame {d.locator.frame ?? 'unknown'} · {d.locator.seconds ?? 'unknown'}s</span> : d.observation.kind.endsWith('.plate_reading') && <span>{d.observation.normalized_value || 'Unreadable'}</span>}
      </button>)}</div>
    {selected && <aside className="media-observation-details" aria-label="Selected detection details"><div className="section-heading"><h4>{selected.kind.endsWith('.plate_reading') ? 'Plate reading · unverified' : detectionStyle(selected.raw_value).label}</h4><button className="icon-button" aria-label="Close detection" onClick={() => setSelected(undefined)}>×</button></div>
      {selected.kind.endsWith('.plate_reading') && <p>{selected.normalized_value || 'Unreadable plate'}</p>}
      {selected.observed_at_utc && <p>{selected.observed_at_utc}</p>}
      <details className="technical-details"><summary>Technical details</summary><dl><dt>Observation</dt><dd>{selected.id}</dd><dt>Source locator</dt><dd>{selected.source_locator}</dd>
        <dt>Reported score (uncalibrated)</dt><dd>{selected.extraction_confidence.toFixed(3)}</dd><dt>Processing run</dt><dd>{selected.processing_run_id}</dd></dl>
        <p>{selected.raw_value}</p></details></aside>}
  </div>;
}
