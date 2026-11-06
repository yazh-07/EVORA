import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { verifyGraphLineage } from './graph-lineage.mjs';
import { verifyTriagePolicy } from './triage-policy-oracle.mjs';
import { verifyFindingLineage } from './finding-lineage-oracle.mjs';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Real loopback HTTP/FastAPI/SQLite, registered parsers, analysis and scoring.
// The shared server uses an explicit transactional Neo4j double. No browser or
// live Neo4j acceptance is claimed here. Only committed synthetic CSVs are used.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
// Rebuild before importing so the direct node command also works on a clean
// checkout with installed dependencies, without npm test or a UI build first.
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const { createTriageController, PriorityListPanel } = await import('../.test-build/src/cases/CaseWorkspace.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i02-'));
const database = join(temporary, 'cases.sqlite3');
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', database], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
// Attach all listeners immediately: startup errors/exits must reject promptly,
// and cleanup must also handle spawn failures without waiting for a missing exit.
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I02 server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I02 server exited (${code ?? signal}): ${diagnostics}`));
  });
});
const closed = new Promise(resolve => child.once('close', resolve));

async function until(read, done, label) {
  const deadline = Date.now() + 15000;
  let value;
  do {
    value = await read();
    if (done(value)) return value;
    await delay(25);
  } while (Date.now() < deadline);
  assert.fail(`${label} timed out: ${JSON.stringify(value)}; ${diagnostics}`);
}
const sorted = values => [...values].sort();
const factor = (result, name) => {
  const matches = result.factors.filter(item => item.name === name);
  assert.equal(matches.length, 1, `exactly one ${name} factor`);
  return matches[0];
};
// Harness-only read-back compares raw stored strings, not parsed/re-serialized
// outputs. All application operations and source reads still go through HTTP.
const storedRun = runId => execFileSync(python, ['-c', `
import json, pathlib, sqlite3, sys
with sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri() + '?mode=ro', uri=True) as connection:
    connection.row_factory = sqlite3.Row
    records = [dict(connection.execute('SELECT * FROM ' + table + ' WHERE ' + key + '=?',
                                      (sys.argv[2],)).fetchone())
               for table, key in [('analysis_runs', 'id'), ('analysis_outputs', 'run_id')]]
