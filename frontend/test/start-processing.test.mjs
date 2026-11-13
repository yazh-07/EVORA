import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createProcessingController, StartProcessingPanel, EvidencePanels } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';

// Fetch doubles + static React rendering; real producer acceptance is in cases.integration.mjs.
const caseId = '11111111-1111-4111-8111-111111111111';
const evidenceId = '22222222-2222-4222-8222-222222222222';
const run = { id: '33333333-3333-4333-8333-333333333333', case_id: caseId, evidence_id: evidenceId,
  status: 'queued', processor_version: 'synthetic/1', created_at: '2026-11-03T00:00:00Z' };
const accepted = data => Response.json(data ?? run, { status: 202 });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function setup(fetch) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-processing');
  return { client, controller: createProcessingController(client, caseId, evidenceId) };
}
const render = (controller, client) => renderToStaticMarkup(createElement(ApiProvider, { client: client ?? createApiClient({ baseUrl: 'http://127.0.0.1:8000' }) }, createElement(StartProcessingPanel, { state: controller.getSnapshot(), submit: controller.submit })));
const click = controller => StartProcessingPanel({ state: controller.getSnapshot(), submit: controller.submit }).props.children[0].props.onClick();

test('explicit button dispatches bodyless generated request with UUID key; busy blocks duplicate; 202 retains actual run', async () => {
  const wait = deferred(); const calls = [];
  const { controller } = setup(async (url, options) => { calls.push({ url: String(url), ...options }); return wait.promise; });
  assert.match(render(controller), />Start processing<\/button>/);
  assert.equal(calls.length, 0);
  click(controller);
  assert.match(render(controller), /disabled="">Starting processing/);
  assert.match(render(controller), /aria-busy="true"/);
  click(controller); await controller.submit();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].url, `http://127.0.0.1:8000/api/v1/cases/${caseId}/evidence/${evidenceId}/processing-runs`);
  assert.match(calls[0].headers.get('Idempotency-Key'), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(calls[0].body, undefined);
  assert.equal(calls[0].cache, 'no-store');
  const done = new Promise(resolve => { const off = controller.subscribe(() => { if (controller.getSnapshot().status !== 'submitting') { off(); resolve(); } }); });
  wait.resolve(accepted()); await done;
  assert.deepEqual(controller.getSnapshot().run, run);
  assert.match(render(controller), new RegExp(run.id));
  assert.match(render(controller), /Last reported status: queued/);
  assert.doesNotMatch(render(controller), /completed/);
  await controller.submit();
  assert.notEqual(calls[0].headers.get('Idempotency-Key'), calls[1].headers.get('Idempotency-Key'));
  controller.dispose();
});

test('400/401/404/409/415/500 and network failures show safe alerts and permit explicit retry with a new key', async () => {
  for (const status of [400, 401, 404, 409, 415, 500, 'network']) {
    const keys = [];
    const { client, controller } = setup(async (_url, options) => {
      keys.push(options.headers.get('Idempotency-Key'));
      if (keys.length > 1) return accepted({ ...run, status: 'running' });
      if (status === 'network') throw Error('PRIVATE <script>');
      return Response.json({ code: 'ERROR', message: 'PRIVATE <script>' }, { status });
    });
    await controller.submit();
    assert.equal(controller.getSnapshot().status, 'error');
    assert.equal(controller.getSnapshot().run, null);
    assert.match(render(controller), /role="alert"/);
    assert.doesNotMatch(render(controller), /PRIVATE|<script>|disabled=""/);
    if (status === 401) {
      assert.equal(client.hasToken(), false);
      assert.match(render(controller), /Authentication required/);
      client.setToken('synthetic-reopened-session');
    }
    await controller.submit();
    assert.equal(controller.getSnapshot().status, 'accepted');
    assert.match(render(controller), /Last reported status: running/);
    assert.notEqual(keys[0], keys[1]);
    controller.dispose();
  }
});

