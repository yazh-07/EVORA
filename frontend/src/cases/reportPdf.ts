/** Local vector PDF export. Original evidence and report text never leave the browser. */
import { jsPDF } from 'jspdf';
import { autoTable } from 'jspdf-autotable';
import regularFont from '../assets/report-fonts/DejaVuSans.ttf';
import boldFont from '../assets/report-fonts/DejaVuSans-Bold.ttf';
import type { ReportData } from './workspaceData';
import type { components } from '../api/schema';

type ModelReport = components['schemas']['GeneratedReport'];
export type ReportPdfInput = {
  data: ReportData; selected: string[]; title: string; scope: string; notes: string;
  preparedAt: string; narrative?: string; modelReport?: ModelReport;
  reviewed: boolean; reviewer?: { id: string; display_name: string } | null;
};
const INK: [number, number, number] = [30, 41, 55];
const MUTED: [number, number, number] = [91, 104, 119];
const ACCENT: [number, number, number] = [37, 83, 120];
const PALE: [number, number, number] = [243, 246, 249];
const MARGIN = 18, WIDTH = 174, BOTTOM = 275;
const MODEL_HEADINGS = new Set(['EXECUTIVE SUMMARY', 'RECORDED CHRONOLOGY', 'EVIDENCE ASSESSMENT', 'UNCERTAINTIES AND FOLLOW-UP']);
const time = (value?: string) => value && Number.isFinite(Date.parse(value))
  ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) + ' UTC'
  : 'Not recorded';

