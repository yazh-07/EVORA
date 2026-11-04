import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createGraphController, GraphPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Schema-derived synthetic Fetch doubles. Real producers exercised by cases.integration.mjs.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), runId = id(2), evidenceId = id(3), processingId = id(4), observationId = id(5);
const graph = () => ({ case_id: caseId, analysis_run_id: runId,
  nodes: ['evidence', 'entity', 'event'].map((kind, i) => ({ id: i ? id(10 + i) : evidenceId, case_id: caseId, kind,
    label: i === 1 ? 'D-7 <script>untrusted</script>' : kind, evidence_ids: [evidenceId] })),
  edges: [{ id: id(20), case_id: caseId, from_id: evidenceId, to_id: id(11), kind: 'supported_by',
    evidence_ids: [evidenceId], observation_ids: [observationId], confidence: .85 }] });
const snapshot = { case_id: caseId, evidence_ids: [evidenceId], processing_run_ids: [processingId], observation_ids: [observationId], sha256: 'a'.repeat(64) };
const observation = { id: observationId, case_id: caseId, evidence_id: evidenceId, processing_run_id: processingId,
  kind: 'network.device', source_locator: 'row 2, device_id', raw_value: 'D-7', normalized_value: 'D-7', extraction_confidence: .9 };
const run = () => ({ id: runId, case_id: caseId, status: 'completed', trigger: 'initial', algorithm_version: 'synthetic-v1', input_snapshot: snapshot,
  created_at: '2026-11-03T00:00:00Z', finished_at: '2026-11-03T00:00:01Z' });
const page = items => ({ items, total: items.length, limit: 100, offset: 0 });
const pause = () => new Promise(r => setTimeout(r, 1));
async function until(predicate) { for (let i = 0; i < 300; i++) { if (predicate()) return; await pause(); } assert.fail('Graph request did not settle'); }
const ready = c => until(() => ['ready', 'error'].includes(c.getSnapshot().status));
const render = c => renderToStaticMarkup(createElement(GraphPanel, { state: c.getSnapshot(), load: c.load, select: c.select }));
const tree = (c, inspectEvidence) => GraphPanel({ state: c.getSnapshot(), load: c.load, select: c.select, inspectEvidence });
function elements(value) {
  if (!value || typeof value !== 'object') return [];
  if (Array.isArray(value)) return value.flatMap(elements);
  return [value, ...elements(value.props?.children)];
}
function setup(fetch, pin = runId, onSelectedRun) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch }); client.setToken('synthetic-u07');
  const controller = createGraphController(client, caseId, pin ?? undefined, onSelectedRun); controller.start();
  return { client, controller };
}
const transport = async url => Response.json(url.pathname.endsWith('/graph') ? graph() : url.pathname.includes('/analysis-runs/') ? run() : page([observation]));

test('typed pinned graph, SVG kinds, escaped labels, diagram click/keyboard selection and source actions', async () => {
  const calls = [];
  const { controller: c } = setup(async (url, options) => { calls.push([url, options]); return transport(url); });
  try {
    await ready(c); assert.equal(c.getSnapshot().status, 'ready');
    assert.equal(calls[0][0].pathname, `/api/v1/cases/${caseId}/graph`);
    assert.equal(calls[0][0].searchParams.get('analysis_run_id'), runId);
    assert.equal(calls[0][1].method, 'GET'); assert.equal(calls[0][1].body, undefined);
    let html = render(c);
    for (const part of ['<svg', '<rect', '<ellipse', '<polygon', 'supported_by', '0.85', 'D-7 &lt;script&gt;']) assert.ok(html.includes(part), part);
    assert.doesNotMatch(html, /<script>/);
    const node = elements(tree(c)).find(e => e.type === 'g' && e.props['aria-label']?.startsWith('Inspect node entity'));
    node.props.onClick(); assert.equal(c.getSnapshot().selection.id, id(11));
    html = render(c); assert.match(html, /Node details/); assert.match(html, new RegExp(evidenceId));
    const inspected = [];
    elements(tree(c, id => inspected.push(id))).find(e => e.type === 'button' && e.props['aria-label']?.startsWith('Inspect source')).props.onClick();
    assert.deepEqual(inspected, [evidenceId]);
    const edge = elements(tree(c)).find(e => e.type === 'g' && e.props['aria-label']?.startsWith('Inspect relationship'));
    let prevented = false; edge.props.onKeyDown({ key: 'Enter', preventDefault: () => { prevented = true; } });
    await until(() => c.getSnapshot().citationStatus !== 'loading'); assert.equal(prevented, true);
    assert.equal(c.getSnapshot().citationStatus, 'ready');
    html = render(c); for (const part of ['Candidate relationship details', 'Relationship confidence', observationId, 'row 2, device_id', processingId]) assert.ok(html.includes(part), part);
    const sourceCalls = calls.filter(([url]) => url.pathname.endsWith('/observations'));
    assert.equal(sourceCalls[0][0].searchParams.get('processing_run_id'), processingId);
    assert.deepEqual(c.getSnapshot().citations, [observation]);
    elements(tree(c, id => inspected.push(id))).find(e => e.props['aria-label']?.endsWith('row 2, device_id')).props.onClick();
    assert.deepEqual(inspected, [evidenceId, evidenceId]);
  } finally { c.dispose(); }
});

