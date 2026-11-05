import { useEffect, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { useAnalysisWorkspace } from './StartAnalysis';
import { loadCaseMetrics, type CaseMetrics as Metrics } from './metricsData';

export function CaseMetrics() {
  const client = useApiClient();
  const { caseId, analysis_run_id } = useAnalysisWorkspace();
  const [state, setState] = useState<{ scope: string; counts?: Metrics; updated?: string; error?: boolean }>({ scope: '' });
  const [refresh, setRefresh] = useState(0);
  const scope = `${caseId}:${analysis_run_id ?? ''}`;
  useEffect(() => {
    let active = true, pending: AbortController | undefined;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      if (!active || pending || document.hidden) return;
      pending = new AbortController();
      try {
        const counts = await loadCaseMetrics(client, caseId, analysis_run_id, pending.signal);
        if (active) setState({ scope, counts, updated: new Date().toLocaleTimeString() });
      } catch { if (active) setState({ scope, error: true }); }
      finally { pending = undefined; if (active) timer = setTimeout(load, 30000); }
    };
    const resume = () => { if (!document.hidden) { clearTimeout(timer); void load(); } };
    const unsubscribe = client.subscribeSession(() => { active = false; pending?.abort(); clearTimeout(timer); setState({ scope, error: true }); });
    void load(); document.addEventListener('visibilitychange', resume);
    return () => { active = false; pending?.abort(); clearTimeout(timer); unsubscribe(); document.removeEventListener('visibilitychange', resume); };
  }, [client, caseId, analysis_run_id, scope, refresh]);
  const counts = state.scope === scope ? state.counts : undefined;
  const entries = [
    ['Total Evidence Items', counts?.evidence, 'Live uploaded evidence', 'blue'],
    ['Extracted Forensic Entities', counts?.entities, 'Live extracted candidate entities', 'gold'],
    ['Cross-source Relationship Links', counts?.links, 'Selected analysis: links involving more than one evidence source', 'cyan'],
    ['Unresolved Contradictions / Conflicts', counts?.conflicts, 'Selected analysis: conflicts whose latest review is not rejected. Accepting a finding does not resolve the conflict.', 'coral'],
    ['Priority 1 Leads', counts?.priority, 'Selected analysis: evidence with effective P1 priority, including current overrides', 'purple'],
  ] as const;
  return <section className="case-metrics" aria-label="Investigative metrics">
    <div className="metrics-heading"><span className="section-label">INVESTIGATION PULSE</span><span>{state.scope === scope && state.error ? 'Metrics unavailable' : state.updated && counts ? `Updated ${state.updated} · refreshes every 30s` : 'Loading metrics…'}</span><button type="button" onClick={() => setRefresh(value => value + 1)}>Refresh metrics</button></div>
    <dl className="metrics-grid">{entries.map(([label, value, description, color]) => <div key={label} className={`metric metric-${color}`} title={description}><dt>{label}</dt><dd>{value == null ? '—' : value.toLocaleString()}</dd></div>)}</dl>
    {!analysis_run_id && <p>Complete an analysis to populate relationship, conflict and priority metrics.</p>}
  </section>;
}