export function createReportPdf(input: ReportPdfInput): Blob {
  const { data, modelReport } = input;
  if (modelReport && (!input.reviewed || modelReport.case_id !== data.run.case_id || modelReport.analysis_run_id !== data.run.id)) {
    throw Error('Review the model draft for this analysis before exporting.');
  }
  const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: true, putOnlyUsedFonts: true });
  pdf.addFileToVFS('DejaVuSans.ttf', regularFont); pdf.addFont('DejaVuSans.ttf', 'Evora', 'normal');
  pdf.addFileToVFS('DejaVuSans-Bold.ttf', boldFont); pdf.addFont('DejaVuSans-Bold.ttf', 'Evora', 'bold');
  pdf.setFont('Evora', 'normal');
  const normal = pdf.getFont().metadata;
  pdf.setFont('Evora', 'bold'); const bold = pdf.getFont().metadata;
  const unsupported = new Set<string>();
  const clean = (value: string) => Array.from(value.replace(/\r\n?/g, '\n')).map(character => {
    const code = character.codePointAt(0)!;
    if (character === '\n' || character === '\t') return character === '\t' ? '    ' : character;
    if (code >= 32 && code <= 0xffff && normal.characterToGlyph(code) && bold.characterToGlyph(code)) return character;
    unsupported.add(`U+${code.toString(16).toUpperCase().padStart(4, '0')}`);
    return `[U+${code.toString(16).toUpperCase().padStart(4, '0')}]`;
  }).join('');
  pdf.setProperties({ title: input.title, author: input.reviewer?.display_name ?? '', creator: 'EVORA', subject: 'Investigation report draft' });
  const sourceIds = new Map(data.evidence.map((source, i) => [source.id, `E${String(i + 1).padStart(2, '0')}`]));
  const citations = new Map<string, { ref: string; evidence: string; locator: string; claims: Set<string> }>();
  for (const citation of modelReport?.citations ?? []) {
    const id = citation.observation_id ?? citation.evidence_id + ':' + citation.source_locator;
    const existing = citations.get(id);
    if (existing) existing.claims.add(citation.claim);
    else citations.set(id, { ref: `S${citations.size + 1}`, evidence: citation.evidence_id, locator: citation.source_locator, claims: new Set([citation.claim]) });
  }
  const references = (text: string) => text.replace(/\[([^\]]+)\]/g, (whole, ids: string) => {
    const selected = ids.split(',').map(id => citations.get(id.trim())?.ref);
    return selected.length && selected.every(Boolean) ? `[${selected.join(', ')}]` : whole;
  });
  let y = 25;
  const font = (size = 10, weight: 'normal' | 'bold' = 'normal', color = INK) => { pdf.setFont('Evora', weight); pdf.setFontSize(size); pdf.setTextColor(...color); };
  const newPage = () => { pdf.addPage(); y = 27; };
  const ensure = (height: number) => { if (y + height > BOTTOM) newPage(); };
  const paragraph = (value: string, size = 10, color = INK, weight: 'normal' | 'bold' = 'normal') => {
    font(size, weight, color);
    const lines: string[] = pdf.splitTextToSize(clean(value), WIDTH);
    const leading = size * .52;
    for (const line of lines) { ensure(leading); pdf.text(line, MARGIN, y); y += leading; }
    y += 3;
  };
  const heading = (value: string) => {
    ensure(24); y += 4; font(14, 'bold', ACCENT); pdf.text(clean(value), MARGIN, y); y += 5;
    pdf.setDrawColor(218, 225, 232); pdf.setLineWidth(.35); pdf.line(MARGIN, y, 192, y); y += 8;
  };
  const table = (headers: string[], rows: string[][], widths?: number[]) => {
    ensure(22);
    autoTable(pdf, {
      startY: y, head: [headers.map(clean)], body: rows.map(row => row.map(clean)),
      theme: 'grid', margin: { top: 27, bottom: 23, left: MARGIN, right: MARGIN },
      styles: { font: 'Evora', fontSize: 8, cellPadding: 3, textColor: INK, lineColor: [219, 226, 233], lineWidth: .15, overflow: 'linebreak', valign: 'top' },
      headStyles: { font: 'Evora', fontStyle: 'bold', fillColor: ACCENT, textColor: [255, 255, 255], fontSize: 8 },
      alternateRowStyles: { fillColor: [248, 250, 252] }, showHead: 'everyPage', rowPageBreak: 'avoid',
      columnStyles: widths ? Object.fromEntries(widths.map((width, index) => [index, { cellWidth: width }])) : undefined,
    });
    y = (pdf as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
  };

  // Cover: calm typography, document status and an exact case/analysis reference.
  pdf.setFillColor(...ACCENT); pdf.rect(MARGIN, 23, 13, 2, 'F');
  font(12, 'bold', ACCENT); pdf.text('EVORA', MARGIN, 35);
  font(10, 'normal', MUTED); pdf.text('INVESTIGATION REPORT', MARGIN, 44);
  y = 62; font(24, 'bold');
  const title = clean(input.title || 'Investigation report');
  const titleLines: string[] = pdf.splitTextToSize(title, WIDTH);
  paragraph(input.title || 'Investigation report', titleLines.length <= 5 ? 24 : titleLines.length <= 9 ? 18 : 14, INK, 'bold');
  y += 5;
  paragraph(modelReport && input.reviewed ? 'INVESTIGATOR-REVIEWED DRAFT' : 'DRAFT · INVESTIGATOR REVIEW REQUIRED', 9, ACCENT, 'bold');
  ensure(25);
  const boxY = y;
  for (const [i, label, value] of [[0, 'EVIDENCE SOURCES', String(data.evidence.length)], [1, 'SELECTED FINDINGS', String(input.selected.length)], [2, 'MODEL NARRATIVE', modelReport ? 'Included' : 'Not generated']] as const) {
    const x = MARGIN + i * 59;
    pdf.setFillColor(...PALE); pdf.roundedRect(x, boxY, 56, 24, 2, 2, 'F');
    font(7, 'bold', MUTED); pdf.text(label, x + 4, boxY + 7); font(14, 'bold'); pdf.text(value, x + 4, boxY + 17);
  }
  y += 35;
  table(['Document field', 'Value'], [
    ['Prepared', time(input.preparedAt)], ['Investigator', input.reviewer?.display_name ?? 'Not recorded'],
    ['Case reference', data.run.case_id], ['Analysis reference', data.run.id], ['Analysis completed', time(data.run.finished_at)],
  ], [42, 132]);
  paragraph('This document supports investigation. Source records, extracted candidates and model-derived interpretations require independent verification.', 9, MUTED);
  newPage();
  heading('Scope and investigative questions'); paragraph(input.scope.trim() || 'Not provided.');
  heading('Investigator assessment'); paragraph(input.notes.trim() || 'Not provided.');
  if (modelReport && input.narrative) {
    heading('Model-assisted narrative');
    const coverage = modelReport.coverage;
    paragraph(`Context coverage: ${coverage.observations_included} of ${coverage.observations_total} observations from ${coverage.sources_included} of ${coverage.sources_total} sources. ${coverage.truncated_observations} observations were shortened.`, 8, MUTED);
    const blocks = input.narrative.replace(/\r\n?/g, '\n').split(/\n\s*\n/);
    for (const block of blocks) {
      const lines = block.split('\n'); const first = lines[0]?.trim() ?? '';
      if (MODEL_HEADINGS.has(first.toUpperCase()) || /^#{1,3}\s/.test(first)) {
        ensure(22); y += 3; paragraph(first.replace(/^#{1,3}\s*/, '').replace(/\b\w+\b/g, word => word[0]! + word.slice(1).toLowerCase()), 11, ACCENT, 'bold');
        if (lines.length > 1) paragraph(references(lines.slice(1).join('\n')));
      } else if (block.trim()) paragraph(references(block));
    }
  }
  heading('Selected findings');
  const findings = data.findings.filter(item => input.selected.includes(item.id));
  paragraph(`${findings.length} selected of ${data.findings.length} findings in the selected analysis. Review decisions describe investigator assessments.`, 9, MUTED);
  if (!findings.length) paragraph('No findings selected.');
  findings.forEach((finding, index) => {
    const review = data.reviews[finding.id];
    ensure(32); paragraph(`${index + 1}. ${finding.kind.replaceAll('_', ' ')}`, 11, ACCENT, 'bold');
    paragraph(finding.summary);
    paragraph(`Review: ${(review?.decision ?? 'unreviewed').replaceAll('_', ' ')} · Reported score: ${finding.confidence} (a diagnostic score, not a probability).`, 8, MUTED);
    if (review) paragraph(`Reviewer: ${review.actor_id} · ${time(review.created_at)}\nReason: ${review.reason}`, 8, MUTED);
    if (finding.details?.ai_generated) paragraph(`Model-derived, unverified hypothesis (${finding.details.model}): ${finding.details.hypothesis}`, 9);
    paragraph(`Sources: ${finding.evidence_ids.map(id => sourceIds.get(id) ?? id).join(', ')}\nFinding: ${finding.id}\nRule: ${finding.rule}\nObservation references: ${finding.observation_ids.join(', ')}`, 8, MUTED);
    for (const limitation of finding.missing_information ?? []) paragraph('Limitation: ' + limitation, 9, MUTED);
  });
  heading('Evidence register');
  paragraph('Original files are not embedded. Hashes identify the originals represented in the selected analysis.', 9, MUTED);
  table(['ID', 'Source', 'Details', 'SHA-256'], data.evidence.map(source => [
    sourceIds.get(source.id)!, `${source.filename}\n${source.source_label}`, `${(source.kind ?? 'Not recorded').replaceAll('_', ' ')}\n${source.size_bytes.toLocaleString('en-GB')} bytes\nAcquired: ${time(source.acquired_at)}`, source.sha256,
  ]), [12, 65, 38, 59]);
  heading('Source references');
  if (!citations.size) paragraph('No model source citations are included in this draft.');
  else {
    paragraph('References support the original model draft. Investigator edits require fresh source verification.', 9, MUTED);
    table(['ID', 'Source and locator', 'Original draft support'], [...citations.entries()].map(([id, citation]) => [
      citation.ref, `${sourceIds.get(citation.evidence) ?? citation.evidence}\n${citation.locator}\nObservation: ${id}`, [...citation.claims].join('\n\n'),
    ]), [12, 72, 90]);
  }
  heading('Methods and limitations');
  paragraph('Findings and model interpretations are investigative leads. A review decision does not establish identity, guilt or causality. Video interpretations describe sampled frames; descriptions, OCR and transcripts remain model-derived unless independently verified.');
  paragraph('This report contains selected findings, review decisions at refresh and investigator-authored notes. It is not a complete case or chain-of-custody export. Sources added or reprocessed after the selected analysis may not be represented.');
  if (modelReport) paragraph('The generation pipeline checks exact source references and literal values, followed by a model entailment check. These checks reduce errors; they cannot prove factual accuracy.');
  heading('Technical record');
  table(['Record', 'Value'], [
    ['Report title', input.title], ['Case ID', data.run.case_id], ['Analysis ID', data.run.id], ['Prepared by user ID', input.reviewer?.id ?? 'Not recorded'],
    ['Analysis method', data.run.algorithm_version], ['Input snapshot SHA-256', data.run.input_snapshot.sha256],
    ['Frozen processing runs', data.run.input_snapshot.processing_run_ids.join('\n') || 'None'],
    ...data.evidence.map(source => [`${sourceIds.get(source.id)} · Evidence ID`, source.id]),
    ...(modelReport ? [['Model', modelReport.model_version], ['Generation time', time(modelReport.created_at)], ['Prompt template', modelReport.prompt_template_version], ['Generation provenance', modelReport.provenance_id]] : []),
    ['Investigator review', input.reviewed && modelReport ? 'Confirmed in EVORA before this export; this is not a cryptographic signature.' : 'No model-draft review confirmation recorded.'],
  ], [42, 132]);
  if (unsupported.size) paragraph(`Font coverage: characters outside the embedded font are preserved as explicit Unicode codes: ${[...unsupported].join(', ')}.`, 8, MUTED);
  const pages = pdf.getNumberOfPages();
  for (let page = 1; page <= pages; page++) {
    pdf.setPage(page);
    if (page > 1) {
      font(8, 'bold', ACCENT); pdf.text('EVORA / INVESTIGATION REPORT', MARGIN, 13);
      font(8, 'normal', MUTED); pdf.text(`Case ${data.run.case_id.slice(0, 8)}`, 192, 13, { align: 'right' });
      pdf.setDrawColor(219, 226, 233); pdf.line(MARGIN, 17, 192, 17);
    }
    pdf.setDrawColor(219, 226, 233); pdf.line(MARGIN, 283, 192, 283);
    font(7, 'normal', MUTED); pdf.text('DRAFT · Requires independent source verification', MARGIN, 289);
    pdf.text(`Page ${page} of ${pages}`, 192, 289, { align: 'right' });
  }
  return pdf.output('blob');
}
