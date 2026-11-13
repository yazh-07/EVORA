import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createAnalysisController, StartAnalysis, CaseAnalysisWorkspace, useAnalysisWorkspace } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';

// Synthetic schema-derived fetch doubles; loopback producer acceptance is separate.
const caseId = '11111111-1111-4111-8111-111111111111';
const runId = '22222222-2222-4222-8222-222222222222';
const otherId = '33333333-3333-4333-8333-333333333333';
const run = { id: runId, case_id: caseId, status: 'queued', trigger: 'initial', algorithm_version: 'synthetic/1',
  created_at: '2026-11-03T00:00:00Z', input_snapshot: { case_id: caseId, evidence_ids: [], processing_run_ids: [], observation_ids: [], sha256: 'a'.repeat(64) } };
const result = (status, extra = {}) => ({ ...run, status, ...(['completed', 'failed'].includes(status) ? { finished_at: run.created_at } : {}), ...extra });
const reply = value => Response.json(value);
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(condition) {
  for (let i = 0; i < 200; i++) { if (condition()) return; await delay(2); }
  assert.fail('Timed out waiting for analysis state');
}
function setup(fetch) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-analysis');
  const controller = createAnalysisController(client, caseId, 1);
  controller.start();
  return { client, controller };
}
const render = controller => renderToStaticMarkup(createElement(StartAnalysis, { state: controller.getSnapshot(), submit: controller.submit }));

test('explicit bodyless typed start carries UUID key; serial queued/running/completed GET pins exact run and stops', async () => {
  const responses = [run, result('running'), result('completed')];
  const calls = []; const states = [];
  const { controller } = setup(async (url, options) => { calls.push({ url: String(url), ...options }); return reply(responses.shift()); });
  try {
    assert.match(render(controller), />Run case analysis<\/button>/); assert.equal(calls.length, 0);
    controller.subscribe(() => { states.push({ ...controller.getSnapshot(), markup: render(controller) }); });
    const click = StartAnalysis({ state: controller.getSnapshot(), submit: controller.submit }).props.children[0].props.onClick;
    click(); await controller.submit();
    await until(() => controller.getSnapshot().status === 'terminal');
    assert.equal(calls.length, 3);
    assert.equal(calls[0].method, 'POST');
    assert.equal(calls[0].url, `http://127.0.0.1:8000/api/v1/cases/${caseId}/analysis-runs`);
    assert.equal(calls[0].body, undefined); assert.equal(calls[0].headers.has('Content-Type'), false);
    assert.match(calls[0].headers.get('Idempotency-Key'), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    for (const call of calls.slice(1)) {
      assert.equal(call.method, 'GET'); assert.ok(call.url.endsWith(`/analysis-runs/${runId}`));
      assert.equal(call.body, undefined); assert.equal(call.cache, 'no-store');
    }
    assert.ok(states.some(s => s.markup.includes('Queued…')));
    assert.ok(states.some(s => s.markup.includes('Analyzing…')));
    assert.ok(states.filter(s => s.status !== 'terminal').every(s => s.pinnedAnalysisRunId === null));
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId);
    assert.doesNotMatch(render(controller), /Analysis completed|Analysis details/);
    await delay(10); assert.equal(calls.length, 3);
  } finally { controller.dispose(); }
});

