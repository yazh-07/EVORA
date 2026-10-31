import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createCaseStore } from '../.test-build/src/cases/store.mjs';

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
  client.setToken('u02-synthetic-one'); await store.load();
  assert.ok(store.getSnapshot().page.items.every(item => item.id !== created.id));
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
