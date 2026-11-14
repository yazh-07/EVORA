import { EvidenceResults } from './EvidenceResults';
import type { ReactNode } from 'react';
import type { components } from '../api/schema';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { MediaInspector } from './MediaInspector';
import type { SourceFocus } from './mediaLocators';
import { ObservationInspector } from './ObservationInspector';
import { OriginalDownload } from './OriginalDownload';
import { BulkProcessing } from './BulkProcessing';
import { ProcessingHistory } from './ProcessingStatus';
import { StartProcessing } from './StartProcessing';
import { TranscriptViewer } from './TranscriptViewer';
import { useApiClient } from '../api/ApiProvider';
import { createEvidenceStore, evidenceKinds } from './evidenceStore';
import type { Evidence, EvidenceState } from './evidenceStore';
import { detectEvidenceKind } from './evidenceDetection';
import { EvidenceIntake, formatSupport } from './EvidenceIntake';
import { OriginalTextPreview } from './OriginalTextPreview';

export function EvidenceWorkspace({ caseId, caseTitle, sourceSelection, intakeRequest = 0 }: { caseId: string; caseTitle?: string; intakeRequest?: number; sourceSelection?: { id: string; focus?: SourceFocus } }) {
  const client = useApiClient();
  const [refreshSequence, setRefreshSequence] = useState(0);
  const store = useMemo(() => createEvidenceStore(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { void store.start(); return () => store.dispose(); }, [store]);
  useEffect(() => { if (sourceSelection) void store.select(sourceSelection.id); }, [store, sourceSelection]);
  return <><EvidencePanels revision={refreshSequence} renderProcessing={client.getUser()?.role !== 'reviewer' ? (ids, onCount) => <BulkProcessing caseId={caseId} caseTitle={caseTitle} evidenceIds={ids} onCount={onCount} revision={state.page} onCompleted={() => { setRefreshSequence(value => value + 1); void store.load(state.page?.offset ?? 0); }} /> : undefined} closeSelection={() => { const id = store.getSnapshot().detail?.id; store.clearSelection(); requestAnimationFrame(() => document.getElementById(`evidence-source-${id}`)?.focus()); }} readOnly={client.getUser()?.role === 'reviewer'} intakeRequest={intakeRequest} sourceFocus={sourceSelection?.id === state.detail?.id ? sourceSelection?.focus : undefined} state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} upload={async (...args) => { const ok = await store.upload(...args); if (ok) store.clearSelection(); return ok; }} /></>;
}
function Metadata({ item, detailed = false }: { item: Evidence; detailed?: boolean }) {
  return <>
    <dl className="evidence-metadata">
      <dt>Kind</dt><dd>{item.kind}</dd><dt>Filename</dt><dd>{item.filename}</dd>
      <dt>Size (bytes)</dt><dd>{item.size_bytes}</dd><dt>SHA-256</dt><dd className="identifier">{item.sha256}</dd>
    </dl>
    {detailed && <details className="metadata-details"><summary>Additional metadata</summary>
      <dl className="evidence-metadata">
        <dt>Evidence ID</dt><dd className="identifier">{item.id}</dd>
        <dt>Case ID</dt><dd className="identifier">{item.case_id}</dd><dt>Media type</dt><dd>{item.media_type}</dd>
        <dt>Acquired at</dt><dd>{item.acquired_at ?? 'Not provided'}</dd><dt>Uploaded at</dt><dd>{item.created_at}</dd>
      </dl>
    </details>}
  </>;
}
export function EvidencePanels({ state, load, select, upload, sourceFocus, intakeRequest = 0, readOnly = false, processingControls, renderProcessing, closeSelection, revision = 0 }: {
  revision?: number;
  renderProcessing?: (ids: string[], onCount: (count: number) => void) => ReactNode;
  closeSelection?: () => void;
  processingControls?: ReactNode;
  readOnly?: boolean;
  intakeRequest?: number;
  sourceFocus?: SourceFocus; state: EvidenceState; load: (offset: number) => void; select: (id: string) => void;
  upload: (file: File | null, kind: string, label: string, acquiredAt: string) => Promise<boolean>;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const error = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (state.uploadMessage) error.current?.focus(); }, [state.uploadMessage]);
  useEffect(() => { if (!state.submitting && (state.detailStatus === 'ready' || state.detailStatus === 'error')) heading.current?.focus(); }, [state.detail, state.detailStatus]);
  const page = state.page;
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [, setPendingCount] = useState(0);
  const [kind, setKind] = useState('all');
  const [sort, setSort] = useState('newest');
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [intakeRevision, setIntakeRevision] = useState(0);
  useEffect(() => { if (intakeRequest) setIntakeOpen(true); }, [intakeRequest]);
  const [detectedKind, setDetectedKind] = useState<string>();
  const [detecting, setDetecting] = useState(false);
  const cancelDetection = useRef<(() => void) | undefined>(undefined);
  useEffect(() => () => cancelDetection.current?.(), []);
  const visible = (page?.items ?? []).filter(item =>
    (kind === 'all' || item.kind === kind) &&
    `${item.source_label} ${item.filename} ${item.id} ${item.sha256}`.toLowerCase().includes(query.trim().toLowerCase())
  ).sort((a, b) => sort === 'name' ? a.source_label.localeCompare(b.source_label) : sort === 'size' ? b.size_bytes - a.size_bytes : b.created_at.localeCompare(a.created_at));
  return <div className="evidence-workspace">
    <div className="section-heading evidence-topbar"><h2 id="evidence-heading">Evidence</h2><div className="evidence-actions"><button ref={addButton} hidden={readOnly} type="button" className="button-primary" disabled={state.submitting} aria-expanded={intakeOpen} aria-controls="evidence-intake" onClick={() => { setIntakeOpen(value => !value); requestAnimationFrame(() => document.getElementById('batch-evidence-files')?.focus()); }}>Upload files</button><button type="button" className="icon-button" aria-label="Refresh evidence" title="Refresh evidence" disabled={state.status === 'loading'} onClick={() => load(page?.offset ?? 0)}>↻</button></div></div>
    {state.uploaded && <p className="sr-only" role="status">Evidence uploaded.</p>}
    <section hidden={readOnly || !intakeOpen} className="panel intake-panel" aria-labelledby="upload-heading">
      <details className="intake-disclosure" id="evidence-intake" open={intakeOpen} onToggle={event => {
        setIntakeOpen(event.currentTarget.open);
        if (!event.currentTarget.open && event.currentTarget.contains(document.activeElement)) addButton.current?.focus();
      }}>
      <summary aria-disabled={state.submitting} onClick={event => { if (state.submitting) event.preventDefault(); }}><h2 id="upload-heading">Add evidence</h2></summary>
      <EvidenceIntake key={intakeRevision} upload={upload} submitting={state.submitting} onUploaded={() => { setSelected(new Set()); setIntakeRevision(value => value + 1); setIntakeOpen(false); requestAnimationFrame(() => addButton.current?.focus({ preventScroll: true })); }} />
      <details className="single-intake"><summary>More upload options</summary>
      <form className="upload-form" noValidate aria-busy={state.submitting} onSubmit={async event => {
        event.preventDefault();
        if (detecting) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0] ?? null;
        if (await upload(file, String(data.get('kind')), String(data.get('source_label') ?? ''), String(data.get('acquired_at') ?? ''))) { cancelDetection.current?.(); form.reset(); setDetectedKind(undefined); setSelected(new Set()); setIntakeRevision(value => value + 1); setIntakeOpen(false); }
        else error.current?.focus();
      }}>
        <fieldset disabled={state.submitting}>
          <legend>Original file and source</legend>
          <label htmlFor="evidence-file">File (required)</label><input id="evidence-file" name="file" type="file" required onChange={event => {
            cancelDetection.current?.();
            setDetectedKind(undefined); setDetecting(false);
            const file = event.target.files?.[0];
            const form = event.target.form;
            if (!file || !form) return;
            const label = form.elements.namedItem('source_label') as HTMLInputElement;
            if (!label.value) label.value = file.name.slice(0, 200);
            const kind = form.elements.namedItem('kind') as HTMLSelectElement;
            setDetecting(true);
            cancelDetection.current = detectEvidenceKind(file, value => {
              kind.value = value; setDetectedKind(value);
            }, () => setDetecting(false));
          }} />
          {detectedKind && <span className="auto-detect-badge" role="status">Detected type: {detectedKind}</span>}
          <label htmlFor="evidence-kind">Kind (required)</label><select id="evidence-kind" name="kind" required defaultValue="document" onChange={() => {
            cancelDetection.current?.(); setDetecting(false); setDetectedKind(undefined);
          }}>
            {evidenceKinds.map(kind => <option key={kind} value={kind}>{kind}</option>)}
          </select>
          <label htmlFor="evidence-label">Source label (required)</label><input id="evidence-label" name="source_label" type="text" required maxLength={200} />
          <details className="advanced-metadata"><summary>Chain-of-custody acquisition date (optional)</summary>
          <label htmlFor="evidence-acquired">Acquired at (optional, UTC)</label><input id="evidence-acquired" name="acquired_at" type="datetime-local" step="1" aria-describedby="acquired-help" />
          <p id="acquired-help">Enter the acquisition time in UTC. Leave blank if unknown.</p>
          </details>
          <button type="submit" disabled={state.submitting || detecting}>{state.submitting ? 'Uploading evidence...' : 'Upload evidence'}</button>
        </fieldset>
        {state.uploadMessage && <p role="alert" ref={error} tabIndex={-1}>{state.uploadMessage}</p>}
      </form>
      </details>
      </details>
    </section>
    <div className={`workspace-layout ${state.detailStatus !== 'idle' ? 'evidence-has-selection' : ''}`}>
      <section className="panel" aria-labelledby="evidence-heading" aria-busy={state.status === 'loading'}>
        <div className="evidence-processing">{renderProcessing?.([...selected], setPendingCount)}</div>{selected.size > 0 && <div className="selection-toolbar"><span>{selected.size} selected</span><button type="button" className="text-action" onClick={() => setSelected(new Set())}>Clear selection</button></div>}

        {processingControls}
