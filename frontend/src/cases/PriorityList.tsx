import './PriorityList.css';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createTriageController } from './triageController';
import type { TriageState } from './triageController';

type OverrideActions = Partial<Pick<ReturnType<typeof createTriageController>, 'updateOverride' | 'submitOverride'>>;

export function PriorityList({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const controller = useMemo(() => createTriageController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <PriorityListPanel state={state} load={controller.load} loadHistory={controller.loadHistory} inspectEvidence={inspectEvidence}
    updateOverride={controller.updateOverride} submitOverride={controller.submitOverride} />;
}

export function PriorityListPanel({ state, load, loadHistory, inspectEvidence, updateOverride, submitOverride }: {
  state: TriageState; load: (offset?: number) => Promise<void>; loadHistory?: (evidenceId: string) => Promise<void>;
  inspectEvidence?: (id: string) => void;
} & OverrideActions) {
  const page = state.page;
  const source = (id: string) => inspectEvidence ?
    <button type="button" className="identifier" onClick={() => inspectEvidence(id)} aria-label={`Inspect source evidence ${id}`}>{id}</button> : id;
  const overrideDetails = (evidenceId: string, effectivePriority?: 'P1' | 'P2' | 'P3' | 'P4') => {
    if (!updateOverride || !submitOverride) return null;
    const draft = state.overrides[evidenceId];
    const busy = draft?.status === 'submitting';
    const errorId = `override-error-${evidenceId}`;
    return <details className="override-details">
      <summary aria-label={`Override priority for evidence ${evidenceId}`}>Manual priority override</summary>
      <form noValidate aria-label={`Set priority override for evidence ${evidenceId}`} aria-busy={busy} onSubmit={event => {
        event.preventDefault(); void submitOverride(evidenceId);
      }}>
        <fieldset disabled={busy}>
          <legend>Set effective priority</legend>
          <label htmlFor={`override-priority-${evidenceId}`}>Target priority</label>
          <select id={`override-priority-${evidenceId}`} name="priority" value={draft?.priority ?? effectivePriority ?? 'P1'}
            onChange={event => updateOverride(evidenceId, { priority: event.currentTarget.value as NonNullable<typeof draft>['priority'] })}>
            {(['P1', 'P2', 'P3', 'P4'] as const).map(priority => <option key={priority} value={priority}>{priority}</option>)}
          </select>
          <label htmlFor={`override-reason-${evidenceId}`}>Reason (required)</label>
          <textarea id={`override-reason-${evidenceId}`} name="reason" required rows={3} value={draft?.reason ?? ''}
            aria-invalid={draft?.status === 'error' && !draft.reason.trim()}
            aria-describedby={draft?.status === 'error' ? errorId : undefined}
            onChange={event => updateOverride(evidenceId, { reason: event.currentTarget.value })} />
          <button type="submit">Set priority override</button>
          {draft?.status === 'error' && <button type="submit">Retry priority override</button>}
        </fieldset>
        {busy && <p role="status">Setting priority override...</p>}
        {draft?.status === 'error' && <p id={errorId} role="alert">{draft.message}</p>}
        {draft?.status === 'success' && <p role="status">{draft.message}</p>}
      </form>
    </details>;
  };
  const historyDetails = (evidenceId: string) => {
    const history = state.histories?.[evidenceId];
    return loadHistory && <details className="triage-history-details" onToggle={event => {
      if (event.currentTarget.open) void loadHistory(evidenceId);
    }}>
      <summary aria-label={`Priority history for evidence ${evidenceId}`}>Priority history</summary>
      <div aria-busy={history?.status === 'loading'}>
        {!history && <p>Open to load evaluation history.</p>}
        {history?.status === 'loading' && <p role="status">Loading priority history...</p>}
        {history?.status === 'error' && <>
          <p role="alert">{history.message}</p>
          <button type="button" onClick={() => { void loadHistory(evidenceId); }}>Retry priority history</button>
        </>}
        {history?.status === 'ready' && (history.items.length === 0 ?
          <p>No historical evaluations for this evidence item.</p> : <>
            <p>Automated evaluations, oldest first. Changes compare consecutive evaluations.</p>
            <ol className="triage-history-list">{history.items.map((result, index) => {
              const previous = history.items[index - 1];
              return <li key={result.id}>
                <h3>Evaluation {index + 1}{index === history.items.length - 1 && ' (latest evaluation)'}</h3>
                <p className="identifier">Analysis Run UUID: {result.analysis_run_id}</p>
                {result.analysis_run_id === page?.analysis_run_id && <p>Selected analysis run</p>}
                <p>Timestamp: <time dateTime={result.created_at}>{result.created_at}</time></p>
                <p>Score: {result.score.toFixed(2)} · Priority: <strong className={`priority-badge priority-${result.priority.toLowerCase()}`}>{result.priority}</strong></p>
                {previous && <div className="triage-history-change">
                  <p>{previous.priority === result.priority ? `Priority unchanged: ${result.priority}` :
                    `${result.priority < previous.priority ? '↑' : '↓'} ${result.priority} from ${previous.priority}`}</p>
                  <p>Score change: {previous.score.toFixed(2)} → {result.score.toFixed(2)}</p>
                </div>}
                <p>{result.explanation}</p>
                <h4>Factor breakdown</h4>
                {result.factors.length === 0 ? <p>No contributing factors for this evaluation.</p> :
                  <ul>{result.factors.map(factor => <li key={factor.name}>
                    <strong>{factor.name.replaceAll('_', ' ')}</strong>: {factor.contribution.toFixed(2)} points
                    {' '}(value {factor.value}, weight {factor.weight}). {factor.explanation}
                    {factor.evidence_ids.length > 0 && <p className="identifier">Supporting evidence: {factor.evidence_ids.map(id => <span key={id}>{source(id)}{' '}</span>)}</p>}
                  </li>)}</ul>}
              </li>;
            })}</ol>
          </>)}
      </div>
    </details>;
  };
  return <section className="panel priority-list" aria-label="Triage & Priority" aria-busy={state.status === 'loading'}>
    <h2>Priorities</h2>
    <details className="context-help"><summary>How priority works</summary><p>Priority guides investigative attention; it does not establish truth, identity or guilt. Order follows computed scores; live overrides do not reorder evidence.</p></details>
    {state.status === 'loading' && <p role="status">Loading priority list...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry priority list</button>}
    {state.status === 'ready' && page && <>
      {page.analysis_run_id ? <details className="technical-details"><summary>Analysis reference</summary><p className="identifier">{page.analysis_run_id}</p></details> :
        <p>No completed analysis selected. This is a live list of uploads, not a scored snapshot.</p>}
      <p className="sr-only" role="status">{page.total} triage items. {page.items.length ? `Showing ${page.offset + 1}–${page.offset + page.items.length}.` : 'Showing 0 items on this page.'}</p>
      {page.items.length === 0 ? <p>{page.total === 0 ? 'No triage items exist in this selection.' : 'No triage items on this page. Return to the previous page.'}</p> :
        <div className="priority-table-region" role="region" aria-label="Evidence priority table" tabIndex={0}><table>
          <caption>Evidence priority and automated factor contributions</caption>
          <thead><tr>{['Evidence ID', 'Priority', 'Score', 'Contributing Factors', 'Explanation', 'Effective Priority'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{page.items.map(entry => <tr key={entry.evidence_id}>
            <th scope="row" className="identifier">{source(entry.evidence_id)}</th>
            <td className={entry.latest_result ? undefined : 'unprocessed-cell'}>{entry.latest_result ? <>
              <span className="priority-origin">Computed</span>
              <strong className={`priority-badge priority-${entry.latest_result.priority.toLowerCase()}`} aria-label={`Computed priority ${entry.latest_result.priority}`}>{entry.latest_result.priority}</strong>
            </> : 'Unprocessed / Not Scored'}</td>
            <td>{entry.latest_result?.score.toFixed(2)}</td>
            <td>{entry.latest_result && <details className="factor-details"><summary>{entry.latest_result.factors.length} contributing factors</summary><ul>{entry.latest_result.factors.map(factor => <li key={factor.name}>
              <strong>{factor.name.replaceAll('_', ' ')}</strong>: {factor.contribution.toFixed(2)} points
              {' '}(value {factor.value}, weight {factor.weight}). {factor.explanation}
              {factor.evidence_ids.length > 0 && <p className="identifier">Supporting evidence: {factor.evidence_ids.map(id => <span key={id}>{source(id)}{' '}</span>)}</p>}
            </li>)}</ul></details>}</td>
            <td>{entry.latest_result && <details className="explanation-details"><summary>View explanation</summary><p>{entry.latest_result.explanation}</p></details>}
              {historyDetails(entry.evidence_id)}
            </td>
            <td>{entry.effective_priority ? <strong className={`priority-badge priority-${entry.effective_priority.toLowerCase()}`}
              aria-label={`Effective priority ${entry.effective_priority}`}>{entry.effective_priority}</strong> : 'Not assigned'}
              {entry.override && <> (live override)
                <p className="override-reason">{entry.override.reason}</p>
                <p className="identifier">Author: {entry.override.actor_id}</p>
                <p>Timestamp: <time dateTime={entry.override.created_at}>{entry.override.created_at}</time></p>
              </>}
              {overrideDetails(entry.evidence_id, entry.effective_priority)}
            </td>
          </tr>)}</tbody>
        </table></div>}
      <nav hidden={!!page && page.total <= page.limit} className="pagination" aria-label="Triage pages">
        <button type="button" disabled={page.offset === 0} onClick={() => { void load(Math.max(0, page.offset - page.limit)); }}>Previous</button>
        <button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => { void load(page.offset + page.limit); }}>Next</button>
        <button type="button" onClick={() => { void load(0); }}>Refresh priorities</button>
      </nav>
    </>}
  </section>;
}