print(json.dumps(records, sort_keys=True))
`, database, runId], { encoding: 'utf8', timeout: 15000 });

try {
  const origin = await originReady;
  // The socket is announced before uvicorn starts accepting requests.
  await until(async () => {
    try { return (await fetch(origin + '/api/v1/cases', {
      headers: { Authorization: 'Bearer u02-synthetic-one' }, signal: AbortSignal.timeout(1000),
    })).status; }
    catch { return null; }
  }, status => status === 200, 'API readiness');
  const client = createApiClient({ baseUrl: origin, fetch: (url, options) =>
    fetch(url, { ...options, signal: AbortSignal.any([options.signal, AbortSignal.timeout(5000)]) }) });
  client.setToken('u02-synthetic-one');
  const investigation = await client.request('post', '/api/v1/cases', {
    body: { title: 'Synthetic I02 adaptive tracer', description: 'Committed network/GPS/message fixtures only' },
  });
  const caseId = investigation.id;
  const get = (route, query, path = {}) => client.request('get', `/api/v1/cases/{caseId}${route}`, {
    path: { caseId, ...path }, query,
  });
  const post = (route, options) => client.request('post', `/api/v1/cases/{caseId}${route}`, {
    ...options, path: { caseId, ...options.path },
  });
  const sources = [];
  async function uploadAndProcess(filename, kind) {
    const bytes = await readFile(new URL(`../../fixtures/synthetic-case/${filename}`, import.meta.url));
    const body = new FormData();
    body.set('file', new File([bytes], filename, { type: 'text/csv' }));
    body.set('kind', kind); body.set('source_label', `Synthetic I02 ${filename}`);
    const evidence = await post('/evidence', { body });
    assert.equal(evidence.sha256, createHash('sha256').update(bytes).digest('hex'));
    assert.equal(evidence.size_bytes, bytes.length);
    const path = { evidenceId: evidence.id };
    const accepted = await post('/evidence/{evidenceId}/processing-runs', {
      path, header: { 'Idempotency-Key': randomUUID() },
    });
    const processing = await until(() => get('/evidence/{evidenceId}/processing-runs/{runId}', undefined,
      { ...path, runId: accepted.id }), run => ['completed', 'failed'].includes(run.status), `${filename} processing`);
    assert.equal(processing.status, 'completed', JSON.stringify(processing));
    assert.equal(processing.evidence_id, evidence.id);
    const observations = await get('/observations', { processing_run_id: processing.id, limit: 100, offset: 0 });
    assert.equal(observations.items.length, observations.total, 'complete fixture observation page');
    assert.ok(observations.total > 0);
    for (const observation of observations.items) {
      assert.equal(observation.case_id, caseId);
      assert.equal(observation.evidence_id, evidence.id);
      assert.equal(observation.processing_run_id, processing.id);
      assert.ok(observation.source_locator.length > 0);
    }
    const own=new Set(observations.items.map(item=>item.id));
    const source = { evidence, processing, observations: observations.items, bytes,
      entities:(await get('/entities',{limit:100})).items.filter(item=>item.observation_ids.every(id=>own.has(id))),
      events:(await get('/events',{limit:100})).items.filter(item=>item.observation_ids.every(id=>own.has(id))) };
    sources.push(source);
    return source;
  }
  async function start(key) {
    const accepted = await post('/analysis-runs', { header: { 'Idempotency-Key': key } });
    const run = await until(() => get('/analysis-runs/{runId}', undefined, { runId: accepted.id }),
      run => ['completed', 'failed'].includes(run.status), 'analysis completion');
    assert.equal(run.status, 'completed', JSON.stringify(run));
    return run;
  }
  function checkSnapshot(run) {
    const snapshot = run.input_snapshot;
    const manifest = {
      case_id: caseId,
      evidence_ids: sorted(sources.map(source => source.evidence.id)),
      observation_ids: sorted(sources.flatMap(source => source.observations.map(item => item.id))),
      processing_run_ids: sorted(sources.map(source => source.processing.id)),
    };
    assert.deepEqual(snapshot, { ...manifest,
      sha256: createHash('sha256').update(JSON.stringify(manifest)).digest('hex') });
    assert.equal(run.algorithm_version,
      'evora-analysis/3;source_semantic_relations/2;candidate_link_shared_identifier:v1;candidate_link_co_mention:v1;g02-triage-v1;multi-modal-detectors/1');
  }
  async function outputs(run) {
    const query = { analysis_run_id: run.id };
    const [graph, findings, triage] = await Promise.all([
      get('/graph', query), get('/findings', query), get('/triage', query),
    ]);
    for (const output of [graph, findings, triage]) assert.equal(output.analysis_run_id, run.id);
    assert.equal(findings.items.length, findings.total);
    assert.equal(triage.items.length, triage.total);
    assert.deepEqual(sorted(triage.items.map(item => item.evidence_id)), run.input_snapshot.evidence_ids);
    const frozen=sources.filter(item=>run.input_snapshot.processing_run_ids.includes(item.processing.id));
    verifyGraphLineage({graph,caseId,evidence:frozen.map(item=>item.evidence),entities:frozen.flatMap(item=>item.entities),events:frozen.flatMap(item=>item.events),observations:frozen.flatMap(item=>item.observations)});
    verifyFindingLineage({graph,findings:findings.items,entities:frozen.flatMap(item=>item.entities),events:frozen.flatMap(item=>item.events)});
    return { graph, findings, triage };
  }
  const resultFor = (output, source) => {
    const entry = output.triage.items.find(item => item.evidence_id === source.evidence.id);
    assert.ok(entry?.latest_result, 'processed evidence has a computed result');
    assert.equal(entry.effective_priority, entry.latest_result.priority);
    return entry.latest_result;
  };
  const network = await uploadAndProcess('network.csv', 'network_log');
  const gps = await uploadAndProcess('gps.csv', 'gps');
  const key1 = randomUUID();
  const run1 = await start(key1);
  assert.equal(run1.trigger, 'initial');
  checkSnapshot(run1);
  const before = await outputs(run1);
  const persistedBefore = storedRun(run1.id);
  assert.deepEqual(before.graph.edges.filter(edge=>['shared_identifier','co_mention'].includes(edge.kind)), [], 'network and GPS start without cross-source candidate links');
  const gpsBefore = resultFor(before, gps);
  assert.equal(factor(gpsBefore, 'connectivity').value, 0);
  assert.equal(factor(gpsBefore, 'relevance').value, 0.2);
  const expectedBefore=verifyTriagePolicy(gpsBefore,{relevance:.2,connectivity:0,gap_relevance:0,conflict_relevance:0,temporal_proximity:1});
  assert.equal(gpsBefore.priority, 'P4');
  assert.deepEqual(await get('/evidence/{evidenceId}/triage-history', undefined,
    { evidenceId: gps.evidence.id }), [gpsBefore]);

  const message = await uploadAndProcess('messages.csv', 'message');
  assert.deepEqual(message.observations.filter(item => item.kind === 'message.id').map(item => item.raw_value),
    ['MSG-1'], 'the committed synthetic message was parsed');
  assert.ok(message.observations.some(item => item.kind === 'message.body' && item.raw_value.includes('D-7') &&
    item.raw_value.includes('D-8')), 'MSG-1 body was processed by the registered adapter');
  // The original idempotency key must keep its old inputs even after processing
  // a new upload; only a fresh key is allowed to select the new observations.
  assert.deepEqual(await start(key1), run1);
  assert.deepEqual(await outputs(run1), before);
  assert.equal(storedRun(run1.id), persistedBefore);
  const key2 = randomUUID();
  assert.notEqual(key2, key1);
  const run2 = await start(key2);
  assert.notEqual(run2.id, run1.id);
  assert.equal(run2.trigger, 'new_observations');
  checkSnapshot(run2);
  const after = await outputs(run2);
  const entities = await get('/entities', { limit: 100, offset: 0 });
  assert.equal(entities.items.length, entities.total);
  const device = (source, label) => {
    const matches = entities.items.filter(item => item.canonical_label === label &&
      item.evidence_ids.includes(source.evidence.id));
    assert.equal(matches.length, 1, `one ${label} candidate in ${source.evidence.filename}`);
    return matches[0];
  };
  const net7 = device(network, 'D-7'), net9 = device(network, 'D-9');
  const gps8 = device(gps, 'D-8'), msg7 = device(message, 'D-7'), msg8 = device(message, 'D-8');
  const signature = (kind, ids) => `${kind}:${sorted(ids).join(':')}`;
  const candidateEdges=after.graph.edges.filter(edge=>['shared_identifier','co_mention'].includes(edge.kind));
  assert.deepEqual(candidateEdges.map(edge => signature(edge.kind, [edge.from_id, edge.to_id])).sort(), [
    signature('shared_identifier', [net7.id, msg7.id]),
    signature('shared_identifier', [gps8.id, msg8.id]),
    signature('co_mention', [msg7.id, msg8.id]),
  ].sort(), 'exactly the three expected candidate edges');
  assert.equal(after.findings.items.filter(item=>item.kind==='relationship').length,3);
  const byId = new Map(entities.items.map(entity => [entity.id, entity]));
  const observations = new Map(sources.flatMap(source => source.observations.map(item => [item.id, item])));
  for (const edge of candidateEdges) {
    const endpoints = [byId.get(edge.from_id), byId.get(edge.to_id)];
    assert.ok(endpoints.every(Boolean), 'candidate edges connect source entity UUIDs');
    assert.ok(!endpoints.includes(net9), 'D-9 control has no cross-source candidate link');
    const evidenceIds = sorted(new Set(endpoints.flatMap(entity => entity.evidence_ids)));
    const observationIds = sorted(new Set(endpoints.flatMap(entity => entity.observation_ids)));
    assert.deepEqual(edge.evidence_ids, evidenceIds);
    assert.deepEqual(edge.observation_ids, observationIds);
    assert.equal(edge.confidence, 0, 'candidate relationships do not establish identity');
    const findings = after.findings.items.filter(item =>
      item.rule===`candidate_link_${edge.kind}:v1` && signature(edge.kind, item.entity_ids) === signature(edge.kind, [edge.from_id, edge.to_id]));
    assert.equal(findings.length, 1, 'one finding for each expected edge');
    const finding = findings[0];
    assert.equal(finding.rule, `candidate_link_${edge.kind}:v1`);
    assert.equal(finding.analysis_run_id, run2.id);
    assert.equal(finding.case_id, caseId);
    assert.equal(finding.confidence, 0);
    assert.deepEqual(finding.evidence_ids, evidenceIds);
    assert.deepEqual(finding.observation_ids, observationIds);
    assert.ok(!finding.entity_ids.includes(net9.id));
    for (const id of observationIds) {
      assert.ok(run2.input_snapshot.observation_ids.includes(id));
      assert.ok(observations.get(id)?.source_locator, 'edge/finding cites a real frozen source locator');
    }
  }
  const gpsAfter = resultFor(after, gps);
  assert.notEqual(gpsAfter.id, gpsBefore.id);
  assert.equal(factor(gpsAfter, 'connectivity').value, 0.1);
  assert.deepEqual(factor(gpsAfter, 'connectivity').evidence_ids, sorted([gps.evidence.id, message.evidence.id]));
  assert.deepEqual(factor(gpsAfter, 'relevance'), factor(gpsBefore, 'relevance'), 'repeated keys add no relevance boost');
  const expectedAfter=verifyTriagePolicy(gpsAfter,{relevance:.2,connectivity:.1,gap_relevance:0,conflict_relevance:0,temporal_proximity:1});
  assert.equal(gpsAfter.priority, 'P4');
  assert.ok(gpsAfter.score > gpsBefore.score);
  assert.deepEqual(await get('/triage'), after.triage, 'default view selects the new completion');
  const history = await get('/evidence/{evidenceId}/triage-history', undefined, { evidenceId: gps.evidence.id });
  assert.deepEqual(history, [gpsBefore, gpsAfter], 'both exact automated evaluations survive in chronological order');
  assert.deepEqual(history.map(item => factor(item, 'connectivity').value), [0, 0.1]);
  assert.deepEqual(history.map(item => item.score), [expectedBefore.score,expectedAfter.score]);
  assert.deepEqual(history.map(item => item.priority), ['P4', 'P4']);
  assert.deepEqual(await get('/evidence/{evidenceId}/triage-history', undefined,
    { evidenceId: message.evidence.id }), [resultFor(after, message)]);

  // U06B consumes the same real history while keeping a historical list pinned.
  const ui = createTriageController(client, caseId, run1.id);
  try {
    ui.start();
    await until(() => ui.getSnapshot(), state => ['ready', 'error'].includes(state.status), 'pinned priority UI');
    assert.equal(ui.getSnapshot().status, 'ready', ui.getSnapshot().message);
    assert.deepEqual(ui.getSnapshot().page, before.triage);
    await ui.loadHistory(gps.evidence.id);
    const historyState = ui.getSnapshot().histories[gps.evidence.id];
    assert.equal(historyState.status, 'ready', historyState.message);
    assert.deepEqual(historyState.items, history);
    const html = renderToStaticMarkup(createElement(PriorityListPanel, {
      state: ui.getSnapshot(), load: ui.load, loadHistory: ui.loadHistory,
    }));
    for (const run of [run1, run2]) assert.ok(html.includes(run.id), 'UI renders both run IDs');
    for (const score of [expectedBefore.score,expectedAfter.score]) assert.ok(html.includes(String(score)), 'UI renders the independently computed policy scores');
    assert.ok(html.includes('Priority unchanged: P4'), 'UI reports the actual priority progression');
    assert.deepEqual(ui.getSnapshot().page, before.triage, 'history loading cannot replace a pinned evaluation');
  } finally { ui.dispose(); }

  assert.deepEqual(await start(key1), run1);
  assert.deepEqual(await start(key2), run2);
  assert.deepEqual(await get('/analysis-runs/{runId}', undefined, { runId: run1.id }), run1);
  assert.deepEqual(await outputs(run1), before, 'all historical graph/findings/triage fields remain identical');
  assert.equal(storedRun(run1.id), persistedBefore, 'historical SQL rows and stored JSON bytes remain identical');
  assert.deepEqual(await get('/evidence/{evidenceId}/triage-history', undefined,
    { evidenceId: gps.evidence.id }), history, 'idempotent replays cannot append evaluations');
  for (const source of sources) {
    const evidence = await get('/evidence/{evidenceId}', undefined, { evidenceId: source.evidence.id });
    assert.deepEqual(evidence, source.evidence, 'analysis preserves original metadata/hash');
    const blob = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
      path: { caseId, evidenceId: evidence.id }, responseType: 'blob',
    });
    assert.deepEqual(Buffer.from(await blob.arrayBuffer()), source.bytes, 'original bytes remain intact');
  }
  console.log('PASS adaptive HTTP tracer checks: exact source-backed graph and candidate links, D-9 cross-source control, GPS connectivity 0.00 -> 0.10, current policy scores, immutable SQL/API history, U06B history UI and originals.');
  console.log('PASS I02 adaptive tracer exit gate (explicit transactional Neo4j double).');
} finally {
  clearTimeout(startupTimer);
  if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
  const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
  try { await closed; } finally { clearTimeout(forceKill); }
  assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i02-')));
  await rm(temporary, { recursive: true, force: true });
}
