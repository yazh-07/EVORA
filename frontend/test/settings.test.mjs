import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import { SettingsModal } from '../.test-build/src/settings/SettingsModal.mjs';
import { SETTINGS_KEY, defaultSettings, parseSettings, readSettings, saveSettings, subscribeSettings } from '../.test-build/src/settings/settings.mjs';

function browser(t) {
  const values = new Map();
  const window = new EventTarget();
  window.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  const previous = globalThis.window;
  globalThis.window = window;
  t.after(() => { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; });
  return window;
}

test('missing, corrupt and invalid preferences fall back safely; false toggles survive reload', t => {
  const window = browser(t);
  for (const raw of [null, '{bad', 'null', '42', '{"detection_threshold":99,"show_provenance_rays":"false"}']) {
    assert.deepEqual(parseSettings(raw), defaultSettings);
  }
  const preferences = { ...defaultSettings, show_provenance_rays: false, show_bounding_boxes: false, default_node_label: 'filename' };
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(preferences));
  assert.deepEqual(readSettings(), preferences);
});

test('saving uses authenticated PUT, persists browser preferences and notifies mounted views', async t => {
  browser(t);
  let calls = 0, changes = 0;
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async (url, options) => {
    calls++;
    assert.equal(url.pathname, '/api/v1/settings');
    assert.equal(options.method, 'PUT');
    assert.equal(options.headers.get('Authorization'), 'Bearer synthetic-settings');
    const body = JSON.parse(options.body);
    assert.deepEqual(Object.keys(body).sort(), ['detection_threshold', 'openai_base_url', 'qa_model', 'qa_provider', 'qa_url', 'show_provenance_rays']);
    return Response.json(body);
  } });
  client.setToken('synthetic-settings');
  const unsubscribe = subscribeSettings(() => changes++);
  const preferences = { ...defaultSettings, qa_model: 'custom:7b', show_provenance_rays: false, default_node_label: 'filename' };
  await saveSettings(client, preferences);
  assert.equal(calls, 1); assert.equal(changes, 1); assert.deepEqual(readSettings(), preferences);
  unsubscribe();
  await saveSettings(client, defaultSettings);
  assert.equal(changes, 1); assert.deepEqual(readSettings(), defaultSettings);
});

test('failed backend saves preserve local settings without notifying graph subscribers', async t => {
  browser(t);
  let changes = 0;
  const unsubscribe = subscribeSettings(() => changes++);
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async () => Response.json({}, { status: 500 }) });
  client.setToken('synthetic-settings');
  await assert.rejects(saveSettings(client, { ...defaultSettings, show_provenance_rays: false }));
  assert.deepEqual(readSettings(), defaultSettings); assert.equal(changes, 0);
  unsubscribe();
});

test('OpenAI preferences round-trip without persisting API keys and reset preserves saved credentials', async t => {
  const window = browser(t);
  const bodies = [];
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async (_url, options) => {
    const body = JSON.parse(options.body); bodies.push(body);
    // Even an unexpected secret echoed by a server must never reach browser storage.
    return Response.json({ ...body, has_openai_key: true, openai_api_key: 'sk-server-secret' });
  } });
  client.setToken('synthetic-settings');
  const preferences = { ...defaultSettings, qa_provider: 'openai', qa_model: 'custom/model',
    openai_base_url: 'https://provider.test/api/v1', has_openai_key: true };
  await saveSettings(client, preferences, undefined, 'sk-draft-secret');
  assert.equal(bodies[0].openai_api_key, 'sk-draft-secret');
  assert.deepEqual(readSettings(), preferences);
  const raw = window.localStorage.getItem(SETTINGS_KEY);
  assert.ok(!raw.includes('secret')); assert.ok(!raw.includes('openai_api_key'));
  await saveSettings(client, preferences);
  assert.ok(!('openai_api_key' in bodies[1]));
  await saveSettings(client, defaultSettings);
  assert.ok(!('openai_api_key' in bodies[2]));
  assert.deepEqual(readSettings(), { ...defaultSettings, has_openai_key: true });
});

test('failed OpenAI saves never persist draft credentials or preferences', async t => {
  const window = browser(t);
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async () => Response.json({}, { status: 400 }) });
  client.setToken('synthetic-settings');
  await assert.rejects(saveSettings(client, { ...defaultSettings, qa_provider: 'openai' }, undefined, 'sk-secret'));
  assert.equal(window.localStorage.getItem(SETTINGS_KEY), null);
  assert.deepEqual(parseSettings(JSON.stringify({ ...defaultSettings, openai_api_key: 'sk-secret' })), defaultSettings);
});

test('storage failures after backend success are reported without claiming complete persistence', async t => {
  const window = browser(t);
  window.localStorage.setItem = () => { throw Error('Quota'); };
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async () => Response.json(defaultSettings) });
  client.setToken('synthetic-settings');
  await assert.rejects(saveSettings(client, defaultSettings), /Backend settings saved, but browser storage is unavailable/);
});

test('cross-tab settings changes notify mounted views and unsubscribe cleans up', t => {
  const window = browser(t); let changes = 0;
  const unsubscribe = subscribeSettings(() => changes++);
  for (const key of ['other-key', SETTINGS_KEY, null]) {
    const event = new Event('storage'); event.key = key; window.dispatchEvent(event);
  }
  assert.equal(changes, 2); unsubscribe();
  const event = new Event('storage'); event.key = SETTINGS_KEY; window.dispatchEvent(event);
  assert.equal(changes, 2);
});

test('settings dialog exposes labeled controls, slider bounds and actions', () => {
  const client = createApiClient({ baseUrl: 'http://backend.test', fetch: async () => { throw Error('No rendering requests'); } });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(SettingsModal, { onClose() {} })));
  for (const text of ['aria-labelledby="settings-title"', 'AI Copilot Configuration', 'Visual Forensics &amp; Media Settings',
    'Knowledge Graph Settings', 'Source Description', 'Filename', 'Show Bounding Boxes', 'Show Provenance Rays',
    'Test Connection &amp; Fetch Models', 'Save Settings', 'Reset to Defaults', 'Cancel', 'min="50" max="95"',
    'Local (Ollama)', 'Cloud / Custom (OpenAI-compatible)', 'Ollama Endpoint URL']) assert.ok(html.includes(text), text);
  assert.ok(!html.includes('type="password"'));
});

test('OpenAI settings show password, base URL and model choices without revealing saved keys', t => {
  const window = browser(t);
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...defaultSettings, qa_provider: 'openai',
    qa_model: 'gpt-4o', has_openai_key: true, openai_api_key: 'sk-stale-secret' }));
  const client = createApiClient({ baseUrl: 'http://backend.test' });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(SettingsModal, { onClose() {} })));
  for (const text of ['type="password"', 'placeholder="sk-..."', 'Base URL', 'https://api.openai.com/v1',
    'Recommended', 'gpt-4o-mini', 'o3-mini', 'Custom model', 'A key is saved. Leave blank to keep it.']) assert.ok(html.includes(text), text);
  assert.ok(!html.includes('sk-stale-secret'));
  assert.ok(!html.includes('Ollama Endpoint URL'));
});
