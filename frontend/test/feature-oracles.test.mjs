import {test} from 'node:test';
import assert from 'node:assert/strict';
import {verifyTriagePolicy} from './triage-policy-oracle.mjs';
import {verifyFindingLineage} from './finding-lineage-oracle.mjs';
function triage(){
 const values={relevance:.2,connectivity:0,gap_relevance:0,conflict_relevance:0,temporal_proximity:1};
 const raw={relevance:.25,connectivity:.2,gap_relevance:.15,conflict_relevance:.1,temporal_proximity:.05};
 return {values,result:{score:13.34,priority:'P4',factors:Object.entries(values).map(([name,value])=>({name,value,weight:raw[name]/.75,contribution:name==='relevance'||name==='temporal_proximity'?6.67:0,explanation:'source-based fixture',evidence_ids:['source']}))}};
}
test('triage oracle retains evaluated zero factors and normalizes the documented available weights',()=>{const {result,values}=triage();assert.deepEqual(verifyTriagePolicy(result,values),{score:13.34,priority:'P4'});});
test('triage oracle rejects missing evaluated negatives, changed values, weights, scores and priorities',()=>{
 for(const mutate of [r=>r.factors.splice(1,1),r=>{r.factors[0].value=.3;},r=>{r.factors[0].weight=.5;},r=>{r.score=11.11;},r=>{r.priority='P3';}]){
  const {result,values}=triage();mutate(result);assert.throws(()=>verifyTriagePolicy(result,values));
 }
});
function findings(){
 const entities=[{id:'d1',candidate_key:'device:D-1',evidence_ids:['e1'],observation_ids:['o1']},{id:'p1',candidate_key:'ip:203.0.113.1',evidence_ids:['e1'],observation_ids:['o2']},
 {id:'d2',candidate_key:'device:D-1',evidence_ids:['e2'],observation_ids:['o3']},{id:'p2',candidate_key:'ip:203.0.113.1',evidence_ids:['e2'],observation_ids:['o4']}];
 const edges=[{kind:'assigned_ip',from_id:'d1',to_id:'p1',evidence_ids:['e1'],observation_ids:['o1','o2','o5']},
 {kind:'assigned_ip',from_id:'d2',to_id:'p2',evidence_ids:['e2'],observation_ids:['o3','o4','o6']},
 {kind:'shared_identifier',from_id:'d1',to_id:'d2',evidence_ids:['e1','e2'],observation_ids:['o1','o3']},
 {kind:'shared_identifier',from_id:'p1',to_id:'p2',evidence_ids:['e1','e2'],observation_ids:['o2','o4']}];
 const make=(kind,rule,entity_ids,evidence_ids,observation_ids)=>({id:entity_ids.join(':')+kind,kind,rule,entity_ids,evidence_ids,observation_ids,case_id:'case',analysis_run_id:'run',confidence:0,missing_information:['Underlying source independence is unverified.']});
 return {entities,events:[],graph:{case_id:'case',analysis_run_id:'run',edges},findings:[
 make('relationship','candidate_link_shared_identifier:v1',['d1','d2'],['e1','e2'],['o1','o3']),
 make('relationship','candidate_link_shared_identifier:v1',['p1','p2'],['e1','e2'],['o2','o4']),
 make('cluster','cluster_connected_components:v1',['d1','p1','d2','p2'],['e1','e2'],['o1','o2','o3','o4','o5','o6']),
 make('corroboration','corroboration_reported_claim:v1',['d1','d2'],['e1','e2'],['o1','o3']),
 make('corroboration','corroboration_reported_claim:v1',['p1','p2'],['e1','e2'],['o2','o4'])]};
}
test('finding oracle verifies exact relationships, connected entity components and unverified matching claims',()=>verifyFindingLineage(findings()));
test('finding oracle rejects omitted, fabricated or misattributed findings and false source-independence claims',()=>{
 for(const mutate of [v=>v.findings.pop(),v=>v.findings.push({...v.findings[0],id:'extra'}),v=>v.findings[0].observation_ids.push('foreign'),v=>{v.findings[0].evidence_ids=['wrong'];},v=>{v.findings.at(-1).missing_information=[];}]){
  const value=findings();mutate(value);assert.throws(()=>verifyFindingLineage(value));
 }
});
