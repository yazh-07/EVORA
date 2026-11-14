import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createTriageController, PriorityListPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), evidenceId = id(10), runId = id(22);
const evaluation = (run, score, priority, extra = {}) => ({
  id: id(run + 100), case_id: caseId, evidence_id: evidenceId, analysis_run_id: id(run),
  score, priority, created_at: `2026-11-03T00:00:${String(run).padStart(2, '0')}Z`,
  explanation: `Evaluation from run ${run}`,
  factors: [{ name: 'relevance', value: score / 100, weight: 1, contribution: score,
    explanation: `Factor from run ${run}`, evidence_ids: [evidenceId] }], ...extra,
});
const runs = [evaluation(21, 0, 'P4'), evaluation(22, 44.44, 'P3'), evaluation(23, 20, 'P4')];
const page = { analysis_run_id: runId, items: [
  { evidence_id: evidenceId, latest_result: runs[1], effective_priority: 'P3' },
  { evidence_id: id(11) },
], total: 2, limit: 20, offset: 0 };
const pause = () => new Promise(resolve => setTimeout(resolve, 1));
async function until(condition) {
  for (let i = 0; i < 300; i++) { if (condition()) return; await pause(); }
  assert.fail('Timed out waiting for priority history');
}
async function setup(fetchHistory, selectedPage = page) {
  const calls = [];
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async (url, options) => {
    calls.push({ url, options });
    return url.pathname.endsWith('/triage-history') ? fetchHistory(url, options) : Response.json(selectedPage);
  } });
  client.setToken('synthetic-u06b');
  const controller = createTriageController(client, caseId, runId);
  controller.start();
  await until(() => controller.getSnapshot().status === 'ready');
  return { client, controller, calls };
}
const props = controller => ({ state: controller.getSnapshot(), load: controller.load, loadHistory: controller.loadHistory });
const render = controller => renderToStaticMarkup(createElement(PriorityListPanel, props(controller)));
function elements(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => elements(child, predicate));
  return [...(predicate(tree) ? [tree] : []), ...elements(tree.props?.children, predicate)];
}
function toggle(controller, target = evidenceId, open = true) {
  const details = elements(PriorityListPanel(props(controller)), element =>
    element.type === 'details' && element.props.className === 'triage-history-details');
  const disclosure = details.find(element => elements(element, child =>
    child.type === 'summary' && child.props['aria-label'] === `Priority history for evidence ${target}`).length);
  assert.ok(disclosure, `History trigger for ${target}`);
  disclosure.props.onToggle({ currentTarget: { open } });
}
function retry(controller) {
  const button = elements(PriorityListPanel(props(controller)), element =>
    element.type === 'button' && element.props.children === 'Retry priority history')[0];
  assert.ok(button, 'History retry button');
  button.props.onClick();
}
const historyReady = (controller, target = evidenceId) => until(() =>
  ['ready', 'error'].includes(controller.getSnapshot().histories[target]?.status) || controller.getSnapshot().status === 'error');

