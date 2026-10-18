import { build } from 'esbuild';

await build({
  entryPoints: ['src/App.tsx'],
  outfile: '.test-build/App.mjs',
  bundle: true,
  packages: 'external',
  platform: 'node',
  format: 'esm',
  jsx: 'automatic',
});
