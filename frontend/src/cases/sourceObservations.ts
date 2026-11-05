import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';
import type { SourceFocus } from './mediaLocators';
type Observation = components['schemas']['Observation'];

/** Pin the first page's completed output before continuing; never mix processing versions. */
export async function readSourceObservations(client: ApiClient, caseId: string, evidenceId: string,
  signal: AbortSignal, processingRunId?: string): Promise<Observation[]> {
  const items: Observation[] = [], ids = new Set<string>();
  let total: number | undefined, runId = processingRunId;
  do {
    const page = await client.request('get', '/api/v1/cases/{caseId}/observations', {
      path: { caseId }, query: { evidence_id: evidenceId, processing_run_id: runId, limit: 100, offset: items.length }, signal,
    });
    if (signal.aborted) throw Error('Cancelled source read');
    if (!Number.isSafeInteger(page.total) || page.total < 0 || page.offset !== items.length || page.limit !== 100 ||
        page.items.length !== Math.min(100, page.total - page.offset) || (total !== undefined && page.total !== total)) throw Error('Inconsistent source pages');
    total = page.total; runId ??= page.items[0]?.processing_run_id;
    for (const item of page.items) {
      if (item.case_id !== caseId || item.evidence_id !== evidenceId || !runId || item.processing_run_id !== runId ||
          !item.id || ids.has(item.id) || typeof item.source_locator !== 'string' || typeof item.raw_value !== 'string' ||
          !Number.isFinite(item.extraction_confidence) || item.extraction_confidence < 0 || item.extraction_confidence > 1) throw Error('Invalid source observations');
      ids.add(item.id); items.push(item);
    }
  } while (items.length < total);
  return items;
}

export async function resolveSourceObservations(client: ApiClient, caseId: string, evidenceId: string,
  signal: AbortSignal, processingRunId?: string, focus?: SourceFocus) {
  const requestedRun = focus?.processing_run_id ?? processingRunId;
  const items = await readSourceObservations(client, caseId, evidenceId, signal, requestedRun);
  if (!focus?.observation_id || items.some(item => item.id === focus.observation_id)) return items;
  if (!requestedRun) {
    // Q&A citations carry an observation UUID but may precede a later processing output.
    const runs = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', {
      path: { caseId, evidenceId }, signal,
    });
    if (runs.some(run => run.case_id !== caseId || run.evidence_id !== evidenceId)) throw Error('Invalid source history');
    for (const run of [...runs].reverse()) {
      if (run.status !== 'completed' || run.id === items[0]?.processing_run_id) continue;
      const historical = await readSourceObservations(client, caseId, evidenceId, signal, run.id);
      if (historical.some(item => item.id === focus.observation_id)) return historical;
    }
  }
  throw Error('Cited observation unavailable');
}
