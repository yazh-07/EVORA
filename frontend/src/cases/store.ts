import type { ApiClient } from '../api/client';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';

export type Case = components['schemas']['Case'];
type Page = components['schemas']['CasePage'];
export type CaseState = {
  status: 'signed-out' | 'loading' | 'ready' | 'error';
  page: Page | null;
  message: string;
  detail: Case | null;
  detailStatus: 'idle' | 'loading' | 'ready' | 'error';
  detailMessage: string;
};
const initial = (): CaseState => ({ status: 'signed-out', page: null, message: '', detail: null, detailStatus: 'idle', detailMessage: '' });
export function caseError(error: unknown): string {
  if (error instanceof ApiHttpError) {
    if (error.status === 401) return 'Your session is unavailable. Enter a valid access token.';
    if (error.status === 404) return 'Case unavailable. It may no longer be accessible.';
  }
  return 'Could not load cases. Check your connection and try again.';
}

// One store per mounted session; aborted or late requests can never replace newer state.
export function createCaseStore(client: ApiClient) {
  let state = initial();
  const listeners = new Set<() => void>();
  let pageRequest: AbortController | undefined;
  let detailRequest: AbortController | undefined;
  let generation = 0;
  const publish = (next: CaseState) => { state = next; for (const listener of listeners) listener(); };
  const clearDetail = () => { detailRequest?.abort(); };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    async load(offset = 0) {
      if (!Number.isSafeInteger(offset) || offset < 0) throw new Error('Invalid case offset.');
      pageRequest?.abort(); clearDetail();
      const request = pageRequest = new AbortController();
      const version = client.getSessionVersion();
      const current = ++generation;
      if (!client.hasToken()) { publish(initial()); return; }
      publish({ ...initial(), status: 'loading' });
      try {
        const page = await client.request('get', '/api/v1/cases', { query: { limit: 20, offset }, signal: request.signal });
        if (request.signal.aborted || current !== generation || version !== client.getSessionVersion()) return;
        // Validate page metadata before using it to navigate; never replace an API failure with fixtures.
        if (page.offset !== offset || page.limit !== 20 || !Number.isSafeInteger(page.total) || page.total < 0 ||
            !Array.isArray(page.items) || page.items.length > page.limit ||
            page.items.some(item => !validCase(item)) || new Set(page.items.map(item => item.id)).size !== page.items.length) {
          throw new Error('Invalid case page.');
        }
        publish({ ...initial(), status: 'ready', page });
      } catch (error) {
        if (request.signal.aborted || current !== generation || version !== client.getSessionVersion()) return;
        publish({ ...initial(), status: 'error', message: caseError(error) });
      }
    },
    async select(id: string) {
      if (state.status !== 'ready' || !state.page?.items.some(item => item.id === id)) return;
      clearDetail();
      const request = detailRequest = new AbortController();
      const current = generation;
      const version = client.getSessionVersion();
      publish({ ...state, detail: null, detailStatus: 'loading', detailMessage: '' });
      try {
        const detail = await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: id }, signal: request.signal });
        if (request.signal.aborted || current !== generation || version !== client.getSessionVersion()) return;
        if (!validCase(detail) || detail.id !== id) throw new Error('Invalid case detail.');
        publish({ ...state, detailStatus: 'ready', detail });
      } catch (error) {
        if (request.signal.aborted || current !== generation || version !== client.getSessionVersion()) return;
        publish({ ...state, detail: null, detailStatus: 'error', detailMessage: caseError(error) });
      }
    },
    dispose() { generation++; pageRequest?.abort(); clearDetail(); listeners.clear(); state = initial(); },
  };
}
function validCase(value: Case): boolean {
  return !!value && typeof value.id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id) &&
    typeof value.title === 'string' && typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at)) &&
    (value.description === undefined || typeof value.description === 'string');
}
