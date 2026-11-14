import './PriorityList.css';
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { createTriageController } from './triageController';
import type { TriageState } from './triageController';
import { validEvidence } from './evidenceStore';
import type { components } from '../api/schema';

type Factor = components['schemas']['TriageFactor'];
const factorLabels: Record<string, string> = { relevance: 'Case matches', connectivity: 'Connections', corroboration: 'Independent support', gap_relevance: 'Coverage gaps', source_quality: 'Source assessment', conflict_relevance: 'Conflicting records', temporal_proximity: 'Time proximity' };
const label = (factor: Factor) => factorLabels[factor.name] ?? factor.name.replaceAll('_', ' ');
const activeFactors = (factors: Factor[]) => factors.filter(factor => factor.contribution > 0).sort((a, b) => b.contribution - a.contribution);
const basis = (factor: Factor) => factor.explanation
  .replace(/\s*Investigative attention only; not truth, identity or guilt\.\s*$/, '')
  .replace(' (86400-second policy window)', '')
  .replace(/: additional distinct origin groups divided by 3, capped at 1; duplicate bytes\/origins\/records collapse\./, '.')
  .replace('; basis/version retained by the assessor.', '.').trim();
const dateLabel = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' });

type OverrideActions = Partial<Pick<ReturnType<typeof createTriageController>, 'updateOverride' | 'submitOverride'>>;

