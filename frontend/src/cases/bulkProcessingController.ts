import type { ApiClient } from '../api/client';
import { ApiHttpError } from '../api/client';
import type { components } from '../api/schema';
import { validEvidence } from './evidenceStore';
import type { Evidence } from './evidenceStore';
import { validRun, type ProcessingRun } from './processingController';
import { readSourceObservations } from './sourceObservations';

export type BulkOptions = {
  evidenceIds?: string[];
  reprocess?: boolean;
  vision?: { provider: components['schemas']['Settings']['qa_provider']; model: string; endpoint: string; consent: boolean };
};
export type BulkItem = { evidence: Evidence; status: 'waiting' | 'checking' | 'queued' | 'running' | 'completed' | 'failed' | 'skipped' | 'unknown'; message: string; run?: ProcessingRun };
export type BulkState = { status: 'idle' | 'running' | 'done' | 'stopped' | 'error'; items: BulkItem[]; message: string };
const initial = (): BulkState => ({ status: 'idle', items: [], message: '' });

/** Serial, case-wide queue over existing authorized endpoints. Never auto-retries a POST. */
export function createBulkProcessingController(client: ApiClient, caseId: string, pollMs = 1000) {
  let state = initial(), disposed = false;
  let pending: AbortController | undefined;
  const listeners = new Set<() => void>();
  const publish = (next: BulkState) => { state = next; listeners.forEach(listener => listener()); };
  const stop = () => {
    pending?.abort();
    if (state.status === 'running') publish({ ...state, status: 'stopped', message: 'Queue stopped. A request already sent may still finish on the server. Check its processing history before retrying.' });
  };
  let unsubscribe: (() => void) | undefined;
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    stop,
    start() { disposed = false; unsubscribe?.(); unsubscribe = client.subscribeSession(stop); },
    async submit(options: BulkOptions = {}) {
      if (disposed || state.status === 'running' || !client.hasToken() || client.getUser()?.role === 'reviewer') return;
      if (options.vision && (!options.vision.model || !options.vision.endpoint || (options.vision.provider !== 'ollama' && !options.vision.consent))) {
        publish({ ...initial(), status: 'error', message: 'Choose an image model and confirm the external destination before processing media.' }); return;
      }
      const settings = options.vision ? { ...options.vision } : undefined;
      const request = pending = new AbortController(), session = client.getSessionVersion();
      const active = () => !disposed && !request.signal.aborted && session === client.getSessionVersion();
      const check = () => { if (!active()) throw Error('Queue stopped'); };
      const update = (index: number, change: Partial<BulkItem>) => {
        check(); publish({ ...state, items: state.items.map((item, i) => i === index ? { ...item, ...change } : item) });
      };
      const wait = () => new Promise<void>((resolve, reject) => {
        const abort = () => { clearTimeout(timer); reject(Error('Queue stopped')); };
        const timer = setTimeout(() => { request.signal.removeEventListener('abort', abort); resolve(); }, pollMs);
        request.signal.addEventListener('abort', abort, { once: true });
        if (request.signal.aborted) abort();
      });
      const verify = (run: ProcessingRun, item: Evidence) => {
        if (!validRun(run, caseId, item.id)) throw Error('Invalid processing response');
        return run;
      };
      async function follow(run: ProcessingRun, item: Evidence, index: number) {
        const deadline = Date.now() + 15 * 60 * 1000;
        while (run.status === 'queued' || run.status === 'running') {
          update(index, { run, status: run.status, message: 'Waiting for the server to finish.' });
          if (Date.now() > deadline) throw Error('Status monitoring timed out');
          await wait(); check();
          const next = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
            path: { caseId, evidenceId: item.id, runId: run.id }, signal: request.signal,
          });
          check(); verify(next, item);
          if (next.id !== run.id) throw Error('Unexpected processing run');
          run = next;
        }
        return run;
      }
      publish({ ...initial(), status: 'running', message: 'Loading all case evidence…' });
      try {
        const items: Evidence[] = [], ids = new Set<string>();
        let total: number | undefined;
        do {
          const page = await client.request('get', '/api/v1/cases/{caseId}/evidence', {
            path: { caseId }, query: { limit: 100, offset: items.length }, signal: request.signal,
          });
          check();
          if (!Number.isSafeInteger(page.total) || page.total < 0 || page.limit !== 100 || page.offset !== items.length ||
              !Array.isArray(page.items) || page.items.length !== Math.min(100, page.total - items.length) ||
              (total !== undefined && total !== page.total)) throw Error('Evidence changed while loading');
          total = page.total;
          for (const item of page.items) {
            if (!validEvidence(item, caseId) || ids.has(item.id)) throw Error('Invalid evidence page');
            ids.add(item.id); items.push(item);
          }
        } while (items.length < total);
        if (options.evidenceIds) {
          const selected = new Set(options.evidenceIds);
          if (!selected.size || selected.size !== options.evidenceIds.length || [...selected].some(id => !ids.has(id))) throw Error('Selection unavailable');
          const chosen = items.filter(item => selected.has(item.id)); items.splice(0, items.length, ...chosen);
        }
        publish({ status: 'running', message: 'Processing one source at a time. New uploads are included on the next batch.', items: items.map(evidence => ({ evidence, status: 'waiting', message: '' })) });
        for (let index = 0; index < items.length; index++) {
          check(); const item = items[index]!;
          if (!supportsBasicProcessing(item)) { update(index, { status: 'skipped', message: 'Standalone audio extraction is unavailable.' }); continue; }
          const vision = settings && (item.kind === 'image' || item.kind === 'video') ? settings : undefined;
          update(index, { status: 'checking', message: 'Checking processing history…' });
          let sent = false;
          try {
            const history = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId: item.id }, signal: request.signal });
            check();
            if (!Array.isArray(history) || history.some(run => !validRun(run, caseId, item.id))) throw Error('Invalid processing history');
            const ongoing = history.filter(run => run.status === 'queued' || run.status === 'running');
            // Join existing work rather than creating competing runs for this source.
            for (const run of ongoing) { const finished = await follow(run, item, index); history.push(finished); }
            const completed = history.filter(run => run.status === 'completed').sort((a, b) => b.created_at.localeCompare(a.created_at));
            let satisfied = !options.reprocess && completed.length > 0;
            if (vision && satisfied) {
              const observations = await readSourceObservations(client, caseId, item.id, request.signal);
              check();
              satisfied = observations.some(observation => observation.kind === (item.kind === 'image' ? 'image.provenance' : 'video.provenance'));
            }
            if (satisfied) { update(index, { status: 'skipped', message: 'Completed output already available.', run: completed[0] }); continue; }
            const common = { path: { caseId, evidenceId: item.id }, header: { 'Idempotency-Key': crypto.randomUUID() }, signal: request.signal };
            sent = true;
            const run = vision ? item.kind === 'image' ? await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/image-analysis', {
              ...common, body: { expected_provider: vision.provider, expected_model: vision.model, expected_endpoint: vision.endpoint, confirm_external_processing: vision.consent },
            }) : await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/video-analysis', {
              ...common, body: { expected_provider: vision.provider, expected_model: vision.model, expected_endpoint: vision.endpoint, confirm_external_processing: vision.consent,
                sample_interval_seconds: 5, max_frames: 12, transcribe_speech: false },
            }) : await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', common);
            check(); verify(run, item);
            const finished = await follow(run, item, index);
            update(index, { run: finished, status: finished.status === 'completed' ? 'completed' : 'failed', message: finished.status === 'completed' ? 'Processing completed.' : 'Processing failed. Open the source to inspect the run.' });
          } catch (error) {
            if (!active()) return;
            if (error instanceof ApiHttpError && (error.status === 401 || error.status === 403)) throw error;
            const definite = error instanceof ApiHttpError && error.status >= 400 && error.status < 500;
            update(index, { status: sent && !definite ? 'unknown' : 'failed', message: sent && !definite ? 'Could not confirm the result. Check processing history before retrying.' : 'Could not process this source. Open it to inspect its format, settings and processing history.' });
          }
        }
        if (active()) publish({ ...state, status: 'done', message: 'Processing finished.' });
      } catch {
        if (active()) publish({ ...state, status: 'error', message: 'Batch stopped. Evidence may have changed or access could not be confirmed. Refresh the case and check processing history before retrying.' });
      }
    },
    dispose() { disposed = true; pending?.abort(); unsubscribe?.(); listeners.clear(); state = initial(); },
  };
}