test('history disclosure lazily wires getTriageHistory with exact case/evidence IDs and honest loading', async () => {
  let finish;
  const { controller, calls } = await setup(() => new Promise(resolve => { finish = resolve; }));
  try {
    assert.equal(calls.length, 1, 'List loading does not eagerly fetch history');
    assert.equal(elements(PriorityListPanel(props(controller)), e => e.props?.className === 'triage-history-details').length, 2);
    toggle(controller, evidenceId, false);
    assert.equal(calls.length, 1, 'Closing does not fetch');
    toggle(controller);
    assert.match(render(controller), /aria-busy="true"><p role="status">Loading priority history/);
    assert.doesNotMatch(render(controller), /No historical evaluations/);
    toggle(controller);
    assert.equal(calls.length, 2, 'Repeated open events share the pending request');
    const { url, options } = calls[1];
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/evidence/${evidenceId}/triage-history`);
    assert.equal(url.search, '', 'History spans runs without a snapshot selector');
    assert.equal(options.method, 'GET');
    assert.equal(options.body, undefined);
    assert.equal(options.headers.get('Authorization'), 'Bearer synthetic-u06b');
    finish(Response.json(runs));
    await historyReady(controller);
    assert.equal(controller.getSnapshot().histories[evidenceId].status, 'ready');
  } finally { controller.dispose(); }
});

test('history shows recent score changes and selected snapshot without formulas or repeated explanations', async () => {
  const { controller } = await setup(() => Response.json(runs));
  try {
    const selected = controller.getSnapshot().page;
    toggle(controller); await historyReady(controller);
    const list = elements(PriorityListPanel(props(controller)), element => element.props?.className === 'triage-history-list')[0];
    const html = renderToStaticMarkup(list);
    assert.deepEqual(elements(list, element => element.type === 'time').map(element => element.props.dateTime), [...runs].reverse().map(run => run.created_at));
    assert.match(html, /44\.44 → 20\.00 pts/);
    assert.match(html, /0\.00 → 44\.44 pts/);
    assert.match(html, /P4 → P3/); assert.match(html, /P3 → P4/);
    assert.match(html, /Case matches −24\.44 pts/);
    assert.match(html, /Selected/);
    assert.doesNotMatch(html, /Analysis Run UUID|Evaluation from run|Factor from run|value |weight /);
    assert.strictEqual(controller.getSnapshot().page, selected);
    assert.equal(selected.items[0].latest_result.analysis_run_id, runId);
  } finally { controller.dispose(); }
});

test('consecutive runs in the same priority band report unchanged priority and the score change', async () => {
  const { controller } = await setup(() => Response.json([runs[0], evaluation(24, 10, 'P4')]));
  try {
    toggle(controller); await historyReady(controller);
    assert.equal(controller.getSnapshot().histories[evidenceId].items[1].priority, 'P4');
    assert.match(render(controller), /0\.00 → 10\.00 pts/);
  } finally { controller.dispose(); }
});

test('unscored rows have independent empty history and reopening fetches newly appended evaluations', async () => {
  let appended = false;
  const { controller, calls } = await setup(url => Response.json(url.pathname.includes(id(11)) ? [] : appended ? runs : [runs[0]]));
  try {
    toggle(controller, id(11)); await historyReady(controller, id(11));
    assert.match(render(controller), /No earlier scores\./);
    assert.match(render(controller), /Not scored<\/span><\/td><td>—<\/td>/);
    assert.equal(calls[1].url.pathname, `/api/v1/cases/${caseId}/evidence/${id(11)}/triage-history`);
    toggle(controller); await historyReady(controller);
    assert.equal(controller.getSnapshot().histories[evidenceId].items.length, 1);
    toggle(controller, evidenceId, false); appended = true;
    toggle(controller); await historyReady(controller);
    assert.deepEqual(controller.getSnapshot().histories[evidenceId].items, runs);
    assert.deepEqual(controller.getSnapshot().histories[id(11)].items, []);
    assert.equal(controller.getSnapshot().histories[evidenceId].items.length, 3);
  } finally { controller.dispose(); }
});

for (const failure of [404, 'network']) test(`${failure} history error stays local, hides private details, and retries the same evidence`, async () => {
  let fail = true;
  const { controller, calls } = await setup(() => {
    if (!fail) return Response.json(runs);
    if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
    return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN <script>' }, { status: failure });
  });
  try {
    toggle(controller); await historyReady(controller);
    assert.equal(controller.getSnapshot().status, 'ready', 'List remains available');
    assert.equal(controller.getSnapshot().histories[evidenceId].status, 'error');
    assert.match(render(controller), /role="alert"/);
    assert.match(render(controller), failure === 404 ? /Evidence or case unavailable or no longer accessible/ : /Could not load priority history/);
    assert.doesNotMatch(render(controller), /PRIVATE|TOKEN|<script>|No historical evaluations/);
    fail = false; retry(controller); await historyReady(controller);
    assert.equal(controller.getSnapshot().histories[evidenceId].status, 'ready');
    assert.deepEqual(calls.slice(1).map(call => call.url.pathname), Array(2).fill(`/api/v1/cases/${caseId}/evidence/${evidenceId}/triage-history`));
  } finally { controller.dispose(); }
});

test('401 clears session and history; reopening a session and reselecting permits history retry', async () => {
  let fail = false;
  const { client, controller, calls } = await setup(() => fail ?
    Response.json({ code: 'UNAUTHORIZED', message: 'PRIVATE TOKEN <script>' }, { status: 401 }) : Response.json(runs));
  try {
    toggle(controller); await historyReady(controller);
    fail = true; toggle(controller); await historyReady(controller);
    assert.equal(client.hasToken(), false);
    assert.deepEqual(controller.getSnapshot().histories, {});
    assert.equal(controller.getSnapshot().page, null);
    assert.match(render(controller), /Authentication required\. Open a session again before retrying/);
    assert.doesNotMatch(render(controller), /PRIVATE|TOKEN|<script>|Evaluation 1/);
    const before = calls.length;
    await controller.loadHistory(evidenceId);
    assert.equal(calls.length, before, 'No request without authentication');
    fail = false; client.setToken('synthetic-u06b-reopened');
    controller.dispose(); controller.start();
    await until(() => controller.getSnapshot().status === 'ready');
    toggle(controller); await historyReady(controller);
    assert.deepEqual(controller.getSnapshot().histories[evidenceId].items, runs);
  } finally { controller.dispose(); }
});

test('history does not expose raw model explanations or internal factor formulas', async () => {
  const malicious = '<img src=x onerror="alert(1)"><script>alert("private")</script>&';
  const factors = ['relevance', 'connectivity', 'corroboration', 'gap_relevance', 'source_quality', 'conflict_relevance', 'temporal_proximity']
    .map(name => ({ name, value: 0.5, weight: 0.125, contribution: 6.25, explanation: malicious, evidence_ids: [evidenceId] }));
  const { controller } = await setup(() => Response.json([evaluation(21, 43.75, 'P3', { explanation: malicious, factors })]));
  try {
    toggle(controller); await historyReady(controller);
    const html = render(controller);
    assert.doesNotMatch(html, /<img|<script/);
    assert.doesNotMatch(html, /&lt;img|&lt;script|weight 0\.125|value 0\.5/);
    assert.deepEqual(controller.getSnapshot().histories[evidenceId].items[0].factors, factors);

  } finally { controller.dispose(); }
});

test('malformed, duplicate or foreign history is rejected safely without replacing the list', async () => {
  for (const response of [
    {}, [null], [evaluation(21, 0, 'P4', { case_id: id(99) })],
    [evaluation(21, 0, 'P4', { evidence_id: id(99) })], [evaluation(21, '0', 'P4')],
    [evaluation(21, 0, '<script>')], [evaluation(21, 0, ['P4'])],
    [evaluation(21, 0, 'P4', { analysis_run_id: 'invalid' })],
    [evaluation(21, 0, 'P4', { created_at: 'not a date' })], [runs[0], runs[0]],
    [evaluation(21, 0, 'P4', { factors: [{ ...runs[0].factors[0], weight: 2 }] })],
  ]) {
    const { controller } = await setup(() => Response.json(response));
    try {
      toggle(controller); await historyReady(controller);
      assert.equal(controller.getSnapshot().histories[evidenceId].status, 'error');
      assert.equal(controller.getSnapshot().status, 'ready');
      assert.match(render(controller), /Could not load priority history/);
      assert.doesNotMatch(render(controller), /Evaluation 1|<script>/);
    } finally { controller.dispose(); }
  }
});

test('parallel histories do not overwrite each other when responses complete out of order', async () => {
  const finish = new Map();
  const { controller } = await setup(url => new Promise(resolve => { finish.set(url.pathname.split('/').at(-2), resolve); }));
  try {
    toggle(controller); toggle(controller, id(11));
    finish.get(id(11))(Response.json([])); await historyReady(controller, id(11));
    assert.equal(controller.getSnapshot().histories[evidenceId].status, 'loading');
    finish.get(evidenceId)(Response.json(runs)); await historyReady(controller);
    assert.deepEqual(controller.getSnapshot().histories[evidenceId].items, runs);
    assert.deepEqual(controller.getSnapshot().histories[id(11)].items, []);
  } finally { controller.dispose(); }
});

test('unmount/case/run disposal and session changes abort pending history and discard late success or failure', async () => {
  for (const sessionChange of [false, true]) for (const lateFailure of [false, true]) {
    let finish, signal;
    const { client, controller } = await setup((_url, options) => {
      signal = options.signal;
      return new Promise((resolve, reject) => { finish = () => lateFailure ? reject(Error('PRIVATE')) : resolve(Response.json(runs)); });
    });
    toggle(controller);
    if (sessionChange) client.setToken('synthetic-replacement');
    else controller.dispose();
    assert.equal(signal.aborted, true);
    finish(); await pause();
    assert.deepEqual(controller.getSnapshot().histories, {});
    assert.equal(controller.getSnapshot().status, sessionChange ? 'error' : 'idle');
    assert.doesNotMatch(render(controller), /PRIVATE|Evaluation 1/);
    controller.dispose();
  }
});