test('terminal POST must be confirmed by polling; existing completed pin survives newer pending/failed work', async () => {
  let phase = 0; let polls = 0; const keys = [];
  const { controller } = setup(async (_url, options) => {
    if (options.method === 'POST') { keys.push(options.headers.get('Idempotency-Key')); return reply(phase === 0 ? result('completed') : { ...run, id: otherId }); }
    polls++;
    return reply(phase === 0 ? result('completed') : result('failed', { id: otherId, error: '<script>synthetic failure</script>' }));
  });
  try {
    await controller.submit(); assert.equal(controller.getSnapshot().pinnedAnalysisRunId, null);
    assert.doesNotMatch(render(controller), /Analysis completed/);
    await until(() => controller.getSnapshot().status === 'terminal');
    phase = 1; await controller.submit();
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId);
    await until(() => controller.getSnapshot().status === 'terminal');
    assert.match(render(controller), /Analysis failed: &lt;script&gt;synthetic failure/);
    assert.doesNotMatch(render(controller), /<script>/);
    assert.match(render(controller), /Retry case analysis/);
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId);
    const before = polls; await delay(10); assert.equal(polls, before);
    phase = 0; await controller.submit();
    assert.equal(new Set(keys).size, 3);
    await until(() => controller.getSnapshot().status === 'terminal');
  } finally { controller.dispose(); }
});

for (const stage of ['start', 'poll']) {
  for (const error of [400, 401, 404, 500, 'network']) {
    test(`${stage} ${error}: safe alert, session clearing on 401, fresh-key retry`, async () => {
      let fail = true; const keys = [];
      const { client, controller } = setup(async (_url, options) => {
        if (options.method === 'POST') keys.push(options.headers.get('Idempotency-Key'));
        if (fail && (stage === 'start' || options.method === 'GET')) {
          if (error === 'network') throw Error('PRIVATE <script>');
          return Response.json({ code: 'ERROR', message: 'PRIVATE <script>' }, { status: error });
        }
        return reply(options.method === 'POST' ? run : result('completed'));
      });
      try {
        await controller.submit(); await until(() => controller.getSnapshot().status === 'error');
        assert.equal(controller.getSnapshot().pinnedAnalysisRunId, null);
        assert.match(render(controller), /role="alert"/); assert.doesNotMatch(render(controller), /PRIVATE|<script>|disabled=""/);
        if (error === 401) { assert.equal(client.hasToken(), false); assert.match(render(controller), /Authentication required/); client.setToken('synthetic-reopened'); }
        fail = false; await controller.submit(); await until(() => controller.getSnapshot().status === 'terminal');
        assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId);
        assert.equal(keys.length, 2); assert.notEqual(keys[0], keys[1]);
      } finally { controller.dispose(); }
    });
  }
}

test('foreign/malformed/changed snapshots and mismatched poll IDs fail closed without pinning', async () => {
  const invalid = [null, { ...run, case_id: otherId }, { ...run, id: 'invalid' }, { ...run, status: 'verified' },
    { ...run, input_snapshot: null }, { ...run, input_snapshot: { ...run.input_snapshot, sha256: 'invalid' } },
    { ...run, input_snapshot: { ...run.input_snapshot, evidence_ids: [runId, runId] } },
    { ...run, status: 'completed' }, result('failed')];
  for (const data of invalid) {
    const { controller } = setup(async () => reply(data));
    await controller.submit(); assert.equal(controller.getSnapshot().status, 'error');
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId, null); controller.dispose();
  }
  for (const data of [result('completed', { id: otherId }), result('completed', { input_snapshot: { ...run.input_snapshot, sha256: 'b'.repeat(64) } })]) {
    const { controller } = setup(async (_url, options) => reply(options.method === 'POST' ? run : data));
    await controller.submit(); await until(() => controller.getSnapshot().status === 'error');
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId, null); controller.dispose();
  }
});

test('case switch/unmount/session replacement/logout discard late POST and GET successes and failures', async () => {
  for (const stage of ['start', 'poll']) for (const action of ['case-switch', 'unmount', 'replace', 'logout']) for (const status of [200, 400]) {
    const wait = deferred(); let signal;
    const { client, controller } = setup(async (_url, options) => {
      if (stage === 'start' || options.method === 'GET') { signal = options.signal; return wait.promise; }
      return reply(run);
    });
    let pinned = false;
    controller.subscribe(() => { pinned ||= controller.getSnapshot().pinnedAnalysisRunId !== null; });
    const submission = controller.submit();
    await until(() => !!signal);
    if (action === 'replace') client.setToken('synthetic-replacement');
    else if (action === 'logout') client.clearToken();
    else controller.dispose();
    assert.equal(signal.aborted, true);
    wait.resolve(status === 200 ? reply(result('completed')) : Response.json({ code: 'ERROR', message: 'PRIVATE' }, { status }));
    await submission; await delay(4);
    assert.equal(pinned, false); assert.equal(controller.getSnapshot().run, null);
    controller.dispose();
  }
});