export function supportsBasicProcessing(item: Evidence) {
  return item.kind !== 'audio' && !(item.kind === 'document' && /\.(pdf|docx?|pcapng?|bin|raw|dump)$/i.test(item.filename));
}
export type BatchInventory = { evidence: Evidence; status: 'pending' | 'ready' | 'running' | 'unavailable'; visionComplete?: boolean }[];
/** Read all pages before presenting an actionable case-wide count. No writes. */
export async function readBatchInventory(client: ApiClient, caseId: string, signal: AbortSignal, includeVision = false): Promise<BatchInventory> {
  const items: Evidence[] = []; let total: number | undefined;
  do {
    const page = await client.request('get', '/api/v1/cases/{caseId}/evidence', { path: { caseId }, query: { limit: 100, offset: items.length }, signal });
    if (!Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 || page.limit !== 100 || page.offset !== items.length || page.items.length !== Math.min(100, page.total - items.length) || (total !== undefined && total !== page.total) || page.items.some(item => !validEvidence(item, caseId))) throw Error('Evidence changed');
    total = page.total; items.push(...page.items);
  } while (items.length < total);
  if (new Set(items.map(item => item.id)).size !== items.length) throw Error('Duplicate evidence');
  const result: BatchInventory = new Array(items.length); let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(4, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++, evidence = items[index]!;
      if (!supportsBasicProcessing(evidence)) { result[index] = { evidence, status: 'unavailable' }; continue; }
      const runs = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId: evidence.id }, signal });
      if (!Array.isArray(runs) || runs.some(run => !validRun(run, caseId, evidence.id))) throw Error('Invalid history');
      result[index] = { evidence, status: runs.some(run => run.status === 'queued' || run.status === 'running') ? 'running' : runs.some(run => run.status === 'completed') ? 'ready' : 'pending' };
      if (includeVision && ['image', 'video'].includes(evidence.kind) && runs.some(run => run.status === 'completed')) {
        const observations = await readSourceObservations(client, caseId, evidence.id, signal);
        result[index]!.visionComplete = observations.some(item => item.kind === (evidence.kind === 'image' ? 'image.provenance' : 'video.provenance'));
      }
    }
  }));
  signal.throwIfAborted(); return result;
}
