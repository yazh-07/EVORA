import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import type { components } from '../api/schema';
import type { ApiClient } from '../api/client';
import { useAnalysisWorkspace } from './StartAnalysis';
import { loadReport, useWorkspaceData } from './workspaceData';
import type { ReportData } from './workspaceData';
import { saveOriginal } from './downloadController';

type GeneratedReport = components['schemas']['GeneratedReport'];
export function reportNarrative(report: GeneratedReport) {
  return report.sections.map(section => `${section.heading.toUpperCase()}\n${section.claims.length ? section.claims.map(claim => `${claim.text} [${claim.observation_ids.join(', ')}]`).join('\n\n') : 'Insufficient source support for this section.'}`).join('\n\n');
}
export function reportModelAppendix(report: GeneratedReport) {
  const c = report.coverage;
  return ["MODEL DRAFT PROVENANCE", `Model: ${report.model_version}`, `Generated: ${report.created_at}`,
    `Provenance: ${report.provenance_id}`, `Template: ${report.prompt_template_version}`,
    `Context coverage: ${c.observations_included}/${c.observations_total} observations; ${c.sources_included}/${c.sources_total} sources; ${c.truncated_observations} shortened observations.`,
    'Source IDs and literal values were checked, followed by a model entailment check. These checks do not prove factual accuracy. Investigator edits require fresh source verification.',
    'SOURCE CITATIONS FOR THE ORIGINAL MODEL DRAFT',
    ...report.citations.map(citation => `${citation.observation_id} · Evidence ${citation.evidence_id} · ${citation.source_locator}\nDraft claim: ${citation.claim}`),
  ].join('\n');
}

