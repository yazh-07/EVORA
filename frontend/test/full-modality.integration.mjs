import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Real HTTP client, FastAPI, SQLite, registered producers and analysis. The
// shared harness doubles Neo4j. Audio dispatch is an honest 415 control; an
// explicit machine fixture certifies transcript correction, not ASR quality.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const { createTranscriptController, TranscriptPanel } = await import('../.test-build/src/cases/CaseWorkspace.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i03b-'));
const database = join(temporary, 'cases.sqlite3');
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', database], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I03B server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I03B server exited (${code ?? signal}): ${diagnostics}`));
  });
});
const closed = new Promise(resolve => child.once('close', resolve));

async function until(read, done, label) {
  // The real local NER worker can take longer than the CSV parsers to start.
  const deadline = Date.now() + 150000;
  let value;
  do {
    value = await read();
    if (done(value)) return value;
    await delay(50);
  } while (Date.now() < deadline);
  assert.fail(`${label} timed out: ${JSON.stringify(value)}; ${diagnostics}`);
}

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const sorted = values => [...values].sort();
const ids = records => sorted(records.map(record => record.id));
function assertTimestamp(value) {
  assert.match(value, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/);
  assert.ok(Number.isFinite(Date.parse(value)));
}

function syntheticWav() {
  // Valid mono PCM media, rather than text renamed .wav. A tone does not imply
  // speech. Machine transcript text is seeded explicitly, never inferred here.
  const sampleRate = 16000;
  const samples = sampleRate;
  const bytes = Buffer.alloc(44 + samples * 2);
  bytes.write('RIFF'); bytes.writeUInt32LE(bytes.length - 8, 4);
  bytes.write('WAVEfmt ', 8); bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(sampleRate, 24); bytes.writeUInt32LE(sampleRate * 2, 28);
  bytes.writeUInt16LE(2, 32); bytes.writeUInt16LE(16, 34);
  bytes.write('data', 36); bytes.writeUInt32LE(samples * 2, 40);
  for (let index = 0; index < samples; index++) {
    bytes.writeInt16LE(Math.round(2000 * Math.sin(2 * Math.PI * 440 * index / sampleRate)), 44 + index * 2);
  }
  return bytes;
}

function seedMachineTranscript(caseId, evidence) {
  // Match backend/tests/test_transcripts.py::machine_fixture. Only publication
  // setup uses SQL; reads, corrections, derived outputs and audit use real HTTP.
  return execFileSync(python, ['-c', `
import hashlib, json, sqlite3, sys
from uuid import uuid4
database, case_id, evidence_id = sys.argv[1:]
run_id = str(uuid4())
timestamp = '2026-01-01T00:00:00Z'
wire = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
observations = [dict(id=str(uuid4()), case_id=case_id, evidence_id=evidence_id, processing_run_id=run_id,
    kind='transcript.segment', source_locator=f'media:start_ms={i * 1000};end_ms={(i + 1) * 1000}',
    raw_value=text, normalized_value=text, extraction_confidence=0.4 + i / 10)
    for i, text in enumerate(('Machine D-7 spoke.', 'Other D-8 replied.'))]
observations.append(dict(id=str(uuid4()), case_id=case_id, evidence_id=evidence_id, processing_run_id=run_id,
    kind='video.frame', source_locator='media:frame=0', raw_value='Original visual',
    normalized_value='Original visual', extraction_confidence=0.3))
mentions = [dict(id=str(uuid4()), case_id=case_id, evidence_id=evidence_id, processing_run_id=run_id,
    kind='text.mention.device', source_locator=observations[i]['source_locator'], raw_value=label,
    normalized_value=label, entity_key='device:' + label, extraction_confidence=0)
    for i, label in enumerate(('D-7', 'D-8'))]
entities = [dict(id=str(uuid4()), case_id=case_id, kind='device', canonical_label=label,
    candidate_key='device:' + label, evidence_ids=[evidence_id], observation_ids=[mentions[i]['id']], confidence=0)
    for i, label in enumerate(('D-7', 'D-8'))]
events = [dict(id=str(uuid4()), case_id=case_id, kind='visual.detected', summary='Visual source candidate',
    evidence_ids=[evidence_id], observation_ids=[observations[2]['id']], entity_ids=[], confidence=0)]
uncertainty = [dict(observation_id=item['id'], diagnostic='machine-fixture') for item in observations + mentions]
outputs = [observations + mentions, entities, events, uncertainty]
with sqlite3.connect(database) as db:
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('BEGIN IMMEDIATE')
    db.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
        'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (run_id, case_id, evidence_id, 'investigator-2', str(uuid4()), 'synthetic-machine-fixture', '{}',
         'synthetic-asr-fixture/1', timestamp, 'queued'))
    db.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
    serialized = list(map(wire, outputs))
    db.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)', (run_id, case_id, evidence_id, *serialized))
    evidence = dict(db.execute('SELECT kind,sha256,size_bytes FROM evidence WHERE id=?', (evidence_id,)).fetchone())
    payload = dict(record_version='processing-provenance/1', case_id=case_id, evidence_id=evidence_id,
        processing_run_id=run_id, input=evidence,
        execution=dict(versions=dict(processor_version='synthetic-asr-fixture/1'),
                       parameters={}, method='synthetic_machine_fixture', model=None),
        outputs={name: sorted(item['id'] for item in records) for name, records in zip(
            ('observation_ids', 'entity_ids', 'event_ids'), outputs[:3])},
        output_sha256=hashlib.sha256(wire(dict(zip(
            ('observations_json', 'entities_json', 'events_json', 'uncertainty_json'), serialized))).encode()).hexdigest(),
        accepted_at=timestamp, finished_at=timestamp)
    # The production trigger admits registered processors only. Suspend it for
    # this explicit fixture insert and restore its exact SQL before committing;
    # all HTTP operations run with the original database protections intact.
    trigger = db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='processing_provenance_context'").fetchone()[0]
    db.execute('DROP TRIGGER processing_provenance_context')
    db.execute('INSERT INTO processing_provenance VALUES (?,?,?,?,?,?)',
        (run_id, case_id, evidence_id, 'processing-provenance/1', timestamp, wire(payload)))
    db.execute(trigger)
    db.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (timestamp, run_id))
print(run_id)
`, database, caseId, evidence.id], { encoding: 'utf8' }).trim();
}

