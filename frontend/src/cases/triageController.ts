import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

type TriagePage = components['schemas']['TriagePage'];
type Entry = components['schemas']['TriageEntry'];
export type TriageState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  page: TriagePage | null;
  message: string;
};
const initial = (): TriageState => ({ status: 'idle', page: null, message: '' });
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const priority = (value: unknown) => ['P1', 'P2', 'P3', 'P4'].includes(String(value));
const number = (value: number, max: number) => Number.isFinite(value) && value >= 0 && value <= max;
const factorNames = ['relevance', 'connectivity', 'corroboration', 'gap_relevance', 'source_quality', 'conflict_relevance', 'temporal_proximity'];
function validEntry(entry: Entry, caseId: string, runId?: string): boolean {
  if (!entry || !uuid(entry.evidence_id)) return false;
  const result = entry.latest_result;
  const override = entry.override;
  if (result !== undefined && (!result || !runId || result.analysis_run_id !== runId ||
      result.case_id !== caseId || result.evidence_id !== entry.evidence_id || !uuid(result.id) ||
      !number(result.score, 100) || !priority(result.priority) || typeof result.explanation !== 'string' ||
      !Array.isArray(result.factors) || new Set(result.factors.map(f => f?.name)).size !== result.factors.length ||
      result.factors.some(f => !f || !factorNames.includes(f.name) || !number(f.value, 1) || !number(f.weight, 1) ||
        !number(f.contribution, 100) || typeof f.explanation !== 'string' || !Array.isArray(f.evidence_ids) ||
        !f.evidence_ids.every(uuid) || new Set(f.evidence_ids).size !== f.evidence_ids.length))) return false;
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
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: TriageState) => { state = next; listeners.forEach(listener => listener()); };
  async function load(nextOffset = offset) {
    if (!enabled || !client.hasToken() || session !== client.getSessionVersion() ||
        !Number.isSafeInteger(nextOffset) || nextOffset < 0 ||
        (nextOffset !== 0 && total !== undefined && nextOffset >= total)) return;
    pending?.abort();
    const request = pending = new AbortController();
    offset = nextOffset;
    const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ status: 'loading', page: null, message: '' });
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
      publish({ status: 'ready', page, message: '' });
      if (selectedRun) onSelectedRun?.(selectedRun);
    } catch (error) {
      if (!current()) return;
      publish({ status: 'error', page: null, message:
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
        publish({ status: 'error', page: null, message: client.hasToken() ?
          'Session changed. Select the case again.' : 'Authentication required. Open a session again before retrying.' });
      });
      if (!client.hasToken()) publish({ status: 'error', page: null, message: 'Authentication required. Open a session again before retrying.' });
      else void load(0);
    },
    load,
    dispose() {
      enabled = false; pending?.abort(); pending = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); seen.clear();
      total = undefined; offset = 0; selectedRun = analysisRunId; state = initial();
    },
  };
}
