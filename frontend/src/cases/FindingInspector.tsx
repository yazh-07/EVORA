import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createFindingController } from './findingController';
import type { FindingState } from './findingController';
import { FindingKindFilter } from './InvestigationTabs';
import type { FindingKindFilterValue } from './InvestigationTabs';
import { ConflictPanel } from './ConflictPanel';
import { GapPanel } from './GapPanel';
import { ClusterPanel } from './ClusterPanel';
import { AnomalyPanel } from './AnomalyPanel';
import { HypothesisPanel } from './HypothesisPanel';
import { groupFindingViews } from './findingPresentation';
import { ReliabilityInspector } from './ReliabilityInspector';

type ReviewActions = Partial<Pick<ReturnType<typeof createFindingController>, 'loadReviews' | 'updateReview' | 'submitReview'>>;

export function FindingInspector({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const [findingKind, setFindingKind] = useState<FindingKindFilterValue>('all');
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const controller = useMemo(() => createFindingController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  // Latest discovery must become the shared pin before any results are displayed.
  const visible = state.page?.analysis_run_id && state.page.analysis_run_id !== analysis_run_id ?
    { ...state, status: 'loading' as const, page: null } : state;
  return <FindingPanel readOnly={client.getUser()?.role === 'reviewer'} state={visible} load={controller.load} select={controller.select} inspectEvidence={inspectEvidence}
    findingKind={findingKind} onKindChange={setFindingKind}
    loadReviews={controller.loadReviews} updateReview={controller.updateReview} submitReview={controller.submitReview} />;
}

export function FindingPanel({ state, load, select, inspectEvidence, loadReviews, updateReview, submitReview, findingKind = 'all', onKindChange, readOnly = false }: {
  readOnly?: boolean;
  state: FindingState; load: (offset?: number) => Promise<void>; select: (id: string) => Promise<void>;
  inspectEvidence?: (id: string) => void;
  findingKind?: FindingKindFilterValue; onKindChange?: (kind: FindingKindFilterValue) => void;
} & ReviewActions) {
  const page = state.page;
  const findings = page?.items.filter(f => findingKind === 'all' || f.kind === findingKind) ?? [];
  const cards = findingKind === 'all' ? groupFindingViews(findings) : findings.map(primary => ({ primary, related: [] }));
  const selectedFinding = findings.find(f => f.id === state.selectedId);
  const source = (id: string, index = 0) => inspectEvidence ? <button type="button" className="identifier"
    onClick={() => inspectEvidence(id)} aria-label={`Inspect source evidence ${id}`}>Open source {index + 1} ↗</button> : <span className="identifier">{id}</span>;
  const reviewDetails = (findingId: string) => {
    if (!loadReviews || !updateReview || !submitReview) return null;
    const review = state.reviews[findingId];
    const busy = review?.status === 'loading' || review?.submitStatus === 'submitting';
    const errorId = `review-error-${findingId}`;
    return <details className="finding-review-details" onToggle={event => {
      if (event.currentTarget.open) void loadReviews(findingId);
    }}>
      <summary aria-label={`Human reviews for finding ${findingId}`}>Human reviews</summary>
      <div aria-busy={busy}>
        {(!review || review.status === 'idle') && <p>Open to load human reviews.</p>}
        {review?.status === 'loading' && <p role="status">Loading human reviews...</p>}
        {review?.status === 'error' && <>
          <p role="alert">{review.message}</p>
          <button type="button" onClick={() => { void loadReviews(findingId); }}>Retry human reviews</button>
        </>}
        {review?.status === 'ready' && (review.items.length === 0 ? <p>No human reviews recorded yet.</p> : <>
          <p>Human reviews, oldest first.</p>
          <ol className="finding-review-list">{review.items.map(item => <li key={item.id}>
            <strong className="finding-review-badge">{item.decision}</strong>
            <p className="finding-review-reason">{item.reason}</p>
            <p className="identifier">Reviewer: {item.actor_id}</p>
            <p>Timestamp: <time dateTime={item.created_at}>{item.created_at}</time></p>
          </li>)}</ol>
        </>)}
        <form noValidate aria-label={`Submit human review for finding ${findingId}`} onSubmit={event => {
          event.preventDefault(); void submitReview(findingId);
        }}>
          <fieldset disabled={readOnly || review?.status !== 'ready' || busy}>
            <legend>Record a human review</legend>
            <label htmlFor={`review-decision-${findingId}`}>Decision</label>
            <select id={`review-decision-${findingId}`} name="decision" value={review?.decision ?? 'needs_investigation'}
              onChange={event => updateReview(findingId, { decision: event.currentTarget.value as NonNullable<typeof review>['decision'] })}>
              <option value="accepted">accepted</option>
              <option value="rejected">rejected</option>
              <option value="needs_investigation">needs_investigation</option>
            </select>
            <label htmlFor={`review-reason-${findingId}`}>Reason (required)</label>
            <textarea id={`review-reason-${findingId}`} name="reason" required rows={3} value={review?.reason ?? ''}
              aria-invalid={review?.submitStatus === 'error'} aria-describedby={review?.submitStatus === 'error' ? errorId : undefined}
              onChange={event => updateReview(findingId, { reason: event.currentTarget.value })} />
            <button type="submit">Submit review</button>
          </fieldset>
          {review?.submitStatus === 'submitting' && <p role="status">Submitting review...</p>}
          {review?.submitStatus === 'error' && <p id={errorId} role="alert">{review.submitMessage}</p>}
          {review?.submitStatus === 'success' && <p role="status">{review.submitMessage}</p>}
        </form>
      </div>
    </details>;
  };
  return <section className="panel findings-panel" aria-label="Findings" aria-busy={state.status === 'loading'}>
    <h2>Findings</h2>
    <p>Findings are investigative candidates requiring human verification. Confidence does not establish identity, source reliability or guilt. Missing information is unknown, not proof of non-occurrence.</p>
    <FindingKindFilter value={findingKind} onSelect={onKindChange} />
    {state.status === 'loading' && <p role="status">Loading findings...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry findings</button>}
    {state.status === 'ready' && page && <>
      {page.analysis_run_id ? <details className="technical-details"><summary>Selected analysis reference</summary><p className="identifier">{page.analysis_run_id}</p></details> :
        <p>No completed analysis run. Start analysis to generate findings.</p>}
      <p role="status">{page.total} findings. {page.items.length ? `Showing ${page.offset + 1}–${page.offset + page.items.length}.` : 'Showing 0 findings on this page.'}</p>
      {page.analysis_run_id && page.items.length === 0 && <p>{page.total === 0 ?
        'No findings in this completed analysis. This does not establish absence of relevant relationships.' : 'No findings on this page. Return to the previous page.'}</p>}
      {findingKind !== 'all' && <p role="status">{findings.length} {findingKind} findings on this page.
        {findings.length === 0 && ' No findings of this kind on this page.'}</p>}
      {cards.length < findings.length && <p className="scope-note">{cards.length} finding cards on this page. Alternate detector views with identical subjects and citations are folded below; each record retains its own sources and review.</p>}
      <ul className="findings-list">{cards.map(({ primary: f, related }) => <li key={f.id}>
        <strong className="finding-kind-badge">{f.kind}</strong>
        <h3>{f.summary}</h3>
        <details className="technical-details"><summary>Rule, score, and finding reference</summary><p className="identifier">Finding ID: {f.id}</p>
        <p>Confidence: {f.confidence.toFixed(2)} (reported score, 0–1)</p>
        <p>Rule: {f.rule}</p></details>
        {(f.kind === 'relationship' || f.kind === 'corroboration') && <>
        <p>Supporting sources</p><ul className="finding-source-actions">{f.evidence_ids.map((id, index) => <li key={id}>{source(id, index)}</li>)}</ul>
        <details className="technical-details"><summary>Observation references ({f.observation_ids.length})</summary><ul>{f.observation_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul></details>
        {!!f.contradicting_evidence_ids?.length && <><p>Contradicting evidence IDs:</p><ul>{f.contradicting_evidence_ids.map(id => <li key={id}>{source(id)}</li>)}</ul></>}
        {!!f.missing_information?.length && <><p>Missing information:</p><ul>{f.missing_information.map((text, i) => <li key={i}>{text}</li>)}</ul></>}
        </>}
        {f.kind !== 'relationship' && f.kind !== 'corroboration' && <details className="finding-analysis-details"><summary>Supporting evidence and limitations · {f.evidence_ids.length} sources</summary>
        {f.kind === 'conflict' && <ConflictPanel finding={f} citations={state.selectedId === f.id ? state.citations : []} inspectEvidence={inspectEvidence} />}
        {f.kind === 'gap' && <GapPanel finding={f} citations={state.selectedId === f.id ? state.citations : []} inspectEvidence={inspectEvidence} />}
        {f.kind === 'cluster' && <ClusterPanel finding={f} citations={state.selectedId === f.id ? state.citations : []} inspectEvidence={inspectEvidence} />}
        {f.kind === 'anomaly' && <AnomalyPanel finding={f} citations={state.selectedId === f.id ? state.citations : []} inspectEvidence={inspectEvidence} />}
        {f.kind === 'hypothesis' && <HypothesisPanel finding={f} citations={state.selectedId === f.id ? state.citations : []} inspectEvidence={inspectEvidence} />}
        </details>}
        <button type="button" aria-pressed={state.selectedId === f.id} onClick={() => { void select(f.id); }} aria-label={`Inspect finding sources ${f.id}`}>Inspect supporting records</button>
        {reviewDetails(f.id)}
        {related.length > 0 && <details><summary>Related detector views ({related.length})</summary>{related.map(item => <article key={item.id}>
          <strong>{item.kind}</strong><p>{item.summary}</p>
          <button type="button" onClick={() => { void select(item.id); }} aria-label={`Inspect finding sources ${item.id}`}>Inspect supporting records</button>
          {reviewDetails(item.id)}
        </article>)}</details>}
      </li>)}</ul>
      {selectedFinding && <aside aria-label="Finding source details" aria-busy={state.citationStatus === 'loading'}>
        <h3>Selected finding sources</h3>
        <p className="identifier">{state.selectedId}</p>
        {state.citationStatus === 'loading' && <p role="status">Loading frozen source citations...</p>}
        {state.citationMessage && <p role="alert">{state.citationMessage}</p>}
        {state.citationStatus === 'error' && <button type="button" onClick={() => { void select(state.selectedId!); }}>Retry finding sources</button>}
        {state.citationStatus === 'ready' && <><ul>{state.citations.map(c => <li key={c.id}>
          {source(c.evidence_id)}<p className="identifier">Observation: {c.id}; {c.source_locator}</p>
        </li>)}</ul>
        {[...new Set([...selectedFinding.evidence_ids, ...(selectedFinding.contradicting_evidence_ids ?? [])])].map(id =>
          <details className="finding-reliability" key={id}>
            <summary>Reliability and uncertainty for evidence <span className="identifier">{id}</span></summary>
            <ReliabilityInspector evidenceId={id} observations={state.citations} findings={page.items} inspectEvidence={inspectEvidence} />
          </details>)}
        </>}
      </aside>}
      <nav className="pagination" aria-label="Finding pages">
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
        <button type="button" onClick={() => { void load(0); }}>Refresh findings</button>
      </nav>
    </>}
  </section>;
}
