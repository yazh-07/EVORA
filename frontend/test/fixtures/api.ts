import type { components } from '../../src/api/schema';
import { createHash } from 'node:crypto';

// Schema-derived synthetic responses only. These are not an implemented F00/F01/F02.
export const caseA = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'Synthetic case A',
  created_at: '2026-10-22T00:00:00Z',
} satisfies components['schemas']['Case'];
export const caseB = {
  id: '22222222-2222-4222-8222-222222222222',
  title: 'Synthetic case B',
  created_at: '2026-10-22T00:00:00Z',
} satisfies components['schemas']['Case'];
export const invalidInput = {
  code: 'INVALID_INPUT', message: 'Invalid request input.',
} satisfies components['schemas']['ApiError'];
export const emptyCases = {
  items: [], total: 0, limit: 20, offset: 0,
} satisfies components['schemas']['CasePage'];
export const casesA = { ...emptyCases, items: [caseA], total: 1 } satisfies components['schemas']['CasePage'];
export const originalBytes = new Uint8Array([0, 255, 10, 13, 42]);
export const evidence = {
  id: '44444444-4444-4444-8444-444444444444', case_id: caseA.id,
  kind: 'document', filename: 'synthetic.bin', media_type: 'application/octet-stream',
  source_label: 'Synthetic fixture', sha256: createHash('sha256').update(originalBytes).digest('hex'),
  size_bytes: originalBytes.length, created_at: caseA.created_at,
} satisfies components['schemas']['Evidence'];
const manifest = { case_id: caseA.id, evidence_ids: [], observation_ids: [], processing_run_ids: [] };
export const analysis = {
  id: '33333333-3333-4333-8333-333333333333', case_id: caseA.id, status: 'queued', trigger: 'initial',
  algorithm_version: 'synthetic-fixture-v1', created_at: caseA.created_at,
  input_snapshot: { ...manifest, sha256: createHash('sha256').update(JSON.stringify(manifest)).digest('hex') },
} satisfies components['schemas']['AnalysisRun'];
