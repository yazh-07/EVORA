import { useCallback, useEffect, useMemo, useRef, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createCaseOverviewController } from './caseOverviewController';
import { useAnalysisWorkspace } from './StartAnalysis';
import { ActivityChart } from './ActivityChart';
import { loadTimeline, useWorkspaceData } from './workspaceData';
import type { ApiClient } from '../api/client';
import type { InvestigationTab } from './InvestigationTabs';

export function InvestigationOverview({ caseId, navigate, addEvidence, activeView = true, inspectEvidence, showTimeline }: { inspectEvidence?: (id: string) => void; showTimeline?: (from: string, to: string) => void; activeView?: boolean; caseId: string; navigate: (tab: InvestigationTab) => void; addEvidence: () => void }) {
  const client = useApiClient();
  const { analysis_run_id, analysisBusy } = useAnalysisWorkspace();
  const readOnly = client.getUser()?.role === 'reviewer';
  const controller = useMemo(() => createCaseOverviewController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  const loader = useCallback((api: ApiClient, signal: AbortSignal) => loadTimeline(api, caseId, signal), [caseId]);
  const workspace = useWorkspaceData(loader);
  const wasActive = useRef(activeView);
  useEffect(() => {
    if (activeView && !wasActive.current) { void controller.load(); workspace.refresh(); }
    wasActive.current = activeView;
  }, [activeView, controller]);
  const summary = state.summary;
  const kinds = Object.entries(summary?.kinds ?? {}).filter(([, count]) => count > 0);
  const palette = ['#a879d4', '#66cbb6', '#e9c967', '#91c584', '#6f94da', '#d890b0', '#a6b4c7', '#cc9b65', '#86b8bf'];
  let accumulated = 0;
  const segments = kinds.map(([, count], index) => {
    const start = accumulated; accumulated += count / (summary?.total || 1) * 100;
    return `${palette[index % palette.length]} ${start}% ${accumulated}%`;
  });
  const recent = [...(workspace.data?.evidence ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 6);
  const needsProcessing = summary ? summary.statuses.unprocessed + summary.statuses.failed : 0;
  const active = summary ? summary.statuses.running + summary.statuses.queued : 0;
  const next = !summary ? null : analysisBusy ? { title: 'Analysis running', text: '', action: 'View evidence', run: () => navigate('evidence') } : summary.total === 0 ? { title: 'No evidence yet', text: readOnly ? 'An investigator can add files.' : '', action: readOnly ? 'View evidence' : 'Add evidence', run: readOnly ? () => navigate('evidence') : addEvidence } : needsProcessing ? { title: `${needsProcessing} ${needsProcessing === 1 ? 'source needs' : 'sources need'} attention`, text: 'Prepare new files or retry failed processing.', action: 'Review evidence', run: () => navigate('evidence') } : active ? { title: 'Preparing evidence', text: `${active} ${active === 1 ? 'file' : 'files'} queued or running.`, action: 'Check progress', run: () => navigate('evidence') } : !analysis_run_id ? readOnly ? { title: 'Ready for analysis', text: 'An investigator can start analysis.', action: 'View timeline', run: () => navigate('timeline') } : null : { title: 'Analysis available', text: '', action: 'Review findings', run: () => navigate('investigation') };
  return <div className="overview-workspace">
    <header className="workspace-section-heading overview-heading"><h2 className="sr-only">Overview</h2><button className="quiet-button" type="button" disabled={state.status === 'loading' || workspace.loading} onClick={() => { void controller.load(); workspace.refresh(); }} aria-label="Refresh overview" title="Refresh overview"><span aria-hidden="true">↻</span></button></header>
    {state.status === 'loading' && <p className="sr-only" role="status">Loading overview…</p>}
    {state.message && <p role="alert">{state.message}</p>}
    <div className="overview-stats" aria-label="Evidence readiness">
      {[
        ['Evidence files', summary?.total, 'Original files', 'M4 4h7l2 3h7v13H4V4Zm0 6h16'],
        ['Ready to review', summary?.statuses.completed, 'Processing complete', 'm5 12 4 4L19 6'],
        ['Processing', summary ? active : undefined, 'Queued or running', 'M12 3a9 9 0 1 1-9 9M12 7v5l3 2'],
        ['Needs attention', summary ? needsProcessing : undefined, 'Unprocessed or failed', 'M12 3 2 21h20L12 3Zm0 6v5m0 3v1'],
      ].map(([label, value, note, path]) => <button key={label} type="button" title={String(note)} onClick={() => navigate('evidence')}><span>{label}<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d={String(path)} /></svg></span><strong>{value ?? '—'}</strong></button>)}
    </div>
    {next && <section className="next-action" aria-label="Next action"><button type="button" className="button-primary" title={[next.title, next.text].filter(Boolean).join('. ')} onClick={next.run}>{next.action}</button></section>}
    <div className="dashboard-charts">
      <div className="dashboard-activity">{workspace.data ? <ActivityChart events={workspace.data.events} from="" to="" select={(from, to) => { if (showTimeline) showTimeline(from, to); else navigate('timeline'); }} /> : <section className="panel dashboard-chart-empty"><h3>Activity</h3><p role={workspace.error ? 'alert' : 'status'}>{workspace.error || 'Loading activity…'}</p>{workspace.error && <button type="button" onClick={workspace.refresh}>Retry activity</button>}</section>}</div>
      <section className="panel evidence-distribution" aria-label="Evidence types"><h3>Evidence types</h3>
        {state.status === 'loading' && <p role="status">Loading file types…</p>}
        {summary && summary.total > 0 ? <><ul className="distribution-legend">{kinds.map(([kind, count], index) => <li key={kind}><span style={{ background: palette[index % palette.length] }} aria-hidden="true" /><span>{kind.replaceAll('_', ' ')}</span><strong>{count}</strong></li>)}</ul><div className="distribution-ring" role="img" aria-label={kinds.map(([kind, count]) => `${kind.replaceAll('_', ' ')}: ${count}`).join(', ')} style={{ background: `conic-gradient(${segments.join(',')})` }}><div><strong>{summary.total}</strong><span>{summary.total === 1 ? 'file' : 'files'}</span></div></div></> : state.status !== 'loading' && <p className="chart-empty-copy">{state.status === 'error' ? 'File types unavailable.' : 'No evidence uploaded.'}</p>}
      </section>
    </div>
    <section className="panel recent-evidence" aria-labelledby="recent-evidence-title"><div className="section-heading"><h3 id="recent-evidence-title">Recent evidence</h3><button type="button" className="text-action" onClick={() => navigate('evidence')}>View all evidence</button></div>
      {workspace.loading && <p role="status">Loading evidence…</p>}{workspace.error && <p role="alert">{workspace.error}</p>}
      {workspace.data && (recent.length ? <div className="recent-table-scroll"><table><thead><tr><th>Source</th><th>Type</th><th>Added</th><th>Size</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{recent.map(item => <tr key={item.id}><td><strong title={item.filename}>{item.source_label}</strong></td><td>{item.kind.replaceAll('_', ' ')}</td><td><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</time></td><td>{item.size_bytes < 1024 ? `${item.size_bytes} B` : `${(item.size_bytes / 1024).toFixed(1)} KB`}</td><td><button type="button" className="text-action" aria-label={`Inspect ${item.source_label}`} onClick={() => inspectEvidence ? inspectEvidence(item.id) : navigate('evidence')}>Inspect</button></td></tr>)}</tbody></table></div> : <p className="empty-table-copy">No evidence yet.</p>)}
    </section>
  </div>;
}