test('empty graphs distinguish no completed run from empty selected snapshot; latest run adoption pins retries', async () => {
  for (const selected of [undefined, runId]) {
    const pins = [], calls = [];
    const { controller: c } = setup(async url => { calls.push(url); return Response.json({ case_id: caseId, nodes: [], edges: [], ...(selected && { analysis_run_id: selected }) }); }, null, id => pins.push(id));
    try {
      await ready(c); assert.match(render(c), selected ? /No graph nodes in this completed analysis/ : /No analysis run completed yet\. Start analysis/);
      await c.load(); assert.equal(calls[1].searchParams.get('analysis_run_id'), selected ?? null);
      assert.deepEqual(pins, selected ? [runId, runId] : []);
    } finally { c.dispose(); }
  }
});

test('foreign/missing/mixed run, foreign nodes/edges, duplicates, dangling endpoints and malformed confidence rejected', async () => {
  const mutations = [g => { g.analysis_run_id = id(99); }, g => { delete g.analysis_run_id; }, g => { g.case_id = id(99); },
    g => { g.nodes[0].case_id = id(99); }, g => { g.edges[0].case_id = id(99); }, g => g.nodes.push(g.nodes[0]),
    g => g.edges.push(g.edges[0]), g => { g.edges[0].to_id = id(99); }, g => { g.edges[0].confidence = 2; },
    g => { g.edges[0].observation_ids = []; }, g => { g.nodes[0].evidence_ids = []; }];
  for (const mutate of mutations) {
    const g = graph(); mutate(g); const { controller: c } = setup(async () => Response.json(g));
    await ready(c); assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().graph, null); c.dispose();
  }
});

for (const failure of [401, 404, 'network']) test(`safe ${failure} error and retry`, async () => {
  let fail = true;
  const { client, controller: c } = setup(async url => {
    if (!fail) return transport(url);
    if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
    return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN' }, { status: failure });
  });
  await ready(c); assert.equal(c.getSnapshot().status, 'error');
  assert.match(render(c), /Retry graph/); assert.doesNotMatch(render(c), /PRIVATE|TOKEN/);
  if (failure === 401) { assert.equal(client.hasToken(), false); assert.match(render(c), /Authentication required/); c.dispose(); client.setToken('new-synthetic'); }
  fail = false; if (failure === 401) c.start(); else await c.load();
  await ready(c); assert.equal(c.getSnapshot().status, 'ready'); c.dispose();
});

test('source snapshot, processing, observation, evidence joins and missing citations fail closed; retry succeeds', async () => {
  for (const bad of ['snapshot', 'pending', 'case', 'processing', 'evidence', 'missing', 'locator', 'foreign-id']) {
    let fail = true;
    const { controller: c } = setup(async url => {
      if (!fail || url.pathname.endsWith('/graph')) return transport(url);
      if (url.pathname.includes('/analysis-runs/')) {
        const r = run();
        if (bad === 'snapshot') r.input_snapshot = { ...snapshot, observation_ids: [] };
        if (bad === 'pending') r.status = 'running';
        return Response.json(r);
      }
      const item = { ...observation };
      if (bad === 'case') item.case_id = id(99);
      if (bad === 'processing') item.processing_run_id = id(99);
      if (bad === 'evidence') item.evidence_id = id(99);
      if (bad === 'locator') item.source_locator = '';
      if (bad === 'foreign-id') item.id = id(99);
      return Response.json(page(bad === 'missing' ? [] : [item]));
    });
    await ready(c); await c.select({ kind: 'edge', id: id(20) });
    assert.equal(c.getSnapshot().citationStatus, 'error', bad); assert.deepEqual(c.getSnapshot().citations, []);
    assert.match(render(c), /Retry citations/); fail = false; await c.select({ kind: 'edge', id: id(20) });
    assert.equal(c.getSnapshot().citationStatus, 'ready'); c.dispose();
  }
});

