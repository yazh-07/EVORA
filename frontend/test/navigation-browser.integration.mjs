// Real case data and saving; model lists and ChatGPT status are explicit protocol fixtures.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const root = fileURLToPath(new URL('../../', import.meta.url));
const scratch = await mkdtemp(join(tmpdir(), 'evora-navigation-browser-'));
const probe = createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
const origin = `http://127.0.0.1:${port}`, headers = { 'X-Evora-Request': '1' };
const child = spawn(process.env.EVORA_TEST_PYTHON ?? 'python', ['-m', 'backend.run', '--database', join(scratch, 'case.sqlite'), '--storage', join(scratch, 'evidence'), '--port', String(port)], { cwd: root, env: { ...process.env, EVORA_AUTO_UPDATE_CHECKS: '0' }, stdio: ['ignore', 'ignore', 'pipe'] });
let diagnostics = '', browser; child.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-4000); });
const frame = locator => locator.evaluate(element => { const r = element.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; });
const equalFrame = (actual, expected, label) => { for (const key of ['x', 'y', 'width', 'height']) assert.ok(Math.abs(actual[key] - expected[key]) < 1, `${label} ${key}: ${actual[key]} ≠ ${expected[key]}`); };
try {
  for (let attempt = 0; ; attempt++) {
    try { if ((await fetch(origin + '/api/v1/auth/status')).ok) break; } catch {}
    assert.equal(child.exitCode, null, diagnostics); assert.ok(attempt < 200, diagnostics);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox', '--disable-features=OverlayScrollbar'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
  assert.ok((await context.request.post(origin + '/api/v1/auth/setup', { headers, data: { username: 'navigation-test', display_name: 'Navigation Tester', password: 'disposable navigation test passphrase' } })).ok());
  const response = await context.request.post(origin + '/api/v1/cases', { headers, data: { title: 'Navigation acceptance' } }); assert.ok(response.ok());
  const record = await response.json();
  for (let index = 0; index < 20; index++) {
    const upload = await context.request.post(`${origin}/api/v1/cases/${record.id}/evidence`, { headers, multipart: { kind: 'document', source_label: `Source ${index + 1}`, file: { name: `note-${index}.txt`, mimeType: 'text/plain', buffer: Buffer.from(`Synthetic navigation fixture ${index}.`) } } });
    assert.ok(upload.ok());
  }
  const page = await context.newPage(), errors = []; page.on('pageerror', error => errors.push(error.message));
  // Use the real authenticated response header even for protocol fixtures.
  const me = await (await context.request.get(origin + '/api/v1/auth/me')).json();
  await page.route('**/api/v1/settings/models', route => route.fulfill({ json: { models: ['fixture-chat', 'fixture-vision'], vision_models: ['fixture-vision'] }, headers: { 'X-Evora-User': me.user.id } }));
  await page.route('**/api/v1/chatgpt/status', route => route.fulfill({ json: { connected: true, sharing: true, email: 'fixture@example.test', pending: false, error: '' }, headers: { 'X-Evora-User': me.user.id } }));
  await page.goto(origin);
  await page.getByRole('button', { name: 'Open case Navigation acceptance', exact: true }).click();
  await page.locator('.overview-stats').waitFor();
  await page.waitForTimeout(300);
  const nav = page.getByRole('complementary', { name: 'Case tools' }), header = page.locator('.case-header'), content = page.locator('.investigation-content');
  const navFrame = await frame(nav), headerFrame = await frame(header), contentFrame = await frame(content);
  const tab = name => page.getByRole('tab', { name, exact: true });
  await tab('Evidence').click();
  await page.locator('.evidence-table tbody tr').nth(19).waitFor();
  const evidence = page.locator('#panel-evidence');
  const scroll = await evidence.evaluate(element => { element.scrollTop = 480; return element.scrollTop; });
  assert.ok(scroll > 100, `Evidence must have a real scroll range: ${scroll}`);
  for (const name of ['Timeline', 'Locations', 'Findings', 'Report', 'Overview', 'Evidence']) {
    await tab(name).click();
    assert.equal(await tab(name).getAttribute('aria-selected'), 'true');
    equalFrame(await frame(nav), navFrame, 'Sidebar'); equalFrame(await frame(header), headerFrame, 'Case header'); equalFrame(await frame(content), contentFrame, 'Content');
    assert.equal(await page.evaluate(() => scrollY), 0);
  }
  assert.ok(Math.abs(await evidence.evaluate(element => element.scrollTop) - scroll) < 1, 'Evidence scroll must survive other views');
  await tab('Evidence').press('ArrowDown'); await tab('Timeline').waitFor({ state: 'visible' });
  assert.equal(await tab('Timeline').getAttribute('aria-selected'), 'true');
  await tab('Timeline').press('ArrowUp');
  assert.ok(Math.abs(await evidence.evaluate(element => element.scrollTop) - scroll) < 1);
  // Rapid switches must not leave a delayed window-scroll callback behind.
  await page.evaluate(() => { for (let i = 0; i < 8; i++) { document.querySelector('#tab-timeline').click(); document.querySelector('#tab-evidence').click(); } });
  await page.waitForTimeout(250); equalFrame(await frame(nav), navFrame, 'Rapid navigation');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Settings' }); await page.waitForTimeout(250);
  const modalFrame = await frame(dialog), sections = dialog.getByRole('navigation', { name: 'Settings sections' }), sectionsFrame = await frame(sections);
  for (const section of ['Models', 'Viewer', 'Updates', 'Appearance', 'Models']) {
    await sections.getByRole('button', { name: section, exact: true }).click();
    equalFrame(await frame(dialog), modalFrame, 'Settings'); equalFrame(await frame(sections), sectionsFrame, 'Settings sections');
  }
  assert.equal(await dialog.getByLabel('Ollama URL', { exact: true }).isVisible(), false);
  await dialog.getByText('Connection options', { exact: true }).click();
  await dialog.getByLabel('Ollama URL', { exact: true }).waitFor();
  await dialog.getByRole('switch', { name: 'Local models only' }).uncheck();
  await dialog.getByLabel('Provider', { exact: true }).selectOption('openai');
  await dialog.getByLabel('API key', { exact: true }).fill('synthetic-navigation-key');
  await dialog.getByLabel('Model', { exact: true }).fill('fixture-chat');
  await dialog.getByRole('button', { name: 'Test connection', exact: true }).click();
  await dialog.getByRole('status').filter({ hasText: 'Connected' }).waitFor();
  await dialog.getByLabel('Model list', { exact: true }).selectOption('vision');
  await dialog.getByRole('button', { name: 'Use fixture-vision for images', exact: true }).click();
  await dialog.getByRole('button', { name: 'Save', exact: true }).click();
  await dialog.waitFor({ state: 'hidden' }); equalFrame(await frame(nav), navFrame, 'After settings');
  const saved = await (await context.request.get(origin + '/api/v1/settings')).json();
  assert.equal(saved.qa_model, 'fixture-chat'); assert.equal(saved.vision_model, 'fixture-vision'); assert.equal(saved.vision_use_qa_model, false);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await sections.getByRole('button', { name: 'Models', exact: true }).click();
  await dialog.getByLabel('Provider', { exact: true }).selectOption('chatgpt');
  await dialog.getByText('fixture@example.test · Connected', { exact: true }).waitFor();
  assert.equal(await dialog.getByRole('button', { name: 'Continue with ChatGPT', exact: true }).count(), 0);
  assert.equal(await dialog.getByRole('button', { name: 'Switch account', exact: true }).isVisible(), false);
  await dialog.getByText('Account options', { exact: true }).click();
  await dialog.getByRole('button', { name: 'Disconnect', exact: true }).waitFor();
  await sections.getByRole('button', { name: 'Appearance', exact: true }).click();
  await dialog.getByRole('button', { name: 'Blue', exact: true }).click();
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(scratch, 'settings-desktop.png') });
  await dialog.getByRole('button', { name: 'Apply', exact: true }).click(); await dialog.waitFor({ state: 'hidden' });
  await tab('Evidence').click(); await page.screenshot({ path: join(scratch, 'case-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileNav = await frame(nav), mobileContent = await frame(content);
  assert.ok(mobileContent.height > 200 && mobileContent.y + mobileContent.height <= 844, JSON.stringify(mobileContent));
  for (const name of ['Timeline', 'Report', 'Overview', 'Evidence']) {
    await tab(name).click(); equalFrame(await frame(nav), mobileNav, 'Mobile navigation'); equalFrame(await frame(content), mobileContent, 'Mobile content');
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth || scrollY !== 0), false);
  assert.equal(await evidence.evaluate(element => getComputedStyle(element).opacity), '1');
  await tab('Overview').press('End');
  assert.equal(await tab('Report').getAttribute('aria-selected'), 'true');
  const reportFrame = await frame(tab('Report'));
  assert.ok(reportFrame.x >= mobileNav.x && reportFrame.x + reportFrame.width <= mobileNav.x + mobileNav.width, 'Keyboard selection must remain visible');
  await tab('Evidence').click();
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(scratch, 'case-mobile.png') });
  await page.getByRole('button', { name: 'Settings', exact: true }).click(); await page.waitForTimeout(250);
  const mobileModal = await frame(dialog);
  for (const section of ['Models', 'Updates', 'Appearance', 'Viewer']) {
    await sections.getByRole('button', { name: section, exact: true }).click(); equalFrame(await frame(dialog), mobileModal, 'Mobile settings');
  }
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(scratch, 'settings-mobile.png') });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  assert.deepEqual(errors, []);
  console.log('PASS stable desktop/mobile frames, retained view scroll, rapid/keyboard navigation, concise settings, model/vision saving and ChatGPT account controls. Screenshots:', scratch);
} finally {
  await browser?.close();
  if (child.exitCode === null) { const exited = new Promise(resolve => child.once('exit', resolve)); child.kill('SIGTERM'); await exited; }
}
