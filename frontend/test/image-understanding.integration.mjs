// Real UI/API/SQLite; explicit local HTTP vision-provider double, not an accuracy evaluation.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const root = fileURLToPath(new URL('../../', import.meta.url));
const scratch = await mkdtemp(join(tmpdir(), 'evora-image-understanding-'));
const calls=[];let failNext=false;let catalogMode='normal';
const provider=createServer(async(req,res)=>{
 try{
  const chunks=[];for await(const chunk of req)chunks.push(chunk);
  const body=JSON.parse(Buffer.concat(chunks).toString()||'{}');
  if(req.url==='/v1/models'){
   res.setHeader('Content-Type','application/json');
   if(req.headers.authorization==='Bearer synthetic-rejected-key'){res.writeHead(401);res.end(JSON.stringify({error:'private provider response'}));return;}
   const text={id:'synthetic-text',architecture:{input_modalities:['text']}};
   res.end(JSON.stringify({data:catalogMode==='unknown' ? [{id:'synthetic-text'}] : catalogMode==='empty' ? [text] : [text,{id:'synthetic-vision',architecture:{input_modalities:['text','image']}}]}));return;
  }
  if(req.url!=='/v1/chat/completions'){res.writeHead(404).end();return;}
  calls.push({body,authorization:req.headers.authorization});
  if(failNext){failNext=false;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:'length',message:{content:'{}'}}]}));return;}
  res.setHeader('Content-Type','application/json');
  res.end(JSON.stringify({model:'synthetic-vision-actual',choices:[{finish_reason:'stop',message:{content:JSON.stringify({description:'A person in a light-colored suit against a dark background.',visible_text:'SYNTHETIC OCR FIXTURE\nReference 42',limitations:['Protocol fixture, not measured OCR accuracy.']})}}]}));
 }catch{res.writeHead(500).end();}
});
await new Promise(resolve=>provider.listen(0,'127.0.0.1',resolve));
const endpoint=`http://127.0.0.1:${provider.address().port}/v1`;
const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const child=spawn(process.env.EVORA_TEST_PYTHON??'python',['-m','backend.run','--database',join(scratch,'case.sqlite'),'--storage',join(scratch,'evidence'),'--port',String(port)],{cwd:root,env:{...process.env,EVORA_QA_MODEL:''},stdio:['ignore','ignore','pipe']});
let diagnostics='';child.stderr.on('data',chunk=>{diagnostics=(diagnostics+chunk).slice(-3000);});
const origin=`http://127.0.0.1:${port}`;
let browser,page;
try{
 for(let i=0;i<100;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)break;}catch{}if(child.exitCode!==null)throw Error(diagnostics);await new Promise(resolve=>setTimeout(resolve,100));if(i===99)throw Error('Server startup timeout');}
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1400,height:1000}});
 await context.request.post(origin+'/api/v1/auth/setup',{headers:{'X-Evora-Request':'1'},data:{username:'vision-test',display_name:'Vision Tester',password:'synthetic vision passphrase'}});
 page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);await page.getByRole('button',{name:'Settings',exact:true}).click();let dialog=page.getByRole('dialog');
 await dialog.getByRole('switch',{name:'Offline mode — local models only',exact:true}).uncheck();
 await dialog.getByLabel('Provider').selectOption('openai');
 await dialog.getByLabel('API Key',{exact:true}).fill('synthetic-key');await dialog.getByLabel('Base URL',{exact:true}).fill(endpoint);
 // Test the unsaved online draft while the backend is still in offline mode.
 await dialog.getByRole('button',{name:'Test Connection & Fetch Models',exact:true}).click();
 await dialog.getByRole('button',{name:'synthetic-text',exact:true}).click();
 await dialog.getByRole('button',{name:'Fetch image-capable models',exact:true}).click();
 const picker=dialog.getByRole('region',{name:'Image-capable models',exact:true});
 await picker.getByRole('button',{name:'Use synthetic-vision for images',exact:true}).waitFor();
 assert.equal(await picker.getByRole('button',{name:'Use synthetic-text for images',exact:true}).count(),0);
 await picker.getByLabel('Filter image-capable models',{exact:true}).fill('no-such-model');
 await picker.getByText('No image-capable models match this search.',{exact:true}).waitFor();
 await picker.getByLabel('Filter image-capable models',{exact:true}).fill('vision');
 await picker.getByRole('button',{name:'Use synthetic-vision for images',exact:true}).click();
 assert.equal(await dialog.getByLabel('Custom model name',{exact:true}).inputValue(),'synthetic-text');
 assert.equal(await dialog.getByLabel('Vision model',{exact:true}).inputValue(),'synthetic-vision');
 assert.equal(await dialog.getByRole('switch',{name:'Use selected model for image description and OCR',exact:true}).isChecked(),false);
 catalogMode='unknown';await dialog.getByRole('button',{name:'Fetch image-capable models',exact:true}).click();
 await picker.getByText('The provider does not publish image capabilities in its model list. Enter a supported vision model manually.',{exact:true}).waitFor();
 catalogMode='empty';await dialog.getByRole('button',{name:'Fetch image-capable models',exact:true}).click();
 await picker.getByText('No image-capable models were advertised by this provider.',{exact:true}).waitFor();
 await dialog.getByRole('button',{name:'Save Settings',exact:true}).click();await dialog.waitFor({state:'detached'});
 await page.getByRole('button',{name:'Settings',exact:true}).click();dialog=page.getByRole('dialog');
 assert.equal(await dialog.getByLabel('Custom model name',{exact:true}).inputValue(),'synthetic-text');
 assert.equal(await dialog.getByLabel('Vision model',{exact:true}).inputValue(),'synthetic-vision');
 catalogMode='normal';await dialog.getByRole('button',{name:'Test Connection & Fetch Models',exact:true}).click();
 await dialog.getByRole('button',{name:'synthetic-vision · Image input',exact:true}).click();
 await dialog.getByRole('switch',{name:'Use selected model for image description and OCR',exact:true}).check();
 assert.equal(await dialog.getByLabel('Vision model',{exact:true}).count(),0);
 await dialog.getByLabel('API Key',{exact:true}).fill('synthetic-rejected-key');
 await dialog.getByRole('button',{name:'Test Connection & Fetch Models',exact:true}).click();
 await dialog.getByText('The provider rejected the API key (HTTP 401). Check that it is a key for this provider.',{exact:true}).waitFor();
 await dialog.getByLabel('API Key',{exact:true}).fill('synthetic-key');
 await dialog.getByRole('button',{name:'Save Settings',exact:true}).click();await dialog.waitFor({state:'detached'});
 await page.locator('.case-creation summary').click();await page.getByLabel('Title (required)',{exact:true}).fill('Vision protocol acceptance');await page.getByRole('button',{name:'Create case',exact:true}).click();
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:'＋ Add evidence',exact:true}).click();
 await page.locator('#batch-evidence-files').setInputFiles(join(root,'fixtures/media/astronaut.png'));
 await page.getByRole('button',{name:'Upload 1 source',exact:true}).click();await page.getByText('1 source uploaded. Select a source in the library to inspect it and start extraction.',{exact:true}).waitFor();
 const image=page.getByRole('region',{name:'Image description and OCR',exact:true});await image.getByText('Hosted / OpenAI-compatible',{exact:true}).waitFor();
 assert.ok(await image.getByRole('button',{name:'Describe image and extract text',exact:true}).isDisabled());assert.equal(calls.length,0);
 await image.getByRole('checkbox').check();await image.getByRole('button',{name:'Describe image and extract text',exact:true}).click();
 await image.getByText('A person in a light-colored suit against a dark background.',{exact:true}).waitFor();
 await image.getByText('SYNTHETIC OCR FIXTURE\nReference 42',{exact:true}).waitFor();
 await image.getByRole('button',{name:'Describe image and extract text',exact:true}).waitFor();
 assert.ok(!(await image.getByRole('button',{name:'Describe image and extract text',exact:true}).isDisabled()),'Successful processing must release the image action');
 assert.equal(calls.length,1);assert.equal(calls[0].authorization,'Bearer synthetic-key');
 const dataUrl=calls[0].body.messages[1].content[1].image_url.url;assert.ok(dataUrl.startsWith('data:image/png;base64,'));assert.ok(Buffer.from(dataUrl.split(',')[1],'base64').length>1000);
 assert.equal(calls[0].body.model,'synthetic-vision','Shared model must be used without a separate vision model');
 assert.equal(await page.evaluate(()=>JSON.stringify(localStorage).includes('synthetic-key')),false);
 await page.getByRole('button',{name:'Open media inspector',exact:true}).click();
 await page.locator('.media-viewer img').waitFor();
 await image.getByText('Image-processing provenance · synthetic-vision-actual',{exact:true}).click();
 await page.screenshot({path:join(scratch,'image-results.png'),fullPage:true});
 failNext=true;await image.getByRole('button',{name:'Describe image and extract text',exact:true}).click();
 await image.getByText('Image understanding failed. Check that the selected model supports images and that its service and credentials are available. Earlier completed results remain available.',{exact:true}).waitFor();
 assert.ok(!(await image.getByRole('button',{name:'Describe image and extract text',exact:true}).isDisabled()),'Failed processing must release the image action');
 assert.equal(calls.length,2);
 await page.reload();await page.getByRole('button',{name:'Open case Vision protocol acceptance',exact:true}).click();await page.getByRole('tab',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:'astronaut.png',exact:true}).click();
 await page.getByRole('region',{name:'Image description and OCR',exact:true}).getByText('SYNTHETIC OCR FIXTURE\nReference 42',{exact:true}).waitFor();assert.equal(calls.length,2,'Reload must never transmit an image automatically');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:join(scratch,'image-mobile.png'),fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.getByRole('button',{name:'Settings',exact:true}).click();dialog=page.getByRole('dialog');await dialog.getByRole('switch',{name:'Offline mode — local models only',exact:true}).check();await dialog.getByRole('button',{name:'Save Settings',exact:true}).click();await dialog.waitFor({state:'detached'});
 assert.deepEqual(errors,[]);
 console.log('PASS: online/offline settings, explicit image consent, image content transmission, description and OCR publication, provenance, persisted results, no auto-transmission, responsive layout. Provider protocol double; no live paid-provider accuracy claim.');
 console.log('Artifacts: '+scratch);
}catch(error){if(page)await page.screenshot({path:join(scratch,'failure.png'),fullPage:true});console.error('Artifacts: '+scratch);throw error;}
finally{await browser?.close();child.kill('SIGTERM');await new Promise(resolve=>provider.close(resolve));}
