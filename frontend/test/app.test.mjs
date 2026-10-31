import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { App } from '../.test-build/src/App.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';

test('workspace offers session-only case access with landmarks and no fabricated records', () => {
  let calls = 0;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { calls++; throw Error(); } });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(App)));
  assert.match(html, /<h1>Case workspace/);
  assert.match(html, /href="#workspace">Skip to workspace/);
  assert.match(html, /<main id="workspace" tabindex="-1"/);
  assert.match(html, /aria-label="Workspace"/);
  assert.match(html, /type="password" autoComplete="off"/);
  assert.match(html, /Enter an access token to load your cases/);
  assert.match(html, /Case details/);
  assert.doesNotMatch(html, /SYSTEM ONLINE|Synthetic case|Create case|Upload/);
  assert.equal(calls, 0);
});
