import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { App } from '../.test-build/src/App.mjs';

test('root renders the workspace, skip link and contextual inspector', () => {
  const html = renderToStaticMarkup(createElement(App));
  assert.match(html, /<h1>Evidence workspace<\/h1>/);
  assert.match(html, /<main id="workspace" tabindex="-1">/);
  assert.match(html, /href="#workspace">Skip to workspace<\/a>/);
  assert.match(html, /<nav[^>]+aria-label="Workspace"/);
  assert.match(html, /<aside[^>]+aria-labelledby="inspector-heading"/);
  assert.match(html, /id="inspector-heading">Evidence details/);
});

test('unavailable access renders honestly without API traffic or enabled domain actions', () => {
  const calls = [];
  const fetch = globalThis.fetch;
  globalThis.fetch = (...args) => {
    calls.push(args);
    throw new Error('No API request is expected from the skeleton');
  };
  try {
    const html = renderToStaticMarkup(createElement(App));
    assert.match(html, /No case selected\./);
    assert.match(html, /Case access is not available yet/);
    assert.doesNotMatch(html, /<button|<input|<table|SYSTEM ONLINE/i);
    assert.equal(calls.length, 0);
  } finally {
    globalThis.fetch = fetch;
  }
});
