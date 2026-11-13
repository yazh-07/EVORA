import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import { createTranscriptController, TranscriptPanel, EvidenceProcessingInspection } from '../.test-build/src/cases/CaseWorkspace.mjs';

// Fetch doubles exercise the generated client, controller and actual JSX event handlers.
// Static markup checks do not claim browser mounting or media decoding coverage.
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1), evidenceId = id(2), runId = id(3), root = id(4);
const segment = (extra = {}) => ({ id: root, case_id: caseId, evidence_id: evidenceId, processing_run_id: runId,
  kind: 'transcript.segment', source_locator: 'media:start_ms=1250;end_ms=4125', raw_value: 'Machine heard gate.',
  normalized_value: 'Meet at the gate.', extraction_confidence: 0.82, ...extra });
const revision = (extra = {}) => ({ id: id(10), case_id: caseId, evidence_id: evidenceId, source_observation_id: root,
  processing_run_id: runId, base_processing_run_id: runId, previous_revision_id: null,
  corrected_text: 'Meet at the east gate.', reason: 'Checked against the recording.', actor_id: 'JebasJ',
  created_at: '2026-11-04T12:00:00.000001Z', derived_processing_run_id: id(11), derived_observation_id: id(12), ...extra });
const page = (items = [], total = items.length, offset = 0, limit = 100) => ({ items, total, limit, offset });
const sourceBytes = new TextEncoder().encode('synthetic audio source');
const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', sourceBytes)), n => n.toString(16).padStart(2, '0')).join('');
const evidence = (extra = {}) => ({ id: evidenceId, case_id: caseId, kind: 'audio', filename: 'interview.wav',
  source_label: 'Interview', media_type: 'audio/wav', size_bytes: sourceBytes.length, sha256,
  created_at: '2026-11-04T10:00:00Z', ...extra });
function setup(t, transport, options = {}, item = evidence()) {
  const calls = [];
  const client = createApiClient({ baseUrl: 'https://transcripts.invalid', fetch: async (url, init) => {
    calls.push({ url, init });
    if (transport) return transport(url, init);
    if (init.method === 'POST') return Response.json(revision(), { status: 201 });
    if (url.pathname.endsWith('/transcript-revisions')) return Response.json(page());
    return Response.json(page([segment()]));
  } });
  client.setToken('synthetic-u14');
  const c = createTranscriptController(client, item, options);
  t.after(() => c.dispose()); c.start();
  return { c, client, calls };
}
const props = c => ({ ...c, state: c.getSnapshot(), mediaKind: 'audio', filename: 'interview.wav' });
const render = c => renderToStaticMarkup(createElement(TranscriptPanel, props(c)));
function elements(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => elements(child, predicate));
  return [...(predicate(tree) ? [tree] : []), ...elements(tree.props?.children, predicate)];
}
function find(c, predicate) {
  const result = elements(TranscriptPanel(props(c)), predicate)[0];
  assert.ok(result, 'Expected transcript control'); return result;
}
const button = (c, label) => find(c, element => element.type === 'button' && element.props.children === label).props.onClick();
const change = (c, field, value) => find(c, e => field === 'correctedText' ? e.type === 'textarea' : e.type === 'input' && e.props.type === 'text')
  .props.onChange({ currentTarget: { value } });
const search = (c, value) => find(c, e => e.type === 'input' && e.props.type === 'search').props.onChange({ currentTarget: { value } });
async function ready(c) {
  for (let i = 0; i < 100; i++) {
    const state = c.getSnapshot();
    if (state.status !== 'loading' && !Object.values(state.histories).some(h => h.status === 'loading' || h.submission === 'submitting')) return;
    await setImmediate();
  }
  assert.fail('Transcript request did not settle');
}
async function open(c) {
  find(c, e => e.type === 'details').props.onToggle({ currentTarget: { open: true } }); await ready(c);
}
function submitForm(c) {
  let prevented = false;
  find(c, e => e.type === 'form').props.onSubmit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
}

