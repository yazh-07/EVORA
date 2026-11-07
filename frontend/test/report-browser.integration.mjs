// Browser interaction fixture; real HTTP/source/model protocol checks live in test_reports.py.
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const frontend=fileURLToPath(new URL('..',import.meta.url));
const temporary=await mkdtemp(join(tmpdir(),'evora-report-ui-'));
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const run={id:id(2),case_id:id(1),status:'completed',trigger:'initial',algorithm_version:'test/1',created_at:'2026-11-07T00:00:00Z',finished_at:'2026-11-07T00:01:00Z',input_snapshot:{case_id:id(1),evidence_ids:[id(3)],observation_ids:[id(4)],processing_run_ids:[id(5)],sha256:'b'.repeat(64)}};
const findings=Array.from({length:30},(_,i)=>({id:id(100+i),case_id:id(1),analysis_run_id:id(2),kind:'relationship',summary:'Synthetic gateway source association '+i,rule:'test/1',confidence:.3,evidence_ids:[id(3)],observation_ids:[id(4)]}));
const evidence={id:id(3),case_id:id(1),filename:'gateway.csv',source_label:'Gateway',sha256:'a'.repeat(64),size_bytes:120};
const report={case_id:id(1),analysis_run_id:id(2),provenance_id:id(6),model_version:'synthetic:test-model',prompt_template_version:'forensic-report/1',created_at:'2026-11-07T00:02:00Z',sections:['Executive summary','Recorded chronology','Evidence assessment','Uncertainties and follow-up'].map((heading,i)=>({heading,claims:i?[]:[{text:'The source records D-7. <script>unsafe</script>',observation_ids:[id(4)]}]})),citations:[{claim:'The source records D-7.',observation_id:id(4),evidence_id:id(3),source_locator:'row 2, device_id'}],coverage:{observations_included:1,observations_total:8,sources_included:1,sources_total:1,truncated_observations:0}};
let browser;
try{
 await build({stdin:{contents:`import React from'react';import{createRoot}from'react-dom/client';import{ApiProvider}from'./src/api/ApiProvider';import{CaseAnalysisWorkspace}from'./src/cases/StartAnalysis';import{ReportWorkspace}from'./src/cases/ReportWorkspace';const run=${JSON.stringify(run)},evidence=${JSON.stringify(evidence)},findings=${JSON.stringify(findings)},report=${JSON.stringify(report)};window.calls=[];const client={getUser:()=>null,getSessionVersion:()=>0,subscribeSession:()=>()=>{},request:async(method,path,options)=>{if(path.endsWith('/reports')){window.calls.push(options.body);await new Promise(r=>setTimeout(r,100));if(window.fail)throw Error('unavailable');return report;}if(path.endsWith('/analysis-runs'))return[run];if(path.endsWith('/analysis-runs/{runId}'))return run;if(path.endsWith('/findings'))return{items:findings,total:findings.length,offset:0,limit:100,analysis_run_id:run.id};if(path.endsWith('/reviews'))return[];return evidence;}};createRoot(document.getElementById('root')).render(<ApiProvider client={client}><CaseAnalysisWorkspace caseId={run.case_id}><ReportWorkspace caseId={run.case_id} caseTitle="Report fixture" investigate={()=>{}}/></CaseAnalysisWorkspace></ApiProvider>);`,resolveDir:frontend,loader:'tsx'},outfile:join(temporary,'preview.js'),bundle:true,format:'iife',platform:'browser',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({acceptDownloads:true,viewport:{width:1365,height:950}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<div id="root"></div>');await page.addStyleTag({path:join(frontend,'dist/assets/main.css')});await page.addScriptTag({path:join(temporary,'preview.js')});
 await page.waitForTimeout(300);if(!(await page.getByRole('button',{name:'Generate with model',exact:true}).count()))throw Error(JSON.stringify({errors,body:await page.locator('body').innerText()}));
 const generate=page.getByRole('button',{name:'Generate with model',exact:true}),download=page.getByRole('button',{name:'Download report',exact:true});
 const bounds=await generate.boundingBox();assert.ok(bounds&&bounds.y>=0&&bounds.y+bounds.height<=950,'Generation must be visible without scrolling through 30 findings.');
 await generate.click();await page.getByLabel('Model-assisted narrative · editable').waitFor();assert.ok(await download.isDisabled());
 assert.equal(await page.evaluate(()=>window.calls[0].allow_remote),false);
 assert.ok((await page.getByRole('textbox',{name:'Model-assisted narrative · editable'}).inputValue()).includes(id(4)));
 assert.equal(await page.locator('script').count(),1); // Only the fixture script, never generated text.
 const reviewed=page.getByRole('checkbox',{name:'I reviewed this draft',exact:false});await reviewed.check();assert.ok(await download.isEnabled());
 await page.getByLabel('Model-assisted narrative · editable').fill('Investigator amendment');assert.ok(await download.isDisabled());await reviewed.check();
 const file=page.waitForEvent('download');await download.click();const artifact=await file;assert.match(artifact.suggestedFilename(),/report\.txt$/);
 await page.getByLabel('Scope and investigative questions').fill('New scope');assert.equal(await page.getByLabel('Model-assisted narrative · editable').count(),0);await page.getByText('Report inputs changed.',{exact:false}).waitFor();
 await page.getByRole('checkbox',{name:'Allow sending extracted source text',exact:false}).check();await generate.click();await page.getByLabel('Model-assisted narrative · editable').waitFor();assert.equal(await page.evaluate(()=>window.calls.at(-1).allow_remote),true);
 // Late model responses cannot replace a draft after its source inputs change.
 await generate.click();await page.getByLabel('Investigator notes').fill('Changed during generation');await generate.waitFor();assert.equal(await page.getByLabel('Model-assisted narrative · editable').count(),0);
 await page.evaluate(()=>window.fail=true);await generate.click();await page.getByRole('alert').waitFor();assert.deepEqual(errors,[]);
 console.log('PASS report browser: generation, exact citations, escaped prose, sharing consent, review gate, edit invalidation, download, stale response rejection and safe generation failure.');
}finally{await browser?.close();await rm(temporary,{recursive:true,force:true});}
