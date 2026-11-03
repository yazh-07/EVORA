import { ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';
import { validRun } from './processingController';

export const evidenceKinds = ['document', 'image', 'video', 'audio', 'message', 'network_log', 'mobile_log', 'transaction', 'gps'] as const satisfies readonly components['schemas']['EvidenceKind'][];
export const overviewStatuses = ['completed', 'running', 'queued', 'failed', 'unprocessed'] as const;
export type OverviewSummary = {
  total: number;
  kinds: Record<typeof evidenceKinds[number], number>;
  statuses: Record<typeof overviewStatuses[number], number>;
};
export type CaseOverviewState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  summary: OverviewSummary | null;
  message: string;
};
const initial = (): CaseOverviewState => ({ status: 'idle', summary: null, message: '' });

/** A refresh is a live read, not an immutable analysis snapshot. Publish no partial totals. */
export function createCaseOverviewController(client: ApiClient, caseId: string) {
  let state = initial();
  let enabled = false;
  let session = client.getSessionVersion();
  let pending: AbortController | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: CaseOverviewState) => { state = next; listeners.forEach(listener => listener()); };
  async function load() {
    if (!enabled || session !== client.getSessionVersion() || !client.hasToken()) return;
    pending?.abort();
    const request = pending = new AbortController();
    const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ status: 'loading', summary: null, message: '' });
    try {
      const detail = await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId }, signal: request.signal });
      if (!current()) return;
      if (!detail || detail.id !== caseId) throw Error('Mismatched case.');
      const items: components['schemas']['Evidence'][] = [];
      const ids = new Set<string>();
      let total: number | undefined;
      do {
        const offset = items.length;
        const page = await client.request('get', '/api/v1/cases/{caseId}/evidence', {
          path: { caseId }, query: { limit: 20, offset }, signal: request.signal,
        });
        if (!current()) return;
        if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
            !Number.isInteger(page.limit) || page.limit < 1 || page.limit > 100 || page.offset !== offset ||
            page.items.length > page.limit || offset + page.items.length > page.total ||
            (total !== undefined && total !== page.total) || (page.items.length === 0 && offset < page.total)) {
          throw Error('Inconsistent evidence pages.');
        }
        total = page.total;
        for (const item of page.items) {
          if (!item || item.case_id !== caseId || typeof item.id !== 'string' || !item.id || ids.has(item.id) ||
              !evidenceKinds.includes(item.kind)) throw Error('Invalid evidence.');
          ids.add(item.id); items.push(item);
        }
      } while (items.length < total);
      const summary: OverviewSummary = {
        total: items.length,
        kinds: Object.fromEntries(evidenceKinds.map(kind => [kind, 0])) as OverviewSummary['kinds'],
        statuses: { completed: 0, running: 0, queued: 0, failed: 0, unprocessed: 0 },
      };
      // Serial histories bound request fan-out and stop immediately on failure/disposal.
      for (const item of items) {
        const runs = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', {
          path: { caseId, evidenceId: item.id }, signal: request.signal,
        });
        if (!current()) return;
        if (!Array.isArray(runs) || runs.some(run => !validRun(run, caseId, item.id)) ||
            new Set(runs.map(run => run.id)).size !== runs.length) throw Error('Invalid processing history.');
        // listProcessingRuns contract returns oldest first; the final entry is latest.
        const status = runs.at(-1)?.status ?? 'unprocessed';
        summary.kinds[item.kind]++; summary.statuses[status]++;
      }
      publish({ status: 'ready', summary, message: '' });
    } catch (error) {
      if (!current()) return;
      publish({ status: 'error', summary: null, message: error instanceof ApiHttpError && error.status === 404
        ? 'Case or evidence unavailable or no longer accessible.'
        : 'Could not load the complete case overview. Refresh to retry.' });
    } finally { if (pending === request) pending = undefined; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true; session = client.getSessionVersion();
      unsubscribe?.();
      unsubscribe = client.subscribeSession(() => {
        enabled = false; pending?.abort(); pending = undefined;
        publish({ status: 'error', summary: null, message: client.hasToken()
          ? 'Session changed. Select the case again.' : 'Authentication required. Open a session again before retrying.' });
      });
      void load();
    },
    load,
    dispose() {
      enabled = false; pending?.abort(); pending = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); state = initial();
    },
  };
}