<div className="contextual-workspace"><details className="context-filters" open><summary>Filters</summary><div className="evidence-toolbar">
          <label className="search-field">Search evidence<input type="search" placeholder="Filter this page by name…" value={query} onChange={event => setQuery(event.target.value)} /></label>
          <label>Kind<select value={kind} onChange={event => setKind(event.target.value)}><option value="all">All kinds</option>{evidenceKinds.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
          <label>Sort by<select value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Newest first</option><option value="name">Source name</option><option value="size">Largest first</option></select></label>
        </div>
        </details><div className="context-records">
        {page && page.total > page.items.length && <p className="filter-scope">Filters apply to this page.</p>}
        {state.status === 'loading' && <p className={page ? 'sr-only' : 'loading-placeholder'} role="status">Loading evidence…</p>}
        {state.status === 'error' && <p role="alert">{state.message}</p>}
        {page && <>
          <p className="sr-only" role="status">{page.total} evidence items. Showing {page.items.length} on this page.</p>
          {page.items.length === 0 && <p>{page.total === 0 ? 'No evidence uploaded yet for this case' : 'No evidence on this page.'}</p>}
          {page.items.length > 0 && visible.length === 0 && <div className="empty-state"><h3>No matching evidence</h3><button onClick={() => { setQuery(''); setKind('all'); }}>Clear filters</button></div>}
          {visible.length > 0 && <div className="evidence-table-scroll" role="region" aria-label="Evidence library" tabIndex={0}><table className="evidence-table">
            <thead><tr>{!readOnly && <th className="selection-cell"><input type="checkbox" aria-label="Select visible files" checked={visible.length > 0 && visible.every(item => selected.has(item.id))} onChange={event => setSelected(previous => { const next = new Set(previous); visible.forEach(item => event.target.checked ? next.add(item.id) : next.delete(item.id)); return next; })} /></th>}<th scope="col">Source / filename</th><th scope="col">Kind</th><th scope="col">Size</th><th scope="col">Added</th></tr></thead>
            <tbody>{visible.map(item => <tr key={item.id} className={state.detail?.id === item.id ? 'selected-row' : ''}>
              {!readOnly && <td className="selection-cell"><input type="checkbox" aria-label={`Select ${item.source_label}`} checked={selected.has(item.id)} onChange={event => setSelected(previous => { const next = new Set(previous); if (event.target.checked) next.add(item.id); else next.delete(item.id); return next; })} /></td>}
              <td className="source-cell"><button id={`evidence-source-${item.id}`} className="source-button" type="button" onClick={() => select(item.id)} aria-pressed={state.detail?.id === item.id}>{item.source_label}</button>{item.filename !== item.source_label && <span className="source-filename">{item.filename}</span>}</td>
              <td><span className="kind-badge">{item.kind.replaceAll('_', ' ')}</span></td>
              <td className="size-cell">{formatFileSize(item.size_bytes)}</td>
              <td><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</time></td>
            </tr>)}</tbody>
          </table></div>}
          <nav hidden={!!page && page.total <= page.limit} className="pagination" aria-label="Evidence pages">
            <button onClick={() => load(Math.max(0, page.offset - page.limit))} disabled={page.offset === 0 || state.submitting}>Previous</button>
            <button onClick={() => load(page.offset + page.limit)} disabled={page.offset + page.limit >= page.total || state.submitting}>Next</button>
          </nav>
        </>}
        </div></div>
      </section>
      <aside className="panel inspector" aria-labelledby="evidence-inspector" aria-busy={state.detailStatus === 'loading'}>
        <div className="section-heading"><h2 id="evidence-inspector" ref={heading} tabIndex={-1}>{state.detail?.source_label || 'Source'}</h2>{closeSelection && state.detailStatus !== 'idle' && <button type="button" className="icon-button" aria-label="Close source" title="Back to evidence" onClick={closeSelection}>×</button>}</div>
        {state.detailStatus === 'idle' && <p className="inspector-empty">Select a source.</p>}
        {state.detailStatus === 'loading' && <p role="status">Loading evidence metadata...</p>}
        {state.detailStatus === 'error' && <p role="alert">{state.detailMessage} Select evidence again to retry.</p>}
        {state.detail && <EvidenceProcessingInspection key={`${state.detail.case_id}:${state.detail.id}`} item={state.detail} sourceFocus={sourceFocus} externalRevision={revision} />}

      </aside>
    </div>
  </div>;
}

