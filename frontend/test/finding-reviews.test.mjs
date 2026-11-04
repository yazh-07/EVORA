import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createFindingController, FindingPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Schema-derived transport doubles, exercising the same controller and events as the inspector.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), runId = id(2), findingId = id(10);
const finding = n => ({ id: id(n), case_id: caseId, analysis_run_id: runId, kind: 'relationship',
  summary: `Candidate ${n}`, rule: 'shared-identifier/1', confidence: 0.5,
  evidence_ids: [id(40)], observation_ids: [id(50)] });
const page = { items: [finding(10), finding(11)], total: 2, limit: 20, offset: 0, analysis_run_id: runId };
const review = (n = 1, extra = {}) => ({ id: id(100 + n), case_id: caseId, finding_id: findingId,
  decision: 'needs_investigation', reason: `Investigator reason ${n}`, actor_id: 'investigator-one',
  created_at: `2026-11-04T10:00:${String(n).padStart(2, '0')}Z`, ...extra });
const pause = () => new Promise(resolve => setTimeout(resolve, 1));
async function until(condition) {
  for (let i = 0; i < 300; i++) { if (condition()) return; await pause(); }
  assert.fail('Timed out waiting for finding reviews');
}
async function setup(transport) {
  const calls = [];
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async (url, options) => {
    calls.push({ url, options });
    return url.pathname.endsWith('/reviews') ? transport(url, options) : Response.json(page);
  } });
  client.setToken('synthetic-u08b');
  const controller = createFindingController(client, caseId, runId);
  controller.start();
  await until(() => controller.getSnapshot().status === 'ready');
  return { client, controller, calls };
}
const props = c => ({ state: c.getSnapshot(), load: c.load, select: c.select,
  loadReviews: c.loadReviews, updateReview: c.updateReview, submitReview: c.submitReview });
const render = c => renderToStaticMarkup(createElement(FindingPanel, props(c)));
function elements(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => elements(child, predicate));
  return [...(predicate(tree) ? [tree] : []), ...elements(tree.props?.children, predicate)];
}
const find = (c, predicate) => {
  const element = elements(FindingPanel(props(c)), predicate)[0];
  assert.ok(element, 'Expected review control');
  return element;
};
function toggle(c, target = findingId, open = true) {
  find(c, e => e.type === 'details' && elements(e, child => child.type === 'summary' &&
    child.props['aria-label'] === `Human reviews for finding ${target}`).length)
    .props.onToggle({ currentTarget: { open } });
}
const ready = (c, target = findingId) => until(() => ['ready', 'error'].includes(c.getSnapshot().reviews[target]?.status) || c.getSnapshot().status === 'error');
function change(c, name, value, target = findingId) {
  find(c, e => e.props?.id === `review-${name}-${target}`).props.onChange({ currentTarget: { value } });
}
function submit(c, target = findingId) {
  let prevented = false;
  find(c, e => e.type === 'form' && e.props['aria-label'] === `Submit human review for finding ${target}`)
    .props.onSubmit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
}
const submitted = c => until(() => ['success', 'error'].includes(c.getSnapshot().reviews[findingId]?.submitStatus) || c.getSnapshot().status === 'error');
const reviewCalls = calls => calls.filter(({ url }) => url.pathname.endsWith('/reviews'));

