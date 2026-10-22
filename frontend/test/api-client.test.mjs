import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { test } from 'node:test';
import { ApiClientError, ApiHttpError, apiOrigin, createApiClient } from '../.test-build/src/api/client.mjs';
import { analysis, caseA, caseB, casesA, emptyCases, evidence, invalidInput, originalBytes } from '../.test-build/test/fixtures/api.mjs';

// Fetch and localhost responses below are disclosed schema-derived doubles, not F00.
const origin = 'http://127.0.0.1:8000';
const tokenA = 'synthetic-investigator-1';
const tokenB = 'synthetic-investigator-2';
const json = (value, status = 200) => Response.json(value, { status });
function clientWith(fetch) {
  const client = createApiClient({ baseUrl: origin, fetch });
  client.setToken(tokenA);
  return client;
}

test('configures one HTTP(S) origin and rejects credential/path/query/fragment configuration safely', () => {
  assert.equal(apiOrigin('https://api.example.test/'), 'https://api.example.test');
  for (const baseUrl of ['not-a-url', '/api', '//other.test', 'file:///tmp', 'https://secret:private@api.test',
    'https://api.test/api/v1', 'https://api.test?token=private', 'https://api.test/#private', ' https://api.test']) {
    assert.throws(() => createApiClient({ baseUrl }), error => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, 'configuration');
      assert.doesNotMatch(error.message, /private|secret/);
      return true;
    });
  }
});

test('missing/cleared tokens stop requests before transport; tokens are isolated per client', async () => {
  let calls = 0;
  const client = createApiClient({ baseUrl: origin, fetch: async () => { calls += 1; return json(emptyCases); } });
  await assert.rejects(client.request('get', '/api/v1/cases', {}), { kind: 'authentication' });
  client.setToken(tokenA);
  await client.request('get', '/api/v1/cases', {});
  client.clearToken();
  await assert.rejects(client.request('get', '/api/v1/cases', {}), { kind: 'authentication' });
  assert.equal(calls, 1);
  assert.equal(createApiClient({ baseUrl: origin }).hasToken(), false);
  assert.doesNotMatch(JSON.stringify(client), /synthetic-investigator/);
  for (const token of [undefined, null, '', 'has spaces', 'bad\r\nAuthorization: private']) {
    assert.throws(() => client.setToken(token), { kind: 'authentication' });
  }
});

test('sends explicit bearer credentials, encoded paths/query and no persistent cache/cookies/referrer/redirects', async () => {
  const calls = [];
  const client = clientWith(async (url, init) => { calls.push({ url, init }); return json(url.pathname === '/api/v1/cases' ? casesA : caseA); });
  const data = await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: caseA.id } });
  assert.deepEqual(data, caseA);
  await client.request('get', '/api/v1/cases', { query: { limit: 1, offset: 0 } });
  assert.equal(calls[0].url.href, `${origin}/api/v1/cases/${caseA.id}`);
  assert.equal(calls[1].url.search, '?limit=1&offset=0');
  assert.equal(calls[0].init.headers.get('Authorization'), `Bearer ${tokenA}`);
  assert.equal(calls[0].init.headers.get('Accept'), 'application/json');
  assert.equal(calls[0].init.headers.has('Content-Type'), false);
  assert.equal(calls[0].init.credentials, 'omit');
  assert.equal(calls[0].init.cache, 'no-store');
  assert.equal(calls[0].init.redirect, 'error');
  assert.equal(calls[0].init.referrerPolicy, 'no-referrer');
  assert.equal(calls[0].init.body, undefined);
});

test('encodes hostile segment values without changing origin or path boundaries; rejects dot traversal', async () => {
  let calls = 0;
  const client = clientWith(async (url) => {
    calls += 1;
    assert.equal(url.origin, origin);
    assert.match(url.pathname, /%2F%2Fother.test%2F%3Fprivate%23/);
    return json(caseA);
  });
  await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: '//other.test/?private#' } });
  for (const caseId of ['', '.', '..']) {
    await assert.rejects(client.request('get', '/api/v1/cases/{caseId}', { path: { caseId } }), { kind: 'request' });
  }
  await assert.rejects(client.request('get', 'https://other.test/api/v1/cases', {}), { kind: 'request' });
  await assert.rejects(client.request('get', '/api/v1/cases', { header: { Authorization: 'private' } }), { kind: 'request' });
  assert.equal(calls, 1);
});

