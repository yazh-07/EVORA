import { ApiClientError, ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

type FindingPage = components['schemas']['FindingPage'];
type Entry = components['schemas']['Finding'];
type Observation = components['schemas']['Observation'];
export type FindingState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  page: FindingPage | null;
  message: string;
  selectedId: string | null; citations: Observation[];
  citationStatus: 'idle' | 'loading' | 'ready' | 'error'; citationMessage: string;
};
const initial = (): FindingState => ({ status: 'idle', page: null, message: '', selectedId: null, citations: [], citationStatus: 'idle', citationMessage: '' });
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const ids = (v: unknown, nonempty = true): v is string[] => Array.isArray(v) && (!nonempty || v.length > 0) && v.every(uuid) && new Set(v).size === v.length;
function validEntry(f: Entry, caseId: string, runId?: string): boolean {
  return !!f && uuid(f.id) && f.case_id === caseId && !!runId && f.analysis_run_id === runId &&
    ['relationship', 'corroboration', 'conflict', 'gap', 'cluster', 'anomaly', 'hypothesis'].includes(f.kind) &&
    typeof f.summary === 'string' && typeof f.rule === 'string' && Number.isFinite(f.confidence) &&
    f.confidence >= 0 && f.confidence <= 1 && ids(f.evidence_ids) && ids(f.observation_ids) &&
    (f.contradicting_evidence_ids === undefined || ids(f.contradicting_evidence_ids, false)) &&
    (f.entity_ids === undefined || ids(f.entity_ids, false)) &&
    (f.missing_information === undefined || (Array.isArray(f.missing_information) &&
      f.missing_information.every(v => typeof v === 'string' && v.trim().length > 0)));
}
const computedKey = (f: Entry) => JSON.stringify([f.id, f.case_id, f.analysis_run_id, f.kind, f.summary,
  f.rule, f.confidence, f.evidence_ids, f.observation_ids, f.contradicting_evidence_ids, f.entity_ids, f.missing_information]);
const safeError = (error: unknown) => error instanceof ApiHttpError && error.status === 404 ?
  'Case, completed analysis or source unavailable or no longer accessible.' :
  error instanceof ApiClientError && error.kind === 'authentication' ? 'Authentication required. Open a session again before retrying.' :
  'Could not load consistent findings or sources. Retry the request.';

