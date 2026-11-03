import './PriorityList.css';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createTriageController } from './triageController';
import type { TriageState } from './triageController';

export function PriorityList({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const controller = useMemo(() => createTriageController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <PriorityListPanel state={state} load={controller.load} inspectEvidence={inspectEvidence} />;
}

export function PriorityListPanel({ state, load, inspectEvidence }: { state: TriageState; load: (offset?: number) => Promise<void>; inspectEvidence?: (id: string) => void }) {
  const page = state.page;
  const source = (id: string) => inspectEvidence ?
    <button type="button" className="identifier" onClick={() => inspectEvidence(id)} aria-label={`Inspect source evidence ${id}`}>{id}</button> : id;
  return <section className="panel priority-list" aria-label="Triage & Priority" aria-busy={state.status === 'loading'}>
    <h2>Triage &amp; Priority</h2>
    <p>Priority guides investigative attention; it does not establish truth, identity or guilt. Order follows computed scores; live overrides do not reorder evidence.</p>
    {state.status === 'loading' && <p role="status">Loading priority list...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry priority list</button>}
    {state.status === 'ready' && page && <>
      {page.analysis_run_id ? <p className="identifier">Selected completed analysis: {page.analysis_run_id}</p> :
        <p>No completed analysis selected. This is a live list of uploads, not a scored snapshot.</p>}
      <p role="status">{page.total} triage items. {page.items.length ? `Showing ${page.offset + 1}–${page.offset + page.items.length}.` : 'Showing 0 items on this page.'}</p>
      {page.items.length === 0 ? <p>{page.total === 0 ? 'No triage items exist in this selection.' : 'No triage items on this page. Return to the previous page.'}</p> :
        <div className="priority-table-region" role="region" aria-label="Evidence priority table" tabIndex={0}><table>
          <caption>Evidence priority and automated factor contributions</caption>
          <thead><tr>{['Evidence ID', 'Priority', 'Score', 'Contributing Factors', 'Explanation', 'Effective Priority'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{page.items.map(entry => <tr key={entry.evidence_id}>
            <th scope="row" className="identifier">{source(entry.evidence_id)}</th>
            <td>{entry.latest_result ? <strong className="priority-badge">{entry.latest_result.priority}</strong> : 'Unprocessed / Not Scored'}</td>
            <td>{entry.latest_result?.score.toFixed(2)}</td>
            <td>{entry.latest_result && <ul>{entry.latest_result.factors.map(factor => <li key={factor.name}>
              <strong>{factor.name.replaceAll('_', ' ')}</strong>: {factor.contribution.toFixed(2)} points
              {' '}(value {factor.value}, weight {factor.weight}). {factor.explanation}
              {factor.evidence_ids.length > 0 && <p className="identifier">Supporting evidence: {factor.evidence_ids.map(id => <span key={id}>{source(id)}{' '}</span>)}</p>}
            </li>)}</ul>}</td>
            <td>{entry.latest_result?.explanation}</td>
            <td>{entry.override ? <><strong>{entry.effective_priority}</strong> (live override)<p>{entry.override.reason}</p></> : entry.effective_priority ?? 'Not assigned'}</td>
          </tr>)}</tbody>
        </table></div>}
      <nav className="pagination" aria-label="Triage pages">
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
        <button type="button" onClick={() => { void load(0); }}>Refresh priorities</button>
      </nav>
    </>}
  </section>;
}