// Provenance is deliberately private (there is no HTTP endpoint). Inspect only
// the disposable database, in read-only mode, after HTTP publication completes.
function privateRuns(caseId) {
  return JSON.parse(execFileSync(python, ['-c', `
import json, sqlite3, sys
from pathlib import Path
with sqlite3.connect(Path(sys.argv[1]).as_uri() + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    result = {}
    for run in db.execute('SELECT * FROM processing_runs WHERE case_id=? ORDER BY id', (sys.argv[2],)):
        output = db.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone()
        provenance = db.execute('SELECT * FROM processing_provenance WHERE run_id=?', (run['id'],)).fetchone()
        result[run['id']] = dict(run=dict(run), output=dict(output) if output else None,
            provenance=dict(provenance) if provenance else None)
    print(json.dumps(result))
`, database, caseId], { encoding: 'utf8' }));
}

function verifyProvenance(entry, evidence, run) {
  assert.ok(entry?.output, 'completed run has persisted outputs');
  assert.ok(entry.provenance, 'completed run has private provenance');
  const payload = JSON.parse(entry.provenance.payload_json);
  for (const record of [entry.output, entry.provenance, payload]) {
    assert.equal(record.case_id, evidence.case_id);
    assert.equal(record.evidence_id, evidence.id);
  }
  assert.equal(payload.processing_run_id, run.id);
  assert.equal(payload.record_version, 'processing-provenance/1');
  assert.equal(payload.finished_at, run.finished_at);
  assert.equal(payload.accepted_at, run.created_at);
  assert.deepEqual(payload.input, { kind: evidence.kind, sha256: evidence.sha256, size_bytes: evidence.size_bytes });
  assert.equal(payload.execution.versions.processor_version, run.processor_version);
  // Hash the exact stored JSON strings, framed in the producer's canonical order.
  const fields = ['entities_json', 'events_json', 'observations_json', 'uncertainty_json'];
  const framed = Object.fromEntries(fields.map(field => [field, entry.output[field]]));
  assert.equal(payload.output_sha256, digest(JSON.stringify(framed)));
  for (const [manifest, field] of [['observation_ids', 'observations_json'],
    ['entity_ids', 'entities_json'], ['event_ids', 'events_json']]) {
    assert.deepEqual(payload.outputs[manifest], ids(JSON.parse(entry.output[field])));
  }
  return payload;
}

