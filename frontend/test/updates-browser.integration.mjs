// Actual encrypted restart and browser controls; release downloads use a local protocol double.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const root = fileURLToPath(new URL('../../', import.meta.url));
const scratch = await mkdtemp(join(tmpdir(), 'evora-updates-browser-'));
const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
const origin = `http://127.0.0.1:${port}`, headers = { 'X-Evora-Request': '1' };
const credentials = { username: 'updates-test', display_name: 'Update Tester', password: 'disposable browser restart passphrase' };
let child, browser, diagnostics = '';
async function start() {
  child = spawn(process.env.EVORA_TEST_PYTHON ?? 'python', [join(root, 'frontend/test/serve-updates.py'), scratch, String(port)], { cwd: root, env: { ...process.env, PYTHONPATH: root, EVORA_AUTO_UPDATE_CHECKS: '1' }, stdio: ['ignore', 'ignore', 'pipe'] });
  child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-4000); });
  for (let attempt = 0; ; attempt++) {
    try { if ((await fetch(origin + '/api/v1/auth/status')).ok) return; } catch {}
    assert.equal(child.exitCode, null, diagnostics); assert.ok(attempt < 200, diagnostics);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}
async function stop() {
  if (!child || child.exitCode !== null) return;
  const exited = new Promise(resolve => child.once('exit', resolve)); child.kill('SIGTERM'); await exited;
}
try {
  await start();
  browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 }, colorScheme: 'light' });
  assert.ok((await context.request.post(origin + '/api/v1/auth/setup', { headers, data: credentials })).ok());
  const page = await context.newPage(), errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin);
  await page.getByRole('button', { name: 'Update available', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Application updates' });
  await panel.getByText('Version 1.3.11', { exact: true }).waitFor();
  await panel.getByText('Version 9.0.0 available', { exact: true }).waitFor();
  await Promise.all([page.waitForResponse(response => response.url().endsWith('/api/v1/updates') && response.status() === 200), panel.getByRole('switch', { name: 'Check automatically' }).uncheck()]);
  assert.equal((await (await context.request.get(origin + '/api/v1/settings')).json()).automatic_update_checks, false);
  await panel.getByRole('button', { name: 'Download update', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.updates-progress progress')?.value > 0);
  await panel.getByRole('button', { name: 'Cancel download' }).click();
  await panel.getByRole('button', { name: 'Resume download' }).click();
  await panel.getByRole('button', { name: 'Install update', exact: true }).waitFor({ timeout: 20000 });
  await page.screenshot({ path: join(scratch, 'updates-desktop.png') });
  await panel.getByRole('button', { name: 'Install update', exact: true }).click();
  await panel.getByText('Finish setup in the installer.').waitFor();
  const events = await (await context.request.get(origin + '/test/update-events')).json();
  assert.equal(events.installs, 1); assert.ok(events.downloads.some(start => start > 0), JSON.stringify(events));
  assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), 'rgb(244, 246, 248)');
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: join(scratch, 'updates-mobile.png') });
  assert.ok((await context.request.put(origin + '/api/v1/settings', { headers, data: { offline_mode: false, qa_provider: 'chatgpt', qa_model: 'saved-vision-model', vision_use_qa_model: true } })).ok());
  await stop(); await start();
  assert.ok((await context.request.post(origin + '/api/v1/auth/login', { headers, data: { username: credentials.username, password: credentials.password } })).ok());
  await page.setViewportSize({ width: 1400, height: 1000 }); await page.goto(origin);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  assert.equal(await page.getByRole('switch', { name: 'Local models only' }).isChecked(), false);
  const saved = await (await context.request.get(origin + '/api/v1/settings')).json();
  assert.equal(saved.qa_model, 'saved-vision-model'); assert.equal(saved.qa_provider, 'chatgpt');
  await page.getByRole('button', { name: 'Updates', exact: true }).click();
  await panel.getByRole('switch', { name: 'Check automatically' }).waitFor();
  assert.equal(await panel.getByRole('switch', { name: 'Check automatically' }).isChecked(), false);
  assert.equal((await (await context.request.get(origin + '/test/update-events')).json()).checks, 0);
  await panel.getByRole('button', { name: 'Check for updates', exact: true }).click();
  await panel.getByText('Version 9.0.0 available', { exact: true }).waitFor();
  assert.equal((await (await context.request.get(origin + '/test/update-events')).json()).checks, 1);
  assert.deepEqual(errors, []);
  console.log('PASS verified update controls, cancel/resume, installer launch, neutral light canvas, mobile layout and encrypted settings restart. Screenshots:', scratch);
} finally { await browser?.close(); await stop(); }