export function buildReportText(data: ReportData, selected: string[], title: string, scope: string, notes: string, generated: string, narrative?: string) {
  const findings = data.findings.filter(item => selected.includes(item.id));
  const sources = new Map(data.evidence.map(item => [item.id, item]));
  return [title, 'INVESTIGATION REPORT · DRAFT', `Prepared: ${generated}`, `Case: ${data.run.case_id}`,
    `Analysis: ${data.run.id}`, `Analysis completed: ${data.run.finished_at ?? 'Not recorded'}`,
    `Method: ${data.run.algorithm_version}`, `Snapshot SHA-256: ${data.run.input_snapshot.sha256}`,
    '\nSCOPE AND QUESTIONS', scope.trim() || 'Not provided.', '\nINVESTIGATOR NOTES', notes.trim() || 'Not provided.',
    ...(narrative ? ['\nMODEL-ASSISTED NARRATIVE · DRAFT', narrative] : []),
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
  const client = useApiClient();
  const loader = useCallback((client: ApiClient, signal: AbortSignal) => loadReport(client, caseId, runId, signal), [caseId, runId]);
  const { data, loading, error, refresh } = useWorkspaceData(loader);
  const [title, setTitle] = useState(caseTitle), [scope, setScope] = useState(''), [notes, setNotes] = useState('');
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState('');
  const [pdfBusy, setPdfBusy] = useState(false);
  const mounted = useRef(true);
  const selected = useMemo(() => data?.findings.filter(item => choices[item.id] ?? data.reviews[item.id]?.decision === 'accepted').map(item => item.id) ?? [], [data, choices]);
  const [modelDraft, setModelDraft] = useState<{ report: GeneratedReport; input: string }>();
  const [narrative, setNarrative] = useState(''), [reviewed, setReviewed] = useState(false);
  const [allowRemote, setAllowRemote] = useState(false), [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const pending = useRef<AbortController | null>(null);
  const fingerprint = JSON.stringify({ runId, selected, scope, notes, reviews: data?.reviews });
  const current = useRef(fingerprint); current.current = fingerprint;
  const draft = modelDraft?.input === fingerprint ? modelDraft.report : undefined;
  const exportKey = JSON.stringify([fingerprint, title, narrative, reviewed, draft?.provenance_id]);
  const currentExport = useRef(exportKey); currentExport.current = exportKey;
  useEffect(() => {
    mounted.current = true;
    const unsubscribe = client.subscribeSession(() => { pending.current?.abort(); setModelDraft(undefined); setNarrative(''); setReviewed(false); });
    return () => { mounted.current = false; pending.current?.abort(); unsubscribe(); };
  }, [client]);
  const generate = async () => {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    const input = fingerprint;
    setGenerating(true); setGenerationError(''); setReviewed(false);
    try {
      const report = await client.request('post', '/api/v1/cases/{caseId}/reports', {
        path: { caseId }, body: { analysis_run_id: runId, finding_ids: selected, scope, notes, allow_remote: allowRemote }, signal: controller.signal,
      });
      if (controller.signal.aborted || current.current !== input) return;
      if (report.case_id !== caseId || report.analysis_run_id !== runId || report.citations.some(c => !data?.run.input_snapshot.observation_ids.includes(c.observation_id ?? '') || !data.run.input_snapshot.evidence_ids.includes(c.evidence_id))) throw Error('Invalid report references');
      setModelDraft({ report, input }); setNarrative(reportNarrative(report));
      setMessage('Draft generated. Review the narrative and cited sources before exporting.');
    } catch {
      if (!controller.signal.aborted) setGenerationError('Could not generate a source-checked report. Check the configured model, online mode and sharing consent, or reduce the selected findings and retry.');
    } finally { pending.current = null; if (!controller.signal.aborted) setGenerating(false); }
  };
  const [preparedAt] = useState(() => new Date().toISOString());
  const baseText = data ? buildReportText(data, selected, title || caseTitle, scope, notes, preparedAt, draft ? narrative : undefined) : '';
  const text = draft ? `${baseText}\n\n${reportModelAppendix(draft)}` : baseText;
  const exportReport = () => { try { saveOriginal(new Blob([text], { type: 'text/plain;charset=utf-8' }), `${title || 'Investigation'}-report.txt`); setMessage('Report download requested. Check your browser downloads.'); } catch { setMessage('Download unavailable. Copy the report preview to save your draft.'); } };
  const exportPdf = async () => {
    if (!data || pdfBusy || generating || (draft && !reviewed)) return;
    const identity = currentExport.current, session = client.getSessionVersion();
    const active = () => mounted.current && identity === currentExport.current && session === client.getSessionVersion();
    setPdfBusy(true); setMessage('Preparing your PDF…');
    try {
      const { createReportPdf } = await import('./reportPdf');
      if (!active()) return;
      const blob = createReportPdf({ data, selected, title: title || caseTitle, scope, notes,
        preparedAt: new Date().toISOString(), narrative: draft ? narrative : undefined, modelReport: draft,
        reviewed, reviewer: client.getUser() });
      if (!active()) return;
      saveOriginal(blob, `${title || 'Investigation'}-report.pdf`);
      setMessage('Formatted PDF download requested. Check your browser downloads.');
    } catch {
      if (active()) setMessage('Could not prepare the PDF. Try again or download the text report.');
    } finally { if (mounted.current) setPdfBusy(false); }
  };
  return <section className="report-workspace" aria-label="Report builder" aria-busy={loading || pdfBusy}>
    <header className="workspace-section-heading"><span className="section-label">Report draft</span><h2>Prepare your report</h2><p>Generate a source-cited narrative with your configured model, review it, and export your report.</p></header>
    <p className="scope-note">Your editable draft stays in this open case. Model output and source context are recorded in private provenance. Export your edits before leaving the case, signing out, reloading, or selecting another analysis.</p>
    {loading && <p role="status">Loading the selected analysis, source manifest, and review decisions…</p>}
    {error && <p role="alert">{error}</p>}
    <div className="report-actions"><button type="button" onClick={refresh} disabled={loading}>Refresh review decisions</button><button type="button" onClick={investigate}>Review findings</button></div>
    {data && <div className="report-columns"><div className="panel report-editor">
      <h3>1. Describe the investigation</h3>
      <div className="report-field"><label htmlFor="report-title">Report title</label><input id="report-title" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} /></div>
      <div className="report-field"><label htmlFor="report-scope">Scope and investigative questions</label><textarea id="report-scope" rows={4} maxLength={4000} value={scope} onChange={event => setScope(event.target.value)} placeholder="What did you examine? Which questions were you trying to answer?" /></div>
      <div className="report-field"><label htmlFor="report-notes">Investigator notes</label><textarea id="report-notes" rows={6} maxLength={8000} value={notes} onChange={event => setNotes(event.target.value)} placeholder="Record your assessment, alternative explanations, limitations, and follow-up work." /></div>
      <h3>2. Choose findings</h3><p>Accepted findings are selected by default. Other review states remain visible in the exported report.</p>
      {!data.findings.length && <p>No findings in this analysis. You can still export your scope, notes, and evidence manifest.</p>}
      <ul className="report-finding-list">{data.findings.map(item => <li key={item.id}><label><input type="checkbox" checked={selected.includes(item.id)} onChange={event => setChoices(value => ({ ...value, [item.id]: event.target.checked }))} /><span>{item.summary}<small>{(data.reviews[item.id]?.decision ?? 'unreviewed').replaceAll('_', ' ')}{item.details?.ai_generated ? ' · AI-assisted' : ''}</small></span></label></li>)}</ul>
      <h3>3. Review the narrative</h3>
      {!draft && <p>Use Generate with model at the top of the report preview to write a draft.</p>}
      {modelDraft && !draft && <p role="status">Report inputs changed. Generate a fresh narrative to include it in your export.</p>}
      {draft && <><p>{draft.model_version} · {draft.coverage.observations_included}/{draft.coverage.observations_total} observations from {draft.coverage.sources_included}/{draft.coverage.sources_total} sources in model context. {draft.coverage.truncated_observations} observations shortened.</p>
        <label htmlFor="report-narrative">Model-assisted narrative · editable</label><textarea id="report-narrative" rows={20} value={narrative} onChange={event => { setNarrative(event.target.value); setReviewed(false); }} />
        <p>References in square brackets point to the source appendix. Edits are your assessment and have not been checked by the model.</p>
        <label><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} /> I reviewed this draft against its cited sources and checked my edits.</label></>}
    </div><div className="panel report-preview"><div className="section-heading"><h3>Report preview</h3><span className="kind-badge">DRAFT</span></div><p>{selected.length} findings selected · {data.evidence.length} sources in the analysis</p>
      <div className="report-generation-controls" aria-label="Model report generation">
      <label><input type="checkbox" checked={allowRemote} onChange={event => setAllowRemote(event.target.checked)} /> Allow sending extracted source text, selected findings, review decisions, scope and notes to the hosted provider configured in Settings. Leave unchecked for local Ollama.</label>
      <div className="report-actions"><button type="button" className="button-primary" onClick={() => void generate()} disabled={generating || loading || client.getUser()?.role === 'reviewer'}> {generating ? 'Writing and checking source citations…' : 'Generate with model'}</button></div>
      {generating && <p role="status">Generating the narrative and checking its claims against the sources. This may take a few minutes.</p>}
      {generationError && <p role="alert">{generationError}</p>}
      </div>
      <div className="report-actions"><button className="button-primary" type="button" onClick={() => void exportPdf()} disabled={pdfBusy || generating || Boolean(draft && !reviewed)}>{pdfBusy ? 'Preparing PDF…' : 'Download PDF'}</button><button type="button" onClick={exportReport} disabled={generating || Boolean(draft && !reviewed)}>Download text</button></div>
      <p className="scope-note">PDF includes a cover page, formatted narrative, findings, evidence tables, source references and page numbers.</p>
      {message && <p role="status">{message}</p>}<pre tabIndex={0} aria-label="Report text">{text}</pre></div></div>}
  </section>;
}
