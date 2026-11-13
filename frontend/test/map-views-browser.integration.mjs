// Synthetic case/API data, real MapLibre workers and controls. Map tiles
// are synthetic unless EVORA_LIVE_MAP_TILES=1 explicitly enables the live provider.
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp, mkdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = await import(process.env.EVORA_PLAYWRIGHT_MODULE ?? 'playwright');
const frontend = fileURLToPath(new URL('..', import.meta.url));
const temporary = await mkdtemp(join(tmpdir(), 'evora-map-views-'));
const artifacts = process.env.EVORA_BROWSER_ARTIFACTS ?? '/tmp/evora-map-views-qa';
const origin = 'http://127.0.0.1:4187';
const liveTiles = process.env.EVORA_LIVE_MAP_TILES === '1';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const gps = {
  id: id(1), evidence_id: id(2), processing_run_id: id(3), observation_id: id(4),
  source_locator: 'row 2, latitude', basis: 'gps', label: 'D-1', device: 'D-1',
  observed_at_utc: '2026-11-13T10:30:00Z', observed_at_raw: '2026-11-13T10:30:00Z',
  geometry: { type: 'Point', coordinates: [77.59, 12.97] },
  precision: 'reported_coordinates', accuracy_m: null,
};
const approximate = {
  ...gps, id: id(5), basis: 'place_mention', device: null, label: 'Paris',
  geometry: { type: 'Point', coordinates: [2.35, 48.86] }, precision: 'city',
};
// Reuse a valid square image for synthetic tile responses; no provider is called.
const fixtureTile = await readFile(join(frontend, '../fixtures/media/astronaut.png'));
let browser;
try {
  await mkdir(artifacts, { recursive: true });
  await build({
    stdin: {
      contents: `import React from 'react'; import {createRoot} from 'react-dom/client';
        import {ApiProvider} from './src/api/ApiProvider'; import {createApiClient} from './src/api/client';
        import {LocationsWorkspace} from './src/cases/LocationsWorkspace';
        const client=createApiClient({baseUrl:'${origin}'}); client.setToken('synthetic-map-test');
        createRoot(document.getElementById('root')).render(<ApiProvider client={client}>
          <LocationsWorkspace caseId='${id(9)}' inspectEvidence={(id,focus)=>{window.inspected={id,focus};}}/>
        </ApiProvider>);`,
      resolveDir: frontend, loader: 'tsx',
    },
    outfile: join(temporary, 'fixture.js'), bundle: true, format: 'iife', platform: 'browser', jsx: 'automatic',
    define: { 'process.env.NODE_ENV': '"production"' },
  });
  browser = await chromium.launch({
    executablePath: process.env.EVORA_CHROME_PATH, headless: true,
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const errors = [], external = [], successfulTiles = [], successfulStreets = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url()) && !request.url().startsWith(origin)) external.push(request.url()); });
  page.on('response', response => {
    if (response.url().startsWith('https://services.arcgisonline.com/') && response.ok()) successfulTiles.push(response.url());
    if (response.url().startsWith('https://tile.openstreetmap.org/') && response.ok()) successfulStreets.push(response.url());
  });
  await page.route(origin + '/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: '<html data-theme="light"><body><div id="root"></div></body></html>' });
    if (path.endsWith('/locations')) return route.fulfill({ json: { case_id: id(9), items: [gps, approximate], total: 2, limit: 1000, offset: 0, revision: 'snapshot-1' } });
    if (['/assets/maplibre-gl-worker.mjs', '/assets/maplibre-gl-shared.mjs', '/maps/countries.geojson'].includes(path)) {
      return route.fulfill({ contentType: path.endsWith('.mjs') ? 'application/javascript' : 'application/json', body: await readFile(join(frontend, 'dist', path)) });
    }
    throw Error('Unexpected local request ' + path);
  });
  await context.route('https://www.google.com/maps/@**', route => route.fulfill({ contentType: 'text/html', body: 'Street View navigation fixture' }));
  await page.route('https://services.arcgisonline.com/**', route => liveTiles ? route.continue() : route.fulfill({ contentType: 'image/png', body: fixtureTile }));
  await page.route('https://tile.openstreetmap.org/**', route => liveTiles ? route.continue() : route.fulfill({ contentType: 'image/png', body: fixtureTile }));
  await page.goto(origin);
  await page.addStyleTag({ path: join(frontend, 'dist/assets/main.css') });
  await page.addScriptTag({ path: join(temporary, 'fixture.js') });
  const picker = page.getByLabel('Basemap', { exact: true });
  await page.waitForFunction(() => !document.querySelector('.basemap-picker select')?.disabled);
  assert.equal(await picker.inputValue(), 'streets', 'A fresh map must display actual streets');
  await page.getByText('Online · OpenStreetMap', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'D-1', exact: true }).click();
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => document.querySelector('.map-stage')?.getAttribute('aria-busy') === 'false');
  assert.ok(successfulStreets.length > 0);
  await page.screenshot({ path: join(artifacts, 'streets.png'), fullPage: true });
  await page.getByRole('button', { name: 'Paris', exact: true }).click();
  assert.equal(await page.getByText('Street View ↗', { exact: true }).count(), 0, 'Place centers cannot imply a GPS position');
  await page.getByRole('button', { name: 'D-1', exact: true }).click();
  const satelliteResponse = page.waitForResponse(response => response.url().startsWith('https://services.arcgisonline.com/') && response.ok());
  await picker.selectOption('satellite');
  await page.getByText('Online · Satellite · Esri', { exact: true }).waitFor();
  await satelliteResponse;
  assert.ok(successfulTiles.length > 0);
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => document.querySelector('.map-stage')?.getAttribute('aria-busy') === 'false');
  await page.waitForFunction(() => document.querySelector('.maplibregl-ctrl-attrib-inner')?.textContent.includes('Vantor'));
  await page.screenshot({ path: join(artifacts, 'satellite.png'), fullPage: true });
  const street = page.getByRole('link', { name: 'Street View ↗', exact: true });
  assert.equal(await street.getAttribute('referrerpolicy'), 'no-referrer');
  assert.match(await street.getAttribute('rel'), /noopener.*noreferrer/);
  const popupPromise = context.waitForEvent('page');
  await street.click();
  const popup = await popupPromise;
  await popup.waitForURL('https://www.google.com/maps/@**');
  assert.equal(new URL(popup.url()).searchParams.get('viewpoint'), '12.97,77.59');
  assert.deepEqual([...new URL(popup.url()).searchParams.keys()], ['api', 'map_action', 'viewpoint']);
  await popup.close();
  await page.getByRole('button', { name: 'Open source', exact: true }).click();
  assert.deepEqual(await page.evaluate(() => window.inspected), { id: gps.evidence_id, focus: { observation_id: gps.observation_id, processing_run_id: gps.processing_run_id, source_locator: gps.source_locator } });
  await picker.selectOption('streets');
  await page.getByText('Online · OpenStreetMap', { exact: true }).waitFor();
  await picker.selectOption('offline');
  await page.getByText('Offline · world overview', { exact: true }).waitFor();
  assert.equal(await picker.inputValue(), 'offline');
  assert.equal(await page.getByRole('link', { name: 'Street View ↗', exact: true }).count(), 0);
  await page.waitForLoadState('networkidle');
  const externalBeforeOfflineReload = external.length;
  await page.reload();
  await page.addStyleTag({ path: join(frontend, 'dist/assets/main.css') });
  await page.addScriptTag({ path: join(temporary, 'fixture.js') });
  await page.waitForFunction(() => !document.querySelector('.basemap-picker select')?.disabled);
  await page.waitForLoadState('networkidle');
  assert.equal(await picker.inputValue(), 'offline', 'The offline choice must survive a reload');
  assert.equal(external.length, externalBeforeOfflineReload, 'Stored offline mode must make no external requests');
  await picker.selectOption('streets');
  await page.getByRole('button', { name: 'D-1', exact: true }).click();
  await page.waitForLoadState('networkidle');
  await page.setViewportSize({ width: 360, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: join(artifacts, 'mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  assert.equal(await page.getByRole('alert').count(), 0);
  console.log(`PASS default street detail, satellite/street switching, attribution, exact GPS Street View navigation, source citation, persistent offline choice without external requests, and mobile layout. ${liveTiles ? 'Live OpenStreetMap and Esri satellite tiles verified.' : 'Tiles and API outputs are synthetic.'}`);
} finally {
  await browser?.close();
  await rm(temporary, { recursive: true, force: true });
}
