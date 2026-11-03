import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

type ObservationPage = components['schemas']['ObservationPage'];
export type ObservationState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  page: ObservationPage | null;
  message: string;
};

/** One evidence/optional historical output per controller; no persistent cache or timers. */
export function createObservationController(client: ApiClient, caseId: string, evidenceId: string, processingRunId?: string) {
  let state: ObservationState = { status: 'idle', page: null, message: '' };
  let enabled = false;
  let offset = 0;
  let session = client.getSessionVersion();
  let pending: AbortController | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: ObservationState) => { state = next; listeners.forEach(listener => listener()); };
  async function load(nextOffset = offset) {
    if (!enabled || session !== client.getSessionVersion() || !Number.isInteger(nextOffset) || nextOffset < 0) return;
    pending?.abort();
    const request = pending = new AbortController();
    offset = nextOffset;
    const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ status: 'loading', page: null, message: '' });
    try {
      const page = await client.request('get', '/api/v1/cases/{caseId}/observations', {
        path: { caseId }, query: { evidence_id: evidenceId, processing_run_id: processingRunId, limit: 20, offset },
        signal: request.signal,
      });
      if (!current()) return;
      // Never render a foreign resource or values from a mismatched pinned output.
      if (!page || !Array.isArray(page.items) || !Number.isInteger(page.total) || page.total < 0 ||
          !Number.isInteger(page.limit) || page.limit < 1 || page.limit > 100 || page.offset !== nextOffset ||
          page.items.length > page.limit || page.items.length > Math.max(0, page.total - page.offset) ||
          page.items.some(item => !item || item.case_id !== caseId || item.evidence_id !== evidenceId ||
            (processingRunId !== undefined && item.processing_run_id !== processingRunId) ||
            !['id', 'processing_run_id', 'kind', 'source_locator', 'raw_value', 'normalized_value'].every(key =>
              typeof item[key as keyof typeof item] === 'string') || !item.source_locator ||
            (item.observed_at_raw !== undefined && typeof item.observed_at_raw !== 'string') ||
            (item.observed_at_utc !== undefined && typeof item.observed_at_utc !== 'string') ||
            !Number.isFinite(item.extraction_confidence) || item.extraction_confidence < 0 || item.extraction_confidence > 1)) {
        throw new Error('Invalid observations response.');
      }
      publish({ status: 'ready', page, message: '' });
    } catch (error) {
      if (!current()) return;
      publish({ status: 'error', page: null, message:
        error instanceof ApiHttpError && error.status === 404 ? 'Evidence or completed processing run unavailable or no longer accessible.' :
        error instanceof ApiHttpError && error.status === 400 ? 'Observation request was rejected. Refresh the evidence selection and retry.' :
        error instanceof ApiClientError && error.kind === 'authentication' ? 'Authentication required. Open a session again before retrying.' :
        'Could not load observations. Retry the request.',
      });
    } finally { if (pending === request) pending = undefined; }
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
        enabled = false; pending?.abort(); pending = undefined;
        publish({ status: 'error', page: null, message: client.hasToken() ?
          'Session changed. Select evidence again to load observations.' :
          'Authentication required. Open a session again before retrying.' });
      });
      void load(0);
    },
    load,
    dispose() {
      enabled = false; pending?.abort(); pending = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear();
      state = { status: 'idle', page: null, message: '' };
    },
  };
}
