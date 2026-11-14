import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createTriageController, PriorityListPanel, PriorityList, CaseAnalysisWorkspace, createAnalysisController } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';

// Schema-derived synthetic Fetch doubles; producer acceptance is in cases.integration.mjs.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), runId = id(2), time = '2026-11-03T00:00:00Z';
const scored = (n, score = 48.88, band = 'P3') => ({ evidence_id: id(n), effective_priority: band,
  latest_result: { id: id(n + 100), evidence_id: id(n), case_id: caseId, analysis_run_id: runId,
    score, priority: band, created_at: time, explanation: 'Candidate association; requires human verification. <script>source</script>',
    factors: [
      { name: 'relevance', value: .8, weight: 5 / 9, contribution: 44.44, explanation: 'Matched candidate keys <script>source</script> Investigative attention only; not truth, identity or guilt.', evidence_ids: [id(n)] },
      { name: 'connectivity', value: .1, weight: 4 / 9, contribution: 4.44, explanation: 'One supported neighbor', evidence_ids: [id(n)] },
    ] } });
const unscored = n => ({ evidence_id: id(n) });
const page = (items, extra = {}) => ({ items, total: items.length, limit: 20, offset: 0, analysis_run_id: runId, ...extra });
const render = controller => renderToStaticMarkup(createElement(PriorityListPanel, { state: controller.getSnapshot(), load: controller.load }));
const pause = () => new Promise(resolve => setTimeout(resolve, 1));
async function until(condition) {
  for (let i = 0; i < 300; i++) { if (condition()) return; await pause(); }
  assert.fail('Timed out waiting for triage state');
}
function setup(fetch, { pin = runId, onSelectedRun, limit = 20 } = {}) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch });
  client.setToken('synthetic-u06');
  const controller = createTriageController(client, caseId, pin ?? undefined, onSelectedRun, limit);
  controller.start();
  return { client, controller };
}
const ready = controller => until(() => ['ready', 'error'].includes(controller.getSnapshot().status));
function buttons(element) {
  if (!element || typeof element !== 'object') return [];
  if (Array.isArray(element)) return element.flatMap(buttons);
  return [...(element.type === 'button' ? [element] : []), ...buttons(element.props?.children)];
}
function click(controller, text) {
  const button = buttons(PriorityListPanel({ state: controller.getSnapshot(), load: controller.load })).find(b => b.props.children === text);
  assert.ok(button, text); assert.ok(!button.props.disabled, `${text} enabled`); button.props.onClick();
}

test('typed request, table, exact score formatting, server pagination, stable pin and factor sources', async () => {
  const calls = [], pins = [];
  const entries = [scored(10), scored(11, 0, 'P4'), unscored(12)];
  const { controller } = setup(async (url, options) => {
    calls.push({ url, options });
    const offset = Number(url.searchParams.get('offset'));
    return Response.json(page(entries.slice(offset, offset + 2), { total: 3, limit: 2, offset }));
  }, { onSelectedRun: pin => pins.push(pin), limit: 2 });
  try {
    await ready(controller); assert.equal(controller.getSnapshot().status, 'ready');
    const html = render(controller);
    for (const label of ['Source', 'Priority', 'Score', 'Why flagged', 'Actions', 'Case matches', 'Connections', '+44.44 pts', '+4.44 pts', '48.88', '0.00', 'P3', 'P4']) assert.ok(html.includes(label), label);
    assert.match(html, /&lt;script&gt;source&lt;\/script&gt;/); assert.doesNotMatch(html, /<script>/);
    assert.match(html, /disabled="">Previous/);
    click(controller, 'Next'); await ready(controller);
    assert.equal(controller.getSnapshot().page.offset, 2);
    assert.match(render(controller), /disabled="">Next/);
    assert.match(render(controller), /Showing 3–3/);
    const before = calls.length; await controller.load(4); assert.equal(calls.length, before);
    click(controller, 'Previous'); await ready(controller);
    assert.equal(controller.getSnapshot().page.offset, 0);
    for (const { url, options } of calls) {
      assert.equal(url.pathname, `/api/v1/cases/${caseId}/triage`); assert.equal(options.method, 'GET');
      assert.equal(url.searchParams.get('analysis_run_id'), runId); assert.equal(url.searchParams.get('limit'), '2');
      assert.equal(options.body, undefined);
    }
    assert.ok(pins.every(pin => pin === runId));
  } finally { controller.dispose(); }
});