export function PriorityList({ inspectEvidence }: { inspectEvidence?: (id: string) => void }) {
  const client = useApiClient();
  const { caseId, analysis_run_id, selectCompletedRun } = useAnalysisWorkspace();
  const [sourceNames, setSourceNames] = useState<Record<string, string>>({});
  useEffect(() => {
    const request = new AbortController(); setSourceNames({});
    void (async () => {
      const names: Record<string, string> = {}; let offset = 0, total: number | undefined;
      do {
        const page = await client.request('get', '/api/v1/cases/{caseId}/evidence', { path: { caseId }, query: { limit: 100, offset }, signal: request.signal });
        if (page.limit !== 100 || page.offset !== offset || !Number.isSafeInteger(page.total) || page.total < offset ||
            (total !== undefined && total !== page.total) || page.items.length !== Math.min(100, page.total - offset) || page.items.some(item => !validEvidence(item, caseId))) throw Error('Evidence changed');
        total = page.total;
        for (const item of page.items) names[item.id] = item.filename;
        offset += page.items.length;
      } while (offset < total);
      if (!request.signal.aborted) setSourceNames(names);
    })().catch(() => { /* Source actions remain usable if filenames cannot be loaded. */ });
    return () => request.abort();
  }, [client, caseId]);
  const controller = useMemo(() => createTriageController(client, caseId, analysis_run_id ?? undefined, selectCompletedRun),
    [client, caseId, analysis_run_id, selectCompletedRun]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <PriorityListPanel sourceNames={sourceNames} state={state} load={controller.load} loadHistory={controller.loadHistory} inspectEvidence={inspectEvidence}
    updateOverride={controller.updateOverride} submitOverride={controller.submitOverride} />;
}

export function PriorityListPanel({ state, load, loadHistory, inspectEvidence, sourceNames = {}, updateOverride, submitOverride }: {
  state: TriageState; load: (offset?: number) => Promise<void>; loadHistory?: (evidenceId: string) => Promise<void>;
  inspectEvidence?: (id: string) => void; sourceNames?: Record<string, string>;
} & OverrideActions) {
  const page = state.page;
  const source = (id: string) => inspectEvidence ?
    <button type="button" className="source-link" onClick={() => inspectEvidence(id)} aria-label={`Inspect ${sourceNames[id] ?? 'source'}`}>{sourceNames[id] ?? 'Open source'}</button> : (sourceNames[id] ?? 'Source');
  const reasons = (factors: Factor[], evidenceId: string) => {
    const contributing = activeFactors(factors);
    if (!contributing.length) return <span className="priority-muted">No positive review signals</span>;
    return <details className="factor-details"><summary>{contributing.map(label).join(' · ')}</summary>
      <ul className="priority-reasons">{contributing.map(factor => <li key={factor.name}>
        <div className="priority-factor-heading">{contributing.length > 1 && <strong>{label(factor)}</strong>}<span>+{factor.contribution.toFixed(2)} pts</span></div>
        <meter min={0} max={100} value={factor.contribution} aria-label={`${label(factor)} score contribution`} />
        <p>{basis(factor)}</p>
        {factor.evidence_ids.some(id => id !== evidenceId) && <div className="priority-related-sources">{factor.evidence_ids.filter(id => id !== evidenceId).map(id => <span key={id}>{source(id)}</span>)}</div>}
      </li>)}</ul>
    </details>;
  };
  const overrideDetails = (evidenceId: string, effectivePriority?: 'P1' | 'P2' | 'P3' | 'P4') => {
    if (!updateOverride || !submitOverride) return null;
    const draft = state.overrides[evidenceId];
    const busy = draft?.status === 'submitting';
    const errorId = `override-error-${evidenceId}`;
    return <details className="override-details">
      <summary aria-label={`Override priority for evidence ${evidenceId}`}>Change priority</summary>
      <form noValidate aria-label={`Set priority override for evidence ${evidenceId}`} aria-busy={busy} onSubmit={event => {
        event.preventDefault(); void submitOverride(evidenceId);
      }}>
        <fieldset disabled={busy}>
          <legend>Priority</legend>
          <label htmlFor={`override-priority-${evidenceId}`}>Priority</label>
          <select id={`override-priority-${evidenceId}`} name="priority" value={draft?.priority ?? effectivePriority ?? 'P1'}
            onChange={event => updateOverride(evidenceId, { priority: event.currentTarget.value as NonNullable<typeof draft>['priority'] })}>
            {(['P1', 'P2', 'P3', 'P4'] as const).map(priority => <option key={priority} value={priority}>{priority}</option>)}
          </select>
          <label htmlFor={`override-reason-${evidenceId}`}>Reason</label>
          <textarea id={`override-reason-${evidenceId}`} name="reason" required rows={3} value={draft?.reason ?? ''}
            aria-invalid={draft?.status === 'error' && !draft.reason.trim()}
            aria-describedby={draft?.status === 'error' ? errorId : undefined}
            onChange={event => updateOverride(evidenceId, { reason: event.currentTarget.value })} />
          <button type="submit">Save priority</button>
          {draft?.status === 'error' && <button type="submit">Retry priority override</button>}
        </fieldset>
        {busy && <p role="status">Saving priority…</p>}
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
      <summary aria-label={`Priority history for evidence ${evidenceId}`}>Score history</summary>
      <div aria-busy={history?.status === 'loading'}>
        {history?.status === 'loading' && <p role="status">Loading priority history…</p>}
        {history?.status === 'error' && <><p role="alert">{history.message}</p><button type="button" onClick={() => { void loadHistory(evidenceId); }}>Retry priority history</button></>}
        {history?.status === 'ready' && (history.items.length === 0 ? <p>No earlier scores.</p> :
          <ol className="triage-history-list">{[...history.items].reverse().map((result, reverseIndex) => {
            const index = history.items.length - 1 - reverseIndex;
            const previous = history.items[index - 1];
            const changes = result.factors.flatMap(factor => {
              const before = previous?.factors.find(value => value.name === factor.name)?.contribution ?? 0;
              const delta = factor.contribution - before;
              return previous && Math.abs(delta) >= .005 ? [`${label(factor)} ${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(2)} pts`] : [];
            });
            if (previous) for (const factor of previous.factors) {
              if (factor.contribution > 0 && !result.factors.some(value => value.name === factor.name)) changes.push(`${label(factor)} −${factor.contribution.toFixed(2)} pts`);
            }
            return <li key={result.id}>
              <div className="priority-history-heading"><strong className={`priority-badge priority-${result.priority.toLowerCase()}`}>{result.priority}</strong><time dateTime={result.created_at}>{dateLabel(result.created_at)}</time>{result.analysis_run_id === page?.analysis_run_id && <span className="kind-badge">Selected</span>}</div>
              <p className="priority-history-score">{previous ? `${previous.score.toFixed(2)} → ${result.score.toFixed(2)} pts` : `${result.score.toFixed(2)} pts`}{previous && previous.priority !== result.priority && ` · ${previous.priority} → ${result.priority}`}</p>
              {changes.length > 0 ? <p>{changes.join(' · ')}</p> : <p className="priority-muted">{previous ? 'No score changes' : activeFactors(result.factors).map(label).join(' · ') || 'No positive review signals'}</p>}
            </li>;
          })}</ol>)}
      </div>
    </details>;
  };
  return <section className="panel priority-list" aria-label="Triage & Priority" aria-busy={state.status === 'loading'}>
    <h2>Priorities</h2>
    {state.status === 'loading' && <p role="status">Loading priority list...</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {state.status === 'error' && <button type="button" onClick={() => { void load(); }}>Retry priority list</button>}
    {state.status === 'ready' && page && <>
      {!page.analysis_run_id && <p>Run case analysis to calculate priorities.</p>}
      <p className="sr-only" role="status">{page.total} triage items. {page.items.length ? `Showing ${page.offset + 1}–${page.offset + page.items.length}.` : 'Showing 0 items on this page.'}</p>
      {page.items.length === 0 ? <p>{page.total === 0 ? 'No evidence to prioritize.' : 'No sources on this page.'}</p> :
        <div className="priority-table-region" role="region" aria-label="Evidence priority table" tabIndex={0}><table>
          <caption className="sr-only">Evidence review priorities</caption>
          <thead><tr>{['Source', 'Priority', 'Score', 'Why flagged', 'Actions'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{page.items.map(entry => <tr key={entry.evidence_id}>
            <th scope="row">{source(entry.evidence_id)}</th>
            <td>{entry.effective_priority ? <strong className={`priority-badge priority-${entry.effective_priority.toLowerCase()}`} aria-label={`Effective priority ${entry.effective_priority}`}>{entry.effective_priority}</strong> : <span className="priority-muted">Not scored</span>}
              {entry.override && <span className="priority-origin">Manual{entry.latest_result ? ` · automatic ${entry.latest_result.priority}` : ''}</span>}
            </td>
            <td>{entry.latest_result ? <span title="Review score out of 100">{entry.latest_result.score.toFixed(2)}</span> : '—'}</td>
            <td>{entry.latest_result ? reasons(entry.latest_result.factors, entry.evidence_id) : <span className="priority-muted">Awaiting analysis</span>}
              {entry.override && <p className="override-reason">{entry.override.reason}</p>}
            </td>
            <td>{historyDetails(entry.evidence_id)}{overrideDetails(entry.evidence_id, entry.effective_priority)}</td>
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
