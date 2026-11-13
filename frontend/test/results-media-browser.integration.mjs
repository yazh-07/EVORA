// Synthetic extraction outputs with real, hash-verified media bytes and browser seeking.
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const frontend = fileURLToPath(new URL('..', import.meta.url));
const temporary = await mkdtemp(join(tmpdir(), 'evora-result-media-'));
const artifacts = process.env.EVORA_BROWSER_ARTIFACTS ?? '/tmp/evora-results-media-qa';
await mkdir(artifacts, {recursive:true});
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const created_at = '2026-01-01T00:00:00Z';
const wav = Buffer.alloc(44 + 16000 * 2); wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(wav.length-44,40);
execFileSync('ffmpeg',['-loglevel','error','-f','lavfi','-i','color=c=gray:s=160x120:d=2','-c:v','libvpx','-y',join(temporary,'video.webm')]);
const media = {image:await readFile(join(frontend,'../fixtures/media/astronaut.png')),audio:wav,video:await readFile(join(temporary,'video.webm')),gps:Buffer.from('timestamp,device_id,latitude,longitude\n'+Array.from({length:60},()=> '2026-01-01T00:00:00Z,D-1,12,77').join('\n')+'\n')};
let browser;
try {
 browser = await chromium.launch({ executablePath:process.env.EVORA_CHROME_PATH, headless:true, args:['--no-sandbox'] });
 for (const kind of ['image','audio','video','gps']) {
  const context = await browser.newContext({viewport:{width:1280,height:1000},reducedMotion:'reduce'}), page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const item={id:id(2),case_id:id(1),kind,filename:kind,source_label:kind+' source',media_type:kind==='image'?'image/png':kind==='audio'?'audio/wav':kind==='gps'?'text/csv':'video/webm',sha256:createHash('sha256').update(media[kind]).digest('hex'),size_bytes:media[kind].length,created_at};
  const observation = (n,kind,value,locator,run=3)=>({id:id(n),case_id:id(1),evidence_id:id(2),processing_run_id:id(run),kind,raw_value:value,normalized_value:value,source_locator:locator,extraction_confidence:0});
  const observations=kind==='gps'?Array.from({length:60},(_,n)=>observation(20+n,'gps.latitude',String(12+n/1000),`row ${String(n+2).padStart(3,'0')}, latitude`)):kind==='image'?[observation(10,'image.detection','person:face [classifier]','frame=0; time_offset=0s; box=100,50,70,70'),observation(11,'image.ocr','NOTICE Room 12','image=0; region=full',4)]:kind==='audio'?[observation(10,'transcript.segment','Meet at the gateway.','media:start_ms=250;end_ms=750')]:[observation(10,'video.frame_detection','person:fullbody [classifier]','frame=10; time_offset=1s; box=20,20,40,80'),observation(11,'video.scene','A gray sample frame.','frame=10; time_offset=1s',4)];
  const operations=kind==='gps'?['records']:kind==='image'?['detection','ocr']:kind==='audio'?['transcript']:['detection','description'];
  const opname=o=>o.kind.startsWith('gps.')?'records':o.kind.endsWith('detection')?'detection':o.kind.endsWith('ocr')?'ocr':o.kind==='video.scene'?'description':'transcript';
  const manifest=operations.map(operation=>({operation,status:'completed',count:kind==='gps'?60:1,output_run_id:id(operation==='ocr'||operation==='description'?4:3),latest_run_id:id(operation==='ocr'||operation==='description'?4:3),updated_at:created_at,notes:operation==='detection'?['Candidate detection. Identity unknown.']:[]}));
  await page.route('http://127.0.0.1:4179/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:'<html data-theme="light"><body><div id="root"></div></body></html>'});
   if(url.pathname.endsWith('/content'))return route.fulfill({contentType:'application/octet-stream',body:media[kind]});
   if(url.pathname.endsWith('/results')){const operation=url.searchParams.get('operation')??operations[0];const all=observations.filter(o=>opname(o)===operation),offset=Number(url.searchParams.get('offset')??0);return route.fulfill({json:{case_id:id(1),evidence_id:id(2),operation,operations:manifest,items:all.slice(offset,offset+50),total:all.length,limit:50,offset}});}
   if(url.pathname.endsWith('/observations')){const run=url.searchParams.get('processing_run_id');const items=observations.filter(o=>!run||o.processing_run_id===run);return route.fulfill({json:{items,total:items.length,limit:100,offset:0}});}
   throw Error('Unexpected request '+url.pathname);
  });
  await build({stdin:{contents:`import React from 'react';import{createRoot}from'react-dom/client';import{ApiProvider}from './src/api/ApiProvider';import{createApiClient}from './src/api/client';import{EvidenceResults}from './src/cases/EvidenceResults';const client=createApiClient({baseUrl:'http://127.0.0.1:4179'});client.setToken('fixture');createRoot(document.getElementById('root')).render(<ApiProvider client={client}><EvidenceResults item={${JSON.stringify(item)}} focus={${JSON.stringify(kind==='gps'?{observation_id:observations[59].id,processing_run_id:id(3),source_locator:observations[59].source_locator}:undefined)??'undefined'}} onDerivedRun={()=>{}}/></ApiProvider>);`,resolveDir:frontend,loader:'tsx'},outfile:join(temporary,'fixture.js'),bundle:true,format:'iife',platform:'browser',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
  await page.goto('http://127.0.0.1:4179');await page.addStyleTag({path:join(frontend,'dist/assets/main.css')});await page.addScriptTag({path:join(temporary,'fixture.js')});
  await page.locator('.extracted-result-list > li').first().waitFor();
  if(kind==='gps'){await page.getByText('51–60 of 60',{exact:true}).waitFor();await page.getByRole('complementary',{name:'Selected source record'}).getByText('row 061, latitude',{exact:true}).waitFor();await page.getByRole('button',{name:'Previous results',exact:true}).click();await page.getByText('1–50 of 60',{exact:true}).waitFor();await page.getByRole('button',{name:'Next results',exact:true}).click();await page.getByText('51–60 of 60',{exact:true}).waitFor();}else await page.locator('.extracted-result-list > li > button').first().click();
  if(kind==='image'){
   await page.getByRole('img',{name:'image source'}).waitFor();
   await page.getByRole('button',{name:/Inspect Face region · identity unknown/}).waitFor();
   await page.getByRole('button',{name:/Visible text Completed/}).click();await page.getByText('NOTICE Room 12',{exact:true}).waitFor();
   assert.equal(await page.locator('.extracted-result-list li').count(),1);
  } else if(kind==='audio'){
   await page.getByRole('audio').count();
   await page.waitForFunction(()=>document.querySelector('audio')?.readyState>=1);
   await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-.25)<.03);
  } else if(kind==='video'){
   await page.waitForFunction(()=>document.querySelector('video')?.readyState>=1);
   await page.waitForFunction(()=>Math.abs(document.querySelector('video').currentTime-1)<.1);
   await page.getByRole('button',{name:/Scene descriptions Completed/}).click();await page.getByText('A gray sample frame.',{exact:true}).waitFor();
  }
  await page.screenshot({path:join(artifacts,kind+'.png'),fullPage:true});
  await page.setViewportSize({width:360,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),kind+' mobile overflow');
  assert.deepEqual(errors,[]);await context.close();
 }
 console.log('PASS populated image detection/OCR, audio transcript seek, video detection/frame seek/scene descriptions, hash verification, GPS citations beyond page one, pagination after citation focus, and mobile widths. Extraction outputs are synthetic; media bytes and browser playback are real.');
}finally{await browser?.close();await rm(temporary,{recursive:true,force:true});}
