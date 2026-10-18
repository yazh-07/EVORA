import type { components, operations } from './schema';

// Compile-only assertions exercise the generated interface without a second schema.
const bodyless: operations['startAnalysis']['requestBody'] = undefined;
const headers: operations['startAnalysis']['parameters']['header'] = {
  'Idempotency-Key': 'synthetic-typecheck-key',
};
const error: operations['createCase']['responses'][400]['content']['application/json'] = {
  code: 'INVALID_INPUT',
  message: 'Invalid request input.',
} satisfies components['schemas']['ApiError'];

// @ts-expect-error The contract has no analysis request body.
const invalidBody: operations['startAnalysis']['requestBody'] = { trigger: 'manual' };
// @ts-expect-error The required error message cannot be omitted.
const invalidError: components['schemas']['ApiError'] = { code: 'INVALID_INPUT' };

void [bodyless, headers, error, invalidBody, invalidError];
