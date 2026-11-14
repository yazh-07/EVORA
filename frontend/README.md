# Frontend

React and TypeScript investigator workspace, built with esbuild. The application uses the same-origin `/api/v1` backend and local-account sessions.

## Development

Use the Node.js and npm versions pinned in `package.json`.

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

The development server listens on `127.0.0.1:5173`. The normal workstation serves the production frontend and API together through `scripts/run-local.sh`.

## Checks and production build

```sh
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

Regenerate API declarations after contract changes with `npm --prefix frontend run generate:api`. Generated files come from `specs/openapi.yaml`.

## Browser checks

Integration scripts are listed in `package.json`. Browser tests require Playwright and Chrome; `EVORA_PLAYWRIGHT_MODULE` and `EVORA_CHROME_PATH` can select local installations. `EVORA_BROWSER_BASE_URL` sets the workstation origin for scripts that support it. Live-account tests require a fresh disposable backend, never an investigator's database.

`test:map-views` uses synthetic API data and tiles by default. Set `EVORA_LIVE_MAP_TILES=1` to explicitly test external map providers.

## Assets

Application branding uses `public/brand/`, matching `desktop/icon.png` and `desktop/icon.ico`. `public/maps/` contains the offline overview basemap and attribution. The build copies public assets and MapLibre worker files into `dist/`.
