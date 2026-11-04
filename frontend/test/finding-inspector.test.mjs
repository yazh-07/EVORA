import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createFindingController, FindingPanel, FindingInspector, CaseAnalysisWorkspace } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';

// Synthetic schema-derived Fetch doubles; real producer acceptance is in cases.integration.mjs.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), runId = id(2), processingId = id(3);
const finding = n => ({ id: id(n), case_id: caseId, analysis_run_id: runId, kind: 'relationship',
  summary: 'Candidate match <script>untrusted</script>', rule: 'shared-identifier/1', confidence: 0,
  evidence_ids: [id(40)], observation_ids: [id(50)], contradicting_evidence_ids: [id(41)], missing_information: ['Identity remains unknown <img>'] });
const page = (items = [], extra = {}) => ({ items, total: items.length, limit: 20, offset: 0, analysis_run_id: runId, ...extra });
const run = () => ({ id: runId, case_id: caseId, status: 'completed', input_snapshot: { case_id: caseId,
  evidence_ids: [id(40), id(41)], observation_ids: [id(50)], processing_run_ids: [processingId] } });
const observation = () => ({ id: id(50), case_id: caseId, evidence_id: id(40), processing_run_id: processingId, source_locator: 'row 2, device_id <img>' });
async function until(fn) { for (let i = 0; i < 300; i++) { if (fn()) return; await new Promise(r => setTimeout(r, 1)); } assert.fail('Finding state timeout'); }
const settled = c => until(() => ['ready', 'error'].includes(c.getSnapshot().status));
function setup(fetch, { pin = runId, limit = 20, onSelectedRun } = {}) {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch }); client.setToken('synthetic-u07b');
  const controller = createFindingController(client, caseId, pin ?? undefined, onSelectedRun, limit); controller.start();
  return { client, controller };
}
const props = c => ({ state: c.getSnapshot(), load: c.load, select: c.select });
const render = c => renderToStaticMarkup(createElement(FindingPanel, props(c)));
function buttons(e) { return !e || typeof e !== 'object' ? [] : Array.isArray(e) ? e.flatMap(buttons) :
  [...(e.type === 'button' ? [e] : []), ...buttons(e.props?.children)]; }
function click(c, label) { const b = buttons(FindingPanel(props(c))).find(b => b.props.children === label); assert.ok(b, label); assert.ok(!b.props.disabled); b.props.onClick(); }

test('typed GET, safe list/details, authoritative pagination and source navigation', async () => {
  const calls = [], pins = [], entries = [finding(10), finding(11), finding(12)];
  const { controller: c } = setup(async (url, options) => {
    calls.push({ url, options }); const offset = Number(url.searchParams.get('offset'));
    return Response.json(page(entries.slice(offset, offset + 2), { total: 3, limit: 2, offset }));
  }, { limit: 2, onSelectedRun: pin => pins.push(pin) });
  try {
    await settled(c); assert.equal(c.getSnapshot().status, 'ready'); const html = render(c);
    for (const text of ['relationship', 'Candidate match', 'Confidence: 0.00', 'shared-identifier/1', 'Supporting evidence IDs', 'Supporting observation IDs', 'Contradicting evidence IDs', 'Missing information', id(40), id(41), id(50)]) assert.ok(html.includes(text), text);
    assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img&gt;/); assert.doesNotMatch(html, /<script>|<img>/);
    assert.match(html, /disabled="">Previous/); click(c, 'Next'); await settled(c);
    assert.equal(c.getSnapshot().page.offset, 2); assert.match(render(c), /Showing 3–3/); assert.match(render(c), /disabled="">Next/);
    const before = calls.length; await c.load(4); await c.load(-1); assert.equal(calls.length, before);
    click(c, 'Previous'); await settled(c); assert.equal(c.getSnapshot().page.offset, 0);
    for (const { url, options } of calls) { assert.equal(url.pathname, `/api/v1/cases/${caseId}/findings`); assert.equal(url.searchParams.get('analysis_run_id'), runId); assert.equal(url.searchParams.get('limit'), '2'); assert.equal(options.method, 'GET'); assert.equal(options.body, undefined); }
    assert.ok(pins.every(pin => pin === runId));
    const inspected = [];
    const sourceButtons = buttons(FindingPanel({ ...props(c), inspectEvidence: value => inspected.push(value) })).filter(b => b.props['aria-label']?.startsWith('Inspect source evidence'));
    sourceButtons[0].props.onClick(); assert.deepEqual(inspected, [id(40)]);
  } finally { c.dispose(); }
});

