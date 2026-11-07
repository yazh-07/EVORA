import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createActivityStore, ActivityEntryPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';
const caseId='11111111-1111-4111-8111-111111111111', evidenceId='22222222-2222-4222-8222-222222222222';
const item={id:evidenceId,case_id:caseId,filename:'queued-demo.txt',source_label:'Queued demo',kind:'document',sha256:'a'.repeat(64),size_bytes:1,media_type:'text/plain',created_at:'2026-11-05T00:00:00Z'};
const completed={id:'33333333-3333-4333-8333-333333333333',case_id:caseId,evidence_id:evidenceId,status:'completed',processor_version:'fixture/1',created_at:item.created_at,finished_at:item.created_at};
function fixture(){
 let resolvePost,startedPost;const post=new Promise(resolve=>resolvePost=resolve),started=new Promise(resolve=>startedPost=resolve);
 const sessions=new Set();let writes=0;
 const client={getSessionVersion:()=>0,hasToken:()=>true,getUser:()=>({role:'investigator'}),subscribeSession(listener){sessions.add(listener);return()=>sessions.delete(listener);},async request(method,route,options){
  if(method==='post'){writes++;startedPost();return post;}
  if(route.endsWith('/evidence'))return {items:[item],total:1,limit:100,offset:0};
  if(route.endsWith('/processing-runs'))return [];
  throw Error('Unexpected route');
 }};
 return{store:createActivityStore(client),started,resolvePost,sessions,writes:()=>writes};
}

test('activity owns a batch across view unsubscribe and case navigation; same case reuses controller and shows current filename',async()=>{
 const f=fixture();f.store.start();const controller=f.store.getBatch(caseId,'Harborlight demo');
 const off=controller.subscribe(()=>{});const pending=controller.submit();await f.started;off();
 f.store.getBatch('44444444-4444-4444-8444-444444444444','Another case');
 assert.equal(f.store.getBatch(caseId),controller);
 const entry=f.store.getSnapshot()[0];assert.equal(entry.title,'Harborlight demo');assert.equal(entry.state.status,'running');
 assert.equal(f.writes(),1);
 const html=renderToStaticMarkup(createElement(ActivityEntryPanel,{entry,stop:()=>f.store.stop(caseId)}));
 assert.match(html,/queued-demo.txt/);assert.match(html,/Stop queue/);assert.match(html,/Harborlight demo progress/);
 f.resolvePost(completed);await pending;assert.equal(f.store.getSnapshot()[0].state.status,'done');f.store.dispose();
});

test('header stop targets its case queue and a late accepted server result cannot restart it',async()=>{
 const f=fixture();f.store.start();const batch=f.store.getBatch(caseId);const pending=batch.submit();await f.started;
 f.store.stop(caseId);assert.equal(f.store.getSnapshot()[0].state.status,'stopped');
 const html=renderToStaticMarkup(createElement(ActivityEntryPanel,{entry:f.store.getSnapshot()[0],stop:()=>{}}));
 assert.match(html,/server/);assert.doesNotMatch(html,/>Stop queue</);
 f.resolvePost(completed);await pending;assert.equal(f.store.getSnapshot()[0].state.status,'stopped');assert.equal(f.writes(),1);f.store.dispose();
});

test('session-scope disposal clears activity, detaches session listeners and ignores late results; StrictMode setup can restart',async()=>{
 const f=fixture();f.store.start();const batch=f.store.getBatch(caseId);const pending=batch.submit();await f.started;
 assert.equal(f.sessions.size,1);f.store.dispose();assert.equal(f.sessions.size,0);assert.deepEqual(f.store.getSnapshot(),[]);
 f.resolvePost(completed);await pending;assert.deepEqual(f.store.getSnapshot(),[]);
 f.store.start();assert.equal(f.sessions.size,1);assert.equal(f.store.getBatch(caseId),batch);f.store.dispose();
});
