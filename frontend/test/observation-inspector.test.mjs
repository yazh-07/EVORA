import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createObservationController, ObservationPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Synthetic Fetch doubles + actual panel handlers/static rendering; no browser mount claim.
const caseId = '11111111-1111-4111-8111-111111111111';
const evidenceId = '22222222-2222-4222-8222-222222222222';
const runId = '33333333-3333-4333-8333-333333333333';
const observation = { id: '44444444-4444-4444-8444-444444444444', case_id: caseId, evidence_id: evidenceId,
  processing_run_id: runId, kind: 'network.device', source_locator: 'row 2, device_id',
  raw_value: '<script>untrusted</script>', normalized_value: 'D-7', observed_at_raw: 'source time',
  observed_at_utc: '2026-01-12T10:01:00Z', extraction_confidence: 0 };
const page = (items = [observation], total = items.length, limit = 20, offset = 0) => ({ items, total, limit, offset });
function setup(t, fetch, pin) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch }); client.setToken('synthetic-observations');
  const controller = createObservationController(client, caseId, evidenceId, pin);
  t.after(() => controller.dispose()); return { client, controller };
}
const render = controller => renderToStaticMarkup(createElement(ObservationPanel, { state: controller.getSnapshot(), load: controller.load }));
const buttons = element => {
  if (!element || typeof element !== 'object') return [];
  return [...(element.type === 'button' ? [element] : []), ...[element.props?.children].flat(Infinity).flatMap(buttons)];
};
const click = (controller, label) => buttons(ObservationPanel({ state: controller.getSnapshot(), load: controller.load })).find(b => b.props.children === label).props.onClick();

