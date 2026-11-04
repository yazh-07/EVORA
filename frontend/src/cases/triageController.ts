import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

type TriagePage = components['schemas']['TriagePage'];
type Entry = components['schemas']['TriageEntry'];
type TriageResult = components['schemas']['TriageResult'];
type TriageHistoryState = {
  status: 'loading' | 'ready' | 'error';
  items: TriageResult[];
  message: string;
};
export type TriageState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  page: TriagePage | null;
  message: string;
  histories: Record<string, TriageHistoryState | undefined>;
};
const initial = (): TriageState => ({ status: 'idle', page: null, message: '', histories: {} });
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const priority = (value: unknown) => typeof value === 'string' && ['P1', 'P2', 'P3', 'P4'].includes(value);
const number = (value: number, max: number) => Number.isFinite(value) && value >= 0 && value <= max;
const factorNames = ['relevance', 'connectivity', 'corroboration', 'gap_relevance', 'source_quality', 'conflict_relevance', 'temporal_proximity'];
function validResult(result: TriageResult, caseId: string, evidenceId: string): boolean {
  return !!result && result.case_id === caseId && result.evidence_id === evidenceId && uuid(result.id) &&
    uuid(result.analysis_run_id) && number(result.score, 100) && priority(result.priority) &&
    typeof result.created_at === 'string' && Number.isFinite(Date.parse(result.created_at)) &&
    typeof result.explanation === 'string' && Array.isArray(result.factors) &&
    new Set(result.factors.map(f => f?.name)).size === result.factors.length &&
    result.factors.every(f => f && factorNames.includes(f.name) && number(f.value, 1) && number(f.weight, 1) &&
      number(f.contribution, 100) && typeof f.explanation === 'string' && Array.isArray(f.evidence_ids) &&
      f.evidence_ids.every(uuid) && new Set(f.evidence_ids).size === f.evidence_ids.length);
}
function validEntry(entry: Entry, caseId: string, runId?: string): boolean {
  if (!entry || !uuid(entry.evidence_id)) return false;
  const result = entry.latest_result;
  const override = entry.override;
  if (result !== undefined && (!result || !runId || result.analysis_run_id !== runId ||
      !validResult(result, caseId, entry.evidence_id))) return false;
  if (override !== undefined && (!override || override.case_id !== caseId || override.evidence_id !== entry.evidence_id ||
      !uuid(override.id) || !priority(override.priority) || typeof override.reason !== 'string')) return false;
  return entry.effective_priority === (override?.priority ?? result?.priority);
}
// Compare immutable automated fields independently of JSON object-key order; overlays stay live.
function computedKey(entry: Entry): string {
  const r = entry.latest_result;
  return JSON.stringify([entry.evidence_id, r && [r.id, r.case_id, r.evidence_id, r.analysis_run_id,
    r.score, r.priority, r.explanation, r.created_at, r.factors.map(f =>
      [f.name, f.value, f.weight, f.contribution, f.explanation, f.evidence_ids])]]);
}
function compare(a: Entry, b: Entry): number {
  if (!!a.latest_result !== !!b.latest_result) return a.latest_result ? -1 : 1;
  return (b.latest_result?.score ?? 0) - (a.latest_result?.score ?? 0) ||
    (a.evidence_id < b.evidence_id ? -1 : a.evidence_id > b.evidence_id ? 1 : 0);
}

