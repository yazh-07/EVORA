import assert from 'node:assert/strict';
const sorted=values=>[...new Set(values)].sort();
const facts=item=>JSON.stringify([item.kind,item.rule,sorted(item.entity_ids??[]),sorted(item.evidence_ids),sorted(item.observation_ids)]);
export function verifyFindingLineage({graph,findings,entities,events}){
 const expected=[],entityIds=new Set(entities.map(item=>item.id));
 for(const edge of graph.edges)if(['shared_identifier','co_mention'].includes(edge.kind))expected.push(facts({...edge,kind:'relationship',rule:`candidate_link_${edge.kind}:v1`,entity_ids:[edge.from_id,edge.to_id]}));
 const adjacent=new Map();
 for(const edge of graph.edges)if(entityIds.has(edge.from_id)&&entityIds.has(edge.to_id)){
  for(const [a,b] of [[edge.from_id,edge.to_id],[edge.to_id,edge.from_id]])adjacent.set(a,new Set([...(adjacent.get(a)??[]),b]));
 }
 const seen=new Set();
 for(const id of adjacent.keys())if(!seen.has(id)){
  const pending=[id],members=new Set();while(pending.length){const next=pending.pop();if(members.has(next))continue;members.add(next);pending.push(...adjacent.get(next));}
  for(const id of members)seen.add(id);
  const edges=graph.edges.filter(edge=>members.has(edge.from_id)&&members.has(edge.to_id));
  expected.push(facts({kind:'cluster',rule:'cluster_connected_components:v1',entity_ids:members,evidence_ids:edges.flatMap(edge=>edge.evidence_ids),observation_ids:edges.flatMap(edge=>edge.observation_ids)}));
 }
 const byId=new Map(entities.map(item=>[item.id,item])),claims=new Map();
 const add=(key,item)=>claims.set(key,[...(claims.get(key)??[]),item]);
 for(const item of entities)add(JSON.stringify(['identifier',item.candidate_key]),item);
 for(const item of events)if(item.observed_at_utc)add(JSON.stringify(['event',item.kind,item.summary,sorted(item.entity_ids.map(id=>byId.get(id).candidate_key)),new Date(item.observed_at_utc).toISOString()]),item);
 for(const members of claims.values())if(new Set(members.flatMap(item=>item.evidence_ids)).size>1){
  expected.push(facts({kind:'corroboration',rule:'corroboration_reported_claim:v1',entity_ids:members.filter(item=>entityIds.has(item.id)).map(item=>item.id),evidence_ids:members.flatMap(item=>item.evidence_ids),observation_ids:members.flatMap(item=>item.observation_ids)}));
 }
 for(const item of findings){
  assert.equal(item.case_id,graph.case_id);assert.equal(item.analysis_run_id,graph.analysis_run_id);assert.equal(item.confidence,0);
  if(item.kind==='corroboration')assert.ok(item.missing_information.includes('Underlying source independence is unverified.'),'matching reports do not establish independent origins');
 }
 assert.equal(new Set(findings.map(item=>item.id)).size,findings.length);
 assert.deepEqual(findings.map(facts).sort(),expected.sort(),'exact candidate links, source-backed entity components and repeated source claims');
}
