import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

// Real HTTP/FastAPI/SQLite, registered CSV producers, detectors and scoring.
// serve-cases.py explicitly doubles Neo4j; this is not live graph acceptance.
// No SQL seeding or detector/assessment mocks may manufacture scoring support.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i07-'));
const database = join(temporary, 'cases.sqlite3');
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', database], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I07 server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I07 server exited (${code ?? signal}): ${diagnostics}`));
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
const factorsByName = result => Object.fromEntries(result.factors.map(item => [item.name, item]));
function factor(result, name) {
  const matches = result.factors.filter(item => item.name === name);
  assert.equal(matches.length, 1, `exactly one ${name} factor for ${result.evidence_id}`);
  return matches[0];
}
// Read-only comparison retains the exact stored JSON strings as well as run
// metadata; all writes, processing and analysis use the public HTTP client.
function storedRun(runId) {
  return execFileSync(python, ['-c', `
import json, pathlib, sqlite3, sys
with sqlite3.connect(pathlib.Path(sys.argv[1]).as_uri() + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    records = [dict(db.execute('SELECT * FROM ' + table + ' WHERE ' + key + '=?',
                              (sys.argv[2],)).fetchone())
               for table, key in [('analysis_runs', 'id'), ('analysis_outputs', 'run_id')]]
print(json.dumps(records, sort_keys=True))
`, database, runId], { encoding: 'utf8', timeout: 15000 });
}
const failures = [];
async function check(label, action) {
  try { await action(); console.log(`PASS I07 ${label}`); }
  catch (cause) {
    const failure = new Error(`${label}: ${cause.message}`, { cause });
    failures.push(failure);
    console.error(`FAIL I07 ${failure.message}`);
  }
}

