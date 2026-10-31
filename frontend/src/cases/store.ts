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
  createStatus: 'idle' | 'submitting' | 'error';
  createMessage: string;
};
const initial = (): CaseState => ({ status: 'signed-out', page: null, message: '', detail: null, detailStatus: 'idle', detailMessage: '', createStatus: 'idle', createMessage: '' });
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
  let creationRequest: AbortController | undefined;
  const publish = (next: CaseState) => { state = next; for (const listener of listeners) listener(); };
  const clearDetail = () => { detailRequest?.abort(); };
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    async create(title: string, description: string): Promise<boolean> {
      if (state.createStatus === 'submitting' || !client.hasToken()) return false;
      const message = !title.trim() ? 'Title cannot be empty' :
        Array.from(title).length > 200 ? 'Title must be at most 200 characters' :
        Array.from(description).length > 5000 ? 'Description must be at most 5000 characters' : '';
      if (message) { publish({ ...state, createStatus: 'error', createMessage: message }); return false; }
      pageRequest?.abort(); clearDetail(); generation++;
      const request = creationRequest = new AbortController();
      const version = client.getSessionVersion();
      publish({ ...state, createStatus: 'submitting', createMessage: '' });
      try {
        const created = await client.request('post', '/api/v1/cases', {
          body: { title, ...(description ? { description } : {}) }, signal: request.signal,
        });
        if (request.signal.aborted || version !== client.getSessionVersion()) return false;
        if (!validCase(created)) throw new Error('Invalid created case.');
        // Invalidate older reads so they cannot erase the confirmed creation.
        pageRequest?.abort(); clearDetail(); generation++;
        const current = generation;
        let page = null;
        try {
          const result = await client.request('get', '/api/v1/cases', { query: { limit: 20, offset: 0 }, signal: request.signal });
          if (result.offset !== 0 || result.limit !== 20 || !Number.isSafeInteger(result.total) || result.total < 1 ||
              !Array.isArray(result.items) || result.items.length > 20 || !result.items.every(validCase) ||
              new Set(result.items.map(item => item.id)).size !== result.items.length) throw new Error('Invalid case page.');
          page = result;
        } catch { /* Creation succeeded; show confirmed details and allow list retry. */ }
        if (request.signal.aborted || current !== generation || version !== client.getSessionVersion()) return false;
        publish({ ...initial(), status: page ? 'ready' : 'error', page,
          message: page ? '' : 'Case created. Could not refresh cases. Try again.',
          detail: created, detailStatus: 'ready' });
        return !request.signal.aborted && version === client.getSessionVersion();
      } catch (error) {
        if (request.signal.aborted || version !== client.getSessionVersion()) return false;
        publish({ ...state,
          status: state.status === 'loading' ? 'error' : state.status,
          message: state.status === 'loading' ? 'Could not load cases. Try again.' : state.message,
          detailStatus: state.detailStatus === 'loading' ? 'idle' : state.detailStatus,
          createStatus: 'error', createMessage:
          error instanceof ApiHttpError && error.status === 400 ? 'Case not created. Check the title and description and try again.' : 'Could not confirm whether the case was created. Refresh cases before submitting again.' });
        return false;
      }
    },
    async load(offset = 0) {
      if (state.createStatus === 'submitting') return;
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
      if (state.createStatus === 'submitting') return;
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
    dispose() { generation++; creationRequest?.abort(); pageRequest?.abort(); clearDetail(); listeners.clear(); state = initial(); },
  };
}
function validCase(value: Case): boolean {
  return !!value && typeof value.id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id) &&
    typeof value.title === 'string' && typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at)) &&
    (value.description === undefined || typeof value.description === 'string');
}
