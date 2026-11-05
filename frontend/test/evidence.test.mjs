import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createEvidenceStore, EvidencePanels } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import { caseA, caseB } from '../.test-build/test/fixtures/api.mjs';

const item = { id: '00000000-0000-4000-8000-000000000003', case_id: caseA.id, source_label: 'Synthetic source', kind: 'network_log', filename: 'network.csv', media_type: 'text/csv', size_bytes: 5, sha256: 'a'.repeat(64), created_at: '2026-10-31T00:00:00Z' };
const page = (items = [], offset = 0, total = items.length) => ({ items, limit: 20, offset, total });
const file = () => new File(['hello'], 'network.csv', { type: 'text/csv' });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function setup(fetch) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-one');
  return { client, store: createEvidenceStore(client, caseA.id) };
}
const renderClient = createApiClient({baseUrl:'http://127.0.0.1:8000'});
const render = store => renderToStaticMarkup(createElement(ApiProvider, {client:renderClient}, createElement(EvidencePanels, { state: store.getSnapshot(), load: store.load, select: store.select, upload: store.upload })));

test('selected-case evidence has labeled upload fields, honest empty state, and local validation', async () => {
  let calls = 0;
  const { store } = setup(async () => { calls++; return Response.json(page()); });
  await store.load();
  assert.match(render(store), /No evidence uploaded yet for this case/);
  for (const markup of [/type="file" required/, /maxLength="200"/i, /<select[^>]*required/, /Acquired at \(optional, UTC\)/, /Upload evidence/]) assert.match(render(store), markup);
  assert.equal((render(store).match(/<select id="evidence-kind"[\s\S]*?<\/select>/)[0].match(/<option /g) ?? []).length, 9);
  calls = 0;
  for (const args of [[null, 'document', 'label'], [file(), 'document', ' \t '], [file(), 'invalid', 'label'], [file(), 'audio', 'x'.repeat(201)], [file(), 'document', 'label', 'invalid']]) assert.equal(await store.upload(...args), false);
  assert.equal(calls, 0); assert.match(render(store), /role="alert"/);
  store.dispose();
});

test('uploadEvidence sends actual FormData bytes; busy prevents duplicates; success refreshes and inspects metadata', async () => {
  const wait = deferred(); const requests = [];
  const { store } = setup(async (url, options) => {
    requests.push({ url: String(url), ...options });
    return options.method === 'POST' ? wait.promise : Response.json(page([item]));
  });
  const pending = store.upload(file(), 'network_log', 'Synthetic source', '2026-10-31T12:34');
  assert.equal(store.getSnapshot().submitting, true);
  assert.match(render(store), /aria-busy="true"/); assert.match(render(store), /<fieldset disabled/);
  assert.match(render(store), /disabled="">Uploading evidence/);
  assert.equal(await store.upload(file(), 'document', 'duplicate'), false);
  assert.equal(requests.length, 1);
  const body = requests[0].body;
  assert.ok(body instanceof FormData); assert.equal(await body.get('file').text(), 'hello');
  assert.equal(body.get('file').name, 'network.csv'); assert.equal(body.get('kind'), 'network_log');
  assert.equal(body.get('source_label'), 'Synthetic source'); assert.equal(body.get('acquired_at'), '2026-10-31T12:34:00Z');
  assert.equal(requests[0].headers.has('Content-Type'), false);
  wait.resolve(Response.json(item, { status: 201 }));
  assert.equal(await pending, true);
  assert.equal(store.getSnapshot().submitting, false); assert.equal(store.getSnapshot().uploaded, true);
  assert.equal(store.getSnapshot().page.items[0].id, item.id);
  assert.match(render(store), new RegExp(item.sha256)); assert.match(render(store), /Size \(bytes\)<\/dt><dd>5/);
  assert.match(render(store), new RegExp(item.id)); assert.match(requests[1].url, /limit=20&offset=0/);
  store.dispose();
});

test('400, 413 and 415 server messages are escaped alerts and upload may retry', async () => {
  for (const status of [400, 413, 415]) {
    const { store } = setup(async () => Response.json({ code: 'INVALID_INPUT', message: `Upload ${status} <script>` }, { status }));
    assert.equal(await store.upload(file(), 'document', 'label'), false);
    assert.equal(store.getSnapshot().submitting, false);
    assert.match(render(store), new RegExp(`Upload ${status} &lt;script&gt;`));
    assert.doesNotMatch(render(store), /<script>/); assert.match(render(store), /role="alert"/);
    store.dispose();
  }
});

