import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

export type AnalysisRun = components['schemas']['AnalysisRun'];
export type AnalysisState = {
  status: 'idle' | 'submitting' | 'polling' | 'terminal' | 'error';
  run: AnalysisRun | null;
  pinnedAnalysisRunId: string | null;
  message: string;
};
const initial = (): AnalysisState => ({ status: 'idle', run: null, pinnedAnalysisRunId: null, message: '' });
const terminal = (run: AnalysisRun) => run.status === 'completed' || run.status === 'failed';
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const timestamp = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value));
const ids = (value: unknown): boolean => Array.isArray(value) && value.every(uuid) &&
  value.every((id, index) => {
    const previous = value[index - 1];
    return index === 0 || (typeof previous === 'string' && previous < id);
  });

// Compare declared fields rather than JSON object-key order.
function snapshotKey(run: AnalysisRun): string {
  const s = run.input_snapshot;
  return JSON.stringify([s.case_id, s.evidence_ids, s.processing_run_ids, s.observation_ids, s.sha256]);
}

function validRun(run: AnalysisRun, caseId: string): boolean {
  const snapshot = run?.input_snapshot;
  return !!run && uuid(run.id) && run.case_id === caseId &&
    ['queued', 'running', 'completed', 'failed'].includes(run.status) &&
    ['initial', 'new_observations', 'manual'].includes(run.trigger) &&
    typeof run.algorithm_version === 'string' && !!run.algorithm_version.trim() && timestamp(run.created_at) &&
    (!terminal(run) || timestamp(run.finished_at)) &&
    (run.status !== 'failed' || (typeof run.error === 'string' && !!run.error.trim())) &&
    !!snapshot && snapshot.case_id === caseId && ids(snapshot.evidence_ids) &&
    ids(snapshot.processing_run_ids) && ids(snapshot.observation_ids) &&
    typeof snapshot.sha256 === 'string' && /^[0-9a-f]{64}$/.test(snapshot.sha256);
}

/** One case/session; serial polling. Cancellation stops delivery, not server analysis. */
export function createAnalysisController(client: ApiClient, caseId: string, pollIntervalMs = 750) {
  let state = initial();
  let enabled = false;
  let request: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: AnalysisState) => { state = next; listeners.forEach(listener => listener()); };
  const cancel = () => { clearTimeout(timer); timer = undefined; request?.abort(); request = undefined; };

  async function perform(runId?: string) {
    if (!enabled || request) return;
    const pending = request = new AbortController();
    const session = client.getSessionVersion();
    const current = () => enabled && request === pending && !pending.signal.aborted && session === client.getSessionVersion();
    try {
      const run = runId ? await client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', {
        path: { caseId, runId }, signal: pending.signal,
      }) : await client.request('post', '/api/v1/cases/{caseId}/analysis-runs', {
        path: { caseId }, header: { 'Idempotency-Key': crypto.randomUUID() }, signal: pending.signal,
      });
      if (!current()) return;
      if (!validRun(run, caseId) || (runId && run.id !== runId) ||
          (runId && (!state.run || snapshotKey(run) !== snapshotKey(state.run)))) {
        throw new Error('Invalid analysis response.');
      }
      // Even a terminal POST response is confirmed by getAnalysisRun before pinning.
      const confirmed = !!runId && terminal(run);
      publish({ ...state, status: confirmed ? 'terminal' : 'polling', run, message: '',
        pinnedAnalysisRunId: confirmed && run.status === 'completed' ? run.id : state.pinnedAnalysisRunId });
      if (!confirmed && current()) timer = setTimeout(() => { void perform(run.id); }, Math.max(0, pollIntervalMs));
    } catch (error) {
      if (!current()) return;
      publish({ ...state, status: 'error', run: null, message: analysisError(error) });
    } finally {
      if (request === pending) request = undefined;
    }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true;
      unsubscribe = client.subscribeSession(() => {
        cancel();
        publish({ ...initial(), status: 'error', message: client.hasToken() ?
          'Session changed. Select the case again before starting analysis.' :
          'Authentication required. Open a session again before retrying.' });
      });
    },
    async submit() {
      if (!enabled || request || state.status === 'polling') return;
      cancel();
      publish({ ...state, status: 'submitting', run: null, message: '' });
      await perform();
    },
    dispose() {
      enabled = false; cancel(); unsubscribe?.(); unsubscribe = undefined;
      listeners.clear(); state = initial();
    },
  };
}

function analysisError(error: unknown): string {
  if (error instanceof ApiHttpError) {
    if (error.status === 400) return 'Analysis request was invalid. Refresh the case and retry with a new key.';
    if (error.status === 401) return 'Authentication required. Open a session again before retrying.';
    if (error.status === 404) return 'Case or analysis run unavailable or no longer accessible. Refresh the case and retry.';
  }
  if (error instanceof ApiClientError && error.kind === 'authentication') return 'Authentication required. Open a session again before retrying.';
  return 'Could not confirm analysis status. The server may still be working. Retrying with a new key starts another run.';
}
