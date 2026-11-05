import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import {
  createQuestionController, QuestionAnswerPanel, CaseEvidenceWorkspace, CaseAnalysisWorkspace,
} from '../.test-build/src/cases/CaseWorkspace.mjs';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const caseId = id(1);
const question = 'What network events mention 203.0.113.8?';
const citation = (n = 1, extra = {}) => ({ claim: `Network observation ${n} records a connection.`,
  evidence_id: id(10 + n), observation_id: id(20 + n), source_locator: `row ${n}`, ...extra });
const answer = (extra = {}) => ({ case_id: caseId, question, supported: true,
  answer: 'The network log records two connections.', citations: [citation(1), citation(2)],
  retrieval_version: 'deterministic-grounded-retrieval/1', ...extra });

function setup(t, transport = () => Response.json(answer())) {
  const calls = [];
  const client = createApiClient({ baseUrl: 'https://questions.invalid', fetch: async (url, options) => {
    calls.push({ url, options }); return transport(url, options);
  } });
  client.setToken('synthetic-u11');
  const controller = createQuestionController(client, caseId);
  controller.start();
  t.after(() => controller.dispose());
  return { client, controller, calls };
}
const props = (c, inspectEvidence = () => {}) => ({ state: c.getSnapshot(),
  setQuestion: c.setQuestion, submit: c.submit, inspectEvidence });