test('historical citation pagination reaches a later page without latest output substitution', async () => {
  const filler = Array.from({ length: 100 }, (_, i) => ({ ...observation, id: id(100 + i) }));
  const requests = [];
  const { controller: c } = setup(async url => {
    if (url.pathname.endsWith('/graph')) return transport(url);
    if (url.pathname.includes('/analysis-runs/')) return Response.json({ ...run(), input_snapshot: { ...snapshot, observation_ids: [...filler.map(i => i.id), observationId].sort() } });
    requests.push(url); const offset = Number(url.searchParams.get('offset'));
    return Response.json({ total: 101, limit: 100, offset, items: offset ? [observation] : filler });
  });
  await ready(c); await c.select({ kind: 'edge', id: id(20) });
  assert.equal(c.getSnapshot().citationStatus, 'ready'); assert.deepEqual(requests.map(u => u.searchParams.get('offset')), ['0', '100']); c.dispose();
});

test('unmount/case/run switch, session change, refresh and source selection abort requests and ignore late delivery', async () => {
  for (const citation of [false, true]) for (const rejectLate of [false, true]) {
    let finish, signal;
    const { client, controller: c } = setup(async (url, options) => {
      if (citation && url.pathname.endsWith('/graph')) return transport(url);
      signal = options.signal;
      return new Promise((resolve, reject) => { finish = () => rejectLate ? reject(Error('PRIVATE')) : resolve(Response.json(citation ? run() : graph())); });
    });
    if (citation) { await ready(c); void c.select({ kind: 'edge', id: id(20) }); }
    c.dispose(); assert.equal(signal.aborted, true); finish(); await pause(); assert.equal(c.getSnapshot().status, 'idle');
    // A fresh controller is the React useMemo/effect lifetime on case/run switch.
    const next = createGraphController(client, id(88), id(89)); next.start(); next.dispose(); finish(); await pause();
    c.start(); if (citation) { await ready(c); void c.select({ kind: 'edge', id: id(20) }); }
    client.setToken('replacement-synthetic'); assert.equal(signal.aborted, true); finish(); await pause();
    assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().graph, null); c.dispose();
  }
});

test('superseded graph requests and edge-to-node changes discard late success', async () => {
  const pending = [];
  const { controller: c } = setup(async (url, options) => new Promise(resolve => pending.push({ url, signal: options.signal, resolve })));
  const refresh = c.load(); assert.equal(pending[0].signal.aborted, true);
  pending[0].resolve(Response.json(graph())); await pause(); assert.equal(c.getSnapshot().status, 'loading');
  pending[1].resolve(Response.json(graph())); await refresh;
  const inspect = c.select({ kind: 'edge', id: id(20) });
  await c.select({ kind: 'node', id: evidenceId }); assert.equal(pending[2].signal.aborted, true);
  pending[2].resolve(Response.json(run())); await inspect;
  assert.equal(c.getSnapshot().selection.kind, 'node'); assert.deepEqual(c.getSnapshot().citations, []); c.dispose();
});

test('merged producer subkinds have entity/event shapes without changing wire labels', async () => {
  const g = graph(); g.nodes[1].kind = 'device'; g.nodes[2].kind = 'network.activity';
  const { controller: c } = setup(async () => Response.json(g));
  try {
    await ready(c); assert.match(render(c), /graph-node-entity/); assert.match(render(c), /graph-node-event/);
    await c.select({ kind: 'node', id: id(12) }); assert.match(render(c), /network.activity/);
  } finally { c.dispose(); }
});

for (const status of [401, 404, 'network']) test(`citation ${status} stays safe and never substitutes latest sources`, async () => {
  let fail = true;
  const { client, controller: c } = setup(async url => {
    if (!fail || url.pathname.endsWith('/graph')) return transport(url);
    if (status === 'network') throw Error('PRIVATE SOURCE');
    return Response.json({ code: 'ERROR', message: 'PRIVATE SOURCE' }, { status });
  });
  try {
    await ready(c); await c.select({ kind: 'edge', id: id(20) });
    assert.deepEqual(c.getSnapshot().citations, []); assert.doesNotMatch(render(c), /PRIVATE SOURCE/);
    if (status === 401) { assert.equal(client.hasToken(), false); assert.equal(c.getSnapshot().graph, null); }
    else {
      assert.equal(c.getSnapshot().citationStatus, 'error'); fail = false;
      const retry = elements(tree(c)).find(e => e.type === 'button' && e.props.children === 'Retry citations');
      retry.props.onClick(); await until(() => c.getSnapshot().citationStatus !== 'loading');
      assert.equal(c.getSnapshot().citationStatus, 'ready');
    }
  } finally { c.dispose(); }
});
