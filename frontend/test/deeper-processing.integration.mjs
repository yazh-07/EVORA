import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

// Real HTTP/FastAPI/SQLite, registered CSV processors, analysis and scoring.
// serve-cases.py uses an explicit transactional Neo4j double, not live Neo4j.
// No new upload, SQL mutation or mocked producer may manufacture a rerank.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i07b-'));
const database = join(temporary, 'cases.sqlite3');
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', database], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I07B server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I07B server exited (${code ?? signal}): ${diagnostics}`));
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
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const sorted = values => [...values].sort();
const factor = (result, name) => {
  const matches = result.factors.filter(item => item.name === name);
  assert.equal(matches.length, 1, `exactly one ${name} factor`);
  return matches[0];
};
// Read-only harness access: provenance has no public HTTP surface. Retain exact
// stored JSON column strings so comparison also detects byte-level rewrites.
function storedRun(kind, runId) {
  return JSON.parse(execFileSync(python, ['-c', `
import json, pathlib, sqlite3, sys
tables = {'processing': [('processing_runs', 'id'), ('processing_outputs', 'run_id'),
                         ('processing_provenance', 'run_id')],
          'analysis': [('analysis_runs', 'id'), ('analysis_outputs', 'run_id')]}
with sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri() + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    records = {table: dict(db.execute('SELECT * FROM ' + table + ' WHERE ' + key + '=?',
                                     (sys.argv[3],)).fetchone())
               for table, key in tables[sys.argv[2]]}
print(json.dumps(records, sort_keys=True))
`, database, kind, runId], { encoding: 'utf8', timeout: 15000 }));
}

