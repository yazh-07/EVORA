import { build, context } from 'esbuild';
import { copyFile, mkdir, cp } from 'node:fs/promises';

const serve = process.argv.includes('--serve');
await mkdir('dist', { recursive: true });
await copyFile('index.html', 'dist/index.html');
await cp('public', 'dist', { recursive: true });
await mkdir('dist/assets', { recursive: true });
await copyFile('node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', 'dist/assets/maplibre-gl-worker.mjs');
await copyFile('node_modules/maplibre-gl/dist/maplibre-gl-shared.mjs', 'dist/assets/maplibre-gl-shared.mjs');

const options = {
  entryPoints: { main: 'src/main.tsx' },
  outdir: 'dist/assets',
  splitting: true,
  chunkNames: 'chunks/[name]-[hash]',
  bundle: true,
  loader: { '.ttf': 'base64' },
  format: 'esm',
  platform: 'browser',
  target: ['es2022'],
  jsx: 'automatic',
  minify: !serve,
  define: {
    'process.env.NODE_ENV': JSON.stringify(serve ? 'development' : 'production'),
    __EVORA_API_BASE_URL__: JSON.stringify(process.env.EVORA_API_BASE_URL ?? 'http://127.0.0.1:8000'),
  },
  logLevel: 'info',
};

if (serve) {
  const development = await context(options);
  try {
    await development.watch();
    const server = await development.serve({ servedir: 'dist', host: '127.0.0.1', port: 5173 });
    console.log(`EVORA frontend: http://${server.hosts[0]}:${server.port}`);
    for (const signal of ['SIGINT', 'SIGTERM']) {
      process.once(signal, async () => {
        await development.dispose();
        process.exit(0);
      });
    }
  } catch (error) {
    await development.dispose();
    throw error;
  }
} else {
  await build(options);
}
