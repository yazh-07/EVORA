// Requires the local synthetic server from test/serve-cases.py. Never use a production case.
import { readFile, mkdir } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const origin = process.env.EVORA_BROWSER_BASE_URL ?? 'http://127.0.0.1:8913';
const artifactDir = process.env.EVORA_BROWSER_ARTIFACTS ?? `/tmp/evora-workspace-browser-${Date.now()}`;
await mkdir(artifactDir, {recursive:true});
const caseTitle = `Synthetic workspace review ${Date.now()}`;
async function request(path, options={}) {
 const response=await fetch(origin+'/api/v1'+path,{...options,headers:{Authorization:'Bearer u02-synthetic-one',...options.headers}});
 if(!response.ok) throw Error(`Synthetic setup failed: ${response.status} ${path}`);
 return response.json();
}
const caseRecord=await request('/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:caseTitle,description:'Compare synthetic network and location records; verify source references.'})});
for(const [name,kind,label] of [['network.csv','network_log','Gateway access log'],['gps.csv','gps','Device location export']]) {
 const bytes=await readFile(new URL('../../fixtures/synthetic-case/'+name,import.meta.url));
 const body=new FormData();body.set('file',new Blob([bytes],{type:'text/csv'}),name);body.set('kind',kind);body.set('source_label',label);
 const evidence=await request(`/cases/${caseRecord.id}/evidence`,{method:'POST',body});
 const run=await request(`/cases/${caseRecord.id}/evidence/${evidence.id}/processing-runs`,{method:'POST',headers:{'Idempotency-Key':randomUUID()}});
 await completed(`/cases/${caseRecord.id}/evidence/${evidence.id}/processing-runs/${run.id}`);
}
async function completed(path) {
 for(let i=0;i<200;i++){const run=await request(path);if(run.status==='completed')return run;if(run.status==='failed')throw Error('Synthetic processing failed');await new Promise(resolve=>setTimeout(resolve,100));}
 throw Error('Synthetic processing timed out');
}
const analysis=await request(`/cases/${caseRecord.id}/analysis-runs`,{method:'POST',headers:{'Idempotency-Key':randomUUID()}});
await completed(`/cases/${caseRecord.id}/analysis-runs/${analysis.id}`);
const findings=await request(`/cases/${caseRecord.id}/findings?analysis_run_id=${analysis.id}&limit=100`);
await request(`/cases/${caseRecord.id}/findings/${findings.items[0].id}/reviews`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'accepted',reason:'Synthetic acceptance: source references inspected.'})});
import assert from 'node:assert/strict';
const browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = []; page.on('pageerror', e => errors.push(e.message));
try {
 await page.goto(origin);
 await page.getByLabel('Access token', { exact: true }).fill('u02-synthetic-one');
 await page.getByRole('button', { name: 'Open cases', exact: true }).click();
 await page.getByRole('button', { name: `Open case ${caseTitle}`, exact: true }).click();
 await page.getByRole('button', { name: 'Review findings', exact: true }).waitFor();
 await page.screenshot({path:`${artifactDir}/overview.png`,fullPage:true});
 assert.equal(await page.getByRole('tab').count(),5);
 await page.getByRole('tab', {name:'Timeline',exact:true}).click();
 await page.locator('.timeline-list li').first().waitFor();
 await page.getByLabel('Search all events').fill('no-matching-record');
 await page.getByRole('heading',{name:'No events match these filters'}).waitFor();
 await page.getByRole('button',{name:'Clear filters',exact:true}).click();
 await page.screenshot({path:`${artifactDir}/timeline.png`,fullPage:true});
 await page.locator('.timeline-sources button').first().click();
 await page.getByRole('button',{name:'Preview original text',exact:true}).click();
 await page.getByText('Original bytes verified against the recorded SHA-256. Displayed as plain text.').waitFor();
 await page.screenshot({path:`${artifactDir}/evidence.png`,fullPage:true});
 await page.getByRole('tab',{name:'Investigation',exact:true}).click();
 await page.locator('.findings-list li').first().waitFor();
 await page.getByRole('button',{name:'Explore connections',exact:true}).click();
 await page.locator('.graph-node').first().waitFor();
 await page.screenshot({path:`${artifactDir}/connections.png`,fullPage:true});
 await page.getByRole('tab',{name:'Report',exact:true}).click();
 await page.getByLabel('Report title',{exact:true}).waitFor();
 await page.getByLabel('Scope and investigative questions',{exact:true}).fill('Compare the two original sources.');
 await page.getByLabel('Investigator notes',{exact:true}).fill('Verify clock alignment before drawing conclusions.');
 assert.equal(await page.locator('.report-finding-list input:checked').count(),1);
 await page.getByRole('tab',{name:'Timeline',exact:true}).click();
 await page.getByRole('tab',{name:'Report',exact:true}).click();
 assert.equal(await page.getByLabel('Investigator notes',{exact:true}).inputValue(),'Verify clock alignment before drawing conclusions.');
 const downloaded = page.waitForEvent('download');
 await page.getByRole('button',{name:'Download report',exact:true}).click();
 await (await downloaded).saveAs(`${artifactDir}/report.txt`);
 await page.screenshot({path:`${artifactDir}/report.png`,fullPage:true});
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'＋ Add evidence',exact:true}).click();
 await page.locator('#batch-evidence-files').setInputFiles([
 {name:'review-notes.txt',mimeType:'text/plain',buffer:Buffer.from('Review notes: compare the original timestamps.')},
 {name:'archive.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nsynthetic intake fixture')}
 ]);
 await page.getByRole('button',{name:'Upload 2 sources',exact:true}).click();
 await page.getByText('2 sources uploaded. Select a source in the library to inspect it and start extraction.').waitFor();
 assert.equal(await page.locator('.intake-queue li').filter({hasText:'uploaded'}).count(),2);
 await page.getByRole('tab',{name:'Overview',exact:true}).click();
 await page.getByRole('button',{name:'Refresh overview',exact:true}).click();
 await page.getByRole('heading',{name:'2 sources need attention',exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:`${artifactDir}/mobile.png`,fullPage:true});
 const heading=await page.locator('.case-heading h1').boundingBox();
 assert.ok(heading.width>300 && heading.height<150,'mobile header must remain readable');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),'mobile overflow');
 await page.getByRole('button',{name:'Switch to dark mode',exact:true}).click();
 await page.screenshot({path:`${artifactDir}/dark.png`,fullPage:true});
 await page.getByRole('button',{name:'End session',exact:true}).click();
 await page.getByRole('button',{name:'Open cases',exact:true}).waitFor();
 assert.equal(await page.locator('.report-preview').count(),0);
 assert.deepEqual(errors,[]);
 console.log('PASS: real API overview, timeline filters, source navigation, hash-verified preview, graph, report review defaults and export, tab draft retention, batch upload, mobile layout, themes, logout clearing.');
} catch (error) { console.log('Browser errors:', errors); await page.screenshot({path:`${artifactDir}/failure.png`,fullPage:true}); throw error; } finally { await browser.close(); }
