import test from 'node:test';
import assert from 'node:assert/strict';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { createUpdatesController } from '../.test-build/src/settings/Updates.mjs';

const status = (extra = {}) => ({ current_version: '1.3.8', latest_version: null, status: 'idle', downloaded_bytes: 0, total_bytes: 0, release_url: 'https://github.com/yazh-07/EVORA/releases/latest', download_url: null, checked_at: null, error: null, automatic: true, can_install: true, available: false, ...extra });
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 30)); };
function fixture(t, respond, role = 'administrator') {
  const calls = [];
  const client = createApiClient({ baseUrl: 'http://localhost:8000', authMode: 'local', fetch: async (url, options) => {
    calls.push({ path: new URL(url).pathname, ...options });
    return Response.json(await respond(calls.at(-1)), { headers: { 'X-Evora-User': 'update-tester' } });
  } });
  client.activateUser({ id: 'update-tester', username: 'admin', display_name: 'Tester', role, disabled: false, must_change_password: false }, false);
  const controller = createUpdatesController(client, 10);
  t.after(() => controller.dispose());
  return { client, controller, calls };
}

test('automatic checks run for an administrator and honor the saved opt-out', async t => {
  for (const automatic of [true, false]) {
    const { controller, calls } = fixture(t, () => status({ automatic }));
    controller.start(); await settle();
    assert.deepEqual(calls.map(call => call.path), automatic ? ['/api/v1/updates', '/api/v1/updates/check'] : ['/api/v1/updates']);
    if (automatic) assert.deepEqual(JSON.parse(calls[1].body), { automatic: true });
    controller.dispose();
  }
});

test('investigators can read update status without triggering automatic checks', async t => {
  const { controller, calls } = fixture(t, () => status(), 'investigator');
  controller.start(); await settle();
  assert.deepEqual(calls.map(call => call.path), ['/api/v1/updates']);
});

test('manual actions use the update endpoints and poll download progress until ready', async t => {
  let reads = 0;
  const { controller, calls } = fixture(t, call => call.path.endsWith('/download') ? status({ status: 'downloading', total_bytes: 100, downloaded_bytes: 20 }) : status({ status: ++reads > 1 ? 'ready' : 'idle', total_bytes: 100, downloaded_bytes: 100 }));
  await controller.action('check');
  assert.deepEqual(JSON.parse(calls[0].body), { automatic: false });
  await controller.action('download'); await settle();
  assert.equal(controller.getSnapshot().data.status, 'ready');
  await controller.action('install'); await controller.action('cancel');
  assert.ok(calls.some(call => call.path === '/api/v1/updates/install'));
  assert.ok(calls.some(call => call.path === '/api/v1/updates/cancel'));
});

test('untrusted download destinations and impossible progress are rejected', async t => {
  for (const extra of [{ download_url: 'https://untrusted.example/installer.exe' }, { total_bytes: 1, downloaded_bytes: 2 }]) {
    const { controller } = fixture(t, () => status(extra));
    await controller.refresh();
    assert.equal(controller.getSnapshot().data, null);
    assert.match(controller.getSnapshot().error, /Could not read update status/);
  }
});

test('a delayed status response cannot repopulate state after sign-out', async t => {
  let resolve;
  const { client, controller } = fixture(t, () => new Promise(done => { resolve = done; }));
  controller.start();
  client.clearToken(); resolve(status()); await settle();
  assert.equal(controller.getSnapshot().data, null);
  assert.equal(controller.getSnapshot().error, '');
});

test('incremental update status accepts the official bundle and retains changed file sizes', async t => {
  const { controller } = fixture(t, () => status({ mode: 'incremental', file_count: 3, available: true,
    latest_version: '9.0.0', status: 'ready', total_bytes: 32768, downloaded_bytes: 32768,
    download_url: 'https://github.com/yazh-07/EVORA/releases/download/v9.0.0/EVORA-Update-Windows-x64.bin' }));
  await controller.refresh();
  assert.equal(controller.getSnapshot().data.mode, 'incremental');
  assert.equal(controller.getSnapshot().data.file_count, 3);
  assert.equal(controller.getSnapshot().error, '');
});

test('invalid update modes and file counts are rejected', async t => {
  for (const extra of [{ mode: 'unknown' }, { file_count: -1 }, { file_count: 1.5 }]) {
    const { controller } = fixture(t, () => status(extra));
    await controller.refresh(); assert.equal(controller.getSnapshot().data, null);
  }
});