test('renders selected transcript segments with original timeline offsets, effective text and confidence', async t => {
  const later = segment({ id: id(5), source_locator: 'media:start_ms=3661000;end_ms=3662250', normalized_value: 'Later segment.', extraction_confidence: 0 });
  const { c, calls } = setup(t, () => Response.json(page([later, segment(), segment({ id: id(6), kind: 'entity.candidate', normalized_value: 'Excluded entity' })])));
  assert.match(render(c), /Loading transcript/); await ready(c);
  assert.equal(calls.length, 1);
  const { url, init } = calls[0];
  assert.equal(url.pathname, `/api/v1/cases/${caseId}/observations`);
  assert.deepEqual(Object.fromEntries(url.searchParams), { evidence_id: evidenceId, limit: '100', offset: '0' });
  assert.equal(init.method, 'GET'); assert.equal(init.body, undefined);
  const html = render(c);
  for (const value of ['00:00:01.250', '00:00:04.125', '01:01:01.000', '1250', '4125', 'Meet at the gate.', '0.82', 'Extraction confidence: 0', '2 of 2 transcript segments', 'not source reliability']) assert.ok(html.includes(value), value);
  assert.ok(html.indexOf('Meet at the gate.') < html.indexOf('Later segment.'));
  assert.doesNotMatch(html, /Excluded entity|Machine heard gate|JebasJ/);
});

test('search handlers filter and highlight literal case-insensitive matches locally in real time', async t => {
  const { c, calls } = setup(t, () => Response.json(page([segment(), segment({ id: id(5), normalized_value: 'Gate gate [unclear].' })])));
  await ready(c); search(c, ' GATE ');
  assert.match(render(c), /<mark>gate<\/mark>/); assert.match(render(c), /<mark>Gate<\/mark> <mark>gate<\/mark>/);
  search(c, '[unclear]'); assert.match(render(c), /1 of 2 transcript segments/); assert.match(render(c), /<mark>\[unclear\]<\/mark>/);
  assert.doesNotMatch(render(c), /Meet at the/);
  search(c, 'missing'); assert.match(render(c), /No transcript segments match your search/);
  search(c, ''); assert.match(render(c), /2 of 2 transcript segments/);
  assert.equal(calls.length, 1, 'Search makes no API requests');
});

test('loads all observation pages and pins subsequent pages to the first selected output', async t => {
  const { c, calls } = setup(t, url => {
    const offset = Number(url.searchParams.get('offset'));
    if (!offset) return Response.json(page([segment({ kind: 'transcript.status', normalized_value: 'silence' })], 2, 0, 1));
    assert.equal(url.searchParams.get('processing_run_id'), runId);
    return Response.json(page([segment({ id: id(5), normalized_value: 'Found on the second page.' })], 2, 1, 1));
  });
  await ready(c); assert.equal(calls.length, 2); assert.match(render(c), /Found on the second page/);
});

test('opens revision history lazily, reads all pages in server order and caches closed disclosures', async t => {
  const first = revision(), second = revision({ id: id(20), previous_revision_id: first.id, base_processing_run_id: id(11),
    derived_processing_run_id: id(21), derived_observation_id: id(22), corrected_text: 'Second correction.', created_at: '2026-11-04T12:00:00.000002Z', actor_id: 'reviewer-two' });
  const { c, calls } = setup(t, url => {
    if (!url.pathname.endsWith('/transcript-revisions')) return Response.json(page([segment()]));
    assert.equal(url.pathname, `/api/v1/cases/${caseId}/observations/${root}/transcript-revisions`);
    return Response.json(url.searchParams.get('offset') === '0' ? page([first], 2, 0, 1) : page([second], 2, 1, 1));
  });
  await ready(c); assert.equal(calls.length, 1);
  find(c, e => e.type === 'details').props.onToggle({ currentTarget: { open: true } });
  assert.match(render(c), /Loading revision history/); await ready(c);
  const html = render(c);
  for (const value of ['oldest first', 'JebasJ', 'reviewer-two', first.created_at, second.created_at, first.corrected_text, second.corrected_text, first.reason, 'Machine heard gate.']) assert.ok(html.includes(value), value);
  assert.ok(html.indexOf(first.corrected_text) < html.indexOf(second.corrected_text));
  c.toggleHistory(root, false); await open(c); assert.equal(calls.length, 3);
});

