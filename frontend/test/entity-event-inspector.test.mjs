import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import {
  createEntityEventController, EntityEventInspector, EntityEventPanel, CaseEvidenceWorkspace, CaseAnalysisWorkspace,
} from '../.test-build/src/cases/CaseWorkspace.mjs';

// Synthetic schema-derived Fetch doubles for the live candidate endpoints.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), evidenceId = id(2), observationId = id(3);
const entity = n => ({ id: id(100 + n), case_id: caseId, kind: ['device', 'ip', 'person'][n % 3],
  canonical_label: `Candidate ${n}`, candidate_key: `device:D-${n}`, confidence: n === 0 ? 0 : 0.856,
  evidence_ids: [evidenceId], observation_ids: [observationId] });
const event = n => ({ id: id(200 + n), case_id: caseId, kind: ['network.activity', 'gps.fix', 'mobile.call'][n % 3],
  summary: `Extracted event ${n}`, observed_at_utc: '2026-10-02T03:04:05Z', confidence: 0.9,
  evidence_ids: [evidenceId], observation_ids: [observationId], entity_ids: [id(100)] });
const records = { entities: Array.from({ length: 3 }, (_, i) => entity(i)), events: Array.from({ length: 3 }, (_, i) => event(i)) };
function pageFor(url, items = records[url.pathname.split('/').at(-1)]) {
  const limit = Number(url.searchParams.get('limit')), offset = Number(url.searchParams.get('offset'));
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
}
function setup(t, fetch = async url => Response.json(pageFor(url)), limit = 2) {
  const client = createApiClient({ baseUrl: 'https://candidates.invalid', fetch }); client.setToken('synthetic-u13c');
  const controller = createEntityEventController(client, caseId, limit);
  t.after(() => controller.dispose());
  return { client, controller };
}
const props = (c, inspectEvidence = () => {}) => ({ state: c.getSnapshot(), load: c.load, selectView: c.selectView, inspectEvidence });
const render = c => renderToStaticMarkup(createElement(EntityEventPanel, props(c)));
function buttons(tree) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(buttons);
  return [...(tree.type === 'button' ? [tree] : []), ...buttons(tree.props?.children)];
}
function click(c, label) {
  const button = buttons(EntityEventPanel(props(c))).find(button => [button.props.children].flat().join('') === label);
  assert.ok(button, label); assert.ok(!button.props.disabled, `${label} enabled`); button.props.onClick();
}

