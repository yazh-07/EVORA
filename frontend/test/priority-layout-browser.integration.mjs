import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { PriorityListPanel } from '../.test-build/src/cases/CaseWorkspace.mjs';

const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const factors = [{ name: 'connectivity', contribution: 30, value: .6, weight: .5, evidence_ids: [id(1)], explanation: 'Related sources share a documented reference. '.repeat(20) }];
const result = { id: id(100), evidence_id: id(1), case_id: id(10), analysis_run_id: id(20), priority: 'P3', score: 30, created_at: '2026-11-15T10:00:00Z', factors };
const state = { status: 'ready', message: '', overrides: {}, histories: { [id(1)]: { status: 'ready', message: '', items: Array.from({ length: 4 }, (_, i) => ({ ...result, id: id(100 + i) })) } }, page: { analysis_run_id: id(20), total: 2, limit: 20, offset: 0, items: [1, 2].map(n => ({ evidence_id: id(n), effective_priority: 'P3', latest_result: { ...result, evidence_id: id(n) } })) } };
const html = renderToStaticMarkup(createElement(PriorityListPanel, { state, load: async () => {}, loadHistory: async () => {}, updateOverride: () => {}, submitOverride: async () => {}, sourceNames: { [id(1)]: 'asset-register.txt', [id(2)]: 'network.csv' } }));
const css = await readFile(new URL('../dist/assets/main.css', import.meta.url), 'utf8');
const browser = await chromium.launch({ executablePath: process.env.EVORA_CHROME_PATH, headless: true, args: ['--no-sandbox'] });
try {
  for (const width of [1920, 960, 390]) for (const reducedMotion of ['no-preference', 'reduce']) {
    const page = await browser.newPage({ viewport: { width, height: 1080 }, reducedMotion });
    await page.setContent(`<style>${css}</style>${html}`);
    const row = page.locator('.priority-list tbody tr').first();
    const height = () => row.evaluate(e => e.getBoundingClientRect().height);
    const collapsed = await height();
    for (const selector of ['.factor-details', '.triage-history-details', '.override-details']) {
      const details = row.locator(selector), summary = details.locator(':scope > summary');
      for (let repeat = 0; repeat < 2; repeat++) {
        await summary.click(); await page.waitForTimeout(350);
        assert.ok(await height() > collapsed + 20, `${width} ${selector} must expand`);
        await summary.click();
        assert.ok(Math.abs(await height() - collapsed) < 2, `${width} ${selector}: closing must release row height immediately`);
        await page.waitForTimeout(350);
        assert.ok(Math.abs(await height() - collapsed) < 2, `${width} ${reducedMotion} ${selector}: ${await height()} != ${collapsed}`);
      }
    }
    // Closing one disclosure keeps any other open content sized correctly.
    await row.locator('.factor-details > summary').click();
    await row.locator('.triage-history-details > summary').click(); await page.waitForTimeout(350);
    await row.locator('.factor-details > summary').click(); await page.waitForTimeout(350);
    assert.ok(await height() > collapsed + 20);
    await row.locator('.triage-history-details > summary').click(); await page.waitForTimeout(350);
    assert.ok(Math.abs(await height() - collapsed) < 2);
    await page.close();
  }
  console.log('PASS: priority rows shrink after repeated disclosure toggles at desktop/mobile widths and with reduced motion');
} finally { await browser.close(); }