test('latest discovery adopts shared completed pin and retains it on every page', async () => {
  const calls = [], pins = [];
  const { controller: c } = setup(async url => { calls.push(url); const offset = Number(url.searchParams.get('offset'));
    return Response.json(page([finding(10 + offset)], { total: 2, limit: 1, offset }));
  }, { pin: null, limit: 1, onSelectedRun: value => pins.push(value) });
  try { await settled(c); click(c, 'Next'); await settled(c); assert.equal(calls[0].searchParams.has('analysis_run_id'), false); assert.equal(calls[1].searchParams.get('analysis_run_id'), runId); assert.deepEqual(pins, [runId, runId]); }
  finally { c.dispose(); }
});

test('no completed run and completed empty findings are distinct honest states', async () => {
  for (const pin of [null, runId]) {
    const { controller: c } = setup(async () => Response.json(page([], { analysis_run_id: pin ?? undefined })), { pin });
    try { await settled(c); assert.equal(c.getSnapshot().status, 'ready'); assert.match(render(c), pin ? /No findings in this completed analysis/ : /No completed analysis run/); assert.match(render(c), /disabled="">Next/); }
    finally { c.dispose(); }
  }
});

for (const failure of [401, 404, 'network']) test(`${failure} uses safe error, clears stale data and retries`, async () => {
  let fail = false; const offsets = [];
  const { client, controller: c } = setup(async url => {
    const offset = Number(url.searchParams.get('offset')); offsets.push(offset);
    if (fail) { if (failure === 'network') throw Error('PRIVATE TOKEN'); return Response.json({ code: 'ERROR', message: 'PRIVATE TOKEN' }, { status: failure }); }
    return Response.json(page([finding(10 + offset)], { total: 2, limit: 1, offset }));
  }, { limit: 1 });
  try {
    await settled(c); fail = true; click(c, 'Next'); await settled(c); assert.equal(c.getSnapshot().page, null); assert.match(render(c), /role="alert"/); assert.doesNotMatch(render(c), /PRIVATE|Candidate match/);
    fail = false;
    if (failure === 401) { assert.equal(client.hasToken(), false); assert.match(render(c), /Authentication required/); click(c, 'Retry findings'); assert.equal(c.getSnapshot().status, 'error'); client.setToken('synthetic-reopened'); c.dispose(); c.start(); await settled(c); }
    else { click(c, 'Retry findings'); await settled(c); assert.deepEqual(offsets, [0, 1, 1]); }
    assert.equal(c.getSnapshot().status, 'ready');
  } finally { c.dispose(); }
});

test('run mismatches are rejected and retry refetches the original pinned run', async () => {
  for (const wrong of [page([finding(10)], { analysis_run_id: id(99) }), page([finding(10)], { analysis_run_id: undefined }), page([{ ...finding(10), analysis_run_id: id(99) }])]) {
    let fail = true; const calls = [];
    const { controller: c } = setup(async url => { calls.push(url); return Response.json(fail ? wrong : page([finding(10)])); });
    try { await settled(c); assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().page, null); fail = false; click(c, 'Retry findings'); await settled(c); assert.equal(c.getSnapshot().status, 'ready'); assert.ok(calls.every(url => url.searchParams.get('analysis_run_id') === runId)); }
    finally { c.dispose(); }
  }
});

test('malformed, foreign and duplicate findings fail closed', async () => {
  const bad = [page([{ ...finding(10), case_id: id(99) }]), page([finding(10), finding(10)]), page([finding(10)], { total: 2 }), page([finding(10)], { limit: 1 }), page([finding(10)], { offset: 1 }), page([{ ...finding(10), evidence_ids: [] }]), page([{ ...finding(10), observation_ids: [] }]), page([{ ...finding(10), confidence: 2 }]), page([{ ...finding(10), kind: 'candidate_match' }])];
  for (const response of bad) { const { controller: c } = setup(async () => Response.json(response)); try { await settled(c); assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().page, null); } finally { c.dispose(); } }
});

test('snapshot total and membership stay immutable across pages and refresh', async () => {
  for (const mode of ['total', 'duplicate', 'mutation']) {
    let changed = false;
    const { controller: c } = setup(async url => { const offset = Number(url.searchParams.get('offset'));
      return Response.json(page([{ ...finding(mode === 'duplicate' ? 10 : 10 + offset), summary: changed && mode === 'mutation' ? 'Changed' : finding(10).summary }], { total: changed && mode === 'total' ? 3 : 2, limit: 1, offset }));
    }, { limit: 1 });
    try { await settled(c); changed = true; await c.load(mode === 'mutation' ? 0 : 1); assert.equal(c.getSnapshot().status, 'error'); }
    finally { c.dispose(); }
  }
});

