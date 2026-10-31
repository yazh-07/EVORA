import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createCaseStore } from '../.test-build/src/cases/store.mjs';
import { CasePanels, CaseCreation } from '../.test-build/src/cases/CaseWorkspace.mjs';
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

const creationHtml = store => renderToStaticMarkup(createElement(CaseCreation, { state: store.getSnapshot(), create: store.create }));
test('creation form has labeled constrained fields and rejects blank titles without requests', async () => {
  let calls = 0;
  const { store } = setup(async () => { calls++; return Response.json(page()); });
  const html = creationHtml(store);
  assert.match(html, /<form/); assert.match(html, /1 to 200 characters/); assert.doesNotMatch(html, /maxLength=/i);
  assert.match(html, /for="case-title"/); assert.match(html, /Create case/);
  for (const title of ['', '  \t\n', 'x'.repeat(201)]) assert.equal(await store.create(title, ''), false);
  assert.equal(await store.create('Valid', 'x'.repeat(5001)), false);
  await store.create('   ', '');
  assert.match(creationHtml(store), /Title cannot be empty/);
  assert.match(creationHtml(store), /aria-describedby="create-error"/);
  assert.equal(calls, 0); store.dispose();
});
test('valid creation sends exact body, prevents duplicates and refreshes/selects confirmed case', async () => {
  const wait = deferred(); const requests = [];
  const { store } = setup(async (_url, options) => {
    requests.push(options);
    return options.method === 'POST' ? wait.promise : Response.json(page([caseB, caseA]));
  });
  const pending = store.create('Synthetic case', 'Synthetic description');
  assert.equal(store.getSnapshot().createStatus, 'submitting');
  assert.match(creationHtml(store), /disabled=""[^>]*>Creating case/);
  assert.equal(await store.create('Duplicate', ''), false);
  await store.load();
  assert.equal(requests.length, 1);
  assert.deepEqual(JSON.parse(requests[0].body), { title: 'Synthetic case', description: 'Synthetic description' });
  wait.resolve(Response.json(caseB, { status: 201 }));
  assert.equal(await pending, true);
  assert.equal(store.getSnapshot().detail.id, caseB.id);
  assert.equal(store.getSnapshot().page.total, 2);
  assert.ok(store.getSnapshot().page.items.some(item => item.id === caseB.id)); store.dispose();
});
test('creation server errors render safely and permit retry; refresh failure retains confirmed details', async () => {
  let fail = true;
  const { store } = setup(async (_url, options) => {
    if (options.method === 'GET') throw Error('private');
    return fail ? Response.json({ code: 'INVALID_INPUT', message: 'Invalid title <script>' }, { status: 400 }) : Response.json(caseA, { status: 201 });
  });
  assert.equal(await store.create('Valid', ''), false);
  assert.match(creationHtml(store), /Case not created/); assert.doesNotMatch(creationHtml(store), /Invalid title|&lt;script|<script/);
  fail = false;
  assert.equal(await store.create('Valid', ''), true);
  assert.equal(store.getSnapshot().detail.id, caseA.id);
  assert.match(render(store.getSnapshot()), /Case created. Could not refresh/); store.dispose();
});
test('late creation from a replaced session or disposed workspace is discarded', async () => {
  for (const action of ['session', 'dispose']) {
    const wait = deferred();
    const { client, store } = setup(async () => wait.promise);
    const pending = store.create('Valid', '');
    if (action === 'session') client.setToken('replacement'); else store.dispose();
    wait.resolve(Response.json(caseB, { status: 201 }));
    assert.equal(await pending, false);
    assert.equal(store.getSnapshot().detail, null);
    store.dispose();
  }
});

test('a list request started before creation cannot clear its submitting state', async () => {
  const listing = deferred(); const creation = deferred(); let gets = 0;
  const { store } = setup(async (_url, options) => options.method === 'POST' ? creation.promise :
    ++gets === 1 ? listing.promise : Response.json(page([caseB])));
  const old = store.load();
  const pending = store.create('Valid', '');
  listing.resolve(Response.json(page())); await old;
  assert.equal(store.getSnapshot().createStatus, 'submitting');
  creation.resolve(Response.json(caseB, { status: 201 }));
  assert.equal(await pending, true);
  assert.equal(store.getSnapshot().detail.id, caseB.id); store.dispose();
});

test('failed creation after aborting an initial list leaves a retryable list state', async () => {
  const listing = deferred();
  const { store } = setup(async (_url, options) => options.method === 'POST' ?
    Response.json({ code: 'INVALID_INPUT', message: 'Invalid title' }, { status: 400 }) : listing.promise);
  const old = store.load();
  assert.equal(await store.create('Valid', ''), false);
  assert.equal(store.getSnapshot().status, 'error');
  assert.match(render(store.getSnapshot()), /Try again/);
  listing.resolve(Response.json(page())); await old;
  assert.equal(store.getSnapshot().status, 'error'); store.dispose();
});


test('creation counts Unicode codepoints and preserves boundary source values', async () => {
  const title = String.fromCodePoint(0x1f9ea).repeat(200);
  const description = String.fromCodePoint(0x1f9ea).repeat(5000);
  let posts = 0;
  const created = { ...caseA, title, description };
  const { store } = setup(async (_url, options) => {
    if (options.method === 'POST') { posts++; assert.deepEqual(JSON.parse(options.body), { title, description }); return Response.json(created, {status:201}); }
    return Response.json(page([created]));
  });
  assert.equal(await store.create(title, description), true);
  assert.equal(store.getSnapshot().detail.title, title);
  assert.equal(await store.create(title + 'x', ''), false);
  assert.equal(await store.create('valid', description + 'x'), false);
  assert.equal(posts, 1); store.dispose();
});

test('uncertain creation failures never claim rejection or automatically retry POSTs', async () => {
  for (const kind of ['network', '500', 'malformed']) {
    let calls = 0;
    const { store } = setup(async () => {
      calls++;
      if (kind === 'network') throw Error('private transport content');
      return kind === '500' ? Response.json({code:'SERVER_ERROR',message:'private server content'}, {status:500}) : Response.json({title:'incomplete'});
    });
    assert.equal(await store.create('Synthetic uncertain', ''), false);
    assert.equal(calls, 1);
    assert.match(creationHtml(store), /Could not confirm whether the case was created/);
    assert.match(creationHtml(store), /Refresh cases before submitting again/);
    assert.doesNotMatch(creationHtml(store), /private|Case not created/);
    store.dispose();
  }
});
