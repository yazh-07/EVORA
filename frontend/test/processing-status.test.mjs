import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createProcessingStatusController, ProcessingStatusPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Synthetic Fetch doubles, deterministic timer ticks and static rendering, not browser mounting.
const seed = { id: '33333333-3333-4333-8333-333333333333',
  case_id: '11111111-1111-4111-8111-111111111111', evidence_id: '22222222-2222-4222-8222-222222222222',
  status: 'queued', processor_version: 'synthetic/1', created_at: '2026-11-03T00:00:00Z' };
const finished_at = '2026-11-03T00:01:00Z';
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function setup(t, fetch, run = seed) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-status');
  const controller = createProcessingStatusController(client, run);
  t.after(() => controller.dispose());
  return { client, controller };
}
const render = controller => renderToStaticMarkup(createElement(ProcessingStatusPanel, { state: controller.getSnapshot(), retry: controller.refresh }));
const tick = async (t, ms = 750) => { t.mock.timers.tick(ms); await setImmediate(); };

test('polls queued -> running -> completed using exact generated path; terminal stops polling', async t => {
  const responses = [seed, { ...seed, status: 'running' }, { ...seed, status: 'completed', finished_at }];
  const calls = [];
  const { controller } = setup(t, async (url, options) => {
    calls.push({ url: String(url), ...options }); return Response.json(responses.shift());
  });
  controller.start(); await setImmediate();
  assert.match(render(controller), /Last reported status: queued/);
  assert.match(render(controller), new RegExp(seed.created_at));
  assert.doesNotMatch(render(controller), /Finished time/);
  await tick(t);
  assert.match(render(controller), /Last reported status: running/);
  assert.match(render(controller), /synthetic\/1/);
  await tick(t);
  assert.match(render(controller), /Last reported status: completed/);
  assert.match(render(controller), new RegExp(finished_at));
  assert.deepEqual(controller.getSnapshot().run, { ...seed, status: 'completed', finished_at });
  await tick(t, 10000); await controller.refresh();
  assert.equal(calls.length, 3);
  for (const call of calls) {
    assert.equal(call.url, `http://127.0.0.1:8000/api/v1/cases/${seed.case_id}/evidence/${seed.evidence_id}/processing-runs/${seed.id}`);
    assert.equal(call.method, 'GET'); assert.equal(call.body, undefined);
    assert.equal(call.headers.has('Idempotency-Key'), false);
  }
});

test('running -> failed displays escaped diagnostic and exact finished time; stops polling', async t => {
  let calls = 0;
  const error = 'MALFORMED_CSV <script>alert("synthetic")</script>';
  const { controller } = setup(t, async () => { calls++; return Response.json({ ...seed, status: 'failed', error, finished_at }); }, { ...seed, status: 'running' });
  assert.match(render(controller), /running/);
  controller.start(); await setImmediate();
  assert.match(render(controller), /Last reported status: failed/);
  assert.match(render(controller), /MALFORMED_CSV &lt;script&gt;/);
  assert.doesNotMatch(render(controller), /<script>/);
  assert.match(render(controller), new RegExp(finished_at));
  await tick(t, 10000); await controller.refresh(); assert.equal(calls, 1);
});

for (const status of [401, 404, 'network', 500]) {
  test(`${status} produces safe alert; transient failures retry same run without starting processing`, async t => {
    let calls = 0;
    const { client, controller } = setup(t, async () => {
      calls++;
      if (calls > 1) return Response.json({ ...seed, status: 'completed', finished_at });
      if (status === 'network') throw Error('PRIVATE <script>');
      return Response.json({ code: 'PRIVATE', message: '<script>' }, { status });
    });
    controller.start(); await setImmediate();
    assert.match(render(controller), /role="alert"/);
    assert.doesNotMatch(render(controller), /PRIVATE|<script>/);
    await tick(t, 10000); assert.equal(calls, 1);
    if (status === 401) { assert.equal(client.hasToken(), false); assert.match(render(controller), /Authentication required/); }
    else if (status === 404) assert.match(render(controller), /Run or evidence unavailable/);
    else {
      assert.match(render(controller), /Last reported values may be out of date/);
      // Invoke the rendered retry button's actual handler.
      ProcessingStatusPanel({ state: controller.getSnapshot(), retry: controller.refresh }).props.children[1].props.onClick();
      await setImmediate(); assert.equal(calls, 2);
      assert.match(render(controller), /Last reported status: completed/);
      assert.doesNotMatch(render(controller), /role="alert"|Retry status check/);
    }
  });
}

