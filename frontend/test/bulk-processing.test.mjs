import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createBulkProcessingController, BulkProcessingResults } from '../.test-build/src/cases/CaseWorkspace.mjs';

const caseId = '11111111-1111-4111-8111-111111111111';
const uuid = number => `22222222-2222-4222-8222-${String(number).padStart(12, '0')}`;
const evidence = (number, kind = 'document') => ({ id: uuid(number), case_id: caseId, kind, filename: `source-${number}.${kind === 'image' ? 'png' : 'txt'}`, source_label: `Source ${number}`, sha256: 'a'.repeat(64), size_bytes: 30, media_type: 'text/plain', created_at: '2026-11-05T00:00:00Z' });
const run = (item, status = 'completed', number = 1000) => ({ id: uuid(number), case_id: caseId, evidence_id: item.id, status, processor_version: 'fixture/1', created_at: '2026-11-05T00:00:00Z', ...(['completed', 'failed'].includes(status) ? { finished_at: '2026-11-05T00:01:00Z' } : {}), ...(status === 'failed' ? { error: 'Fixture failure' } : {}) });
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function setup(items, handler = () => undefined) {
  const calls = [], sessionListeners = new Set(); let session = 0;
  const client = { hasToken: () => true, getUser: () => ({ role: 'investigator' }), getSessionVersion: () => session,
    subscribeSession(listener) { sessionListeners.add(listener); return () => sessionListeners.delete(listener); },
    async request(method, route, options) {
      calls.push({ method, route, options });
      const answer = await handler(method, route, options, calls);
      if (answer !== undefined) return answer;
      if (method === 'get' && route.endsWith('/evidence')) {
        const { offset, limit } = options.query;
        return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
      }
      if (method === 'get' && route.endsWith('/processing-runs')) return [];
      if (method === 'post') return run(items.find(item => item.id === options.path.evidenceId), 'completed', calls.length + 1000);
      throw Error('Unexpected request');
    },
  };
  const controller = createBulkProcessingController(client, caseId, 0); controller.start();
  return { client, controller, calls, changeSession() { session++; sessionListeners.forEach(listener => listener()); } };
}
const posts = calls => calls.filter(call => call.method === 'post');

test('processes every evidence page serially; skips completed files and audio; failures do not hide other results', async () => {
  const items = Array.from({ length: 101 }, (_, i) => evidence(i + 1)); items[2].kind = 'audio';
  const { controller, calls } = setup(items, (method, route, options) => {
    const item = items.find(item => item.id === options.path.evidenceId);
    if (method === 'get' && route.endsWith('/processing-runs') && item === items[0]) return [run(item)];
    if (method === 'post' && item === items[1]) return run(item, 'queued', 1900);
    if (route.endsWith('/processing-runs/{runId}')) return run(item, 'failed', 1900);
  });
  await controller.submit();
  const result = controller.getSnapshot();
  assert.equal(result.status, 'done'); assert.equal(result.items.length, 101);
  assert.deepEqual(result.items.slice(0, 4).map(item => item.status), ['skipped', 'failed', 'skipped', 'completed']);
  assert.equal(result.items[100].status, 'completed');
  assert.deepEqual(calls.filter(call => call.route.endsWith('/evidence')).map(call => call.options.query.offset), [0, 100]);
  assert.equal(posts(calls).length, 99);
  assert.equal(new Set(posts(calls).map(call => call.options.header['Idempotency-Key'])).size, 99);
  assert.ok(posts(calls).every(call => call.options.body === undefined));
  const html = renderToStaticMarkup(createElement(BulkProcessingResults, { state: result }));
  assert.match(html, /101 of 101 checked/); assert.match(html, /1 failed/); assert.match(html, /Evidence processing progress/);
  controller.dispose();
});

test('joins queued work rather than posting another run; duplicate clicks cannot start another batch', async () => {
  const item = evidence(1), wait = deferred(); let reads = 0;
  const { controller, calls } = setup([item], (method, route) => {
    if (method === 'get' && route.endsWith('/processing-runs')) { reads++; return wait.promise; }
    if (route.endsWith('/processing-runs/{runId}')) return run(item);
  });
  const pending = controller.submit();
  await new Promise(resolve => setTimeout(resolve, 0)); await controller.submit();
  wait.resolve([run(item, 'running')]); await pending;
  assert.equal(reads, 1); assert.equal(posts(calls).length, 0);
  assert.equal(controller.getSnapshot().items[0].status, 'skipped'); controller.dispose();
});

