import { SourceExcerpt } from './SourceExcerpt';
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import type { Evidence } from './evidenceStore';
import { detectionStyle, parseMediaLocator } from './mediaLocators';
import type { SourceFocus } from './mediaLocators';
import { resolveSourceObservations } from './sourceObservations';
import { MediaInspector } from './MediaInspector';
import { createOriginalDownload } from './downloadController';

type Results = components['schemas']['EvidenceResults'];
type Observation = components['schemas']['Observation'];
type Operation = Results['operation'];
const labels: Record<Operation, string> = { detection: 'Detections', description: 'Scene descriptions', ocr: 'Visible text', transcript: 'Transcript', records: 'Records', plates: 'Plates' };
const statusLabels = { not_run: 'Not run', unsupported: 'Unavailable', queued: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed' };

function operationFor(value: Observation): Operation | undefined {
  const kind = value.kind;
  if (kind.endsWith('.plate_reading')) return 'plates';
  if (kind === 'image.detection' || kind === 'video.frame_detection') return 'detection';
  if (kind === 'image.description' || kind === 'video.scene') return 'description';
  if (kind === 'image.ocr' || kind === 'video.ocr') return 'ocr';
  if (kind.startsWith('transcript.')) return 'transcript';
  return /\.(provenance|limitations|track)$/.test(kind) ? undefined : 'records';
}

export function resultTitle(item: Observation): string {
  if (item.kind.endsWith('.plate_reading')) return item.normalized_value ? 'Plate reading · unverified' : 'Plate unreadable';
  if (item.kind === 'transcript.status') return item.normalized_value === 'silence' ? 'No speech returned' : 'No audio track';
  if (item.kind === 'image.detection' || item.kind === 'video.frame_detection') {
    const category = detectionStyle(item.raw_value).label;
    return category === 'Object' ? (item.raw_value.split(' [')[0] || 'Detection') : category;
  }
  return item.kind.replaceAll('.', ' / ').replaceAll('_', ' ');
}

function sourceLabel(value: Observation, kind: Evidence['kind']) {
  if (kind === 'image') return undefined;
  if (kind === 'video' || kind === 'audio') {
    const locator = parseMediaLocator(value.source_locator);
    return locator.seconds !== undefined ? `At ${locator.seconds.toFixed(2)}s` : undefined;
  }
  const row = value.source_locator.match(/(?:^|[;: ])row=(\d+)/)?.[1];
  return row ? `Row ${row}` : value.source_locator;
}

function ResultAudio({ item, selection }: { item: Evidence; selection: Observation }) {
  const client = useApiClient(), media = useRef<HTMLAudioElement>(null);
  const [url, setUrl] = useState('');
  const loader = useMemo(() => createOriginalDownload(client, item, blob => {
    const value = URL.createObjectURL(new Blob([blob], { type: item.media_type })); setUrl(value);
    return () => { URL.revokeObjectURL(value); setUrl(''); };
  }), [client, item]);
  const state = useSyncExternalStore(loader.subscribe, loader.getSnapshot, loader.getSnapshot);
  const seek = () => {
    const match = selection.source_locator.match(/^media:start_ms=(\d+);end_ms=(\d+)$/);
    if (media.current && match) media.current.currentTime = Number(match[1]) / 1000;
  };
  useEffect(() => { loader.start(); void loader.download(); return () => loader.dispose(); }, [loader]);
  useEffect(seek, [selection, url]);
  return <section aria-label="Audio source">{url && <audio ref={media} src={url} controls onLoadedMetadata={seek} aria-label="Selected source audio" />}
    {state.status === 'loading' && <p role="status">Verifying original audio…</p>}
    {state.status === 'error' && <><p role="alert">{state.message}</p><button type="button" onClick={() => { void loader.download(); }}>Retry audio</button></>}
    <p>{selection.source_locator}</p>
  </section>;
}

export function EvidenceResults({ item, revision, focus, onDerivedRun, onSelectResult, onInspectOriginal }: { item: Evidence; revision?: string; focus?: SourceFocus; onDerivedRun: (id: string) => void; onSelectResult?: (value: Observation) => void; onInspectOriginal?: (focus: SourceFocus) => void }) {
  const client = useApiClient();
  const pagePin = useRef<string | undefined>(undefined);
  const focused = useRef('');
  const [operation, setOperation] = useState<Operation>();
  const [offset, setOffset] = useState(0), [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<Observation>();
  const [state, setState] = useState<{ data?: Results; loading: boolean; error?: string }>({ loading: true });
  // When following a citation the caller supplies its exact historical run. Never fall back to live results.
  useEffect(() => {
    const request = new AbortController();
    setState({ loading: true }); setSelected(undefined);
    const load = async () => {
      let runId = focus?.processing_run_id ?? (offset > 0 ? pagePin.current : undefined);
      let chosen = operation;
      if (focus?.observation_id) {
        const source = await resolveSourceObservations(client, item.case_id, item.id, request.signal, runId, focus);
        const cited = source.find(value => value.id === focus.observation_id);
        if (!cited) throw Error();
        runId = cited.processing_run_id;
        const key = `${item.id}:${cited.processing_run_id}:${cited.id}`;
        if (focused.current !== key) {
          request.signal.throwIfAborted();
          chosen = operationFor(cited) ?? 'records';
          const ordered = source.filter(value => operationFor(value) === chosen).sort((a, b) => a.source_locator < b.source_locator ? -1 : a.source_locator > b.source_locator ? 1 : a.kind < b.kind ? -1 : a.kind > b.kind ? 1 : a.id.localeCompare(b.id));
          const page = Math.floor(ordered.findIndex(value => value.id === cited.id) / 50) * 50;
          if (page < 0) throw Error();
          focused.current = key;
          if (offset !== page || operation !== chosen) { setOffset(page); setOperation(chosen); return; }
        }
        chosen ??= operationFor(cited) ?? 'records';
      }
      const response = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/results', {
      path: { caseId: item.case_id, evidenceId: item.id }, query: { operation: chosen, processing_run_id: runId, limit: 50, offset }, signal: request.signal,
    });
      return { data: response, chosen, runId };
    };
    void load().then(payload => {
      if (!payload) return;
      const { data, chosen, runId } = payload;
      if (request.signal.aborted) return;
      if (data.case_id !== item.case_id || data.evidence_id !== item.id || data.offset !== offset || data.limit !== 50 || !Number.isSafeInteger(data.total) || data.total < 0 || !Array.isArray(data.operations) || !Array.isArray(data.items)) throw Error();
      const op = data.operations.find(value => value.operation === data.operation);
      if (!op || !(data.operation in labels) || (chosen && data.operation !== chosen) || (runId && op.output_run_id !== runId && data.items.length > 0) || data.items.length > 50 || data.items.length !== Math.min(50, Math.max(0, data.total - offset)) || data.operations.some(entry => !(entry.operation in labels) || !(entry.status in statusLabels) || (entry.count !== null && (!Number.isSafeInteger(entry.count) || entry.count < 0))) || new Set(data.items.map(value => value.id)).size !== data.items.length || data.items.some(value => value.case_id !== item.case_id || value.evidence_id !== item.id || value.processing_run_id !== op.output_run_id || typeof value.source_locator !== 'string' || typeof value.raw_value !== 'string')) throw Error();
      pagePin.current = op.output_run_id ?? undefined;
      setState({ data, loading: false });
      if (focus?.observation_id) setSelected(data.items.find(value => value.id === focus.observation_id));
    }).catch(() => { if (!request.signal.aborted) setState({ loading: false, error: 'Could not load extraction results. Retry or inspect processing history.' }); });
    return () => request.abort();
  }, [client, item.case_id, item.id, operation, offset, refresh, revision, focus?.processing_run_id, focus?.observation_id]);
  const data = state.data, current = data?.operations.find(value => value.operation === data.operation);
  const selectedFocus = selected ? { source_locator: selected.source_locator, observation_id: selected.id, processing_run_id: selected.processing_run_id } : focus;
  return <section className="extraction-results" aria-label="Extraction results" aria-busy={state.loading}>
    <div className="section-heading"><h3>Results</h3>{!onSelectResult && <button type="button" className="icon-button" aria-label="Refresh results" title="Refresh results" disabled={state.loading} onClick={() => setRefresh(value => value + 1)}>↻</button>}</div>
    {state.loading && <p role="status">Loading results…</p>}
    {state.error && <><p role="alert">{state.error}</p><button type="button" onClick={() => setRefresh(value => value + 1)}>Retry results</button></>}
    {data && <>
      <div className="result-operations" role="group" aria-label="Extraction operations">{data.operations.map(op => <button type="button" key={op.operation} aria-pressed={data.operation === op.operation} onClick={() => { setOperation(op.operation); setOffset(0); }}>
        <strong>{labels[op.operation]}</strong><span>{statusLabels[op.status]}{op.count !== null ? ` · ${op.count} ${op.operation === 'transcript' ? (op.count === 1 ? 'record' : 'records') : (op.count === 1 ? 'result' : 'results')}` : ''}</span>
      </button>)}</div>
      {current?.status === 'unsupported' && <p>Unavailable for this source.</p>}
      {current?.status === 'not_run' && <p>Not processed. Choose an operation under Processing.</p>}
      {current?.status === 'failed' && <p role="alert">Latest attempt failed ({current.error}). {current.output_run_id ? 'Showing earlier completed results.' : 'No completed results available.'}</p>}
      {(current?.status === 'queued' || current?.status === 'running') && <p role="status">Operation {current.status}.{current.output_run_id ? ' Showing earlier completed results.' : ''}</p>}
      {!!current?.notes.length && <details className="context-help"><summary>Method</summary><p>{current.notes.join(' ')}</p></details>}
      {current?.output_run_id && data.total === 0 && <p>No results returned; the source may still contain relevant content.</p>}
      <ol className="extracted-result-list">{data.items.map(value => <li key={value.id} className={selected?.id === value.id ? 'selected-result' : ''}>
        <button type="button" aria-pressed={selected?.id === value.id} onClick={() => { setSelected(value); onSelectResult?.(value); if (['image', 'video'].includes(item.kind)) onInspectOriginal?.({ source_locator: value.source_locator, observation_id: value.id, processing_run_id: value.processing_run_id }); }}><strong>{resultTitle(value)}</strong><span>{value.normalized_value || value.raw_value || 'No readable text returned'}</span>{sourceLabel(value, item.kind) && <small>{sourceLabel(value, item.kind)}</small>}</button>
        {(value.kind.startsWith('image.') || value.kind.startsWith('video.') || value.kind.startsWith('transcript.')) && !value.kind.endsWith('detection') && !value.kind.endsWith('.plate_reading') && <span className="result-origin">{value.transcript_revision_id ? 'Human corrected' : 'Model output · unverified'}</span>}
        {!onSelectResult && <details className="technical-details"><summary>Details</summary><dl><dt>Observation</dt><dd>{value.id}</dd><dt>Processing output</dt><dd>{value.processing_run_id}</dd><dt>Reported score (not a probability of correctness)</dt><dd>{value.extraction_confidence}</dd></dl>{value.raw_value !== value.normalized_value && <><h4>Original extracted value</h4><p>{value.raw_value}</p></>}</details>}
      </li>)}</ol>
      {selected && !['image', 'video', 'audio'].includes(item.kind) && <SourceExcerpt item={item} observation={selected} />}
      {selected && item.kind === 'audio' && <ResultAudio item={item} selection={selected} />}
      {data.total > data.limit && <nav className="pagination" aria-label="Result pages"><button type="button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 50))}>Previous results</button><span>{offset + 1}–{Math.min(offset + 50, data.total)} of {data.total}</span><button type="button" disabled={offset + 50 >= data.total} onClick={() => setOffset(value => value + 50)}>Next results</button></nav>}
      {!onSelectResult && current?.output_run_id && <details className="technical-details"><summary>Output reference</summary><p>{current.output_run_id} · {current.updated_at}</p></details>}
    </>}
    {!onInspectOriginal && (item.kind === 'image' || item.kind === 'video') && <MediaInspector item={item} resultsOnly processingRunId={selected?.processing_run_id || current?.output_run_id || undefined} focus={selectedFocus} refreshKey={revision} onDerivedRun={onDerivedRun} />}
  </section>;
}
