import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { App } from '../.test-build/src/App.mjs';
import { ApiProvider } from '../.test-build/src/api/ApiProvider.mjs';
import { createApiClient } from '../.test-build/src/api/client.mjs';

test('workspace offers local login with landmarks and no fabricated records', () => {
  let calls = 0;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { calls++; throw Error(); } });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client }, createElement(App)));
  assert.match(html, /<h1 id="session-heading">Sign in to EVORA/);
  assert.match(html, /href="#workspace">Skip to workspace/);
  assert.match(html, /<main id="workspace" tabindex="-1"/);
  assert.match(html, /aria-label="Settings"/);
  assert.match(html, /Sign in to EVORA/);
  assert.doesNotMatch(html, /Access token|synthetic-one|synthetic-two/);
  assert.match(html, /Sign in to load your cases/);
  assert.match(html, /Case details/);
  assert.doesNotMatch(html, /SYSTEM ONLINE|Synthetic case|Create case|Upload/);
  assert.match(html, /class="header-settings"[^>]*aria-haspopup="dialog"/);
  assert.equal(calls, 0);
});

test('task navigation starts at overview and defers unused tools while keeping accessible panel targets', async () => {
  const { CaseEvidenceWorkspace, CaseAnalysisWorkspace } = await import('../.test-build/src/cases/CaseWorkspace.mjs');
  const caseId = '11111111-1111-4111-8111-111111111111';
  let calls = 0;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { calls++; throw Error(); } });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client },
    createElement(CaseAnalysisWorkspace, { caseId }, createElement(CaseEvidenceWorkspace, { caseId }))));
  for (const tab of ['overview', 'evidence', 'timeline', 'investigation', 'report']) {
    assert.match(html, new RegExp(`role="tab" id="tab-${tab}" aria-controls="panel-${tab}" aria-selected="${tab === 'overview'}"`));
    assert.match(html, new RegExp(`id="panel-${tab}" role="tabpanel" aria-labelledby="tab-${tab}" tabindex="0"${tab === 'overview' ? '>' : ' hidden=""'}`));
  }
  assert.match(html, /<h2 class="sr-only">Overview/);
  assert.doesNotMatch(html, /id="evidence-file"|class="knowledge-graph"|id="case-question"/);
  assert.equal(calls, 0);
});