test('vision enrichment uses pinned provider/model/destination and video limits; base-only completed image is enriched', async () => {
  const items = [evidence(1, 'image'), evidence(2, 'video'), evidence(3, 'image')];
  const vision = { provider: 'chatgpt', model: 'vision-model', endpoint: 'https://api.openai.com/v1', consent: true };
  const { controller, calls } = setup(items, (method, route, options) => {
    const item = items.find(item => item.id === options.path.evidenceId);
    if (method === 'get' && route.endsWith('/processing-runs') && item.kind === 'image') return [run(item)];
    if (route.endsWith('/observations')) return { items: options.query.evidence_id === items[0].id ? [] : [{ id: uuid(3000), case_id: caseId, evidence_id: items[2].id, processing_run_id: uuid(1000), kind: 'image.provenance', source_locator: 'image=0', raw_value: '{}', extraction_confidence: 0 }], total: options.query.evidence_id === items[0].id ? 0 : 1, offset: 0, limit: 100 };
    if (method === 'post') { vision.model = 'changed-after-start'; return run(item); }
  });
  await controller.submit({ vision });
  assert.deepEqual(posts(calls).map(call => call.route.split('/').at(-1)), ['image-analysis', 'video-analysis']);
  assert.ok(posts(calls).every(call => call.options.body.expected_model === 'vision-model' && call.options.body.confirm_external_processing));
  assert.equal(posts(calls)[1].options.body.sample_interval_seconds, 5);
  assert.equal(posts(calls)[1].options.body.max_frames, 12); assert.equal(posts(calls)[1].options.body.transcribe_speech, false);
  assert.equal(controller.getSnapshot().items[2].status, 'skipped'); controller.dispose();
});

test('external vision requires explicit consent before any request; default batch uses only basic processing', async () => {
  const { controller, calls } = setup([evidence(1, 'image')]);
  await controller.submit({ vision: { provider: 'openai', model: 'vision', endpoint: 'https://example.test/v1', consent: false } });
  assert.equal(controller.getSnapshot().status, 'error'); assert.equal(calls.length, 0);
  await controller.submit(); assert.equal(posts(calls)[0].route.split('/').at(-1), 'processing-runs'); controller.dispose();
});

for (const action of ['stop', 'dispose', 'session']) test(`${action} during a POST ignores late completion and never starts the next source`, async () => {
  const wait = deferred(); const items = [evidence(1), evidence(2)];
  const fixture = setup(items, method => method === 'post' ? wait.promise : undefined);
  const pending = fixture.controller.submit();
  await new Promise(resolve => setTimeout(resolve, 0));
  if (action === 'session') fixture.changeSession(); else fixture.controller[action]();
  wait.resolve(run(items[0])); await pending;
  assert.equal(posts(fixture.calls).length, 1); assert.notEqual(fixture.controller.getSnapshot().status, 'done');
  fixture.controller.dispose();
});

test('an ambiguous failed POST is not retried automatically; next explicit batch reconciles completed history', async () => {
  const item = evidence(1); let uncertain = true;
  const { controller, calls } = setup([item], (method, route) => {
    if (method === 'post') { uncertain = false; throw Error('PRIVATE server details'); }
    if (!uncertain && route.endsWith('/processing-runs')) return [run(item)];
  });
  await controller.submit(); assert.equal(controller.getSnapshot().items[0].status, 'unknown');
  assert.doesNotMatch(JSON.stringify(controller.getSnapshot()), /PRIVATE/);
  await controller.submit(); assert.equal(posts(calls).length, 1); assert.equal(controller.getSnapshot().items[0].status, 'skipped'); controller.dispose();
});

test('foreign evidence page stops before writes, and foreign run cannot become a completed result', async () => {
  const item = evidence(1);
  const foreign = setup([item], (_method, route) => route.endsWith('/evidence') ? { items: [{ ...item, case_id: uuid(777) }], total: 1, offset: 0, limit: 100 } : undefined);
  await foreign.controller.submit(); assert.equal(foreign.controller.getSnapshot().status, 'error'); assert.equal(posts(foreign.calls).length, 0); foreign.controller.dispose();
  const malformed = setup([item], method => method === 'post' ? { ...run(item), evidence_id: uuid(999) } : undefined);
  await malformed.controller.submit(); assert.equal(malformed.controller.getSnapshot().items[0].status, 'unknown'); malformed.controller.dispose();
});

test('reviewer cannot start a batch; effect cleanup/setup supports remount', async () => {
  const fixture = setup([evidence(1)]); fixture.client.getUser = () => ({ role: 'reviewer' });
  await fixture.controller.submit(); assert.equal(fixture.calls.length, 0);
  fixture.controller.dispose(); fixture.controller.start(); fixture.client.getUser = () => ({ role: 'investigator' });
  await fixture.controller.submit(); assert.equal(posts(fixture.calls).length, 1); fixture.controller.dispose();
});

test('explicit selection processes only those authorized sources, including across pages', async () => {
 const items=Array.from({length:102},(_,i)=>evidence(i+1));
 const {controller,calls}=setup(items);
 await controller.submit({evidenceIds:[items[1].id,items[101].id]});
 assert.deepEqual(posts(calls).map(call=>call.options.path.evidenceId),[items[1].id,items[101].id]);
 assert.equal(controller.getSnapshot().items.length,2);controller.dispose();
});
test('missing or duplicate selected IDs cannot trigger any processing request', async () => {
 for(const evidenceIds of [[uuid(999)],[uuid(1),uuid(1)],[]]){
  const {controller,calls}=setup([evidence(1)]);await controller.submit({evidenceIds});
  assert.equal(posts(calls).length,0);assert.equal(controller.getSnapshot().status,'error');controller.dispose();
 }
});
test('explicit reprocessing replaces the default completed-output skip',async()=>{
 const item=evidence(1);const {controller,calls}=setup([item],(method,route)=>method==='get'&&route.endsWith('/processing-runs')?[run(item)]:undefined);
 await controller.submit({evidenceIds:[item.id],reprocess:true});assert.equal(posts(calls).length,1);controller.dispose();
});
