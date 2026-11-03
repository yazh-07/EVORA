import test from 'node:test';
import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createCaseOverviewController, CaseOverviewPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { caseA, caseB, evidence } from '../.test-build/test/fixtures/api.mjs';
const items = Array.from({ length: 23 }, (_, i) => ({ ...evidence, id: `00000000-0000-4000-8000-${String(i).padStart(12, '0')}`, kind: i < 12 ? 'document' : 'network_log' }));
const run = (item, status, id = item.id) => ({ id, case_id: caseA.id, evidence_id: item.id, status, processor_version: 'synthetic', created_at: caseA.created_at,
  ...(['completed', 'failed'].includes(status) ? { finished_at: caseA.created_at } : {}), ...(status === 'failed' ? { error: 'PRIVATE' } : {}) });
function setup(t, transport) {
  const client = createApiClient({ baseUrl: 'https://overview.invalid', fetch: transport }); client.setToken('synthetic');
  const controller = createCaseOverviewController(client, caseA.id); t.after(() => controller.dispose());
  return { client, controller };
}
const render = controller => renderToStaticMarkup(createElement(CaseOverviewPanel, { state: controller.getSnapshot(), load: controller.load }));
const route = (url, list = items) => {
  if (url.pathname.endsWith(caseA.id)) return caseA;
  const offset = Number(url.searchParams.get('offset'));
  return { items: list.slice(offset, offset + 20), total: list.length, limit: 20, offset };
};

test('all pages (>20), kinds and latest per-item statuses; bodyless typed GETs', async t => {
  const offsets = []; let histories = 0;
  const { controller } = setup(t, async (url, options) => {
    assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
    if (url.pathname.endsWith('/processing-runs')) {
      histories++; const item = items.find(item => url.pathname.includes(item.id)); const i = items.indexOf(item);
      return Response.json(i % 5 === 4 ? [] : [run(item, 'completed', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'), run(item, ['completed', 'running', 'queued', 'failed'][i % 5])]);
    }
    if (url.pathname.endsWith('/evidence')) { offsets.push(Number(url.searchParams.get('offset'))); assert.equal(url.searchParams.get('limit'), '20'); }
    return Response.json(route(url));
  });
  controller.start(); await setImmediate();
  assert.deepEqual(offsets, [0, 20]); assert.equal(histories, 23);
  const summary = controller.getSnapshot().summary;
  assert.equal(summary.total, 23); assert.equal(summary.kinds.document, 12); assert.equal(summary.kinds.network_log, 11);
  assert.deepEqual(summary.statuses, { completed: 5, running: 5, queued: 5, failed: 4, unprocessed: 4 });
  assert.match(render(controller), /Total evidence items: <strong>23/); assert.doesNotMatch(render(controller), /PRIVATE/);
});

test('honest empty state makes no processing requests', async t => {
  const { controller } = setup(t, async url => Response.json(route(url, [])));
  controller.start(); await setImmediate(); assert.equal(controller.getSnapshot().summary.total, 0);
  assert.match(render(controller), /No evidence uploaded yet\./);
});

for (const phase of ['case', 'evidence', 'history']) for (const status of [401, 404, 'network']) test(`${phase} ${status}: safe error, no partial totals, retry`, async t => {
  let fail = true;
  const { client, controller } = setup(t, async url => {
    const current = url.pathname.endsWith('/processing-runs') ? 'history' : url.pathname.endsWith('/evidence') ? 'evidence' : 'case';
    if (fail && phase === current) {
      if (status === 'network') throw Error('PRIVATE <script>');
      return Response.json({ message: 'PRIVATE <script>' }, { status });
    }
    return Response.json(current === 'history' ? [] : route(url, [items[0]]));
  });
  controller.start(); await setImmediate(); assert.equal(controller.getSnapshot().status, 'error');
  assert.equal(controller.getSnapshot().summary, null); assert.match(render(controller), /role="alert"/);
  assert.doesNotMatch(render(controller), /PRIVATE|<script>|Total evidence items/);
  fail = false;
  if (status === 401) { assert.equal(client.hasToken(), false); assert.match(render(controller), /Authentication required/); client.setToken('replacement'); controller.start(); }
  else await controller.load();
  await setImmediate(); assert.equal(controller.getSnapshot().summary.total, 1);
});

for (const defect of ['duplicate', 'empty', 'total', 'offset', 'foreign', 'kind', 'history']) test(`rejects ${defect} without publishing partial counts`, async t => {
  const { controller } = setup(t, async url => {
    if (url.pathname.endsWith('/processing-runs')) return Response.json(defect === 'history' ? [{ ...run(items[0], 'completed'), case_id: caseB.id }] : []);
    const page = route(url);
    if (url.pathname.endsWith('/evidence')) {
      if (defect === 'duplicate' && page.offset) page.items[0] = items[0];
      if (defect === 'empty') page.items = [];
      if (defect === 'total' && page.offset) page.total++;
      if (defect === 'offset') page.offset++;
      if (defect === 'foreign') page.items = [{ ...items[0], case_id: caseB.id }];
      if (defect === 'kind') page.items = [{ ...items[0], kind: '<script>' }];
    }
    return Response.json(page);
  });
  controller.start(); await setImmediate(); assert.equal(controller.getSnapshot().status, 'error'); assert.equal(controller.getSnapshot().summary, null);
});

for (const phase of ['case', 'evidence', 'history']) test(`${phase}: selection/unmount abort and late delivery disposal`, async t => {
  let resolve; let signal;
  const { client, controller } = setup(t, async (url, options) => {
    const current = url.pathname.endsWith('/processing-runs') ? 'history' : url.pathname.endsWith('/evidence') ? 'evidence' : 'case';
    if (current === phase) { signal = options.signal; return new Promise(r => { resolve = r; }); }
    return Response.json(route(url, [items[0]]));
  });
  controller.start(); await setImmediate(); let deliveries = 0; controller.subscribe(() => deliveries++);
  controller.dispose(); assert.equal(signal.aborted, true);
  const next = createCaseOverviewController(client, caseB.id); const state = next.getSnapshot();
  resolve(Response.json(phase === 'case' ? caseA : phase === 'history' ? [] : route(new URL('https://overview.invalid/evidence'), [])));
  await setImmediate(); assert.equal(deliveries, 0); assert.equal(next.getSnapshot(), state); assert.equal(controller.getSnapshot().summary, null); next.dispose();
});

test('refresh replacement and session change abort stale reads', async t => {
  let resolve; let signal; let hold = false;
  const { client, controller } = setup(t, async (url, options) => {
    if (hold) { hold = false; signal = options.signal; return new Promise(r => { resolve = r; }); }
    return Response.json(route(url, []));
  });
  controller.start(); await setImmediate(); hold = true; const late = controller.load(); await controller.load();
  assert.equal(signal.aborted, true); const state = controller.getSnapshot(); resolve(Response.json(caseA)); await late; assert.equal(controller.getSnapshot(), state);
  hold = true; const pending = controller.load(); client.setToken('changed'); assert.equal(signal.aborted, true);
  resolve(Response.json(caseA)); await pending; assert.equal(controller.getSnapshot().summary, null); assert.match(render(controller), /Session changed/);
});
