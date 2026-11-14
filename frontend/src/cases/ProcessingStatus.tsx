import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { ProcessingRun } from './processingController';
import { validRun } from './processingController';
import { createProcessingStatusController } from './processingStatusController';
import type { ProcessingStatusState } from './processingStatusController';

export function ProcessingHistory({ caseId, evidenceId, revision }: { caseId: string; evidenceId: string; revision?: unknown }) {
  const client = useApiClient();
  const [runs, setRuns] = useState<ProcessingRun[]>(), [error, setError] = useState(false), [reload, setReload] = useState(0);
  useEffect(() => {
    const request = new AbortController(); setError(false); setRuns(undefined);
    void client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId }, signal: request.signal }).then(value => {
      if (request.signal.aborted) return;
      if (!Array.isArray(value) || value.some(run => !validRun(run, caseId, evidenceId))) throw Error('Invalid history');
      setRuns([...value].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id.localeCompare(a.id)));
    }).catch(() => { if (!request.signal.aborted) setError(true); });
    return () => request.abort();
  }, [client, caseId, evidenceId, revision, reload]);
  return <section aria-label="Previous processing runs">
    {error ? <p role="alert">Could not load history. <button type="button" onClick={() => setReload(value => value + 1)}>Retry</button></p>
      : !runs ? <p role="status">Loading history…</p> : !runs.length ? <p>No processing runs yet.</p>
      : <ol className="processing-history-list">{runs.map(run => <li key={run.id}><div><time dateTime={run.created_at}>{new Date(run.created_at).toLocaleString()}</time><span>{run.status === 'completed' ? 'Complete' : run.status === 'running' ? 'Processing' : run.status === 'queued' ? 'Queued' : 'Failed'}</span></div>
        {run.processing_kind && <p>{run.processing_kind.replaceAll('_', ' ')}</p>}
        {run.error && <p role="alert">{run.error}</p>}
        <details><summary>Run information</summary><dl><dt>Run</dt><dd className="identifier">{run.id}</dd><dt>Processor</dt><dd>{run.processor_version}</dd>{run.finished_at && <><dt>Finished</dt><dd>{new Date(run.finished_at).toLocaleString()}</dd></>}</dl></details>
      </li>)}</ol>}
  </section>;
}

export function ProcessingStatus({ run, pollIntervalMs = 750, onCompleted, onStatusChange }: {
  onStatusChange?: (run: ProcessingRun) => void; run: ProcessingRun; pollIntervalMs?: number; onCompleted?: (runId: string) => void }) {
  const client = useApiClient();
  const controller = useMemo(() => createProcessingStatusController(client, run, pollIntervalMs), [client, run, pollIntervalMs]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  useEffect(() => { if (state.run) onStatusChange?.(state.run); }, [state.run, onStatusChange]);
  useEffect(() => { if (state.run?.status === 'completed') onCompleted?.(state.run.id); }, [state.run, onCompleted]);
  return <ProcessingStatusPanel state={state} retry={controller.refresh} />;
}

export function ProcessingStatusPanel({ state, retry }: { state: ProcessingStatusState; retry: () => Promise<void> }) {
  const { run } = state;
  return <section aria-label="Processing run status">
    {state.message && <p role="alert">{state.message}</p>}
    {state.retryable && <button type="button" onClick={() => { void retry(); }}>Retry status check</button>}
    {run && <div role="status">
      <p className={`processing-stage status-${run.status}`}>{run.status === 'queued' ? 'Queued' : run.status === 'running' ? 'Processing…' : run.status === 'completed' ? 'Complete' : 'Processing failed'}</p>
      {run.processing_kind && <p>Format: {run.processing_kind.replaceAll('_', ' ')}</p>}
      <details className="processing-details"><summary>Processing run details</summary><dl>
        <dt>Run ID</dt><dd className="identifier">{run.id}</dd>
        <dt>Created time</dt><dd>{run.created_at}</dd>
        <dt>Processor version</dt><dd>{run.processor_version}</dd>
        {run.finished_at && <><dt>Finished time</dt><dd>{run.finished_at}</dd></>}
      </dl></details>
      {run.status === 'failed' && <dl><dt>Processing diagnostic</dt><dd>{run.error}</dd></dl>}
    </div>}
  </section>;
}