test('unscored entries before analysis and inside snapshots have blank score and no computed priority', async () => {
  for (const selected of [undefined, runId]) {
    const { controller } = setup(async () => Response.json(page([unscored(10)], { analysis_run_id: selected })), { pin: selected ?? null });
    try {
      await ready(controller); assert.equal(controller.getSnapshot().status, 'ready');
      const html = render(controller);
      assert.match(html, /<td>—<\/td>/);
      assert.doesNotMatch(html, /P4|0\.00|priority-badge/);
      assert.equal(html.includes('Run case analysis'), !selected);
    } finally { controller.dispose(); }
  }
});

test('latest read adopts selected snapshot then pins every page despite newer analysis/uploads', async () => {
  const calls = [], pins = [];
  const { controller } = setup(async url => {
    calls.push(new URL(url));
    const offset = Number(url.searchParams.get('offset'));
    return Response.json(page([offset ? unscored(11) : scored(10)], { total: 2, limit: 1, offset }));
  }, { pin: null, onSelectedRun: value => pins.push(value), limit: 1 });
  try {
    await ready(controller); click(controller, 'Next'); await ready(controller);
    assert.equal(calls[0].searchParams.has('analysis_run_id'), false);
    assert.equal(calls[1].searchParams.get('analysis_run_id'), runId);
    assert.equal(controller.getSnapshot().page.total, 2); assert.deepEqual(pins, [runId, runId]);
  } finally { controller.dispose(); }
});

test('live override changes effective display while automated fields and server order stay unchanged', async () => {
  let revision = 0;
  const { controller } = setup(async () => {
    const entry = scored(11, 20, 'P4');
    entry.override = { id: id(200 + revision), evidence_id: entry.evidence_id, case_id: caseId,
      actor_id: 'synthetic', created_at: time, priority: revision ? 'P2' : 'P1', reason: '<img> Investigator reason' };
    entry.effective_priority = entry.override.priority;
    const unprocessed = { ...unscored(12), override: { ...entry.override, evidence_id: id(12) }, effective_priority: entry.override.priority };
    return Response.json(page([scored(10), entry, unprocessed]));
  });
  try {
    await ready(controller); const before = controller.getSnapshot().page.items.map(e => [e.evidence_id, e.latest_result]);
    let html = render(controller); assert.match(html, /Effective priority P1/); assert.match(html, /&lt;img&gt;/);
    assert.deepEqual(controller.getSnapshot().page.items.map(entry => entry.evidence_id), [id(10), id(11), id(12)]);
    revision++; click(controller, 'Refresh priorities'); await ready(controller);
    html = render(controller); assert.match(html, /Effective priority P2/);
    assert.deepEqual(controller.getSnapshot().page.items.map(e => [e.evidence_id, e.latest_result]), before);
    assert.match(html, /<td>—<\/td>/);
  } finally { controller.dispose(); }
});

