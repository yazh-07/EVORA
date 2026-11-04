import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  ConflictPanel, GapPanel, ClusterPanel, AnomalyPanel, HypothesisPanel, ReliabilityInspector,
  FindingPanel, FindingKindFilter, ObservationPanel, createFindingController,
} from '../.test-build/src/cases/CaseWorkspace.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), runId = id(2), processingId = id(3), evidenceId = id(10), otherEvidenceId = id(11);
const unsafe = '<script>untrusted</script>';
const finding = (kind, n = 20) => ({
  id: id(n), case_id: caseId, analysis_run_id: runId, kind,
  summary: `${kind}: ${unsafe}; 2026-10-02T10:00:00Z–2026-10-02T12:00:00Z; locations 12,77 and 13,78`,
  rule: `${kind}/v1`, confidence: 0.75, evidence_ids: [evidenceId],
  contradicting_evidence_ids: [otherEvidenceId], observation_ids: [id(30)], entity_ids: [id(40)],
  missing_information: [`Clock offset unknown ${unsafe}`],
});
const observation = (extra = {}) => ({
  id: id(30), case_id: caseId, evidence_id: evidenceId, processing_run_id: processingId,
  kind: 'gps.location', source_locator: `row 2 ${unsafe}`, raw_value: '12.000,77.000', normalized_value: '12,77',
  observed_at_raw: '2026-10-02 10:00', observed_at_utc: '2026-10-02T10:00:00Z', extraction_confidence: 0,
  ...extra,
});
const render = (Component, props = {}) => renderToStaticMarkup(createElement(Component, props));
// Resolve the pure view components to invoke the same handlers used by the rendered buttons/selects.
function elements(node) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap(elements);
  if (typeof node.type === 'function') return elements(node.type(node.props));
  return [node, ...elements(node.props?.children)];
}
const panels = [
  ['conflict', ConflictPanel, 'Conflicting evidence, timestamps or locations'],
  ['gap', GapPanel, 'Missing intervals and data gaps'],
  ['cluster', ClusterPanel, 'Connected evidence and candidate entities'],
  ['anomaly', AnomalyPanel, 'Abnormal data points'],
  ['hypothesis', HypothesisPanel, 'Alternative hypothesis'],
];
const disclaimer = {
  gap: 'Missing evidence is not proof of non-occurrence.',
  anomaly: 'Investigative attention only; abnormal is not proof of guilt.',
};

for (const [kind, Component, title] of panels) {
  test(`${kind}: renders reported data and frozen locators with safe text`, () => {
    const html = render(Component, { finding: finding(kind), citations: [observation()] });
    for (const text of [title, evidenceId, id(30), 'row 2', '12,77', '2026-10-02T10:00:00Z', '&lt;script&gt;untrusted&lt;/script&gt;']) {
      assert.ok(html.includes(text), text);
    }
    assert.doesNotMatch(html, /<script>/);
    if (disclaimer[kind]) assert.ok(html.includes(disclaimer[kind]));
    if (kind === 'cluster') assert.ok(html.includes(id(40)));
    if (kind === 'conflict' || kind === 'hypothesis') {
      assert.ok(html.includes(otherEvidenceId)); assert.match(html, /detector-comparison/);
      assert.match(html, /Contradicting evidence/);
    }
    if (kind === 'gap') assert.match(html, /Clock offset unknown/);
  });

  test(`${kind}: explicit empty and wrong-kind states preserve disclaimers`, () => {
    for (const props of [{}, { finding: null }, { finding: finding('relationship') }]) {
      const html = render(Component, props);
      assert.match(html, new RegExp(`No ${kind} finding selected`));
      assert.doesNotMatch(html, /untrusted|row 2/);
      if (disclaimer[kind]) assert.ok(html.includes(disclaimer[kind]));
    }
  });

  test(`${kind}: unresolved values and missing optional data stay explicit`, () => {
    const html = render(Component, { finding: { ...finding(kind), evidence_ids: [], observation_ids: [],
      contradicting_evidence_ids: undefined, entity_ids: undefined, missing_information: undefined } });
    assert.match(html, /No evidence IDs provided/);
    assert.match(html, /No source observation IDs provided/);
    assert.doesNotMatch(html, /<table>|undefined|NaN/);
    if (kind === 'cluster') assert.match(html, /No entity IDs provided/);
    if (kind === 'hypothesis' || kind === 'conflict') assert.match(html, /Uncertainty remains unassessed/);
  });

  test(`${kind}: evidence navigation passes the exact evidence ID`, () => {
    const inspected = [];
    const tree = elements(createElement(Component, { finding: finding(kind), citations: [observation()], inspectEvidence: value => inspected.push(value) }));
    const buttons = tree.filter(node => node.type === 'button');
    const source = buttons.find(node => node.props['aria-label'] === `Inspect source evidence ${evidenceId}`);
    assert.ok(source); source.props.onClick();
    assert.deepEqual(inspected, [evidenceId]);
    if (kind === 'hypothesis' || kind === 'conflict') {
      const contradicting = buttons.find(node => node.props['aria-label'] === `Inspect source evidence ${otherEvidenceId}`);
      assert.ok(contradicting); contradicting.props.onClick();
      assert.deepEqual(inspected, [evidenceId, otherEvidenceId]);
    }
    assert.doesNotMatch(render(Component, { finding: finding(kind) }), /<button/);
  });
}

