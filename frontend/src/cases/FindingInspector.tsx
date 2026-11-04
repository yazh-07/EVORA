import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createFindingController } from './findingController';
import type { FindingState } from './findingController';

export function FindingInspector({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const controller = useMemo(() => createFindingController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  // Latest discovery must become the shared pin before any results are displayed.
  const visible = state.page?.analysis_run_id && state.page.analysis_run_id !== analysis_run_id ?
    { ...state, status: 'loading' as const, page: null } : state;
  return <FindingPanel state={visible} load={controller.load} select={controller.select} inspectEvidence={inspectEvidence} />;
}

export function FindingPanel({ state, load, select, inspectEvidence }: {
  state: FindingState; load: (offset?: number) => Promise<void>; select: (id: string) => Promise<void>;
  inspectEvidence?: (id: string) => void;
}) {
  const page = state.page;
  const source = (id: string) => inspectEvidence ? <button type="button" className="identifier"
    onClick={() => inspectEvidence(id)} aria-label={`Inspect source evidence ${id}`}>{id}</button> : <span className="identifier">{id}</span>;
  return <section className="panel findings-panel" aria-label="Findings" aria-busy={state.status === 'loading'}>
    <h2>Findings</h2>
    <p>Findings are investigative candidates requiring human verification. Confidence does not establish identity, source reliability or guilt. Missing information is unknown, not proof of non-occurrence.</p>
    {state.status === 'loading' && <p role="status">Loading findings...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry findings</button>}
    {state.status === 'ready' && page && <>
      {page.analysis_run_id ? <p className="identifier">Selected completed analysis: {page.analysis_run_id}</p> :
        <p>No completed analysis run. Start analysis to generate findings.</p>}
      <p role="status">{page.total} findings. {page.items.length ? `Showing ${page.offset + 1}–${page.offset + page.items.length}.` : 'Showing 0 findings on this page.'}</p>
      {page.analysis_run_id && page.items.length === 0 && <p>{page.total === 0 ?
        'No findings in this completed analysis. This does not establish absence of relevant relationships.' : 'No findings on this page. Return to the previous page.'}</p>}
      <ul className="findings-list">{page.items.map(f => <li key={f.id}>
        <strong className="finding-kind-badge">{f.kind}</strong>
        <h3>{f.summary}</h3>
        <p className="identifier">Finding ID: {f.id}</p>
        <p>Confidence: {f.confidence.toFixed(2)} (reported score, 0–1)</p>
        <p>Rule: {f.rule}</p>
        <p>Supporting evidence IDs:</p><ul>{f.evidence_ids.map(id => <li key={id}>{source(id)}</li>)}</ul>
        <p>Supporting observation IDs:</p><ul>{f.observation_ids.map(id => <li key={id} className="identifier">{id}</li>)}</ul>
        {!!f.contradicting_evidence_ids?.length && <><p>Contradicting evidence IDs:</p><ul>{f.contradicting_evidence_ids.map(id => <li key={id}>{source(id)}</li>)}</ul></>}
        {!!f.missing_information?.length && <><p>Missing information:</p><ul>{f.missing_information.map((text, i) => <li key={i}>{text}</li>)}</ul></>}
        <button type="button" aria-pressed={state.selectedId === f.id} onClick={() => { void select(f.id); }}>Inspect finding sources {f.id}</button>
      </li>)}</ul>
      {state.selectedId && <aside aria-label="Finding source details" aria-busy={state.citationStatus === 'loading'}>
        <h3>Selected finding sources</h3>
        <p className="identifier">{state.selectedId}</p>
        {state.citationStatus === 'loading' && <p role="status">Loading frozen source citations...</p>}
        {state.citationMessage && <p role="alert">{state.citationMessage}</p>}
        {state.citationStatus === 'error' && <button type="button" onClick={() => { void select(state.selectedId!); }}>Retry finding sources</button>}
        {state.citationStatus === 'ready' && <ul>{state.citations.map(c => <li key={c.id}>
          {source(c.evidence_id)}<p className="identifier">Observation: {c.id}; {c.source_locator}</p>
        </li>)}</ul>}
      </aside>}
      <nav className="pagination" aria-label="Finding pages">
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
        <button type="button" onClick={() => { void load(0); }}>Refresh findings</button>
      </nav>
    </>}
  </section>;
}