test('detail resolves frozen observations over all pages; source errors retry without live fallback', async () => {
  const calls = []; let fail = true;
  const manifest = run(); manifest.input_snapshot.observation_ids.push(...Array.from({ length: 100 }, (_, i) => id(1000 + i)));
  const { controller: c } = setup(async url => {
    calls.push(url);
    if (url.pathname.endsWith('/findings')) return Response.json(page([finding(10)]));
    if (url.pathname.includes('/analysis-runs/')) return Response.json(manifest);
    assert.equal(url.searchParams.get('processing_run_id'), processingId);
    if (fail) return Response.json({ code: 'NOT_FOUND', message: 'PRIVATE' }, { status: 404 });
    const offset = Number(url.searchParams.get('offset'));
    const items = Array.from({ length: 101 }, (_, i) => ({ ...observation(), id: id(1000 + i) })); items[100] = observation();
    return Response.json({ items: items.slice(offset, offset + 100), total: 101, limit: 100, offset });
  });
  try {
    await settled(c);
    await c.select(id(10)); assert.equal(c.getSnapshot().citationStatus, 'error'); assert.match(render(c), /Retry finding sources/); assert.doesNotMatch(render(c), /PRIVATE/);
    fail = false; click(c, 'Retry finding sources'); await until(() => c.getSnapshot().citationStatus !== 'loading');
    assert.equal(c.getSnapshot().citationStatus, 'ready', c.getSnapshot().citationMessage);
    assert.deepEqual(c.getSnapshot().citations, [observation()]); assert.match(render(c), /row 2, device_id &lt;img&gt;/);
    assert.deepEqual(calls.filter(url => url.pathname.endsWith('/observations')).map(url => url.searchParams.get('offset')), ['0', '0', '100']);
  } finally { c.dispose(); }
});


test('foreign, missing and non-snapshot source records fail closed', async () => {
  for (const change of [o => ({ ...o, case_id: id(99) }), o => ({ ...o, processing_run_id: id(99) }), o => ({ ...o, evidence_id: id(41) }), o => ({ ...o, id: id(99) }), o => ({ ...o, source_locator: '' })]) {
    const { controller: c } = setup(async url => Response.json(url.pathname.endsWith('/findings') ? page([finding(10)]) : url.pathname.includes('/analysis-runs/') ? run() : { items: [change(observation())], total: 1, limit: 100, offset: 0 }));
    try { await settled(c); await c.select(id(10)); assert.equal(c.getSnapshot().citationStatus, 'error'); assert.deepEqual(c.getSnapshot().citations, []); }
    finally { c.dispose(); }
  }
});

test('dispose on unmount/case replacement aborts list and source reads and ignores late delivery', async () => {
  for (const stage of ['list', 'sources']) {
    let resolve, signal;
    const { controller: c, client } = setup(async (url, options) => {
      if (stage === 'sources' && url.pathname.endsWith('/findings')) return Response.json(page([finding(10)]));
      signal = options.signal; return new Promise(r => { resolve = r; });
    });
    let selecting;
    if (stage === 'sources') { await settled(c); selecting = c.select(id(10)); }
    await until(() => resolve); c.dispose(); assert.equal(signal.aborted, true);
    const replacement = createFindingController(client, id(99), runId); // Same lifecycle as case switch.
    resolve(Response.json(stage === 'list' ? page([finding(10)]) : run())); await selecting; await new Promise(r => setTimeout(r, 1));
    assert.equal(c.getSnapshot().status, 'idle'); assert.equal(c.getSnapshot().page, null); assert.equal(replacement.getSnapshot().page, null); replacement.dispose();
  }
});

test('page switch cancels pending detail sources; session replacement clears findings', async () => {
  let resolve, signal;
  const { client, controller: c } = setup(async (url, options) => {
    if (url.pathname.endsWith('/findings')) { const offset = Number(url.searchParams.get('offset')); return Response.json(page([finding(10 + offset)], { total: 2, limit: 1, offset })); }
    signal = options.signal; return new Promise(r => { resolve = r; });
  }, { limit: 1 });
  try { await settled(c); const selecting = c.select(id(10)); await until(() => resolve); await c.load(1); assert.equal(signal.aborted, true); resolve(Response.json(run())); await selecting; assert.equal(c.getSnapshot().selectedId, null); assert.equal(c.getSnapshot().page.offset, 1); client.setToken('synthetic-new-session'); assert.equal(c.getSnapshot().page, null); assert.equal(c.getSnapshot().status, 'error'); }
  finally { c.dispose(); }
});

test('finding component composes with shared case analysis context', () => {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000' }); client.setToken('synthetic');
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(CaseAnalysisWorkspace, { caseId }, createElement(FindingInspector))));
  assert.match(html, /Findings/); assert.match(html, /Start Analysis/);
});
