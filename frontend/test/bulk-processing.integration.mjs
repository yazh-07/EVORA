import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const frontend = fileURLToPath(new URL('..', import.meta.url));
execFileSync(process.execPath, ['scripts/build-test.mjs'], { cwd: frontend, stdio: 'inherit' });
const { createApiClient } = await import('../.test-build/src/api/client.mjs');
const { createBulkProcessingController } = await import('../.test-build/src/cases/CaseWorkspace.mjs');
const temporary = await mkdtemp(join(tmpdir(), 'evora-bulk-'));
const server = spawn(process.env.EVORA_TEST_PYTHON ?? 'python', ['test/serve-cases.py', '--api-only', '--database', join(temporary, 'case.sqlite3')], { cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'] });
let diagnostics = '', controller;
server.stderr.on('data', chunk => { diagnostics = (diagnostics + chunk).slice(-8000); });
const closed = new Promise(resolve => server.once('close', resolve));
const ready = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(Error(`Server startup timed out: ${diagnostics}`)), 20000);
  let output = '';
  server.stdout.on('data', chunk => { output += chunk; const match = output.match(/U02_URL=(http:\/\/127\.0\.0\.1:\d+)/); if (match) { clearTimeout(timer); resolve(match[1]); } });
  server.once('error', error => { clearTimeout(timer); reject(error); });
  server.once('exit', code => { clearTimeout(timer); reject(Error(`Server exited ${code}: ${diagnostics}`)); });
});
try {
  const origin = await ready;
  const client = createApiClient({ baseUrl: origin }); client.setToken('u02-synthetic-two');
  for (let i = 0; ; i++) {
    try { await client.request('get', '/api/v1/cases', { query: { offset: 0, limit: 20 } }); break; }
    catch (error) { if (i > 50) throw error; await new Promise(resolve => setTimeout(resolve, 100)); }
  }
  const caseRecord = await client.request('post', '/api/v1/cases', { body: { title: 'Synthetic bulk processing regression' } });
  const caseId = caseRecord.id, sources = [];
  async function upload(name, kind, bytes, media = 'text/plain') {
    const body = new FormData(); body.set('file', new File([bytes], name, { type: media })); body.set('kind', kind); body.set('source_label', name);
    const evidence = await client.request('post', '/api/v1/cases/{caseId}/evidence', { path: { caseId }, body });
    assert.equal(evidence.sha256, createHash('sha256').update(bytes).digest('hex')); sources.push({ evidence, bytes });
  }
  for (let i = 0; i < 101; i++) await upload(`note-${i}.txt`, 'document', Buffer.from(`Synthetic source ${i}.\nReview the original before drawing conclusions.\n`));
  await upload('network.csv', 'network_log', Buffer.from('timestamp,device_id,ip_address,event\n2026-11-05T09:00:00Z,D-101,203.0.113.44,connected\n'), 'text/csv');
  await upload('bad.csv', 'network_log', Buffer.from('timestamp,device_id,ip_address,event\n2026-11-05T09:00:00Z,D-777,not-an-ip,connected\n'), 'text/csv');
  await upload('invalid.png', 'image', Buffer.from('This is intentionally not image bytes.'), 'application/octet-stream');
  await upload('audio.wav', 'audio', Buffer.from('Synthetic storage-only audio control.'), 'audio/wav');
  controller = createBulkProcessingController(client, caseId, 5); controller.start();
  await controller.submit();
  const state = controller.getSnapshot(); assert.equal(state.status, 'done', diagnostics);
  assert.equal(state.items.length, sources.length);
  const histories = new Map();
  for (const { evidence, bytes } of sources) {
    const item = state.items.find(item => item.evidence.id === evidence.id); assert.ok(item);
    assert.equal(item.evidence.case_id, caseId);
    const history = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId: evidence.id } });
    histories.set(evidence.id, history.map(run => run.id));
    if (evidence.kind === 'audio') { assert.equal(item.status, 'skipped'); assert.equal(history.length, 0); }
    else if (evidence.filename === 'invalid.png') { assert.equal(item.status, 'failed'); assert.equal(history.length, 0); }
    else if (evidence.filename === 'bad.csv') { assert.equal(item.status, 'failed'); assert.ok(history.every(run => run.status === 'failed')); }
    else {
      assert.equal(item.status, 'completed', `${evidence.filename}: ${item.message}`);
      assert.equal(history.length, 1); assert.equal(history[0].status, 'completed');
      const output = await client.request('get', '/api/v1/cases/{caseId}/observations', { path: { caseId }, query: { evidence_id: evidence.id, processing_run_id: item.run.id, limit: 100, offset: 0 } });
      assert.ok(output.items.length > 0);
      for (const observation of output.items) {
        assert.equal(observation.case_id, caseId); assert.equal(observation.evidence_id, evidence.id); assert.equal(observation.processing_run_id, item.run.id);
      }
    }
    const metadata = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}', { path: { caseId, evidenceId: evidence.id } });
    assert.equal(metadata.sha256, createHash('sha256').update(bytes).digest('hex'));
  }
  await controller.submit();
  for (const { evidence } of sources.filter(source => !['bad.csv', 'invalid.png'].includes(source.evidence.filename))) {
    const history = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', { path: { caseId, evidenceId: evidence.id } });
    assert.deepEqual(history.map(run => run.id), histories.get(evidence.id), 'repeat batch must not duplicate completed runs');
  }
  console.log('PASS bulk processing: 105 originals across two API pages, real extraction and source lineage, malformed-input isolation, audio skip, preserved hashes and no duplicate completed runs.');
} finally {
  controller?.dispose(); server.kill('SIGTERM'); await closed; await rm(temporary, { recursive: true, force: true });
}
