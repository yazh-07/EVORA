// Opt-in real local-account workstation acceptance. Requires a fresh disposable backend.
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
if(process.env.EVORA_DISPOSABLE_BACKEND!=='1')throw Error('Set EVORA_DISPOSABLE_BACKEND=1 only for a fresh test workstation.');
const {chromium}=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const origin=process.env.EVORA_BROWSER_BASE_URL??'http://127.0.0.1:8917';
const artifacts='/tmp/evora-results-live-qa';await mkdir(artifacts,{recursive:true});
const status=await fetch(origin+'/api/v1/auth/status').then(r=>r.json());assert.equal(status.setup_required,true,'Refuse a workstation with existing accounts');
const setup=await fetch(origin+'/api/v1/auth/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Evora-Request':'1'},body:JSON.stringify({username:'results-qa',display_name:'Results QA',password:'Disposable results QA passphrase 2026'})});
assert.equal(setup.status,200);const cookie=setup.headers.get('set-cookie').split(';')[0];
async function api(path,options={}){const r=await fetch(origin+'/api/v1'+path,{...options,headers:{Cookie:cookie,'X-Evora-Request':'1',...options.headers}});assert.ok(r.ok,`${path}: ${r.status}`);return r.json();}
const record=await api('/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Results / Real backend test'})});
const body=new FormData();body.set('kind','network_log');body.set('source_label','Gateway records');body.set('file',new Blob([await readFile(new URL('../../fixtures/synthetic-case/network.csv',import.meta.url))],{type:'text/csv'}),'network.csv');
const source=await api(`/cases/${record.id}/evidence`,{method:'POST',body});
const run=await api(`/cases/${record.id}/evidence/${source.id}/processing-runs`,{method:'POST',headers:{'Idempotency-Key':randomUUID()}});
for(let i=0;i<100;i++){const state=await api(`/cases/${record.id}/evidence/${source.id}/processing-runs/${run.id}`);if(state.status==='completed')break;assert.notEqual(state.status,'failed');if(i===99)throw Error('Processing timed out');await new Promise(r=>setTimeout(r,100));}
const results=await api(`/cases/${record.id}/evidence/${source.id}/results`);assert.equal(results.operations[0].status,'completed');assert.ok(results.total>0);assert.equal(results.items[0].processing_run_id,run.id);
const browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const split=cookie.indexOf('=');await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:origin,httpOnly:true,sameSite:'Strict'}]);
 await page.goto(origin);await page.getByRole('button',{name:`Open case ${record.title}`,exact:true}).click();
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:source.source_label,exact:true}).click();
 await page.locator('.extracted-result-list > li > button').first().click();await page.getByText('Original source lines · size and SHA-256 verified.',{exact:true}).waitFor();
 await page.screenshot({path:artifacts+'/records.png',fullPage:true});
 await page.getByRole('tab',{name:'Timeline',exact:true}).click();await page.locator('.activity-bars button').first().click();
 assert.ok(await page.getByLabel('From (UTC)',{exact:true}).inputValue());await page.screenshot({path:artifacts+'/timeline.png',fullPage:true});
 await page.setViewportSize({width:360,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);console.log('PASS real backend: local account/cookie, original upload, processing, operation-specific Results API, readable results, verified source excerpt, event histogram/date filter, mobile width. No API mocks.');
 await context.close();
}finally{await browser.close();}
