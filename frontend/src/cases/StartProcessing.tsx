import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createProcessingController, validRun } from './processingController';
import { ProcessingStatus } from './ProcessingStatus';
import type { ProcessingState } from './processingController';

export function StartProcessing({ caseId, evidenceId, sourceKind, filename, onCompleted }: { caseId: string; evidenceId: string; sourceKind?: string; filename?: string; onCompleted?: (runId: string) => void }) {
  const client = useApiClient();
  const edited = useRef(false);
  const [interpretation, setInterpretation] = useState<Parameters<typeof createProcessingController>[3]>();
  const controller = useMemo(() => createProcessingController(client, caseId, evidenceId, interpretation), [client, caseId, evidenceId, interpretation]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => {
    if (sourceKind !== 'document' || !filename?.toLowerCase().endsWith('.csv')) return;
    const request = new AbortController();
    void client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId }, signal: request.signal }).then(runs => {
      if (request.signal.aborted || edited.current) return;
      if (!Array.isArray(runs) || runs.some(run => !validRun(run, caseId, evidenceId))) return;
      const latest = [...runs].filter(run => run.status === 'completed').sort((a,b) => b.created_at.localeCompare(a.created_at))[0];
      if (latest?.processing_kind) setInterpretation(latest.processing_kind);
    }).catch(() => { /* Explicit format selection remains available if history cannot be loaded. */ });
    return () => request.abort();
  }, [client, caseId, evidenceId, sourceKind, filename]);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  if (client.getUser()?.role === 'reviewer') return <p className="scope-note">Read-only access. You can inspect existing source observations.</p>;
  return <>
    {sourceKind === 'document' && filename?.toLowerCase().endsWith('.csv') && <label>Interpret this CSV as<select value={interpretation ?? ''} disabled={state.status === 'submitting'} onChange={event => { edited.current = true; setInterpretation((event.target.value || undefined) as typeof interpretation); }}>
      <option value="">Document (uploaded type)</option>{(['mobile_log','network_log','gps','message','transaction'] as const).map(kind => <option key={kind} value={kind}>{kind.replaceAll('_',' ')}</option>)}
    </select><span className="scope-note">Creates a new processing interpretation. Original metadata and earlier runs are preserved.</span></label>}
    <StartProcessingPanel state={state} submit={controller.submit} onCompleted={onCompleted} />
  </>;
}

export function StartProcessingPanel({ state, submit, onCompleted }: { state: ProcessingState; submit: () => Promise<void>; onCompleted?: (runId: string) => void }) {
  const busy = state.status === 'submitting';
  return <div aria-busy={busy}>
    <button type="button" disabled={busy} onClick={() => { void submit(); }}>
      {busy ? 'Processing…' : 'Process source'}
    </button>
    {state.message && <p role="alert">{state.message}</p>}
    {state.run && <>
      <ProcessingStatus run={state.run} onCompleted={onCompleted} />
    </>}
  </div>;
}
