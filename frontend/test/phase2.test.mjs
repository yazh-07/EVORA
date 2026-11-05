import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { parseMediaLocator, detectionVisible, detectionStyle } from '../.test-build/src/cases/mediaLocators.mjs';
import { resolveSourceObservations } from '../.test-build/src/cases/sourceObservations.mjs';
import { loadCaseMetrics } from '../.test-build/src/cases/metricsData.mjs';
import { AnswerMarkdown } from '../.test-build/src/cases/AnswerMarkdown.mjs';
import { graphAppearance } from '../.test-build/src/cases/graphAppearance.mjs';
import { QuestionAnswerPanel, createQuestionController, createObservationController } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';

const signal = () => new AbortController().signal;
const observation = (i, run = 'run1') => ({ id: `o${i}`, case_id: 'c', evidence_id: 'e', processing_run_id: run,
  source_locator: `frame=${i}; time_offset=${i}s; box=10,20,30,40`, raw_value: 'person:face', extraction_confidence: .8 });

test('media locators parse Phase 1 pixels and offsets without guessing invalid numbers or frame rates', () => {
  assert.deepEqual(parseMediaLocator('frame=120; time_offset=4.000000s; box=10,20,30,40'), { frame: 120, seconds: 4, box: { x: 10, y: 20, width: 30, height: 40 } });
  for (const source of ['box=-1,2,3,4', 'box=1,2,0,4', 'box=1,2,3,NaN', 'frame=-1; time_offset=Infinity', 'box=1,2,3,4junk']) assert.deepEqual(parseMediaLocator(source), {});
  const locator = parseMediaLocator('frame=120; box=1,2,3,4');
  assert.equal(detectionVisible(locator, 4, true), false);
  assert.equal(detectionVisible(locator, 4, true, 30), true);
  assert.equal(detectionVisible(locator, 5, true, 30), false);
  assert.equal(detectionVisible(locator, 0, false), true);
  assert.equal(detectionVisible({ ...locator, seconds: 4 }, 4.02, true), true);
  assert.equal(detectionVisible({ ...locator, seconds: 4 }, 4.5, true), false);
  assert.equal(detectionStyle('person:face').color, '#f59e0b');
  assert.equal(detectionStyle('vehicle:plate').color, '#06b6d4');
  assert.equal(detectionStyle('bag').color, '#8b5cf6');
});

test('media reads every page, pins processing output and rejects mixed-source or incomplete responses', async () => {
  const queries = [], all = Array.from({ length: 103 }, (_, i) => observation(i));
  const client = { request: async (_method, _path, { query }) => {
    queries.push(query); return { items: all.slice(query.offset, query.offset + 100), limit: 100, offset: query.offset, total: all.length };
  } };
  assert.equal((await resolveSourceObservations(client, 'c', 'e', signal())).length, 103);
  assert.equal(queries[0].processing_run_id, undefined);
  assert.equal(queries[1].processing_run_id, 'run1');
  all[102] = { ...all[102], processing_run_id: 'foreign-run' };
  await assert.rejects(resolveSourceObservations(client, 'c', 'e', signal()), /Invalid source/);
  await assert.rejects(resolveSourceObservations({ request: async () => ({ total: 103, offset: 0, limit: 100, items: [] }) }, 'c', 'e', signal()), /Inconsistent/);
});

test('citation UUID resolves its historical source after reprocessing and never substitutes a live row', async () => {
  const client = { request: async (_method, path, { query }) => path.endsWith('processing-runs') ? [
    { id: 'old', case_id: 'c', evidence_id: 'e', status: 'completed' },
  ] : { items: [observation(query.processing_run_id === 'old' ? 1 : 2, query.processing_run_id ?? 'run1')], total: 1, limit: 100, offset: 0 } };
  const result = await resolveSourceObservations(client, 'c', 'e', signal(), undefined, { observation_id: 'o1', source_locator: 'row 1' });
  assert.equal(result[0].processing_run_id, 'old');
  await assert.rejects(resolveSourceObservations(client, 'c', 'e', signal(), 'run1', { observation_id: 'o1', source_locator: 'row 1' }), /unavailable/);
  const cancelled = new AbortController(); cancelled.abort();
  await assert.rejects(resolveSourceObservations(client, 'c', 'e', cancelled.signal), /Cancelled/);
});

test('KPI totals use all snapshot pages, source unions, live overrides and non-rejected conflicts', async () => {
  const findings = [{ id: 'f1', kind: 'conflict' }, { id: 'f2', kind: 'conflict' }, { id: 'f3', kind: 'gap' }].map(f => ({ ...f, case_id: 'c', analysis_run_id: 'a' }));
  const triage = Array.from({ length: 101 }, (_, i) => ({ evidence_id: `e${i}`, effective_priority: i === 100 ? 'P1' : 'P2', latest_result: { priority: 'P1' } }));
  const client = { request: async (_method, path, options) => {
    if (path.endsWith('/evidence')) return { total: 104, items: [{ case_id: 'c' }] };
    if (path.endsWith('/entities')) return { total: 250, items: [{ case_id: 'c' }] };
    if (path.endsWith('/graph')) return { case_id: 'c', analysis_run_id: 'a', nodes: [{ id: 'n1', case_id: 'c', evidence_ids: ['e1'] }, { id: 'n2', case_id: 'c', evidence_ids: ['e2'] }],
      edges: [{ case_id: 'c', from_id: 'n1', to_id: 'n2', evidence_ids: ['e1'] }, { case_id: 'c', from_id: 'n1', to_id: 'n1', evidence_ids: ['e1'] }] };
    if (path.endsWith('/reviews')) return [{ id: 'r1', case_id: 'c', finding_id: options.path.findingId, created_at: '2026-01-01', decision: options.path.findingId === 'f1' ? 'rejected' : 'accepted' }];
    const items = path.endsWith('/findings') ? findings : triage, { offset, limit } = options.query;
    assert.equal(options.query.analysis_run_id, 'a');
    return { analysis_run_id: 'a', total: items.length, offset, limit, items: items.slice(offset, offset + limit) };
  } };
  assert.deepEqual(await loadCaseMetrics(client, 'c', 'a', signal()), { evidence: 104, entities: 250, links: 1, conflicts: 1, priority: 1 });
  assert.deepEqual(await loadCaseMetrics(client, 'c', null, signal()), { evidence: 104, entities: 250, links: null, conflicts: null, priority: null });
});

