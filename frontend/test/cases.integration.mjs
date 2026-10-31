import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createOriginalDownload } from '../.test-build/src/cases/downloadController.mjs';
import { createCaseStore } from '../.test-build/src/cases/store.mjs';
import { createEvidenceStore } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Run explicitly after npm test + build. Real HTTP, FastAPI and SQLite; synthetic identities/data only.
const temporary = await mkdtemp(join(tmpdir(), 'evora-u02-'));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
const child = spawn(python, ['test/serve-cases.py', '--database', join(temporary, 'cases.sqlite3')], { cwd: fileURLToPath(new URL('..', import.meta.url)), stdio: ['ignore', 'pipe', 'pipe'] });
let errors = '';
child.stderr.on('data', data => { errors += data; });
const exited = once(child, 'exit');
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
  console.log('PASS U04 real F05: original byte/hash/size read-back through download controller and empty original.');
  evidenceStore.dispose();
  client.setToken('u02-synthetic-one'); await store.load();
  assert.ok(store.getSnapshot().page.items.every(item => item.id !== created.id));
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence', { path: { caseId: created.id } }), { status: 404 });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId: created.id, evidenceId: evidence.id } }), { status: 404 });
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId: first.items[0].id, evidenceId: evidence.id } }), { status: 404 });
  const forbiddenOriginal = createOriginalDownload(client, evidence, () => { throw Error('Foreign original must not save'); });
  await forbiddenOriginal.download(); assert.equal(forbiddenOriginal.getSnapshot().status, 'error'); assert.match(forbiddenOriginal.getSnapshot().message, /unavailable/); forbiddenOriginal.dispose();
  await assert.rejects(client.request('get','/api/v1/cases/{caseId}/evidence/{evidenceId}/content',{path:{caseId:created.id,evidenceId:evidence.id},responseType:'blob'}),{status:404});
  console.log('PASS U03 real HTTP/FastAPI/SQLite: multipart 201, exact SHA-256/size/list/detail/acquired UTC, local validation, server blank-label/invalid-kind 400, oversize 413, case/actor isolation 404.');
  client.setToken('invalid-synthetic-token'); await store.load();
  assert.equal(client.hasToken(), false); await store.load(); assert.equal(store.getSnapshot().status, 'signed-out');
  store.dispose();
  console.log('PASS U02/U02B creation 201, immediate listing, whitespace 400, actor isolation; real HTTP/SQLite: empty, 21-case pagination/detail, two-actor isolation, foreign/missing 404, invalid limit 400, invalid token 401, same-origin UI HTTP 200.');
} finally {
  child.kill(); await exited;
  // mkdtemp created this exact directory; only the owned synthetic database is removed.
  assert.ok(temporary.startsWith(join(tmpdir(), 'evora-u02-')));
  await rm(temporary, { recursive: true, force: true });
}
