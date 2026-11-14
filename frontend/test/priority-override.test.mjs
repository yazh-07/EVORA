import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createTriageController, PriorityListPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), evidenceId = id(10), runId = id(2);
const timestamp = '2026-11-04T10:00:00Z';
const result = { id: id(100), case_id: caseId, evidence_id: evidenceId, analysis_run_id: runId,
  priority: 'P3', score: 44.44, explanation: 'Automated evaluation', created_at: timestamp,
  factors: [{ name: 'relevance', value: 0.4444, weight: 1, contribution: 44.44,
    explanation: 'Computed factor', evidence_ids: [evidenceId] }] };
const override = (extra = {}) => ({ id: id(200), case_id: caseId, evidence_id: evidenceId,
  actor_id: 'investigator-one', priority: 'P1', reason: 'Urgent source check', created_at: timestamp, ...extra });
const page = { analysis_run_id: runId, items: [
  { evidence_id: evidenceId, latest_result: result, effective_priority: 'P3' },
  { evidence_id: id(11) },
], total: 2, limit: 20, offset: 0 };
const pause = () => new Promise(resolve => setTimeout(resolve, 1));
async function until(condition) {
  for (let i = 0; i < 300; i++) { if (condition()) return; await pause(); }
  assert.fail('Timed out waiting for priority override');
}
async function setup(transport, selectedPage = page) {
  const calls = [];
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async (url, options) => {
    calls.push({ url, options });
    if (url.pathname.endsWith('/priority-overrides')) return transport(url, options);
    if (url.pathname.endsWith('/triage-history')) return Response.json([result]);
    return Response.json(selectedPage);
  } });
  client.setToken('synthetic-u09b');
  const controller = createTriageController(client, caseId, runId);
  controller.start();
  await until(() => controller.getSnapshot().status === 'ready');
  return { controller, client, calls };
}
const props = c => ({ state: c.getSnapshot(), load: c.load, loadHistory: c.loadHistory,
  updateOverride: c.updateOverride, submitOverride: c.submitOverride });
const render = c => renderToStaticMarkup(createElement(PriorityListPanel, props(c)));
function elements(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => elements(child, predicate));
  return [...(predicate(tree) ? [tree] : []), ...elements(tree.props?.children, predicate)];
}
const find = (c, predicate) => {
  const element = elements(PriorityListPanel(props(c)), predicate)[0];
  assert.ok(element, 'Expected override control');
  return element;
};
function change(c, name, value, target = evidenceId) {
  find(c, e => e.props?.id === `override-${name}-${target}`).props.onChange({ currentTarget: { value } });
}
function submit(c, target = evidenceId) {
  let prevented = false;
  find(c, e => e.type === 'form' && e.props['aria-label'] === `Set priority override for evidence ${target}`)
    .props.onSubmit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
}
const submitted = (c, target = evidenceId) => until(() =>
  ['success', 'error'].includes(c.getSnapshot().overrides[target]?.status) || c.getSnapshot().status === 'error');
const posts = calls => calls.filter(({ url }) => url.pathname.endsWith('/priority-overrides'));