test('actual correction form sends UUID idempotency key and both run preconditions; publishes a new output', async t => {
  let finish, posted;
  const notified = [];
  const { c, calls } = setup(t, (url, init) => {
    if (init.method === 'POST') { posted = { url, init }; return new Promise(resolve => { finish = resolve; }); }
    return Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()]));
  }, { onDerivedRun: run => notified.push(run) });
  await ready(c); await open(c);
  assert.match(render(c), /No corrections recorded/);
  change(c, 'correctedText', revision().corrected_text); change(c, 'reason', revision().reason);
  submitForm(c); submitForm(c);
  assert.match(render(c), /Saving correction/); assert.equal(find(c, e => e.type === 'fieldset').props.disabled, true);
  assert.equal(calls.filter(call => call.init.method === 'POST').length, 1);
  assert.equal(posted.url.pathname, `/api/v1/cases/${caseId}/observations/${root}/transcript-revisions`);
  assert.equal(posted.url.search, ''); assert.equal(posted.init.headers.get('Authorization'), 'Bearer synthetic-u14');
  assert.match(posted.init.headers.get('Idempotency-Key'), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  assert.deepEqual(JSON.parse(posted.init.body), { processing_run_id: runId, base_processing_run_id: runId,
    expected_latest_revision_id: null, corrected_text: revision().corrected_text, reason: revision().reason });
  c.setDraft(root, 'correctedText', 'blocked while saving');
  finish(Response.json(revision(), { status: 201 })); await ready(c);
  assert.equal(c.getSnapshot().segments[0].normalized_value, revision().corrected_text);
  assert.equal(c.getSnapshot().segments[0].raw_value, segment().raw_value);
  assert.equal(c.getSnapshot().segments[0].extraction_confidence, 0.82);
  assert.deepEqual(c.getSnapshot().histories[root].revisions, [revision()]);
  assert.deepEqual(notified, [id(11)]); assert.equal(c.getSnapshot().baseRunId, id(11));
  assert.match(render(c), /Correction saved in a new processing output/);
});

test('second correction uses root observation and original machine run with the new derived base', async t => {
  let posts = 0;
  const { c, calls } = setup(t, (url, init) => {
    if (init.method === 'POST') {
      posts++;
      const body = JSON.parse(init.body);
      return Response.json(revision({ id: id(posts * 10), ...body, previous_revision_id: body.expected_latest_revision_id,
        derived_processing_run_id: id(posts * 10 + 1), derived_observation_id: id(posts * 10 + 2) }), { status: 201 });
    }
    return Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()]));
  });
  await ready(c); await open(c);
  change(c, 'correctedText', 'First corrected text'); change(c, 'reason', 'First reason'); await c.submit(root);
  change(c, 'correctedText', 'Second corrected text'); change(c, 'reason', 'Second reason'); await c.submit(root);
  const writes = calls.filter(call => call.init.method === 'POST');
  assert.deepEqual(JSON.parse(writes[1].init.body), { processing_run_id: runId, base_processing_run_id: id(11),
    expected_latest_revision_id: id(10), corrected_text: 'Second corrected text', reason: 'Second reason' });
  assert.equal(writes[1].url.pathname, writes[0].url.pathname);
  assert.notEqual(writes[1].init.headers.get('Idempotency-Key'), writes[0].init.headers.get('Idempotency-Key'));
  assert.equal(c.getSnapshot().histories[root].revisions.length, 2); assert.equal(c.getSnapshot().baseRunId, id(21));
});

test('uncorrected segment copied into a derived output resolves its original run lazily', async t => {
  const derived = id(30);
  const { c, calls } = setup(t, (url, init) => {
    if (init.method === 'POST') return Response.json(revision({ base_processing_run_id: derived }), { status: 201 });
    if (url.pathname.endsWith('/processing-runs')) return Response.json([{ id: derived, case_id: caseId, evidence_id: evidenceId, status: 'completed' },
      { id: runId, case_id: caseId, evidence_id: evidenceId, status: 'completed' }]);
    if (url.pathname.endsWith('/transcript-revisions')) return Response.json(page());
    return Response.json(page([url.searchParams.get('processing_run_id') === runId ? segment()
      : segment({ id: id(31), source_observation_id: root, processing_run_id: derived })]));
  });
  await ready(c); assert.equal(calls.length, 1); await open(c);
  assert.equal(c.getSnapshot().histories[root].originalRunId, runId);
  change(c, 'correctedText', revision().corrected_text); change(c, 'reason', revision().reason); await c.submit(root);
  const body = JSON.parse(calls.find(call => call.init.method === 'POST').init.body);
  assert.equal(body.processing_run_id, runId); assert.equal(body.base_processing_run_id, derived);
  assert.match(calls.find(call => call.init.method === 'POST').url.pathname, new RegExp(`/${root}/transcript-revisions$`));
});

