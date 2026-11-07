// Real local authentication, UI, immutable original and corrected CSV processing.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium }=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const root=fileURLToPath(new URL('../..',import.meta.url));
const scratch=await mkdtemp(join(tmpdir(),'evora-structured-csv-'));
const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const server=spawn(process.env.EVORA_TEST_PYTHON??'python',['-m','backend.run','--database',join(scratch,'case.sqlite'),'--storage',join(scratch,'evidence'),'--port',String(port)],{cwd:root,stdio:['ignore','ignore','pipe']});
let diagnostics='',browser;server.stderr.on('data',chunk=>{diagnostics=(diagnostics+chunk).slice(-4000);});
const closed=new Promise(resolve=>server.once('close',resolve));const origin=`http://127.0.0.1:${port}`;
try{
 for(let i=0;i<100;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)break;}catch{}if(server.exitCode!==null)throw Error(diagnostics);await new Promise(r=>setTimeout(r,100));}
 const setup=await fetch(origin+'/api/v1/auth/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Evora-Request':'1'},body:JSON.stringify({username:'csv-regression',display_name:'CSV Regression',password:'disposable CSV regression passphrase'})});
 assert.equal(setup.status,200);const cookie=setup.headers.get('set-cookie').split(';')[0];
 const request=async(path,options={})=>{const response=await fetch(origin+'/api/v1'+path,{...options,headers:{Cookie:cookie,'X-Evora-Request':'1',...options.headers}});assert.ok(response.ok,`${path}: ${response.status}`);return response.json();};
 const record=await request('/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Structured CSV correction'})});
 const csv='timestamp,device_id,event,detail\n2026-11-05T09:13:00Z,D-101,notification,Cancellation delivered; reading unverified.\n';
 const body=new FormData();body.set('file',new File([csv],'mobile.csv',{type:'text/csv'}));body.set('kind','document');body.set('source_label','Mobile export uploaded as document');
 const item=await request(`/cases/${record.id}/evidence`,{method:'POST',body});
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1365,height:950}});const split=cookie.indexOf('=');await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:origin,httpOnly:true,sameSite:'Strict'}]);
 const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(origin);await page.getByRole('button',{name:'Open case Structured CSV correction',exact:true}).click();await page.getByRole('tab',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Mobile export uploaded as document',exact:true}).click();
 await page.getByLabel('Interpret this CSV as').selectOption('mobile_log');await page.getByRole('button',{name:'Start processing',exact:true}).click();
 await page.getByText('Interpreted as mobile log.',{exact:false}).waitFor();
 await page.getByText('Last reported status: completed',{exact:true}).waitFor({timeout:30000});
 const history=await request(`/cases/${record.id}/evidence/${item.id}/processing-runs`);assert.equal(history.length,1);assert.equal(history[0].processing_kind,'mobile_log');assert.equal(history[0].source_kind,'document');
 const observations=await request(`/cases/${record.id}/observations?evidence_id=${item.id}&limit=100&offset=0`);assert.ok(observations.items.some(o=>o.kind==='mobile.device'&&o.normalized_value==='D-101'));assert.ok(observations.items.every(o=>o.processing_run_id===history[0].id));
 const source=await request(`/cases/${record.id}/evidence/${item.id}`);assert.equal(source.kind,'document');assert.equal(source.sha256,item.sha256);
 const original=await fetch(origin+`/api/v1/cases/${record.id}/evidence/${item.id}/content`,{headers:{Cookie:cookie}});assert.equal(await original.text(),csv);
 await page.reload();await page.getByRole('button',{name:'Open case Structured CSV correction',exact:true}).click();await page.getByRole('tab',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:'Mobile export uploaded as document',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('select')&&[...document.querySelectorAll('select')].some(select=>select.value==='mobile_log'));
 assert.equal(await page.getByLabel('Interpret this CSV as').inputValue(),'mobile_log');assert.deepEqual(errors,[]);
 console.log('PASS structured CSV browser: local-admin authorization, explicit interpretation, actual mobile records, preserved uploaded metadata/original bytes and restored processing choice after reload.');
}finally{await browser?.close();server.kill('SIGTERM');await closed;await rm(scratch,{recursive:true,force:true});}
