import assert from 'node:assert/strict';
import test from 'node:test';
import {createApiClient,ApiClientError} from '../.test-build/src/api/client.mjs';
const user={id:'11111111-1111-4111-8111-111111111111',username:'admin',display_name:'Admin',role:'administrator',disabled:false,must_change_password:false};

test('local auth uses same-origin cookies and a CSRF header without exposing a bearer credential',async()=>{
 const calls=[];
 const client=createApiClient({baseUrl:'http://localhost:8000',authMode:'local',fetch:async(url,options)=>{calls.push({url,options});return Response.json({user},{headers:{'X-Evora-User':user.id}});}});
 assert.throws(()=>client.setToken('synthetic'),ApiClientError);
 await client.authRequest('post','/api/v1/auth/login',{body:{username:'admin',password:'local passphrase'}});
 assert.equal(calls[0].options.credentials,'same-origin');assert.equal(calls[0].options.headers['X-Evora-Request'],'1');
 client.activateUser(user);
 await client.request('get','/api/v1/cases',{});
 assert.equal(calls[1].options.headers.get('Authorization'),null);assert.equal(calls[1].options.headers.get('X-Evora-Request'),'1');assert.equal(calls[1].options.credentials,'same-origin');
 assert.doesNotMatch(JSON.stringify(client),/local passphrase/);
 client.clearToken();assert.equal(client.getUser(),null);assert.equal(client.hasToken(),false);
});
test('cross-account cookie replacement clears the workspace before publishing any successful response',async()=>{
 const client=createApiClient({baseUrl:'http://localhost',authMode:'local',fetch:async()=>Response.json({items:['other account data']},{headers:{'X-Evora-User':'other'}})});
 client.activateUser(user);
 await assert.rejects(client.request('get','/api/v1/cases',{}),{kind:'session'});
 assert.equal(client.getUser(),null);assert.equal(client.hasToken(),false);
});
test('logout or session replacement cancels in-flight authenticated reads and discards late data',async()=>{
 let resolve;
 const client=createApiClient({baseUrl:'http://localhost',authMode:'local',fetch:async()=>new Promise(done=>{resolve=done;})});
 client.activateUser(user);
 const read=client.request('get','/api/v1/cases',{});
 client.clearToken();resolve(Response.json({items:[]},{headers:{'X-Evora-User':user.id}}));
 await assert.rejects(read,{kind:'session'});
});
