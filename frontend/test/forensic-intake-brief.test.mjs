import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { detectEvidenceKind, createExecutiveBriefController, ExecutiveBriefPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';

test('intake recognizes every requested extension and MIME families', () => {
  const kinds = { video: 'mp4 webm mov avi mkv', image: 'png jpg jpeg webp bmp', audio: 'wav mp3 m4a ogg flac', document: 'pdf docx' };
  for (const [kind, extensions] of Object.entries(kinds)) for (const extension of extensions.split(' ')) {
    let detected, settled = false;
    detectEvidenceKind(new File([''], `source.${extension.toUpperCase()}`), value => { detected = value; }, () => { settled = true; });
    assert.equal(detected, kind); assert.equal(settled, true);
  }
  for (const kind of ['image', 'audio', 'video']) {
    let detected;
    detectEvidenceKind(new File([''], 'unknown', { type: `${kind}/example` }), value => { detected = value; }, () => {});
    assert.equal(detected, kind);
  }
});

test('intake reads only the first KB and header, handles errors, and discards canceled results', async t => {
  const readers = [];
  const original = Object.getOwnPropertyDescriptor(globalThis, 'FileReader');
  t.after(() => { if (original) Object.defineProperty(globalThis, 'FileReader', original); else delete globalThis.FileReader; });
  globalThis.FileReader = class {
    readyState = 1;
    constructor() { readers.push(this); }
    readAsText(blob) { this.blob = blob; }
    abort() { this.aborted = true; this.onloadend?.(); }
    async finish() { this.result = await this.blob.text(); this.onload?.(); this.onloadend?.(); }
  };
  for (const [header, kind] of [['timestamp,lat,longitude', 'gps'], ['ip_address,packet', 'network_log'],
    ['amount,currency,account_id', 'transaction'], ['sender,recipient,message_id,body', 'message'],
    ['notes\nlatitude,ip,amount', 'document']]) {
    let detected, settled = false;
    detectEvidenceKind(new File([header.toUpperCase(), '\n', 'x'.repeat(2000)], 'source.csv', { type: 'text/csv' }),
      value => { detected = value; }, () => { settled = true; });
    const reader = readers.at(-1);
    assert.equal(reader.blob.size, 1024);
    await reader.finish();
    assert.equal(detected, kind); assert.equal(settled, true);
  }
  let detected, settled = false;
  const cancel = detectEvidenceKind(new File(['ip_address'], 'source.txt'), value => { detected = value; }, () => { settled = true; });
  cancel(); await readers.at(-1).finish();
  assert.equal(detected, 'document'); assert.equal(settled, false); assert.equal(readers.at(-1).aborted, true);
  detectEvidenceKind(new File(['amount'], 'unknown', { type: 'text/plain' }), value => { detected = value; }, () => { settled = true; });
  readers.at(-1).onloadend();
  assert.equal(detected, 'document'); assert.equal(settled, true);
});

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const finding = (n, kind = 'relationship') => ({ id: id(n), case_id: id(1), analysis_run_id: id(2), kind,
  summary: kind === 'hypothesis' ? 'AI Forensic Executive Brief: Review the timeline.' : 'Device link',
  rule: 'synthetic', confidence: 0, evidence_ids: [id(3)], observation_ids: [id(4)],
  ...(kind === 'hypothesis' ? { details: { hypothesis: '<script>untrusted</script>', ai_generated: true, model: 'test-model' } } : {}) });
const until = async predicate => {
  for (let i = 0; i < 100; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 1)); }
  assert.fail('Controller did not settle');
};

test('overview finds a brief on later pages, pins every request, and clears it on session change', async () => {
  const items = [...Array.from({ length: 100 }, (_, i) => finding(100 + i)), finding(300, 'hypothesis')];
  const requests = [];
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async url => {
    requests.push(url);
    const offset = Number(url.searchParams.get('offset'));
    return Response.json({ items: items.slice(offset, offset + 100), total: items.length, limit: 100, offset, analysis_run_id: id(2) });
  } });
  client.setToken('synthetic');
  const controller = createExecutiveBriefController(client, id(1), id(2));
  try {
    controller.start();
    await until(() => controller.getSnapshot().status === 'ready');
    assert.deepEqual(requests.map(url => url.searchParams.get('offset')), ['0', '100']);
    assert.ok(requests.every(url => url.searchParams.get('analysis_run_id') === id(2)));
    assert.deepEqual(controller.getSnapshot().findings, [items.at(-1)]);
    const html = renderToStaticMarkup(createElement(ExecutiveBriefPanel, { findings: controller.getSnapshot().findings }));
    assert.match(html, /AI Forensic Executive Brief/); assert.match(html, /Review the timeline/);
    assert.match(html, /&lt;script&gt;untrusted/); assert.doesNotMatch(html, /<script>/);
    client.clearToken();
    assert.equal(controller.getSnapshot().status, 'error');
    assert.deepEqual(controller.getSnapshot().findings, []);
  } finally { controller.dispose(); }
});

test('overview retains deterministic hypothesis summaries and omits cards without hypotheses', () => {
  const fallback = { ...finding(300, 'hypothesis'), details: undefined, summary: 'Competing reports require review.' };
  const html = renderToStaticMarkup(createElement(ExecutiveBriefPanel, { findings: [fallback] }));
  assert.match(html, /Deterministic hypotheses/); assert.match(html, /Competing reports/);
  assert.equal(renderToStaticMarkup(createElement(ExecutiveBriefPanel, { findings: [finding(300)] })), '');
});