test('refresh failure preserves confirmed upload; optional timestamp omitted; unsafe metadata renders as text', async () => {
  const unsafe = { ...item, source_label: '<img src=x onerror=alert(1)>', filename: '<script>' };
  const { store } = setup(async (_url, options) => {
    if (options.method === 'GET') throw Error('private error');
    assert.equal(options.body.has('acquired_at'), false);
    return Response.json(unsafe, { status: 201 });
  });
  assert.equal(await store.upload(file(), 'document', 'label'), true);
  assert.equal(store.getSnapshot().detail.id, item.id); assert.equal(store.getSnapshot().status, 'error');
  assert.match(render(store), /Evidence uploaded/); assert.match(render(store), /&lt;img/);
  assert.doesNotMatch(render(store), /<img|<script|private error/); store.dispose();
});

test('getEvidence fetches selected metadata and rejects foreign/missing/mismatched details', async () => {
  let detail = item; const urls = [];
  const { store } = setup(async url => {
    urls.push(String(url));
    return String(url).includes('?') ? Response.json(page([item])) : detail === null ? Response.json({ code: 'NOT_FOUND', message: 'Resource not found.' }, { status: 404 }) : Response.json(detail);
  });
  await store.load(); await store.select(item.id);
  assert.equal(store.getSnapshot().detail.id, item.id);
  assert.ok(urls[1].endsWith(`/cases/${caseA.id}/evidence/${item.id}`));
  for (detail of [null, { ...item, case_id: caseB.id }, { ...item, id: caseB.id }]) {
    await store.select(item.id); assert.equal(store.getSnapshot().detail, null); assert.equal(store.getSnapshot().detailStatus, 'error');
  }
  store.dispose();
});

test('pagination and malformed/foreign list failures never substitute stale records', async () => {
  let result = page([item]);
  const { store } = setup(async () => Response.json(result));
  await store.load();
  for (result of [page([{ ...item, case_id: caseB.id }]), page([item, item]), { ...page(), total: -1 }, { ...page(), limit: 100 }]) {
    await store.load(); assert.equal(store.getSnapshot().page, null); assert.equal(store.getSnapshot().status, 'error');
  }
  result = page([item], 20, 21); await store.load(20);
  assert.match(render(store), /21 evidence items/); assert.match(render(store), /disabled="">Next/);
  result = page([], 40, 21); await store.load(40); assert.match(render(store), /No evidence on this page/);
  store.dispose();
});

test('late page/detail/upload responses are discarded on newer requests, disposal and session changes', async () => {
  for (const action of ['dispose', 'session']) {
    for (const operation of ['load', 'upload', 'select']) {
      const wait = deferred(); let pendingRequest = false;
      const { store, client } = setup(async () => pendingRequest ? wait.promise : Response.json(page([item])));
      await store.load(); pendingRequest = true;
      const pending = operation === 'load' ? store.load() : operation === 'select' ? store.select(item.id) : store.upload(file(), 'document', 'label');
      const before = store.getSnapshot();
      if (action === 'dispose') store.dispose(); else client.setToken('synthetic-two');
      wait.resolve(Response.json(operation === 'load' ? page([item]) : item)); await pending;
      assert.equal(store.getSnapshot().detail, null);
      if (action === 'session') assert.equal(store.getSnapshot(), before);
      store.dispose();
    }
  }
  const wait = deferred(); let count = 0;
  const { store } = setup(async () => ++count === 1 ? wait.promise : Response.json(page([], 20, 21)));
  const old = store.load(); await store.load(20); wait.resolve(Response.json(page([item]))); await old;
  assert.equal(store.getSnapshot().page.offset, 20); store.dispose();
});

// React development StrictMode runs setup/cleanup/setup for the same store.
test('effect reconnect after cleanup loads evidence and ignores the aborted first response', async () => {
  const wait = deferred(); let count = 0;
  const { store } = setup(async () => ++count === 1 ? wait.promise : Response.json(page([item])));
  const old = store.start(); store.dispose(); await store.start();
  wait.resolve(Response.json(page())); await old;
  assert.equal(store.getSnapshot().page.items[0].id, item.id);
  assert.equal(store.getSnapshot().status, 'ready'); store.dispose();
});


test('source links resolve evidence outside the loaded page and still reject foreign case details', async () => {
  let detail = item;
  const { store } = setup(async url => String(url).includes('?') ? Response.json(page()) : Response.json(detail));
  // Source navigation may arrive before the evidence list has loaded.
  await store.select(item.id);
  assert.equal(store.getSnapshot().detail.id, item.id);
  await store.load();
  await store.select(item.id);
  assert.equal(store.getSnapshot().detail.id, item.id);
  detail = { ...item, case_id: caseB.id };
  await store.select(item.id);
  assert.equal(store.getSnapshot().detail, null);
  assert.equal(store.getSnapshot().detailStatus, 'error');
  store.dispose();
});
