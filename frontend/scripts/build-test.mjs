import { build } from 'esbuild';

await build({
  entryPoints: ['src/cases/LocationsWorkspace.tsx', 'src/cases/bulkProcessingController.ts', 'src/cases/ActivityChart.tsx', 'src/cases/EvidenceResults.tsx', 'src/appearance/appearance.ts', 'src/settings/settings.ts', 'src/settings/SettingsModal.tsx', 'src/App.tsx', 'src/api/client.ts', 'src/api/ApiProvider.tsx', 'test/fixtures/api.ts', 'src/cases/store.ts', 'src/cases/CaseWorkspace.tsx', 'src/cases/downloadController.ts', 'src/cases/mediaLocators.ts', 'src/cases/sourceObservations.ts', 'src/cases/metricsData.ts', 'src/cases/AnswerMarkdown.tsx', 'src/cases/graphAppearance.ts'],
  outbase: '.',
  outdir: '.test-build',
  outExtension: { '.js': '.mjs' },
  bundle: true,
  loader: { '.ttf': 'base64' },
  packages: 'external',
  platform: 'node',
  format: 'esm',
  jsx: 'automatic',
  // Keep one shared class/context identity across the test bundles.
  splitting: true,
});
