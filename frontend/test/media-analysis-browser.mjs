// Real browser/API/SQLite processing with an explicit local vision-protocol double.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export async function checkMediaAnalysis(kind) {
  const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const scratch = await mkdtemp(join(tmpdir(), `evora-${kind}-browser-`));
  const python = process.env.EVORA_TEST_PYTHON ?? 'python';
  let fixture = join(root, 'fixtures/media/astronaut.png');
  if (kind === 'video') {
    const raw = join(scratch, 'clip.avi'); fixture = join(scratch, 'clip.mp4');
    const generated = spawnSync(python, ['-c', 'from pathlib import Path; import sys; from backend.tests.test_media_detection import video_bytes; Path(sys.argv[1]).write_bytes(video_bytes())', raw], { cwd: root });
    assert.equal(generated.status, 0, generated.stderr.toString());
    const encoded = spawnSync('ffmpeg', ['-nostdin', '-v', 'error', '-i', raw, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', fixture]);
    assert.equal(encoded.status, 0, encoded.stderr.toString());
  }
  const calls = []; let fail = false;
  const description = `Synthetic ${kind} description from supplied pixels.`;
  const visibleText = 'TEST REFERENCE 42';
  const provider = createServer(async (request, response) => {
    const chunks = []; for await (const chunk of request) chunks.push(chunk);
    if (request.url !== '/v1/chat/completions') { response.writeHead(404).end(); return; }
    const body = JSON.parse(Buffer.concat(chunks).toString()); calls.push(body);
    assert.ok(body.messages[1].content[1].image_url.url.startsWith('data:image/png;base64,'));
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ model: 'vision-double', choices: [{ finish_reason: fail ? 'length' : 'stop', message: {
      content: JSON.stringify({ description, visible_text: visibleText, limitations: ['Synthetic protocol fixture.'] }),
    } }] }));
  });
  await new Promise(resolve => provider.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${provider.address().port}/v1`;
  const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
  const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
  const child = spawn(python, ['-m', 'backend.run', '--database', join(scratch, 'case.sqlite'), '--storage', join(scratch, 'evidence'), '--port', String(port)], { cwd: root, env: { ...process.env, EVORA_AUTO_UPDATE_CHECKS: '0' }, stdio: ['ignore', 'ignore', 'pipe'] });
  let diagnostics = ''; child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-4000); });
  const origin = `http://127.0.0.1:${port}`;
  let browser, page;
  try {
    for (let index = 0; ; index++) {
      try { if ((await fetch(origin + '/api/v1/auth/status')).ok) break; } catch {}
      assert.equal(child.exitCode, null, diagnostics); assert.ok(index < 150, diagnostics);
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
    const headers = { 'X-Evora-Request': '1' };
    assert.ok((await context.request.post(origin + '/api/v1/auth/setup', { headers, data: {
      username: 'media-test', display_name: 'Media Tester', password: 'disposable media test passphrase',
    } })).ok());
    assert.ok((await context.request.put(origin + '/api/v1/settings', { headers, data: {
      offline_mode: false, qa_provider: 'openai', openai_base_url: endpoint, openai_api_key: 'synthetic-key',
      qa_model: 'vision-double', vision_use_qa_model: true, vision_model: '',
    } })).ok());
    const title = `${kind} processing acceptance`;
    const caseResponse = await context.request.post(origin + '/api/v1/cases', { headers, data: { title } });
    assert.ok(caseResponse.ok()); const caseId = (await caseResponse.json()).id;
    const filename = kind === 'image' ? 'astronaut.png' : 'clip.mp4';
    const upload = await context.request.post(`${origin}/api/v1/cases/${caseId}/evidence`, { headers, multipart: {
      kind, source_label: filename, file: { name: filename, mimeType: kind === 'image' ? 'image/png' : 'video/mp4', buffer: await readFile(fixture) },
    } });
    assert.ok(upload.ok(), await upload.text()); const evidenceId = (await upload.json()).id;
    const base = `${origin}/api/v1/cases/${caseId}/evidence/${evidenceId}`;
    page = await context.newPage(); const errors = []; page.on('pageerror', error => errors.push(error.message));
    const openCase = async () => {
      await page.getByRole('button', { name: `Open case ${title}`, exact: true }).click();
      await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
    };
    await page.goto(origin); await openCase();
    const batch = page.locator('.batch-toolbar');
    await batch.getByText('vision-double', { exact: true }).waitFor();
    assert.equal(await batch.getByLabel('Analyze images and video', { exact: true }).isChecked(), true);
    const processButton = batch.getByRole('button', { name: 'Process 1', exact: true });
    assert.equal(await processButton.isDisabled(), true); assert.equal(calls.length, 0);
    await batch.getByRole('checkbox', { name: /^Send images and sampled frames/ }).check();
    await processButton.click();
    await batch.getByText('1 ready', { exact: true }).waitFor();
    assert.ok(calls.length > 0, 'The main Process action must request pixel analysis');
    assert.ok(calls.every(body => body.model === 'vision-double'));
    await page.getByRole('button', { name: filename, exact: true }).click();
    const results = page.getByRole('region', { name: 'Extraction results', exact: true });
    await results.getByText(description, { exact: true }).first().waitFor();
    const first = await (await context.request.get(base + '/results')).json();
    assert.equal(first.operation, 'description'); assert.ok(first.total > 0);
    assert.equal(await results.getByRole('button', { name: /^Scene descriptions/ }).getAttribute('aria-pressed'), 'true');
    await results.getByRole('button', { name: /^Visible text/ }).click();
    await results.getByText(visibleText, { exact: true }).first().waitFor();
    // Following a current result into its original must not strand later processing on an old output.
    await results.locator('.extracted-result-list > li button').first().click();
    await page.locator(kind === 'image' ? '.media-viewer img' : '.media-viewer video').waitFor();
    if (kind === 'video') await page.waitForFunction(() => document.querySelector('video')?.readyState >= 1);
    await page.getByRole('button', { name: 'Results', exact: true }).click();
    await results.getByText(`Reanalyze ${kind}`, { exact: true }).click();
    const analysis = results.getByRole('region', { name: kind === 'image' ? 'Image description and OCR' : 'Video scene analysis', exact: true });
    const analyze = analysis.getByRole('button', { name: kind === 'image' ? 'Analyze image' : 'Analyze video', exact: true });
    assert.equal(await analyze.isDisabled(), true, 'Batch consent must not authorize a new individual request');
    await analysis.getByRole('checkbox', { name: /^Send/ }).check();
    fail = true; const beforeFailure = calls.length; await analyze.click();
    await results.getByRole('alert').filter({ hasText: 'Showing saved results.' }).waitFor();
    assert.equal(calls.length, beforeFailure + 1);
    await results.getByText(`Reanalyze ${kind}`, { exact: true }).click();
    await analysis.getByText('Processing failed', { exact: true }).waitFor();
    assert.equal(await analyze.isDisabled(), false, 'A failed attempt must release its action');
    await results.getByText(visibleText, { exact: true }).first().waitFor();
    await results.getByText(`Reanalyze ${kind}`, { exact: true }).click();
    await page.screenshot({ path: join(scratch, 'results.png'), fullPage: true });
    await page.reload(); await openCase(); await page.getByRole('button', { name: filename, exact: true }).click();
    await page.getByRole('region', { name: 'Extraction results', exact: true }).getByText(description, { exact: true }).first().waitFor();
    assert.equal(calls.length, beforeFailure + 1, 'Reload must not transmit media');
    if (kind === 'image') {
      // A new batch and every failed-batch retry need their own hosted consent.
      const retryBatch = page.locator('.batch-toolbar');
      await retryBatch.locator('.batch-options > summary').click();
      await retryBatch.getByLabel('Reprocess completed files', { exact: true }).check();
      await retryBatch.locator('.batch-options > summary').click();
      await retryBatch.getByRole('checkbox', { name: /^Send images and sampled frames/ }).waitFor();
      assert.equal(await retryBatch.getByRole('checkbox', { name: /^Send images and sampled frames/ }).isChecked(), false);
      assert.equal(await retryBatch.getByRole('button', { name: 'Process 1', exact: true }).isDisabled(), true);
      await retryBatch.getByRole('checkbox', { name: /^Send images and sampled frames/ }).check();
      await retryBatch.getByRole('button', { name: 'Process 1', exact: true }).click();
      await retryBatch.getByText('0 ready · 1 failed', { exact: true }).waitFor();
      await retryBatch.locator('.batch-options > summary').click();
      await retryBatch.getByLabel('Reprocess completed files', { exact: true }).uncheck();
      await retryBatch.locator('.batch-options > summary').click();
      const retry = retryBatch.getByRole('button', { name: 'Retry failed', exact: true });
      assert.equal(await retry.isDisabled(), true);
      await retryBatch.getByRole('checkbox', { name: /^Send images and sampled frames/ }).check();
      const beforeRetry = calls.length; await retry.click();
      await retryBatch.getByText('0 ready · 1 failed', { exact: true }).waitFor();
      assert.equal(calls.length, beforeRetry + 1);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: join(scratch, 'mobile.png'), fullPage: true });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    console.log(`PASS ${kind}: default batch pixel analysis, explicit consent, populated results, OCR, failed-run recovery, persisted results and mobile layout. Artifacts: ${scratch}`);
  } catch (error) {
    if (page) await page.screenshot({ path: join(scratch, 'failure.png'), fullPage: true });
    console.error(`Artifacts: ${scratch}`); throw error;
  } finally {
    await browser?.close(); child.kill('SIGTERM'); provider.closeAllConnections(); await new Promise(resolve => provider.close(resolve));
  }
}
