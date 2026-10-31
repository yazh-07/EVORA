import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createOriginalDownload, saveOriginal } from '../.test-build/src/cases/downloadController.mjs';

// Explicit Fetch/save/DOM doubles; real F05 HTTP acceptance is in cases.integration.mjs.
const bytes = new Uint8Array([0, 255, 10, 65]);
const item = { id:'00000000-0000-4000-8000-000000000003', case_id:'11111111-1111-4111-8111-111111111111', filename:'synthetic.bin', size_bytes:bytes.length, sha256:createHash('sha256').update(bytes).digest('hex') };
const response = (data=bytes) => new Response(data,{headers:{'Content-Type':'application/octet-stream'}});
const deferred = () => { let resolve; const promise=new Promise(r=>{resolve=r;}); return {promise,resolve}; };
function setup(fetch, metadata=item, save=()=>()=>{}) {
 const client=createApiClient({baseUrl:'http://127.0.0.1:8000',fetch});client.setToken('synthetic-download-token');
 return {client, download:createOriginalDownload(client,metadata,save)};
}
test('authorized explicit original read verifies bytes/hash/size before saving',async()=>{
 let saved=0,released=0;
 const {download}=setup(async(url,options)=>{assert.ok(String(url).endsWith(`/cases/${item.case_id}/evidence/${item.id}/content`));assert.equal(options.headers.get('Authorization'),'Bearer synthetic-download-token');assert.equal(options.cache,'no-store');return response();},item,(blob,name)=>{assert.equal(blob.size,4);assert.equal(name,item.filename);saved++;return ()=>{released++;};});
 assert.equal(download.getSnapshot().status,'idle');await download.download();assert.equal(saved,1);assert.equal(download.getSnapshot().status,'ready');assert.match(download.getSnapshot().message,/download requested/);download.dispose();assert.equal(released,1);
});
test('empty original is verified and downloadable',async()=>{
 let saved=0;const {download}=setup(async()=>response(new Uint8Array()),{...item,size_bytes:0,sha256:createHash('sha256').update('').digest('hex')},()=>{saved++;return ()=>{};});await download.download();assert.equal(saved,1);download.dispose();
});
test('wrong size or SHA-256 stops the browser save',async()=>{
 for(const metadata of [{...item,size_bytes:5},{...item,sha256:'0'.repeat(64)}]){
 let saved=0;const {download}=setup(async()=>response(),metadata,()=>{saved++;return ()=>{};});await download.download();assert.equal(saved,0);assert.equal(download.getSnapshot().status,'error');assert.match(download.getSnapshot().message,/Download stopped/);download.dispose();}
});
test('missing/foreign, server, protocol and network errors are safe and retryable',async()=>{
 for(const kind of ['404','500','protocol','network']){
 let calls=0,saves=0;const {download}=setup(async()=>{calls++;if(calls>1)return response();if(kind==='network')throw Error('private');if(kind==='protocol')return Response.json({secret:'private'});return Response.json({code:'ERROR',message:'private'}, {status:Number(kind)});},item,()=>{saves++;return ()=>{};});await download.download();assert.equal(saves,0);assert.equal(download.getSnapshot().status,'error');assert.doesNotMatch(download.getSnapshot().message,/private/);await download.download();assert.equal(saves,1);assert.equal(calls,2);download.dispose();}
});
test('busy prevents duplicate reads; selection disposal and session changes discard late bytes',async()=>{
 for(const action of ['dispose','logout','replace']){
 const wait=deferred();let calls=0,saves=0;const {client,download}=setup(async()=>{calls++;return wait.promise;},item,()=>{saves++;return ()=>{};});const pending=download.download();assert.equal(download.getSnapshot().status,'loading');await download.download();assert.equal(calls,1);
 if(action==='dispose')download.dispose();else if(action==='logout')client.clearToken();else client.setToken('replacement-token');wait.resolve(response());await pending;assert.equal(saves,0);download.dispose();}
});
test('401 clears the session without saving; effect reconnect discards aborted old response',async()=>{
 const denied=setup(async()=>Response.json({}, {status:401}));await denied.download.download();assert.equal(denied.client.hasToken(),false);denied.download.dispose();
 const wait=deferred();let calls=0,saves=0;const {download}=setup(async()=>++calls===1?wait.promise:response(),item,()=>{saves++;return ()=>{};});download.start();const old=download.download();download.dispose();download.start();await download.download();wait.resolve(response());await old;assert.equal(saves,1);download.dispose();
});
test('browser save uses a temporary URL, sanitizes filename and cleans once on failure/disposal',()=>{
 const originalDocument=globalThis.document,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
 let revoked=0,removed=0,clicked=0,fail=false;const link={remove(){removed++;},click(){clicked++;if(fail)throw Error('save blocked');}};
 globalThis.document={body:{append(){}},createElement(){return link;}};URL.createObjectURL=()=> 'blob:synthetic';URL.revokeObjectURL=url=>{assert.equal(url,'blob:synthetic');revoked++;};
 try{const release=saveOriginal(new Blob([bytes]),'../unsafe:name.bin');assert.equal(link.download,'.._unsafe_name.bin');assert.equal(clicked,1);assert.equal(removed,1);release();release();assert.equal(revoked,1);fail=true;assert.throws(()=>saveOriginal(new Blob(),'a.bin'));assert.equal(revoked,2);assert.equal(removed,2);}finally{globalThis.document=originalDocument;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
});