test('conflict compares both cited timestamps and locations without unrelated observations', () => {
  const f = { ...finding('conflict'), evidence_ids: [evidenceId, otherEvidenceId], observation_ids: [id(30), id(31)] };
  const html = render(ConflictPanel, { finding: f, citations: [observation(), observation({ id: id(31), evidence_id: otherEvidenceId,
    normalized_value: '13,78', observed_at_utc: '2026-10-02T10:01:00Z', source_locator: 'row 9' }),
  observation({ id: id(99), raw_value: 'UNRELATED' }), observation({ case_id: id(99), raw_value: 'FOREIGN' })] });
  for (const text of ['12,77', '13,78', '2026-10-02T10:01:00Z', 'row 9']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /UNRELATED|FOREIGN/);
});

test('reliability renders extraction, corroboration, conflicts and missing information for selected evidence', () => {
  const findings = [finding('corroboration'), finding('conflict', 21), { ...finding('corroboration', 22), evidence_ids: [id(99)], contradicting_evidence_ids: [] }];
  const html = render(ReliabilityInspector, { evidenceId, observations: [observation(), observation({ id: id(99), evidence_id: id(99), extraction_confidence: 0.99 })], findings });
  for (const text of ['Source reliability', 'Unknown', '0.00', 'Corroboration findings', 'Conflict findings', '1 on the current findings page.',
    'Clock offset unknown', 'not source reliability', 'does not establish independent sources', 'frozen citations']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /0\.99|<script>/);
  const inspected = [];
  const button = elements(createElement(ReliabilityInspector, { evidenceId, inspectEvidence: value => inspected.push(value) })).find(node => node.type === 'button');
  button.props.onClick(); assert.deepEqual(inspected, [evidenceId]);
});

test('reliability distinguishes no selection, unknown findings and a loaded empty page', () => {
  assert.match(render(ReliabilityInspector), /Select evidence to inspect reliability and uncertainty/);
  const unknown = render(ReliabilityInspector, { evidenceId });
  assert.match(unknown, /Not loaded in this view/); assert.doesNotMatch(unknown, /0 on the current/);
  assert.match(unknown, /No resolved observations/); assert.match(unknown, /No additional uncertainty assessment/);
  const empty = render(ReliabilityInspector, { evidenceId, findings: [] });
  assert.match(empty, /0 on the current findings page/); assert.match(empty, /Unknown/);
});

const entries = ['relationship', 'corroboration', ...panels.map(([kind]) => kind)].map((kind, n) => finding(kind, 100 + n));
const stateFor = (items = entries) => ({ status: 'ready', page: { items, total: items.length, limit: 20, offset: 0, analysis_run_id: runId },
  message: '', selectedId: null, citations: [], citationStatus: 'idle', citationMessage: '', reviews: {} });
const actions = { load: async () => {}, select: async () => {} };

test('kind filter switches between every supported kind and all without changing page totals', () => {
  const state = stateFor();
  let kind = 'all';
  const props = () => ({ state, ...actions, findingKind: kind, onKindChange: value => { kind = value; } });
  assert.match(render(FindingPanel, props()), /Filters the current page/);
  for (const next of ['conflict', 'gap', 'cluster', 'anomaly', 'hypothesis', 'relationship', 'all']) {
    const select = elements(createElement(FindingPanel, props())).find(node => node.type === 'select');
    assert.ok(!select.props.disabled); select.props.onChange({ currentTarget: { value: next } });
    assert.equal(kind, next);
    const html = render(FindingPanel, props());
    assert.match(html, /7 findings/);
    for (const entry of entries) {
      assert.equal(html.includes(`Finding ID: ${entry.id}`), next === 'all' || entry.kind === next);
    }
    if (next !== 'all') assert.ok(html.includes(`1 ${next} findings on this page`));
  }
  const filter = render(FindingKindFilter, { value: 'all', onSelect: () => {} });
  assert.equal((filter.match(/<option/g) ?? []).length, 7);
});

