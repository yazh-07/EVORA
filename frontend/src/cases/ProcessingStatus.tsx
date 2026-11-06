import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { ProcessingRun } from './processingController';
import { createProcessingStatusController } from './processingStatusController';
import type { ProcessingStatusState } from './processingStatusController';

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
      <p className={`processing-stage status-${run.status}`}>{run.status === 'queued' ? 'Waiting for extraction to start.' : run.status === 'running' ? 'Extracting records from this source. You can continue reviewing other evidence.' : run.status === 'completed' ? 'Extraction complete. Inspect the observations below, then run case analysis to connect the evidence.' : 'Extraction could not complete. Check the file format and diagnostic before trying again.'}</p>
      <p className="scope-note">Last reported status: {run.status}</p>
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
