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
    const particles = elements(tree(c)).filter(e => e.type === 'g' && e.props['data-node-id']);
    assert.equal(particles.length, 3);
    const shapes = particles.map(e => e.props.children[0]);
    assert.equal(shapes.find(e => e.type === 'rect').props.width, '28');
    assert.equal(shapes.find(e => e.type === 'ellipse').props.rx, '12');
    const diamond = shapes.find(e => e.type === 'polygon').props.points.split(' ').map(p => p.split(',').map(Number));
    assert.equal(diamond[1][0] - diamond[3][0], 24);
    assert.equal(diamond[2][1] - diamond[0][1], 24);
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

function clusteredGraph() {
  const g = graph(), second = id(30);
  g.nodes[0].label = 'Synthetic network · primary';
  g.nodes.push({ ...g.nodes[0], id: second, label: 'Synthetic network · comparison', evidence_ids: [second] },
    { ...g.nodes[1], id: id(31), label: 'Comparison device', evidence_ids: [second] },
    { ...g.nodes[1], id: id(32), label: 'Shared D-7', evidence_ids: [evidenceId, second] });
  g.edges = [];
  return g;
}
const panelState = g => ({ status: 'ready', graph: g, selection: null, message: '', citations: [], citationStatus: 'idle', citationMessage: '' });
const panel = (g, props = {}) => GraphPanel({ state: panelState(g), load: async () => {}, select: async () => {}, ...props });
const diagramNodes = value => elements(value).filter(e => e.type === 'g' && e.props.className?.startsWith('graph-node '));
const nodePoint = element => {
  const shape = element.props.children[0];
  if (shape.type === 'rect') return { x: shape.props.x + 14, y: shape.props.y + 14 };
  if (shape.type === 'ellipse') return { x: shape.props.cx, y: shape.props.cy };
  const [x, y] = shape.props.points.split(' ')[0].split(',').map(Number);
  return { x, y: y + 12 };
};
const pointsByLabel = value => new Map(diagramNodes(value).map(e => [e.props['aria-label'], nodePoint(e)]));

test('evidence, camera and document nodes use source labels in captions, clusters, search and inspection', () => {
  for (const kind of ['evidence', 'camera', 'document']) {
    const g = clusteredGraph();
    const sources = g.nodes.filter(n => n.kind === 'evidence');
    const labels = ['DMZ Firewall Logs', 'Perimeter Firewall Logs (DMZ)'];
    sources.forEach((n, i) => { n.kind = kind; n.label = 'network.csv'; n.properties = { filename: n.label, source_label: labels[i] }; });
    const value = panel(g, { view: { filter: 'All', query: 'perimeter', zoom: 1 },
      state: { ...panelState(g), selection: { kind: 'node', id: sources[1].id } } });
    for (const label of labels) {
      const node = diagramNodes(value).find(e => e.props['aria-label'] === `Inspect node ${kind}: ${label}`);
      assert.ok(node);
      assert.equal(elements(node).find(e => e.type === 'title').props.children, label);
      assert.ok(elements(value).some(e => e.props.className === 'graph-cluster' && elements(e).some(t => t.type === 'title' && t.props.children[0] === label)));
    }
    assert.equal(diagramNodes(value).filter(e => e.props['data-search-match']).length, 1);
    assert.ok(elements(value).some(e => e.type === 'dd' && e.props.children === labels[1]));
    const filenameSearch = panel(g, { view: { filter: 'All', query: 'network.csv', zoom: 1 } });
    assert.equal(diagramNodes(filenameSearch).filter(e => e.props['data-search-match']).length, 2);
  }
});

