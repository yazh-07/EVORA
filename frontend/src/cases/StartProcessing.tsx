import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createProcessingController } from './processingController';
import type { ProcessingState } from './processingController';

export function StartProcessing({ caseId, evidenceId }: { caseId: string; evidenceId: string }) {
  const client = useApiClient();
  const controller = useMemo(() => createProcessingController(client, caseId, evidenceId), [client, caseId, evidenceId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return <StartProcessingPanel state={state} submit={controller.submit} />;
}

export function StartProcessingPanel({ state, submit }: { state: ProcessingState; submit: () => Promise<void> }) {
  const busy = state.status === 'submitting';
  return <div aria-busy={busy}>
    <button type="button" disabled={busy} onClick={() => { void submit(); }}>
      {busy ? 'Starting processing...' : 'Start processing'}
    </button>
    {state.message && <p role="alert">{state.message}</p>}
    {state.run && <div role="status">
      <p>Processing request accepted. Status at acceptance: {state.run.status}.</p>
      <p>Run ID: <span className="identifier">{state.run.id}</span></p>
      <p>This view does not refresh run status. Starting again requests a new run.</p>
    </div>}
  </div>;
}
