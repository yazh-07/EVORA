import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync, spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createOriginalDownload } from '../.test-build/src/cases/downloadController.mjs';
import { createCaseStore } from '../.test-build/src/cases/store.mjs';
import { createAnalysisController, createEvidenceStore, createProcessingController, createProcessingStatusController, createObservationController, createCaseOverviewController } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Run explicitly after npm test + build. Real HTTP, FastAPI and SQLite; synthetic identities/data only.
const temporary = await mkdtemp(join(tmpdir(), 'evora-u02-'));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
const child = spawn(python, ['test/serve-cases.py', '--database', join(temporary, 'cases.sqlite3')], { cwd: fileURLToPath(new URL('..', import.meta.url)), stdio: ['ignore', 'pipe', 'pipe'] });
let errors = '';
child.stderr.on('data', data => { errors += data; });
const exited = once(child, 'exit');
// Harness-only read-back: application UI/client still accesses data through HTTP.
const intakeSnapshot = () => execFileSync(python, ['-c', `
import hashlib, json, pathlib, sqlite3, sys
root = pathlib.Path(sys.argv[1])
connection = sqlite3.connect((root / 'cases.sqlite3').as_uri() + '?mode=ro', uri=True)
try:
    sql = list(connection.iterdump())
finally:
    connection.close()
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted((root / 'evidence').rglob('*')) if p.is_file()}
print(json.dumps([sql, files], sort_keys=True))
`, temporary], { encoding: 'utf8' });
const auditFailures = [];
const expectAuditEvent = (page, action, targetId, caseId) => {
  // Collect producer mismatches so the rest of the real intake smoke still runs.
  try {
    assert.ok(page.items.some(event => event.action === action && event.target_id === targetId &&
      event.actor_id === 'investigator-2' && event.case_id === caseId),
    `Expected ${action} audit event for its target and investigator-2; received actions: ${page.items.map(event => event.action).join(', ') || '(none)'}`);
  } catch (error) { auditFailures.push(error); }
};
try {
  const origin = await new Promise((resolveUrl, reject) => {
    const timer = setTimeout(() => reject(Error('Integration server startup timeout: ' + errors)), 15000);
    let stdout = '';
    child.stdout.on('data', data => {
      stdout += data;
      const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
      if (found) { clearTimeout(timer); resolveUrl(found[1]); }
    });
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', () => { clearTimeout(timer); reject(Error('Integration server exited: ' + errors)); });
  });
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try { ready = (await fetch(origin + '/')).status === 200; } catch {}
    if (ready) break;
    await new Promise(resolveDelay => setTimeout(resolveDelay, 50));
  }
  assert.ok(ready, 'built UI is served on the real API origin');
  const statuses = [];
  const client = createApiClient({ baseUrl: origin, fetch: async (...args) => {
    const response = await fetch(...args);
    statuses.push({ method: args[1].method, status: response.status });
    return response;
  } });
  client.setToken('u02-synthetic-two');
  const listAuditEvents = caseId => client.request('get', '/api/v1/cases/{caseId}/audit-events', { path: { caseId } });
  const store = createCaseStore(client);
  await store.load(); assert.equal(store.getSnapshot().page.total, 0);
  const foreign = await client.request('post', '/api/v1/cases', { body: { title: 'Synthetic actor-two private case' } });
  client.setToken('u02-synthetic-one');
  for (let index = 0; index < 21; index++) {
    await client.request('post', '/api/v1/cases', { body: { title: `Synthetic U02 case ${index}`, description: 'Synthetic permitted fixture only' } });
  }
  await store.load();
  const first = store.getSnapshot().page;
  assert.equal(first.total, 21); assert.equal(first.items.length, 20);
  assert.ok(first.items.every(item => item.id !== foreign.id));
  await store.select(first.items[0].id);
  assert.equal(store.getSnapshot().detail.id, first.items[0].id);
  await store.load(20);
  const second = store.getSnapshot().page;
  assert.equal(second.items.length, 1);
  assert.ok(!first.items.some(item => item.id === second.items[0].id));
  await store.load(40); assert.equal(store.getSnapshot().page.items.length, 0);
  const denied = async id => {
    try { await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: id } }); assert.fail('Expected 404'); }
    catch (error) { assert.equal(error.status, 404); return error.apiError; }
  };
  assert.deepEqual(await denied(foreign.id), await denied('00000000-0000-4000-8000-000000000000'));
  await assert.rejects(client.request('get', '/api/v1/cases', { query: { limit: 0 } }), { status: 400 });
  client.setToken('u02-synthetic-two'); await store.load();
  assert.equal(store.getSnapshot().page.total, 1);
  assert.equal(store.getSnapshot().page.items[0].id, foreign.id);
  statuses.length = 0;
  assert.equal(await store.create('   ', ''), false);
  assert.equal(statuses.length, 0);
  assert.equal(await store.create('Synthetic U02B created case', 'Synthetic description'), true);
  const created = store.getSnapshot().detail;
  assert.equal(created.title, 'Synthetic U02B created case');
  assert.equal(created.description, 'Synthetic description');
  assert.ok(statuses.some(item => item.method === 'POST' && item.status === 201));
  const beforeCreationAudit = intakeSnapshot();
  const creationAudit = await listAuditEvents(created.id);
  assert.deepEqual(await listAuditEvents(created.id), creationAudit);
  assert.equal(intakeSnapshot(), beforeCreationAudit, 'case audit listing changes no SQL records or original bytes');
  assert.equal(creationAudit.total, 0, 'case creation performs no intake and emits no intake audit events');
  const listed = await client.request('get', '/api/v1/cases', { query: { limit: 20, offset: 0 } });
  assert.ok(listed.items.some(item => item.id === created.id));
  await assert.rejects(client.request('post', '/api/v1/cases', { body: { title: '   ' } }), { status: 400 });
  assert.equal(await store.create(String.fromCodePoint(0x1f9ea).repeat(200), 'd'.repeat(5000)), true);
  const unicodeCase = store.getSnapshot().detail;
  assert.equal(Array.from(unicodeCase.title).length, 200);
  assert.equal(unicodeCase.description.length, 5000);
  assert.equal(await store.create(unicodeCase.title + 'x', ''), false);
  const evidenceStore = createEvidenceStore(client, created.id);
  await evidenceStore.load(); assert.equal(evidenceStore.getSnapshot().page.total, 0);
  const bytes = new TextEncoder().encode('Synthetic U03 evidence bytes\n');
  statuses.length = 0;
  assert.equal(await evidenceStore.upload(null, 'network_log', 'source'), false);
  assert.equal(await evidenceStore.upload(new File([bytes], 'network.csv'), 'network_log', '   '), false);
  assert.equal(statuses.length, 0);
  assert.equal(await evidenceStore.upload(new File([bytes], 'network.csv', { type: 'text/csv' }), 'network_log', 'Synthetic U03 source', '2026-10-31T12:34'), true);
  assert.ok(statuses.some(item => item.method === 'POST' && item.status === 201));
  const evidence = evidenceStore.getSnapshot().detail;
  assert.equal(evidence.sha256, createHash('sha256').update(bytes).digest('hex'));
  assert.equal(evidence.size_bytes, bytes.length);
  assert.equal(evidence.acquired_at, '2026-10-31T12:34:00Z');
  const beforeUploadAudit = intakeSnapshot();
  const uploadAudit = await listAuditEvents(created.id);
  assert.deepEqual(await listAuditEvents(created.id), uploadAudit);
  assert.equal(intakeSnapshot(), beforeUploadAudit, 'upload audit listing is strictly read-only');
  expectAuditEvent(uploadAudit, 'uploadEvidence', evidence.id, created.id);
  assert.ok(uploadAudit.items.length > 0, 'real intake produces audit records');
  assert.deepEqual(uploadAudit.items.filter(event => creationAudit.items.some(old => old.id === event.id)), creationAudit.items);
  assert.deepEqual(evidenceStore.getSnapshot().page.items[0], evidence);
  await evidenceStore.select(evidence.id);
  assert.deepEqual(evidenceStore.getSnapshot().detail, evidence);
  for (const [kind, label] of [['network_log', '   '], ['unsupported', 'source']]) {
    const body = new FormData(); body.set('file', new File([bytes], 'network.csv')); body.set('kind', kind); body.set('source_label', label);
    await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/evidence', { path: { caseId: created.id }, body }), { status: 400 });
  }
  // Actual F03 byte limit, not a simulated transport error.
  assert.equal(await evidenceStore.upload(new File([new Uint8Array(50 * 1024 * 1024 + 1)], 'large.bin'), 'document', 'Synthetic oversize'), false);
  assert.equal(evidenceStore.getSnapshot().uploadMessage, 'Upload exceeds configured limit.');
  await evidenceStore.load(); assert.equal(evidenceStore.getSnapshot().page.total, 1);
  let savedBytes = null;
  const originalDownload = createOriginalDownload(client, evidence, blob => {
    savedBytes = blob; return () => {};
  });
  await originalDownload.download();
  assert.equal(originalDownload.getSnapshot().status, 'ready');
  assert.deepEqual(new Uint8Array(await savedBytes.arrayBuffer()), bytes);
  assert.equal(createHash('sha256').update(new Uint8Array(await savedBytes.arrayBuffer())).digest('hex'), evidence.sha256);
  originalDownload.dispose();
  const emptyBody = new FormData(); emptyBody.set('file', new File([], 'empty.bin')); emptyBody.set('kind', 'document'); emptyBody.set('source_label', 'Synthetic empty original');
  const emptyEvidence = await client.request('post', '/api/v1/cases/{caseId}/evidence', {path:{caseId:created.id},body:emptyBody});
  let emptySaved = false;
  const emptyDownload = createOriginalDownload(client, emptyEvidence, blob => { assert.equal(blob.size,0); emptySaved=true;return ()=>{}; });
  await emptyDownload.download(); assert.equal(emptySaved,true); emptyDownload.dispose();
  const beforeCompleteAudit = intakeSnapshot();
  const completeAudit = await listAuditEvents(created.id);
  assert.equal(completeAudit.total, creationAudit.total + 2, 'only the two successful uploads append intake events');
  assert.equal(completeAudit.items.length, completeAudit.total);
  assert.deepEqual(await listAuditEvents(created.id), completeAudit);
  assert.equal(intakeSnapshot(), beforeCompleteAudit, 'repeated audit listing changes no SQL records or original bytes');
  let previousTimestamp = '';
  for (const event of completeAudit.items) {
    assert.equal(event.case_id, created.id);
    assert.equal(event.actor_id, 'investigator-2');
    assert.deepEqual(Object.keys(event).sort(), ['action', 'actor_id', 'case_id', 'created_at', 'id', 'target_id']);
    assert.match(event.created_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/);
    assert.ok(Number.isFinite(Date.parse(event.created_at)), 'valid UTC RFC3339 timestamp');
    // Normalize fractions without losing the microsecond precision to Date.parse.
    const [seconds, fraction = ''] = event.created_at.slice(0, -1).split('.');
    const timestamp = seconds + '.' + fraction.padEnd(9, '0');
    assert.ok(timestamp >= previousTimestamp, 'audit timestamps are monotonically nondecreasing');
    previousTimestamp = timestamp;
  }
  console.log('PASS U04 real F05: original byte/hash/size read-back through download controller and empty original.');
  // U05C: real merged P04 producer, committed permitted CSV and generated client.
  const network = await readFile(new URL('../../fixtures/synthetic-case/network.csv', import.meta.url));
  assert.equal(await evidenceStore.upload(new File([network], 'network.csv', { type: 'text/csv' }), 'network_log', 'Synthetic U05C network', ''), true);
  const processingEvidence = evidenceStore.getSnapshot().detail;
  const processing = createProcessingController(client, created.id, processingEvidence.id);
  statuses.length = 0;
  await processing.submit();
  assert.equal(processing.getSnapshot().status, 'accepted');
  const acceptedRun = processing.getSnapshot().run;
  assert.equal(acceptedRun.case_id, created.id);
  assert.equal(acceptedRun.evidence_id, processingEvidence.id);
  assert.equal(acceptedRun.status, 'queued');
  assert.ok(statuses.some(item => item.method === 'POST' && item.status === 202));
  const runPath = { caseId: created.id, evidenceId: processingEvidence.id, runId: acceptedRun.id };
  const statusController = createProcessingStatusController(client, acceptedRun, 10);
  let readBack;
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(Error('U05 real processing status timeout')), 10000);
      const off = statusController.subscribe(() => {
        const state = statusController.getSnapshot();
        if (state.message || state.run?.status === 'completed' || state.run?.status === 'failed') {
          clearTimeout(timeout); off();
          if (state.message) reject(Error(state.message));
          else { readBack = state.run; resolve(); }
        }
      });
      statusController.start();
    });
    assert.equal(readBack.id, acceptedRun.id);
    assert.equal(readBack.case_id, created.id);
    assert.equal(readBack.evidence_id, processingEvidence.id);
    assert.equal(readBack.processor_version, acceptedRun.processor_version);
    assert.ok(readBack.processor_version.length > 0);
    assert.equal(readBack.status, 'completed');
    assert.ok(Number.isFinite(Date.parse(readBack.finished_at)));
    assert.deepEqual(await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', { path: runPath }), readBack,
      'terminal finished_at and all fields equal real API read-back');
    const requestCount = statuses.length;
    await new Promise(resolve => setTimeout(resolve, 40));
    assert.equal(statuses.length, requestCount, 'terminal controller stops polling real HTTP');
  } finally { statusController.dispose(); }
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
    path: { ...runPath, runId: '00000000-0000-4000-8000-000000000000' },
  }), { status: 404 });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
    path: { ...runPath, caseId: first.items[0].id },
  }), { status: 404 });
  console.log('PASS U05 real P04: status controller polls exact case/evidence/run to completed, version/finished_at read-back, terminal stop, missing-run/foreign-case 404.');
  // U05B: real P04B outputs, exact physical source locators/raw values, no SQL output doubles.
  const observationQuery = { evidence_id: processingEvidence.id };
  const observations = query => client.request('get', '/api/v1/cases/{caseId}/observations', {
    path: { caseId: created.id }, query: { ...observationQuery, ...query },
  });
  const latestObservations = await observations({ limit: 20, offset: 0 });
  assert.equal(latestObservations.total, 6);
  const expectedSources = [
    ['network.device', 'row 2, device_id', 'D-7'],
    ['network.ip', 'row 2, ip_address', '203.0.113.7'],
    ['network.event', 'row 2, event', 'connected'],
    ['network.device', 'row 3, device_id', 'D-9'],
    ['network.ip', 'row 3, ip_address', '203.0.113.9'],
    ['network.event', 'row 3, event', 'connected'],
  ];
  assert.deepEqual(latestObservations.items.map(item => [item.kind, item.source_locator, item.raw_value]).sort(), expectedSources.sort());
  for (const item of latestObservations.items) {
    assert.equal(item.case_id, created.id); assert.equal(item.evidence_id, processingEvidence.id);
    assert.equal(item.processing_run_id, acceptedRun.id); assert.equal(item.normalized_value, item.raw_value);
    assert.equal(item.observed_at_raw, item.source_locator.startsWith('row 2,') ? '2026-01-12T10:01:00Z' : '2026-01-12T10:02:00Z');
    assert.equal(item.observed_at_utc, item.observed_at_raw); assert.equal(item.extraction_confidence, 0);
  }
  const pinnedQuery = { processing_run_id: acceptedRun.id };
  const collected = [];
  for (const offset of [0, 2, 4, 6]) {
    const page = await observations({ ...pinnedQuery, limit: 2, offset });
    assert.deepEqual([page.total, page.limit, page.offset], [6, 2, offset]); collected.push(...page.items);
  }
  assert.deepEqual(collected, latestObservations.items); assert.equal(new Set(collected.map(item => item.id)).size, 6);
  const inspector = createObservationController(client, created.id, processingEvidence.id, acceptedRun.id);
  try { inspector.start(); await inspector.load(); assert.deepEqual(inspector.getSnapshot().page, latestObservations); }
  finally { inspector.dispose(); }
  const unprocessedObservations = await client.request('get', '/api/v1/cases/{caseId}/observations', {
    path: { caseId: created.id }, query: { evidence_id: emptyEvidence.id },
  });
  assert.equal(unprocessedObservations.total, 0); assert.deepEqual(unprocessedObservations.items, []);
  for (const query of [{ ...observationQuery, processing_run_id: '00000000-0000-4000-8000-000000000000' }, { ...observationQuery, limit: 0 }]) {
    await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/observations', { path: { caseId: created.id }, query }),
      { status: query.limit === 0 ? 400 : 404 });
  }
  await assert.rejects(observations({ evidence_id: emptyEvidence.id, ...pinnedQuery }), error => {
    assert.equal(error.status, 404); assert.deepEqual(error.apiError, { code: 'NOT_FOUND', message: 'Resource not found.' }); return true;
  });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/observations', {
    path: { caseId: first.items[0].id }, query: { ...observationQuery, ...pinnedQuery },
  }), error => {
    assert.equal(error.status, 404); assert.deepEqual(error.apiError, { code: 'NOT_FOUND', message: 'Resource not found.' }); return true;
  });
  console.log('PASS U05B real P04B: all six exact source/raw/normalized/time/confidence values, inspector read-back, pinned pagination without skips, honest empty output, invalid query/missing run/foreign case isolation.');

  // I00B: actual P05/P05B source joins and F08 terminal audit, no output doubles.
  const entities = await client.request('get', '/api/v1/cases/{caseId}/entities', { path: { caseId: created.id } });
  const events = await client.request('get', '/api/v1/cases/{caseId}/events', { path: { caseId: created.id } });
  assert.equal(entities.total, 4); assert.equal(entities.items.length, entities.total);
  assert.equal(events.total, 2); assert.equal(events.items.length, events.total);
  for (const label of ['D-7', 'D-9']) {
    assert.ok(entities.items.some(item => item.canonical_label === label && item.candidate_key === `device:${label}`));
  }
  const sourceById = new Map(latestObservations.items.map(item => [item.id, item]));
  for (const item of [...entities.items, ...events.items]) {
    assert.equal(item.case_id, created.id);
    assert.deepEqual(item.evidence_ids, [processingEvidence.id]);
    assert.ok(item.observation_ids.length > 0);
    assert.equal(new Set(item.observation_ids).size, item.observation_ids.length);
    for (const id of item.observation_ids) {
      const source = sourceById.get(id);
      assert.ok(source, 'every candidate source joins to this completed output');
      assert.equal(source.evidence_id, processingEvidence.id);
      assert.equal(source.processing_run_id, acceptedRun.id);
      assert.ok(source.source_locator.length > 0);
    }
  }
  assert.deepEqual(events.items.map(item => item.observed_at_utc).sort(), ['2026-01-12T10:01:00Z', '2026-01-12T10:02:00Z']);
  for (const event of events.items) {
    assert.equal(event.observed_at_raw, event.observed_at_utc);
    assert.ok(event.entity_ids.length > 0);
    assert.ok(event.entity_ids.every(id => entities.items.some(entity => entity.id === id)));
    assert.ok(event.observation_ids.some(id => sourceById.get(id).kind === 'network.event'));
  }
  const beforeProcessingAudit = intakeSnapshot();
  const processingAudit = await listAuditEvents(created.id);
  const terminalEvents = processingAudit.items.filter(event => event.action === 'startProcessing' &&
    event.target_id === processingEvidence.id);
  assert.equal(terminalEvents.length, 1, 'one terminal audit event for the first run');
  const [terminalEvent] = terminalEvents;
  assert.equal(terminalEvent.case_id, created.id);
  assert.equal(terminalEvent.actor_id, 'investigator-2');
  assert.equal(terminalEvent.created_at, readBack.finished_at);
  assert.equal(terminalEvent.reason, `run:${acceptedRun.id};status:completed;version:${readBack.processor_version}`,
    'safe reason contains only run/status/version references, no source content or private parameters');
  assert.deepEqual(Object.keys(terminalEvent).sort(), ['action', 'actor_id', 'case_id', 'created_at', 'id', 'reason', 'target_id']);
  assert.deepEqual(await listAuditEvents(created.id), processingAudit);
  assert.equal(intakeSnapshot(), beforeProcessingAudit, 'processing audit listing changes no persisted data');

  await processing.submit();
  assert.notEqual(processing.getSnapshot().run.id, acceptedRun.id, 'new explicit action uses a new key/run');
  const newerRun = processing.getSnapshot().run;
  for (let attempt = 0; ; attempt++) {
    const run = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
      path: { ...runPath, runId: newerRun.id },
    });
    if (run.status === 'completed') break;
    assert.notEqual(run.status, 'failed'); assert.ok(attempt < 100, 'new run completes');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  assert.deepEqual(await observations(pinnedQuery), latestObservations, 'historical completed output survives real newer completion');
  assert.ok((await observations()).items.every(item => item.processing_run_id === newerRun.id));
  const path = { caseId: created.id, evidenceId: processingEvidence.id };
  await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path, header: { 'Idempotency-Key': '' } }), { status: 400 });
  await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { ...path, evidenceId: '00000000-0000-4000-8000-000000000000' }, header: { 'Idempotency-Key': crypto.randomUUID() } }), { status: 404 });
  processing.dispose();
  console.log('PASS U05C real P04 HTTP: synthetic network.csv upload, explicit keyed start 202/queued, exact completed run read-back, new-action/new-run and 400/404.');
  // U13: all-page overview with real uploads and processing history, no SQL doubles.
  for (let index = 0; index < 20; index++) {
    assert.equal(await evidenceStore.upload(new File([bytes], `overview-${index}.bin`), 'image', 'Synthetic U13 image'), true);
  }
  const overview = createCaseOverviewController(client, created.id);
  overview.start(); await overview.load();
  assert.equal(overview.getSnapshot().status, 'ready');
  const summary = overview.getSnapshot().summary;
  assert.equal(summary.total, 23);
  assert.deepEqual(summary.kinds, { document: 1, image: 20, video: 0, audio: 0, message: 0, network_log: 2, mobile_log: 0, transaction: 0, gps: 0 });
  assert.deepEqual(summary.statuses, { completed: 1, running: 0, queued: 0, failed: 0, unprocessed: 22 });
  overview.dispose();
  const emptyOverview = createCaseOverviewController(client, unicodeCase.id);
  emptyOverview.start(); await emptyOverview.load(); assert.equal(emptyOverview.getSnapshot().summary.total, 0); emptyOverview.dispose();
  console.log('PASS U13 real HTTP/FastAPI: 23 evidence across two pages, exact kind/latest-status counts, 22 unprocessed and honest empty case.');
  // GPS uses the same real UI command/status/source controllers in a separate case
  // so U13's network-case all-page counts above remain an independent assertion.
  const gpsCase = await client.request('post', '/api/v1/cases', { body: { title: 'Synthetic I00B GPS case' } });
  const gpsStore = createEvidenceStore(client, gpsCase.id);
  const gpsBytes = await readFile(new URL('../../fixtures/synthetic-case/gps.csv', import.meta.url));
  assert.equal(await gpsStore.upload(new File([gpsBytes], 'gps.csv', { type: 'text/csv' }), 'gps', 'Synthetic I00B GPS'), true);
  const gpsEvidence = gpsStore.getSnapshot().detail;
  const gpsProcessing = createProcessingController(client, gpsCase.id, gpsEvidence.id);
  await gpsProcessing.submit();
  assert.equal(gpsProcessing.getSnapshot().status, 'accepted');
  const gpsRun = gpsProcessing.getSnapshot().run;
  const gpsStatus = createProcessingStatusController(client, gpsRun, 10);
  try {
    gpsStatus.start();
    for (let attempt = 0; ; attempt++) {
      const state = gpsStatus.getSnapshot();
      assert.equal(state.message, '');
      assert.notEqual(state.run?.status, 'failed');
      if (state.run?.status === 'completed') break;
      assert.ok(attempt < 200, 'GPS status controller reaches completion');
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    const gpsInspector = createObservationController(client, gpsCase.id, gpsEvidence.id, gpsRun.id);
    try {
      gpsInspector.start(); await gpsInspector.load();
      const page = gpsInspector.getSnapshot().page;
      assert.equal(page.total, 3);
      assert.deepEqual(page.items.map(item => [item.kind, item.source_locator, item.raw_value, item.normalized_value]).sort(), [
        ['gps.device', 'row 2, device_id', 'D-8', 'D-8'],
        ['gps.latitude', 'row 2, latitude', '12.9716', '12.9716'],
        ['gps.longitude', 'row 2, longitude', '77.5946', '77.5946'],
      ]);
      for (const item of page.items) {
        assert.equal(item.case_id, gpsCase.id); assert.equal(item.evidence_id, gpsEvidence.id);
        assert.equal(item.processing_run_id, gpsRun.id);
        assert.equal(item.observed_at_raw, '2026-01-12T10:02:00Z');
        assert.equal(item.observed_at_utc, item.observed_at_raw);
      }
      for (const route of ['/api/v1/cases/{caseId}/entities', '/api/v1/cases/{caseId}/events']) {
        const candidates = await client.request('get', route, { path: { caseId: gpsCase.id } });
        assert.equal(candidates.total, 1); assert.equal(candidates.items.length, 1);
        const [candidate] = candidates.items;
        assert.equal(candidate.case_id, gpsCase.id); assert.deepEqual(candidate.evidence_ids, [gpsEvidence.id]);
        assert.ok(candidate.observation_ids.length > 0);
        assert.ok(candidate.observation_ids.every(id => page.items.some(item => item.id === id)));
        if (route.endsWith('/entities')) assert.equal(candidate.candidate_key, 'device:D-8');
      }
    } finally { gpsInspector.dispose(); }
  } finally { gpsStatus.dispose(); gpsProcessing.dispose(); gpsStore.dispose(); }
  console.log('PASS I00B real GPS: UI start/poll/inspection, D-8 source-backed candidates, exact row/raw/normalized coordinates and UTC.');
  // U05D: real bodyless start + polling in both processed source cases.
  // The server uses an explicit Neo4j double; all other producers are real.
  const analysisRuns = [];
  for (const [caseId, evidenceId, processingRunId, observationCount] of [
    [created.id, processingEvidence.id, newerRun.id, 6],
    [gpsCase.id, gpsEvidence.id, gpsRun.id, 3],
  ]) {
    const analysis = createAnalysisController(client, caseId, 10);
    try {
      analysis.start(); await analysis.submit();
      for (let attempt = 0; ; attempt++) {
        const state = analysis.getSnapshot();
        assert.equal(state.message, ''); assert.notEqual(state.run?.status, 'failed');
        if (state.status === 'terminal') break;
        assert.equal(state.pinnedAnalysisRunId, null);
        assert.ok(attempt < 300, 'analysis completes');
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      const state = analysis.getSnapshot(); const completed = state.run;
      assert.equal(completed.status, 'completed');
      assert.equal(state.pinnedAnalysisRunId, completed.id);
      const path = { caseId, runId: completed.id };
      assert.deepEqual(await client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', { path }), completed);
      const snapshot = completed.input_snapshot;
      assert.equal(snapshot.case_id, caseId);
      assert.ok(snapshot.evidence_ids.includes(evidenceId));
      assert.deepEqual(snapshot.processing_run_ids, [processingRunId]);
      assert.equal(snapshot.observation_ids.length, observationCount);
      for (const ids of [snapshot.evidence_ids, snapshot.processing_run_ids, snapshot.observation_ids]) {
        assert.deepEqual(ids, [...new Set(ids)].sort());
      }
      const canonical = JSON.stringify({ case_id: caseId, evidence_ids: snapshot.evidence_ids,
        observation_ids: snapshot.observation_ids, processing_run_ids: snapshot.processing_run_ids });
      assert.equal(snapshot.sha256, createHash('sha256').update(canonical, 'utf8').digest('hex'));
      const requestCount = statuses.length; await new Promise(resolve => setTimeout(resolve, 40));
      assert.equal(statuses.length, requestCount, 'terminal analysis stops polling');
      for (const route of ['/api/v1/cases/{caseId}/graph', '/api/v1/cases/{caseId}/findings', '/api/v1/cases/{caseId}/triage']) {
        const page = await client.request('get', route, { path: { caseId }, query: { analysis_run_id: state.pinnedAnalysisRunId } });
        assert.equal(page.analysis_run_id, completed.id, 'real read agrees with workspace pin');
      }
      analysisRuns.push(path);
    } finally { analysis.dispose(); }
  }
  console.log('PASS U05D real HTTP/FastAPI/SQLite analysis: network/GPS frozen snapshots and SHA-256, completed pins, terminal stop, pinned graph/findings/triage. Neo4j is an explicit double.');
  evidenceStore.dispose();
  const beforeDeniedAudit = intakeSnapshot();
  client.setToken('u02-synthetic-one'); await store.load();
  for (const path of analysisRuns) {
    await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/analysis-runs/{runId}', { path }), { status: 404 });
  }
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', { path: runPath }), { status: 404 });
  for (const route of ['/api/v1/cases/{caseId}/entities', '/api/v1/cases/{caseId}/events']) {
    for (const caseId of [created.id, '00000000-0000-4000-8000-000000000000']) {
      await assert.rejects(client.request('get', route, { path: { caseId } }), error => {
        assert.equal(error.status, 404);
        assert.deepEqual(error.apiError, { code: 'NOT_FOUND', message: 'Resource not found.' });
        return true;
      });
    }
  }
  const foreignProcessing = createProcessingController(client, created.id, processingEvidence.id);
  await foreignProcessing.submit(); assert.equal(foreignProcessing.getSnapshot().status, 'error');
  assert.match(foreignProcessing.getSnapshot().message, /unavailable/); foreignProcessing.dispose();
  const deniedAudit = async caseId => {
    await assert.rejects(listAuditEvents(caseId), error => {
      assert.equal(error.status, 404);
      assert.deepEqual(error.apiError, { code: 'NOT_FOUND', message: 'Resource not found.' });
      return true;
    });
  };
  await deniedAudit(created.id);
  await deniedAudit(foreign.id);
  await deniedAudit('00000000-0000-4000-8000-000000000000');
  assert.equal(intakeSnapshot(), beforeDeniedAudit, 'foreign/missing audit reads change no SQL records or original bytes');
  console.log('PASS I00 audit transport: safe fields, UTC ordering, repeated read-only listing, actor isolation and identical foreign/missing 404 ApiError.');
  assert.ok(store.getSnapshot().page.items.every(item => item.id !== created.id));
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence', { path: { caseId: created.id } }), { status: 404 });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId: created.id, evidenceId: evidence.id } }), { status: 404 });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId: first.items[0].id, evidenceId: evidence.id } }), { status: 404 });
  const forbiddenOriginal = createOriginalDownload(client, evidence, () => { throw Error('Foreign original must not save'); });
  await forbiddenOriginal.download(); assert.equal(forbiddenOriginal.getSnapshot().status, 'error'); assert.match(forbiddenOriginal.getSnapshot().message, /unavailable/); forbiddenOriginal.dispose();
  await assert.rejects(client.request('get','/api/v1/cases/{caseId}/evidence/{evidenceId}/content',{path:{caseId:created.id,evidenceId:evidence.id},responseType:'blob'}),{status:404});
  console.log('PASS U03 real HTTP/FastAPI/SQLite: multipart 201, exact SHA-256/size/list/detail/acquired UTC, local validation, server blank-label/invalid-kind 400, oversize 413, case/actor isolation 404.');
  client.setToken('invalid-synthetic-token');
  const unauthorizedProcessing = createProcessingController(client, created.id, processingEvidence.id);
  await unauthorizedProcessing.submit(); assert.equal(unauthorizedProcessing.getSnapshot().status, 'error');
  assert.match(unauthorizedProcessing.getSnapshot().message, /Authentication required/); unauthorizedProcessing.dispose();
  client.setToken('invalid-synthetic-token');
  await store.load();
  assert.equal(client.hasToken(), false); await store.load(); assert.equal(store.getSnapshot().status, 'signed-out');
  store.dispose();
  console.log('PASS U02/U02B creation 201, immediate listing, whitespace 400, actor isolation; real HTTP/SQLite: empty, 21-case pagination/detail, two-actor isolation, foreign/missing 404, invalid limit 400, invalid token 401, same-origin UI HTTP 200.');
  if (auditFailures.length) throw new AggregateError(auditFailures, 'I00 audit producer acceptance failed; Checkpoint 1A cannot be sealed.');
  console.log('PASS I00 authorized intake gate, including uploadEvidence audit target/actor read-back.');
  console.log('PASS I00B verified first network/GPS processing and source inspection gate.');
} finally {
  child.kill(); await exited;
  // mkdtemp created this exact directory; only the owned synthetic database is removed.
  assert.ok(temporary.startsWith(join(tmpdir(), 'evora-u02-')));
  await rm(temporary, { recursive: true, force: true });
}
