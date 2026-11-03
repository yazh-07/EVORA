import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import { validRun } from './processingController';
import type { ProcessingRun } from './processingController';

export type ProcessingStatusState = {
  run: ProcessingRun | null;
  message: string;
  retryable: boolean;
};
const terminal = (run: ProcessingRun) => run.status === 'completed' || run.status === 'failed';

/** Serial polling of one accepted run; aborting delivery does not cancel server work. */
export function createProcessingStatusController(client: ApiClient, initialRun: ProcessingRun, pollIntervalMs = 750) {
  const { id: runId, case_id: caseId, evidence_id: evidenceId } = initialRun;
  let state: ProcessingStatusState = { run: initialRun, message: '', retryable: false };
  let enabled = false;
  let session = client.getSessionVersion();
  let request: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: ProcessingStatusState) => { state = next; listeners.forEach(listener => listener()); };
  const cancel = () => { clearTimeout(timer); timer = undefined; request?.abort(); request = undefined; };
  const current = () => enabled && session === client.getSessionVersion();
  async function refresh() {
    if (!current() || request || !state.run || terminal(state.run)) return;
    clearTimeout(timer); timer = undefined;
    const pending = request = new AbortController();
    const deliver = () => current() && !pending.signal.aborted && request === pending;
    try {
      const run = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
        path: { caseId, evidenceId, runId }, signal: pending.signal,
      });
      if (!deliver()) return;
      if (!validRun(run, caseId, evidenceId) || run.id !== runId) throw new Error('Invalid processing response.');
      publish({ run, message: '', retryable: false });
      if (!terminal(run) && deliver()) timer = setTimeout(() => { void refresh(); }, Math.max(0, pollIntervalMs));
    } catch (error) {
      if (!deliver()) return;
      const auth = (error instanceof ApiHttpError && error.status === 401) ||
        (error instanceof ApiClientError && error.kind === 'authentication');
      const missing = error instanceof ApiHttpError && error.status === 404;
      publish({ run: auth ? null : state.run, retryable: !auth && !missing,
        message: auth ? 'Authentication required. Open a session again before retrying.' :
          missing ? 'Run or evidence unavailable or no longer accessible. Refresh evidence.' :
            'Could not refresh processing status. Last reported values may be out of date. Retry status check.',
      });
    } finally {
      if (request === pending) request = undefined;
    }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      unsubscribe?.();
      enabled = true;
      session = client.getSessionVersion();
      unsubscribe = client.subscribeSession(() => {
        enabled = false; cancel();
        publish({ run: null, retryable: false, message: client.hasToken() ?
          'Session changed. Select the evidence again to refresh processing status.' :
          'Authentication required. Open a session again before retrying.' });
      });
      void refresh();
    },
    refresh,
    dispose() {
      enabled = false; cancel(); unsubscribe?.(); unsubscribe = undefined;
      listeners.clear(); state = { run: initialRun, message: '', retryable: false };
    },
  };
}
