import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { ApiProvider, useApiClient } from '../.test-build/src/api/ApiProvider.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';
import { App } from '../.test-build/src/App.mjs';

test('provides one shared client without issuing requests or exposing its token in markup', () => {
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { throw new Error('No request expected'); } });
  client.setToken('synthetic-provider-token');
  function Consumer() {
    assert.equal(useApiClient(), client);
    return createElement(App);
  }
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(Consumer)));
  assert.match(html, /Case access is not available yet/);
  assert.doesNotMatch(html, /synthetic-provider-token/);
});

test('fails clearly when a consumer is outside the shared provider', () => {
  function Consumer() { useApiClient(); return null; }
  assert.throws(() => renderToStaticMarkup(createElement(Consumer)), /require ApiProvider/);
});
