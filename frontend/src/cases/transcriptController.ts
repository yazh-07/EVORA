import { ApiHttpError } from '../api/client';
import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';
import { createOriginalDownload } from './downloadController';
import type { DownloadState } from './downloadController';
import type { Evidence } from './evidenceStore';

type Observation = components['schemas']['Observation'];
type Revision = components['schemas']['TranscriptRevision'];
type RevisionBody = components['schemas']['CreateTranscriptRevision'];
export type SegmentHistory = {
  open: boolean; status: 'loading' | 'ready' | 'error'; revisions: Revision[];
  originalRunId: string | null; correctedText: string; reason: string;
  submission: 'idle' | 'submitting' | 'success' | 'error' | 'conflict'; message: string;
};
export type TranscriptState = {
  status: 'idle' | 'loading' | 'ready' | 'error'; segments: Observation[];
  baseRunId: string | null; query: string; message: string;
  histories: Record<string, SegmentHistory>; sourceUrl: string; media: DownloadState;
};
const initial = (): TranscriptState => ({ status: 'idle', segments: [], baseRunId: null, query: '', message: '',
  histories: {}, sourceUrl: '', media: { status: 'idle', message: '' } });
export const transcriptRoot = (segment: Observation) => segment.source_observation_id ?? segment.id;
export function transcriptOffsets(locator: string): [number, number] | null {
  const match = /^media:start_ms=(\d+);end_ms=(\d+)$/.exec(locator);
  if (!match) return null;
  const start = Number(match[1]), end = Number(match[2]);
  return Number.isSafeInteger(start) && Number.isSafeInteger(end) && end > start ? [start, end] : null;
}
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const safeError = (error: unknown, action: string) => error instanceof ApiHttpError && error.status === 404
  ? 'Evidence, transcript or processing run unavailable or no longer accessible.'
  : `Could not ${action}. Check your connection and retry.`;