for (const failure of [401, 404, 'network']) test(`${failure} safe error and retry repeats failed page`, async () => {
  let fail = false; const offsets = [];
  const { client, controller } = setup(async url => {
    const offset = Number(url.searchParams.get('offset')); offsets.push(offset);
    if (fail) {
      if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
      return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN <script>' }, { status: failure });
    }
    return Response.json(page([offset ? unscored(11) : scored(10)], { total: 2, limit: 1, offset }));
  }, { limit: 1 });
  try {
    await ready(controller); fail = true; click(controller, 'Next'); await ready(controller);
    assert.equal(controller.getSnapshot().status, 'error'); assert.equal(controller.getSnapshot().page, null);
    assert.match(render(controller), /role="alert"/); assert.doesNotMatch(render(controller), /PRIVATE|TOKEN|<script>/);
    if (failure === 401) {
      assert.equal(client.hasToken(), false); assert.match(render(controller), /Authentication required/);
      fail = false; click(controller, 'Retry priority list'); assert.equal(controller.getSnapshot().status, 'error');
      client.setToken('synthetic-reopened'); // Case must be reselected after a session change.
      controller.dispose(); controller.start(); await ready(controller);
    } else {
      if (failure === 404) assert.match(render(controller), /unavailable or no longer accessible/);
      fail = false; click(controller, 'Retry priority list'); await ready(controller);
      assert.deepEqual(offsets, [0, 1, 1]); assert.equal(controller.getSnapshot().page.offset, 1);
    }
    assert.equal(controller.getSnapshot().status, 'ready');
  } finally { controller.dispose(); }
});

test('empty selection is honest; selected empty snapshot retains run ID', async () => {
  const { controller } = setup(async () => Response.json(page([])));
  try { await ready(controller); assert.match(render(controller), /No evidence to prioritize/); assert.equal(controller.getSnapshot().page.analysis_run_id, runId); }
  finally { controller.dispose(); }
});

test('mismatched run/case/evidence, missing pin, duplicate IDs and malformed values never render', async () => {
  const wrong = [
    page([scored(10)], { analysis_run_id: id(99) }), page([scored(10)], { analysis_run_id: undefined }),
    page([{ ...scored(10), latest_result: { ...scored(10).latest_result, case_id: id(99) } }]),
    page([{ ...scored(10), latest_result: { ...scored(10).latest_result, evidence_id: id(99) } }]),
    page([{ ...scored(10), latest_result: { ...scored(10).latest_result, analysis_run_id: id(99) } }]),
    page([scored(10), scored(10)]), page([scored(10)], { total: -1 }),
    page([scored(10)], { offset: 1 }), page([scored(10)], { limit: 0 }),
    page([{ ...scored(10), latest_result: { ...scored(10).latest_result, score: '48.88' } }]),
    page([scored(10, 20, 'P4'), scored(11)]), page([scored(10)], { total: 2 }),
  ];
  for (const response of wrong) {
    const { controller } = setup(async () => Response.json(response));
    await ready(controller); assert.equal(controller.getSnapshot().status, 'error'); assert.equal(controller.getSnapshot().page, null); controller.dispose();
  }
});

test('pinned totals, page membership and computed results cannot drift after upload or override refresh', async () => {
  for (const changed of [page([scored(10)], { total: 2 }), page([scored(11)]), page([scored(10, 49)])]) {
    let first = true;
    const { controller } = setup(async () => { const response = first ? page([scored(10)]) : changed; first = false; return Response.json(response); });
    await ready(controller); await controller.load(0);
    assert.equal(controller.getSnapshot().status, 'error'); assert.equal(controller.getSnapshot().page, null); controller.dispose();
  }
});

test('pre-analysis pagination restarts page one if a completed snapshot becomes available', async () => {
  const offsets = [];
  const { controller } = setup(async url => {
    const offset = Number(url.searchParams.get('offset')); offsets.push(offset);
    if (offsets.length === 1) return Response.json(page([unscored(10)], { analysis_run_id: undefined, limit: 1, total: 2 }));
    return Response.json(page([offset ? unscored(11) : scored(10)], { offset, limit: 1, total: 2 }));
  }, { pin: null, limit: 1 });
  try { await ready(controller); click(controller, 'Next'); await ready(controller); assert.deepEqual(offsets, [0, 1, 0]); assert.equal(controller.getSnapshot().page.offset, 0); }
  finally { controller.dispose(); }
});