/** One case/session/selection; all pages and source reads retain the completed snapshot. */
export function createFindingController(client: ApiClient, caseId: string, analysisRunId?: string,
  onSelectedRun?: (id: string) => void, limit = 20) {
  let state = initial();
  let enabled = false;
  let session = client.getSessionVersion();
  let selectedRun = analysisRunId;
  let offset = 0;
  let total: number | undefined;
  const seen = new Map<number, Entry>();
  let pending: AbortController | undefined, sources: AbortController | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: FindingState) => { state = next; listeners.forEach(listener => listener()); };
  async function load(nextOffset = offset) {
    if (!enabled || !client.hasToken() || session !== client.getSessionVersion() ||
        !Number.isSafeInteger(nextOffset) || nextOffset < 0 ||
        (nextOffset !== 0 && total !== undefined && nextOffset >= total)) return;
    pending?.abort(); sources?.abort();
    const request = pending = new AbortController();
    offset = nextOffset;
    const current = () => enabled && pending === request && !request.signal.aborted && session === client.getSessionVersion();
    publish({ ...initial(), status: 'loading' });
    try {
      const page = await client.request('get', '/api/v1/cases/{caseId}/findings', {
        path: { caseId }, query: { analysis_run_id: selectedRun, limit, offset: nextOffset }, signal: request.signal,
      });
      if (!current()) return;
      if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
          page.limit !== limit || page.offset !== nextOffset ||
          page.items.length !== Math.min(limit, Math.max(0, page.total - nextOffset)) ||
          (page.analysis_run_id !== undefined && !uuid(page.analysis_run_id)) ||
          (selectedRun !== undefined && page.analysis_run_id !== selectedRun) ||
          page.items.some(item => !validEntry(item, caseId, page.analysis_run_id)) ||
          new Set(page.items.map(item => item.id)).size !== page.items.length ||
          (!page.analysis_run_id && page.total !== 0)) {
        throw Error('Invalid finding response.');
      }
      if (selectedRun) {
        if (total !== undefined && total !== page.total) throw Error('Snapshot total changed.');
        for (const [i, item] of page.items.entries()) {
          const previous = seen.get(nextOffset + i);
          if (previous && computedKey(previous) !== computedKey(item)) throw Error('Snapshot changed.');
          for (const [position, known] of seen) {
            if (position !== nextOffset + i && known.id === item.id) throw Error('Snapshot membership changed.');
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
      publish({ ...initial(), status: 'ready', page });
      if (selectedRun) onSelectedRun?.(selectedRun);
    } catch (error) {
      if (!current()) return;
      publish({ ...initial(), status: 'error', message: safeError(error) });
    } finally { if (pending === request) pending = undefined; }
  }
  async function select(id: string) {
    if (!enabled || state.status !== 'ready') return;
    const finding = state.page?.items.find(f => f.id === id);
    if (!finding) return;
    sources?.abort();
    publish({ ...state, selectedId: id, citations: [], citationStatus: 'loading', citationMessage: '' });
    const request = sources = new AbortController();
    const current = () => enabled && sources === request && !request.signal.aborted && session === client.getSessionVersion();
    try {
      const run = await client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', {
        path: { caseId, runId: finding.analysis_run_id }, signal: request.signal,
      });
      if (!current()) return;
      const snapshot = run.input_snapshot;
      if (run.id !== finding.analysis_run_id || run.case_id !== caseId || run.status !== 'completed' ||
          !snapshot || snapshot.case_id !== caseId || !ids(snapshot.processing_run_ids, false) ||
          !ids(snapshot.observation_ids, false) || !ids(snapshot.evidence_ids, false) ||
          !finding.observation_ids.every(id => snapshot.observation_ids.includes(id)) ||
          !finding.evidence_ids.every(id => snapshot.evidence_ids.includes(id)) ||
          !(finding.contradicting_evidence_ids ?? []).every(id => snapshot.evidence_ids.includes(id))) throw Error('Invalid snapshot.');
      const found = new Map<string, Observation>();
      // A processing selector is sufficient; do not query latest entity/event or observation lists.
      for (const processingRunId of snapshot.processing_run_ids) {
        let total: number | undefined;
        for (let offset = 0; ; offset += 100) {
          const page = await client.request('get', '/api/v1/cases/{caseId}/observations', {
            path: { caseId }, query: { processing_run_id: processingRunId, limit: 100, offset }, signal: request.signal,
          });
          if (!current()) return;
          if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
              page.limit !== 100 || page.offset !== offset || (total !== undefined && total !== page.total) ||
              page.items.length !== Math.min(100, Math.max(0, page.total - offset))) throw Error('Invalid sources.');
          total = page.total;
          for (const item of page.items) {
            if (!item || !uuid(item.id) || item.case_id !== caseId || item.processing_run_id !== processingRunId ||
                !snapshot.evidence_ids.includes(item.evidence_id) || !snapshot.observation_ids.includes(item.id) ||
                typeof item.source_locator !== 'string' || !item.source_locator.trim()) throw Error('Invalid source.');
            if (finding.observation_ids.includes(item.id)) {
              if (found.has(item.id) || !finding.evidence_ids.includes(item.evidence_id)) throw Error('Invalid citation.');
              found.set(item.id, item);
            }
          }
          if (offset + page.items.length >= total) break;
        }
      }
      if (found.size !== finding.observation_ids.length) throw Error('Missing citations.');
      publish({ ...state, citations: finding.observation_ids.map(id => found.get(id)!), citationStatus: 'ready' });
    } catch (error) {
      if (current()) publish({ ...state, citations: [], citationStatus: 'error', citationMessage: safeError(error) });
    } finally { if (sources === request) sources = undefined; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true; session = client.getSessionVersion();
      unsubscribe?.();
      unsubscribe = client.subscribeSession(() => {
        enabled = false; pending?.abort(); sources?.abort(); pending = undefined; seen.clear(); total = undefined; selectedRun = analysisRunId;
        publish({ ...initial(), status: 'error', message: client.hasToken() ?
          'Session changed. Select the case again.' : 'Authentication required. Open a session again before retrying.' });
      });
      if (!client.hasToken()) publish({ ...initial(), status: 'error', message: 'Authentication required. Open a session again before retrying.' });
      else void load(0);
    },
    load, select,
    dispose() {
      enabled = false; pending?.abort(); sources?.abort(); pending = sources = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); seen.clear();
      total = undefined; offset = 0; selectedRun = analysisRunId; state = initial();
    },
  };
}