test('effective priority and recorded reason are visible without raw author identifiers', async () => {
  const selectedPage = { ...page, items: [{ ...page.items[0], override: override(), effective_priority: 'P1' }, page.items[1]] };
  const { controller: c, calls } = await setup(() => Response.json(override(), { status: 201 }), selectedPage);
  try {
    const html = render(c);
    assert.match(html, /Manual · automatic P3/);
    assert.match(html, /automatic P3/);
    assert.match(html, /title="Review score out of 100">44\.44<\/span>/);
    assert.match(html, /class="priority-badge priority-p1" aria-label="Effective priority P1">P1/);
    assert.match(html, /Urgent source check/);
    assert.doesNotMatch(html, /Author: investigator-one/);
    assert.equal(c.getSnapshot().page.items[0].override.created_at, timestamp);
    assert.match(html, /Not scored<\/span><\/td><td>—<\/td>/);
    assert.match(html, /Not scored/);
    assert.equal(elements(PriorityListPanel(props(c)), e => e.props?.className === 'override-details').length, 2);
    for (const target of [evidenceId, id(11)]) {
      for (const name of ['priority', 'reason']) {
        assert.ok(find(c, e => e.type === 'label' && e.props.htmlFor === `override-${name}-${target}`));
      }
      const select = find(c, e => e.type === 'select' && e.props.id === `override-priority-${target}`);
      assert.deepEqual(elements(select, e => e.type === 'option').map(e => e.props.value), ['P1', 'P2', 'P3', 'P4']);
      assert.equal(find(c, e => e.type === 'textarea' && e.props.id === `override-reason-${target}`).props.required, true);
    }
    assert.equal(posts(calls).length, 0, 'Rendering forms does not send a write');
  } finally { c.dispose(); }
});

