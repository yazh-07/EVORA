import { test } from 'node:test';
import assert from 'node:assert/strict';
import { verifyGraphLineage, uuid5 } from './graph-lineage.mjs';
const id=n=>`00000000-0000-4000-8000-${n.toString(16).padStart(12,'0')}`;
function fixture(){
  const caseId=id(1),gps=id(2),network=id(3),gpsRun=id(4),networkRun=id(5);
  const evidence=[{id:gps,case_id:caseId,kind:'gps',filename:'gps.csv'},{id:network,case_id:caseId,kind:'network_log',filename:'network.csv'}];
  const source=(n,evidence_id,processing_run_id,kind,normalized_value,entity_key)=>({id:id(n),case_id:caseId,evidence_id,processing_run_id,kind,normalized_value,source_locator:'row 2, '+kind,...entity_key?{entity_key}:{}});
  const observations=[source(10,gps,gpsRun,'gps.device','D-8','device:D-8'),source(11,gps,gpsRun,'gps.latitude','12.5'),source(12,gps,gpsRun,'gps.longitude','77.2'),
    source(13,network,networkRun,'network.device','D-7','device:D-7'),source(14,network,networkRun,'network.ip','203.0.113.7','ip:203.0.113.7'),source(15,network,networkRun,'network.event','connected')];
  const entity=(n,o,kind,label,key)=>({id:id(n),case_id:caseId,kind,canonical_label:label,candidate_key:key,evidence_ids:[o.evidence_id],observation_ids:[o.id]});
  const entities=[entity(20,observations[0],'device','D-8','device:D-8'),entity(21,observations[3],'device','D-7','device:D-7'),entity(22,observations[4],'ip','203.0.113.7','ip:203.0.113.7')];
  const location=uuid5(caseId,`location:${gps}:${gpsRun}:row 2`);
  const nodes=[...evidence.map(item=>({...item,kind:'evidence',label:item.filename,evidence_ids:[item.id],properties:{}})),
    ...entities.map(item=>({...item,label:item.canonical_label,properties:{observation_ids:item.observation_ids}})),
    {id:location,case_id:caseId,kind:'location',label:'12.5, 77.2',evidence_ids:[gps],properties:{latitude:'12.5',longitude:'77.2',observation_ids:[id(11),id(12)]}}];
  const edges=[{id:id(30),case_id:caseId,kind:'located_at',from_id:id(20),to_id:location,evidence_ids:[gps],observation_ids:[id(10),id(11),id(12)]},
    {id:id(31),case_id:caseId,kind:'assigned_ip',from_id:id(21),to_id:id(22),evidence_ids:[network],observation_ids:[id(13),id(14),id(15)]}];
  return {caseId,evidence,observations,entities,events:[],graph:{case_id:caseId,nodes,edges}};
}
test('graph oracle accepts source-backed GPS locations and network assignments',()=>verifyGraphLineage(fixture()));
test('graph oracle rejects missing assignments, forged nodes and source/row mismatches',()=>{
  const mutations=[
    value=>value.graph.edges.pop(),
    value=>value.graph.nodes.push({...value.graph.nodes.at(-1),id:id(99)}),
    value=>{value.graph.nodes.at(-1).properties.longitude='78.0';},
    value=>{value.observations[2].processing_run_id=id(98);},
    value=>{value.graph.edges[1].to_id=id(20);},
    value=>{value.graph.edges[1].evidence_ids=[id(2)];},
    value=>{value.graph.edges[1].observation_ids.push(id(99));},
    value=>value.graph.edges.push({id:id(32),case_id:value.caseId,kind:'referenced_in',from_id:id(20),to_id:id(2),evidence_ids:[id(2)],observation_ids:[id(10)]}),
  ];
  for(const mutate of mutations){const value=fixture();mutate(value);assert.throws(()=>verifyGraphLineage(value),undefined,mutate.toString());}
});
