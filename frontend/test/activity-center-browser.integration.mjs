import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const frontend=fileURLToPath(new URL('..',import.meta.url));
const root=fileURLToPath(new URL('../..',import.meta.url));
const scratch=await mkdtemp(join(tmpdir(),'evora-activity-browser-'));
const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const server=spawn(process.env.EVORA_TEST_PYTHON ?? 'python',['-c', `import sys
from pathlib import Path
from backend.app import create_app
from starlette.staticfiles import StaticFiles
import uvicorn
app=create_app(sys.argv[1],storage_dir=sys.argv[2],offline_mode=True)
app.mount('/',StaticFiles(directory=sys.argv[3],html=True))
uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[4]),access_log=False)
`,join(scratch,'case.sqlite'),join(scratch,'evidence'),join(frontend,'dist'),String(port)],{cwd:root,stdio:['ignore','ignore','pipe']});
let diagnostics='';server.stderr.on('data',chunk=>{diagnostics=(diagnostics+chunk).slice(-4000);});
const closed=new Promise(resolve=>server.once('close',resolve));
let browser;
try {
const origin=`http://127.0.0.1:${port}`;
for(let i=0;i<60;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
const setup=await fetch(origin+'/api/v1/auth/setup',{method:'POST',headers:{'Content-Type':'application/json','X-Evora-Request':'1'},body:JSON.stringify({username:'batch-demo',display_name:'Batch Demo',password:'disposable bulk demo passphrase'})});
assert.equal(setup.status,200);const cookie=setup.headers.get('set-cookie').split(';')[0];
async function request(path,options={}){const response=await fetch(origin+'/api/v1'+path,{...options,headers:{Cookie:cookie,'X-Evora-Request':'1',...options.headers}});assert.ok(response.ok,`${path}: ${response.status}`);return response.json();}
const record=await request('/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Bulk processing browser demo'})});
for(let i=0;i<3;i++){
 const body=new FormData();body.set('file',new File([`Synthetic note ${i}. No allegation is established.\n`],`note-${i}.txt`,{type:'text/plain'}));body.set('kind','document');body.set('source_label',`Note ${i}`);
 await request(`/cases/${record.id}/evidence`,{method:'POST',body});
}
browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1365,height:1000}});
 const split=cookie.indexOf('=');await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:origin,httpOnly:true,sameSite:'Strict'}]);
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);
 await page.getByRole('button',{name:'Open case Bulk processing browser demo',exact:true}).click();
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Process all',exact:true}).click();
 await page.getByRole('heading',{name:'Process all case evidence',exact:true}).waitFor();
 await page.getByRole('checkbox',{name:'Include image descriptions, OCR and video scene analysis',exact:true}).check();
 await page.getByRole('button',{name:'Start batch',exact:true}).isDisabled().then(value=>assert.ok(value));
 await page.getByRole('checkbox',{name:'Include image descriptions, OCR and video scene analysis',exact:true}).uncheck();
 let statusHeld;const held=new Promise(resolve=>statusHeld=resolve);let statusRoute;
 await page.route('**/processing-runs/*',async route=>{if(!statusRoute && route.request().method()==='GET'){statusRoute=route;statusHeld();}else await route.continue();});
 await page.getByRole('button',{name:'Start batch',exact:true}).click();
 await Promise.race([held,new Promise((_,reject)=>{const timer=setTimeout(()=>reject(Error('No processing status request: '+diagnostics)),15000);timer.unref();})]);
 await page.getByRole('tab',{name:'Timeline',exact:true}).click();
 await page.getByRole('button',{name:'Activity (1 running)',exact:true}).click();
 await page.getByRole('region',{name:'Processing activity',exact:true}).waitFor();
 await page.getByText('Current: note-', {exact:false}).waitFor();
 await page.getByRole('link',{name:'Cases',exact:true}).click();
 await page.getByRole('button',{name:'Open case Bulk processing browser demo',exact:true}).waitFor();
 await page.getByRole('button',{name:'Activity (1 running)',exact:true}).click();
 await page.getByText('Current: note-', {exact:false}).waitFor();
 await page.getByRole('button',{name:'Stop queue',exact:true}).click();
 await page.getByText('Queue stopped',{exact:true}).waitFor();
 await statusRoute.abort().catch(()=>{});await page.unroute('**/processing-runs/*');
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Open case Bulk processing browser demo',exact:true}).click();
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();
 await page.getByRole('button',{name:'Process all',exact:true}).click();
 await page.getByRole('button',{name:'Check remaining files',exact:true}).click();
 await page.getByText('3 of 3 checked · 2 completed · 1 skipped · 0 failed · 0 unconfirmed',{exact:true}).waitFor({timeout:60000});
 await page.getByRole('button',{name:'Check remaining files',exact:true}).click();
 await page.getByText('3 of 3 checked · 0 completed · 3 skipped · 0 failed · 0 unconfirmed',{exact:true}).waitFor();
 await page.screenshot({path:join(scratch,'activity-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:join(scratch,'activity-mobile.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'No mobile page overflow');
 assert.deepEqual(errors,[]);
 console.log('PASS activity browser: navigation while processing, header current file, stop from another tab, resume, no duplicate runs; local admin session, Process all panel, missing vision-model guard, basic batch progress, completed-run skip, desktop/mobile layout and no JavaScript errors.');
}finally{await browser?.close();server.kill('SIGTERM');await closed;await rm(scratch,{recursive:true,force:true});}
