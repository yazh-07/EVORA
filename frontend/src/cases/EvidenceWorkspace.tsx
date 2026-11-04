import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ObservationInspector } from './ObservationInspector';
import { OriginalDownload } from './OriginalDownload';
import { StartProcessing } from './StartProcessing';
import { useApiClient } from '../api/ApiProvider';
import { createEvidenceStore, evidenceKinds } from './evidenceStore';
import type { Evidence, EvidenceState } from './evidenceStore';

export function EvidenceWorkspace({ caseId, sourceSelection }: { caseId: string; sourceSelection?: { id: string } }) {
  const client = useApiClient();
  const store = useMemo(() => createEvidenceStore(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  useEffect(() => { void store.start(); return () => store.dispose(); }, [store]);
  useEffect(() => { if (sourceSelection) void store.select(sourceSelection.id); }, [store, sourceSelection]);
  return <>{sourceSelection && <p role="status">Source evidence inspection shows live metadata and processing outputs, separately from the selected analysis snapshot.</p>}<EvidencePanels state={state} load={offset => { void store.load(offset); }} select={id => { void store.select(id); }} upload={store.upload} /></>;
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
export function EvidencePanels({ state, load, select, upload }: {
  state: EvidenceState; load: (offset: number) => void; select: (id: string) => void;
  upload: (file: File | null, kind: string, label: string, acquiredAt: string) => Promise<boolean>;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const error = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (state.uploadMessage) error.current?.focus(); }, [state.uploadMessage]);
  useEffect(() => { if (state.detailStatus === 'ready' || state.detailStatus === 'error') heading.current?.focus(); }, [state.detail, state.detailStatus]);
  const page = state.page;
  return <div className="evidence-workspace">
    <section className="panel intake-panel" aria-labelledby="upload-heading">
      <details className="intake-disclosure">
      <summary><h2 id="upload-heading">Upload evidence</h2><span>Add an original file to this case</span></summary>
      <p>Upload one original file. Intake stores its bytes and integrity metadata; content has not been verified.</p>
      <form className="upload-form" noValidate aria-busy={state.submitting} onSubmit={async event => {
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0] ?? null;
        if (await upload(file, String(data.get('kind')), String(data.get('source_label') ?? ''), String(data.get('acquired_at') ?? ''))) form.reset();
        else error.current?.focus();
      }}>
        <fieldset disabled={state.submitting}>
          <legend>Original file and source</legend>
          <label htmlFor="evidence-file">File (required)</label><input id="evidence-file" name="file" type="file" required />
          <label htmlFor="evidence-kind">Kind (required)</label><select id="evidence-kind" name="kind" required defaultValue="document">
            {evidenceKinds.map(kind => <option key={kind} value={kind}>{kind}</option>)}
          </select>
          <label htmlFor="evidence-label">Source label (required)</label><input id="evidence-label" name="source_label" type="text" required maxLength={200} />
          <label htmlFor="evidence-acquired">Acquired at (optional, UTC)</label><input id="evidence-acquired" name="acquired_at" type="datetime-local" step="1" aria-describedby="acquired-help" />
          <p id="acquired-help">Enter the acquisition time in UTC. Leave blank if unknown.</p>
          <button type="submit" disabled={state.submitting}>{state.submitting ? 'Uploading evidence...' : 'Upload evidence'}</button>
        </fieldset>
        {state.uploadMessage && <p role="alert" ref={error} tabIndex={-1}>{state.uploadMessage}</p>}
        {state.uploaded && <p role="status">Evidence uploaded. Its confirmed metadata is shown in the inspector.</p>}
      </form>
      </details>
    </section>
    <div className="workspace-layout">
      <section className="panel" aria-labelledby="evidence-heading" aria-busy={state.status === 'loading'}>
        <h2 id="evidence-heading">Case evidence</h2>
        {state.status === 'loading' && <p role="status">Loading evidence...</p>}
        {state.status === 'error' && <p role="alert">{state.message}</p>}
        {state.status === 'ready' && page && <>
          <p role="status">{page.total} evidence items. Showing {page.items.length} on this page.</p>
          {page.items.length === 0 && <p>{page.total === 0 ? 'No evidence uploaded yet for this case' : 'No evidence on this page. Return to the previous page or refresh.'}</p>}
          <ul className="evidence-list">{page.items.map(item => <li className="evidence-card" key={item.id}>
            <button type="button" onClick={() => select(item.id)} aria-pressed={state.detail?.id === item.id}>{item.source_label}</button>
            <Metadata item={item} />
          </li>)}</ul>
          <nav className="pagination" aria-label="Evidence pages">
            <button onClick={() => load(Math.max(0, page.offset - page.limit))} disabled={page.offset === 0 || state.submitting}>Previous</button>
            <button onClick={() => load(page.offset + page.limit)} disabled={page.offset + page.limit >= page.total || state.submitting}>Next</button>
          </nav>
        </>}
        <button type="button" onClick={() => load(0)} disabled={state.submitting}>Refresh evidence</button>
      </section>
      <aside className="panel inspector" aria-labelledby="evidence-inspector" aria-busy={state.detailStatus === 'loading'}>
        <h2 id="evidence-inspector" ref={heading} tabIndex={-1}>Evidence metadata</h2>
        {state.detailStatus === 'idle' && <p>Select evidence to inspect its metadata.</p>}
        {state.detailStatus === 'loading' && <p role="status">Loading evidence metadata...</p>}
        {state.detailStatus === 'error' && <p role="alert">{state.detailMessage} Select evidence again to retry.</p>}
        {state.detail && <><h3>{state.detail.source_label}</h3><Metadata item={state.detail} detailed /><OriginalDownload key={state.detail.id} item={state.detail} />
          <EvidenceProcessingInspection key={`${state.detail.case_id}:${state.detail.id}`} item={state.detail} /></>}
      </aside>
    </div>
  </div>;
}

/** Selection-keyed lifetime also discards the previous completion/pin on evidence switches. */
export function EvidenceProcessingInspection({ item }: { item: Evidence }) {
  const [completedRunId, setCompletedRunId] = useState<string>();
  const [pinnedRunId, setPinnedRunId] = useState<string>();
  return <>
    <StartProcessing caseId={item.case_id} evidenceId={item.id} onCompleted={setCompletedRunId} />
    {completedRunId && <label><input type="checkbox" checked={pinnedRunId !== undefined} onChange={event => setPinnedRunId(event.target.checked ? completedRunId : undefined)} />
      Pin observations to completed run {pinnedRunId ?? completedRunId}
    </label>}
    <ObservationInspector caseId={item.case_id} evidenceId={item.id}
      processingRunId={pinnedRunId} refreshKey={pinnedRunId ?? completedRunId} />
  </>;
}
