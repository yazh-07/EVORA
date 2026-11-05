import { useEffect, useState } from 'react';
import type { ApiClient } from '../api/client';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';

export type EvidenceRecord = components['schemas']['Evidence'];
export type EventRecord = components['schemas']['Event'];
export type FindingRecord = components['schemas']['Finding'];
export type ReviewRecord = components['schemas']['ReviewDecision'];
export type AnalysisRecord = components['schemas']['AnalysisRun'];
export type Page<T> = { items: T[]; total: number; offset: number; limit: number };

/** Never publish partial or mixed-case results as a complete collection. */
export async function collectPages<T extends { id: string; case_id: string }>(
  caseId: string, signal: AbortSignal, read: (offset: number) => Promise<Page<T>>,
): Promise<T[]> {
  const items: T[] = [], ids = new Set<string>();
  let total: number | undefined;
  do {
    signal.throwIfAborted();
    const page = await read(items.length);
    signal.throwIfAborted();
    if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0 ||
        page.offset !== items.length || !Number.isInteger(page.limit) || page.limit < 1 || page.limit > 100 ||
        page.items.length > page.limit || items.length + page.items.length > page.total ||
        (total !== undefined && total !== page.total) || (!page.items.length && items.length < page.total)) {
      throw Error('The collection changed while loading. Refresh to try again.');
    }
    total = page.total;
    for (const item of page.items) {
      if (!item || item.case_id !== caseId || typeof item.id !== 'string' || !item.id || ids.has(item.id)) throw Error('Invalid source collection.');
      ids.add(item.id); items.push(item);
    }
  } while (items.length < total);
  return items;
}
export async function loadTimeline(client: ApiClient, caseId: string, signal: AbortSignal) {
  const events = await collectPages(caseId, signal, offset => client.request('get', '/api/v1/cases/{caseId}/events', {
    path: { caseId }, query: { limit: 100, offset }, signal,
  }));
  const evidence = await collectPages(caseId, signal, offset => client.request('get', '/api/v1/cases/{caseId}/evidence', {
    path: { caseId }, query: { limit: 100, offset }, signal,
  }));
  const ids = new Set(evidence.map(item => item.id));
  if (events.some(event => typeof event.summary !== 'string' || typeof event.kind !== 'string' ||
      !Array.isArray(event.evidence_ids) || !event.evidence_ids.length || event.evidence_ids.some(id => !ids.has(id)) ||
      !Array.isArray(event.observation_ids) || (event.observed_at_utc !== undefined && !Number.isFinite(Date.parse(event.observed_at_utc))))) {
    throw Error('An event or source could not be verified.');
  }
  return { events, evidence };
}
export type ReportData = { run: AnalysisRecord; findings: FindingRecord[]; evidence: EvidenceRecord[]; reviews: Record<string, ReviewRecord | undefined> };
export async function loadReport(client: ApiClient, caseId: string, runId: string, signal: AbortSignal): Promise<ReportData> {
  const run = await client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', { path: { caseId, runId }, signal });
  if (run.id !== runId || run.case_id !== caseId || run.status !== 'completed' || run.input_snapshot.case_id !== caseId) throw Error('Analysis unavailable.');
  const findings = await collectPages(caseId, signal, async offset => {
    const page = await client.request('get', '/api/v1/cases/{caseId}/findings', { path: { caseId }, query: { analysis_run_id: runId, limit: 100, offset }, signal });
    if (page.analysis_run_id !== runId) throw Error('Analysis changed.');
    return page;
  });
  const evidence: EvidenceRecord[] = [];
  for (const evidenceId of run.input_snapshot.evidence_ids) {
    signal.throwIfAborted();
    const item = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId, evidenceId }, signal });
    if (item.id !== evidenceId || item.case_id !== caseId || !/^[a-f0-9]{64}$/.test(item.sha256)) throw Error('Evidence unavailable.');
    evidence.push(item);
  }
  const reviews: ReportData['reviews'] = {};
  for (const finding of findings) {
    if (finding.analysis_run_id !== runId || typeof finding.summary !== 'string' ||
        !Array.isArray(finding.evidence_ids) || !finding.evidence_ids.length ||
        !finding.evidence_ids.every(id => run.input_snapshot.evidence_ids.includes(id)) ||
        !Array.isArray(finding.observation_ids) || !finding.observation_ids.length ||
        !finding.observation_ids.every(id => run.input_snapshot.observation_ids.includes(id))) throw Error('Finding references unavailable.');
    const history = await client.request('get', '/api/v1/cases/{caseId}/findings/{findingId}/reviews', {
      path: { caseId, findingId: finding.id }, signal,
    });
    if (!Array.isArray(history) || history.some(review => review.case_id !== caseId || review.finding_id !== finding.id ||
        typeof review.actor_id !== 'string' || typeof review.reason !== 'string' || typeof review.id !== 'string' ||
        !['accepted', 'rejected', 'needs_investigation'].includes(review.decision) || !Number.isFinite(Date.parse(review.created_at))) ||
        new Set(history.map(review => review.id)).size !== history.length) throw Error('Review history unavailable.');
    reviews[finding.id] = [...history].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)).at(-1);
  }
  return { run, findings, evidence, reviews };
}

/** Data belongs to one mounted case and session. A late response can never restore it after logout. */
export function useWorkspaceData<T>(loader: (client: ApiClient, signal: AbortSignal) => Promise<T>) {
  const client = useApiClient();
  const [revision, refresh] = useState(0);
  const [state, setState] = useState<{ data?: T; loading: boolean; error?: string }>({ loading: true });
  useEffect(() => {
    const request = new AbortController();
    let active = true;
    setState({ loading: true });
    const unsubscribe = client.subscribeSession(() => { active = false; request.abort(); setState({ loading: false, error: 'Session changed. Open the case again.' }); });
    void loader(client, request.signal).then(data => { if (active) setState({ data, loading: false }); })
      .catch(() => { if (active) setState({ loading: false, error: 'Could not load the complete records. Check your connection and refresh.' }); });
    return () => { active = false; request.abort(); unsubscribe(); };
  }, [client, loader, revision]);
  return { ...state, refresh: () => refresh(value => value + 1) };
}