for (const view of ['entities', 'events']) test(`${view}: typed GET, loading, source fields and server pagination`, async t => {
  const calls = [];
  const { controller: c } = setup(t, async (url, options) => {
    calls.push({ url, options }); return Response.json(pageFor(url));
  });
  c.start();
  if (view === 'events') click(c, 'Events');
  assert.equal(c.getSnapshot()[view].status, 'loading');
  assert.match(render(c), new RegExp(`role="status">Loading ${view}`));
  assert.match(render(c), /aria-busy="true"/);
  assert.doesNotMatch(render(c), /Showing|No .* extracted/);
  await setImmediate();
  assert.equal(c.getSnapshot()[view].status, 'ready');
  let html = render(c);
  for (const text of ['Showing 1–2 of 3', 'Supporting evidence', 'Supporting observation IDs', evidenceId, observationId]) assert.ok(html.includes(text), text);
  if (view === 'entities') {
    for (const text of ['device', 'ip', 'Candidate 0', 'device:D-0', 'Confidence: 0.00', 'Confidence: 0.86']) assert.ok(html.includes(text), text);
  } else {
    for (const text of ['network.activity', 'gps.fix', 'Extracted event 0', 'Confidence: 0.90', '<time dateTime="2026-10-02T03:04:05Z">2026-10-02T03:04:05Z</time>']) assert.ok(html.includes(text), text);
  }
  assert.match(html, /disabled="">Previous/);
  click(c, 'Next'); assert.equal(c.getSnapshot()[view].page, null); await setImmediate();
  html = render(c); assert.match(html, /Showing 3–3 of 3/); assert.match(html, /disabled="">Next/);
  assert.ok(html.includes(view === 'entities' ? 'person' : 'mobile.call'));
  click(c, 'Previous'); await setImmediate();
  click(c, `Refresh ${view}`); await setImmediate();
  const relevant = calls.filter(({ url }) => url.pathname.endsWith(`/${view}`));
  assert.deepEqual(relevant.map(({ url }) => url.searchParams.get('offset')), ['0', '2', '0', '0']);
  for (const { url, options } of relevant) {
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/${view}`);
    assert.equal(url.searchParams.get('limit'), '2');
    assert.deepEqual([...url.searchParams.keys()].sort(), ['limit', 'offset']);
    assert.equal(options.method, 'GET'); assert.equal(options.body, undefined);
  }
});

test('switching views retains independent pages and offsets and fetches events only when selected', async t => {
  const calls = [];
  const { controller: c } = setup(t, async url => { calls.push(url.pathname); return Response.json(pageFor(url)); });
  c.start(); c.start(); await setImmediate(); assert.equal(calls.length, 1);
  assert.equal(c.getSnapshot().activeView, 'entities');
  assert.equal(c.getSnapshot().events.status, 'idle');
  click(c, 'Next'); await setImmediate();
  click(c, 'Events'); await setImmediate();
  assert.match(render(c), /aria-pressed="true">Events/);
  assert.doesNotMatch(render(c), /Candidate 2|device:D-2/);
  click(c, 'Next'); await setImmediate();
  const count = calls.length;
  click(c, 'Entities'); assert.match(render(c), /Showing 3–3 of 3/); assert.match(render(c), /Candidate 2/);
  click(c, 'Events'); assert.match(render(c), /Showing 3–3 of 3/); assert.match(render(c), /Extracted event 2/);
  assert.equal(c.getSnapshot().entities.offset, 2); assert.equal(c.getSnapshot().events.offset, 2);
  click(c, 'Events'); assert.equal(calls.length, count);
  for (const offset of [-1, 0.5, NaN, Infinity]) await c.load(offset);
  assert.equal(calls.length, count);
});

for (const view of ['entities', 'events']) test(`${view}: evidence buttons invoke inspectEvidence with the source ID`, async t => {
  const { controller: c } = setup(t); c.start(); if (view === 'events') click(c, 'Events'); await setImmediate();
  const inspected = [];
  const sourceButtons = buttons(EntityEventPanel(props(c, value => inspected.push(value))))
    .filter(button => button.props['aria-label'] === `Inspect source evidence ${evidenceId}`);
  assert.equal(sourceButtons.length, 2); sourceButtons[0].props.onClick(); assert.deepEqual(inspected, [evidenceId]);
});

for (const view of ['entities', 'events']) for (const failure of [400, 401, 404, 500, 'network']) test(`${view}: ${failure} clears stale data and offers safe retry`, async t => {
  let fail = false; const offsets = [];
  const { client, controller: c } = setup(t, async url => {
    if (!url.pathname.endsWith(`/${view}`)) return Response.json(pageFor(url));
    offsets.push(Number(url.searchParams.get('offset')));
    if (fail) {
      if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
      return Response.json({ code: 'PRIVATE', message: 'PRIVATE TOKEN <script>' }, { status: failure });
    }
    return Response.json(pageFor(url));
  });
  c.start(); if (view === 'events') click(c, 'Events'); await setImmediate();
  fail = true; click(c, 'Next'); await setImmediate();
  assert.equal(c.getSnapshot()[view].status, 'error'); assert.equal(c.getSnapshot()[view].page, null);
  assert.match(render(c), /role="alert"/); assert.match(render(c), new RegExp(`Retry ${view}`));
  assert.doesNotMatch(render(c), /PRIVATE|TOKEN|<script>|Candidate 0|Extracted event 0|Showing/);
  fail = false;
  if (failure === 401) {
    assert.equal(client.hasToken(), false); assert.match(render(c), /Authentication required/);
    click(c, `Retry ${view}`); await setImmediate(); assert.equal(offsets.length, 2);
    client.setToken('synthetic-reopened');
    assert.equal(c.getSnapshot().entities.page, null); assert.equal(c.getSnapshot().events.page, null);
  }
  click(c, `Retry ${view}`); await setImmediate();
  assert.equal(c.getSnapshot()[view].status, 'ready');
  assert.deepEqual(offsets, failure === 401 ? [0, 2, 0] : [0, 2, 2]);
});

for (const view of ['entities', 'events']) test(`${view}: honest empty and out-of-range page states`, async t => {
  let total = 0;
  const { controller: c } = setup(t, async url => Response.json({ items: [], total, limit: 2, offset: Number(url.searchParams.get('offset')) }));
  c.start(); if (view === 'events') click(c, 'Events'); await setImmediate();
  assert.match(render(c), new RegExp(`No ${view} extracted for this case`));
  assert.match(render(c), /Showing 0–0 of 0/); assert.match(render(c), /disabled="">Previous/); assert.match(render(c), /disabled="">Next/);
  total = 2; await c.load(2);
  assert.match(render(c), new RegExp(`No ${view} on this page`)); assert.match(render(c), /Showing 0–0 of 2/);
  assert.doesNotMatch(render(c), /No .* extracted for this case/);
  click(c, 'Previous'); await setImmediate(); assert.equal(c.getSnapshot()[view].offset, 0);
});

test('missing event UTC timestamp is explicit and never replaced with a fabricated time', async t => {
  const { controller: c } = setup(t, async url => Response.json(pageFor(url, [{ ...event(0), observed_at_utc: undefined }])));
  c.start(); click(c, 'Events'); await setImmediate();
  assert.equal(c.getSnapshot().events.status, 'ready'); assert.match(render(c), /Observed at \(UTC\): Not provided/);
  assert.doesNotMatch(render(c), /<time/);
});

for (const view of ['entities', 'events']) test(`${view}: untrusted text and evidence attributes are escaped`, async t => {
  const unsafe = '<img src=x onerror="alert(1)"><script>untrusted</script>';
  const record = { ...(view === 'entities' ? entity(0) : event(0)), kind: unsafe, canonical_label: unsafe,
    candidate_key: unsafe, summary: unsafe, observed_at_utc: unsafe, evidence_ids: [unsafe], observation_ids: [unsafe] };
  const { controller: c } = setup(t, async url => Response.json(pageFor(url, [record])));
  c.start(); if (view === 'events') click(c, 'Events'); await setImmediate();
  assert.equal(c.getSnapshot()[view].status, 'ready');
  assert.match(render(c), /&lt;img/); assert.match(render(c), /&lt;script&gt;/); assert.match(render(c), /&quot;alert\(1\)&quot;/);
  assert.doesNotMatch(render(c), /<img|<script|dateTime="<|aria-label="Inspect source evidence </);
  const inspected = [];
  buttons(EntityEventPanel(props(c, value => inspected.push(value)))).find(button => button.props['aria-label'] === `Inspect source evidence ${unsafe}`).props.onClick();
  assert.deepEqual(inspected, [unsafe]);
});

for (const view of ['entities', 'events']) test(`${view}: malformed, duplicate and foreign records never render`, async t => {
  const item = view === 'entities' ? entity(0) : event(0);
  const valid = { items: [item], total: 1, limit: 2, offset: 0 };
  const bad = [null, { ...valid, items: {} }, { ...valid, total: -1 }, { ...valid, total: 0.5 },
    { ...valid, limit: 0 }, { ...valid, limit: 101 }, { ...valid, offset: 1 }, { ...valid, total: 0 },
    { ...valid, items: [item, item], total: 2 },
    ...[null, { ...item, case_id: id(99) }, { ...item, id: '' }, { ...item, kind: {} },
      { ...item, confidence: 2 }, { ...item, confidence: null }, { ...item, evidence_ids: [null] },
      { ...item, observation_ids: 'invalid' }, view === 'entities' ? { ...item, candidate_key: null } : { ...item, summary: {} },
      view === 'entities' ? { ...item, canonical_label: {} } : { ...item, entity_ids: null },
      ...(view === 'events' ? [{ ...item, observed_at_utc: {} }] : [])].map(item => ({ ...valid, items: [item] })),
  ];
  let response = valid;
  const { controller: c } = setup(t, async () => Response.json(response));
  c.start(); if (view === 'events') click(c, 'Events'); await setImmediate();
  for (response of bad) {
    await c.load(0); assert.equal(c.getSnapshot()[view].status, 'error'); assert.equal(c.getSnapshot()[view].page, null);
    assert.doesNotMatch(render(c), /Candidate 0|Extracted event 0/);
  }
});

for (const status of [200, 500]) test(`replaced requests discard late ${status} without disturbing either view`, async t => {
  let resolve, signal; let hold = true;
  const { controller: c } = setup(t, async (url, options) => {
    if (hold) { hold = false; signal = options.signal; return new Promise(r => { resolve = r; }); }
    return Response.json(pageFor(url));
  });
  c.start(); const entitySignal = signal;
  click(c, 'Events'); await setImmediate();
  click(c, 'Entities'); await c.load(2); assert.equal(entitySignal.aborted, true);
  const state = c.getSnapshot();
  resolve(Response.json(status === 200 ? { items: [], total: 0, limit: 2, offset: 0 } : { message: 'PRIVATE' }, { status }));
  await setImmediate(); assert.equal(c.getSnapshot(), state); assert.equal(state.entities.page.offset, 2); assert.equal(state.events.status, 'ready');
});

test('unmount/case replacement aborts both view requests and discards late responses', async t => {
  const held = [];
  const { client, controller: c } = setup(t, async (url, options) => new Promise(resolve => held.push({ url, signal: options.signal, resolve })));
  let deliveries = 0; c.subscribe(() => deliveries++);
  c.start(); click(c, 'Events'); assert.equal(held.length, 2);
  const before = deliveries; c.dispose(); assert.ok(held.every(request => request.signal.aborted));
  const next = createEntityEventController(client, id(99)); t.after(() => next.dispose()); const nextState = next.getSnapshot();
  for (const request of held) request.resolve(Response.json(pageFor(request.url)));
  await setImmediate(); assert.equal(deliveries, before); assert.equal(next.getSnapshot(), nextState);
  assert.equal(c.getSnapshot().entities.page, null); assert.equal(c.getSnapshot().events.page, null);
  await c.load(); c.selectView('events'); assert.equal(held.length, 2);
});

test('session change clears both loaded views, aborts requests and allows explicit retry', async t => {
  let hold = false; const held = [];
  const { client, controller: c } = setup(t, async (url, options) => hold
    ? new Promise(resolve => held.push({ url, signal: options.signal, resolve })) : Response.json(pageFor(url)));
  c.start(); click(c, 'Events'); await setImmediate();
  assert.equal(c.getSnapshot().entities.status, 'ready'); assert.equal(c.getSnapshot().events.status, 'ready');
  hold = true; const eventRead = c.load(); click(c, 'Entities'); const entityRead = c.load();
  client.setToken('synthetic-changed'); assert.ok(held.every(request => request.signal.aborted));
  const state = c.getSnapshot(); assert.equal(state.entities.page, null); assert.equal(state.events.page, null); assert.match(render(c), /Session changed/);
  for (const request of held) request.resolve(Response.json(pageFor(request.url)));
  await Promise.all([eventRead, entityRead]); assert.equal(c.getSnapshot(), state);
  hold = false; click(c, 'Retry entities'); await setImmediate(); assert.equal(c.getSnapshot().entities.status, 'ready');
});

test('inspector and workspace expose accessible Entities & Events navigation without invented records', () => {
  let calls = 0;
  const client = createApiClient({ baseUrl: 'https://candidates.invalid', fetch: async () => { calls++; throw Error(); } }); client.setToken('synthetic');
  const wrap = child => renderToStaticMarkup(createElement(ApiProvider, { client }, child));
  const html = wrap(createElement(CaseAnalysisWorkspace, { caseId }, createElement(CaseEvidenceWorkspace, { caseId })));
  assert.match(html, /role="tab" id="tab-entities-events" aria-controls="panel-entities-events" aria-selected="false"/);
  assert.match(html, /id="panel-entities-events" role="tabpanel" aria-labelledby="tab-entities-events" tabindex="0" style="display:none"/);
  assert.match(html, /Entities &amp; Events/); assert.match(html, /aria-label="Candidate entities and events"/);
  assert.match(html, /role="group" aria-label="Candidate view"/);
  assert.match(html, /aria-pressed="true">Entities/); assert.match(html, /aria-pressed="false">Events/);
  assert.doesNotMatch(wrap(createElement(EntityEventInspector, { caseId, inspectEvidence: () => {} })), /Candidate 0|No entities extracted|Showing/);
  assert.equal(calls, 0);
});
