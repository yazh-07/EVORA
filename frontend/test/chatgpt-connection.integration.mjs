// Real workstation/UI, with explicit OAuth UI protocol doubles. Never signs into a real account.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url)),scratch=await mkdtemp(join(tmpdir(),'evora-chatgpt-ui-'));
const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const child=spawn(process.env.EVORA_TEST_PYTHON??'python',['-m','backend.run','--database',join(scratch,'db.sqlite'),'--storage',join(scratch,'evidence'),'--port',String(port)],{cwd:root,stdio:['ignore','ignore','pipe']});
let diagnostics='';child.stderr.on('data',data=>{diagnostics=(diagnostics+data).slice(-3000);});
const origin=`http://127.0.0.1:${port}`;let browser,page;
try{
 for(let i=0;i<150;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)break;}catch{}assert.equal(child.exitCode,null,diagnostics);await new Promise(resolve=>setTimeout(resolve,100));}
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1400,height:1000}});let connected=false,userID='';
 const reply=(route,json)=>route.fulfill({json,headers:{'X-Evora-User':userID}});
 await context.route(origin+'/api/v1/chatgpt/status',route=>reply(route,{connected,sharing:connected,email:connected?'test@example.test':'',pending:false,error:''}));
 await context.route(origin+'/api/v1/chatgpt/connect',route=>{assert.equal(route.request().postDataJSON().offline_mode,false);return reply(route,{authorization_url:'https://auth.openai.com/api/accounts/authorize?state=synthetic-ui-fixture'});});
 await context.route('https://auth.openai.com/**',route=>{connected=true;return route.fulfill({contentType:'text/html',body:'Synthetic authorization UI fixture; no real account.'});});
 await context.route(origin+'/api/v1/chatgpt/disconnect',route=>{connected=false;return reply(route,{disconnected:true,revoked:true});});
 await context.route(origin+'/api/v1/settings/models',route=>{assert.equal(route.request().postDataJSON().qa_provider,'chatgpt');return reply(route,{models:['test-multimodal']});});
 const setup=await context.request.post(origin+'/api/v1/auth/setup',{headers:{'X-Evora-Request':'1'},data:{username:'oauth-ui',display_name:'OAuth UI',password:'isolated oauth ui passphrase'}});assert.ok(setup.ok());userID=(await setup.json()).user.id;
 page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);await page.getByRole('button',{name:'Settings',exact:true}).click();let dialog=page.getByRole('dialog');
 await dialog.getByRole('switch',{name:'Offline mode — local models only',exact:true}).uncheck();await dialog.getByLabel('Provider').selectOption('chatgpt');
 assert.equal(await dialog.getByLabel('API Key',{exact:true}).count(),0);assert.equal(await dialog.getByLabel('Base URL',{exact:true}).count(),0);
 const [popup]=await Promise.all([context.waitForEvent('page'),dialog.getByRole('button',{name:'Continue with ChatGPT',exact:true}).click()]);
 await dialog.getByText('Connected as test@example.test. Plan usage authorized. Fetch models to choose one.',{exact:true}).waitFor();await popup.close();
 await dialog.getByRole('button',{name:'Test Connection & Fetch Models',exact:true}).click();await dialog.getByRole('button',{name:'test-multimodal',exact:true}).click();
 assert.ok(await dialog.getByRole('switch',{name:'Use selected model for image description and OCR',exact:true}).isChecked());
 await page.screenshot({path:join(scratch,'connected.png'),fullPage:true});
 await dialog.getByRole('button',{name:'Save Settings',exact:true}).click();await dialog.waitFor({state:'detached'});
 const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('evora-settings')));assert.equal(stored.qa_provider,'chatgpt');assert.equal(stored.qa_model,'test-multimodal');
 assert.equal(await page.evaluate(()=>JSON.stringify(localStorage).includes('access_token')),false);
 await page.getByRole('button',{name:'Settings',exact:true}).click();dialog=page.getByRole('dialog');await dialog.getByRole('button',{name:'Disconnect ChatGPT',exact:true}).click();
 await dialog.getByRole('button',{name:'Continue with ChatGPT',exact:true}).waitFor();assert.equal(connected,false);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
 console.log('PASS: provider selection, no API key/base URL, browser popup, connection status, model discovery, shared image model, saved preferences, disconnect, no browser tokens and mobile layout. OAuth UI protocol doubles; no live plan inference claim. Artifacts: '+scratch);
}catch(error){if(page)await page.screenshot({path:join(scratch,'failure.png'),fullPage:true});console.error('Artifacts: '+scratch);throw error;}
finally{await browser?.close();child.kill('SIGTERM');}