test('markdown formats claims and citation references while escaping untrusted content', () => {
  const html = renderToStaticMarkup(createElement(AnswerMarkdown, { text: '# Findings\n**Vehicle** seen [1]\n- `plate`\n- *candidate*\n> uncertain\n<script>alert(1)</script>\n[bad](javascript:alert(1))', citationIds: ['source1'] }));
  assert.match(html, /<h4>Findings/); assert.match(html, /<strong>Vehicle/); assert.match(html, /href="#source1"/);
  assert.match(html, /<ul>/); assert.match(html, /<code>plate/); assert.match(html, /<em>candidate/);
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script|href="javascript:/);
});

test('forensic graph palette honors entity_type and media aliases', () => {
  for (const [type, color] of Object.entries({ person: '#f59e0b', vehicle: '#06b6d4', device: '#3b82f6', ip: '#6366f1', location: '#10b981', account: '#8b5cf6', video: '#f43f5e', camera: '#f43f5e', document: '#94a3b8' })) {
    assert.equal(graphAppearance('entity', type).color, color); assert.ok(graphAppearance(type).path);
  }
});

function elements(node) {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!node || typeof node !== 'object') return [];
  return [node, ...elements(node.props?.children)];
}
test('quick prompts populate the composer and citation actions retain frame locators', () => {
  let question, selected;
  const answer = { case_id: 'c', question: 'Where?', answer: '**Here** [1]', supported: true, citations: [{ evidence_id: 'e', observation_id: 'o', source_locator: 'frame=30; time_offset=1s', claim: 'Seen here' }], retrieval_version: 'v1' };
  const tree = QuestionAnswerPanel({ state: { question: '', status: 'ready', answer }, setQuestion: v => { question = v; }, submit: async () => {}, inspectEvidence: (...args) => { selected = args; } });
  const controls = elements(tree);
  controls.find(e => e.type === 'button' && e.props.children?.[0] === 'Trace financial transactions').props.onClick();
  assert.equal(question, 'Trace financial transactions');
  controls.find(e => e.type === 'button' && e.props['aria-label'] === 'Inspect source evidence e').props.onClick();
  assert.deepEqual(selected, ['e', { observation_id: 'o', source_locator: 'frame=30; time_offset=1s' }]);
});

test('chat history persists separate answers and clears on session change', async () => {
  const id = '00000000-0000-4000-8000-000000000001';
  const client = createApiClient({ baseUrl: 'https://phase2.invalid', fetch: async (_url, options) => Response.json({
    case_id: id, question: JSON.parse(options.body).question, answer: 'Insufficient evidence.', supported: false, citations: [], retrieval_version: 'v1',
  }) });
  client.setToken('test-session'); const controller = createQuestionController(client, id); controller.start();
  controller.setQuestion('First'); await controller.submit(); controller.setQuestion('Second'); await controller.submit();
  assert.deepEqual(controller.getSnapshot().history.map(a => a.question), ['First', 'Second']);
  client.clearToken(); assert.deepEqual(controller.getSnapshot().history, []); controller.dispose();
});


test('citation navigation opens the matching page and retry never substitutes an uncited output', async () => {
  const all = Array.from({ length: 45 }, (_, i) => ({ ...observation(i), kind: 'image.detection', normalized_value: 'person:face' }));
  const client = { getSessionVersion: () => 1, hasToken: () => true, subscribeSession: () => () => {},
    request: async (_method, path, { query }) => path.endsWith('/processing-runs') ? [] :
      { items: all.slice(query.offset, query.offset + query.limit), limit: query.limit, offset: query.offset, total: all.length } };
  const controller = createObservationController(client, 'c', 'e', undefined, { observation_id: 'o42', source_locator: all[42].source_locator });
  controller.start(); await controller.load();
  assert.equal(controller.getSnapshot().page.offset, 40);
  assert.ok(controller.getSnapshot().page.items.some(item => item.id === 'o42'));
  controller.dispose();
  const missing = createObservationController(client, 'c', 'e', undefined, { observation_id: 'missing', source_locator: 'row 1' });
  missing.start(); await missing.load();
  assert.equal(missing.getSnapshot().status, 'error');
  await missing.load();
  assert.equal(missing.getSnapshot().page, null);
  assert.match(missing.getSnapshot().message, /cited source observation is unavailable/);
  missing.dispose();
});
