// PDF artifact validation; requires Poppler's pdfinfo and pdftotext.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
import {createReportPdf,reportNarrative} from '../.test-build/src/cases/CaseWorkspace.mjs';
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const evidence=Array.from({length:40},(_,i)=>({id:id(100+i),case_id:id(1),kind:'network_log',filename:`evidence-${String(i+1).padStart(2,'0')}-Ω.csv`,source_label:`Synthetic gateway export ${i+1}`,sha256:String(i+1).padStart(64,'0'),size_bytes:100+i,acquired_at:'2026-11-07T00:00:00Z'}));
const observations=evidence.map((_,i)=>id(300+i));
const run={id:id(2),case_id:id(1),status:'completed',finished_at:'2026-11-07T01:00:00Z',algorithm_version:'synthetic-report-format/1',input_snapshot:{sha256:'f'.repeat(64),case_id:id(1),evidence_ids:evidence.map(e=>e.id),observation_ids:observations,processing_run_ids:[id(3)]}};
const findings=evidence.map((e,i)=>({id:id(500+i),analysis_run_id:run.id,case_id:run.case_id,kind:'relationship',summary:`Finding marker ${String(i+1).padStart(2,'0')}. This synthetic record contains a reported network event; identity and causality are unverified.`,rule:'synthetic/1',confidence:.4,evidence_ids:[e.id],observation_ids:[observations[i]],missing_information:['The source clock has not been independently verified.']}));
const sections=['Executive summary','Recorded chronology','Evidence assessment','Uncertainties and follow-up'].map((heading,i)=>({heading,claims:[{text:`Synthetic section ${i+1}: the source describes a recorded gateway event requiring investigator review.`,observation_ids:[observations[i]]}]}));
const model={case_id:id(1),analysis_run_id:id(2),provenance_id:id(4),model_version:'synthetic:format-test',prompt_template_version:'forensic-report/1',created_at:'2026-11-07T01:01:00Z',sections,citations:sections.map((section,i)=>({claim:section.claims[0].text,observation_id:observations[i],evidence_id:evidence[i].id,source_locator:`row ${i+2}, event`})),coverage:{observations_included:40,observations_total:80,sources_included:40,sources_total:40,truncated_observations:0}};
const input={data:{run,evidence,findings,reviews:{}},selected:findings.map(f=>f.id),title:'Synthetic investigation · Málaga Ω',scope:'Demonstrate a formatted investigation report with source-backed references.',notes:'This example contains synthetic data only. Unicode preservation check: 中文.\n'+Array.from({length:65},(_,i)=>`Assessment line ${i+1}: source records require independent verification.`).join('\n'),preparedAt:'2026-11-07T02:00:00Z',modelReport:model,narrative:reportNarrative(model),reviewed:true,reviewer:{id:id(5),display_name:'Synthetic Investigator'}};
assert.throws(()=>createReportPdf({...input,reviewed:false}),/Review/);
const blob=createReportPdf(input);assert.equal(blob.type,'application/pdf');
const path='/tmp/evora-formatted-long-report.pdf';const bytes=Buffer.from(await blob.arrayBuffer());assert.equal(bytes.subarray(0,5).toString(),'%PDF-');await writeFile(path,bytes);
const info=execFileSync('pdfinfo',[path],{encoding:'utf8'});assert.match(info,/Page size:\s+595\.28 x 841\.89 pts \(A4\)/);const pages=Number(info.match(/Pages:\s+(\d+)/)[1]);assert.ok(pages>=6);
const raw=execFileSync('pdftotext',['-raw',path,'-'],{encoding:'utf8'});const compact=raw.replace(/\s/g,'');
for(const label of ['Executive Summary','Recorded Chronology','Evidence Assessment','Uncertainties And Follow-Up','Evidence register','Source references','Technical record','Málaga Ω','[S1]','[U+4E2D]','[U+6587]'])assert.ok(raw.includes(label),label);
for(const source of evidence){assert.ok(raw.includes(source.filename),source.filename);assert.ok(compact.includes(source.sha256),source.sha256);}
for(let i=1;i<=findings.length;i++)assert.ok(raw.includes(`Finding marker ${String(i).padStart(2,'0')}`));
for(let page=1;page<=pages;page++)assert.ok(raw.includes(`Page ${page} of ${pages}`));
assert.match(raw,/Assessment line 65/);assert.match(info,/JavaScript:\s+no/);
console.log(`PASS formatted PDF: ${pages} A4 pages, all 40 findings and source hashes, model sections, readable Unicode, explicit unsupported glyphs, numbered citations, complete long notes, page numbers and review gate. Artifact: ${path}`);
