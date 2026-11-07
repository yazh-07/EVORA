import test from 'node:test';
import assert from 'node:assert/strict';
import { groupFindingViews } from '../.test-build/src/cases/CaseWorkspace.mjs';
const base={id:'r',case_id:'case',analysis_run_id:'run',kind:'relationship',rule:'candidate_link_shared_identifier:v1',summary:'Shared identifier',entity_ids:['n1','n2'],evidence_ids:['e1','e2'],observation_ids:['o1','o2'],confidence:0};
test('same-subject, same-citation detector views fold without losing independently reviewable records',()=>{
 const findings=[{...base,id:'c',kind:'corroboration',rule:'corroboration_reported_claim:v1'},base,{...base,id:'g',kind:'cluster',rule:'cluster_connected_components:v1'}];
 const before=structuredClone(findings),cards=groupFindingViews(findings);
 assert.equal(cards.length,1);assert.equal(cards[0].primary.id,'r');assert.deepEqual(cards[0].related.map(f=>f.id),['c','g']);
 assert.deepEqual(new Set(cards.flatMap(c=>[c.primary,...c.related]).map(f=>f.id)),new Set(['c','r','g']));assert.deepEqual(findings,before);
});
test('different observations, subjects, contradiction evidence and unrelated relationship rules remain separate',()=>{
 for(const delta of [{observation_ids:['other']},{entity_ids:['n3','n4']},{contradicting_evidence_ids:['counter']}]) {
  assert.equal(groupFindingViews([base,{...base,id:'c',kind:'corroboration',rule:'corroboration_reported_claim:v1',...delta}]).length,2);
 }
 assert.equal(groupFindingViews([{...base,rule:'candidate_link_co_mention:v1'},{...base,id:'g',kind:'cluster'}]).length,2);
});