test('409 shows stale preconditions, blocks resubmission and reloads latest transcript/history while retaining draft', async t => {
  let writes = 0, refreshed = false;
  const external = revision();
  const { c, calls } = setup(t, (url, init) => {
    if (init.method === 'POST') {
      if (++writes === 1) return Response.json({ code: 'CONFLICT', message: 'PRIVATE server detail' }, { status: 409 });
      return Response.json(revision({ id: id(20), base_processing_run_id: id(11), previous_revision_id: external.id,
        corrected_text: 'My retained correction', reason: 'My retained reason', derived_processing_run_id: id(21) }), { status: 201 });
    }
    if (url.pathname.endsWith('/transcript-revisions')) return Response.json(page(refreshed ? [external] : []));
    return Response.json(page([refreshed ? segment({ id: id(12), processing_run_id: id(11), source_observation_id: root,
      transcript_revision_id: external.id, normalized_value: external.corrected_text }) : segment()]));
  });
  await ready(c); await open(c);
  change(c, 'correctedText', 'My retained correction'); change(c, 'reason', 'My retained reason'); await c.submit(root);
  assert.match(render(c), /role="alert">Stale correction precondition/); assert.match(render(c), /Reload transcript and history/);
  assert.doesNotMatch(render(c), /PRIVATE/); assert.equal(find(c, e => e.type === 'fieldset').props.disabled, true);
  await c.submit(root); assert.equal(writes, 1);
  refreshed = true; button(c, 'Reload transcript and history'); await ready(c);
  assert.equal(c.getSnapshot().baseRunId, id(11)); assert.equal(c.getSnapshot().histories[root].correctedText, 'My retained correction');
  assert.equal(c.getSnapshot().histories[root].reason, 'My retained reason');
  assert.deepEqual(c.getSnapshot().histories[root].revisions, [external]);
  await c.submit(root);
  const posts = calls.filter(call => call.init.method === 'POST');
  assert.equal(JSON.parse(posts[1].init.body).expected_latest_revision_id, external.id);
  assert.equal(JSON.parse(posts[1].init.body).base_processing_run_id, id(11));
  assert.equal(c.getSnapshot().histories[root].submission, 'success');
});

test('blank and oversized fields validate locally; maximum lengths are accepted', async t => {
  const { c, calls } = setup(t, (url, init) => init.method === 'POST'
    ? Response.json(revision({ ...JSON.parse(init.body) }), { status: 201 })
    : Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()])));
  await ready(c); await open(c);
  for (const [text, reason] of [['', 'Reason'], [' \n\t', 'Reason'], ['Text', ''], ['Text', ' \n\t'], ['x'.repeat(20001), 'Reason'], ['Text', 'x'.repeat(2001)]]) {
    change(c, 'correctedText', text); change(c, 'reason', reason); submitForm(c); await ready(c);
    assert.match(render(c), /role="alert">Enter non-empty corrected text/);
    assert.equal(calls.filter(call => call.init.method === 'POST').length, 0);
  }
  assert.equal(find(c, e => e.type === 'textarea').props.maxLength, 20000);
  assert.equal(find(c, e => e.type === 'input' && e.props.type === 'text').props.maxLength, 2000);
  change(c, 'correctedText', 'x'.repeat(20000)); change(c, 'reason', 'y'.repeat(2000)); await c.submit(root);
  assert.equal(c.getSnapshot().histories[root].submission, 'success');
});

test('network retry for identical correction reuses its key; edited correction receives a new key', async t => {
  const { c, calls } = setup(t, (url, init) => {
    if (init.method === 'POST') throw Error('PRIVATE transport failure');
    return Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()]));
  });
  await ready(c); await open(c); change(c, 'reason', 'Verified'); await c.submit(root); await c.submit(root);
  change(c, 'reason', 'Verified again'); await c.submit(root);
  const keys = calls.filter(call => call.init.method === 'POST').map(call => call.init.headers.get('Idempotency-Key'));
  assert.equal(keys[0], keys[1]); assert.notEqual(keys[1], keys[2]); assert.doesNotMatch(render(c), /PRIVATE/);
});

