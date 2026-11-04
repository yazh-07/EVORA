import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

export type EntityEventView = 'entities' | 'events';
type PageState<Page> = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  page: Page | null;
  offset: number;
  message: string;
};
export type EntityEventState = {
  activeView: EntityEventView;
  entities: PageState<components['schemas']['EntityPage']>;
  events: PageState<components['schemas']['EventPage']>;
};
const empty = () => ({ status: 'idle' as const, page: null, offset: 0, message: '' });
const initial = (): EntityEventState => ({ activeView: 'entities', entities: empty(), events: empty() });
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(id => typeof id === 'string' && id.length > 0);

function validPage(page: components['schemas']['EntityPage'] | components['schemas']['EventPage'], view: EntityEventView, caseId: string, offset: number) {
  if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
      !Number.isInteger(page.limit) || page.limit < 1 || page.limit > 100 || page.offset !== offset ||
      page.items.length > page.limit || page.items.length > Math.max(0, page.total - offset)) return false;
  const ids = new Set<string>();
  return page.items.every(item => {
    if (!item || typeof item.id !== 'string' || !item.id || ids.has(item.id) || item.case_id !== caseId ||
        typeof item.kind !== 'string' || !strings(item.evidence_ids) || !strings(item.observation_ids) ||
        !Number.isFinite(item.confidence) || item.confidence < 0 || item.confidence > 1) return false;
    ids.add(item.id);
    return view === 'entities'
      ? 'canonical_label' in item && typeof item.canonical_label === 'string' && 'candidate_key' in item && typeof item.candidate_key === 'string'
      : 'summary' in item && typeof item.summary === 'string' && 'entity_ids' in item && strings(item.entity_ids) &&
        (item.observed_at_utc === undefined || typeof item.observed_at_utc === 'string') &&
        (item.observed_at_raw === undefined || typeof item.observed_at_raw === 'string');
  });
}

/** Live candidate pages, with independent view offsets and no analysis-run selector. */
export function createEntityEventController(client: ApiClient, caseId: string, limit = 20) {
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw Error('Invalid page limit.');
  let state = initial();
  let enabled = false;
  let unsubscribe: (() => void) | undefined;
  const pending: Partial<Record<EntityEventView, AbortController>> = {};
  const listeners = new Set<() => void>();
  const publish = (next: EntityEventState) => { state = next; listeners.forEach(listener => listener()); };
  const abort = () => {
    pending.entities?.abort(); pending.events?.abort();
    delete pending.entities; delete pending.events;
  };

  async function loadView(view: EntityEventView, offset = state[view].offset) {
    if (!enabled || !Number.isSafeInteger(offset) || offset < 0) return;
    pending[view]?.abort();
    const request = pending[view] = new AbortController();
    const session = client.getSessionVersion();
    const current = () => enabled && pending[view] === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ ...state, [view]: { status: 'loading', page: null, offset, message: '' } });
    try {
      const options = { path: { caseId }, query: { limit, offset }, signal: request.signal };
      if (view === 'entities') {
        const page = await client.request('get', '/api/v1/cases/{caseId}/entities', options);
        if (!current()) return;
        if (!validPage(page, view, caseId, offset)) throw Error('Invalid entities response.');
        publish({ ...state, entities: { status: 'ready', page, offset, message: '' } });
      } else {
        const page = await client.request('get', '/api/v1/cases/{caseId}/events', options);
        if (!current()) return;
        if (!validPage(page, view, caseId, offset)) throw Error('Invalid events response.');
        publish({ ...state, events: { status: 'ready', page, offset, message: '' } });
      }
    } catch (error) {
      if (!current()) return;
      publish({ ...state, [view]: { status: 'error', page: null, offset, message:
        error instanceof ApiHttpError && error.status === 400 ? 'The request was rejected. Refresh the case and retry.' :
        error instanceof ApiHttpError && error.status === 404 ? 'Case unavailable or no longer accessible.' :
        error instanceof ApiClientError && error.kind === 'authentication' ? 'Authentication required. Open a session again before retrying.' :
        `Could not load ${view}. Retry the request.`,
      } });
    } finally { if (pending[view] === request) delete pending[view]; }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true;
      unsubscribe = client.subscribeSession(() => {
        abort();
        const message = client.hasToken() ? 'Session changed. Retry to load this case again.' :
          'Authentication required. Open a session again before retrying.';
        publish({ activeView: state.activeView, entities: { ...empty(), status: 'error', message }, events: { ...empty(), status: 'error', message } });
      });
      void loadView(state.activeView);
    },
    load: (offset?: number) => loadView(state.activeView, offset),
    selectView(view: EntityEventView) {
      if (!enabled || !['entities', 'events'].includes(view) || view === state.activeView) return;
      publish({ ...state, activeView: view });
      if (state[view].status === 'idle') void loadView(view);
    },
    dispose() {
      enabled = false; abort(); unsubscribe?.(); unsubscribe = undefined;
      listeners.clear(); state = initial();
    },
  };
}