test('unmount/case/pin lifecycle disposal aborts delivery; reconnect and overlapping requests ignore stale responses', async () => {
  let resolve; let signal;
  const { controller } = setup(async (_url, options) => { signal = options.signal; return new Promise(r => { resolve = r; }); });
  controller.dispose(); assert.equal(signal.aborted, true);
  resolve(Response.json(page([scored(10)]))); await pause();
  assert.equal(controller.getSnapshot().status, 'idle');
  controller.start(); assert.equal(signal.aborted, false);
  const late = resolve;
  const loading = controller.load(); const latest = resolve;
  late(Response.json(page([scored(11)]))); await pause(); assert.equal(controller.getSnapshot().status, 'loading');
  latest(Response.json(page([scored(10)]))); await loading; assert.equal(controller.getSnapshot().status, 'ready');
  controller.dispose();
  // The actual view requires the workspace context; case/pin dependencies create fresh controllers.
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000' });
  assert.match(renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(CaseAnalysisWorkspace, { caseId }, createElement(PriorityList)))), /Triage &amp; Priority/);
});

test('latest selection is shared with workspace and cannot replace an existing completed pin', () => {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000' }); client.setToken('synthetic');
  const controller = createAnalysisController(client, caseId); controller.start();
  controller.selectCompletedRun(runId); assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId);
  controller.selectCompletedRun(id(99)); assert.equal(controller.getSnapshot().pinnedAnalysisRunId, runId); controller.dispose();
});

test('case switch and session replacement abort old requests and discard late success/error', async () => {
  for (const lateFailure of [false, true]) {
    let finish, signal;
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async (url, options) => {
      if (url.pathname.includes(caseId)) {
        signal = options.signal;
        return new Promise((resolve, reject) => { finish = () => lateFailure ? reject(Error('PRIVATE')) : resolve(Response.json(page([scored(10)]))); });
      }
      return Response.json(page([unscored(90)], { analysis_run_id: id(99) }));
    } });
    client.setToken('synthetic');
    const old = createTriageController(client, caseId, runId); old.start();
    old.dispose(); assert.equal(signal.aborted, true);
    const next = createTriageController(client, id(88), id(99)); next.start(); await ready(next);
    finish(); await pause();
    assert.equal(old.getSnapshot().status, 'idle'); assert.equal(next.getSnapshot().page.items[0].evidence_id, id(90));
    next.dispose();
    old.start(); client.setToken('synthetic-replacement'); assert.equal(signal.aborted, true);
    finish(); await pause(); assert.equal(old.getSnapshot().status, 'error'); assert.equal(old.getSnapshot().page, null);
    old.dispose();
  }
});

test('cross-page duplicates or reordered computed scores are rejected without publishing mixed pages', async () => {
  for (const second of [scored(10), scored(10, 20, 'P4'), scored(11, 90, 'P1')]) {
    const { controller } = setup(async url => Response.json(page([
      Number(url.searchParams.get('offset')) ? second : scored(10),
    ], { total: 2, limit: 1, offset: Number(url.searchParams.get('offset')) })), { limit: 1 });
    await ready(controller); await controller.load(1);
    assert.equal(controller.getSnapshot().status, 'error'); assert.equal(controller.getSnapshot().page, null); controller.dispose();
  }
});

test('filenames and related sources open their exact evidence without displaying internal IDs', async () => {
  const entry = scored(10);
  entry.latest_result.factors.forEach(factor => { factor.evidence_ids.push(id(11)); });
  const { controller } = setup(async () => Response.json(page([entry])));
  try {
    await ready(controller); const inspected = [];
    const tree = PriorityListPanel({ state: controller.getSnapshot(), load: controller.load, sourceNames: { [id(10)]: 'gateway.csv', [id(11)]: 'phone.csv' }, inspectEvidence: value => inspected.push(value) });
    const sources = buttons(tree).filter(button => button.props.className === 'source-link');
    assert.equal(sources.length, 3);
    sources.forEach(button => button.props.onClick());
    assert.deepEqual(inspected, [id(10), id(11), id(11)]);
    const html = renderToStaticMarkup(tree);
    assert.match(html, /gateway\.csv/); assert.match(html, /phone\.csv/);
    assert.doesNotMatch(html, /View explanation|contributing factors|Investigative attention only|value 0\.8|weight|00000000-0000/);
  } finally { controller.dispose(); }
});
