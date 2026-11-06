// Independent source oracle: no expected graph counts and no production graph imports.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
const sorted = values => [...new Set(values)].sort();
const ids = records => sorted(records.map(item => item.id));
export function uuid5(namespace, name) {
  const bytes = createHash('sha1').update(Buffer.from(namespace.replaceAll('-', ''), 'hex')).update(name).digest().subarray(0, 16);
  bytes[6] = bytes[6] & 15 | 80; bytes[8] = bytes[8] & 63 | 128;
  const hex = bytes.toString('hex'); return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function sourceGroup(item) {
  let locator = item.source_locator.split('; chars=')[0];
  if (/^rows? /.test(locator)) locator = locator.split(', ')[0];
  return [item.evidence_id, item.processing_run_id, locator].join(':');
}
const edgeFacts = edge => JSON.stringify([edge.kind, edge.from_id, edge.to_id, sorted(edge.evidence_ids), sorted(edge.observation_ids)]);

export function verifyGraphLineage({ graph, caseId, evidence, entities, events, observations }) {
  assert.equal(graph.case_id, caseId);
  const evidenceById = new Map(evidence.map(item => [item.id, item]));
  const observationById = new Map(observations.map(item => [item.id, item]));
  assert.equal(observationById.size,observations.length,'no duplicate source observation IDs');
  const entityById = new Map(entities.map(item => [item.id, item]));
  const runs = new Map(), groups = new Map();
  for (const item of observations) {
    assert.equal(item.case_id, caseId); assert.ok(evidenceById.has(item.evidence_id)); assert.ok(item.source_locator.trim());
    if (runs.has(item.evidence_id)) assert.equal(runs.get(item.evidence_id), item.processing_run_id, 'one frozen processing run per source');
    runs.set(item.evidence_id, item.processing_run_id);
    const key = sourceGroup(item); groups.set(key, [...groups.get(key) ?? [], item]);
  }
  const expectedNodes = new Map();
  for (const item of evidence) expectedNodes.set(item.id, { kind: { image:'camera', video:'camera', document:'document' }[item.kind] ?? 'evidence', label:item.filename, evidence_ids:[item.id] });
  for (const item of [...entities, ...events]) {
    assert.equal(item.case_id, caseId);
    const cited = item.observation_ids.map(id => { assert.ok(observationById.has(id), 'source observation exists'); return observationById.get(id); });
    assert.deepEqual(sorted(item.evidence_ids), sorted(cited.map(item => item.evidence_id)), 'source ownership agrees with citations');
    expectedNodes.set(item.id, { kind:item.kind, label:item.canonical_label ?? item.summary, evidence_ids:sorted(item.evidence_ids), observation_ids:sorted(item.observation_ids) });
  }
  for(const entity of entities) assert.ok(entity.observation_ids.some(id=>observationById.get(id).entity_key===entity.candidate_key),'candidate has its own source mention');
  for(const event of events) for(const id of event.entity_ids){
    assert.ok(entityById.has(id),'event participant exists');
    assert.ok(entityById.get(id).observation_ids.some(id=>event.observation_ids.includes(id)),'event participant shares cited source observations');
  }
  const locations = new Map();
  for (const [key, members] of groups) {
    const coords = members.filter(item => ['gps.latitude','gps.longitude'].includes(item.kind));
    if (!coords.length) continue;
    assert.equal(new Set(coords.map(item => item.kind)).size, coords.length, 'coordinate fields are unique within their source row');
    if (coords.length !== 2) continue;
    const latitude = coords.find(item => item.kind === 'gps.latitude').normalized_value;
    const longitude = coords.find(item => item.kind === 'gps.longitude').normalized_value;
    assert.ok(Number.isFinite(Number(latitude)) && Math.abs(Number(latitude)) <= 90);
    assert.ok(Number.isFinite(Number(longitude)) && Math.abs(Number(longitude)) <= 180);
    const id = uuid5(caseId, 'location:' + key);
    expectedNodes.set(id, { kind:'location', label:`${latitude}, ${longitude}`, evidence_ids:[coords[0].evidence_id],
      observation_ids:ids(coords), latitude, longitude });
    locations.set(key, id);
  }
  assert.equal(new Set(graph.nodes.map(item => item.id)).size, graph.nodes.length, 'no duplicate nodes');
  assert.deepEqual(ids(graph.nodes), sorted(expectedNodes.keys()), 'every node is a source record or exact derived coordinate pair');
  for (const item of graph.nodes) {
    const expected = expectedNodes.get(item.id);
    assert.equal(item.case_id, caseId); assert.equal(item.kind, expected.kind); assert.equal(item.label, expected.label);
    assert.deepEqual(sorted(item.evidence_ids), expected.evidence_ids);
    if (expected.observation_ids) assert.deepEqual(sorted(item.properties.observation_ids), expected.observation_ids);
    if (item.kind === 'location') {
      assert.equal(item.properties.latitude, expected.latitude); assert.equal(item.properties.longitude, expected.longitude);
    }
  }
  const expectedEdges = [];
  const add = (kind, from_id, to_id, cited) => {
    if (from_id !== to_id) expectedEdges.push(edgeFacts({ kind, from_id, to_id, evidence_ids:sorted(cited.map(item => item.evidence_id)), observation_ids:ids(cited) }));
  };
  for (let i=0; i<entities.length; i++) for (let j=i+1; j<entities.length; j++) {
    const [a,b] = [entities[i],entities[j]].sort((a,b) => a.id.localeCompare(b.id));
    const cited = sorted([...a.observation_ids, ...b.observation_ids]).map(id => observationById.get(id));
    if (a.candidate_key === b.candidate_key && new Set([...a.evidence_ids,...b.evidence_ids]).size > 1) add('shared_identifier',a.id,b.id,cited);
    if (a.candidate_key !== b.candidate_key) {
      const bodyIds = entity => entity.observation_ids.filter(id => {
        const body = observationById.get(id);
        return body.kind === 'message.body' && !body.entity_key && entity.observation_ids.some(mentionId => {
          const mention=observationById.get(mentionId);
          return mention.kind==='message.device' && mention.entity_key===entity.candidate_key && mention.source_locator.includes('; chars=') && sourceGroup(mention)===sourceGroup(body);
        });
      });
      if (bodyIds(a).some(id => bodyIds(b).includes(id))) add('co_mention',a.id,b.id,cited);
    }
  }
  for (const [key,members] of groups) {
    const roles = kind => members.filter(item => item.kind===kind).flatMap(item => entities.filter(entity =>
      entity.candidate_key===item.entity_key && entity.observation_ids.includes(item.id)).map(entity => ({ entity,item })));
    if (locations.has(key)) for (const source of roles('gps.device')) add('located_at',source.entity.id,locations.get(key),
      [source.item,...members.filter(item => ['gps.latitude','gps.longitude'].includes(item.kind))]);
    const pairs = [['message.sender','message.recipient','communicated_with'],['network.source','network.destination','communicated_with'],['transaction.account','transaction.recipient','transferred_to']];
    if (members.some(item => item.kind==='network.event' && ['connected','sent','received'].includes(item.normalized_value.toLowerCase()))) pairs.push(['network.device','network.ip','assigned_ip']);
    for (const [a,b,kind] of pairs) for (const first of roles(a)) for (const second of roles(b)) add(kind,first.entity.id,second.entity.id,members);
  }
  for (const edge of graph.edges) {
    assert.equal(edge.case_id, caseId); assert.ok(expectedNodes.has(edge.from_id)); assert.ok(expectedNodes.has(edge.to_id));
    assert.ok(edge.observation_ids.length); assert.equal(new Set(edge.observation_ids).size, edge.observation_ids.length);
    const cited = edge.observation_ids.map(id => { assert.ok(observationById.has(id)); return observationById.get(id); });
    assert.deepEqual(sorted(edge.evidence_ids), sorted(cited.map(item => item.evidence_id)));
    for (const id of [edge.from_id,edge.to_id]) if (entityById.has(id)) {
      const entity=entityById.get(id);
      assert.ok(cited.some(item => entity.observation_ids.includes(item.id) && item.entity_key===entity.candidate_key), 'edge cites the endpoint candidate');
    }
  }
  assert.equal(new Set(graph.edges.map(item => item.id)).size, graph.edges.length, 'no duplicate edge IDs');
  assert.deepEqual(graph.edges.map(edgeFacts).sort(), [...new Set(expectedEdges)].sort(), 'all and only source-justified candidate/semantic relationships; no provenance-only edges');
}
