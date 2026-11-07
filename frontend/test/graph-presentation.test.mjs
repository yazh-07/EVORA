import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { compactGraph, GraphPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const caseId=id(1),runId=id(2);
const node=(n,kind,label,key,source=id(100))=>({id:id(n),case_id:caseId,kind,label,evidence_ids:[source],properties:{...(key?{candidate_key:key}:{}),observation_ids:[id(n+500)]}});
function fixture(){
 const nodes=[node(10,'device','D-101','device:D-101'),node(11,'device','D-101','device:D-101',id(101)),node(12,'ip','203.0.113.44','ip:203.0.113.44'),
  node(13,'location','12.5, 77.5'),node(14,'location','12.5, 77.5'),node(15,'visual_candidate','Unverified region','visual_candidate:source:frame-0:visual_candidate-0'),
  node(16,'vehicle','Legacy detector region','vehicle:source:frame-0:vehicle-0'),node(17,'visual.detected','Unverified event'),node(18,'network.activity','Connected'),
  node(19,'date','2026-11-05'),node(20,'organization','UTC','organization:UTC'),node(21,'camera','image.png')];
 for(const n of nodes.filter(n=>[id(13),id(14)].includes(n.id)))Object.assign(n.properties,{latitude:'12.5',longitude:'77.5'});
 nodes.at(-1).properties.filename='image.png';
 const edge=(n,from,to,kind)=>({id:id(n),case_id:caseId,from_id:id(from),to_id:id(to),kind,evidence_ids:[id(100)],observation_ids:[id(700+n)],confidence:0});
 return {case_id:caseId,analysis_run_id:runId,nodes,edges:[edge(30,10,11,'shared_identifier'),edge(31,11,12,'assigned_ip'),edge(32,10,13,'located_at'),edge(33,11,14,'located_at')]};
}
test('compact graph groups exact identifiers and coordinates and preserves all semantic edge IDs and citations',()=>{
 const raw=fixture(),before=structuredClone(raw),view=compactGraph(raw);
 assert.equal(view.nodes.length,3);assert.deepEqual(view.edges.map(e=>e.id),raw.edges.filter(e=>e.kind!=='shared_identifier').map(e=>e.id));
 const device=view.nodes.find(n=>n.kind==='device');assert.deepEqual(device.properties.source_node_ids,[id(10),id(11)]);
 assert.deepEqual(device.evidence_ids,[id(100),id(101)]);
 assert.deepEqual(device.properties.observation_ids,[id(510),id(511)]);
 for(const edge of view.edges){const original=raw.edges.find(e=>e.id===edge.id);assert.deepEqual(edge.observation_ids,original.observation_ids);assert.deepEqual(edge.evidence_ids,original.evidence_ids);}
 assert.ok(view.edges.every(e=>view.nodes.some(n=>n.id===e.from_id)&&view.nodes.some(n=>n.id===e.to_id)));
 assert.deepEqual(raw,before);assert.equal(compactGraph(raw),view,'stable presentation identity');
});
test('the default view hides detector noise and the full source view retains every raw node',()=>{
 const graph=fixture();const state={status:'ready',graph,selection:null,citations:[],citationStatus:'idle',message:'',citationMessage:''};
 const render=view=>renderToStaticMarkup(createElement(GraphPanel,{state,load:async()=>{},select:async()=>{},...(view?{view}:{})}));
 const compact=render();assert.match(compact,/Show all source records/);assert.doesNotMatch(compact,/Legacy detector region|Unverified region/);
 const raw=render({filter:'All',query:'',zoom:1,compact:false});assert.match(raw,/Legacy detector region/);assert.match(raw,/Unverified region/);
 assert.equal((raw.match(/data-node-id=/g)||[]).length,graph.nodes.length);
});
test('matching labels across different namespaces remain separate; grouping never asserts identity',()=>{
 const raw={...fixture(),nodes:[node(40,'person','Alex Smith','person:Alex Smith'),node(41,'organization','Alex Smith','organization:Alex Smith')],edges:[]};
 assert.equal(compactGraph(raw).nodes.length,2);
});

test('image-only graphs retain an accessible route to raw records when grouped view has no subjects',()=>{
 const original=fixture();const graph={...original,nodes:original.nodes.filter(n=>['camera','visual_candidate','visual.detected'].includes(n.kind)),edges:[]};
 const html=renderToStaticMarkup(createElement(GraphPanel,{state:{status:'ready',graph,selection:null,citations:[],citationStatus:'idle',message:'',citationMessage:''},load:async()=>{},select:async()=>{}}));
 assert.match(html,/Show all source records/);assert.match(html,/No grouped subjects in this view/);
 assert.doesNotMatch(html,/No graph nodes in this completed analysis/);
});