test('duplicate evidence captions have visible stable counters even with long labels or legacy filenames', () => {
  for (const sourceLabels of [[undefined, undefined], ['Fleet GPS Telemetry', 'Fleet GPS Telemetry'],
    ['A very long descriptive source label first', 'A very long descriptive source label second']]) {
    const g = clusteredGraph();
    const sources = g.nodes.filter(n => n.kind === 'evidence');
    sources.forEach((n, i) => { n.label = 'gps.csv'; n.properties = { filename: n.label, source_label: sourceLabels[i] }; });
    const captions = value => new Map(diagramNodes(value).filter(e => sources.some(n => n.id === e.props['data-node-id']))
      .map(e => [e.props['data-node-id'], elements(e).find(t => t.type === 'text').props.children[1]]));
    const value = panel(g), original = captions(value);
    assert.equal(new Set(original.values()).size, 2);
    assert.match(original.get(sources[0].id), /^#1 · /);
    assert.match(original.get(sources[1].id), /^#2 · /);
    assert.deepEqual(captions(panel({ ...g, nodes: [...g.nodes].reverse() })), original);
    assert.deepEqual(captions(panel(g, { view: { filter: 'Evidence', query: '', zoom: 1 } })), original);
    for (const cluster of elements(value).filter(e => e.props.className === 'graph-cluster')) {
      assert.match(elements(cluster).find(e => e.type === 'title').props.children[0], /^#[12] · /);
    }
  }
});

test('empty or invalid source labels fall back to filenames and entity labels are preserved', () => {
  for (const sourceLabel of ['', null, 42]) {
    const g = graph();
    g.nodes.forEach(n => { n.properties = { source_label: sourceLabel }; });
    assert.deepEqual([...pointsByLabel(panel(g)).keys()], [...pointsByLabel(panel(graph())).keys()]);
  }
  const g = graph();
  g.nodes[1].properties = { source_label: 'Do not replace an entity label' };
  assert.deepEqual([...pointsByLabel(panel(g)).keys()], [...pointsByLabel(panel(graph())).keys()]);
});

test('unlinked provenance clusters seed compact particles and put a shared entity between evidence hubs', () => {
  const g = clusteredGraph(), value = panel(g), points = pointsByLabel(value);
  const point = label => points.get(`Inspect node ${label}`);
  const primary = point('evidence: Synthetic network · primary'), comparison = point('evidence: Synthetic network · comparison');
  const shared = point('entity: Shared D-7');
  assert.equal(elements(value).filter(e => e.props?.className === 'graph-cluster').length, 2);
  assert.equal(shared.x, (primary.x + comparison.x) / 2);
  assert.equal(shared.y, (primary.y + comparison.y) / 2);
  assert.ok(Math.abs(point('entity: D-7 <script>untrusted</script>').x - primary.x) < Math.abs(primary.x - comparison.x) / 2);
  const html = renderToStaticMarkup(createElement(GraphPanel, { state: panelState(g), load: async () => {}, select: async () => {} }));
  for (const text of ['No candidate relationships in this snapshot', 'Source evidence', 'Cross-source correlation', 'Synthetic network · primary', 'Synthetic network · comparison']) assert.ok(html.includes(text), text);
  assert.equal(elements(value).filter(e => e.props?.className === 'graph-edge').length, 0, 'provenance grouping never fabricates edges');
  assert.deepEqual(pointsByLabel(panel({ ...g, nodes: [...g.nodes].reverse() })), points, 'wire order does not move nodes');
});

test('dense source groups have distinct bounded particle positions and missing anchors stay explicit', () => {
  const g = clusteredGraph();
  g.nodes.push(...Array.from({ length: 60 }, (_, i) => ({ ...g.nodes[1], id: id(1000 + i), label: `Device ${i}` })));
  g.nodes.push({ ...g.nodes[1], id: id(2000), label: 'No source anchor', evidence_ids: [id(2001)] });
  const value = panel(g), points = [...pointsByLabel(value).values()];
  const svg = elements(value).find(e => e.type === 'svg');
  const [left, top, width, height] = svg.props.viewBox.split(' ').map(Number);
  for (const p of points) {
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
    assert.ok(p.x - 14 >= left && p.x + 14 <= left + width);
    assert.ok(p.y - 14 >= top && p.y + 14 <= top + height);
  }
  for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
    assert.ok(Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y) >= 28, `nodes ${i} and ${j} overlap`);
  }
  assert.equal(elements(value).filter(e => e.props?.className === 'graph-cluster').length, 3);
  assert.ok(elements(value).some(e => e.type === 'title' && String(e.props.children).includes(id(2001))));
});

test('filters preserve source positions, hide incident edges and retain inspection context', () => {
  const g = graph(), original = pointsByLabel(panel(g));
  for (const [filter, kind] of [['Evidence', 'evidence'], ['Entities', 'entity'], ['Events', 'event']]) {
    const value = panel(g, { view: { filter, query: '', zoom: 1 }, state: { ...panelState(g), selection: { kind: 'node', id: evidenceId } } });
    const nodes = diagramNodes(value);
    assert.equal(nodes.length, 1);
    assert.ok(nodes[0].props.className.endsWith(kind));
    assert.deepEqual(nodePoint(nodes[0]), original.get(nodes[0].props['aria-label']));
    assert.equal(elements(value).filter(e => e.props?.className === 'graph-edge').length, 0);
    assert.ok(elements(value).some(e => e.type === 'h3' && e.props.children === 'Node details'));
  }
});

test('search safely highlights matching labels, kinds and source IDs without removing nodes', () => {
  const g = graph();
  for (const [query, expected] of [['d-7 <SCRIPT>', 1], ['NETWORK', 0], [evidenceId, 3], ['  entity  ', 1], ['<img src=x onerror=alert(1)>', 0]]) {
    const value = panel(g, { view: { filter: 'All', query, zoom: 1 } });
    assert.equal(diagramNodes(value).length, 3);
    assert.equal(diagramNodes(value).filter(e => e.props['data-search-match']).length, expected, query);
  }
});

test('toolbar dispatches bounded zoom, reset, filter and search changes through controlled view state', () => {
  let view = { filter: 'All', query: '', zoom: 1 };
  const value = () => panel(graph(), { view, onViewChange: next => { view = next; } });
  const button = label => elements(value()).find(e => e.type === 'button' && (e.props['aria-label'] === label || e.props.children === label));
  button('Zoom in').props.onClick(); assert.ok(Math.abs(view.zoom - 1.2) < .0001);
  button('Zoom out').props.onClick(); assert.equal(view.zoom, 1);
  button('Events').props.onClick(); assert.equal(view.filter, 'Events');
  elements(value()).find(e => e.type === 'input').props.onChange({ target: { value: 'D-7' } });
  assert.equal(view.query, 'D-7');
  let reset = false;
  button('Reset view').props.onClick({ currentTarget: { closest: () => ({ querySelector: () => ({ scrollTo: (x, y) => { reset = x === 0 && y === 0; } }) }) } });
  assert.ok(reset); assert.equal(view.zoom, 1); assert.equal(view.query, 'D-7');
  view = { ...view, zoom: 2.4 }; assert.equal(button('Zoom in').props.disabled, true);
  view = { ...view, zoom: .4 }; assert.equal(button('Zoom out').props.disabled, true);
  const svg = elements(value()).find(e => e.type === 'svg');
  assert.equal(svg.props.style.width, '100%', 'zoom transforms the world within a fixed viewport');
  assert.equal(svg.props.style.touchAction, 'none');
  assert.equal(svg.props['aria-label'], 'Candidate relationship diagram');
});

test('parallel and reversed candidate relationships retain separate labels, confidence and hit lines', () => {
  const g = graph();
  g.edges.push({ ...g.edges[0], id: id(21), from_id: id(11), to_id: evidenceId, kind: 'shared_identifier', confidence: .93 });
  const edges = elements(panel(g)).filter(e => e.props?.className === 'graph-edge');
  const captions = edges.map(e => elements(e).find(item => item.props?.className === 'graph-edge-caption'));
  assert.notEqual(captions[0].props.transform, captions[1].props.transform, 'parallel relationship pills occupy separate positions');
  const labels = edges.map(e => elements(e).find(item => item.type === 'text'));
  assert.notDeepEqual([labels[0].props.x, labels[0].props.y], [labels[1].props.x, labels[1].props.y]);
  for (const edge of edges) {
    assert.equal(edge.props.role, 'button'); assert.equal(edge.props.tabIndex, 0);
    assert.ok(elements(edge).some(e => e.type === 'line' && e.props.className === 'graph-edge-hit'));
    assert.ok(elements(edge).some(e => e.type === 'line' && e.props.markerEnd));
  }
});

test('settings hide only lineage rays and switch evidence captions to filenames', () => {
  const g = graph();
  g.nodes[0].properties = { source_label: 'Source description', filename: 'capture.csv' };
  const settings = { show_provenance_rays: false, default_node_label: 'filename' };
  const value = panel(g, { settings });
  const rays = elements(value).find(e => e.props.className === 'graph-provenance-rays');
  assert.equal(rays.props.display, 'none');
  assert.equal(elements(value).filter(e => e.props.className === 'graph-edge').length, g.edges.length);
  assert.ok(diagramNodes(value).some(e => e.props['aria-label'] === 'Inspect node evidence: capture.csv'));
  const restored = panel(g, { settings: { show_provenance_rays: true, default_node_label: 'source_description' } });
  assert.equal(elements(restored).find(e => e.props.className === 'graph-provenance-rays').props.display, undefined);
  assert.ok(diagramNodes(restored).some(e => e.props['aria-label'] === 'Inspect node evidence: Source description'));
});

test('raw event toggle hides event variants and incident edges while preserving entities and evidence', () => {
  const g = graph();
  g.nodes.push({ ...g.nodes[2], id: id(50), kind: 'network.activity' },
    { ...g.nodes[2], id: id(51), kind: 'custom', entity_type: 'event' });
  g.edges.push({ ...g.edges[0], id: id(52), to_id: id(50) });
  let view = { filter: 'All', query: '', zoom: 1 };
  const value = () => panel(g, { view, onViewChange: next => { view = next; } });
  const toggle = () => elements(value()).find(e => e.type === 'button' && e.props.children === 'Hide raw log events');
  toggle().props.onClick();
  assert.equal(toggle().props['aria-pressed'], true);
  assert.equal(diagramNodes(value()).length, 2);
  assert.equal(elements(value()).filter(e => e.props.className === 'graph-edge').length, 1);
  toggle().props.onClick();
  assert.equal(diagramNodes(value()).length, 5);
});

test('evidence UUID captions fall back to clean filenames', () => {
  const g = graph();
  g.nodes[0].label = evidenceId;
  g.nodes[0].properties = { filename: '/uploads/network.csv' };
  assert.ok(diagramNodes(panel(g)).some(e => e.props['aria-label'] === 'Inspect node evidence: network.csv'));
});

test('focusing a selected node shows only it and direct neighbors without dropping the underlying graph', () => {
  const source=graph();
  const state={status:'ready',graph:source,selection:{kind:'node',id:evidenceId},citations:[],citationStatus:'idle',message:''};
  const focused=GraphPanel({state,load:async()=>{},select:async()=>{},view:{filter:'All',query:'',zoom:1,focusSelection:true}});
  assert.deepEqual(elements(focused).filter(item=>item.props?.['data-node-id']).map(item=>item.props['data-node-id']).sort(),[evidenceId,id(11)].sort());
  assert.equal(source.nodes.length,3);
  const complete=GraphPanel({state:{...state,selection:null},load:async()=>{},select:async()=>{},view:{filter:'All',query:'',zoom:1,focusSelection:true}});
  assert.equal(elements(complete).filter(item=>item.props?.['data-node-id']).length,3);
});
