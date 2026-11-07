import assert from 'node:assert/strict';
import test from 'node:test';
import { collectPages, filterTimeline, loadReport, buildReportText } from '../.test-build/src/cases/CaseWorkspace.mjs';

const signal = () => new AbortController().signal;
const event = (id, time, source = 'source') => ({ id, case_id: 'case', kind: 'network.activity', summary: `Device ${id}`, evidence_ids: [source], observation_ids: ['observation'], entity_ids: [], confidence: .5, ...(time ? { observed_at_utc: time } : {}) });

test('timeline compares absolute instants across offsets and keeps missing timestamps out of dated results', () => {
  const events = [event('late','2026-01-12T09:00:00Z'), event('early','2026-01-12T10:00:00+02:00'), event('unknown')];
  assert.deepEqual(filterTimeline(events, '', '', '', '', false).map(item => item.id), ['early','late']);
  assert.deepEqual(filterTimeline(events, '', '', '2026-01-12', '2026-01-12', true).map(item => item.id), ['unknown']);
  assert.equal(filterTimeline(events, '', '', '2026-01-13', '', false).length,0);
  assert.equal(filterTimeline(events, 'early', 'other', '', '', false).length,0);
  assert.equal(filterTimeline(events, 'EARLY', 'source', '', '', false).length,1);
});

test('collection reads all pages and rejects foreign records, duplicates, changing totals and stalled pages', async () => {
  const records = Array.from({length:103},(_,i)=>({id:`item-${i}`,case_id:'case'}));
  const offsets=[];
  const result=await collectPages('case',signal(),async offset=>{offsets.push(offset);return {items:records.slice(offset,offset+100),offset,limit:100,total:103};});
  assert.equal(result.length,103);assert.deepEqual(offsets,[0,100]);
  for(const change of [page=>({...page,total:104}),page=>({...page,items:[]}),page=>({...page,items:[records[0]]}),page=>({...page,items:[{id:'foreign',case_id:'other'}]})]) {
    await assert.rejects(collectPages('case',signal(),async offset=>{const page={items:records.slice(offset,offset+100),offset,limit:100,total:103};return offset?change(page):page;}));
  }
  const controller=new AbortController();controller.abort();let calls=0;
  await assert.rejects(collectPages('case',controller.signal,async()=>{calls++;}));assert.equal(calls,0);
});

const run={id:'run',case_id:'case',status:'completed',algorithm_version:'test/1',created_at:'2026-01-12T00:00:00Z',finished_at:'2026-01-12T00:01:00Z',input_snapshot:{case_id:'case',evidence_ids:['source'],observation_ids:['observation'],processing_run_ids:['processing'],sha256:'b'.repeat(64)}};
const evidence={id:'source',case_id:'case',filename:'gateway.csv',source_label:'Gateway log',sha256:'a'.repeat(64),size_bytes:120};
const finding={id:'finding',case_id:'case',analysis_run_id:'run',kind:'relationship',summary:'Device connection',rule:'test/1',confidence:.5,evidence_ids:['source'],observation_ids:['observation']};
const review={id:'review',case_id:'case',finding_id:'finding',decision:'accepted',reason:'Checked source',actor_id:'reviewer',created_at:'2026-01-12T00:02:00Z'};
function reportClient(mutate=x=>x){return {request:async(_method,path,options)=>{
  let value=path.endsWith('/analysis-runs/{runId}')?run:path.endsWith('/findings')?{items:[finding],offset:0,limit:100,total:1,analysis_run_id:'run'}:path.endsWith('/reviews')?[review]:evidence;
  if(path.endsWith('/findings'))assert.equal(options.query.analysis_run_id,'run');
  return mutate(structuredClone(value),path);
}};}
test('report pins source manifest and findings to the selected run and resolves real review decisions',async()=>{
  const data=await loadReport(reportClient(),'case','run',signal());
  assert.equal(data.reviews.finding.decision,'accepted');assert.equal(data.evidence[0].sha256,evidence.sha256);
  for(const mutate of [
    (value,path)=>path.endsWith('/findings')?{...value,analysis_run_id:'other'}:value,
    (value,path)=>path.endsWith('/findings')?{...value,items:[{...finding,observation_ids:['foreign']}]}:value,
    (value,path)=>path.endsWith('/reviews')?[{...review,case_id:'other'}]:value,
    (value,path)=>path.endsWith('/evidence/{evidenceId}')?{...value,sha256:'invalid'}:value,
  ]) await assert.rejects(loadReport(reportClient(mutate),'case','run',signal()));
});
test('report export retains review, provenance, AI labels and limitations without presenting omitted findings as reviewed',()=>{
  const ai={...finding,id:'ai',summary:'Possible association',details:{ai_generated:true,model:'test-model',hypothesis:'Needs independent verification'},missing_information:['Unknown clock alignment']};
  const data={run,evidence:[evidence],findings:[finding,ai],reviews:{finding:review}};
  const text=buildReportText(data,['ai'],'Case report','Compare sources','Do not infer identity','2026-01-12');
  assert.match(text,/1 selected of 2/);assert.match(text,/Review: UNREVIEWED/);assert.match(text,/AI-assisted hypothesis \(test-model\)/);
  assert.match(text,/Unknown clock alignment/);assert.match(text,/Snapshot SHA-256: b{64}/);assert.match(text,/SHA-256: a{64}/);
  assert.doesNotMatch(text,/1\. Device connection/);assert.match(text,/not a complete export/);
});

test('model report narrative preserves exact claim citations and shows partial coverage and draft provenance',async()=>{
  const {reportNarrative,reportModelAppendix}=await import('../.test-build/src/cases/CaseWorkspace.mjs');
  const report={model_version:'chatgpt:test-model',created_at:'2026-11-07T00:00:00Z',provenance_id:'provenance',prompt_template_version:'forensic-report/1',sections:[{heading:'Executive summary',claims:[{text:'Model-derived, unverified: a notice appears.',observation_ids:['obs-a','obs-b']}]},{heading:'Recorded chronology',claims:[]}],citations:[{claim:'Model-derived, unverified: a notice appears.',observation_id:'obs-a',evidence_id:'source-a',source_locator:'frame=3'}],coverage:{observations_included:2,observations_total:100,sources_included:1,sources_total:12,truncated_observations:1}};
  const narrative=reportNarrative(report),appendix=reportModelAppendix(report);
  assert.match(narrative,/unverified: a notice appears\. \[obs-a, obs-b\]/);
  assert.match(narrative,/Insufficient source support/);
  assert.match(appendix,/2\/100 observations; 1\/12 sources; 1 shortened/);
  assert.match(appendix,/obs-a · Evidence source-a · frame=3/);
  assert.match(appendix,/chatgpt:test-model/);assert.match(appendix,/do not prove factual accuracy/);
});
