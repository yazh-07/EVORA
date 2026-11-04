import { ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';

export type Graph = components['schemas']['Graph'];
type Observation = components['schemas']['Observation'];
export type GraphSelection = { kind: 'node' | 'edge'; id: string };
export type GraphState = {
  status: 'idle' | 'loading' | 'ready' | 'error'; graph: Graph | null; message: string;
  selection: GraphSelection | null; citations: Observation[];
  citationStatus: 'idle' | 'loading' | 'ready' | 'error'; citationMessage: string;
};
const initial = (): GraphState => ({ status: 'idle', graph: null, message: '', selection: null,
  citations: [], citationStatus: 'idle', citationMessage: '' });
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
const ids = (v: unknown, nonempty = true): v is string[] => Array.isArray(v) && (!nonempty || v.length > 0) && v.every(uuid) && new Set(v).size === v.length;
const safeError = (error: unknown) => error instanceof ApiHttpError && error.status === 404 ?
  'Case, completed analysis or source unavailable or no longer accessible.' : 'Could not load a consistent graph or its sources. Retry the request.';
function validGraph(g: Graph, caseId: string, runId?: string): boolean {
  if (!g || g.case_id !== caseId || !Array.isArray(g.nodes) || !Array.isArray(g.edges) ||
      (g.analysis_run_id !== undefined && !uuid(g.analysis_run_id)) ||
      (runId !== undefined && g.analysis_run_id !== runId) ||
      ((g.nodes.length > 0 || g.edges.length > 0) && !g.analysis_run_id)) return false;
  if (g.nodes.some(n => !n || !uuid(n.id) || n.case_id !== caseId || typeof n.kind !== 'string' ||
      typeof n.label !== 'string' || !ids(n.evidence_ids)) || new Set(g.nodes.map(n => n.id)).size !== g.nodes.length) return false;
  const nodes = new Set(g.nodes.map(n => n.id));
  return new Set(g.edges.map(e => e?.id)).size === g.edges.length && g.edges.every(e => e && uuid(e.id) &&
    e.case_id === caseId && nodes.has(e.from_id) && nodes.has(e.to_id) && typeof e.kind === 'string' &&
    ids(e.evidence_ids) && ids(e.observation_ids) && Number.isFinite(e.confidence) && e.confidence >= 0 && e.confidence <= 1);
}

/** One case, session and completed snapshot. Never fall back to live sources. */
export function createGraphController(client: ApiClient, caseId: string, analysisRunId?: string,
  onSelectedRun?: (id: string) => void) {
  let state = initial(), enabled = false, session = client.getSessionVersion();
  let selectedRun = analysisRunId;
  let pending: AbortController | undefined, sources: AbortController | undefined;
  let unsubscribe: (() => void) | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: GraphState) => { state = next; listeners.forEach(fn => fn()); };
  const active = (request: AbortController) => enabled && !request.signal.aborted && session === client.getSessionVersion();
  async function load() {
    if (!enabled || !client.hasToken() || session !== client.getSessionVersion()) return;
    pending?.abort(); sources?.abort();
    const request = pending = new AbortController();
    publish({ ...initial(), status: 'loading' });
    try {
      const graph = await client.request('get', '/api/v1/cases/{caseId}/graph', {
        path: { caseId }, query: { analysis_run_id: selectedRun }, signal: request.signal,
      });
      if (!active(request) || pending !== request) return;
      if (!validGraph(graph, caseId, selectedRun)) throw Error('Invalid graph.');
      selectedRun = graph.analysis_run_id;
      publish({ ...initial(), status: 'ready', graph });
      if (selectedRun) onSelectedRun?.(selectedRun);
    } catch (error) {
      if (active(request) && pending === request) publish({ ...initial(), status: 'error', message: safeError(error) });
    } finally { if (pending === request) pending = undefined; }
  }
  async function select(selection: GraphSelection) {
    if (!enabled || state.status !== 'ready' || !state.graph) return;
    const graph = state.graph;
    const record = selection.kind === 'node' ? graph.nodes.find(n => n.id === selection.id) : graph.edges.find(e => e.id === selection.id);
    if (!record) return;
    sources?.abort();
    publish({ ...state, selection, citations: [], citationStatus: selection.kind === 'edge' ? 'loading' : 'idle', citationMessage: '' });
    if (selection.kind === 'node') return;
    const edge = graph.edges.find(e => e.id === selection.id)!;
    const request = sources = new AbortController();
    const current = () => active(request) && sources === request;
    try {
      const run = await client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', {
        path: { caseId, runId: graph.analysis_run_id! }, signal: request.signal,
      });
      if (!current()) return;
      const snapshot = run.input_snapshot;
      if (run.id !== graph.analysis_run_id || run.case_id !== caseId || run.status !== 'completed' ||
          !snapshot || snapshot.case_id !== caseId || !ids(snapshot.processing_run_ids, false) ||
          !ids(snapshot.observation_ids, false) || !ids(snapshot.evidence_ids, false) ||
          !edge.observation_ids.every(id => snapshot.observation_ids.includes(id)) ||
          !edge.evidence_ids.every(id => snapshot.evidence_ids.includes(id))) throw Error('Invalid snapshot.');
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
            if (edge.observation_ids.includes(item.id)) {
              if (found.has(item.id) || !edge.evidence_ids.includes(item.evidence_id)) throw Error('Invalid citation.');
              found.set(item.id, item);
            }
          }
          if (offset + page.items.length >= total) break;
        }
      }
      if (found.size !== edge.observation_ids.length) throw Error('Missing citations.');
      publish({ ...state, citations: edge.observation_ids.map(id => found.get(id)!), citationStatus: 'ready' });
    } catch (error) {
      if (current()) publish({ ...state, citations: [], citationStatus: 'error', citationMessage: safeError(error) });
    } finally { if (sources === request) sources = undefined; }
  }
  return {
    getSnapshot: () => state,
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; },
    start() {
      if (enabled) return;
      enabled = true; session = client.getSessionVersion();
      unsubscribe?.();
      unsubscribe = client.subscribeSession(() => {
        enabled = false; pending?.abort(); sources?.abort();
        publish({ ...initial(), status: 'error', message: client.hasToken() ? 'Session changed. Select the case again.' :
          'Authentication required. Open a session again before retrying.' });
      });
      if (client.hasToken()) void load();
      else publish({ ...initial(), status: 'error', message: 'Authentication required. Open a session again before retrying.' });
    },
    load, select,
    dispose() {
      enabled = false; pending?.abort(); sources?.abort(); pending = sources = undefined;
      unsubscribe?.(); unsubscribe = undefined; listeners.clear(); state = initial(); selectedRun = analysisRunId;
    },
  };
}
