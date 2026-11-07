import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { MediaInspector } from './MediaInspector';
import type { SourceFocus } from './mediaLocators';
import { ObservationInspector } from './ObservationInspector';
import { OriginalDownload } from './OriginalDownload';
import { BulkProcessing } from './BulkProcessing';
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
  const store = useMemo(() => createEvidenceStore(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { void store.start(); return () => store.dispose(); }, [store]);
  useEffect(() => { if (sourceSelection) void store.select(sourceSelection.id); }, [store, sourceSelection]);
  return <>{client.getUser()?.role !== 'reviewer' && <BulkProcessing key={caseId} caseId={caseId} caseTitle={caseTitle} />}{sourceSelection && <p role="status">Source evidence inspection shows live metadata. Citation locators select their referenced processing output when available; other processing controls show live outputs.</p>}<EvidencePanels readOnly={client.getUser()?.role === 'reviewer'} intakeRequest={intakeRequest} sourceFocus={sourceSelection?.id === state.detail?.id ? sourceSelection?.focus : undefined} state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} upload={store.upload} /></>;
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
export function EvidencePanels({ state, load, select, upload, sourceFocus, intakeRequest = 0, readOnly = false }: {
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
  const [kind, setKind] = useState('all');
  const [sort, setSort] = useState('newest');
  const [intakeOpen, setIntakeOpen] = useState(false);
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
    {state.uploaded && <p className="upload-confirmation" role="status">Evidence uploaded. The original file and integrity metadata have been saved.</p>}
    <section hidden={readOnly} className="panel intake-panel" aria-labelledby="upload-heading">
      <details className="intake-disclosure" id="evidence-intake" open={intakeOpen} onToggle={event => {
        setIntakeOpen(event.currentTarget.open);
        if (!event.currentTarget.open && event.currentTarget.contains(document.activeElement)) addButton.current?.focus();
      }}>
      <summary><h2 id="upload-heading">Add evidence</h2><span>Originals are preserved</span></summary>
      <EvidenceIntake upload={upload} submitting={state.submitting} />
      <details className="single-intake"><summary>Add one file with individual metadata</summary>
      <p>Upload one original file. Intake stores its bytes and integrity metadata; content has not been verified.</p>
      <form className="upload-form" noValidate aria-busy={state.submitting} onSubmit={async event => {
        event.preventDefault();
        if (detecting) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0] ?? null;
        if (await upload(file, String(data.get('kind')), String(data.get('source_label') ?? ''), String(data.get('acquired_at') ?? ''))) { cancelDetection.current?.(); form.reset(); setDetectedKind(undefined); setIntakeOpen(false); }
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
        {state.uploaded && <p role="status">Evidence uploaded. Its confirmed metadata is shown in the inspector.</p>}
      </form>
      </details>
      {state.uploadMessage && <p role="alert">{state.uploadMessage}</p>}
      </details>
    </section>
    <div className="workspace-layout">
      <section className="panel" aria-labelledby="evidence-heading" aria-busy={state.status === 'loading'}>
        <div className="section-heading"><div><span className="section-label">SOURCE LIBRARY</span><h2 id="evidence-heading">Case evidence</h2></div><button ref={addButton} hidden={readOnly} type="button" className="button-primary" aria-expanded={intakeOpen} aria-controls="evidence-intake" onClick={() => { setIntakeOpen(true); requestAnimationFrame(() => document.getElementById('batch-evidence-files')?.focus()); }}>＋ Add evidence</button></div>
        <p>Choose a source to inspect its original, process its contents, and verify observations.</p>
        <div className="evidence-toolbar">
          <label className="search-field">Search evidence<input type="search" placeholder="Filename, label, ID or hash…" value={query} onChange={event => setQuery(event.target.value)} /></label>
          <label>Kind<select value={kind} onChange={event => setKind(event.target.value)}><option value="all">All kinds</option>{evidenceKinds.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
          <label>Sort by<select value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Newest first</option><option value="name">Source name</option><option value="size">Largest first</option></select></label>
        </div>
        <p className="filter-scope">Search, kind and sorting apply to this page.</p>
        {state.status === 'loading' && <p role="status">Loading evidence...</p>}
        {state.status === 'error' && <p role="alert">{state.message}</p>}
        {state.status === 'ready' && page && <>
          <p role="status">{page.total} evidence items. Showing {page.items.length} on this page.</p>
          {page.items.length === 0 && <p>{page.total === 0 ? 'No evidence uploaded yet for this case' : 'No evidence on this page. Return to the previous page or refresh.'}</p>}
          {page.items.length > 0 && visible.length === 0 && <div className="empty-state"><h3>No matching evidence</h3><p>Try another filename or kind, or check another page.</p><button onClick={() => { setQuery(''); setKind('all'); }}>Clear filters</button></div>}
          {visible.length > 0 && <div className="evidence-table-scroll" role="region" aria-label="Evidence library" tabIndex={0}><table className="evidence-table">
            <thead><tr><th scope="col">Source / filename</th><th scope="col">Kind</th><th scope="col">Size</th><th scope="col">Added</th></tr></thead>
            <tbody>{visible.map(item => <tr key={item.id} className={state.detail?.id === item.id ? 'selected-row' : ''}>
              <td><button className="source-button" type="button" onClick={() => select(item.id)} aria-pressed={state.detail?.id === item.id}>{item.source_label}</button><span className="source-filename">{item.filename}</span></td>
              <td><span className="kind-badge">{item.kind.replaceAll('_', ' ')}</span></td>
              <td className="size-cell">{formatFileSize(item.size_bytes)}</td>
              <td><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</time></td>
            </tr>)}</tbody>
          </table></div>}
          <nav className="pagination" aria-label="Evidence pages">
            <button onClick={() => load(Math.max(0, page.offset - page.limit))} disabled={page.offset === 0 || state.submitting}>Previous</button>
            <button onClick={() => load(page.offset + page.limit)} disabled={page.offset + page.limit >= page.total || state.submitting}>Next</button>
          </nav>
        </>}
        <button type="button" onClick={() => load(0)} disabled={state.submitting}>Refresh evidence</button>
      </section>
      <aside className="panel inspector" aria-labelledby="evidence-inspector" aria-busy={state.detailStatus === 'loading'}>
        <h2 id="evidence-inspector" ref={heading} tabIndex={-1}>Inspect the source</h2>
        {state.detailStatus === 'idle' && <div className="inspector-empty"><span aria-hidden="true">↗</span><h3>Select a source</h3><p>Select evidence to inspect its metadata.</p><p>Original file, integrity hash, processing controls and extracted observations appear here.</p></div>}
        {state.detailStatus === 'loading' && <p role="status">Loading evidence metadata...</p>}
        {state.detailStatus === 'error' && <p role="alert">{state.detailMessage} Select evidence again to retry.</p>}
        {state.detail && <><h3>{state.detail.source_label}</h3><p className="format-support">{formatSupport(state.detail.filename, state.detail.kind)}</p><details className="source-integrity"><summary>Integrity and acquisition details</summary><Metadata item={state.detail} detailed /></details><OriginalDownload key={state.detail.id} item={state.detail} />
          <OriginalTextPreview key={`original:${state.detail.id}`} item={state.detail} />
          <EvidenceProcessingInspection key={`${state.detail.case_id}:${state.detail.id}`} item={state.detail} sourceFocus={sourceFocus} /></>}
      </aside>
    </div>
  </div>;
}

/** Selection-keyed lifetime also discards the previous completion/pin on evidence switches. */
export function EvidenceProcessingInspection({ item, sourceFocus }: { item: Evidence; sourceFocus?: SourceFocus }) {
  const [completedRunId, setCompletedRunId] = useState<string>();
  const [transcriptRefreshKey, setTranscriptRefreshKey] = useState<string>();
  const [pinnedRunId, setPinnedRunId] = useState<string>();
  const onProcessingCompleted = useCallback((runId: string) => {
    setCompletedRunId(runId); setTranscriptRefreshKey(runId);
  }, []);
  return <>
    <div className="extraction-heading"><h3>Extract and inspect</h3><p>Processing derives observations from the original. Review the source before relying on an extraction.</p></div>
    <StartProcessing caseId={item.case_id} evidenceId={item.id} sourceKind={item.kind} filename={item.filename} onCompleted={onProcessingCompleted} />
    {completedRunId && <label><input type="checkbox" checked={pinnedRunId !== undefined} onChange={event => setPinnedRunId(event.target.checked ? completedRunId : undefined)} />
      Pin observations to completed run {pinnedRunId ?? completedRunId}
    </label>}
    {sourceFocus && <p className="source-focus">Citation locator: <strong>{sourceFocus.source_locator}</strong>{sourceFocus.observation_id && <span className="identifier"> · {sourceFocus.observation_id}</span>}</p>}
    {(item.kind === 'image' || item.kind === 'video') && <MediaInspector item={item} onDerivedRun={onProcessingCompleted} processingRunId={pinnedRunId} refreshKey={completedRunId} focus={sourceFocus} />}
    <ObservationInspector focus={sourceFocus} caseId={item.case_id} evidenceId={item.id}
      processingRunId={pinnedRunId} refreshKey={pinnedRunId ?? completedRunId} />
    {(item.kind === 'audio' || item.kind === 'video') && <TranscriptViewer item={item}
      refreshKey={transcriptRefreshKey} onDerivedRun={setCompletedRunId} />}
  </>;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