test('generated GET filters evidence; renders locators, exact raw/normalized/time/confidence safely', async t => {
  const { controller } = setup(t, async (url, options) => {
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/observations`);
    assert.equal(url.searchParams.get('evidence_id'), evidenceId); assert.equal(url.searchParams.get('limit'), '20');
    assert.equal(url.searchParams.get('offset'), '0'); assert.equal(url.searchParams.has('processing_run_id'), false);
    assert.equal(options.method, 'GET'); assert.equal(options.body, undefined); return Response.json(page());
  });
  controller.start(); assert.match(render(controller), /Loading observations/); await setImmediate();
  const html = render(controller);
  for (const value of ['<table>', 'network.device', 'row 2, device_id', 'D-7', 'source time', observation.observed_at_utc, '<td>0</td>', 'unverified', 'not source reliability']) assert.ok(html.includes(value), value);
  assert.match(html, /&lt;script&gt;untrusted&lt;\/script&gt;/); assert.doesNotMatch(html, /<script>/);
});

test('actual pagination handlers use server limit/offset and authoritative total, bounded at each end', async t => {
  const offsets = [];
  const { controller } = setup(t, async url => { const offset = Number(url.searchParams.get('offset')); offsets.push(offset); return Response.json(page([observation], 3, 2, offset)); });
  controller.start(); await setImmediate();
  let controls = buttons(ObservationPanel({ state: controller.getSnapshot(), load: controller.load }));
  assert.equal(controls[0].props.disabled, true); assert.equal(controls[1].props.disabled, false);
  click(controller, 'Next'); await setImmediate();
  controls = buttons(ObservationPanel({ state: controller.getSnapshot(), load: controller.load }));
  assert.equal(controls[0].props.disabled, false); assert.equal(controls[1].props.disabled, true);
  assert.match(render(controller), /3 observations. Showing 1/);
  click(controller, 'Previous'); await setImmediate(); assert.deepEqual(offsets, [0, 2, 0]);
});

test('zero total is honest; an empty later page is distinct from unprocessed evidence', async t => {
  const { controller } = setup(t, async url => Response.json(Number(url.searchParams.get('offset')) === 0 ? page([], 0) : page([], 20, 20, 20)));
  controller.start(); await setImmediate(); assert.match(render(controller), /No completed observations for this evidence. Start processing/);
  await controller.load(20); assert.match(render(controller), /No observations on this page/); assert.doesNotMatch(render(controller), /Start processing/);
});

for (const status of [400, 401, 404, 500, 'network']) test(`${status} gives safe alert and retry control without server diagnostics`, async t => {
  let calls = 0;
  const { client, controller } = setup(t, async () => {
    if (++calls > 1) return Response.json(page());
    if (status === 'network') throw Error('PRIVATE TOKEN <script>');
    return Response.json({ code: 'PRIVATE', message: 'PRIVATE TOKEN <script>' }, { status });
  });
  controller.start(); await setImmediate(); assert.match(render(controller), /role="alert"/);
  assert.match(render(controller), /Retry observations/); assert.doesNotMatch(render(controller), /PRIVATE|TOKEN|<script>/);
  assert.equal(controller.getSnapshot().page, null);
  if (status === 401) { assert.equal(client.hasToken(), false); assert.match(render(controller), /Authentication required/); }
  else { click(controller, 'Retry observations'); await setImmediate(); assert.equal(controller.getSnapshot().status, 'ready'); }
});

test('historical pin is included on every page and foreign case/evidence/run responses are rejected', async t => {
  let response = page(); const offsets = [];
  const { controller } = setup(t, async url => {
    assert.equal(url.searchParams.get('processing_run_id'), runId); offsets.push(url.searchParams.get('offset'));
    return Response.json({ ...response, offset: Number(url.searchParams.get('offset')) });
  }, runId);
  controller.start(); await setImmediate(); assert.equal(controller.getSnapshot().status, 'ready');
  response = page([], 30); await controller.load(20); assert.deepEqual(offsets, ['0', '20']);
  for (const field of ['case_id', 'evidence_id', 'processing_run_id']) {
    response = page([{ ...observation, [field]: 'foreign' }]); await controller.load(0);
    assert.equal(controller.getSnapshot().status, 'error'); assert.doesNotMatch(render(controller), /D-7|foreign/);
  }
});

test('pending requests abort on pagination replacement/disposal; late responses cannot replace current state', async t => {
  let resolve; let signal; let calls = 0;
  const late = new Promise(r => { resolve = r; });
  const { controller } = setup(t, async (_url, options) => {
    if (++calls === 1) { signal = options.signal; return late; } return Response.json(page());
  });
  controller.start(); await controller.load(0); assert.equal(signal.aborted, true);
  const state = controller.getSnapshot(); resolve(Response.json(page([], 0))); await setImmediate(); assert.equal(controller.getSnapshot(), state);
  let deliveries = 0; controller.subscribe(() => deliveries++); controller.dispose(); await controller.load(); assert.equal(deliveries, 0);
});

for (const status of [200, 500]) test(`selection switch/disposal discards late ${status}; new evidence stays independent`, async t => {
  let resolve; let signal;
  const { client, controller } = setup(t, async (_url, options) => { signal = options.signal; return new Promise(r => { resolve = r; }); });
  let deliveries = 0; controller.subscribe(() => deliveries++); controller.start(); controller.dispose();
  const next = createObservationController(client, caseId, 'another-evidence'); t.after(() => next.dispose());
  const state = next.getSnapshot();
  resolve(Response.json(status === 200 ? page() : { code: 'PRIVATE', message: 'PRIVATE' }, { status })); await setImmediate();
  assert.equal(signal.aborted, true); assert.equal(deliveries, 1); assert.equal(next.getSnapshot(), state); assert.equal(controller.getSnapshot().page, null);
});

test('session change clears loaded values and prevents pending delivery', async t => {
  let resolve; let calls = 0;
  const { client, controller } = setup(t, async () => ++calls === 1 ? Response.json(page()) : new Promise(r => { resolve = r; }));
  controller.start(); await setImmediate(); const pending = controller.load(); client.setToken('replacement');
  resolve(Response.json(page())); await pending;
  assert.equal(controller.getSnapshot().page, null); assert.match(render(controller), /Session changed/); assert.doesNotMatch(render(controller), /D-7/);
});