test('disclosures lazily call listFindingReviews with exact identifiers and share pending reads', async () => {
  let finish;
  const { controller: c, calls } = await setup(() => new Promise(resolve => { finish = resolve; }));
  try {
    assert.equal(elements(FindingPanel(props(c)), e => e.props?.className === 'finding-review-details').length, 2);
    assert.equal(reviewCalls(calls).length, 0);
    toggle(c, findingId, false); assert.equal(reviewCalls(calls).length, 0);
    toggle(c); toggle(c);
    assert.match(render(c), /aria-busy="true"><p role="status">Loading human reviews/);
    assert.doesNotMatch(render(c), /No human reviews recorded yet/);
    assert.equal(reviewCalls(calls).length, 1);
    const { url, options } = reviewCalls(calls)[0];
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/findings/${findingId}/reviews`);
    assert.equal(url.search, '', 'Human reviews are independent of the automated run selector');
    assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
    assert.equal(options.headers.get('Authorization'), 'Bearer synthetic-u08b');
    finish(Response.json([review(1), review(2)])); await ready(c);
    assert.deepEqual(c.getSnapshot().reviews[findingId].items, [review(1), review(2)]);
    const html = render(c);
    assert.ok(html.indexOf('Investigator reason 1') < html.indexOf('Investigator reason 2'));
    assert.match(html, /Reviewer: investigator-one/);
    assert.match(html, /<time dateTime="2026-11-04T10:00:01Z">2026-11-04T10:00:01Z<\/time>/);
    toggle(c, findingId, false); toggle(c); assert.equal(reviewCalls(calls).length, 1);
    await c.loadReviews(id(999)); assert.equal(reviewCalls(calls).length, 1);
  } finally { c.dispose(); }
});

for (const decision of ['accepted', 'rejected', 'needs_investigation']) test(`reviewFinding submits ${decision}, appends the result and resets the labeled form`, async () => {
  let finish;
  const saved = review(2, { decision, reason: 'Source checked' });
  const { controller: c, calls } = await setup((_url, options) => options.method === 'GET' ?
    Response.json([review(1)]) : new Promise(resolve => { finish = resolve; }));
  try {
    toggle(c); await ready(c);
    const html = render(c);
    assert.match(html, new RegExp(`<label for="review-decision-${findingId}">Decision</label>`));
    assert.match(html, new RegExp(`<label for="review-reason-${findingId}">Reason \\(required\\)</label>`));
    for (const value of ['accepted', 'rejected', 'needs_investigation']) assert.ok(html.includes(`value="${value}"`));
    change(c, 'decision', decision); change(c, 'reason', '  Source checked \n'); submit(c);
    assert.match(render(c), /Submitting review/);
    assert.match(render(c), /<fieldset disabled="">/);
    submit(c); change(c, 'reason', 'Blocked while submitting');
    assert.equal(reviewCalls(calls).length, 2, 'Duplicate submits do not send another POST');
    const { url, options } = reviewCalls(calls)[1];
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/findings/${findingId}/reviews`);
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.get('Content-Type'), 'application/json');
    assert.deepEqual(JSON.parse(options.body), { decision, reason: 'Source checked' });
    finish(Response.json(saved, { status: 201 })); await submitted(c);
    const state = c.getSnapshot().reviews[findingId];
    assert.deepEqual(state.items, [review(1), saved]);
    assert.equal(state.reason, ''); assert.equal(state.decision, 'needs_investigation');
    assert.match(render(c), /role="status">Review submitted\./);
    assert.match(render(c), new RegExp(`<textarea[^>]*id="review-reason-${findingId}"[^>]*></textarea>`));
    assert.equal(c.getSnapshot().reviews[id(11)], undefined);
  } finally { c.dispose(); }
});

test('empty history is explicit; blank or whitespace reasons fail locally with no POST', async () => {
  const { controller: c, calls } = await setup(() => Response.json([]));
  try {
    toggle(c); await ready(c); assert.match(render(c), /No human reviews recorded yet\./);
    for (const reason of ['', '   ', '\n\t\r ']) {
      change(c, 'reason', reason); submit(c); await submitted(c);
      assert.match(render(c), /role="alert">Choose a valid decision and enter a non-empty reason/);
      assert.match(render(c), /aria-invalid="true"/);
      assert.match(render(c), new RegExp(`aria-describedby="review-error-${findingId}"`));
    }
    change(c, 'reason', 'Present'); change(c, 'decision', 'invalid'); submit(c);
    assert.equal(reviewCalls(calls).length, 1);
    assert.deepEqual(c.getSnapshot().reviews[findingId].items, []);
  } finally { c.dispose(); }
});

for (const method of ['GET', 'POST']) for (const failure of [400, 401, 404, 'network']) {
  test(`${method} ${failure} has safe errors and can be retried`, async () => {
    let fail = true;
    const { controller: c, client, calls } = await setup((_url, options) => {
      if (options.method === method && fail) {
        if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
        return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN <script>' }, { status: failure });
      }
      return options.method === 'GET' ? Response.json([review(1)]) : Response.json(review(2, { decision: 'rejected', reason: 'Contradicted' }), { status: 201 });
    });
    try {
      toggle(c); await ready(c);
      if (method === 'POST') { change(c, 'decision', 'rejected'); change(c, 'reason', 'Contradicted'); submit(c); await submitted(c); }
      assert.match(render(c), /role="alert"/); assert.doesNotMatch(render(c), /PRIVATE|TOKEN|<script>/);
      if (failure === 400) assert.match(render(c), /Check the decision and reason/);
      if (failure === 404) assert.match(render(c), /Finding or case unavailable/);
      if (failure === 'network') assert.match(render(c), method === 'GET' ? /Could not load human reviews/ : /Could not submit the review/);
      if (failure === 401) {
        assert.equal(client.hasToken(), false); assert.match(render(c), /Authentication required/);
        assert.deepEqual(c.getSnapshot().reviews, {});
        const before = calls.length; await c.loadReviews(findingId); await c.submitReview(findingId); assert.equal(calls.length, before);
        fail = false; client.setToken('synthetic-reopened'); c.dispose(); c.start();
        await until(() => c.getSnapshot().status === 'ready'); toggle(c); await ready(c);
      } else {
        fail = false;
        if (method === 'GET') {
          find(c, e => e.type === 'button' && e.props.children === 'Retry human reviews').props.onClick(); await ready(c);
        } else {
          assert.equal(c.getSnapshot().reviews[findingId].reason, 'Contradicted');
          assert.equal(c.getSnapshot().reviews[findingId].decision, 'rejected');
          assert.deepEqual(c.getSnapshot().reviews[findingId].items, [review(1)]);
        }
      }
      if (method === 'POST') {
        change(c, 'decision', 'rejected'); change(c, 'reason', 'Contradicted'); submit(c); await submitted(c);
        assert.equal(c.getSnapshot().reviews[findingId].submitStatus, 'success');
        assert.equal(c.getSnapshot().reviews[findingId].items.length, 2);
      } else assert.deepEqual(c.getSnapshot().reviews[findingId].items, [review(1)]);
      assert.equal(reviewCalls(calls).filter(call => call.options.method === method).length, 2);
    } finally { c.dispose(); }
  });
}