test('serializes JSON writes and preserves explicit idempotency keys/bodyless commands without retries', async () => {
  const calls = [];
  const client = clientWith(async (url, init) => { calls.push({ url, init }); return init.body ? json(caseA, 201) : json(analysis, 202); });
  await client.request('post', '/api/v1/cases', { body: { title: caseA.title } });
  await client.request('post', '/api/v1/cases/{caseId}/analysis-runs', {
    path: { caseId: caseA.id }, header: { 'Idempotency-Key': 'synthetic-replay-key' },
  });
  assert.equal(calls[0].init.body, JSON.stringify({ title: caseA.title }));
  assert.equal(calls[0].init.headers.get('Content-Type'), 'application/json');
  assert.equal(calls[1].init.body, undefined);
  assert.equal(calls[1].init.headers.get('Content-Type'), null);
  assert.equal(calls[1].init.headers.get('Idempotency-Key'), 'synthetic-replay-key');
  assert.equal(calls.length, 2);
});

test('passes multipart boundaries to Fetch and returns synthetic original bytes as a memory Blob', async () => {
  const payload = originalBytes;
  const form = new FormData();
  form.append('file', new Blob([payload]), 'synthetic.bin');
  form.append('source_label', 'Synthetic fixture');
  form.append('kind', 'document');
  const client = clientWith(async (_url, init) => {
    if (init.method === 'POST') {
      assert.equal(init.body, form);
      assert.equal(init.headers.has('Content-Type'), false);
      return json(evidence, 201);
    }
    assert.equal(init.headers.get('Accept'), 'application/octet-stream');
    return new Response(payload, { headers: { 'Content-Type': 'application/octet-stream' } });
  });
  await client.request('post', '/api/v1/cases/{caseId}/evidence', { path: { caseId: caseA.id }, body: form });
  const data = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
    path: { caseId: caseA.id, evidenceId: caseB.id }, responseType: 'blob',
  });
  assert.deepEqual(new Uint8Array(await data.arrayBuffer()), payload);
});

test('shares schema-shaped HTTP errors and keeps 404 foreign/missing indistinguishable', async () => {
  const client = clientWith(async () => json(invalidInput, 400));
  await assert.rejects(client.request('get', '/api/v1/cases', {}), error => {
    assert.ok(error instanceof ApiHttpError);
    assert.equal(error.status, 400);
    assert.deepEqual(error.apiError, invalidInput);
    return true;
  });
  const notFound = clientWith(async () => json({ code: 'DO_NOT_EXPOSE', message: 'private case details' }, 404));
  const errors = [];
  for (const caseId of [caseA.id, caseB.id]) {
    try { await notFound.request('get', '/api/v1/cases/{caseId}', { path: { caseId } }); }
    catch (error) { errors.push(error.apiError); }
  }
  assert.deepEqual(errors, [
    { code: 'NOT_FOUND', message: 'Resource not found.' },
    { code: 'NOT_FOUND', message: 'Resource not found.' },
  ]);
  assert.equal(notFound.hasToken(), true);
});

test('401 invalidates the memory session and pending responses, with no automatic token refresh/retry', async () => {
  let finish;
  let calls = 0;
  let pendingSignal;
  const client = clientWith(async (_url, init) => {
    calls += 1;
    if (calls === 1) { pendingSignal = init.signal; return new Promise(resolve => { finish = resolve; }); }
    return new Response('private invalid-token response', { status: 401 });
  });
  const outstanding = client.request('get', '/api/v1/cases', {});
  await assert.rejects(client.request('get', '/api/v1/cases', {}), error => {
    assert.equal(error.status, 401);
    assert.deepEqual(error.apiError, { code: 'UNAUTHORIZED', message: 'Authentication required.' });
    return true;
  });
  assert.equal(client.hasToken(), false);
  assert.equal(pendingSignal.aborted, true);
  finish(json(casesA)); // This deliberate fake ignores cancellation to test the stale-session guard.
  await assert.rejects(outstanding, { kind: 'session' });
  await assert.rejects(client.request('get', '/api/v1/cases', {}), { kind: 'authentication' });
  assert.equal(calls, 2);
});

test('actor replacement rejects late data and late 401 without clearing the new actor token', async () => {
  for (const status of [200, 401]) {
    let finish;
    const seen = [];
    const client = clientWith(async (_url, init) => {
      seen.push(init.headers.get('Authorization'));
      if (seen.length === 1) return new Promise(resolve => { finish = resolve; });
      return json(caseB);
    });
    const outstanding = client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: caseA.id } });
    client.setToken(tokenB);
    finish(json(status === 200 ? caseA : invalidInput, status));
    await assert.rejects(outstanding, { kind: 'session' });
    assert.equal(client.hasToken(), true);
    assert.deepEqual(await client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: caseB.id } }), caseB);
    assert.deepEqual(seen, [`Bearer ${tokenA}`, `Bearer ${tokenB}`]);
  }
});

