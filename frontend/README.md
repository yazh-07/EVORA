# G01B frontend skeleton

Task **G01B / Checkpoint 0**, `whale2186`, branch `feat/g01b-frontend-skeleton`,
common contract/base `e0257a6ad231105b93ae98a97f176ed233a25412`.

The React + TypeScript application in `frontend/src` creates the foundational
investigation workspace shell. It generates client types from `specs/openapi.yaml`
(draft 0.3.0) and adheres to `DESIGN.md` tokens. It exposes no simulated domain
data or unapproved features.

## Tested environment and setup

The local tested baseline is **Node 26.7.0** and **npm 11.19.0**.
`frontend/package.json` pins dependencies: React 19.3.0, React DOM 19.3.0,
TypeScript 5.9.3, esbuild 0.28.1, and openapi-typescript 7.10.1.

Run from the repository root:

```sh
npm --prefix frontend install
npm --prefix frontend run generate:api
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

## Available scripts

- `npm --prefix frontend run generate:api`: Generates TypeScript interfaces from `specs/openapi.yaml` into `frontend/src/api/schema.d.ts`.
- `npm --prefix frontend run check:api`: Verifies that `src/api/schema.d.ts` matches `specs/openapi.yaml`.
- `npm --prefix frontend run typecheck`: Runs `tsc --noEmit` across all TypeScript files.
- `npm --prefix frontend run test`: Runs unit tests via Node test runner (`node --test test/*.test.mjs`).
- `npm --prefix frontend run build`: Checks API freshness, runs typecheck, and bundles assets with esbuild into `dist/`.
- `npm --prefix frontend run dev`: Runs local dev server on `http://127.0.0.1:5173`.

## How you can test it

1. `npm --prefix frontend run typecheck` — exit 0, no diagnostic errors.
2. `npm --prefix frontend run test` — exit 0, 2 passing tests verifying DOM rendering and honest unavailable access.
3. `npm --prefix frontend run build` — exit 0, produces `dist/assets/main.js` and `dist/assets/main.css`.
4. Negative check: Modify `frontend/src/api/schema.type-test.ts` to pass an invalid property to an API response type; `npm --prefix frontend run typecheck` will fail with compile-time error.
