// Real UI, video decoding, processing and SQL; hosted vision protocol double.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const root=fileURLToPath(new URL('../../',import.meta.url));
const scratch=await mkdtemp(join(tmpdir(),'evora-video-browser-'));
const python=process.env.EVORA_TEST_PYTHON??'python';
const fixture=join(scratch,'clip.mp4');
const generated=spawnSync(python,['-c','from pathlib import Path; import sys; from backend.tests.test_media_detection import video_bytes; Path(sys.argv[1]).write_bytes(video_bytes())',join(scratch,'clip.avi')],{cwd:root});
assert.equal(generated.status,0,generated.stderr.toString());
const encoded=spawnSync('ffmpeg',['-nostdin','-v','error','-i',join(scratch,'clip.avi'),'-c:v','libx264','-pix_fmt','yuv420p','-y',fixture]);
assert.equal(encoded.status,0,encoded.stderr.toString());
let calls=0, fail=false;
const provider=createServer(async(req,res)=>{
 const chunks=[];for await(const chunk of req)chunks.push(chunk);
 const body=JSON.parse(Buffer.concat(chunks).toString()||'{}');
 if(req.url!=='/v1/chat/completions'){res.writeHead(404).end();return;}
 calls++;assert.ok(body.messages[1].content[1].image_url.url.startsWith('data:image/png;base64,'));
 res.setHeader('Content-Type','application/json');
 res.end(JSON.stringify({model:'vision-double',choices:[{finish_reason:fail?'length':'stop',message:{content:JSON.stringify({description:'Sampled frame description.',visible_text:'VIDEO TEXT',limitations:['Synthetic protocol output.']})}}]}));
});
await new Promise(resolve=>provider.listen(0,'127.0.0.1',resolve));
const endpoint=`http://127.0.0.1:${provider.address().port}/v1`;
const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
const child=spawn(python,['-m','backend.run','--database',join(scratch,'case.sqlite'),'--storage',join(scratch,'evidence'),'--port',String(port)],{cwd:root,stdio:['ignore','ignore','pipe']});
let diagnostics='';child.stderr.on('data',data=>{diagnostics=(diagnostics+data).slice(-4000);});
const origin=`http://127.0.0.1:${port}`;let browser,page;
try {
 for(let i=0;i<150;i++){try{if((await fetch(origin+'/api/v1/auth/status')).ok)break;}catch{}assert.equal(child.exitCode,null,diagnostics);await new Promise(resolve=>setTimeout(resolve,100));}
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1400,height:1000}});
 const headers={'X-Evora-Request':'1'};
 assert.ok((await context.request.post(origin+'/api/v1/auth/setup',{headers,data:{username:'video-browser',display_name:'Video Browser',password:'disposable video browser passphrase'}})).ok());
 assert.ok((await context.request.put(origin+'/api/v1/settings',{headers,data:{offline_mode:false,qa_provider:'openai',openai_base_url:endpoint,openai_api_key:'synthetic-key',vision_model:'vision-double'}})).ok());
 page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin);await page.locator('.case-creation summary').click();await page.getByLabel('Title (required)',{exact:true}).fill('Video acceptance');await page.getByRole('button',{name:'Create case',exact:true}).click();
 await page.getByRole('tab',{name:'Evidence',exact:true}).click();await page.getByRole('button',{name:'＋ Add evidence',exact:true}).click();
 await page.locator('#batch-evidence-files').setInputFiles(fixture);await page.getByRole('button',{name:'Upload 1 source',exact:true}).click();
 const panel=page.getByRole('region',{name:'Video scene analysis',exact:true});await panel.getByText('vision-double',{exact:true}).waitFor();
 assert.ok(await panel.getByRole('button',{name:'Analyze video scenes and text',exact:true}).isDisabled());assert.equal(calls,0);
 await panel.getByLabel('Frame sampling interval (seconds)',{exact:true}).fill('1');await panel.getByLabel('Maximum frames to describe',{exact:true}).fill('2');
 await panel.getByRole('checkbox').filter({visible:true}).last().check();
 await panel.getByRole('button',{name:'Analyze video scenes and text',exact:true}).click();
 await panel.getByText('Sampled frame description.',{exact:true}).first().waitFor();
 assert.equal(await panel.getByText('Sampled frame description.',{exact:true}).count(),2);assert.equal(calls,2);
 await page.getByRole('button',{name:'Open media inspector',exact:true}).click();
 const video=page.locator('video');await video.waitFor();await page.waitForFunction(()=>document.querySelector('video')?.readyState>=1);
 await panel.getByRole('button',{name:'At 2.00s',exact:true}).click();assert.ok(Math.abs(await video.evaluate(el=>el.currentTime)-2)<.1);
 await panel.getByText('Video-processing provenance and sampled coverage',{exact:true}).click();await page.screenshot({path:join(scratch,'video-results.png'),fullPage:true});
 fail=true;await panel.getByRole('button',{name:'Analyze video scenes and text',exact:true}).click();
 await panel.getByText('Video analysis failed. Check the model, media decoder and speech configuration. Earlier completed results remain available.',{exact:true}).waitFor();
 assert.equal(await panel.getByText('Sampled frame description.',{exact:true}).count(),2);
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);console.log('PASS: video consent, bounded frames, descriptions/OCR, timestamp seeking, provenance, failed rerun retention and mobile layout. Vision provider double; live speech tested separately. Artifacts: '+scratch);
} catch(error){if(page)await page.screenshot({path:join(scratch,'failure.png'),fullPage:true});console.error('Artifacts: '+scratch);throw error;}
finally{await browser?.close();child.kill('SIGTERM');await new Promise(resolve=>provider.close(resolve));}
