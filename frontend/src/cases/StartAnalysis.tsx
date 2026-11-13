import { confirmLeaveWorkspace } from '../ui/unsavedChanges';
import { createContext, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createAnalysisController, validAnalysisRun } from './analysisController';
import type { AnalysisState, AnalysisRun } from './analysisController';
import type { Case } from './store';

// Analytical views consume this one case-scoped pin for all reads/pages.
const AnalysisContext = createContext<{ caseId: string; analysis_run_id: string | null; selectCompletedRun: (id: string) => void; startAnalysis: () => Promise<void>; analysisBusy: boolean } | null>(null);
export function useAnalysisWorkspace() {
  const value = useContext(AnalysisContext);
  if (!value) throw new Error('Analysis views require a case analysis workspace.');
  return value;
}

export function CaseAnalysisWorkspace({ caseId, children, caseDetails, onBack }: {
  caseId: string; children: ReactNode; caseDetails?: Case; onBack?: () => void;
}) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, [caseId]);
  const client = useApiClient();
  const controller = useMemo(() => createAnalysisController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  const [history, setHistory] = useState<AnalysisRun[]>([]);
  const [historyError, setHistoryError] = useState(false);
  const [historyRevision, setHistoryRevision] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    const session = client.getSessionVersion();
    setHistoryError(false);
    void client.request('get', '/api/v1/cases/{caseId}/analysis-runs', { path: { caseId }, signal: request.signal })
      .then(runs => {
        if (request.signal.aborted || session !== client.getSessionVersion()) return;
        if (!Array.isArray(runs) || runs.some(run => !validAnalysisRun(run, caseId))) throw Error('Invalid history');
        const completed = runs.filter(run => run.status === 'completed').sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id.localeCompare(a.id));
        setHistory(completed);
        if (!controller.getSnapshot().pinnedAnalysisRunId && completed[0]) controller.selectCompletedRun(completed[0].id);
      }).catch(() => { if (!request.signal.aborted && session === client.getSessionVersion()) setHistoryError(true); });
    return () => request.abort();
  }, [client, caseId, controller, state.run?.status, historyRevision]);
  const startAnalysis = useMemo(() => async () => {
    if (client.getUser()?.role === 'reviewer' || !confirmLeaveWorkspace()) return;
    await controller.submit();
  }, [client, controller]);
  const analysisBusy = state.status === 'submitting' || state.status === 'polling';
  const value = useMemo(() => ({ caseId, analysis_run_id: state.pinnedAnalysisRunId, selectCompletedRun: controller.selectCompletedRun, startAnalysis, analysisBusy }), [caseId, state.pinnedAnalysisRunId, controller, startAnalysis, analysisBusy]);
  return <AnalysisContext.Provider value={value}>
    <header className={`panel case-header ${caseDetails ? 'case-header-active' : ''}`}>
      {caseDetails && <div className="case-heading">
        <button type="button" className="back-button" onClick={onBack}>← All Cases</button>
        <h1 ref={title} tabIndex={-1}>{caseDetails.title}</h1>
      </div>}
      <section className="analysis-action" aria-label="Analysis controls">
        <StartAnalysis state={state} submit={startAnalysis} readOnly={client.getUser()?.role === 'reviewer'} />
        <details className="analysis-history-menu"><summary>History</summary>
        {history.length ? <label>Results<select disabled={analysisBusy} value={state.pinnedAnalysisRunId ?? ''} onChange={event => { if (confirmLeaveWorkspace()) controller.chooseCompletedRun(event.target.value); }}>
          {!state.pinnedAnalysisRunId && <option value="">Choose an analysis</option>}
          {history.map((run, index) => <option key={run.id} value={run.id}>{index === 0 ? 'Latest · ' : ''}{new Date(run.created_at).toLocaleString('en-GB', { timeZone: 'UTC' })} UTC</option>)}
        </select></label> : <p>No completed analysis.</p>}
        {state.pinnedAnalysisRunId && <p className="identifier">{state.pinnedAnalysisRunId}</p>}
        </details>
        {historyError && <p role="alert">Could not load previous analyses. <button type="button" onClick={() => setHistoryRevision(value => value + 1)}>Retry history</button></p>}
      </section>
    </header>
    {children}
  </AnalysisContext.Provider>;
}

export function StartAnalysis({ state, submit, readOnly = false }: { state: AnalysisState; submit: () => Promise<void>; readOnly?: boolean }) {
  const busy = state.status === 'submitting' || state.status === 'polling';
  const run = state.run;
  const failed = state.status === 'terminal' && run?.status === 'failed';
  return <div className="analysis-controls" aria-busy={busy}>
    <button className="button-primary" type="button" title={readOnly ? 'Read-only access. An investigator can run analysis.' : undefined} disabled={busy || readOnly} onClick={() => { void submit(); }}>
      {state.status === 'submitting' ? 'Starting analysis...' : failed || state.status === 'error' ? 'Retry case analysis' : 'Run case analysis'}
    </button>

    {state.message && <p role="alert">{state.message}</p>}
    {run && (run.status === 'running' || run.status === 'queued') && <p className={`analysis-status status-${run.status}`} role="status">{run.status === 'queued' ? 'Queued…' : 'Analyzing…'}</p>}
    {failed && <p role="alert">Analysis failed: {run?.error}</p>}

  </div>;
}