try {
  const origin = await originReady;
  await until(async () => {
    try { return (await fetch(origin + '/api/v1/cases', {
      headers: { Authorization: 'Bearer u02-synthetic-two' }, signal: AbortSignal.timeout(1000),
    })).status; } catch { return null; }
  }, status => status === 200, 'API readiness');
  const client = createApiClient({ baseUrl: origin, fetch: (url, options) => fetch(url, {
    ...options, signal: AbortSignal.any([options.signal, AbortSignal.timeout(10000)]),
  }) });
  client.setToken('u02-synthetic-two');
  const { id: caseId } = await client.request('post', '/api/v1/cases', {
    body: { title: 'Synthetic I07B existing-evidence deeper processing' },
  });
  const get = (route, query, path = {}) => client.request('get', `/api/v1/cases/{caseId}${route}`, {
    path: { caseId, ...path }, query,
  });
  const post = (route, options) => client.request('post', `/api/v1/cases/{caseId}${route}`, {
    ...options, path: { caseId, ...options.path },
  });
  async function page(route, query = {}) {
    const result = await get(route, { ...query, limit: 100, offset: 0 });
    assert.equal(result.items.length, result.total, `${route}: complete fixture page`);
    return result;
  }
  const processingPath = source => ({ evidenceId: source.evidence.id });
  const startProcessing = (source, key) => post('/evidence/{evidenceId}/processing-runs', {
    path: processingPath(source), header: { 'Idempotency-Key': key },
  });
  const readProcessing = (source, runId) => get('/evidence/{evidenceId}/processing-runs/{runId}',
    undefined, { ...processingPath(source), runId });
  const listProcessing = source => get('/evidence/{evidenceId}/processing-runs', undefined, processingPath(source));
  const readObservations = async run => (await page('/observations', { processing_run_id: run.id })).items;
  async function processEvidence(source, key) {
    const accepted = await startProcessing(source, key);
    const run = await until(() => readProcessing(source, accepted.id),
      item => ['completed', 'failed'].includes(item.status), `${source.evidence.filename} processing`);
    assert.equal(run.status, 'completed', JSON.stringify(run));
    assert.equal(run.case_id, caseId);
    assert.equal(run.evidence_id, source.evidence.id);
    assert.ok(Date.parse(run.finished_at) >= Date.parse(run.created_at));
    const observations = await readObservations(run);
    assert.ok(observations.length > 0);
    for (const observation of observations) {
      assert.equal(observation.case_id, caseId);
      assert.equal(observation.evidence_id, source.evidence.id);
      assert.equal(observation.processing_run_id, run.id);
      assert.ok(observation.source_locator.trim(), 'every observation resolves to the original source');
    }
    return { run, observations };
  }
  async function upload(filename, kind, customBytes) {
    const bytes = customBytes ?? await readFile(new URL(`../../fixtures/synthetic-case/${filename}`, import.meta.url));
    const body = new FormData();
    body.set('file', new File([bytes], filename, { type: 'text/csv' }));
    body.set('kind', kind);
    body.set('source_label', `Synthetic I07B ${filename}`);
    const evidence = await post('/evidence', { body });
    assert.equal(evidence.case_id, caseId);
    assert.equal(evidence.kind, kind);
    assert.equal(evidence.sha256, digest(bytes));
    assert.equal(evidence.size_bytes, bytes.length);
    return { evidence, bytes, key: randomUUID() };
  }
  const startAnalysis = key => post('/analysis-runs', { header: { 'Idempotency-Key': key } });
  async function analyze(key) {
    const accepted = await startAnalysis(key);
    const run = await until(() => get('/analysis-runs/{runId}', undefined, { runId: accepted.id }),
      item => ['completed', 'failed'].includes(item.status), 'analysis');
    assert.equal(run.status, 'completed', JSON.stringify(run));
    assert.equal(run.case_id, caseId);
    assert.ok(Date.parse(run.finished_at) >= Date.parse(run.created_at));
    return run;
  }
  async function outputs(run) {
    const query = { analysis_run_id: run.id };
    const [graph, findings, triage] = await Promise.all([
      get('/graph', query), page('/findings', query), page('/triage', query),
    ]);
    for (const output of [graph, findings, triage]) assert.equal(output.analysis_run_id, run.id);
    assert.deepEqual(sorted(triage.items.map(item => item.evidence_id)), run.input_snapshot.evidence_ids);
    return { graph, findings, triage };
  }
  function resultFor(output, source) {
    const entry = output.triage.items.find(item => item.evidence_id === source.evidence.id);
    assert.ok(entry?.latest_result, 'processed evidence has an automated evaluation');
    assert.equal(entry.latest_result.case_id, caseId);
    assert.equal(entry.latest_result.analysis_run_id, output.triage.analysis_run_id);
    assert.equal(entry.effective_priority, entry.latest_result.priority);
    return entry.latest_result;
  }
  const history = source => get('/evidence/{evidenceId}/triage-history', undefined, processingPath(source));
  function checkSnapshot(run, selections) {
    const manifest = {
      case_id: caseId,
      evidence_ids: sorted(sources.map(source => source.evidence.id)),
      observation_ids: sorted(selections.flatMap(selection => selection.observations.map(item => item.id))),
      processing_run_ids: sorted(selections.map(selection => selection.run.id)),
    };
    assert.deepEqual(run.input_snapshot, { ...manifest, sha256: digest(JSON.stringify(manifest)) });
  }
  function checkProvenance(source, selection, stored) {
    const { run, observations } = selection;
    const record = stored.processing_provenance;
    const payload = JSON.parse(record.payload_json);
    const config = JSON.parse(stored.processing_runs.config_json);
    const output = stored.processing_outputs;
    for (const row of [stored.processing_runs, output, record]) {
      assert.equal(row.case_id, caseId);
      assert.equal(row.evidence_id, source.evidence.id);
    }
    assert.equal(record.run_id, run.id);
    assert.equal(record.record_version, 'processing-provenance/1');
    assert.equal(record.finished_at, run.finished_at);
    assert.deepEqual(sorted(Object.keys(payload)), sorted([
      'record_version', 'case_id', 'evidence_id', 'processing_run_id', 'input', 'execution',
      'outputs', 'output_sha256', 'accepted_at', 'finished_at',
    ]), 'private provenance contains integrity metadata rather than raw source contents');
    assert.equal(payload.record_version, record.record_version);
    assert.equal(payload.case_id, caseId);
    assert.equal(payload.evidence_id, source.evidence.id);
    assert.equal(payload.processing_run_id, run.id);
    assert.equal(payload.accepted_at, run.created_at);
    assert.equal(payload.finished_at, run.finished_at);
    assert.deepEqual(payload.input, {
      kind: source.evidence.kind, sha256: digest(source.bytes), size_bytes: source.bytes.length,
    });
    const versionKeys = ['parser_version', 'normalizer_version', 'entity_version', 'event_version', 'processor_version'];
    assert.deepEqual(payload.execution.versions, Object.fromEntries(versionKeys.map(key => [key, config[key]])));
    assert.equal(payload.execution.versions.processor_version, run.processor_version);
    const expectedParams = {
      max_source_bytes: config.max_source_bytes, max_data_rows: config.max_data_rows,
    };
    if (config.max_device_mentions !== undefined) expectedParams.max_device_mentions = config.max_device_mentions;
    assert.deepEqual(payload.execution.parameters, expectedParams);
    assert.equal(payload.execution.method, 'deterministic');
    assert.equal(payload.execution.model, null);
    const fields = ['entities_json', 'events_json', 'observations_json', 'uncertainty_json'];
    assert.equal(payload.output_sha256, digest(JSON.stringify(Object.fromEntries(fields.map(key => [key, output[key]])))));
    for (const [name, field] of [['observation_ids', 'observations_json'], ['entity_ids', 'entities_json'],
      ['event_ids', 'events_json']]) {
      const records = JSON.parse(output[field]);
      assert.deepEqual(payload.outputs[name], sorted(records.map(item => item.id)));
      for (const item of records) assert.equal(item.case_id, caseId);
    }
    assert.deepEqual(sorted(observations.map(item => item.id)), payload.outputs.observation_ids);
    assert.deepEqual([...observations].sort((a, b) => a.id.localeCompare(b.id)),
      JSON.parse(output.observations_json).sort((a, b) => a.id.localeCompare(b.id)));
    assert.deepEqual(sorted(Object.keys(run)), sorted([
      'id', 'case_id', 'evidence_id', 'status', 'processor_version', 'created_at', 'finished_at',
    ]), 'public processing run does not disclose private config, provenance or idempotency digests');
  }

  const network = await upload('network.csv', 'network_log');
  const messageBytes = Buffer.from('message_id,timestamp,sender,body\nMSG-1,2026-01-12T10:01:00Z,synthetic-sender,D-7 203.0.113.7 203.0.113.9 AC-42 +120****0123\n');
  const target = await upload('messages.csv', 'message', messageBytes);
  const sources = [network, target];
  const networkProcessing = await processEvidence(network, network.key);
  const proc1 = await processEvidence(target, target.key);
  const storedNetwork = storedRun('processing', networkProcessing.run.id);
  const storedProc1 = storedRun('processing', proc1.run.id);
  checkProvenance(network, networkProcessing, storedNetwork);
  checkProvenance(target, proc1, storedProc1);
  const key1 = randomUUID();
  const run1 = await analyze(key1);
  assert.equal(run1.trigger, 'initial');
  checkSnapshot(run1, [networkProcessing, proc1]);
  const before = await outputs(run1);
  const storedRun1 = storedRun('analysis', run1.id);
  const targetBefore = resultFor(before, target);
  assert.ok(before.findings.items.length > 0, 'initial run creates candidate relationship finding');
  for (const source of sources) {
    const result = resultFor(before, source);
    assert.ok(result.score > 0);
    assert.ok(factor(result, 'relevance').value > 0);
    assert.deepEqual(await history(source), [result]);
  }
  console.log('PASS I07B real baseline processing, private provenance and frozen initial triage.');

  // Same Evidence, same bytes/hash, no third upload and no invented selector
  // request fields. Any deeper selection must come from real internal policy.
  const processingKey2 = randomUUID();
  assert.notEqual(processingKey2, target.key);
  const proc2 = await processEvidence(target, processingKey2);
  assert.notEqual(proc2.run.id, proc1.run.id);
  assert.ok(Date.parse(proc2.run.finished_at) > Date.parse(proc1.run.finished_at));
  assert.ok(proc2.observations.every(item => !proc1.observations.some(old => old.id === item.id)));
  const storedProc2 = storedRun('processing', proc2.run.id);
  checkProvenance(target, proc2, storedProc2);
  assert.deepEqual(await listProcessing(target), [proc1.run, proc2.run]);
  assert.deepEqual(await readProcessing(target, proc1.run.id), proc1.run);
  assert.deepEqual(await readObservations(proc1.run), proc1.observations);
  assert.deepEqual(storedRun('processing', proc1.run.id), storedProc1);
  assert.deepEqual(await startProcessing(target, target.key), proc1.run);
  assert.deepEqual(await startProcessing(target, processingKey2), proc2.run);
  assert.deepEqual(await startAnalysis(key1), run1, 'original analysis key cannot refreeze after reprocessing');
  assert.deepEqual(await outputs(run1), before, 'processing alone cannot rewrite old triage');
  assert.deepEqual(await history(target), [targetBefore]);
  console.log('PASS I07B same-evidence reprocessing retains proc1/proc2 outputs and private provenance.');

  const key2 = randomUUID();
  assert.notEqual(key2, key1);
  const run2 = await analyze(key2);
  assert.notEqual(run2.id, run1.id);
  assert.equal(run2.trigger, 'new_observations');
  assert.notEqual(run2.input_snapshot.sha256, run1.input_snapshot.sha256);
  assert.deepEqual(run2.input_snapshot.evidence_ids, run1.input_snapshot.evidence_ids);
  checkSnapshot(run2, [networkProcessing, proc2]);
  assert.ok(!run2.input_snapshot.processing_run_ids.includes(proc1.run.id));
  assert.ok(proc1.observations.every(item => !run2.input_snapshot.observation_ids.includes(item.id)));
  const after = await outputs(run2);
  const storedRun2 = storedRun('analysis', run2.id);
  const targetAfter = resultFor(after, target);
  assert.deepEqual(await page('/triage'), after.triage, 'default triage selects the new completed analysis');
  for (const source of sources) {
    const first = resultFor(before, source), second = resultFor(after, source);
    assert.notEqual(first.id, second.id);
    const records = await history(source);
    assert.deepEqual(records, [first, second], 'exact scores, factors and explanations in chronological order');
    assert.deepEqual(records.map(item => item.analysis_run_id), [run1.id, run2.id]);
    assert.ok(Date.parse(records[0].created_at) < Date.parse(records[1].created_at));
  }
  console.log('PASS I07B run2 freezes only the latest completed processing and appends chronological triage history.');

  // Replays must not create processing/analysis runs, outputs or evaluations.
  assert.deepEqual(await startProcessing(network, network.key), networkProcessing.run);
  assert.deepEqual(await startProcessing(target, target.key), proc1.run);
  assert.deepEqual(await startProcessing(target, processingKey2), proc2.run);
  assert.deepEqual(await startAnalysis(key1), run1);
  assert.deepEqual(await startAnalysis(key2), run2);
  assert.deepEqual(await get('/analysis-runs'), [run1, run2]);
  assert.deepEqual(await get('/analysis-runs/{runId}', undefined, { runId: run1.id }), run1);
  assert.deepEqual(await outputs(run1), before, 'run1 snapshot, score, every factor and all outputs remain frozen');
  assert.deepEqual(await outputs(run2), after);
  assert.deepEqual(storedRun('analysis', run1.id), storedRun1, 'historical SQL rows and JSON bytes are unchanged');
  assert.deepEqual(storedRun('analysis', run2.id), storedRun2);
  for (const [source, selections] of [[network, [networkProcessing]], [target, [proc1, proc2]]]) {
    assert.deepEqual(await listProcessing(source), selections.map(selection => selection.run));
    for (const selection of selections) {
      assert.deepEqual(await readProcessing(source, selection.run.id), selection.run);
      assert.deepEqual(await readObservations(selection.run), selection.observations);
    }
    assert.deepEqual(await history(source), [resultFor(before, source), resultFor(after, source)]);
    assert.deepEqual(await get('/evidence/{evidenceId}', undefined, processingPath(source)), source.evidence);
    const blob = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
      path: { caseId, ...processingPath(source) }, responseType: 'blob',
    });
    assert.deepEqual(Buffer.from(await blob.arrayBuffer()), source.bytes, 'original bytes/hash stay intact');
  }
  assert.deepEqual(storedRun('processing', networkProcessing.run.id), storedNetwork);
  assert.deepEqual(storedRun('processing', proc1.run.id), storedProc1);
  assert.deepEqual(storedRun('processing', proc2.run.id), storedProc2);
  assert.equal((await page('/evidence')).total, 2, 'rerank cannot be attributed to a new upload');
  console.log('PASS I07B processing/analysis same-key replay, immutable SQL/API history and original evidence.');

  console.log(`I07B Target: ${targetBefore.priority}/${targetBefore.score} -> ${targetAfter.priority}/${targetAfter.score}; ` +
    `factors ${JSON.stringify(Object.fromEntries(targetAfter.factors.map(item => [item.name, item.value])))}`);
  assert.notEqual(targetAfter.score, targetBefore.score,
    'I07B: same-evidence deeper processing must change the score.');
  const changedFactors = targetAfter.factors.filter(item => {
    const previous = targetBefore.factors.find(old => old.name === item.name);
    return (!previous || previous.value !== item.value) && item.contribution !== (previous?.contribution ?? 0);
  });
  assert.ok(changedFactors.length > 0, 'rerank must have a numerically changed contributing factor');
  const selectedObservations = [...networkProcessing.observations, ...proc2.observations];
  const semanticSource = item => JSON.stringify([item.evidence_id, item.kind, item.source_locator,
    item.raw_value, item.normalized_value, item.observed_at_utc, item.entity_key, item.extraction_confidence]);
  const oldSources = new Set(proc1.observations.map(semanticSource));
  const newSupport = proc2.observations.filter(item => !oldSources.has(semanticSource(item)));
  assert.ok(newSupport.length > 0, 'deeper processing must add source support beyond regenerated UUIDs');
  assert.ok(changedFactors.some(item => item.evidence_ids.includes(target.evidence.id)),
    'a changed factor cites the reprocessed original Evidence');
  for (const item of changedFactors) {
    assert.ok(item.explanation.trim(), 'changed factors explain the score delta');
    assert.ok(item.evidence_ids.length > 0);
    for (const evidenceId of item.evidence_ids) {
      assert.ok(run2.input_snapshot.evidence_ids.includes(evidenceId));
      const cited = selectedObservations.filter(observation => observation.evidence_id === evidenceId);
      assert.ok(cited.length > 0, 'factor references resolve to selected processing output');
      for (const observation of cited) {
        assert.ok(run2.input_snapshot.observation_ids.includes(observation.id));
        assert.ok(observation.source_locator.trim());
      }
    }
  }
  assert.ok(Math.abs(targetAfter.score - targetAfter.factors.reduce((sum, item) => sum + item.contribution, 0)) < 0.02,
    'published score includes the justified factor contributions');
  console.log('PASS I07B deeper-processing rerank tracer gate (explicit transactional Neo4j double).');
} finally {
  clearTimeout(startupTimer);
  try {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
    try { await closed; } finally { clearTimeout(forceKill); }
  } finally {
    assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i07b-')));
    await rm(temporary, { recursive: true, force: true });
  }
}
