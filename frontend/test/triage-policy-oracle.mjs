// Independent fixture expectations for the documented g02-triage-v1 weights.
import assert from 'node:assert/strict';
const weights={relevance:25,connectivity:20,corroboration:15,gap_relevance:15,source_quality:10,conflict_relevance:10,temporal_proximity:5};
export function verifyTriagePolicy(result,expectedValues){
 const names=Object.keys(weights).filter(name=>name in expectedValues);
 assert.deepEqual(result.factors.map(item=>item.name),names,'evaluated zero factors remain present; unknown factors stay absent');
 const denominator=names.reduce((total,name)=>total+weights[name],0);
 let score=0;
 for(const factor of result.factors){
  const weight=weights[factor.name]/denominator;
  const contribution=Number((expectedValues[factor.name]*weight*100).toFixed(2));
  assert.equal(factor.value,expectedValues[factor.name]);
  assert.ok(Math.abs(factor.weight-weight)<=2*Number.EPSILON,`normalized weight ${factor.name}: ${factor.weight} versus ${weight}`);
  assert.equal(factor.contribution,contribution);
  assert.ok(factor.explanation.length);assert.ok(factor.evidence_ids.length);score+=contribution;
 }
 score=Math.min(100,Number(score.toFixed(2)));
 const priority=score>=80?'P1':score>=60?'P2':score>=40?'P3':'P4';
 assert.equal(result.score,score);assert.equal(result.priority,priority);
 return {score,priority};
}