test('disposal clears scheduled polling; unmount/evidence switch ignores late success and error after reconnect', async t => {
  let calls = 0; let signal;
  const wait = deferred();
  const { controller } = setup(t, async (_url, options) => {
    signal = options.signal;
    return ++calls === 1 ? wait.promise : Response.json({ ...seed, status: 'running' });
  });
  let notifications = 0; controller.subscribe(() => notifications++);
  controller.start(); controller.dispose(); assert.equal(signal.aborted, true);
  controller.start(); await setImmediate();
  const snapshot = controller.getSnapshot();
  wait.resolve(Response.json({ ...seed, status: 'completed', finished_at })); await setImmediate();
  assert.equal(controller.getSnapshot(), snapshot); assert.equal(notifications, 0);
  controller.dispose(); await tick(t, 10000); assert.equal(calls, 2);
});

test('late failures after disposal cannot notify old selection; session changes abort and discard delivery', async t => {
  const wait = deferred(); let signal;
  const { client, controller } = setup(t, async (_url, options) => { signal = options.signal; return wait.promise; });
  controller.start(); client.setToken('replacement-session');
  assert.equal(signal.aborted, true);
  assert.equal(controller.getSnapshot().run, null);
  wait.resolve(Response.json({ code: 'PRIVATE', message: 'PRIVATE' }, { status: 404 })); await setImmediate();
  assert.match(render(controller), /Session changed/); assert.doesNotMatch(render(controller), /PRIVATE/);
  controller.dispose(); await tick(t, 10000);
});

test('slow requests never overlap, and late errors after disposal are ignored', async t => {
  const wait = deferred(); let calls = 0; let deliveries = 0;
  const { controller } = setup(t, async () => { calls++; return wait.promise; });
  controller.subscribe(() => deliveries++);
  controller.start(); await tick(t, 10000); await controller.refresh(); assert.equal(calls, 1);
  controller.dispose();
  wait.resolve(Response.json({ code: 'PRIVATE', message: 'PRIVATE' }, { status: 500 })); await setImmediate();
  assert.equal(deliveries, 0); await tick(t, 10000); assert.equal(calls, 1);
});

test('rejects mismatched run/case/evidence and malformed terminal payloads without inventing completion', async t => {
  let response;
  const { controller } = setup(t, async () => Response.json(response));
  for (const invalid of [{ ...seed, id: seed.evidence_id }, { ...seed, case_id: seed.evidence_id },
    { ...seed, evidence_id: seed.case_id }, { ...seed, status: 'completed' },
    { ...seed, status: 'failed', finished_at }, { ...seed, status: 'verified' }]) {
    response = invalid;
    controller.start(); await setImmediate();
    assert.deepEqual(controller.getSnapshot().run, seed);
    assert.equal(controller.getSnapshot().retryable, true);
    assert.doesNotMatch(render(controller), /Last reported status: completed|Last reported status: failed|verified/);
    controller.dispose();
  }
});

test('accepted terminal run is displayed without polling', async t => {
  const { controller } = setup(t, async () => { throw Error('Must not fetch'); }, { ...seed, status: 'completed', finished_at });
  controller.start(); await tick(t, 10000);
  assert.match(render(controller), /Last reported status: completed/);
  assert.equal(controller.getSnapshot().message, '');
});
