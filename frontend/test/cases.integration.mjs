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
import { createEvidenceStore, createProcessingController, createProcessingStatusController } from '../.test-build/src/cases/CaseWorkspace.mjs';

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
  await processing.submit();
  assert.notEqual(processing.getSnapshot().run.id, acceptedRun.id, 'new explicit action uses a new key/run');
  const path = { caseId: created.id, evidenceId: processingEvidence.id };
  await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path, header: { 'Idempotency-Key': '' } }), { status: 400 });
  await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { ...path, evidenceId: '00000000-0000-4000-8000-000000000000' }, header: { 'Idempotency-Key': crypto.randomUUID() } }), { status: 404 });
  processing.dispose();
  console.log('PASS U05C real P04 HTTP: synthetic network.csv upload, explicit keyed start 202/queued, exact completed run read-back, new-action/new-run and 400/404.');
  evidenceStore.dispose();
  const beforeDeniedAudit = intakeSnapshot();
  client.setToken('u02-synthetic-one'); await store.load();
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', { path: runPath }), { status: 404 });
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
} finally {
  child.kill(); await exited;
  // mkdtemp created this exact directory; only the owned synthetic database is removed.
  assert.ok(temporary.startsWith(join(tmpdir(), 'evora-u02-')));
  await rm(temporary, { recursive: true, force: true });
}