test('untrusted reasons and actor IDs render only as escaped text in history and new reviews', async () => {
  const unsafe = '<img src=x onerror="alert(1)"><script>PRIVATE</script> & text';
  const { controller: c } = await setup((_url, options) => options.method === 'GET' ?
    Response.json([review(1, { reason: unsafe, actor_id: unsafe })]) :
    Response.json(review(2, { decision: 'accepted', reason: unsafe, actor_id: unsafe }), { status: 201 }));
  try {
    toggle(c); await ready(c);
    for (const html of [render(c)]) {
      assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
      assert.match(html, /&lt;script&gt;PRIVATE&lt;\/script&gt; &amp; text/);
      assert.doesNotMatch(html, /<img|<script/);
    }
    change(c, 'decision', 'accepted'); change(c, 'reason', unsafe); submit(c); await submitted(c);
    assert.equal(c.getSnapshot().reviews[findingId].items.length, 2);
    assert.doesNotMatch(render(c), /<img|<script/);
    assert.match(render(c), /&lt;script&gt;/);
  } finally { c.dispose(); }
});

test('review reads and drafts are isolated by finding', async () => {
  const { controller: c, calls } = await setup(url => Response.json([review(1, {
    finding_id: url.pathname.split('/').at(-2), reason: url.pathname.split('/').at(-2),
  })]));
  try {
    toggle(c); toggle(c, id(11)); await ready(c); await ready(c, id(11));
    change(c, 'reason', 'First draft'); change(c, 'decision', 'accepted');
    change(c, 'reason', 'Second draft', id(11));
    assert.equal(c.getSnapshot().reviews[findingId].reason, 'First draft');
    assert.equal(c.getSnapshot().reviews[id(11)].reason, 'Second draft');
    assert.equal(c.getSnapshot().reviews[id(11)].decision, 'needs_investigation');
    assert.equal(reviewCalls(calls).length, 2);
  } finally { c.dispose(); }
});

test('malformed, foreign, duplicate and out-of-order review responses fail safely', async () => {
  const malformed = [null, {}, [null], [review(1, { case_id: id(99) })], [review(1, { finding_id: id(99) })],
    [review(1, { decision: 'invalid' })], [review(1, { reason: ' ' })], [review(1, { actor_id: '' })],
    [review(1, { created_at: 'PRIVATE' })], [review(1), review(1)], [review(2), review(1)]];
  for (const response of malformed) {
    const { controller: c } = await setup(() => Response.json(response));
    try {
      toggle(c); await ready(c);
      assert.equal(c.getSnapshot().reviews[findingId].status, 'error');
      assert.deepEqual(c.getSnapshot().reviews[findingId].items, []);
      assert.match(render(c), /Retry human reviews/); assert.doesNotMatch(render(c), /PRIVATE/);
    } finally { c.dispose(); }
  }
  const { controller: c } = await setup((_url, options) => options.method === 'GET' ? Response.json([]) :
    Response.json(review(1, { finding_id: id(99) }), { status: 201 }));
  try {
    toggle(c); await ready(c); change(c, 'reason', 'Check source'); submit(c); await submitted(c);
    assert.equal(c.getSnapshot().reviews[findingId].submitStatus, 'error');
    assert.deepEqual(c.getSnapshot().reviews[findingId].items, []);
    assert.equal(c.getSnapshot().reviews[findingId].reason, 'Check source');
  } finally { c.dispose(); }
});

for (const stage of ['GET', 'POST']) for (const action of ['dispose', 'page', 'session']) {
  test(`${action} aborts pending review ${stage} and ignores late results`, async () => {
    let finish, signal;
    const { controller: c, client } = await setup((_url, options) => {
      if (options.method !== stage) return Response.json([]);
      signal = options.signal; return new Promise(resolve => { finish = resolve; });
    });
    try {
      toggle(c);
      if (stage === 'POST') { await ready(c); change(c, 'reason', 'Pending review'); submit(c); }
      await until(() => finish);
      if (action === 'dispose') c.dispose();
      else if (action === 'page') await c.load(0);
      else client.setToken('synthetic-replaced');
      assert.equal(signal.aborted, true);
      finish(stage === 'GET' ? Response.json([review(1)]) : Response.json(review(1), { status: 201 })); await pause();
      assert.deepEqual(c.getSnapshot().reviews, {});
      assert.doesNotMatch(render(c), /Investigator reason|Pending review/);
    } finally { c.dispose(); }
  });
}
