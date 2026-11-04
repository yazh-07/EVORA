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

test('active investigation keeps all five accessible tab panels mounted with CSS display toggles', async () => {
  const { CaseEvidenceWorkspace, CaseAnalysisWorkspace } = await import('../.test-build/src/cases/CaseWorkspace.mjs');
  const caseId = '11111111-1111-4111-8111-111111111111';
  let calls = 0;
  const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetch: async () => { calls++; throw Error(); } });
  const html = renderToStaticMarkup(createElement(ApiProvider, { client },
    createElement(CaseAnalysisWorkspace, { caseId }, createElement(CaseEvidenceWorkspace, { caseId }))));
  for (const tab of ['evidence', 'triage', 'graph', 'findings', 'overview']) {
    assert.match(html, new RegExp(`role="tab" id="tab-${tab}" aria-controls="panel-${tab}" aria-selected="${tab === 'evidence'}"`));
    assert.match(html, new RegExp(`id="panel-${tab}" role="tabpanel" aria-labelledby="tab-${tab}" tabindex="0" style="display:${tab === 'evidence' ? 'block' : 'none'}"`));
  }
  for (const heading of ['upload-heading', 'evidence-heading', 'evidence-inspector', 'analysis-heading']) assert.ok(html.includes(`id="${heading}"`));
  for (const label of ['Triage &amp; Priority', 'Knowledge Graph', 'Findings', 'Case evidence overview']) assert.ok(html.includes(label));
  assert.equal(calls, 0);
});