const failures = [];
async function check(label, action) {
  try { await action(); console.log(`PASS I03B ${label}`); }
  catch (cause) {
    const detail = cause.status ? `HTTP ${cause.status} ${cause.apiError?.code ?? ''}` : cause.message;
    const failure = new Error(`${label}: ${detail}`, { cause });
    failures.push(failure);
    console.error(`FAIL I03B ${failure.message}`);
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
  const transport = (url, options) => fetch(url, {
    ...options, signal: AbortSignal.any([options.signal, AbortSignal.timeout(10000)]),
  });
  const client = createApiClient({ baseUrl: origin, fetch: transport });
  client.setToken('u02-synthetic-two');
  const { id: caseId } = await client.request('post', '/api/v1/cases', {
    body: { title: 'Synthetic I03B full-modality investigation' },
  });
  const get = (route, query, path = {}) => client.request('get', `/api/v1/cases/{caseId}${route}`, {
    path: { caseId, ...path }, query,
  });
  const post = (route, options = {}) => client.request('post', `/api/v1/cases/{caseId}${route}`, {
    ...options, path: { caseId, ...options.path },
  });
  async function page(route, query = {}, path = {}) {
    const result = await get(route, { ...query, limit: 100, offset: 0 }, path);
    assert.equal(result.items.length, result.total, `${route}: fixture fits one complete page`);
    assert.equal(new Set(result.items.map(item => item.id ?? item.evidence_id)).size, result.total);
    return result;
  }
  async function upload(source) {
    const body = new FormData();
    body.set('file', new File([source.bytes], source.filename, { type: source.type ?? 'text/csv' }));
    body.set('kind', source.kind);
    body.set('source_label', `Synthetic I03B ${source.filename}`);
    const evidence = await post('/evidence', { body });
    assert.equal(evidence.case_id, caseId);
    assert.equal(evidence.kind, source.kind);
    assert.equal(evidence.sha256, digest(source.bytes));
    assert.equal(evidence.size_bytes, source.bytes.length);
    const original = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
      path: { caseId, evidenceId: evidence.id }, responseType: 'blob',
    });
    assert.deepEqual(Buffer.from(await original.arrayBuffer()), source.bytes);
    return evidence;
  }
  async function completedRun(route, path = {}, key = randomUUID()) {
    const accepted = await post(route, { path, header: { 'Idempotency-Key': key } });
    const run = await until(() => get(`${route}/{runId}`, undefined, { ...path, runId: accepted.id }),
      item => ['completed', 'failed'].includes(item.status), route);
    assert.equal(run.status, 'completed', `${route} ${run.id} ended ${run.status} (${run.error ?? 'no error code'})`);
    assert.equal(run.case_id, caseId);
    assertTimestamp(run.created_at); assertTimestamp(run.finished_at);
    const replay = await post(route, { path, header: { 'Idempotency-Key': key } });
    assert.deepEqual(replay, run, 'identical key replays the same completed run');
    return run;
  }
  async function rejectsStatus(action, status, code) {
    await assert.rejects(action, error => {
      assert.equal(error.status, status);
      if (code) assert.equal(error.apiError?.code, code);
      return true;
    });
  }
  async function analysisSnapshot(runId) {
    const query = { analysis_run_id: runId };
    return {
      run: await get('/analysis-runs/{runId}', undefined, { runId }),
      graph: await get('/graph', query), findings: await page('/findings', query),
      triage: await page('/triage', query),
    };
  }

  const fixture = name => readFile(new URL(`../../fixtures/synthetic-case/${name}`, import.meta.url));
  const sources = [
    { filename: 'network.csv', kind: 'network_log', contributesEvents: true, bytes: await fixture('network.csv'), keys: ['device:D-7', 'device:D-9'] },
    { filename: 'gps.csv', kind: 'gps', contributesEvents: true, bytes: await fixture('gps.csv'), keys: ['device:D-8'] },
    { filename: 'messages.csv', kind: 'message', contributesEvents: false,
      bytes: await fixture('messages.csv'), keys: ['device:D-7', 'device:D-8'] },
    { filename: 'mobile.csv', kind: 'mobile_log', contributesEvents: true,
      bytes: Buffer.from('timestamp,device_id,event,detail\n2026-11-01T10:04:00Z,D-7,call,Phone +15550100007 called\n'),
      keys: ['device:D-7'] },
    { filename: 'transactions.csv', kind: 'transaction', contributesEvents: true,
      bytes: Buffer.from('timestamp,account_id,amount,currency\n2026-11-01T10:05:00Z,AC-007,125.50,USD\n'),
      keys: ['account:AC-007'] },
    { filename: 'document.txt', kind: 'document', contributesEvents: false, type: 'text/plain',
      bytes: Buffer.from('Incident report regarding D-7 and D-8 on 2026-11-01.\nAccount AC-007 appears in this incident.\n'),
      keys: ['device:D-7', 'device:D-8', 'account:AC-007'] },
    { filename: 'audio.wav', kind: 'audio', type: 'audio/wav',
      bytes: process.env.EVORA_TEST_AUDIO ? await readFile(process.env.EVORA_TEST_AUDIO) : syntheticWav(), keys: [] },
  ];
  const processed = [];
  let structuredSnapshot;
  for (const source of sources) {
    const item = { source };
    await check(`${source.kind} intake`, async () => { item.evidence = await upload(source); });
    if (!item.evidence) continue;
    processed.push(item);
    if (source.kind === 'audio') {
      await check('audio.wav unsupported processing negative control', async () => {
        const before = privateRuns(caseId);
        await rejectsStatus(() => post('/evidence/{evidenceId}/processing-runs', {
          path: { evidenceId: item.evidence.id }, header: { 'Idempotency-Key': randomUUID() },
        }), 415, 'UNSUPPORTED_MEDIA');
        assert.deepEqual(await get('/evidence/{evidenceId}/processing-runs', undefined, { evidenceId: item.evidence.id }), []);
        assert.deepEqual(privateRuns(caseId), before, 'unsupported audio creates no runs, outputs or provenance');
      });
      await check('audio.wav explicit machine transcript fixture and provenance', async () => {
        const runId = seedMachineTranscript(caseId, item.evidence);
        item.run = await get('/evidence/{evidenceId}/processing-runs/{runId}', undefined,
          { evidenceId: item.evidence.id, runId });
        assert.equal(item.run.status, 'completed');
        assert.equal(item.run.processor_version, 'synthetic-asr-fixture/1');
        item.observations = await page('/observations', { evidence_id: item.evidence.id, processing_run_id: runId });
        assert.equal(item.observations.items.filter(value => value.kind === 'transcript.segment').length, 2);
        verifyProvenance(privateRuns(caseId)[runId], item.evidence, item.run);
      });
      continue;
    }
    await check(`${source.filename} processing, observations and provenance`, async () => {
      item.run = await completedRun('/evidence/{evidenceId}/processing-runs', { evidenceId: item.evidence.id });
      assert.equal(item.run.evidence_id, item.evidence.id);
      item.observations = await page('/observations', { evidence_id: item.evidence.id, processing_run_id: item.run.id });
      assert.ok(item.observations.total > 0, 'positive fixture must yield observations');
      for (const observation of item.observations.items) {
        assert.equal(observation.case_id, caseId);
        assert.equal(observation.evidence_id, item.evidence.id);
        assert.equal(observation.processing_run_id, item.run.id);
        assert.ok(observation.source_locator.trim());
        assert.equal(typeof observation.raw_value, 'string');
        assert.equal(typeof observation.normalized_value, 'string');
        assert.ok(observation.extraction_confidence >= 0 && observation.extraction_confidence <= 1);
      }
      verifyProvenance(privateRuns(caseId)[item.run.id], item.evidence, item.run);
    });
    if (source.kind === 'transaction') {
      // Exercise the registered structured producers before text/media intake.
      // The subsequent full snapshot must still succeed to pass the exit gate.
      await check('structured modalities graph, findings and triage baseline', async () => {
        const run = await completedRun('/analysis-runs');
        const output = await analysisSnapshot(run.id);
        const observations = await page('/observations');
        const entities = await page('/entities');
        const events = await page('/events');
        assert.deepEqual(run.input_snapshot.evidence_ids, ids(processed.map(item => item.evidence)));
        assert.deepEqual(run.input_snapshot.processing_run_ids, ids(processed.map(item => item.run)));
        assert.deepEqual(run.input_snapshot.observation_ids, ids(observations.items));
        assert.deepEqual(ids(output.graph.nodes), sorted([...run.input_snapshot.evidence_ids, ...ids(entities.items), ...ids(events.items)]));
        assert.ok(output.graph.edges.length > 0); assert.ok(output.findings.total > 0);
        const nodeIds = new Set(ids(output.graph.nodes));
        const observationIds = new Set(ids(observations.items));
        for (const record of [...output.graph.edges, ...output.findings.items]) {
          assert.equal(record.case_id, caseId);
          for (const id of record.observation_ids) assert.ok(observationIds.has(id));
          for (const id of record.evidence_ids) assert.ok(run.input_snapshot.evidence_ids.includes(id));
        }
        for (const edge of output.graph.edges) {
          assert.ok(nodeIds.has(edge.from_id)); assert.ok(nodeIds.has(edge.to_id));
        }
        assert.deepEqual(sorted(output.triage.items.map(item => item.evidence_id)), run.input_snapshot.evidence_ids);
        for (const entry of output.triage.items) {
          assert.ok(entry.latest_result);
          assert.equal(entry.latest_result.case_id, caseId);
          assert.equal(entry.latest_result.analysis_run_id, run.id);
          assert.ok(Number.isFinite(entry.latest_result.score));
        }
        structuredSnapshot = output;
      });
    }
  }

  await check('earlier structured analysis snapshot preserved after further intake', async () => {
    assert.ok(structuredSnapshot, 'structured baseline completed');
    assert.deepEqual(await analysisSnapshot(structuredSnapshot.run.id), structuredSnapshot);
  });

  const observations = await page('/observations');
  const entities = await page('/entities');
  const events = await page('/events');
  const observationById = new Map(observations.items.map(item => [item.id, item]));
  const entityById = new Map(entities.items.map(item => [item.id, item]));
  await check('same-case entity/event source joins', async () => {
    assert.ok(entities.total > 0); assert.ok(events.total > 0);
    for (const record of [...entities.items, ...events.items]) {
      assert.equal(record.case_id, caseId);
      assert.ok(record.observation_ids.length > 0);
      for (const id of record.observation_ids) {
        const observation = observationById.get(id);
        assert.ok(observation, 'source observation resolves through HTTP');
        assert.ok(record.evidence_ids.includes(observation.evidence_id));
      }
    }
    for (const event of events.items) {
      for (const id of event.entity_ids) {
        const entity = entityById.get(id);
        assert.ok(entity, 'event participant resolves through HTTP');
        assert.ok(entity.observation_ids.some(id => event.observation_ids.includes(id)));
      }
    }
  });
  for (const item of processed.filter(item => item.run)) {
    await check(`${item.source.filename} expected entities and event contract`, async () => {
      const candidates = entities.items.filter(entity => entity.evidence_ids.includes(item.evidence.id));
      for (const key of item.source.keys) assert.ok(candidates.some(entity => entity.candidate_key === key), key);
      if (item.source.contributesEvents === true) {
        assert.ok(events.items.some(event => event.evidence_ids.includes(item.evidence.id)),
          `${item.source.filename} must contribute events`);
      } else if (item.source.contributesEvents === false) {
        assert.ok(!events.items.some(event => event.evidence_ids.includes(item.evidence.id)),
          `${item.source.filename} extracts candidate mentions without events`);
      }
    });
  }

  let analysisRun;
  let snapshot;
  const analysisKey = randomUUID();
  await check('analysis snapshot, graph, findings and computed triage', async () => {
    analysisRun = await completedRun('/analysis-runs', {}, analysisKey);
    snapshot = await analysisSnapshot(analysisRun.id);
    assert.deepEqual(analysisRun.input_snapshot.evidence_ids, ids(processed.map(item => item.evidence)));
    assert.deepEqual(analysisRun.input_snapshot.processing_run_ids, ids(processed.filter(item => item.run).map(item => item.run)));
    assert.deepEqual(analysisRun.input_snapshot.observation_ids, ids(observations.items));
    const { graph, findings, triage } = snapshot;
    assert.equal(graph.case_id, caseId); assert.equal(graph.analysis_run_id, analysisRun.id);
    assert.deepEqual(ids(graph.nodes), sorted([...processed.map(item => item.evidence.id), ...ids(entities.items), ...ids(events.items)]));
    const nodes = new Map(graph.nodes.map(node => [node.id, node]));
    assert.ok(graph.edges.length > 0); assert.ok(findings.total > 0);
    const linkedEvidence = new Set();
    for (const record of [...graph.edges, ...findings.items]) {
      assert.equal(record.case_id, caseId);
      assert.ok(record.evidence_ids.length > 0); assert.ok(record.observation_ids.length > 0);
      for (const id of record.evidence_ids) {
        assert.ok(processed.some(item => item.evidence.id === id)); linkedEvidence.add(id);
      }
      for (const id of record.observation_ids) assert.ok(observationById.has(id));
    }
    for (const edge of graph.edges) {
      assert.ok(nodes.has(edge.from_id)); assert.ok(nodes.has(edge.to_id));
    }
    for (const finding of findings.items) assert.equal(finding.analysis_run_id, analysisRun.id);
    for (const item of processed.filter(item => item.source.keys.length)) {
      assert.ok(linkedEvidence.has(item.evidence.id), `${item.source.filename} contributes a candidate link`);
    }
    assert.equal(triage.analysis_run_id, analysisRun.id);
    assert.deepEqual(sorted(triage.items.map(item => item.evidence_id)), analysisRun.input_snapshot.evidence_ids);
    for (const item of processed.filter(item => item.run)) {
      const result = triage.items.find(entry => entry.evidence_id === item.evidence.id)?.latest_result;
      assert.ok(result, `${item.source.filename} has computed triage`);
      assert.equal(result.case_id, caseId); assert.equal(result.analysis_run_id, analysisRun.id);
      assert.ok(Number.isFinite(result.score));
      const history = await get('/evidence/{evidenceId}/triage-history', undefined, { evidenceId: item.evidence.id });
      assert.deepEqual(history.at(-1), result);
      for (const [index, entry] of history.entries()) {
        assert.equal(entry.evidence_id, item.evidence.id);
        assertTimestamp(entry.created_at);
        if (index) assert.ok(Date.parse(history[index - 1].created_at) <= Date.parse(entry.created_at));
      }
      if (item.source.filename === 'network.csv') assert.ok(history.length >= 2);
    }
  });

  await check('transcript local search and source playback locators over HTTP observations', async () => {
    const audio = processed.find(item => item.source.kind === 'audio');
    assert.ok(audio?.run, 'explicit machine transcript fixture is persisted');
    let requests = 0;
    const transcriptClient = createApiClient({ baseUrl: origin, fetch: (url, options) => {
      requests++;
      return transport(url, options);
    } });
    transcriptClient.setToken('u02-synthetic-two');
    const controller = createTranscriptController(transcriptClient, audio.evidence);
    const render = () => renderToStaticMarkup(createElement(TranscriptPanel, {
      ...controller, state: controller.getSnapshot(), mediaKind: 'audio', filename: audio.evidence.filename,
    }));
    controller.start();
    try {
      const state = await until(async () => controller.getSnapshot(), value => value.status !== 'loading', 'transcript controller');
      assert.equal(state.status, 'ready');
      assert.deepEqual(state.segments.map(segment => segment.source_locator),
        ['media:start_ms=0;end_ms=1000', 'media:start_ms=1000;end_ms=2000']);
      const initial = render();
      for (const text of ['Machine D-7 spoke.', 'Other D-8 replied.', '2 of 2 transcript segments',
        '00:00:00.000', '00:00:01.000', '00:00:02.000', '1000–2000 ms from original media start']) {
        assert.ok(initial.includes(text), text);
      }
      const beforeSearch = requests;
      controller.setQuery(' d-8 ');
      assert.match(render(), /1 of 2 transcript segments/);
      assert.match(render(), /<mark>D-8<\/mark>/);
      assert.doesNotMatch(render(), /Machine D-7 spoke/);
      controller.setQuery('absent phrase');
      assert.match(render(), /No transcript segments match your search/);
      controller.setQuery('');
      assert.match(render(), /2 of 2 transcript segments/);
      assert.equal(requests, beforeSearch, 'local search makes no HTTP requests');
      await controller.download();
      assert.equal(controller.getSnapshot().media.status, 'ready');
      assert.match(render(), /<audio controls="" preload="metadata" src="blob:/);
      const media = await fetch(controller.getSnapshot().sourceUrl);
      assert.deepEqual(Buffer.from(await media.arrayBuffer()), audio.source.bytes);
    } finally {
      controller.dispose();
    }
  });

  await check('transcript revision chain, safe audit and immutable machine/analysis history', async () => {
    const audio = processed.find(item => item.source.kind === 'audio');
    assert.ok(audio?.run, 'explicit machine transcript fixture is persisted');
    assert.ok(snapshot, 'completed analysis snapshot is required');
    const source = audio.observations.items.find(item => item.kind === 'transcript.segment');
    assert.ok(source, 'fixture transcript segment resolves through HTTP');
    const path = { observationId: source.id };
    const route = '/observations/{observationId}/transcript-revisions';
    assert.deepEqual((await page(route, {}, path)).items, []);
    const before = privateRuns(caseId);
    let preserved = before;
    const revisions = [];
    let base = audio.run.id;
    for (const corrected_text of ['Corrected incident report regarding D-7.', 'Corrected incident report regarding D-7 and D-8.']) {
      const body = { processing_run_id: audio.run.id, base_processing_run_id: base,
        expected_latest_revision_id: revisions.at(-1)?.id ?? null, corrected_text, reason: 'Checked against original source playback.' };
      const options = { path, body, header: { 'Idempotency-Key': randomUUID() } };
      const revision = await post(route, options);
      assert.deepEqual(await post(route, options), revision, 'correction replay appends nothing');
      assert.equal(revision.previous_revision_id, revisions.at(-1)?.id ?? null);
      assert.equal(revision.actor_id, 'investigator-2'); assertTimestamp(revision.created_at);
      assert.equal(revision.case_id, caseId); assert.equal(revision.evidence_id, audio.evidence.id);
      assert.equal(revision.source_observation_id, source.id);
      assert.equal(revision.processing_run_id, audio.run.id);
      assert.equal(revision.base_processing_run_id, base);
      assert.equal(revision.corrected_text, corrected_text); assert.equal(revision.reason, body.reason);
      const effective = await page('/observations', { evidence_id: audio.evidence.id, processing_run_id: revision.derived_processing_run_id });
      const segment = effective.items.find(item => item.id === revision.derived_observation_id);
      assert.ok(segment); assert.equal(segment.normalized_value, corrected_text);
      for (const field of ['raw_value', 'source_locator', 'extraction_confidence']) assert.equal(segment[field], source[field]);
      assert.equal(segment.source_observation_id, source.id); assert.equal(segment.transcript_revision_id, revision.id);
      const derivedRun = await get('/evidence/{evidenceId}/processing-runs/{runId}', undefined,
        { evidenceId: audio.evidence.id, runId: revision.derived_processing_run_id });
      assert.equal(derivedRun.status, 'completed');
      const persisted = privateRuns(caseId);
      verifyProvenance(persisted[derivedRun.id], audio.evidence, derivedRun);
      for (const [id, record] of Object.entries(preserved)) assert.deepEqual(persisted[id], record,
        'each correction preserves every prior machine and derived output/provenance');
      preserved = persisted;
      revisions.push(revision); base = revision.derived_processing_run_id;
      await rejectsStatus(() => post(route, { ...options, header: { 'Idempotency-Key': randomUUID() } }), 409);
    }
    assert.deepEqual((await page(route, {}, path)).items, revisions);
    const audit = await page('/audit-events');
    const corrections = audit.items.filter(item => item.action === 'appendTranscriptRevision');
    assert.equal(corrections.length, 2);
    for (const revision of revisions) {
      const event = corrections.find(item => item.target_id === revision.id);
      assert.ok(event); assert.equal(event.actor_id, revision.actor_id);
      assert.equal(event.case_id, caseId); assert.equal(event.created_at, revision.created_at);
      assert.deepEqual(sorted(Object.keys(event)), sorted(['id', 'case_id', 'actor_id', 'action', 'target_id', 'created_at']));
      assert.equal(event.reason, undefined, 'correction reason is private');
      for (const secret of [source.raw_value, revision.corrected_text, revision.reason, 'u02-synthetic-two']) {
        assert.ok(!JSON.stringify(audit).includes(secret), 'all audit events exclude text, reason and bearer token');
      }
    }
    const after = privateRuns(caseId);
    for (const [id, record] of Object.entries(before)) assert.deepEqual(after[id], record, 'earlier persisted runs/outputs/provenance unchanged');
    assert.deepEqual(await page('/observations', { evidence_id: audio.evidence.id, processing_run_id: audio.run.id }), audio.observations);
    const original = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
      path: { caseId, evidenceId: audio.evidence.id }, responseType: 'blob',
    });
    assert.deepEqual(Buffer.from(await original.arrayBuffer()), audio.source.bytes, 'corrections preserve original media bytes');
    assert.deepEqual(await analysisSnapshot(analysisRun.id), snapshot, 'pinned analysis outputs and frozen inputs unchanged');
    assert.deepEqual(await post('/analysis-runs', { header: { 'Idempotency-Key': analysisKey } }), analysisRun);
    const newer = await completedRun('/analysis-runs');
    assert.ok(newer.input_snapshot.processing_run_ids.includes(base));
    assert.ok(!newer.input_snapshot.processing_run_ids.includes(audio.run.id));
    assert.deepEqual(await analysisSnapshot(analysisRun.id), snapshot, 'new analysis preserves prior snapshot');
  });

  await check('foreign case, evidence and run access rejected', async () => {
    const other = createApiClient({ baseUrl: origin, fetch: transport });
    other.setToken('u02-synthetic-one');
    const { id: foreignId } = await other.request('post', '/api/v1/cases', { body: { title: 'Foreign I03B control' } });
    for (const route of ['/observations', '/entities', '/events', '/graph', '/findings', '/triage', '/audit-events']) {
      await rejectsStatus(() => get(route, undefined, { caseId: foreignId }), 404, 'NOT_FOUND');
    }
    const item = processed.find(item => item.run);
    assert.ok(item);
    for (const [method, route, options] of [
      ['get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', {}],
      ['get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {}],
      ['post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { header: { 'Idempotency-Key': randomUUID() } }],
    ]) {
      await rejectsStatus(() => other.request(method, route, { ...options,
        path: { caseId, evidenceId: item.evidence.id, runId: item.run.id } }), 404);
      // Authorized case with an evidence/run ID belonging to another case.
      await rejectsStatus(() => other.request(method, route, { ...options,
        path: { caseId: foreignId, evidenceId: item.evidence.id, runId: item.run.id } }), 404);
    }
    const observationId = item.observations.items[0].id;
    await rejectsStatus(() => other.request('get', '/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions', {
      path: { caseId: foreignId, observationId },
    }), 404);
    await rejectsStatus(() => other.request('post', '/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions', {
      path: { caseId, observationId }, header: { 'Idempotency-Key': randomUUID() },
      body: { processing_run_id: item.run.id, base_processing_run_id: item.run.id,
        expected_latest_revision_id: null, corrected_text: 'Foreign control', reason: 'Access control' },
    }), 404);
  });

  await check('missing/invalid idempotency keys and unauthorized tokens rejected without side effects', async () => {
    const before = privateRuns(caseId);
    const runs = await get('/analysis-runs');
    const item = processed.find(item => item.run);
    for (const header of [undefined, { 'Idempotency-Key': '' }, { 'Idempotency-Key': 'x'.repeat(129) }]) {
      await rejectsStatus(() => post('/evidence/{evidenceId}/processing-runs', { path: { evidenceId: item.evidence.id }, header }), 400, 'INVALID_INPUT');
      await rejectsStatus(() => post('/analysis-runs', { header }), 400, 'INVALID_INPUT');
    }
    await rejectsStatus(() => post('/analysis-runs', { header: { 'Idempotency-Key': 'not-a-uuid' } }), 400);
    const revisionOptions = {
      path: { observationId: item.observations.items[0].id },
      body: { processing_run_id: item.run.id, base_processing_run_id: item.run.id,
        expected_latest_revision_id: null, corrected_text: 'Invalid control', reason: 'Negative control' },
    };
    for (const key of [undefined, '', 'not-a-uuid']) {
      await rejectsStatus(() => post('/observations/{observationId}/transcript-revisions', {
        ...revisionOptions, header: key === undefined ? undefined : { 'Idempotency-Key': key },
      }), 400);
    }
    await rejectsStatus(() => post('/observations/{observationId}/transcript-revisions', {
      ...revisionOptions, header: { 'Idempotency-Key': randomUUID() },
    }), 400, 'INVALID_INPUT');
    const unauthenticated = createApiClient({ baseUrl: origin, fetch: transport });
    await assert.rejects(() => unauthenticated.request('get', '/api/v1/cases', {}), error => error.kind === 'authentication');
    unauthenticated.setToken('i03b-unknown-token');
    await rejectsStatus(() => unauthenticated.request('post', '/api/v1/cases/{caseId}/analysis-runs', {
      path: { caseId }, header: { 'Idempotency-Key': randomUUID() },
    }), 401, 'UNAUTHORIZED');
    assert.equal(unauthenticated.hasToken(), false);
    // A raw request verifies server-side missing-token rejection too.
    assert.equal((await fetch(`${origin}/api/v1/cases/${caseId}/observations`, { signal: AbortSignal.timeout(5000) })).status, 401);
    assert.deepEqual(privateRuns(caseId), before);
    assert.deepEqual(await get('/analysis-runs'), runs);
  });

  await check('malformed and unsupported input fails safely without partial outputs', async () => {
    const before = privateRuns(caseId);
    const beforeObservations = await page('/observations');
    await rejectsStatus(() => upload({ filename: 'unknown.bin', kind: 'unsupported_kind', bytes: Buffer.from('unknown kind') }), 400, 'INVALID_INPUT');
    const bad = await upload({ filename: 'malformed.csv', kind: 'network_log', bytes: Buffer.from('wrong,headers\nprivate-malformed-content,value\n') });
    const accepted = await post('/evidence/{evidenceId}/processing-runs', {
      path: { evidenceId: bad.id }, header: { 'Idempotency-Key': randomUUID() },
    });
    const run = await until(() => get('/evidence/{evidenceId}/processing-runs/{runId}', undefined,
      { evidenceId: bad.id, runId: accepted.id }), item => ['failed', 'completed'].includes(item.status), 'malformed CSV');
    assert.equal(run.status, 'failed'); assert.equal(run.error, 'CSV_INVALID_HEADER');
    assert.ok(!JSON.stringify(run).includes('private-malformed-content'));
    await rejectsStatus(() => page('/observations', { evidence_id: bad.id, processing_run_id: run.id }), 404);
    assert.equal((await page('/observations', { evidence_id: bad.id })).total, 0);
    const unsupported = await upload({ filename: 'unsupported.bin', kind: 'image', type: 'application/octet-stream', bytes: Buffer.from('unsupported synthetic bytes') });
    await rejectsStatus(() => post('/evidence/{evidenceId}/processing-runs', {
      path: { evidenceId: unsupported.id }, header: { 'Idempotency-Key': randomUUID() },
    }), 415, 'UNSUPPORTED_MEDIA');
    assert.deepEqual(await get('/evidence/{evidenceId}/processing-runs', undefined, { evidenceId: unsupported.id }), []);
    const after = privateRuns(caseId);
    assert.equal(after[run.id].output, null); assert.equal(after[run.id].provenance, null);
    for (const [id, record] of Object.entries(before)) assert.deepEqual(after[id], record);
    assert.deepEqual(await page('/observations'), beforeObservations);
    if (snapshot) assert.deepEqual(await analysisSnapshot(analysisRun.id), snapshot);
  });

  await check('safe processing audit and preserved earlier completed analysis', async () => {
    const audit = await page('/audit-events');
    const serialized = JSON.stringify(audit);
    for (const secret of ['u02-synthetic-two', 'i03b-unknown-token', 'private-malformed-content',
      ...sources.map(source => source.filename),
      ...sources.filter(source => source.kind !== 'audio').map(source => source.bytes.toString('utf8').trim())]) {
      assert.ok(!serialized.includes(secret), 'audit excludes bearer tokens, filenames and source content');
    }
    for (const event of audit.items) {
      assert.equal(event.case_id, caseId); assert.equal(event.actor_id, 'investigator-2');
      assertTimestamp(event.created_at);
    }
    for (const item of processed.filter(item => item.run && item.source.kind !== 'audio')) {
      const matches = audit.items.filter(event => event.action === 'startProcessing' &&
        event.target_id === item.evidence.id && event.reason?.startsWith(`run:${item.run.id};status:completed;`));
      assert.equal(matches.length, 1, 'processing replay has exactly one completion audit');
    }
    assert.ok(structuredSnapshot);
    assert.deepEqual(await analysisSnapshot(structuredSnapshot.run.id), structuredSnapshot,
      'failed/unsupported input and subsequent analysis preserve the earlier completed snapshot');
  });

  if (failures.length) {
    process.exitCode = 1;
    console.error(`I03B full-modality gate failed (${failures.length} checks); Checkpoint 3C remains unsealed.`);
  } else {
    console.log('PASS I03B full-modality investigation HTTP tracer (explicit Neo4j double).');
    console.log('PASS I03B Checkpoint 3C sealed (explicit machine transcript fixture; audio dispatch remains unsupported).');
  }
} finally {
  clearTimeout(startupTimer);
  try {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
    try { await closed; } finally { clearTimeout(forceKill); }
  } finally {
    assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i03b-')));
    await rm(temporary, { recursive: true, force: true });
  }
}