test('transcript, original text, drafts, revision text/reason and actor escape XSS; highlighting remains text', async t => {
  const unsafe = '<img src=x onerror="alert(1)"><script>PAYLOAD</script> & text';
  const { c } = setup(t, url => url.pathname.endsWith('/transcript-revisions')
    ? Response.json(page([revision({ corrected_text: unsafe, reason: unsafe, actor_id: unsafe })]))
    : Response.json(page([segment({ raw_value: unsafe, normalized_value: unsafe })])));
  await ready(c); await open(c); change(c, 'reason', unsafe);
  assert.doesNotMatch(render(c), /<img|<script|<\/textarea><img/);
  assert.ok((render(c).match(/&lt;script&gt;PAYLOAD&lt;\/script&gt;/g) ?? []).length >= 6);
  search(c, '<script>'); assert.match(render(c), /<mark>&lt;script&gt;<\/mark>/);
  assert.doesNotMatch(render(c), /<script|<img/);
});

test('empty transcript gives an honest empty state and preserves source access', async t => {
  const { c } = setup(t, () => Response.json(page())); await ready(c);
  assert.match(render(c), /No transcript segments are available/); assert.match(render(c), /Listen \/ Download audio/);
  assert.doesNotMatch(render(c), /Submit correction/);
});

for (const stage of ['observations', 'history', 'correction']) {
  for (const failure of [400, 401, 404, 500, 'network']) {
    test(`${stage}: ${failure} produces a safe error and clears private state on authentication failure`, async t => {
      const { c, client } = setup(t, (url, init) => {
        const failing = stage === 'observations' || (stage === 'history' && url.pathname.endsWith('/transcript-revisions')) ||
          (stage === 'correction' && init.method === 'POST');
        if (failing) {
          if (failure === 'network') throw Error('PRIVATE TOKEN <script>');
          return Response.json({ code: 'FAILURE', message: 'PRIVATE TOKEN <script>' }, { status: failure });
        }
        return Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()]));
      });
      await ready(c);
      if (stage !== 'observations') await open(c);
      if (stage === 'correction') { change(c, 'reason', 'Verified'); await c.submit(root); }
      assert.match(render(c), /role="alert"/); assert.doesNotMatch(render(c), /PRIVATE|TOKEN|<script/);
      if (failure === 401) {
        assert.equal(client.hasToken(), false); assert.match(render(c), /Authentication required/);
        assert.deepEqual(c.getSnapshot().segments, []); assert.deepEqual(c.getSnapshot().histories, {});
      }
    });
  }
}

test('foreign resources, invalid timelines, mixed runs and malformed observation pages fail safely', async t => {
  for (const invalid of [null, {}, page([segment({ case_id: id(90) })]), page([segment({ evidence_id: id(90) })]),
    page([segment({ source_locator: 'media:start_ms=4000;end_ms=1000' })]), page([segment({ extraction_confidence: 2 })]),
    page([segment(), segment({ id: id(5), processing_run_id: id(90) })]), page([], 10), page([segment()], 1, 1), page([segment(), segment()])]) {
    const { c } = setup(t, () => Response.json(invalid)); await ready(c);
    assert.equal(c.getSnapshot().status, 'error'); assert.deepEqual(c.getSnapshot().segments, []);
  }
});

test('foreign history and inconsistent correction responses cannot update transcript or notify workspace', async t => {
  for (const stage of ['history', 'correction']) {
    const notified = [];
    const { c } = setup(t, (url, init) => {
      if (init.method === 'POST') return Response.json(revision({ base_processing_run_id: id(90) }), { status: 201 });
      if (url.pathname.endsWith('/transcript-revisions')) return Response.json(page(stage === 'history' ? [revision({ source_observation_id: id(90) })] : []));
      return Response.json(page([segment()]));
    }, { onDerivedRun: run => notified.push(run) });
    await ready(c); await open(c);
    if (stage === 'correction') { change(c, 'reason', revision().reason); change(c, 'correctedText', revision().corrected_text); await c.submit(root); }
    assert.match(render(c), /role="alert"/); assert.deepEqual(notified, []);
    assert.equal(c.getSnapshot().segments[0].normalized_value, segment().normalized_value);
  }
});