/** Selection-keyed lifetime also discards the previous completion/pin on evidence switches. */
export function EvidenceProcessingInspection({ item, sourceFocus, externalRevision = 0 }: { item: Evidence; sourceFocus?: SourceFocus; externalRevision?: number }) {
  const [view, setView] = useState<'results' | 'original' | 'info'>('results');
  const [visited, setVisited] = useState(() => new Set(['results']));
  const [completedRunId, setCompletedRunId] = useState<string>();
  const [revision, setRevision] = useState(0);
  const [focus, setFocus] = useState(sourceFocus);
  const [selected, setSelected] = useState<components['schemas']['Observation']>();
  const [processingOpen, setProcessingOpen] = useState(false), [rawOpen, setRawOpen] = useState(false), [transcriptOpen, setTranscriptOpen] = useState(false);
  const changeView = (next: 'results' | 'original' | 'info') => { setView(next); setVisited(previous => new Set([...previous, next])); };
  const onProcessingCompleted = useCallback((runId: string) => { setCompletedRunId(runId); setRevision(value => value + 1); }, []);
  const onProcessingFailed = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => { setSelected(undefined); if (!sourceFocus?.processing_run_id) setFocus(undefined); }, [externalRevision, revision, sourceFocus?.processing_run_id]);
  useEffect(() => { setFocus(sourceFocus); }, [sourceFocus]);
  const refreshKey = `${completedRunId ?? ''}:${revision}:${externalRevision}`;
  return <>
    <div className="source-tabs" role="group" aria-label="Source views">{(['results', 'original', 'info'] as const).map(tab => <button key={tab} type="button" aria-pressed={view === tab} onClick={() => changeView(tab)}>{tab.charAt(0).toUpperCase() + tab.slice(1)}</button>)}
      <details className="action-menu source-actions"><summary aria-label="Source actions" title="Source actions">⋯</summary><div className="action-popover"><OriginalDownload item={item} /><button type="button" onClick={() => setRevision(value => value + 1)}>Refresh source</button><button type="button" onClick={() => { changeView('info'); setProcessingOpen(true); }}>Processing history</button></div></details>
    </div>
    <div hidden={view !== 'results'}>{visited.has('results') && <EvidenceResults onFailed={onProcessingFailed} allowProcessing={!sourceFocus?.processing_run_id} item={item} revision={refreshKey} focus={focus} onDerivedRun={onProcessingCompleted} onSelectResult={setSelected} onInspectOriginal={next => { setFocus(next); changeView('original'); }} />}</div>
    <div hidden={view !== 'original'}>{visited.has('original') && (item.kind === 'image' || item.kind === 'video' ? <MediaInspector item={item} processingRunId={focus?.processing_run_id} refreshKey={refreshKey} focus={focus} /> : <OriginalTextPreview item={item} />)}</div>
    <div hidden={view !== 'info'}>{visited.has('info') && <>
      <dl className="evidence-metadata"><dt>File</dt><dd>{item.filename}</dd><dt>Type</dt><dd>{item.kind.replaceAll('_', ' ')}</dd><dt>Size</dt><dd>{formatFileSize(item.size_bytes)}</dd><dt>Added</dt><dd>{new Date(item.created_at).toLocaleString()}</dd></dl>
      {selected && <section className="selected-result-info"><h3>Selected result</h3><p>{selected.source_locator}</p><p>Reported score: {selected.extraction_confidence}</p>{selected.raw_value !== selected.normalized_value && <p>{selected.raw_value}</p>}</section>}
      <details className="processing-actions" open={processingOpen} onToggle={event => setProcessingOpen(event.currentTarget.open)}><summary>Processing history</summary>{processingOpen && <ProcessingHistory caseId={item.case_id} evidenceId={item.id} revision={refreshKey} />}</details>
      {item.kind === 'document' && item.filename.toLowerCase().endsWith('.csv') && <details><summary>CSV format</summary><StartProcessing caseId={item.case_id} evidenceId={item.id} sourceKind={item.kind} filename={item.filename} onCompleted={onProcessingCompleted} /></details>}
      <details className="technical-details"><summary>File verification</summary><Metadata item={item} detailed />{selected && <dl><dt>Observation</dt><dd className="identifier">{selected.id}</dd><dt>Processing output</dt><dd className="identifier">{selected.processing_run_id}</dd></dl>}</details>
      <details className="raw-observations" open={rawOpen} onToggle={event => setRawOpen(event.currentTarget.open)}><summary>Raw observations</summary>{rawOpen && <ObservationInspector focus={focus} caseId={item.case_id} evidenceId={item.id} processingRunId={focus?.processing_run_id} refreshKey={refreshKey} />}</details>
      {(item.kind === 'audio' || item.kind === 'video') && <details open={transcriptOpen} onToggle={event => setTranscriptOpen(event.currentTarget.open)}><summary>Transcript history</summary>{transcriptOpen && <TranscriptViewer item={item} refreshKey={refreshKey} onDerivedRun={onProcessingCompleted} />}</details>}
      <p className="scope-note">{formatSupport(item.filename, item.kind)}</p>
    </>}</div>
  </>;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
