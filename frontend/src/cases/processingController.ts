import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

export type ProcessingRun = components['schemas']['ProcessingRun'];
export type ProcessingState = {
  status: 'idle' | 'submitting' | 'accepted' | 'error';
  run: ProcessingRun | null;
  message: string;
};
const initial = (): ProcessingState => ({ status: 'idle', run: null, message: '' });

/** One selected evidence item. Disposal cancels delivery, not server processing. */
export function createProcessingController(client: ApiClient, caseId: string, evidenceId: string) {
  let state = initial();
  let disposed = false;
  let request: AbortController | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: ProcessingState) => { state = next; listeners.forEach(listener => listener()); };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() { disposed = false; },
    async submit() {
      if (disposed || state.status === 'submitting') return;
      const pending = request = new AbortController();
      const session = client.getSessionVersion();
      const current = () => !disposed && !pending.signal.aborted && session === client.getSessionVersion();
      publish({ ...initial(), status: 'submitting' });
      try {
        const key = crypto.randomUUID();
        const run = await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', {
          path: { caseId, evidenceId }, header: { 'Idempotency-Key': key }, signal: pending.signal,
        });
        if (!current()) return;
        if (!validRun(run, caseId, evidenceId)) throw new Error('Invalid processing response.');
        publish({ status: 'accepted', run, message: '' });
      } catch (error) {
        if (disposed || pending.signal.aborted) return;
        // The shared client clears the token on 401. The provider then remounts
        // case UI; standalone consumers still receive a safe authentication alert.
        const unauthorized = error instanceof ApiHttpError && error.status === 401 &&
          !client.hasToken() && client.getSessionVersion() === session + 1;
        if (!current() && !unauthorized) return;
        publish({ status: 'error', run: null, message: processingError(error) });
      }
    },
    dispose() { disposed = true; request?.abort(); listeners.clear(); state = initial(); },
  };
}

function processingError(error: unknown): string {
  if (error instanceof ApiHttpError) {
    if (error.status === 400) return 'Processing was not started. Check the evidence selection and try again.';
    if (error.status === 401) return 'Authentication required. Open a session again before retrying.';
    if (error.status === 404) return 'Evidence unavailable or no longer accessible. Refresh evidence and try again.';
    if (error.status === 409) return 'Processing request conflicted. Refresh processing history before trying again.';
    if (error.status === 415) return 'This evidence format is not supported for processing.';
  }
  if (error instanceof ApiClientError && error.kind === 'authentication') return 'Authentication required. Open a session again before retrying.';
  return 'Could not confirm whether processing started. Check processing history before trying again; another action starts a new run.';
}

export function validRun(run: ProcessingRun, caseId: string, evidenceId: string): boolean {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return !!run && typeof run.id === 'string' && uuid.test(run.id) && run.case_id === caseId && run.evidence_id === evidenceId &&
    ['queued', 'running', 'completed', 'failed'].includes(run.status) && typeof run.processor_version === 'string' &&
    typeof run.created_at === 'string' && Number.isFinite(Date.parse(run.created_at)) &&
    (!['completed', 'failed'].includes(run.status) || (typeof run.finished_at === 'string' && Number.isFinite(Date.parse(run.finished_at)))) &&
    (run.status !== 'failed' || (typeof run.error === 'string' && run.error.trim().length > 0));
}
