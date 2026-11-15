import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createQuestionController } from '../.test-build/src/cases/CaseWorkspace.mjs';
const caseId = '00000000-0000-4000-8000-000000000001';
const answer = { case_id: caseId, question: 'hello', answer: 'Hello there.', supported: false, citations: [], retrieval_version: 'test', answer_status: 'conversation' };
const encoder = new TextEncoder(), tick = () => new Promise(resolve => setTimeout(resolve, 0));
function setup() {
  let stream;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async (_url, options) => {
    assert.equal(options.headers.get('Accept'), 'application/x-ndjson, application/json');
    return new Response(new ReadableStream({ start(controller) { stream = controller; } }), { headers: { 'Content-Type': 'application/x-ndjson' } });
  } });
  client.setToken('synthetic-stream-token');
  const controller = createQuestionController(client, caseId); controller.start(); controller.setQuestion('hello');
  return { client, controller, send: event => stream.enqueue(encoder.encode(JSON.stringify(event) + '\n')), close: () => stream.close() };
}
test('drafts arrive before completion and final checked answer replaces them', async () => {
  const { controller, send, close } = setup(); const pending = controller.submit(); await tick();
  send({ type: 'status', stage: 'analyzing' }); send({ type: 'delta', text: 'Hello' }); await tick();
  assert.equal(controller.getSnapshot().status, 'submitting'); assert.equal(controller.getSnapshot().draft, 'Hello'); assert.equal(controller.getSnapshot().answer, null);
  send({ type: 'delta', text: ' there' }); send({ type: 'status', stage: 'checking' }); await tick();
  assert.equal(controller.getSnapshot().draft, 'Hello there'); assert.equal(controller.getSnapshot().stage, 'checking');
  send({ type: 'done', answer }); close(); await pending;
  assert.equal(controller.getSnapshot().answer.answer, 'Hello there.'); assert.equal(controller.getSnapshot().draft, ''); controller.dispose();
});
for (const action of ['cancel', 'clear', 'session']) test(`${action} rejects late streamed completion`, async () => {
  const { client, controller, send, close } = setup(); const pending = controller.submit(); await tick();
  send({ type: 'delta', text: 'Unfinished' }); await tick();
  if (action === 'session') client.clearToken(); else controller[action]();
  send({ type: 'done', answer }); close(); await pending;
  assert.ok(!controller.getSnapshot().draft); assert.equal(controller.getSnapshot().answer, null); assert.equal(controller.getSnapshot().history?.length ?? 0, 0); controller.dispose();
});
test('an interrupted stream cannot save a draft as a final answer', async () => {
  const { controller, send, close } = setup(); const pending = controller.submit(); await tick(); send({ type: 'delta', text: 'Partial' }); close(); await pending;
  assert.equal(controller.getSnapshot().status, 'error'); assert.ok(!controller.getSnapshot().draft); assert.equal(controller.getSnapshot().answer, null); controller.dispose();
});
test('transport decodes unicode and lines split across single-byte chunks', async () => {
  let stream;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => new Response(new ReadableStream({ start(c) { stream = c; } }), { headers: { 'Content-Type': 'application/x-ndjson' } }) });
  client.setToken('synthetic'); const seen = [];
  const pending = client.request('post', '/api/v1/cases/{caseId}/questions', { path: { caseId }, body: { question: 'hello' }, onEvent: e => seen.push(e) }); await tick();
  const bytes = encoder.encode(JSON.stringify({ type: 'delta', text: 'GPS → Chennai 📍' })+'\n'+JSON.stringify({ type: 'done', answer })+'\n');
  for (const byte of bytes) stream.enqueue(Uint8Array.of(byte)); stream.close(); await pending; assert.equal(seen[0].text, 'GPS → Chennai 📍');
});
