import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createCaseStore } from '../.test-build/src/cases/store.mjs';
import { CasePanels } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { caseA, caseB } from '../.test-build/test/fixtures/api.mjs';

// Synthetic transport doubles test UI state/races; real backend test is separate.
const page = (items = [caseA], total = items.length, offset = 0) => ({ items, total, limit: 20, offset });
function setup(fetch) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-investigator-1');
  return { client, store: createCaseStore(client) };
}
const render = state => renderToStaticMarkup(createElement(CasePanels, { state, load() {}, select() {} }));
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('loads real wire page metadata and selects details through generated routes', async () => {
  const urls = [];
  const { store } = setup(async url => { urls.push(String(url)); return Response.json(urls.length === 1 ? page([caseA], 21) : caseA); });
  const pending = store.load();
  assert.equal(store.getSnapshot().status, 'loading');
  assert.match(render(store.getSnapshot()), /Loading cases/);
  await pending;
  assert.equal(store.getSnapshot().page.total, 21);
  assert.match(render(store.getSnapshot()), /21 accessible cases/);
  assert.match(urls[0], /limit=20.*offset=0/);
  await store.select(caseA.id);
  assert.equal(store.getSnapshot().detail.id, caseA.id);
  assert.ok(urls[1].endsWith('/api/v1/cases/' + caseA.id));
  assert.match(render(store.getSnapshot()), /No description provided/);
  store.dispose();
});

test('pagination uses server totals; empty and out-of-range pages remain honest', async () => {
  const { store } = setup(async url => {
    const offset = Number(new URL(url).searchParams.get('offset'));
    return Response.json(page(offset === 0 ? [caseA] : [], 21, offset));
  });
  await store.load(20);
  assert.equal(store.getSnapshot().page.offset, 20);
  assert.match(render(store.getSnapshot()), /No cases on this page/);
  assert.match(render(store.getSnapshot()), /disabled="">Next/);
  await assert.rejects(store.load(-1), /Invalid case offset/);
  const empty = setup(async () => Response.json(page([]))).store;
  await empty.load();
  assert.match(render(empty.getSnapshot()), /No cases are available to this account/);
  empty.dispose(); store.dispose();
});

test('network and malformed-page failures show retry and clear stale records', async () => {
  let response = page();
  const { store } = setup(async () => { if (response === null) throw Error('private transport detail'); return Response.json(response); });
  await store.load();
  for (response of [null, { ...page(), offset: 10 }, { ...page(), total: -1 }, page([caseA, caseA])]) {
    await store.load();
    assert.equal(store.getSnapshot().status, 'error');
    assert.equal(store.getSnapshot().page, null);
    assert.match(render(store.getSnapshot()), /Try again/);
    assert.doesNotMatch(render(store.getSnapshot()), /private transport detail|Synthetic case/);
  }
  response = page(); await store.load(); assert.equal(store.getSnapshot().status, 'ready');
  store.dispose();
});

test('foreign/missing detail and mismatched detail never display the former selection', async () => {
  let detail = caseA;
  const { store } = setup(async url => String(url).includes('?') ? Response.json(page()) :
    detail === null ? Response.json({ code: 'NOT_FOUND', message: 'Resource not found.' }, { status: 404 }) : Response.json(detail));
  await store.load(); await store.select(caseA.id);
  detail = null; await store.select(caseA.id);
  assert.equal(store.getSnapshot().detail, null);
  assert.match(render(store.getSnapshot()), /Case unavailable/);
  detail = caseB; await store.select(caseA.id);
  assert.equal(store.getSnapshot().detailStatus, 'error');
  assert.equal(store.getSnapshot().detail, null);
  store.dispose();
});

test('late list responses and old details cannot replace a newer page', async () => {
  const first = deferred(); let count = 0;
  const { store } = setup(async () => ++count === 1 ? first.promise : Response.json(page([caseB], 21, 20)));
  const old = store.load(); await store.load(20);
  first.resolve(Response.json(page())); await old;
  assert.equal(store.getSnapshot().page.items[0].id, caseB.id);
  store.dispose();
  const detail = deferred();
  const next = setup(async url => String(url).includes('?') ? Response.json(page()) : detail.promise).store;
  await next.load(); const selection = next.select(caseA.id); await next.load();
  detail.resolve(Response.json(caseA)); await selection;
  assert.equal(next.getSnapshot().detail, null);
  next.dispose();
});

test('token replacement and logout discard pending actor responses', async () => {
  const wait = deferred();
  const { store, client } = setup(async () => wait.promise);
  const old = store.load(); client.setToken('synthetic-investigator-2');
  wait.resolve(Response.json(page())); await old;
  assert.equal(store.getSnapshot().page, null);
  client.clearToken(); await store.load();
  assert.equal(store.getSnapshot().status, 'signed-out');
  store.dispose();
});

test('401 ends the shared session; malicious titles/descriptions render as text', async () => {
  const { store, client } = setup(async () => Response.json({ code: 'UNAUTHORIZED', message: 'Authentication required.' }, { status: 401 }));
  await store.load(); assert.equal(client.hasToken(), false); await store.load();
  assert.equal(store.getSnapshot().status, 'signed-out'); store.dispose();
  const unsafe = { ...caseA, title: '<img src=x onerror=alert(1)>', description: '<script>alert(1)</script>' };
  const safe = setup(async url => Response.json(String(url).includes('?') ? page([unsafe]) : unsafe)).store;
  await safe.load(); await safe.select(caseA.id);
  const html = render(safe.getSnapshot());
  assert.doesNotMatch(html, /<img|<script/);
  assert.match(html, /&lt;script&gt;/); safe.dispose();
});