try {
  const origin = await originReady;
  await until(async () => {
    try {
      return (await fetch(origin + '/api/v1/cases', {
        headers: { Authorization: 'Bearer u02-synthetic-two' }, signal: AbortSignal.timeout(1000),
      })).status;
    } catch { return null; }
  }, status => status === 200, 'API readiness');
  const client = createApiClient({ baseUrl: origin, fetch: (url, options) => fetch(url, {
    ...options, signal: AbortSignal.any([options.signal, AbortSignal.timeout(10000)]),
  }) });
  client.setToken('u02-synthetic-two');
  const fixture = name => readFile(new URL(`../../fixtures/synthetic-case/${name}`, import.meta.url));
  const networkBytes = await fixture('network.csv');
  const gpsBytes = await fixture('gps.csv');

  async function scenario(label, coordinates) {
    const { id: caseId } = await client.request('post', '/api/v1/cases', {
      body: { title: `Synthetic I07 ${label} detector feedback` },
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
    const sources = [];
    async function uploadAndProcess(filename, kind, bytes) {
      const body = new FormData();
      body.set('file', new File([bytes], filename, { type: 'text/csv' }));
      body.set('kind', kind);
      body.set('source_label', `Synthetic I07 ${filename}`);
      const evidence = await post('/evidence', { body });
      assert.equal(evidence.case_id, caseId);
      assert.equal(evidence.kind, kind);
      assert.equal(evidence.sha256, digest(bytes));
      assert.equal(evidence.size_bytes, bytes.length);
      const path = { evidenceId: evidence.id };
      const accepted = await post('/evidence/{evidenceId}/processing-runs', {
        path, header: { 'Idempotency-Key': randomUUID() },
      });
      const processing = await until(() => get('/evidence/{evidenceId}/processing-runs/{runId}', undefined,
        { ...path, runId: accepted.id }), run => ['completed', 'failed'].includes(run.status), `${filename} processing`);
      assert.equal(processing.status, 'completed', JSON.stringify(processing));
      assert.equal(processing.case_id, caseId);
      assert.equal(processing.evidence_id, evidence.id);
      const observations = (await page('/observations', { processing_run_id: processing.id })).items;
      assert.ok(observations.length > 0);
      for (const observation of observations) {
        assert.equal(observation.case_id, caseId);
        assert.equal(observation.evidence_id, evidence.id);
        assert.equal(observation.processing_run_id, processing.id);
        assert.ok(observation.source_locator.trim());
      }
      const source = { evidence, processing, observations, bytes };
      sources.push(source);
      return source;
    }
    async function start(key) {
      const accepted = await post('/analysis-runs', { header: { 'Idempotency-Key': key } });
      const run = await until(() => get('/analysis-runs/{runId}', undefined, { runId: accepted.id }),
        item => ['completed', 'failed'].includes(item.status), `${label} analysis`);
      assert.equal(run.status, 'completed', JSON.stringify(run));
      assert.equal(run.case_id, caseId);
      assert.ok(Number.isFinite(Date.parse(run.created_at)));
      assert.ok(Date.parse(run.finished_at) >= Date.parse(run.created_at));
      return run;
    }
    function checkSnapshot(run) {
      const manifest = {
        case_id: caseId,
        evidence_ids: sorted(sources.map(source => source.evidence.id)),
        observation_ids: sorted(sources.flatMap(source => source.observations.map(item => item.id))),
        processing_run_ids: sorted(sources.map(source => source.processing.id)),
      };
      assert.deepEqual(run.input_snapshot, { ...manifest, sha256: digest(JSON.stringify(manifest)) });
      assert.ok(run.algorithm_version.includes('multi-modal-detectors/1'));
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
      assert.ok(entry?.latest_result, 'processed evidence has a triage result');
      assert.equal(entry.effective_priority, entry.latest_result.priority);
      assert.equal(entry.latest_result.case_id, caseId);
      assert.equal(entry.latest_result.analysis_run_id, output.triage.analysis_run_id);
      return entry.latest_result;
    }
    const history = source => get('/evidence/{evidenceId}/triage-history', undefined,
      { evidenceId: source.evidence.id });
    const network = await uploadAndProcess('network.csv', 'network_log', networkBytes);
    const gps = await uploadAndProcess('gps.csv', 'gps', gpsBytes);
    const key1 = randomUUID();
    const run1 = await start(key1);
    assert.equal(run1.trigger, 'initial');
    checkSnapshot(run1);
    const before = await outputs(run1);
    const persistedBefore = storedRun(run1.id);
    const gpsBefore = resultFor(before, gps);
    await check(`${label}: baseline findings, factors and history`, async () => {
      assert.deepEqual(before.graph.edges, []);
      assert.deepEqual(before.findings.items, []);
      for (const source of [network, gps]) {
        const result = resultFor(before, source);
        assert.ok(factor(result, 'relevance').value > 0);
        assert.equal(factor(result, 'connectivity').value, 0);
        assert.equal(factor(result, 'conflict_relevance').value, 0);
        assert.equal(factor(result, 'gap_relevance').value, 0);
        assert.ok(result.score > 0);
        assert.equal(result.priority, 'P4');
        assert.deepEqual(await history(source), [result]);
      }
    });

    // Same candidate and instant as gps.csv. Only the reported coordinates
    // differ between the positive and control cases. No new keys/times/gaps
    // confound the comparison. Decimal-equivalent control bytes differ from
    // the original upload, avoiding an evidence deduplication shortcut.
    const extra = await uploadAndProcess('gps-followup.csv', 'gps', Buffer.from(
      `timestamp,device_id,latitude,longitude\n2026-01-12T10:02:00Z,D-8,${coordinates}\n`));
    await check(`${label}: new upload preserves the original run before reanalysis`, async () => {
      assert.deepEqual(await start(key1), run1);
      assert.deepEqual(await outputs(run1), before);
      assert.equal(storedRun(run1.id), persistedBefore);
      assert.deepEqual(await history(gps), [gpsBefore]);
    });
    const key2 = randomUUID();
    assert.notEqual(key1, key2);
    const run2 = await start(key2);
    assert.notEqual(run2.id, run1.id);
    assert.equal(run2.trigger, 'new_observations');
    assert.notEqual(run2.input_snapshot.sha256, run1.input_snapshot.sha256);
    checkSnapshot(run2);
    const after = await outputs(run2);
    const gpsAfter = resultFor(after, gps);
    await check(`${label}: source-backed findings and non-conflicting network control`, async () => {
      const observations = new Map(sources.flatMap(source => source.observations.map(item => [item.id, item])));
      for (const finding of after.findings.items) {
        assert.equal(finding.case_id, caseId);
        assert.equal(finding.analysis_run_id, run2.id);
        assert.ok(finding.observation_ids.length > 0);
        const cited = finding.observation_ids.map(id => {
          assert.ok(run2.input_snapshot.observation_ids.includes(id));
          assert.ok(observations.get(id)?.source_locator, 'finding resolves to a frozen source locator');
          return observations.get(id);
        });
        assert.deepEqual(sorted(finding.evidence_ids), sorted(new Set(cited.map(item => item.evidence_id))));
      }
      assert.equal(after.graph.edges.length, 1, 'one shared-identifier edge in both scenarios');
      assert.deepEqual(sorted(after.graph.edges[0].evidence_ids), sorted([gps.evidence.id, extra.evidence.id]));
      assert.equal(factor(gpsAfter, 'relevance').value, factor(gpsBefore, 'relevance').value);
      assert.equal(factor(gpsAfter, 'connectivity').value, 0.1);
      const conflicts = after.findings.items.filter(item => item.kind === 'conflict');
      if (label === 'positive') {
        assert.equal(conflicts.length, 1, 'the contradictory GPS report must produce a conflict');
        assert.equal(conflicts[0].rule, 'conflict_simultaneous_location:v1');
        assert.deepEqual(sorted(conflicts[0].evidence_ids), sorted([gps.evidence.id, extra.evidence.id]));
        assert.equal(conflicts[0].observation_ids.length, 6, 'both complete GPS rows are cited');
        assert.ok(conflicts[0].missing_information.length > 0, 'uncertainty remains explicit');
      } else {
        assert.deepEqual(conflicts, [], 'equivalent coordinates must not produce false conflicts');
        for (const source of [gps, extra]) assert.equal(factor(resultFor(after, source), 'conflict_relevance').value, 0);
      }
      assert.deepEqual(after.findings.items.filter(item => ['gap', 'anomaly'].includes(item.kind)), []);
      const networkAfter = resultFor(after, network);
      assert.equal(factor(networkAfter, 'conflict_relevance').value, 0);
      assert.equal(factor(networkAfter, 'connectivity').value, 0);
      assert.equal(networkAfter.score, resultFor(before, network).score, 'unrelated evidence score stays unchanged');
      assert.ok(!conflicts.some(item => item.evidence_ids.includes(network.evidence.id)));
    });
    await check(`${label}: immutable history, stored bytes, idempotency and originals`, async () => {
      for (const source of [network, gps]) {
        const first = resultFor(before, source), second = resultFor(after, source);
        assert.notEqual(first.id, second.id);
        const records = await history(source);
        assert.deepEqual(records, [first, second], 'both exact evaluations remain in chronological order');
        assert.deepEqual(records.map(item => item.analysis_run_id), [run1.id, run2.id]);
        assert.ok(Date.parse(records[0].created_at) < Date.parse(records[1].created_at));
      }
      assert.deepEqual(await history(extra), [resultFor(after, extra)]);
      assert.deepEqual(await get('/triage', { limit: 100, offset: 0 }), after.triage);
      assert.deepEqual(await start(key1), run1);
      assert.deepEqual(await start(key2), run2);
      assert.deepEqual(await outputs(run1), before, 'old scores, factor values and findings are frozen');
      assert.equal(storedRun(run1.id), persistedBefore, 'old SQL rows and output JSON strings are unchanged');
      assert.deepEqual(await history(gps), [gpsBefore, gpsAfter], 'replay cannot append history');
      for (const source of sources) {
        assert.deepEqual(await get('/evidence/{evidenceId}', undefined, { evidenceId: source.evidence.id }), source.evidence);
        const content = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
          path: { caseId, evidenceId: source.evidence.id }, responseType: 'blob',
        });
        assert.deepEqual(Buffer.from(await content.arrayBuffer()), source.bytes);
      }
    });
    console.log(`I07 ${label} GPS: ${gpsBefore.priority}/${gpsBefore.score} -> ${gpsAfter.priority}/${gpsAfter.score}; ` +
      `factors ${JSON.stringify(Object.fromEntries(gpsAfter.factors.map(item => [item.name, item.value])))}`);
    return { before: gpsBefore, after: gpsAfter, evidenceIds: sorted([gps.evidence.id, extra.evidence.id]) };
  }

  const positive = await scenario('positive', '13.0827,80.2707');
  const control = await scenario('control', '12.971600,77.594600');
  await check('detector feedback contributes to an existing evidence score beyond matched graph adaptation', async () => {
    assert.equal(positive.before.score, control.before.score);
    for (const name of ['relevance', 'connectivity', 'temporal_proximity']) {
      assert.equal(factor(positive.after, name).value, factor(control.after, name).value,
        `${name} is matched so ordinary upload adaptation cannot certify detector feedback`);
    }
    const feedback = factorsByName(positive.after).conflict_relevance;
    assert.ok(feedback,
      'conflict finding must supply conflict_relevance on existing GPS evidence; absent assessment blocks I07');
    assert.ok(feedback.value > factor(positive.before, 'conflict_relevance').value, 'conflict feedback value increases');
    assert.ok(feedback.contribution > 0, 'detector feedback must actually contribute to scoring');
    assert.deepEqual(sorted(feedback.evidence_ids), positive.evidenceIds, 'factor cites the conflicting source pair');
    assert.ok(positive.after.score > positive.before.score, 'existing evidence score increases');
    assert.ok(positive.after.score > control.after.score, 'conflict score exceeds matched non-conflicting control');
    const otherContributions = positive.after.factors.filter(item => item.name !== 'conflict_relevance')
      .reduce((sum, item) => sum + item.contribution, 0);
    assert.ok(Math.abs(positive.after.score - otherContributions - feedback.contribution) < 0.02,
      'published score includes the detector factor contribution');
  });
  if (failures.length) throw new AggregateError(failures, `I07 detector-feedback gate failed (${failures.length} checks)`);
  console.log('PASS I07 detector-feedback priority tracer gate (explicit transactional Neo4j double).');
} finally {
  clearTimeout(startupTimer);
  try {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
    try { await closed; } finally { clearTimeout(forceKill); }
  } finally {
    assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i07-')));
    await rm(temporary, { recursive: true, force: true });
  }
}
