import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createAnalysisController } from './analysisController';
import type { AnalysisState } from './analysisController';

// Analytical views consume this one case-scoped pin for all reads/pages.
const AnalysisContext = createContext<{ caseId: string; analysis_run_id: string | null; selectCompletedRun: (id: string) => void } | null>(null);
export function useAnalysisWorkspace() {
  const value = useContext(AnalysisContext);
  if (!value) throw new Error('Analysis views require a case analysis workspace.');
  return value;
}

export function CaseAnalysisWorkspace({ caseId, children }: { caseId: string; children: ReactNode }) {
  const client = useApiClient();
  const controller = useMemo(() => createAnalysisController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  const value = useMemo(() => ({ caseId, analysis_run_id: state.pinnedAnalysisRunId, selectCompletedRun: controller.selectCompletedRun }), [caseId, state.pinnedAnalysisRunId, controller]);
  return <AnalysisContext.Provider value={value}>
    <section className="panel" aria-labelledby="analysis-heading">
      <h2 id="analysis-heading">Case analysis</h2>
      <StartAnalysis state={state} submit={controller.submit} />
    </section>
    {children}
  </AnalysisContext.Provider>;
}

export function StartAnalysis({ state, submit }: { state: AnalysisState; submit: () => Promise<void> }) {
  const busy = state.status === 'submitting' || state.status === 'polling';
  const run = state.run;
  const failed = state.status === 'terminal' && run?.status === 'failed';
  return <div aria-busy={busy}>
    <button type="button" disabled={busy} onClick={() => { void submit(); }}>
      {state.status === 'submitting' ? 'Starting analysis...' : failed || state.status === 'error' ? 'Retry analysis with new key' : 'Start Analysis'}
    </button>
    {state.message && <p role="alert">{state.message}</p>}
    {run && <>
      <p role={failed ? 'alert' : 'status'}>{state.status === 'polling' && (run.status === 'completed' || run.status === 'failed') ? 'Confirming analysis status...' :
        run.status === 'queued' ? 'Queued' : run.status === 'running' ? 'Analyzing case evidence...' :
          run.status === 'completed' ? 'Analysis completed' : `Analysis failed: ${run.error}`}</p>
      <p className="identifier">Analysis run: {run.id}</p>
    </>}
    {state.pinnedAnalysisRunId && <p className="identifier">Selected completed analysis: {state.pinnedAnalysisRunId}</p>}
    <p>Analysis supports investigation and requires human verification. Each start or retry uses a new request key.</p>
  </div>;
}