test('empty filtered page stays distinct from an empty analysis and preserves pagination/navigation', () => {
  let offset;
  const props = { state: { ...stateFor([finding('relationship')]), page: { ...stateFor([finding('relationship')]).page, total: 21 } },
    findingKind: 'gap', onKindChange: () => {}, select: async () => {}, load: async value => { offset = value; } };
  const html = render(FindingPanel, props);
  assert.match(html, /No findings of this kind on this page/); assert.match(html, /21 findings/);
  assert.doesNotMatch(html, /No findings in this completed analysis/);
  const next = elements(createElement(FindingPanel, props)).find(node => node.type === 'button' && node.props.children === 'Next');
  assert.ok(!next.props.disabled); next.props.onClick(); assert.equal(offset, 20);
  assert.match(render(FindingPanel, { ...props, state: stateFor([]) }), /No findings in this completed analysis/);
});

test('inspector selects specialized views, resolves locators and exposes evidence reliability', () => {
  for (const [kind, , title] of panels) {
    const entry = finding(kind);
    const state = { ...stateFor([entry]), selectedId: entry.id, citations: [observation()], citationStatus: 'ready' };
    const html = render(FindingPanel, { state, ...actions });
    assert.ok(html.includes(title)); assert.match(html, /row 2/); assert.match(html, /Reliability and uncertainty for evidence/);
    if (disclaimer[kind]) assert.ok(html.includes(disclaimer[kind]));
    assert.doesNotMatch(render(FindingPanel, { state, ...actions, findingKind: 'relationship' }), /Finding source details|row 2|Reliability and uncertainty for evidence/);
    const selected = [];
    const button = elements(createElement(FindingPanel, { state, ...actions, select: async value => { selected.push(value); } }))
      .find(node => node.type === 'button' && node.props['aria-pressed'] !== undefined);
    assert.ok(button);
    button.props.onClick(); assert.deepEqual(selected, [entry.id]);
  }
});

test('selected evidence observations expose reliability with honest page scope', () => {
  const html = render(ObservationPanel, { evidenceId, load: async () => {},
    state: { status: 'ready', message: '', page: { items: [observation()], total: 25, limit: 20, offset: 20 } } });
  assert.match(html, /Source reliability and uncertainty/); assert.match(html, /cover 1 of 25 observations/);
  assert.match(html, /Corroboration findings/); assert.match(html, /Not loaded in this view/);
  const stale = render(ObservationPanel, { evidenceId, load: async () => {}, state: { status: 'loading', page: null, message: '' } });
  assert.doesNotMatch(stale, /Source reliability and uncertainty|0\.00/);
});

test('malformed cited values fail safely before specialized rendering', async () => {
  for (const change of [{ raw_value: {} }, { normalized_value: [] }, { observed_at_utc: {} }, { extraction_confidence: 2 }]) {
    const entry = finding('conflict');
    const client = createApiClient({ baseUrl: 'https://detectors.invalid', fetch: async url => Response.json(
      url.pathname.endsWith('/findings') ? stateFor([entry]).page : url.pathname.includes('/analysis-runs/') ?
        { id: runId, case_id: caseId, status: 'completed', input_snapshot: { case_id: caseId,
          evidence_ids: [evidenceId, otherEvidenceId], observation_ids: [id(30)], processing_run_ids: [processingId] } } :
        { items: [observation(change)], total: 1, limit: 100, offset: 0 }) });
    client.setToken('synthetic-detectors');
    const controller = createFindingController(client, caseId, runId);
    try {
      controller.start(); await controller.load(0); assert.equal(controller.getSnapshot().status, 'ready');
      await controller.select(entry.id);
      assert.equal(controller.getSnapshot().citationStatus, 'error'); assert.deepEqual(controller.getSnapshot().citations, []);
      assert.doesNotMatch(render(FindingPanel, { state: controller.getSnapshot(), ...actions }), /<table>/);
    } finally { controller.dispose(); }
  }
});
