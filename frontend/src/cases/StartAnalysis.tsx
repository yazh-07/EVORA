import { CaseMetrics } from './CaseMetrics';
import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createAnalysisController } from './analysisController';
import type { AnalysisState } from './analysisController';
import type { Case } from './store';

// Analytical views consume this one case-scoped pin for all reads/pages.
const AnalysisContext = createContext<{ caseId: string; analysis_run_id: string | null; selectCompletedRun: (id: string) => void } | null>(null);
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
  const value = useMemo(() => ({ caseId, analysis_run_id: state.pinnedAnalysisRunId, selectCompletedRun: controller.selectCompletedRun }), [caseId, state.pinnedAnalysisRunId, controller]);
  return <AnalysisContext.Provider value={value}>
    <header className={`panel case-header ${caseDetails ? 'case-header-active' : ''}`}>
      {caseDetails && <div className="case-heading">
        <button type="button" className="back-button" onClick={onBack}>← All Cases</button>
        <h1 ref={title} tabIndex={-1}>{caseDetails.title}</h1>
        <span className="identifier case-id-badge">{caseDetails.id}</span>
        <p>{caseDetails.description || 'No description provided.'}</p>
      </div>}
      <section className="analysis-action" aria-labelledby="analysis-heading">
        <h2 id="analysis-heading">Case analysis</h2>
        <StartAnalysis state={state} submit={controller.submit} />
      </section>
    </header>
    {caseDetails && <CaseMetrics />}
    {children}
  </AnalysisContext.Provider>;
}

export function StartAnalysis({ state, submit }: { state: AnalysisState; submit: () => Promise<void> }) {
  const busy = state.status === 'submitting' || state.status === 'polling';
  const run = state.run;
  const failed = state.status === 'terminal' && run?.status === 'failed';
  return <div className="analysis-controls" aria-busy={busy}>
    <button className="button-primary" type="button" disabled={busy} onClick={() => { void submit(); }}>
      {state.status === 'submitting' ? 'Starting analysis...' : failed || state.status === 'error' ? 'Retry analysis with new key' : 'Start Analysis'}
    </button>
    {state.message && <p role="alert">{state.message}</p>}
    {run && <p className={`analysis-status status-${run.status}`} role={failed ? 'alert' : 'status'}>{state.status === 'polling' && (run.status === 'completed' || run.status === 'failed') ? 'Confirming analysis status...' :
        run.status === 'queued' ? 'Queued' : run.status === 'running' ? 'Analyzing case evidence...' :
          run.status === 'completed' ? 'Analysis completed' : `Analysis failed: ${run.error}`}</p>}
    {!run && state.status === 'idle' && <p className="analysis-status" role="status">{state.pinnedAnalysisRunId ? 'Completed analysis selected' : 'No analysis selected'}</p>}
    <details className="analysis-details">
      <summary>Analysis context</summary>
      {run && <p className="identifier">Analysis run: {run.id}</p>}
      {state.pinnedAnalysisRunId && <p className="identifier">Selected completed analysis: {state.pinnedAnalysisRunId}</p>}
      <p>Analysis supports investigation and requires human verification. Each start or retry uses a new request key.</p>
    </details>
  </div>;
}