for (const stage of ['observations', 'history', 'correction']) {
  for (const action of ['dispose', 'sign out', 'token replacement']) {
    test(`${action} aborts pending ${stage} and discards late delivery`, async t => {
      let finish, signal;
      const notified = [];
      const { c, client } = setup(t, (url, init) => {
        const pending = stage === 'observations' || (stage === 'history' && url.pathname.endsWith('/transcript-revisions')) ||
          (stage === 'correction' && init.method === 'POST');
        if (pending) { signal = init.signal; return new Promise(resolve => { finish = resolve; }); }
        return Response.json(page(url.pathname.endsWith('/transcript-revisions') ? [] : [segment()]));
      }, { onDerivedRun: run => notified.push(run) });
      if (stage !== 'observations') {
        await ready(c);
        if (stage === 'history') c.toggleHistory(root, true);
        else { await open(c); change(c, 'reason', 'Checked'); void c.submit(root); }
      }
      assert.ok(signal);
      if (action === 'dispose') c.dispose(); else if (action === 'sign out') client.clearToken(); else client.setToken('replacement');
      assert.equal(signal.aborted, true);
      const previous = c.getSnapshot();
      finish(Response.json(stage === 'correction' ? revision() : page(stage === 'history' ? [revision()] : [segment()]), { status: stage === 'correction' ? 201 : 200 }));
      await setImmediate(); assert.equal(c.getSnapshot(), previous); assert.deepEqual(notified, []);
      assert.deepEqual(c.getSnapshot().segments, []); assert.deepEqual(c.getSnapshot().histories, {});
    });
  }
}

test('refresh supersedes pending reads; late results cannot replace the newer transcript', async t => {
  let finish, signal, count = 0;
  const { c } = setup(t, (_url, init) => {
    if (++count === 1) { signal = init.signal; return new Promise(resolve => { finish = resolve; }); }
    return Response.json(page([segment({ normalized_value: 'Fresh transcript' })]));
  });
  await c.load(); assert.equal(signal.aborted, true); const previous = c.getSnapshot();
  finish(Response.json(page([segment()]))); await setImmediate(); assert.equal(c.getSnapshot(), previous);
  assert.match(render(c), /Fresh transcript/);
});

test('source playback downloads authorized bytes, verifies integrity and revokes media URLs on disposal', {timeout:5000}, async t => {
  const revoked = [], revoke = URL.revokeObjectURL;
  t.mock.method(URL, 'revokeObjectURL', url => { revoked.push(url); revoke(url); });
  const { c, calls } = setup(t, url => url.pathname.endsWith('/content')
    ? new Response(sourceBytes, { headers: { 'Content-Type': 'application/octet-stream' } }) : Response.json(page([segment()])));
  await ready(c);
  let unsubscribe;
  const completed=new Promise(resolve=>{
    unsubscribe=c.subscribe(()=>{
      if(['ready','error'].includes(c.getSnapshot().media.status))resolve();
    });
  });
  t.after(()=>unsubscribe());
  button(c, 'Listen / Download audio');
  assert.match(render(c), /Loading source media/);
  await completed;
  const sourceUrl = c.getSnapshot().sourceUrl;
  assert.match(sourceUrl, /^blob:/); assert.match(render(c), /<audio controls="" preload="metadata"/);
  assert.match(render(c), /download="interview.wav"/); assert.match(render(c), /verified against recorded size and SHA-256/);
  const call = calls.find(call => call.url.pathname.endsWith('/content'));
  assert.equal(call.url.pathname, `/api/v1/cases/${caseId}/evidence/${evidenceId}/content`);
  assert.equal(call.init.headers.get('Authorization'), 'Bearer synthetic-u14'); assert.equal(call.init.method, 'GET');
  c.dispose(); assert.ok(revoked.includes(sourceUrl)); assert.equal(c.getSnapshot().sourceUrl, '');
});

test('mismatched source bytes are never exposed for playback or download', async t => {
  const { c } = setup(t, url => url.pathname.endsWith('/content')
    ? new Response('tampered', { headers: { 'Content-Type': 'application/octet-stream' } }) : Response.json(page()));
  await ready(c); await c.download();
  assert.equal(c.getSnapshot().sourceUrl, ''); assert.match(render(c), /role="alert">Original bytes do not match/);
  assert.doesNotMatch(render(c), /<audio|download="/);
});

test('evidence inspection exposes transcript only for audio/video, with appropriate source controls', t => {
  const { client } = setup(t);
  for (const kind of ['audio', 'video', 'document']) {
    const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(EvidenceProcessingInspection, { item: evidence({ kind }) })));
    assert.match(html, /Source views/); assert.match(html, />Results<\/button>/); assert.match(html, />Info<\/button>/); assert.doesNotMatch(html, /aria-label="Source transcript"/);
  }
});
