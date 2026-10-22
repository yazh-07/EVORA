import type { ApiClient } from './client';
import type { components } from './schema';

// Never called. Compile-only assertions consume the actual client signature and generated contract.
async function checkClient(client: ApiClient) {
  const result: components['schemas']['CasePage'] = await client.request('get', '/api/v1/cases', { query: { limit: 1 } });
  const created: components['schemas']['Case'] = await client.request('post', '/api/v1/cases', { body: { title: 'Synthetic' } });
  const bytes: Blob = await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', {
    path: { caseId: 'synthetic', evidenceId: 'synthetic' }, responseType: 'blob',
  });
  await client.request('post', '/api/v1/cases/{caseId}/analysis-runs', {
    path: { caseId: 'synthetic' }, header: { 'Idempotency-Key': 'synthetic-key' },
  });
  // @ts-expect-error No invented routes.
  await client.request('get', '/api/v1/login', {});
  // @ts-expect-error This route has no POST operation.
  await client.request('post', '/api/v1/cases/{caseId}', { path: { caseId: 'synthetic' } });
  // @ts-expect-error Path parameters are required.
  await client.request('get', '/api/v1/cases/{caseId}', {});
  // @ts-expect-error CreateCase requires title.
  await client.request('post', '/api/v1/cases', { body: { description: 'Missing title' } });
  // @ts-expect-error startAnalysis is bodyless.
  await client.request('post', '/api/v1/cases/{caseId}/analysis-runs', { path: { caseId: 'synthetic' }, header: { 'Idempotency-Key': 'synthetic-key' }, body: {} });
  // @ts-expect-error The idempotency header is required.
  await client.request('post', '/api/v1/cases/{caseId}/analysis-runs', { path: { caseId: 'synthetic' } });
  // @ts-expect-error There is no analytical selector on listEntities.
  await client.request('get', '/api/v1/cases/{caseId}/entities', { path: { caseId: 'synthetic' }, query: { analysis_run_id: 'synthetic' } });
  // @ts-expect-error Bearer headers are supplied only by the in-memory session.
  await client.request('get', '/api/v1/cases', { header: { Authorization: 'synthetic' } });
  // @ts-expect-error Downloads must explicitly select binary decoding.
  await client.request('get', '/api/v1/cases/{caseId}/evidence/{evidenceId}/content', { path: { caseId: 'synthetic', evidenceId: 'synthetic' } });
  void [result, created, bytes];
}
void checkClient;