/** One case/session/selection. Snapshot results stay immutable; override fields may refresh. */
export function createTriageController(client: ApiClient, caseId: string, analysisRunId?: string,
  onSelectedRun?: (id: string) => void, limit = 20) {
  let state = initial();
  let enabled = false;
  let session = client.getSessionVersion();
  let selectedRun = analysisRunId;
  let offset = 0;
  let total: number | undefined;
  const seen = new Map<number, Entry>();
  let pending: AbortController | undefined;
  const pendingHistories = new Map<string, AbortController>();
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: TriageState) => { state = next; listeners.forEach(listener => listener()); };
  const clearHistories = () => {
    pendingHistories.forEach(request => request.abort());
    pendingHistories.clear();
  };
  async function loadHistory(evidenceId: string) {
    if (!enabled || !client.hasToken() || session !== client.getSessionVersion() ||
        !state.page?.items.some(item => item.evidence_id === evidenceId) || pendingHistories.has(evidenceId)) return;
    const request = new AbortController();
    pendingHistories.set(evidenceId, request);
    const current = () => enabled && pendingHistories.get(evidenceId) === request &&
      !request.signal.aborted && session === client.getSessionVersion();
    const publishHistory = (history: TriageHistoryState) => publish({ ...state,
      histories: { ...state.histories, [evidenceId]: history },
    });
    publishHistory({ status: 'loading', items: [], message: '' });
    try {
      // Typed getTriageHistory operation; history spans all runs and takes no snapshot query.
      const items = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/triage-history', {
        path: { caseId, evidenceId }, signal: request.signal,
      });
      if (!current()) return;
      if (!Array.isArray(items) || items.some(item => !validResult(item, caseId, evidenceId)) ||
          new Set(items.map(item => item.id)).size !== items.length ||
          new Set(items.map(item => item.analysis_run_id)).size !== items.length) {
        throw Error('Invalid triage history response.');
      }
      publishHistory({ status: 'ready', items, message: '' });
    } catch (error) {
      if (!current()) return;
      publishHistory({ status: 'error', items: [], message:
        error instanceof ApiHttpError && error.status === 404 ? 'Evidence or case unavailable or no longer accessible.' :
        (error instanceof ApiHttpError && error.status === 401) || (error instanceof ApiClientError && error.kind === 'authentication') ?
          'Authentication required. Open a session again before retrying.' :
          'Could not load priority history. Retry the request.' });
    } finally { if (pendingHistories.get(evidenceId) === request) pendingHistories.delete(evidenceId); }
  }
  async function load(nextOffset = offset) {
    if (!enabled || !client.hasToken() || session !== client.getSessionVersion() ||
        !Number.isSafeInteger(nextOffset) || nextOffset < 0 ||
        (nextOffset !== 0 && total !== undefined && nextOffset >= total)) return;
    pending?.abort();
    const request = pending = new AbortController();
    offset = nextOffset;
    const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ ...state, status: 'loading', page: null, message: '' });
    try {
      const page = await client.request('get', '/api/v1/cases/{caseId}/triage', {
        path: { caseId }, query: { analysis_run_id: selectedRun, limit, offset: nextOffset }, signal: request.signal,
      });
      if (!current()) return;
      if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
          page.limit !== limit || page.offset !== nextOffset ||
          page.items.length !== Math.min(limit, Math.max(0, page.total - nextOffset)) ||
          (page.analysis_run_id !== undefined && !uuid(page.analysis_run_id)) ||
          (selectedRun !== undefined && page.analysis_run_id !== selectedRun) ||
          page.items.some(item => !validEntry(item, caseId, page.analysis_run_id)) ||
          new Set(page.items.map(item => item.evidence_id)).size !== page.items.length ||
          page.items.some((item, i) => i > 0 && compare(page.items[i - 1]!, item) >= 0)) {
        throw Error('Invalid triage response.');
      }
      if (selectedRun) {
        if (total !== undefined && total !== page.total) throw Error('Snapshot total changed.');
        for (const [i, item] of page.items.entries()) {
          const previous = seen.get(nextOffset + i);
          if (previous && computedKey(previous) !== computedKey(item)) throw Error('Snapshot changed.');
          for (const [position, known] of seen) {
            if ((position !== nextOffset + i && known.evidence_id === item.evidence_id) ||
                (position < nextOffset + i && compare(known, item) >= 0) ||
                (position > nextOffset + i && compare(known, item) <= 0)) throw Error('Snapshot order changed.');
          }
        }
      }
      // If analysis completed during pre-analysis pagination, restart coherently at page one.
      if (!selectedRun && page.analysis_run_id && nextOffset !== 0) {
        selectedRun = page.analysis_run_id; total = undefined; seen.clear();
        onSelectedRun?.(selectedRun);
        await load(0); return;
      }
      selectedRun = page.analysis_run_id;
      total = page.total;
      if (selectedRun) page.items.forEach((item, i) => seen.set(nextOffset + i, item));
      publish({ ...state, status: 'ready', page, message: '' });
      if (selectedRun) onSelectedRun?.(selectedRun);
    } catch (error) {
      if (!current()) return;
      publish({ ...state, status: 'error', page: null, message:
        error instanceof ApiHttpError && error.status === 404 ? 'Case or completed analysis unavailable or no longer accessible.' :
        error instanceof ApiClientError && error.kind === 'authentication' ? 'Authentication required. Open a session again before retrying.' :
        'Could not load a consistent priority list. Retry the request.' });
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
        enabled = false; pending?.abort(); pending = undefined; seen.clear(); total = undefined; selectedRun = analysisRunId;
        clearHistories();
        publish({ ...initial(), status: 'error', message: client.hasToken() ?
          'Session changed. Select the case again.' : 'Authentication required. Open a session again before retrying.' });
      });
      if (!client.hasToken()) publish({ ...initial(), status: 'error', message: 'Authentication required. Open a session again before retrying.' });
      else void load(0);
    },
    load,
    loadHistory,
    dispose() {
      enabled = false; pending?.abort(); pending = undefined;
      clearHistories();
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); seen.clear();
      total = undefined; offset = 0; selectedRun = analysisRunId; state = initial();
    },
  };
}
