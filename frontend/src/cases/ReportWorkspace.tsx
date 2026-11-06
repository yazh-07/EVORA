import { useCallback, useMemo, useState } from 'react';
import type { ApiClient } from '../api/client';
import { useAnalysisWorkspace } from './StartAnalysis';
import { loadReport, useWorkspaceData } from './workspaceData';
import type { ReportData } from './workspaceData';
import { saveOriginal } from './downloadController';

export function buildReportText(data: ReportData, selected: string[], title: string, scope: string, notes: string, generated: string) {
  const findings = data.findings.filter(item => selected.includes(item.id));
  const sources = new Map(data.evidence.map(item => [item.id, item]));
  return [title, 'INVESTIGATION REPORT · DRAFT', `Prepared: ${generated}`, `Case: ${data.run.case_id}`,
    `Analysis: ${data.run.id}`, `Analysis completed: ${data.run.finished_at ?? 'Not recorded'}`,
    `Method: ${data.run.algorithm_version}`, `Snapshot SHA-256: ${data.run.input_snapshot.sha256}`,
    '\nSCOPE AND QUESTIONS', scope.trim() || 'Not provided.', '\nINVESTIGATOR NOTES', notes.trim() || 'Not provided.',
    '\nSELECTED FINDINGS', `${findings.length} selected of ${data.findings.length} findings in this analysis.`,
    ...findings.flatMap((item, index) => {
      const review = data.reviews[item.id];
      return [`\n${index + 1}. ${item.summary}`, `Finding: ${item.id}`, `Kind: ${item.kind}`,
        `Review: ${review?.decision ?? 'UNREVIEWED'}`, ...(review ? [`Reviewer: ${review.actor_id} at ${review.created_at}`, `Review reason: ${review.reason}`] : []),
        ...(item.details?.ai_generated ? [`AI-assisted hypothesis (${item.details.model}): ${item.details.hypothesis}`] : []),
        `Rule: ${item.rule}`, `Reported score: ${item.confidence} (not a probability of guilt or correctness)`,
        ...item.evidence_ids.map(id => `Source: ${sources.get(id)?.filename ?? id} · ${id}`),
        `Observation references: ${item.observation_ids.join(', ')}`,
        ...(item.missing_information ?? []).map(value => `Limitation: ${value}`)];
    }), '\nEVIDENCE MANIFEST · SELECTED ANALYSIS',
    ...data.evidence.flatMap(item => [`\n${item.filename}`, `Label: ${item.source_label}`, `Evidence: ${item.id}`, `SHA-256: ${item.sha256}`, `Bytes: ${item.size_bytes}`, `Acquired: ${item.acquired_at ?? 'Unknown'}`]),
    '\nLIMITATIONS', 'This draft contains selected findings, current review decisions at refresh, and investigator-authored notes. It is not a complete export of the case or chain of custody.',
    'Extracted candidates and AI-generated hypotheses require independent verification. A review decision does not establish identity, guilt, or causality.',
    'Sources added or reprocessed after the selected analysis may not be represented. Original evidence is not embedded in this report.',
  ].join('\n');
}
export function ReportWorkspace({ caseId, caseTitle, investigate }: { caseId: string; caseTitle: string; investigate: () => void }) {
  const { analysis_run_id } = useAnalysisWorkspace();
  if (!analysis_run_id) return <section className="panel workflow-empty"><span className="section-label">DOCUMENT YOUR INVESTIGATION</span><h2>Build a report from reviewed findings</h2><p>Process your evidence and run case analysis first. Then review findings in Investigation and select what belongs in your report.</p><button type="button" onClick={investigate}>Open investigation</button></section>;
  return <ReportDraft key={`${caseId}:${analysis_run_id}`} caseId={caseId} runId={analysis_run_id} caseTitle={caseTitle} investigate={investigate} />;
}
function ReportDraft({ caseId, runId, caseTitle, investigate }: { caseId: string; runId: string; caseTitle: string; investigate: () => void }) {
  const loader = useCallback((client: ApiClient, signal: AbortSignal) => loadReport(client, caseId, runId, signal), [caseId, runId]);
  const { data, loading, error, refresh } = useWorkspaceData(loader);
  const [title, setTitle] = useState(caseTitle), [scope, setScope] = useState(''), [notes, setNotes] = useState('');
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState('');
  const selected = useMemo(() => data?.findings.filter(item => choices[item.id] ?? data.reviews[item.id]?.decision === 'accepted').map(item => item.id) ?? [], [data, choices]);
  const text = data ? buildReportText(data, selected, title || caseTitle, scope, notes, new Date().toISOString()) : '';
  const exportReport = () => { try { saveOriginal(new Blob([text], { type: 'text/plain;charset=utf-8' }), `${title || 'Investigation'}-report.txt`); setMessage('Report download requested. Check your browser downloads.'); } catch { setMessage('Download unavailable. Copy the report preview to save your draft.'); } };
  const printReport = () => {
    const popup = window.open('', '_blank');
    if (!popup) { setMessage('Allow pop-ups to print, or download the text report.'); return; }
    popup.opener = null;
    popup.document.title = title || caseTitle;
    const style = popup.document.createElement('style'); style.textContent = 'body{margin:40px;font:12px/1.65 system-ui;color:#17212b}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}@page{margin:20mm}';
    const pre = popup.document.createElement('pre'); pre.textContent = text;
    popup.document.head.append(style); popup.document.body.append(pre); popup.focus(); popup.print();
  };
  return <section className="report-workspace" aria-label="Report builder" aria-busy={loading}>
    <header className="workspace-section-heading"><span className="section-label">Report draft</span><h2>Prepare your report</h2><p>Select findings, explain your scope, and add your own assessment.</p></header>
    <p className="scope-note">Draft text stays in this open case only. Export it before leaving the case, signing out, reloading, or selecting another analysis.</p>
    {loading && <p role="status">Loading the selected analysis, source manifest, and review decisions…</p>}
    {error && <p role="alert">{error}</p>}
    <div className="report-actions"><button type="button" onClick={refresh} disabled={loading}>Refresh review decisions</button><button type="button" onClick={investigate}>Review findings</button></div>
    {data && <div className="report-columns"><div className="panel report-editor">
      <h3>1. Describe the investigation</h3>
      <div className="report-field"><label htmlFor="report-title">Report title</label><input id="report-title" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} /></div>
      <div className="report-field"><label htmlFor="report-scope">Scope and investigative questions</label><textarea id="report-scope" rows={4} value={scope} onChange={event => setScope(event.target.value)} placeholder="What did you examine? Which questions were you trying to answer?" /></div>
      <div className="report-field"><label htmlFor="report-notes">Investigator notes</label><textarea id="report-notes" rows={6} value={notes} onChange={event => setNotes(event.target.value)} placeholder="Record your assessment, alternative explanations, limitations, and follow-up work." /></div>
      <h3>2. Choose findings</h3><p>Accepted findings are selected by default. Other review states remain visible in the exported report.</p>
      {!data.findings.length && <p>No findings in this analysis. You can still export your scope, notes, and evidence manifest.</p>}
      <ul className="report-finding-list">{data.findings.map(item => <li key={item.id}><label><input type="checkbox" checked={selected.includes(item.id)} onChange={event => setChoices(value => ({ ...value, [item.id]: event.target.checked }))} /><span>{item.summary}<small>{(data.reviews[item.id]?.decision ?? 'unreviewed').replaceAll('_', ' ')}{item.details?.ai_generated ? ' · AI-assisted' : ''}</small></span></label></li>)}</ul>
    </div><div className="panel report-preview"><div className="section-heading"><h3>Report preview</h3><span className="kind-badge">DRAFT</span></div><p>{selected.length} findings selected · {data.evidence.length} sources in the analysis</p>
      <div className="report-actions"><button className="button-primary" type="button" onClick={exportReport}>Download report</button><button type="button" onClick={printReport}>Print / Save PDF</button></div>
      {message && <p role="status">{message}</p>}<pre tabIndex={0} aria-label="Report text">{text}</pre></div></div>}
  </section>;
}