test('effect reconnect ignores old pending response; unmount cancels scheduled polling', async () => {
  const wait = deferred(); let calls = 0;
  const { controller } = setup(async () => ++calls === 1 ? wait.promise : reply(result('completed', { id: otherId })));
  const old = controller.submit(); controller.dispose(); controller.start();
  await controller.submit(); wait.resolve(reply(result('completed'))); await old;
  await until(() => controller.getSnapshot().status === 'terminal');
  assert.equal(controller.getSnapshot().pinnedAnalysisRunId, otherId); controller.dispose();
  let count = 0;
  const setup2 = setup(async () => { count++; return reply(run); });
  await setup2.controller.submit(); setup2.controller.dispose(); await delay(10); assert.equal(count, 1);
});

test('case workspace exposes one initially empty analysis pin and the explicit action to descendants', () => {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000' });
  function Consumer() {
    const value = useAnalysisWorkspace();
    return createElement('p', {}, `${value.caseId}:${value.analysis_run_id ?? 'no completed analysis'}`);
  }
  const markup = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(CaseAnalysisWorkspace, { caseId }, createElement(Consumer))));
  assert.match(markup, />Run case analysis<\/button>/);
  assert.ok(markup.includes(`${caseId}:no completed analysis`));
});

test('default polling interval is 750ms and queued/polling clicks cannot start another run', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let calls = 0;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { calls++; return reply(run); } });
  client.setToken('synthetic-timing');
  const controller = createAnalysisController(client, caseId);
  controller.start();
  try {
    await controller.submit(); await controller.submit();
    assert.equal(calls, 1);
    assert.match(render(controller), /disabled=""/);
    t.mock.timers.tick(749); assert.equal(calls, 1);
    t.mock.timers.tick(1); assert.equal(calls, 2);
  } finally { controller.dispose(); }
});

test('switching to a newer completed pin is atomic and object-key order does not change snapshot identity', async () => {
  let phase = 0;
  const { controller } = setup(async (_url, options) => {
    const selected = phase ? { ...run, id: otherId } : run;
    if (options.method === 'POST') return reply(selected);
    return reply({ ...selected, status: 'completed', finished_at: run.created_at,
      input_snapshot: Object.fromEntries(Object.entries(run.input_snapshot).reverse()) });
  });
  try {
    await controller.submit(); await until(() => controller.getSnapshot().status === 'terminal');
    phase = 1;
    const pins = [];
    controller.subscribe(() => pins.push([controller.getSnapshot().status, controller.getSnapshot().pinnedAnalysisRunId]));
    await controller.submit(); await until(() => controller.getSnapshot().status === 'terminal');
    assert.ok(pins.filter(([status]) => status !== 'terminal').every(([, pin]) => pin === runId));
    assert.deepEqual(pins.at(-1), ['terminal', otherId]);
  } finally { controller.dispose(); }
});

test('explicit history choice changes the pin while passive discovery cannot override the investigator', () => {
  const { controller } = setup(async () => { throw Error('No requests expected'); });
  try {
    controller.selectCompletedRun(runId);
    controller.selectCompletedRun(otherId);
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId,runId);
    controller.chooseCompletedRun(otherId);
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId,otherId);
    controller.selectCompletedRun(runId);
    controller.chooseCompletedRun('invalid');
    assert.equal(controller.getSnapshot().pinnedAnalysisRunId,otherId);
  } finally {controller.dispose();}
});