for (const priority of ['P1', 'P2', 'P3', 'P4']) test(`setPriorityOverride submits ${priority} and updates live without changing computed results`, async () => {
  let finish;
  const saved = override({ priority });
  const { controller: c, calls } = await setup(() => new Promise(resolve => { finish = resolve; }));
  try {
    await c.loadHistory(evidenceId);
    const before = c.getSnapshot().page;
    const histories = c.getSnapshot().histories;
    change(c, 'priority', priority); change(c, 'reason', '  Urgent source check \n'); submit(c);
    assert.match(render(c), /aria-busy="true"/);
    assert.match(render(c), /role="status">Saving priority/);
    assert.equal(find(c, e => e.type === 'fieldset').props.disabled, true);
    submit(c); change(c, 'reason', 'Blocked duplicate');
    assert.equal(posts(calls).length, 1);
    assert.equal(c.getSnapshot().overrides[evidenceId].reason, '  Urgent source check \n');
    const { url, options } = posts(calls)[0];
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/evidence/${evidenceId}/priority-overrides`);
    assert.equal(url.search, '', 'Writes have no analysis or pagination query');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.get('Content-Type'), 'application/json');
    assert.equal(options.headers.get('Authorization'), 'Bearer synthetic-u09b');
    assert.deepEqual(JSON.parse(options.body), { priority, reason: 'Urgent source check' });
    finish(Response.json(saved, { status: 201 })); await submitted(c);
    const after = c.getSnapshot().page;
    assert.deepEqual(after.items.map(e => e.evidence_id), before.items.map(e => e.evidence_id));
    assert.strictEqual(after.items[0].latest_result, before.items[0].latest_result);
    assert.strictEqual(after.items[1], before.items[1]);
    assert.strictEqual(c.getSnapshot().histories, histories);
    assert.deepEqual(after.items[0].override, saved);
    assert.equal(after.items[0].effective_priority, priority);
    assert.equal(after.analysis_run_id, runId);
    assert.equal(c.getSnapshot().overrides[evidenceId].reason, '');
    assert.match(render(c), /role="status">Priority override saved\./);
    assert.equal(c.getSnapshot().page.items[0].latest_result.priority, 'P3');
    assert.match(render(c), /title="Review score out of 100">44\.44<\/span>/);
    assert.match(render(c), new RegExp(`Effective priority ${priority}`));
    assert.equal(find(c, e => e.type === 'fieldset').props.disabled, false);
  } finally { c.dispose(); }
});

test('blank and whitespace reasons and invalid priorities fail locally without a POST', async () => {
  const { controller: c, calls } = await setup(() => assert.fail('No POST expected'));
  try {
    const before = c.getSnapshot().page;
    for (const reason of ['', '   ', '\n\t\r ']) {
      change(c, 'reason', reason); submit(c); await submitted(c);
      assert.match(render(c), /role="alert">Choose a priority \(P1–P4\) and enter a non-empty reason/);
      const field = find(c, e => e.type === 'textarea' && e.props.id === `override-reason-${evidenceId}`);
      assert.equal(field.props['aria-invalid'], true);
      assert.equal(field.props['aria-describedby'], `override-error-${evidenceId}`);
    }
    change(c, 'reason', 'Valid reason'); change(c, 'priority', 'P0'); submit(c);
    await c.submitOverride(id(999)); c.updateOverride(id(999), { reason: 'Unknown evidence' });
    assert.equal(c.getSnapshot().overrides[id(999)], undefined);
    assert.equal(posts(calls).length, 0);
    assert.strictEqual(c.getSnapshot().page, before);
  } finally { c.dispose(); }
});

for (const failure of [400, 401, 404, 'network']) test(`${failure} is safe, preserves computed results and permits retry`, async () => {
  let fail = true;
  const { controller: c, client, calls } = await setup(() => {
    if (fail) {
      if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
      return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN <script>' }, { status: failure });
    }
    return Response.json(override(), { status: 201 });
  });
  try {
    const before = c.getSnapshot().page;
    change(c, 'priority', 'P1'); change(c, 'reason', 'Urgent source check'); submit(c); await submitted(c);
    assert.match(render(c), /role="alert"/);
    assert.doesNotMatch(render(c), /PRIVATE|TOKEN|<script>/);
    if (failure === 400) assert.match(render(c), /Check the priority and reason/);
    if (failure === 404) assert.match(render(c), /Evidence or case unavailable/);
    if (failure === 'network') assert.match(render(c), /Could not set priority override/);
    fail = false;
    if (failure === 401) {
      assert.equal(client.hasToken(), false);
      assert.match(render(c), /Authentication required/);
      assert.equal(c.getSnapshot().page, null);
      assert.deepEqual(c.getSnapshot().overrides, {});
      await c.submitOverride(evidenceId);
      assert.equal(posts(calls).length, 1, 'No unauthenticated retry');
      client.setToken('synthetic-reopened'); c.dispose(); c.start();
      await until(() => c.getSnapshot().status === 'ready');
      change(c, 'priority', 'P1'); change(c, 'reason', 'Urgent source check'); submit(c);
    } else {
      assert.strictEqual(c.getSnapshot().page, before, 'Failure leaves the current priorities unchanged');
      assert.equal(c.getSnapshot().overrides[evidenceId].priority, 'P1');
      assert.equal(c.getSnapshot().overrides[evidenceId].reason, 'Urgent source check');
      const retry = find(c, e => e.type === 'button' && e.props.children === 'Retry priority override');
      assert.equal(retry.props.type, 'submit'); submit(c);
    }
    await submitted(c);
    assert.equal(c.getSnapshot().overrides[evidenceId].status, 'success');
    assert.equal(c.getSnapshot().page.items[0].effective_priority, 'P1');
    assert.deepEqual(c.getSnapshot().page.items[0].latest_result, before.items[0].latest_result);
    assert.equal(posts(calls).length, 2);
    assert.equal(posts(calls)[0].options.body, posts(calls)[1].options.body);
  } finally { c.dispose(); }
});

test('existing and newly submitted override reasons and authors escape XSS payloads', async () => {
  const unsafe = '<img src=x onerror="alert(1)"><script>PRIVATE</script> & text';
  const saved = override({ reason: unsafe, actor_id: unsafe });
  const { controller: c } = await setup(() => Response.json(saved, { status: 201 }), {
    ...page, items: [{ ...page.items[0], override: saved, effective_priority: 'P1' }, page.items[1]],
  });
  const check = () => {
    const html = render(c);
    assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
    assert.match(html, /&lt;script&gt;PRIVATE&lt;\/script&gt; &amp; text/);
    assert.doesNotMatch(html, /<img|<script/);
  };
  try {
    check(); change(c, 'reason', unsafe); check(); submit(c); await submitted(c); check();
    assert.equal(c.getSnapshot().overrides[evidenceId].status, 'success');
    assert.equal(c.getSnapshot().page.items[0].override.reason, unsafe);
  } finally { c.dispose(); }
});

test('scored and unscored rows submit independently and later overrides replace the live overlay', async () => {
  const finishes = new Map();
  const { controller: c, calls } = await setup((url, options) => new Promise(resolve => {
    const target = url.pathname.split('/').at(-2);
    finishes.set(target, () => resolve(Response.json(override({
      id: id(200 + posts(calls).length), evidence_id: target, ...JSON.parse(options.body),
    }), { status: 201 })));
  }));
  try {
    change(c, 'priority', 'P2'); change(c, 'reason', 'First row');
    change(c, 'priority', 'P4', id(11)); change(c, 'reason', 'Unscored row', id(11));
    submit(c); submit(c, id(11));
    assert.equal(posts(calls).length, 2);
    finishes.get(id(11))(); await submitted(c, id(11));
    assert.equal(c.getSnapshot().overrides[evidenceId].status, 'submitting');
    assert.equal(c.getSnapshot().page.items[1].latest_result, undefined);
    assert.equal(c.getSnapshot().page.items[1].effective_priority, 'P4');
    finishes.get(evidenceId)(); await submitted(c);
    change(c, 'priority', 'P1'); change(c, 'reason', 'Revised urgency'); submit(c);
    finishes.get(evidenceId)(); await submitted(c);
    assert.equal(c.getSnapshot().page.items[0].override.reason, 'Revised urgency');
    assert.equal(c.getSnapshot().page.items[0].effective_priority, 'P1');
    assert.deepEqual(c.getSnapshot().page.items[0].latest_result, result);
    assert.match(render(c), /<td>—<\/td>/);
  } finally { c.dispose(); }
});

test('malformed and foreign override responses fail safely without replacing the current overlay', async () => {
  const bad = [null, {}, override({ case_id: id(99) }), override({ evidence_id: id(99) }),
    override({ id: 'invalid' }), override({ priority: 'P0' }), override({ priority: 'P2' }),
    override({ actor_id: '' }), override({ reason: ' ' }), override({ created_at: 'PRIVATE' })];
  for (const response of bad) {
    const existing = override({ priority: 'P4', reason: 'Existing decision' });
    const { controller: c } = await setup(() => Response.json(response, { status: 201 }), {
      ...page, items: [{ ...page.items[0], override: existing, effective_priority: 'P4' }, page.items[1]],
    });
    try {
      const before = c.getSnapshot().page;
      change(c, 'priority', 'P1'); change(c, 'reason', 'Urgent source check'); submit(c); await submitted(c);
      assert.equal(c.getSnapshot().overrides[evidenceId].status, 'error');
      assert.strictEqual(c.getSnapshot().page, before);
      assert.match(render(c), /Could not set priority override/);
      assert.doesNotMatch(render(c), /PRIVATE/);
    } finally { c.dispose(); }
  }
});

for (const action of ['dispose', 'refresh', 'session']) for (const lateFailure of [false, true]) {
  test(`${action} aborts pending overrides and discards late ${lateFailure ? 'failure' : 'success'}`, async () => {
    let finish, signal;
    const { controller: c, client } = await setup((_url, options) => {
      signal = options.signal;
      return new Promise((resolve, reject) => {
        finish = () => lateFailure ? reject(Error('PRIVATE')) : resolve(Response.json(override(), { status: 201 }));
      });
    });
    try {
      change(c, 'priority', 'P1'); change(c, 'reason', 'Pending override'); submit(c);
      if (action === 'dispose') c.dispose();
      else if (action === 'refresh') await c.load(0);
      else client.setToken('synthetic-replaced');
      assert.equal(signal.aborted, true);
      const after = c.getSnapshot();
      finish(); await pause();
      assert.strictEqual(c.getSnapshot(), after);
      assert.deepEqual(c.getSnapshot().overrides, {});
      assert.doesNotMatch(render(c), /Priority override saved|Pending override|PRIVATE/);
    } finally { c.dispose(); }
  });
}
