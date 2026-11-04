import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

// Real HTTP client, FastAPI, SQLite, registered parsers, analysis and audit.
// The shared harness explicitly doubles Neo4j; no browser/live graph claim.
const frontend = fileURLToPath(new URL('..', import.meta.url));
const python = process.env.EVORA_TEST_PYTHON ?? 'python';
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-i02b-'));
const child = spawn(python, ['test/serve-cases.py', '--api-only', '--database', join(temporary, 'cases.sqlite3')], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'],
});
let diagnostics = '';
child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-8000); });
// Attach listeners immediately, including close on spawn failure.
let startupTimer;
const originReady = new Promise((resolve, reject) => {
  startupTimer = setTimeout(() => reject(Error(`I02B server startup timed out: ${diagnostics}`)), 15000);
  let stdout = '';
  child.stdout.on('data', data => {
    stdout += data;
    const found = stdout.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/);
    if (found) { clearTimeout(startupTimer); resolve(found[1]); }
  });
  child.once('error', error => { clearTimeout(startupTimer); reject(error); });
  child.once('exit', (code, signal) => {
    clearTimeout(startupTimer);
    reject(Error(`I02B server exited (${code ?? signal}): ${diagnostics}`));
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

function assertTimestamp(value) {
  assert.match(value, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/);
  assert.ok(Number.isFinite(Date.parse(value)), 'valid UTC timestamp');
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
    body: { title: 'Synthetic I02B human review and override tracer' },
  });
  const caseId = investigation.id;
  const get = (route, query, path = {}) => client.request('get', `/api/v1/cases/{caseId}${route}`, {
    path: { caseId, ...path }, query,
  });
  const post = (route, options) => client.request('post', `/api/v1/cases/{caseId}${route}`, {
    ...options, path: { caseId, ...options.path },
  });
  async function completedRun(route, path = {}) {
    const accepted = await post(route, { path, header: { 'Idempotency-Key': randomUUID() } });
    const run = await until(() => get(`${route}/{runId}`, undefined, { ...path, runId: accepted.id }),
      item => ['completed', 'failed'].includes(item.status), route);
    assert.equal(run.status, 'completed', JSON.stringify(run));
    return run;
  }
  async function uploadAndProcess(filename, kind) {
    const bytes = await readFile(new URL(`../../fixtures/synthetic-case/${filename}`, import.meta.url));
    const body = new FormData();
    body.set('file', new File([bytes], filename, { type: 'text/csv' }));
    body.set('kind', kind);
    body.set('source_label', `Synthetic I02B ${filename}`);
    const evidence = await post('/evidence', { body });
    assert.equal(evidence.sha256, createHash('sha256').update(bytes).digest('hex'));
    assert.equal(evidence.size_bytes, bytes.length);
    const processing = await completedRun('/evidence/{evidenceId}/processing-runs', { evidenceId: evidence.id });
    assert.equal(processing.evidence_id, evidence.id);
    return evidence;
  }

  // Two real network uploads generate shared-identifier findings; GPS supplies
  // a distinct lower score so promoting it would expose priority-based sorting.
  const network1 = await uploadAndProcess('network.csv', 'network_log');
  const network2 = await uploadAndProcess('network.csv', 'network_log');
  const gps = await uploadAndProcess('gps.csv', 'gps');
  const run = await completedRun('/analysis-runs');
  const findings = await get('/findings');
  assert.equal(findings.analysis_run_id, run.id);
  assert.equal(findings.items.length, findings.total);
  assert.ok(findings.total > 0, 'real completed analysis generates a reviewable finding');
  const finding = findings.items[0];
  assert.equal(finding.case_id, caseId);
  assert.equal(finding.analysis_run_id, run.id);
  assert.deepEqual([...finding.evidence_ids].sort(), [network1.id, network2.id].sort());

  const baseline = await get('/triage', { limit: 100, offset: 0 });
  assert.equal(baseline.analysis_run_id, run.id);
  assert.equal(baseline.total, 3);
  assert.equal(baseline.items.length, baseline.total);
  const ids = items => items.map(item => item.evidence_id);
  assert.deepEqual([...ids(baseline.items)].sort(), [network1.id, network2.id, gps.id].sort());
  for (const item of baseline.items) {
    assert.ok(item.latest_result, 'every processed fixture has a computed result');
    assert.equal(item.effective_priority, item.latest_result.priority);
    assert.equal(item.override, undefined);
  }
  const computedOrder = [...baseline.items].sort((a, b) =>
    b.latest_result.score - a.latest_result.score ||
    (a.evidence_id < b.evidence_id ? -1 : a.evidence_id > b.evidence_id ? 1 : 0));
  assert.deepEqual(ids(baseline.items), ids(computedOrder), 'computed score descending, evidence ID tie-break');
  assert.equal(baseline.items[0].latest_result.score, baseline.items[1].latest_result.score,
    'network controls exercise the stable tie-break');
  const original = baseline.items.at(-1);
  const evidenceId = original.evidence_id;
  assert.equal(evidenceId, gps.id);
  assert.ok(original.latest_result.score < baseline.items[0].latest_result.score);
  assert.notEqual(original.latest_result.priority, 'P1', 'override must change the displayed priority');
  const history = await get('/evidence/{evidenceId}/triage-history', undefined, { evidenceId });
  assert.deepEqual(history, [original.latest_result]);

  async function checkPages(limit, firstPage) {
    const items = [];
    for (let offset = 0; offset < baseline.total; offset += limit) {
      const page = offset === 0 && firstPage ? firstPage : await get('/triage', { limit, offset });
      assert.equal(page.total, baseline.total);
      assert.equal(page.analysis_run_id, run.id);
      assert.equal(page.limit, limit);
      assert.equal(page.offset, offset);
      assert.equal(page.items.length, Math.min(limit, baseline.total - offset));
      assert.deepEqual(ids(page.items), ids(baseline.items.slice(offset, offset + limit)), 'stable page membership');
      items.push(...page.items);
    }
    assert.equal(new Set(ids(items)).size, baseline.total, 'no duplicate evidence across pages');
    assert.deepEqual(ids(items), ids(baseline.items), 'no skipped evidence or changed order across pages');
    assert.deepEqual(items.map(item => item.latest_result), baseline.items.map(item => item.latest_result),
      'all computed result fields survive pagination and overrides unchanged');
    const end = await get('/triage', { limit, offset: baseline.total });
    assert.equal(end.total, baseline.total);
    assert.deepEqual(end.items, [], 'page after the last record stays empty');
    return items;
  }
  for (const limit of [1, 2]) assert.deepEqual(await checkPages(limit), baseline.items);

  function assertAudit(page, action, targetId, decision) {
    assert.equal(page.items.length, page.total, 'complete audit page');
    const matches = page.items.filter(item => item.action === action && item.target_id === targetId);
    assert.equal(matches.length, 1, `one ${action} event for the exact target`);
    const [event] = matches;
    assert.equal(event.case_id, caseId);
    assert.equal(event.actor_id, 'investigator-2');
    assert.equal(event.reason, decision.reason);
    assert.equal(event.created_at, decision.created_at);
    assertTimestamp(event.created_at);
    return event;
  }
  const reviewPath = { findingId: finding.id };
  assert.deepEqual(await get('/findings/{findingId}/reviews', undefined, reviewPath), []);
  const review = await post('/findings/{findingId}/reviews', {
    path: reviewPath, body: { decision: 'accepted', reason: 'Verified manual finding review' },
  });
  assert.equal(review.case_id, caseId);
  assert.equal(review.finding_id, finding.id);
  assert.equal(review.actor_id, 'investigator-2');
  assert.equal(review.decision, 'accepted');
  assert.equal(review.reason, 'Verified manual finding review');
  assertTimestamp(review.created_at);
  assert.deepEqual(await get('/findings/{findingId}/reviews', undefined, reviewPath), [review],
    'persisted review preserves the decision, reason, actor and timestamp');
  const reviewAudit = assertAudit(await get('/audit-events', { limit: 100, offset: 0 }),
    'reviewFinding', finding.id, review);
  assert.deepEqual(await get('/triage', { limit: 100, offset: 0 }), baseline, 'review preserves computed triage');

  // Keep first pages fetched before the mutation, then continue each traversal
  // afterwards: a reordered P1 item would otherwise be skipped or duplicated.
  const firstPages = new Map();
  for (const limit of [1, 2]) firstPages.set(limit, await get('/triage', { limit, offset: 0 }));
  const override = await post('/evidence/{evidenceId}/priority-overrides', {
    path: { evidenceId },
    body: { priority: 'P1', reason: 'Escalated by supervisor for incident response' },
  });
  assert.equal(override.case_id, caseId);
  assert.equal(override.evidence_id, evidenceId);
  assert.equal(override.priority, 'P1');
  assert.equal(override.reason, 'Escalated by supervisor for incident response');
  assert.equal(override.actor_id, 'investigator-2');
  assertTimestamp(override.created_at);
  const after = await get('/triage', { limit: 100, offset: 0 });
  const expected = {
    ...baseline,
    items: baseline.items.map(item => item.evidence_id === evidenceId ?
      { ...item, effective_priority: 'P1', override } : item),
  };
  assert.deepEqual(after, expected, 'only the human overlay changes; every computed result stays identical');
  const item = after.items.find(entry => entry.evidence_id === evidenceId);
  assert.equal(item.effective_priority, 'P1');
  assert.deepEqual(item.override, override, 'read-back contains the exact reason, actor and timestamp');
  assert.equal(item.latest_result.score, original.latest_result.score, 'computed score is immutable');
  assert.equal(item.latest_result.priority, original.latest_result.priority, 'computed priority is immutable');
  assert.deepEqual(item.latest_result, original.latest_result, 'entire computed result is immutable');
  for (const limit of [1, 2]) {
    assert.deepEqual(await checkPages(limit, firstPages.get(limit)), expected.items, 'stable traversal during override');
    assert.deepEqual(await checkPages(limit), expected.items, 'stable traversal after override');
  }
  assert.deepEqual(await get('/triage', { analysis_run_id: run.id, limit: 100, offset: 0 }), expected,
    'a pinned run keeps computed results and receives the same human overlay');
  assert.deepEqual(await get('/evidence/{evidenceId}/triage-history', undefined, { evidenceId }), history,
    'override neither rewrites nor appends computed history');
  assert.deepEqual(await get('/findings'), findings, 'human decisions preserve generated findings');
  assert.deepEqual(await get('/findings/{findingId}/reviews', undefined, reviewPath), [review]);
  const audit = await get('/audit-events', { limit: 100, offset: 0 });
  assertAudit(audit, 'setPriorityOverride', evidenceId, override);
  assert.deepEqual(assertAudit(audit, 'reviewFinding', finding.id, review), reviewAudit,
    'override preserves the earlier review audit event');

  console.log('PASS I02B human review/override HTTP tracer: investigator-2 review and audit, P1 overlay and audit, immutable computed results/history, stable score sorting and pagination before/during/after override.');
  console.log('PASS Checkpoint 2B exit gate (explicit transactional Neo4j double).');
} finally {
  clearTimeout(startupTimer);
  try {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const forceKill = setTimeout(() => child.kill('SIGKILL'), 5000);
    try { await closed; } finally { clearTimeout(forceKill); }
  } finally {
    assert.ok(temporary.startsWith(join(tmpdir(), 'evora-i02b-')));
    await rm(temporary, { recursive: true, force: true });
  }
}
