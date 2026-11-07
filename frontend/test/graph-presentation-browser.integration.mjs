// Synthetic view fixture: mode transitions must replace physics before drawing new nodes.
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
const {chromium}=await import(process.env.EVORA_PLAYWRIGHT_MODULE??'playwright');
const frontend=fileURLToPath(new URL('..',import.meta.url));
const temporary=await mkdtemp(join(tmpdir(),'evora-graph-presentation-'));
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const source=(n,kind,filename)=>({id:id(n),case_id:id(1),kind:kind==='image'?'camera':'evidence',label:filename,evidence_ids:[id(n)],properties:{filename,kind}});
const entity=(n,kind,label,key,source)=>({id:id(n),case_id:id(1),kind,label,evidence_ids:[id(source)],properties:{candidate_key:key,observation_ids:[id(500+n)]}});
const graph={case_id:id(1),analysis_run_id:id(2),nodes:[source(100,'network_log','network.csv'),source(101,'document','report.txt'),source(102,'image','image.png'),entity(10,'device','D-7','device:D-7',100),entity(11,'device','D-7','device:D-7',101),entity(12,'ip','203.0.113.7','ip:203.0.113.7',100),entity(16,'visual_candidate','Unverified region','visual_candidate:source:frame-0:visual_candidate-0',102),entity(17,'visual.detected','Unverified detection event',undefined,102)],edges:[{id:id(30),case_id:id(1),kind:'shared_identifier',from_id:id(10),to_id:id(11),evidence_ids:[id(100),id(101)],observation_ids:[id(510),id(511)],confidence:0},{id:id(31),case_id:id(1),kind:'assigned_ip',from_id:id(10),to_id:id(12),evidence_ids:[id(100)],observation_ids:[id(510),id(512)],confidence:0}]};
let browser;
try{
 await build({stdin:{contents:`import React,{useState} from 'react';import{createRoot}from'react-dom/client';import{GraphPanel}from ${JSON.stringify(join(frontend,'src/cases/GraphView.tsx'))};const graph=${JSON.stringify(graph)};function Preview(){const[view,setView]=useState({filter:'All',query:'',zoom:1,compact:true});return <GraphPanel state={{graph,status:'ready',selection:null,citations:[],citationStatus:'idle',message:'',citationMessage:''}} view={view} onViewChange={setView} load={async()=>{}} select={async()=>{}}/>}createRoot(document.getElementById('root')).render(<Preview/>);`,resolveDir:frontend,loader:'tsx'},outfile:join(temporary,'preview.js'),bundle:true,format:'iife',platform:'browser',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
 browser=await chromium.launch({executablePath:process.env.EVORA_CHROME_PATH,headless:true,args:['--no-sandbox']});
 for(const reducedMotion of ['reduce','no-preference']){
  const context=await browser.newContext({viewport:{width:1365,height:950},reducedMotion});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="root"></div>');await page.addStyleTag({path:join(frontend,'dist/assets/main.css')});await page.addScriptTag({path:join(temporary,'preview.js')});
  for(let i=0;i<3;i++){
   await page.getByRole('button',{name:'Show all source records',exact:true}).waitFor();assert.equal(await page.locator('.graph-node').count(),2);assert.equal(await page.locator('.graph-edge[data-kind="assigned_ip"]').count(),1);
   await page.getByRole('button',{name:'Show all source records',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.graph-node').length===8);assert.equal(await page.locator('.graph-edge').count(),2);
   await page.getByRole('button',{name:'Group identifiers and hide raw candidates',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.graph-node').length===2);
  }
  assert.deepEqual(errors,[]);await context.close();
 }
 console.log('PASS graph view browser: repeated grouped/raw transitions, preserved semantic edge, full raw records, reduced/normal motion and no stale-physics errors.');
}finally{await browser?.close();await rm(temporary,{recursive:true,force:true});}
