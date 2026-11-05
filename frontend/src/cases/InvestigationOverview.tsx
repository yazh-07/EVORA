import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { createCaseOverviewController } from './caseOverviewController';
import { useAnalysisWorkspace } from './StartAnalysis';
import { ExecutiveBrief } from './ExecutiveBrief';
import type { InvestigationTab } from './InvestigationTabs';

export function InvestigationOverview({ caseId, navigate, addEvidence }: { caseId: string; navigate: (tab: InvestigationTab) => void; addEvidence: () => void }) {
  const client = useApiClient();
  const { analysis_run_id } = useAnalysisWorkspace();
  const controller = useMemo(() => createCaseOverviewController(client, caseId), [client, caseId]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  const summary = state.summary;
  const needsProcessing = summary ? summary.statuses.unprocessed + summary.statuses.failed : 0;
  const active = summary ? summary.statuses.running + summary.statuses.queued : 0;
  const next = !summary ? null : summary.total === 0 ? { title: 'Add your first evidence source', text: 'Bring in original files to establish the evidence available for this investigation.', action: 'Add evidence', run: addEvidence } : needsProcessing ? { title: `${needsProcessing} ${needsProcessing === 1 ? 'source needs' : 'sources need'} attention`, text: 'Open Evidence to process new sources or inspect failed attempts. Completed processing remains available for review.', action: 'Review evidence', run: () => navigate('evidence') } : active ? { title: 'Evidence processing is underway', text: 'Open the source to see its latest status. You can continue reviewing other evidence while processing runs.', action: 'Check evidence', run: () => navigate('evidence') } : !analysis_run_id ? { title: 'Your processed evidence is ready to connect', text: 'Use Run case analysis above to find relationships and investigative leads. Then review the findings against their sources.', action: 'Explore the timeline', run: () => navigate('timeline') } : { title: 'Review the findings against your sources', text: 'Check the supporting evidence, record your decision, and include the reviewed findings in your report.', action: 'Review findings', run: () => navigate('investigation') };
  return <div className="overview-workspace">
    <header className="workspace-section-heading"><span className="section-label">YOUR INVESTIGATION AT A GLANCE</span><h2>A clear path through the evidence</h2><p>Start with the sources. Follow the sequence. Verify what the findings mean.</p></header>
    {state.status === 'loading' && <p role="status">Checking your evidence and processing status…</p>}
    {state.message && <p role="alert">{state.message}</p>}
    {next && <section className="next-action"><div><span className="section-label">SUGGESTED NEXT STEP</span><h3>{next.title}</h3><p>{next.text}</p></div><button type="button" className="button-primary" onClick={next.run}>{next.action} <span aria-hidden="true">→</span></button></section>}
    <div className="overview-stats" aria-label="Evidence readiness">
      <button type="button" onClick={() => navigate('evidence')}><span>Evidence sources</span><strong>{summary?.total ?? '—'}</strong><small>Original files in this case ↗</small></button>
      <button type="button" onClick={() => navigate('evidence')}><span>Latest extraction completed</span><strong>{summary?.statuses.completed ?? '—'}</strong><small>Ready for source review ↗</small></button>
      <button type="button" onClick={() => navigate('evidence')}><span>Needs processing or retry</span><strong>{summary ? needsProcessing : '—'}</strong><small>{summary ? `${active} queued or running` : 'Checking status'} ↗</small></button>
    </div>
    <div className="section-heading"><p className="scope-note">Live counts at refresh. Analysis views use the selected completed snapshot.</p><button type="button" disabled={state.status === 'loading'} onClick={() => { void controller.load(); }}>Refresh overview</button></div>
    <section className="panel workflow-map" aria-label="Investigation workflow"><h3>Work through the case</h3><ol>
      {([
        ['01', 'Gather the evidence', 'Add originals and inspect what each file contains.', 'evidence'],
        ['02', 'Reconstruct the sequence', 'Compare recorded events and identify missing times.', 'timeline'],
        ['03', 'Test your findings', 'Explore connections, inspect sources, and record reviews.', 'investigation'],
        ['04', 'Document your assessment', 'Select findings and export a traceable report draft.', 'report'],
      ] as const).map(([number, title, description, tab]) => <li key={tab}><span className="step-number">{number}</span><div><button type="button" onClick={() => navigate(tab)}>{title} <span aria-hidden="true">→</span></button><p>{description}</p></div></li>)}
    </ol></section>
    {analysis_run_id && <details className="panel brief-disclosure"><summary>Read the investigative hypothesis <span>AI-assisted or rule-based; verify against sources</span></summary><ExecutiveBrief /></details>}
  </div>;
}
