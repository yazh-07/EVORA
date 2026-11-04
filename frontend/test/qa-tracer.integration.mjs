import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

// Real frontend HTTP client, FastAPI, SQLite, parser, retrieval and audit.
// The shared harness explicitly doubles Neo4j; no browser/live graph claim.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i02c-'));
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', join(temporary, 'cases.sqlite3')], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
// Attach startup and close listeners immediately, including on spawn failure.
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I02C server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I02C server exited (${code ?? signal}): ${diagnostics}`));
  });
});
const closed = new Promise(resolve => child.once('close', resolve));

async function until(read, done, label) {
  const deadline = Date.now() + 15000;
  let value;
  do {
    value = await read();
    if (done(value)) return value;
    await delay(25);
  } while (Date.now() < deadline);
  assert.fail(`${label} timed out: ${JSON.stringify(value)}; ${diagnostics}`);
}

try {
  const origin = await originReady;
  // The socket is announced before uvicorn accepts requests.
  await until(async () => {
    try {
      return (await fetch(origin + '/api/v1/cases', {
        headers: { Authorization: 'Bearer u02-synthetic-two' }, signal: AbortSignal.timeout(1000),
      })).status;
    } catch { return null; }
  }, status => status === 200, 'API readiness');
  const client = createApiClient({ baseUrl: origin, fetch: (url, options) =>
    fetch(url, { ...options, signal: AbortSignal.any([options.signal, AbortSignal.timeout(5000)]) }) });
  client.setToken('u02-synthetic-two');
  const investigation = await client.request('post', '/api/v1/cases', {
    body: { title: 'Synthetic I02C grounded Q&A tracer' },
  });
  const caseId = investigation.id;
  const bytes = await readFile(new URL('../../fixtures/synthetic-case/network.csv', import.meta.url));
  const body = new FormData();
  body.set('file', new File([bytes], 'network.csv', { type: 'text/csv' }));
  body.set('kind', 'network_log');
  body.set('source_label', 'Synthetic I02C network.csv');
  const evidence = await client.request('post', '/api/v1/cases/{caseId}/evidence', {
    path: { caseId }, body,
  });
  assert.equal(evidence.case_id, caseId);
  assert.equal(evidence.sha256, createHash('sha256').update(bytes).digest('hex'));
  assert.equal(evidence.size_bytes, bytes.length);
  const runPath = { caseId, evidenceId: evidence.id };
  const accepted = await client.request('post', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', {
    path: runPath, header: { 'Idempotency-Key': randomUUID() },
  });
  const run = await until(() => client.request('get',
    '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', {
      path: { ...runPath, runId: accepted.id },
    }), item => ['completed', 'failed'].includes(item.status), 'network processing');
  assert.equal(run.status, 'completed', JSON.stringify(run));
  assert.equal(run.evidence_id, evidence.id);
  const observations = await client.request('get', '/api/v1/cases/{caseId}/observations', {
    path: { caseId }, query: { evidence_id: evidence.id, processing_run_id: run.id, limit: 100, offset: 0 },
  });
  assert.equal(observations.items.length, observations.total, 'all source observations read through HTTP');
  assert.deepEqual(observations.items.filter(item => item.kind === 'network.device')
    .map(item => [item.normalized_value, item.source_locator]).sort(), [
    ['D-7', 'row 2, device_id'], ['D-9', 'row 3, device_id'],
  ]);

  const supportedQuestion = 'What devices appear in the network log?';
  const supported = await client.request('post', '/api/v1/cases/{caseId}/questions', {
    path: { caseId }, body: { question: supportedQuestion },
  });
  assert.equal(supported.case_id, caseId);
  assert.equal(supported.question, supportedQuestion);
  assert.equal(supported.supported, true);
  assert.equal(typeof supported.answer, 'string');
  assert.match(supported.answer, /network\.device records "D-7"/);
  assert.match(supported.answer, /network\.device records "D-9"/);
  assert.ok(Array.isArray(supported.citations));
  assert.ok(supported.citations.length >= 1, 'supported answers require citations');
  for (const citation of supported.citations) {
    for (const field of ['claim', 'evidence_id', 'source_locator']) {
      assert.equal(typeof citation[field], 'string', `citation has ${field}`);
      assert.ok(citation[field].trim().length > 0, `citation has nonempty ${field}`);
    }
    assert.equal(citation.evidence_id, evidence.id);
    const source = observations.items.find(item => item.id === citation.observation_id);
    assert.ok(source, 'citation resolves to an actual completed observation');
    assert.equal(source.case_id, caseId);
    assert.equal(source.processing_run_id, run.id);
    assert.equal(citation.source_locator, source.source_locator);
    assert.equal(citation.claim, `${source.kind} records ${JSON.stringify(source.normalized_value)}.`);
    assert.ok(supported.answer.includes(citation.claim), 'answer contains the cited fact');
  }
  for (const device of ['D-7', 'D-9']) {
    assert.ok(supported.citations.some(citation =>
      citation.claim === `network.device records "${device}".`), `${device} has a source citation`);
  }

  const unsupportedQuestion = 'Who is the guilty person?';
  const unsupported = await client.request('post', '/api/v1/cases/{caseId}/questions', {
    path: { caseId }, body: { question: unsupportedQuestion },
  });
  assert.equal(unsupported.case_id, caseId);
  assert.equal(unsupported.question, unsupportedQuestion);
  assert.equal(unsupported.supported, false);
  assert.deepEqual(unsupported.citations, [], 'unsupported citations must be an empty array');
  assert.match(unsupported.answer, /Insufficient evidence/);

  const audit = await client.request('get', '/api/v1/cases/{caseId}/audit-events', {
    path: { caseId }, query: { limit: 100, offset: 0 },
  });
  assert.equal(audit.items.length, audit.total, 'complete audit page');
  const inquiries = audit.items.filter(event => event.action === 'askCaseQuestion');
  assert.equal(inquiries.length, 2, 'each accepted question has one audit event');
  assert.deepEqual(inquiries.map(event => event.reason).sort(), [
    'Grounded inquiry (supported)', 'Grounded inquiry (unsupported)',
  ]);
  for (const event of inquiries) {
    assert.equal(event.actor_id, 'investigator-2');
    assert.equal(event.case_id, caseId);
    assert.equal(event.target_id, caseId);
    assert.ok(Number.isFinite(Date.parse(event.created_at)), 'valid audit timestamp');
    const serialized = JSON.stringify(event);
    for (const privateValue of [supportedQuestion, unsupportedQuestion, supported.answer,
      unsupported.answer, 'u02-synthetic-two']) {
      assert.ok(!serialized.includes(privateValue), 'audit omits question, answer and bearer token');
    }
  }

  console.log('PASS I02C grounded Q&A HTTP tracer: investigator-2, real network D-7/D-9 processing, factual answer and resolved citations, unsupported answer with empty citations, safe audit for both inquiries.');
} finally {
  clearTimeout(startupTimer);
  try {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
    try { await closed; } finally { clearTimeout(forceKill); }
  } finally {
    assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i02c-')));
    await rm(temporary, { recursive: true, force: true });
  }
}