const render = c => renderToStaticMarkup(createElement(QuestionAnswerPanel, props(c)));
function elements(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => elements(child, predicate));
  return [...(predicate(tree) ? [tree] : []), ...elements(tree.props?.children, predicate)];
}
function find(c, predicate) {
  const element = elements(QuestionAnswerPanel(props(c)), predicate)[0];
  assert.ok(element, 'Expected question control'); return element;
}
const change = (c, value) => find(c, e => e.type === 'textarea').props.onChange({ currentTarget: { value } });
function submit(c) {
  let prevented = false;
  find(c, e => e.type === 'form').props.onSubmit({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
}
const retry = c => find(c, e => e.type === 'button' && e.props.children === 'Retry question').props.onClick();
async function settled(c) {
  for (let i = 0; i < 100; i++) {
    if (c.getSnapshot().status !== 'submitting') return;
    await setImmediate();
  }
  assert.fail('Question request did not settle');
}

test('supported inquiry posts the typed wire contract, renders every citation and inspects sources', async t => {
  let finish;
  const { controller: c, calls } = setup(t, () => new Promise(resolve => { finish = resolve; }));
  assert.equal(calls.length, 0, 'Opening the panel must not submit an inquiry');
  const initial = render(c);
  assert.match(initial, /<label for="case-question">Inquire about case evidence<\/label>/);
  assert.match(initial, /<textarea id="case-question" name="question" maxLength="2000"/);
  assert.match(initial, /placeholder="Ask a question about extracted entities or events\.\.\."/);
  change(c, `  ${question}  `); submit(c); submit(c);
  assert.equal(c.getSnapshot().status, 'submitting');
  assert.match(render(c), /aria-busy="true"/);
  assert.match(render(c), /role="status">Searching case evidence/);
  assert.match(render(c), /<button type="submit" disabled="">Ask question/);
  assert.equal(find(c, e => e.type === 'textarea').props.disabled, true);
  change(c, 'A different question');
  assert.equal(c.getSnapshot().question, `  ${question}  `, 'Draft cannot change while submitting');
  assert.equal(calls.length, 1, 'Repeated submit events share the in-flight request');
  const { url, options } = calls[0];
  assert.equal(url.origin, 'https://questions.invalid');
  assert.equal(url.pathname, `/api/v1/cases/${caseId}/questions`);
  assert.equal(url.search, ''); assert.equal(options.method, 'POST');
  assert.deepEqual(JSON.parse(options.body), { question });
  assert.equal(options.headers.get('Content-Type'), 'application/json');
  assert.equal(options.headers.get('Authorization'), 'Bearer synthetic-u11');
  finish(Response.json(answer())); await settled(c);
  assert.equal(c.getSnapshot().status, 'ready'); assert.deepEqual(c.getSnapshot().answer, answer());
  const html = render(c);
  assert.match(html, /question-supported/); assert.match(html, /Supported by Evidence/);
  assert.match(html, /The network log records two connections/);
  assert.match(html, /Source locator: row 1/); assert.match(html, /Source locator: row 2/);
  assert.match(html, /Retrieval version: deterministic-grounded-retrieval\/1/);
  assert.match(html, /aria-busy="false"/); assert.doesNotMatch(html, /Searching case evidence/);
  const inspected = [];
  const buttons = elements(QuestionAnswerPanel(props(c, value => inspected.push(value))),
    e => e.type === 'button' && e.props['aria-label']?.startsWith('Inspect source evidence'));
  assert.equal(buttons.length, 2);
  buttons.forEach(button => button.props.onClick());
  assert.deepEqual(inspected, [id(11), id(12)]);
  for (const source of answer().citations) assert.ok(html.includes(source.claim) && html.includes(source.observation_id));
});

test('unsupported inquiry explicitly reports uncertainty, no factual claims and zero citations', async t => {
  const unsupported = answer({ supported: false, answer: 'Insufficient evidence in this case to support the inquiry.', citations: [] });
  const { controller: c, calls } = setup(t, () => Response.json(unsupported));
  change(c, question); submit(c); await settled(c);
  assert.equal(calls.length, 1); assert.equal(c.getSnapshot().status, 'ready');
  assert.deepEqual(c.getSnapshot().answer.citations, []);
  const html = render(c);
  assert.match(html, /question-unsupported/); assert.match(html, /Insufficient Evidence/);
  assert.match(html, /Insufficient evidence in this case to support the inquiry/);
  assert.match(html, /No factual claims or citations were made/);
  assert.doesNotMatch(html, /Inspect source evidence|<li|Supported by Evidence/);
  assert.match(html, /Retrieval version:/);
});

test('blank and oversized questions fail locally; a 2000-character question is accepted', async t => {
  const { controller: c, calls } = setup(t, (_url, options) => Response.json(answer({ question: JSON.parse(options.body).question })));
  for (const value of ['', '   ', '\n\t\r', 'x'.repeat(2001)]) {
    change(c, value); submit(c); await settled(c);
    assert.equal(c.getSnapshot().status, 'error'); assert.equal(calls.length, 0);
    assert.match(render(c), /role="alert">Enter a non-empty question of up to 2000 characters/);
    assert.match(render(c), /aria-invalid="true" aria-describedby="case-question-message"/);
  }
  change(c, 'x'.repeat(2000)); submit(c); await settled(c);
  assert.equal(calls.length, 1); assert.equal(c.getSnapshot().status, 'ready');
});

for (const failure of [400, 401, 404, 'network']) test(`${failure}: safe error alert and successful retry`, async t => {
  let fail = true;
  const { client, controller: c, calls } = setup(t, () => {
    if (!fail) return Response.json(answer());
    if (failure === 'network') throw Error('PRIVATE TOKEN <script>alert(1)</script>');
    return Response.json({ code: 'FAILURE', message: 'PRIVATE TOKEN <script>alert(1)</script>' }, { status: failure });
  });
  change(c, question); submit(c); await settled(c);
  assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().answer, null);
  const html = render(c);
  assert.match(html, /role="alert"/); assert.match(html, /Retry question/);
  assert.doesNotMatch(html, /PRIVATE|TOKEN|<script|Supported by Evidence/);
  const message = { 400: /Check your question and retry/, 401: /Authentication required/,
    404: /Case unavailable or no longer accessible/, network: /Could not answer the question/ }[failure];
  assert.match(html, message);
  fail = false;
  if (failure === 401) {
    assert.equal(client.hasToken(), false); assert.equal(c.getSnapshot().question, '');
    retry(c); await settled(c); assert.equal(calls.length, 1, 'Retry cannot bypass authentication');
    client.setToken('synthetic-reopened'); c.start(); change(c, question);
  } else assert.equal(c.getSnapshot().question, question, 'Retry retains the failed question');
  // Invoke the rendered retry control, including after the session is reopened.
  if (failure === 401) await c.submit();
  else { retry(c); await settled(c); }
  assert.equal(calls.length, 2); assert.equal(c.getSnapshot().status, 'ready');
  assert.match(render(c), /Supported by Evidence/); assert.doesNotMatch(render(c), /role="alert"/);
});

test('questions, answers, claims, locators and retrieval versions are escaped text', async t => {
  const unsafe = '<img src=x onerror="alert(1)"><script>PAYLOAD</script> & text';
  const { controller: c, calls } = setup(t, () => Response.json(answer({ question: unsafe, answer: unsafe,
    citations: [citation(1, { claim: unsafe, source_locator: unsafe })], retrieval_version: unsafe })));
  change(c, unsafe);
  assert.match(render(c), /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  submit(c); await settled(c);
  assert.equal(c.getSnapshot().status, 'ready');
  assert.deepEqual(JSON.parse(calls[0].options.body), { question: unsafe });
  const html = render(c);
  assert.doesNotMatch(html, /<img|<script|<\/textarea><img/);
  assert.equal((html.match(/&lt;script&gt;PAYLOAD&lt;\/script&gt; &amp; text/g) ?? []).length, 6,
    'Textarea plus question, answer, claim, locator and version must all be escaped');
});

test('editing a new inquiry clears its active answer while preserving the conversation', async t => {
  const { controller: c } = setup(t);
  change(c, question); await c.submit(); assert.equal(c.getSnapshot().status, 'ready');
  change(c, 'New inquiry');
  assert.equal(c.getSnapshot().status, 'idle'); assert.equal(c.getSnapshot().answer, null);
  assert.equal(c.getSnapshot().history.length, 1);
  assert.match(render(c), /Supported by Evidence|Network observation/);
});

test('malformed, mismatched and inconsistent citation responses fail safely', async t => {
  const malformed = [null, {}, answer({ case_id: id(99) }), answer({ question: 'Different question' }),
    answer({ supported: 'true' }), answer({ answer: null }), answer({ retrieval_version: '' }),
    answer({ citations: null }), answer({ citations: [] }), answer({ supported: false }),
    ...[null, {}, citation(1, { claim: '' }), citation(1, { source_locator: null }),
      citation(1, { evidence_id: '<script>' }), citation(1, { observation_id: '<script>' })]
      .map(value => answer({ citations: [value] }))];
  for (const response of malformed) {
    const { controller: c } = setup(t, () => Response.json(response));
    change(c, question); await c.submit();
    assert.equal(c.getSnapshot().status, 'error'); assert.equal(c.getSnapshot().answer, null);
    assert.match(render(c), /Could not answer the question/);
    assert.doesNotMatch(render(c), /Supported by Evidence|<script/);
  }
});

test('citations without optional observation IDs remain inspectable under the generated schema', async t => {
  const source = citation(); delete source.observation_id;
  const { controller: c } = setup(t, () => Response.json(answer({ citations: [source] })));
  change(c, question); await c.submit();
  assert.equal(c.getSnapshot().status, 'ready');
  assert.match(render(c), /Inspect source evidence/); assert.doesNotMatch(render(c), /Observation:/);
});

for (const action of ['unmount', 'case change', 'sign out', 'token replacement']) {
  test(`${action} aborts in-flight requests, clears private state and ignores late delivery`, async t => {
    let finish, signal;
    const { controller: c, client } = setup(t, (_url, options) => {
      signal = options.signal; return new Promise(resolve => { finish = resolve; });
    });
    change(c, question); const pending = c.submit();
    let deliveries = 0; c.subscribe(() => deliveries++);
    if (action === 'sign out') client.clearToken();
    else if (action === 'token replacement') client.setToken('synthetic-replacement');
    else c.dispose();
    assert.equal(signal.aborted, true);
    const next = createQuestionController(client, id(99)); next.start(); t.after(() => next.dispose());
    const nextState = next.getSnapshot(), previous = c.getSnapshot(), before = deliveries;
    finish(Response.json(answer())); await pending;
    assert.equal(c.getSnapshot(), previous); assert.equal(deliveries, before);
    assert.equal(next.getSnapshot(), nextState); assert.equal(c.getSnapshot().answer, null);
    assert.equal(c.getSnapshot().question, '');
    assert.doesNotMatch(render(c), /Network observation|203\.0\.113\.8/);
  });
}

test('disposal is restartable and unsubscribes from session updates', async t => {
  const { controller: c, client, calls } = setup(t);
  c.dispose(); const disposed = c.getSnapshot(); client.setToken('synthetic-new');
  assert.equal(c.getSnapshot(), disposed);
  c.start(); change(c, question); await c.submit();
  assert.equal(c.getSnapshot().status, 'ready'); assert.equal(calls.length, 1);
  client.clearToken();
  assert.equal(c.getSnapshot().answer, null); assert.equal(c.getSnapshot().question, '');
  assert.match(render(c), /Authentication required/);
});

test('workspace defers the question composer until the investigator opens the tool', t => {
  const { client, calls } = setup(t);
  const html = renderToStaticMarkup(createElement(ApiProvider, { client },
    createElement(CaseAnalysisWorkspace, { caseId }, createElement(CaseEvidenceWorkspace, { caseId }))));
  assert.match(html, /role="tab" id="tab-investigation" aria-controls="panel-investigation"/);
  assert.match(html, /id="panel-investigation" role="tabpanel" aria-labelledby="tab-investigation" tabindex="0" hidden=""/);
  assert.doesNotMatch(html, /id="case-question"/); assert.equal(calls.length, 0);
});