test('session subscriptions notify only on identity changes and can unsubscribe', () => {
  const client = createApiClient({ baseUrl: origin });
  let notifications = 0;
  const unsubscribe = client.subscribeSession(() => { notifications += 1; });
  client.setToken(tokenA);
  client.setToken(tokenA);
  assert.equal(notifications, 1);
  assert.equal(client.getSessionVersion(), 1);
  client.clearToken();
  assert.equal(notifications, 2);
  unsubscribe();
  client.setToken(tokenB);
  assert.equal(notifications, 2);
});

test('malformed/non-JSON failures never surface raw bodies as ApiError or loggable error messages', async () => {
  for (const response of [
    new Response('<html>private server diagnostics</html>', { status: 500 }),
    new Response('{private', { status: 400, headers: { 'Content-Type': 'application/json' } }),
    json({ ...invalidInput, private: 'unapproved' }, 400),
  ]) {
    const client = clientWith(async () => response);
    await assert.rejects(client.request('get', '/api/v1/cases', {}), error => {
      assert.ok(error instanceof ApiHttpError);
      assert.equal(error.apiError, undefined);
      assert.doesNotMatch(error.message, /private|diagnostics|unapproved/);
      return true;
    });
  }
  for (const response of [new Response('<html>private</html>'), new Response('{private', { headers: { 'Content-Type': 'application/json' } })]) {
    await assert.rejects(clientWith(async () => response).request('get', '/api/v1/cases', {}), { kind: 'protocol' });
  }
});

test('network errors and cancellation expose safe distinct errors without retrying', async () => {
  let calls = 0;
  const client = clientWith(async () => { calls += 1; throw new Error(`private URL contains ${tokenA}`); });
  await assert.rejects(client.request('get', '/api/v1/cases', {}), error => {
    assert.equal(error.kind, 'network');
    assert.doesNotMatch(error.message, /private|synthetic-investigator/);
    assert.equal(error.cause, undefined);
    return true;
  });
  assert.equal(calls, 1);
  let cancelledCalls = 0;
  const cancelled = clientWith(async () => { cancelledCalls += 1; throw new Error('Transport should not run'); });
  await assert.rejects(cancelled.request('get', '/api/v1/cases', { signal: AbortSignal.abort() }), { name: 'AbortError', message: 'API request cancelled.' });
  assert.equal(cancelledCalls, 0);
});

test('logout while reading a response body never returns the old actor data', async () => {
  let finish;
  const reading = new Promise(resolve => { finish = resolve; });
  const response = json(casesA);
  response.json = () => reading;
  const client = clientWith(async () => response);
  const pending = client.request('get', '/api/v1/cases', {});
  await Promise.resolve(); // Fetch has resolved; response.json is still pending.
  client.clearToken();
  finish(casesA);
  await assert.rejects(pending, { kind: 'session' });
});

test('invalid request serialization/header data and mismatched download content fail safely', async () => {
  let calls = 0;
  const client = clientWith(async () => { calls += 1; return json(invalidInput); });
  const body = { title: 'Synthetic' };
  body.self = body;
  await assert.rejects(client.request('post', '/api/v1/cases', { body }), { kind: 'request' });
  await assert.rejects(client.request('post', '/api/v1/cases/{caseId}/analysis-runs', {
    path: { caseId: caseA.id }, header: { 'Idempotency-Key': 'private\r\ninvalid' },
  }), { kind: 'request' });
  assert.equal(calls, 0);
  await assert.rejects(client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
    path: { caseId: caseA.id, evidenceId: evidence.id }, responseType: 'blob',
  }), { kind: 'protocol' });
});

test('real Fetch reaches a localhost fixture and refuses an HTTP redirect before credentials leave that origin', async () => {
  let destinationCalls = 0;
  const destination = createServer((_request, response) => { destinationCalls += 1; response.end('must not be reached'); });
  const source = createServer((request, response) => {
    assert.equal(request.headers.authorization, `Bearer ${tokenA}`);
    if (request.url === '/api/v1/cases') {
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify(emptyCases));
    } else {
      response.writeHead(302, { Location: `http://127.0.0.1:${destination.address().port}/private` });
      response.end();
    }
  });
  try {
    destination.listen(0, '127.0.0.1');
    source.listen(0, '127.0.0.1');
    await Promise.all([once(destination, 'listening'), once(source, 'listening')]);
    const client = createApiClient({ baseUrl: `http://127.0.0.1:${source.address().port}` });
    client.setToken(tokenA);
    assert.deepEqual(await client.request('get', '/api/v1/cases', {}), emptyCases);
    await assert.rejects(client.request('get', '/api/v1/cases/{caseId}', { path: { caseId: caseA.id } }), { kind: 'network' });
    assert.equal(destinationCalls, 0);
  } finally {
    await Promise.all([new Promise(resolve => source.close(resolve)), new Promise(resolve => destination.close(resolve))]);
  }
});