test('selection change/unmount disposal and session changes abort or ignore late success and error', async () => {
  for (const action of ['selection', 'unmount', 'logout', 'replace']) {
    for (const response of [accepted(), Response.json({ code: 'ERROR', message: 'PRIVATE' }, { status: 400 })]) {
      const wait = deferred(); let signal; let deliveries = 0;
      const { client, controller } = setup(async (_url, options) => { signal = options.signal; return wait.promise; });
      controller.subscribe(() => { deliveries++; });
      const pending = controller.submit();
      if (action === 'selection' || action === 'unmount') controller.dispose();
      else if (action === 'logout') client.clearToken();
      else client.setToken('replacement-session');
      assert.equal(signal.aborted, true);
      wait.resolve(response); await pending;
      assert.equal(deliveries, 1);
      assert.equal(controller.getSnapshot().run, null);
      controller.dispose();
    }
  }
});

test('effect reconnect accepts new response while discarding aborted old response', async () => {
  const wait = deferred(); let calls = 0;
  const { controller } = setup(async () => ++calls === 1 ? wait.promise : accepted({ ...run, id: evidenceId }));
  controller.start(); const old = controller.submit(); controller.dispose(); controller.start();
  await controller.submit(); wait.resolve(accepted()); await old;
  assert.equal(controller.getSnapshot().run.id, evidenceId);
  controller.dispose();
});

test('foreign/malformed successful responses never fabricate accepted status', async () => {
  for (const data of [null, { ...run, case_id: evidenceId }, { ...run, evidence_id: caseId }, { ...run, id: 'invalid' }, { ...run, status: 'verified' }, { ...run, status: 'completed' }, { ...run, status: 'failed', finished_at: run.created_at }]) {
    const { controller } = setup(async () => Response.json(data, { status: 202 }));
    await controller.submit(); assert.equal(controller.getSnapshot().status, 'error');
    assert.equal(controller.getSnapshot().run, null); assert.match(render(controller), /Could not confirm/);
    controller.dispose();
  }
});

test('missing authentication is a safe alert without transport; server status and identifiers are escaped', async () => {
  const { client, controller } = setup(async () => { throw Error('Must not fetch'); });
  client.clearToken(); await controller.submit(); assert.match(render(controller), /Authentication required/);
  controller.dispose();
  assert.doesNotMatch(renderToStaticMarkup(createElement(StartProcessingPanel, { state: { status: 'error', run: null, message: '<script>untrusted</script>' }, submit: async () => {} })), /<script>/);
});

test('selected evidence inspector opens on results and defers processing controls', () => {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000' });
  const detail = { id: evidenceId, case_id: caseId, kind: 'network_log', filename: 'network.csv', size_bytes: 0, sha256: 'a'.repeat(64), created_at: run.created_at, source_label: 'Synthetic source', media_type: 'text/csv' };
  const markup = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(EvidencePanels, {
    state: { status: 'ready', page: { items: [detail], total: 1, limit: 20, offset: 0 }, detailStatus: 'ready', detail, submitting: false },
    load() {}, select() {}, upload: async () => false,
  })));
  assert.match(markup, /Source views/); assert.match(markup, />Info<\/button>/); assert.doesNotMatch(markup, />Start processing<\/button>/);
});

test('explicit structured interpretation uses the dedicated endpoint and validates returned source/processing kinds', async () => {
  for (const processingKind of ['mobile_log','audio']) {
    const calls=[];
    const { client, controller: unused }=setup(async (url,options)=>{
      calls.push({url:String(url),...options});
      return accepted({...run,source_kind:'document',processing_kind:processingKind});
    });
    unused.dispose();
    const controller=createProcessingController(client,caseId,evidenceId,'mobile_log');
    await controller.submit();
    assert.ok(calls[0].url.endsWith('/processing-runs/interpret-as'));
    assert.deepEqual(JSON.parse(calls[0].body),{kind:'mobile_log'});
    assert.equal(controller.getSnapshot().status,processingKind==='mobile_log'?'accepted':'error');
    controller.dispose();
  }
});
