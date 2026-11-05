import type { ApiClient } from '../api/client';
import type { components } from '../api/schema';
export type CaseMetrics = { evidence: number; entities: number; links: number | null; conflicts: number | null; priority: number | null };

type Page<T> = { items: T[]; total: number; offset: number; limit: number; analysis_run_id?: string };
async function collect<T>(read: (offset: number) => Promise<Page<T>>, runId: string): Promise<T[]> {
  const items: T[] = []; let total: number | undefined;
  do {
    const page = await read(items.length);
    if (page.analysis_run_id !== runId || !Number.isSafeInteger(page.total) || page.total < 0 ||
        page.offset !== items.length || page.limit < 1 || page.items.length !== Math.min(page.limit, page.total - page.offset) ||
        (total !== undefined && total !== page.total)) throw Error('Inconsistent metrics pages');
    total = page.total; items.push(...page.items);
  } while (items.length < total);
  return items;
}
export async function loadCaseMetrics(client: ApiClient, caseId: string, runId: string | null, signal: AbortSignal): Promise<CaseMetrics> {
  const options = { path: { caseId }, query: { limit: 1, offset: 0 }, signal };
  const [evidence, entities] = await Promise.all([
    client.request('get', '/api/v1/cases/{caseId}/evidence', options),
    client.request('get', '/api/v1/cases/{caseId}/entities', options),
  ]);
  if (![evidence.total, entities.total].every(n => Number.isSafeInteger(n) && n >= 0) ||
      evidence.items.some(item => item.case_id !== caseId) || entities.items.some(item => item.case_id !== caseId)) throw Error('Invalid totals');
  const counts: CaseMetrics = { evidence: evidence.total, entities: entities.total, links: null, conflicts: null, priority: null };
  if (!runId) return counts;
  const [graph, findings, triage] = await Promise.all([
    client.request('get', '/api/v1/cases/{caseId}/graph', { path: { caseId }, query: { analysis_run_id: runId }, signal }),
    collect<components['schemas']['Finding']>(offset => client.request('get', '/api/v1/cases/{caseId}/findings', {
      path: { caseId }, query: { analysis_run_id: runId, limit: 100, offset }, signal,
    }), runId),
    collect<components['schemas']['TriageEntry']>(offset => client.request('get', '/api/v1/cases/{caseId}/triage', {
      path: { caseId }, query: { analysis_run_id: runId, limit: 100, offset }, signal,
    }), runId),
  ]);
  if (graph.case_id !== caseId || graph.analysis_run_id !== runId || graph.nodes.some(n => n.case_id !== caseId) ||
      graph.edges.some(e => e.case_id !== caseId) || findings.some(f => f.case_id !== caseId || f.analysis_run_id !== runId)) throw Error('Invalid metrics scope');
  const nodes = new Map(graph.nodes.map(n => [n.id, n]));
  counts.links = graph.edges.filter(edge => new Set([
    ...edge.evidence_ids, ...(nodes.get(edge.from_id)?.evidence_ids ?? []), ...(nodes.get(edge.to_id)?.evidence_ids ?? []),
  ]).size > 1).length;
  counts.priority = triage.filter(entry => entry.effective_priority === 'P1').length;
  counts.conflicts = 0;
  for (const finding of findings.filter(f => f.kind === 'conflict')) {
    const reviews = await client.request('get', '/api/v1/cases/{caseId}/findings/{findingId}/reviews', {
      path: { caseId, findingId: finding.id }, signal,
    });
    if (reviews.some(r => r.case_id !== caseId || r.finding_id !== finding.id)) throw Error('Invalid reviews');
    const latest = [...reviews].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)).at(-1);
    // Accepting a conflict confirms the finding; it does not resolve the conflicting evidence.
    if (latest?.decision !== 'rejected') counts.conflicts++;
  }
  return counts;
}