/** Evidence-scoped, in-memory controller. Reads are cancellable; writes serialize against one base output. */
export function createTranscriptController(client: ApiClient, item: Evidence, options: {
  onDerivedRun?: (runId: string) => void;
} = {}) {
  const caseId = item.case_id, evidenceId = item.id;
  let state = initial();
  let enabled = false, session = client.getSessionVersion();
  let unsubscribe: (() => void) | undefined;
  let unsubscribeMedia: (() => void) | undefined;
  let loading: AbortController | undefined;
  const requests = new Set<AbortController>();
  const listeners = new Set<() => void>();
  const attempts = new Map<string, { key: string; body: RevisionBody }>();
  const active = () => enabled && session === client.getSessionVersion() && client.hasToken();
  const current = (request: AbortController) => active() && !request.signal.aborted;
  const publish = (next: TranscriptState) => { state = next; listeners.forEach(listener => listener()); };
  const updateHistory = (root: string, patch: Partial<SegmentHistory>) => {
    const history = state.histories[root];
    if (history) publish({ ...state, histories: { ...state.histories, [root]: { ...history, ...patch } } });
  };
  const writing = () => Object.values(state.histories).some(history => history.submission === 'submitting');
  const media = createOriginalDownload(client, item, blob => {
    const url = URL.createObjectURL(new Blob([blob], { type: item.media_type }));
    publish({ ...state, sourceUrl: url });
    return () => URL.revokeObjectURL(url);
  });
  function cancel() { requests.forEach(request => request.abort()); requests.clear(); loading = undefined; }

  function validObservation(value: Observation, runId?: string): boolean {
    return !!value && value.case_id === caseId && value.evidence_id === evidenceId && uuid(value.id) &&
      uuid(value.processing_run_id) && (!runId || value.processing_run_id === runId) &&
      typeof value.kind === 'string' && typeof value.raw_value === 'string' && typeof value.normalized_value === 'string' &&
      typeof value.source_locator === 'string' && Number.isFinite(value.extraction_confidence) &&
      value.extraction_confidence >= 0 && value.extraction_confidence <= 1 &&
      (value.source_observation_id === undefined || uuid(value.source_observation_id)) &&
      (value.transcript_revision_id === undefined || (uuid(value.transcript_revision_id) && uuid(value.source_observation_id))) &&
      (value.kind !== 'transcript.segment' || transcriptOffsets(value.source_locator) !== null);
  }
  function validRevision(value: Revision, root: string): boolean {
    return !!value && value.case_id === caseId && value.evidence_id === evidenceId && value.source_observation_id === root &&
      ['id', 'processing_run_id', 'base_processing_run_id', 'derived_processing_run_id', 'derived_observation_id']
        .every(key => uuid(value[key as keyof Revision])) &&
      (value.previous_revision_id === null || uuid(value.previous_revision_id)) &&
      typeof value.corrected_text === 'string' && !!value.corrected_text.trim() && value.corrected_text.length <= 20000 &&
      typeof value.reason === 'string' && !!value.reason.trim() && value.reason.length <= 2000 &&
      typeof value.actor_id === 'string' && !!value.actor_id && typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at));
  }
  async function observations(request: AbortController, runId?: string) {
    const result: Observation[] = [];
    let offset = 0, total: number | undefined, selectedRun = runId;
    do {
      const page = await client.request('get', '/api/v1/cases/{caseId}/observations', {
        path: { caseId }, query: { evidence_id: evidenceId, processing_run_id: selectedRun, limit: 100, offset }, signal: request.signal,
      });
      if (!current(request)) return [];
      if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
          !Number.isSafeInteger(page.limit) || page.limit < 1 || page.limit > 100 || page.offset !== offset ||
          (total !== undefined && total !== page.total) || page.items.length > page.limit ||
          page.items.length > page.total - offset || (offset < page.total && !page.items.length) ||
          !page.items.every(value => validObservation(value, selectedRun))) throw Error('Invalid observations.');
      selectedRun ??= page.items[0]?.processing_run_id;
      if (page.items.some(value => value.processing_run_id !== selectedRun)) throw Error('Mixed outputs.');
      total = page.total; result.push(...page.items); offset += page.items.length;
    } while (offset < total);
    if (new Set(result.map(value => value.id)).size !== result.length) throw Error('Duplicate observations.');
    return result;
  }
  // Uncorrected copies expose the root ID but no original run. Resolve that run lazily through existing history APIs.
  async function originalRun(segment: Observation, request: AbortController): Promise<string> {
    if (!segment.source_observation_id) return segment.processing_run_id;
    const runs = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', {
      path: { caseId, evidenceId }, signal: request.signal,
    });
    if (!current(request)) throw Error('Cancelled.');
    if (!Array.isArray(runs) || runs.some(run => !run || !uuid(run.id) || run.case_id !== caseId || run.evidence_id !== evidenceId)) throw Error('Invalid runs.');
    for (const run of runs.filter(run => run.status === 'completed')) {
      const values = await observations(request, run.id);
      const source = values.find(value => value.id === transcriptRoot(segment));
      if (source && source.kind === 'transcript.segment' && !source.source_observation_id) return source.processing_run_id;
      if (!current(request)) throw Error('Cancelled.');
    }
    throw Error('Original run unavailable.');
  }
  async function loadHistory(root: string) {
    const segment = state.segments.find(value => transcriptRoot(value) === root);
    if (!active() || !segment || writing()) return;
    const old = state.histories[root];
    if (old?.status === 'loading') return;
    const request = new AbortController(); requests.add(request);
    publish({ ...state, histories: { ...state.histories, [root]: { open: true, status: 'loading', revisions: [],
      originalRunId: null, correctedText: old?.correctedText ?? segment.normalized_value, reason: old?.reason ?? '', submission: 'idle', message: '' } } });
    try {
      const revisions: Revision[] = [];
      let offset = 0, total: number | undefined;
      do {
        const page = await client.request('get', '/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions', {
          path: { caseId, observationId: root }, query: { limit: 100, offset }, signal: request.signal,
        });
        if (!current(request)) return;
        if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
            !Number.isSafeInteger(page.limit) || page.limit < 1 || page.limit > 100 || page.offset !== offset ||
            (total !== undefined && page.total !== total) || page.items.length > page.limit ||
            page.items.length > page.total - offset || (offset < page.total && !page.items.length) ||
            !page.items.every(value => validRevision(value, root))) throw Error('Invalid history.');
        total = page.total; revisions.push(...page.items); offset += page.items.length;
      } while (offset < total);
      // The server supplies chronological order (including sub-millisecond time precision).
      if (new Set(revisions.map(value => value.id)).size !== revisions.length ||
          revisions.some((value, index) => value.previous_revision_id !== (revisions[index - 1]?.id ?? null)) ||
          revisions.some(value => value.processing_run_id !== revisions[0]?.processing_run_id)) throw Error('Invalid revision chain.');
      const runId = revisions[0]?.processing_run_id ?? await originalRun(segment, request);
      if (!current(request)) return;
      updateHistory(root, { status: 'ready', revisions, originalRunId: runId });
    } catch (error) {
      if (current(request)) updateHistory(root, { status: 'error', message: safeError(error, 'load revision history') });
    } finally { requests.delete(request); }
  }
  async function load() {
    if (!active() || writing()) return;
    cancel(); attempts.clear();
    const request = loading = new AbortController(); requests.add(request);
    const openRoots = Object.entries(state.histories).filter(([, history]) => history.open).map(([root]) => root);
    const oldHistories = state.histories;
    publish({ ...state, status: 'loading', segments: [], histories: {}, baseRunId: null, message: '' });
    try {
      const values = await observations(request);
      if (!current(request)) return;
      const segments = values.filter(value => value.kind === 'transcript.segment')
        .sort((a, b) => transcriptOffsets(a.source_locator)![0] - transcriptOffsets(b.source_locator)![0] || a.id.localeCompare(b.id));
      if (new Set(segments.map(transcriptRoot)).size !== segments.length) throw Error('Duplicate roots.');
      const histories: Record<string, SegmentHistory> = {};
      for (const root of openRoots) if (segments.some(value => transcriptRoot(value) === root) && oldHistories[root]) {
        histories[root] = { ...oldHistories[root], status: 'error', submission: 'idle', message: '' };
      }
      publish({ ...state, status: 'ready', segments, baseRunId: values[0]?.processing_run_id ?? null, histories });
      await Promise.all(openRoots.map(loadHistory));
    } catch (error) {
      if (current(request)) publish({ ...state, status: 'error', segments: [], histories: {}, message: safeError(error, 'load transcript') });
    } finally { requests.delete(request); if (loading === request) loading = undefined; }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start() {
      if (enabled) return;
      enabled = true; session = client.getSessionVersion(); unsubscribe?.();
      media.start();
      unsubscribeMedia = media.subscribe(() => {
        if (active()) publish({ ...state, media: media.getSnapshot() });
      });
      unsubscribe = client.subscribeSession(() => {
        enabled = false; cancel(); attempts.clear(); media.dispose(); unsubscribeMedia?.();
        publish({ ...initial(), status: 'error', message: client.hasToken()
          ? 'Session changed. Select evidence again to load the transcript.' : 'Authentication required. Open a session again before retrying.' });
      });
      void load();
    },
    load, loadHistory,
    setQuery(query: string) { if (active()) publish({ ...state, query }); },
    toggleHistory(root: string, open: boolean) {
      if (!active()) return;
      if (state.histories[root]) updateHistory(root, { open });
      else if (open) void loadHistory(root);
    },
    setDraft(root: string, field: 'correctedText' | 'reason', value: string) {
      if (!active() || writing()) return;
      const history = state.histories[root];
      if (history) updateHistory(root, { [field]: value, submission: history.submission === 'conflict' ? 'conflict' : 'idle',
        message: history.submission === 'conflict' ? history.message : '' });
    },
    async submit(root: string) {
      const history = state.histories[root];
      if (!active() || writing() || state.status !== 'ready' || !history || history.status !== 'ready' ||
          history.submission === 'conflict' || !history.originalRunId || !state.baseRunId) return;
      if (!history.correctedText.trim() || history.correctedText.length > 20000 || !history.reason.trim() || history.reason.length > 2000) {
        updateHistory(root, { submission: 'error', message: 'Enter non-empty corrected text (up to 20000 characters) and a reason (up to 2000 characters).' }); return;
      }
      const body: RevisionBody = { processing_run_id: history.originalRunId, base_processing_run_id: state.baseRunId,
        expected_latest_revision_id: history.revisions.at(-1)?.id ?? null, corrected_text: history.correctedText, reason: history.reason };
      const previous = attempts.get(root);
      const attempt = previous && JSON.stringify(previous.body) === JSON.stringify(body) ? previous : { key: crypto.randomUUID(), body };
      attempts.set(root, attempt);
      const request = new AbortController(); requests.add(request);
      updateHistory(root, { submission: 'submitting', message: '' });
      try {
        const revision = await client.request('post', '/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions', {
          path: { caseId, observationId: root }, body, header: { 'Idempotency-Key': attempt.key }, signal: request.signal,
        });
        if (!current(request)) return;
        if (!validRevision(revision, root) || revision.processing_run_id !== body.processing_run_id ||
            revision.base_processing_run_id !== body.base_processing_run_id || revision.previous_revision_id !== body.expected_latest_revision_id ||
            revision.corrected_text !== body.corrected_text || revision.reason !== body.reason) throw Error('Invalid revision.');
        attempts.delete(root);
        publish({ ...state, baseRunId: revision.derived_processing_run_id, segments: state.segments.map(segment => transcriptRoot(segment) === root
          ? { ...segment, id: revision.derived_observation_id, source_observation_id: root, transcript_revision_id: revision.id,
            processing_run_id: revision.derived_processing_run_id, normalized_value: revision.corrected_text } : segment),
          histories: { ...state.histories, [root]: { ...history, open: state.histories[root]?.open ?? true,
            revisions: [...history.revisions, revision], submission: 'success', reason: '', message: '' } } });
        options.onDerivedRun?.(revision.derived_processing_run_id);
      } catch (error) {
        if (!current(request)) return;
        const conflict = error instanceof ApiHttpError && error.status === 409;
        updateHistory(root, { submission: conflict ? 'conflict' : 'error', message: conflict
          ? 'Stale correction precondition: the transcript output or latest revision changed. Reload transcript and history, review your draft, then submit again.'
          : safeError(error, 'save correction') });
      } finally { requests.delete(request); }
    },
    async download() {
      if (!active()) return;
      publish({ ...state, sourceUrl: '' });
      await media.download();
    },
    dispose() {
      enabled = false; cancel(); attempts.clear(); unsubscribe?.(); unsubscribe = undefined;
      unsubscribeMedia?.(); unsubscribeMedia = undefined; media.dispose(); listeners.clear(); state = initial();
    },
  };
}
