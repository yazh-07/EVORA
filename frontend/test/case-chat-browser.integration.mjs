// Real authorized case/processing/Q&A routes with a local model-protocol double.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const root = fileURLToPath(new URL('../../', import.meta.url)), scratch = await mkdtemp(join(tmpdir(), 'evora-case-chat-'));
const calls = []; let delay = false;
const provider = createServer(async (request, response) => {
  const chunks = []; for await (const chunk of request) chunks.push(chunk);
  assert.equal(request.url, '/v1/chat/completions');
  const body = JSON.parse(Buffer.concat(chunks)); calls.push(body);
  const payload = JSON.parse(body.messages[1].content), verifying = body.messages[0].content.startsWith('Independently check');
  let result = { supported: true };
  if (!verifying) {
    const followUp = payload.question.includes('disconnect');
    if (followUp) assert.equal(payload.conversation.at(-1).question, 'What records mention D-7?');
    const observation = payload.context.observations.find(item => item.value.includes(followUp ? 'disconnected' : 'connected at'));
    assert.ok(observation);
    result = { supported: true, claims: [{ text: followUp ? 'Device D-7 disconnected at 10:00.' : 'Device D-7 connected at 09:00.', observation_ids: [observation.id] }] };
    if (delay) await new Promise(resolve => setTimeout(resolve, 800));
  }
  if (!response.destroyed) { response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({ model: 'chat-fixture', choices: [{ finish_reason: 'stop', message: { content: JSON.stringify(result) } }] })); }
});
await new Promise(resolve => provider.listen(0, '127.0.0.1', resolve));
const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve)); const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
const child = spawn(process.env.EVORA_TEST_PYTHON ?? 'python', ['-m', 'backend.run', '--database', join(scratch, 'case.sqlite'), '--storage', join(scratch, 'evidence'), '--port', String(port)], { cwd: root, env: { ...process.env, EVORA_AUTO_UPDATE_CHECKS: '0' }, stdio: ['ignore', 'ignore', 'pipe'] });
let diagnostics = '', browser, page; child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-4000); });
const origin = `http://127.0.0.1:${port}`, headers = { 'X-Evora-Request': '1' };
try {
  for (let i = 0; ; i++) { try { if ((await fetch(origin + '/api/v1/auth/status')).ok) break; } catch {} assert.equal(child.exitCode, null, diagnostics); assert.ok(i < 200, diagnostics); await new Promise(resolve => setTimeout(resolve, 100)); }
  browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  assert.ok((await context.request.post(origin + '/api/v1/auth/setup', { headers, data: { username: 'chat-test', display_name: 'Chat Tester', password: 'disposable chat test passphrase' } })).ok());
  assert.ok((await context.request.put(origin + '/api/v1/settings', { headers, data: { offline_mode: false, qa_provider: 'openai', openai_base_url: `http://127.0.0.1:${provider.address().port}/v1`, openai_api_key: 'synthetic-key', qa_model: 'chat-fixture' } })).ok());
  const record = await (await context.request.post(origin + '/api/v1/cases', { headers, data: { title: 'Case chat acceptance' } })).json();
  const source = await (await context.request.post(`${origin}/api/v1/cases/${record.id}/evidence`, { headers, multipart: { kind: 'document', source_label: 'Connection notes', file: { name: 'connections.txt', mimeType: 'text/plain', buffer: Buffer.from('Device D-7 connected at 09:00.\nDevice D-7 disconnected at 10:00.\n') } } })).json();
  const base = `${origin}/api/v1/cases/${record.id}/evidence/${source.id}/processing-runs`;
  const run = await (await context.request.post(base, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() } })).json();
  for (let i = 0; ; i++) { const status = await (await context.request.get(base + '/' + run.id)).json(); if (status.status === 'completed') break; assert.notEqual(status.status, 'failed', JSON.stringify(status)); assert.ok(i < 200); await new Promise(resolve => setTimeout(resolve, 100)); }
  page = await context.newPage(); const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem('evora-appearance', JSON.stringify({ version: 1, mode: 'light', accent: '#2859b8' })));
  await page.goto(origin); await page.getByRole('button', { name: 'Open case Case chat acceptance', exact: true }).click();
  await page.getByRole('tab', { name: 'Findings', exact: true }).click(); await page.getByRole('button', { name: 'Ask', exact: true }).click();
  const input = page.getByRole('textbox', { name: 'Message about this case', exact: true });
  await input.fill('What records mention D-7?'); await input.press('Enter');
  await page.locator('.chat-answer .answer-markdown').getByText('Device D-7 connected at 09:00.', { exact: true }).waitFor(); assert.equal(await input.inputValue(), '');
  await input.fill('When did it disconnect?'); await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await page.locator('.chat-answer .answer-markdown').getByText('Device D-7 disconnected at 10:00.', { exact: true }).waitFor();
  assert.equal(await page.locator('.question-result').count(), 2); assert.equal(calls.length, 4);
  const references=page.getByRole('region',{name:'References'}).last();
  await references.getByRole('button',{name:'connections.txt',exact:true}).first().waitFor();
  assert.ok(await references.getByText(/Used/).count());
  await page.locator('.chat-sources > summary').last().click(); await page.locator('.chat-sources').last().getByRole('button', { name: 'Open source 1', exact: true }).click();
  await page.getByRole('heading', { name: 'Connection notes', exact: true }).waitFor();
  await page.getByRole('tab', { name: 'Findings', exact: true }).click(); await page.getByRole('button', { name: 'Ask', exact: true }).click();
  assert.equal(await page.locator('.question-result').count(), 2, 'Inspecting sources retains the conversation');
  await page.screenshot({ path: join(scratch, 'chat-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  const composer = await page.locator('.chat-composer').boundingBox(); assert.ok(composer.height > 50 && composer.y >= 0 && composer.y + composer.height <= 844, JSON.stringify(composer));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: join(scratch, 'chat-mobile.png') });
  await page.getByRole('button', { name: 'New chat', exact: true }).click(); assert.equal(await page.locator('.question-result').count(), 0);
  await input.fill('A line'); await input.press('Shift+Enter'); await input.press('KeyB'); assert.equal(await input.inputValue(), 'A line\nb'); assert.equal(calls.length, 4);
  delay = true; await input.fill('What records mention D-7?'); await input.press('Enter');
  for (let i=0; i<100 && calls.length<5; i++) await new Promise(resolve=>setTimeout(resolve,10));
  assert.ok(calls.length>=5);
  await page.getByRole('button', { name: 'Stop response', exact: true }).click(); await page.waitForTimeout(1100);
  assert.equal(await page.locator('.question-result').count(), 0, 'Stopped replies cannot appear later');
  assert.equal(await input.inputValue(), 'What records mention D-7?'); assert.deepEqual(errors, []);
  console.log('PASS real case chat, Enter/Shift+Enter, follow-up context, source inspection, new chat, stop/late delivery and desktop/mobile composer. Screenshots:', scratch);
} catch (error) { if (page) await page.screenshot({ path: join(scratch, 'failure.png') }); console.error('Artifacts:', scratch); throw error; }
finally { await browser?.close(); child.kill('SIGTERM'); provider.closeAllConnections(); await new Promise(resolve => provider.close(resolve)); }
