import { build } from 'esbuild';

await build({
  entryPoints: ['src/App.tsx', 'src/api/client.ts', 'src/api/ApiProvider.tsx', 'test/fixtures/api.ts'],
  outbase: '.',
  outdir: '.test-build',
  outExtension: { '.js': '.mjs' },
  bundle: true,
  packages: 'external',
  platform: 'node',
  format: 'esm',
  jsx: 'automatic',
  // Keep one shared class/context identity across the test bundles.
  splitting: true,
});
