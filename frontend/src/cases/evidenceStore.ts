import { ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

export type Evidence = components['schemas']['Evidence'];
type Page = components['schemas']['EvidencePage'];
export const evidenceKinds = ['document', 'image', 'video', 'audio', 'message', 'network_log', 'mobile_log', 'transaction', 'gps'] as const satisfies readonly Evidence['kind'][];
export type EvidenceState = {
  page: Page | null; status: 'loading' | 'ready' | 'error'; message: string;
  detail: Evidence | null; detailStatus: 'idle' | 'loading' | 'ready' | 'error'; detailMessage: string;
  submitting: boolean; uploadMessage: string; uploaded: boolean;
};
const initial = (): EvidenceState => ({ page: null, status: 'loading', message: '', detail: null, detailStatus: 'idle', detailMessage: '', submitting: false, uploadMessage: '', uploaded: false });
const errorMessage = (error: unknown) => error instanceof ApiHttpError && error.apiError ? error.apiError.message : 'Could not access evidence. Check your connection and try again.';
function validEvidence(item: Evidence, caseId: string): boolean {
  return !!item && item.case_id === caseId && typeof item.id === 'string' &&
    /^[0-9a-f-]{36}$/i.test(item.id) && /^[0-9a-f]{64}$/.test(item.sha256) &&
    Number.isSafeInteger(item.size_bytes) && item.size_bytes >= 0 && evidenceKinds.includes(item.kind) &&
    ['filename', 'source_label', 'media_type', 'created_at'].every(key => typeof item[key as keyof Evidence] === 'string');
}

export function createEvidenceStore(client: ApiClient, caseId: string) {
  let state = initial();
  let disposed = false;
  const session = client.getSessionVersion();
  const listeners = new Set<() => void>();
  let pageRequest: AbortController | undefined;
  let detailRequest: AbortController | undefined;
  let uploadRequest: AbortController | undefined;
  const active = () => !disposed && session === client.getSessionVersion() && client.hasToken();
  const publish = (next: EvidenceState) => { if (active()) { state = next; listeners.forEach(listener => listener()); } };
  async function load(offset = 0) {
    if (!active() || !Number.isSafeInteger(offset) || offset < 0) return;
    pageRequest?.abort();
    const request = pageRequest = new AbortController();
    publish({ ...state, page: null, status: 'loading', message: '' });
    try {
      const page = await client.request('get', '/api/v1/cases/{caseId}/evidence', { path: { caseId }, query: { limit: 20, offset }, signal: request.signal });
      if (!active() || request.signal.aborted) return;
      if (page.limit !== 20 || page.offset !== offset || !Number.isSafeInteger(page.total) || page.total < 0 ||
          !Array.isArray(page.items) || page.items.length > 20 || page.items.length > page.total ||
          !page.items.every(item => validEvidence(item, caseId)) || new Set(page.items.map(item => item.id)).size !== page.items.length) throw Error('Invalid evidence page');
      publish({ ...state, page, status: 'ready' });
    } catch (error) {
      if (!request.signal.aborted) publish({ ...state, page: null, status: 'error', message: errorMessage(error) });
    }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    load,
    start() { disposed = false; return load(); },
    async select(evidenceId: string) {
      if (!active() || !/^[0-9a-f-]{36}$/i.test(evidenceId)) return;
      detailRequest?.abort();
      const request = detailRequest = new AbortController();
      publish({ ...state, detail: null, detailStatus: 'loading', detailMessage: '' });
      try {
        const detail = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId, evidenceId }, signal: request.signal });
        if (!active() || request.signal.aborted) return;
        if (!validEvidence(detail, caseId) || detail.id !== evidenceId) throw Error('Invalid evidence detail');
        publish({ ...state, detail, detailStatus: 'ready' });
      } catch (error) {
        if (!request.signal.aborted) publish({ ...state, detail: null, detailStatus: 'error', detailMessage: errorMessage(error) });
      }
    },
    async upload(file: File | null, kind: string, label: string, acquiredAt = ''): Promise<boolean> {
      if (!active() || state.submitting) return false;
      const message = !file ? 'Select a file to upload.' : !label.trim() ? 'Source label cannot be empty or whitespace.' :
        label.length > 200 ? 'Source label must be at most 200 characters.' : !evidenceKinds.some(value => value === kind) ? 'Select a supported evidence kind.' :
        acquiredAt && !Number.isFinite(Date.parse(acquiredAt + 'Z')) ? 'Enter a valid acquisition date and time in UTC.' : '';
      if (message) { publish({ ...state, uploadMessage: message, uploaded: false }); return false; }
      const request = uploadRequest = new AbortController();
      publish({ ...state, submitting: true, uploadMessage: '', uploaded: false });
      const body = new FormData();
      body.set('file', file!); body.set('kind', kind); body.set('source_label', label);
      if (acquiredAt) body.set('acquired_at', acquiredAt + (acquiredAt.length === 16 ? ':00Z' : 'Z'));
      try {
        const created = await client.request('post', '/api/v1/cases/{caseId}/evidence', { path: { caseId }, body, signal: request.signal });
        if (!active() || request.signal.aborted) return false;
        if (!validEvidence(created, caseId)) throw Error('Invalid upload response');
        // Confirmed upload survives list refresh failure; never invite a duplicate retry.
        detailRequest?.abort();
        publish({ ...state, detail: created, detailStatus: 'ready', detailMessage: '', uploaded: true });
        await load(0);
        if (!active() || request.signal.aborted) return false;
        publish({ ...state, submitting: false });
        return true;
      } catch (error) {
        if (!request.signal.aborted) publish({ ...state, submitting: false, uploadMessage: errorMessage(error) });
        return false;
      }
    },
    dispose() { disposed = true; pageRequest?.abort(); detailRequest?.abort(); uploadRequest?.abort(); listeners.clear(); state = initial(); },
  };
}
