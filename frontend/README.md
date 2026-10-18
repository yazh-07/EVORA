# G01B frontend skeleton

Task **G01B / Checkpoint 0**, `whale2186`, branch `feat/g01b-frontend-skeleton`,
common contract/base `e0257a6ad231105b93ae98a97f176ed233a25412`.

The React + TypeScript application in `frontend/src` creates the foundational
investigation workspace shell. It generates client types from `specs/openapi.yaml`
(draft 0.3.0) and adheres to `DESIGN.md` tokens. It exposes no simulated domain
data or unapproved features.

## Tested environment and setup

G01C's tested Linux baseline is **Node 22.23.3** and **npm 12.2.0**, matching
`engines` and `packageManager` in `frontend/package.json`. Earlier G01B notes
reported Node 26.7.0/npm 11.19.0; those are historical, not this supported baseline.
`frontend/package.json` pins dependencies: React 19.3.0, React DOM 19.3.0,
TypeScript 5.9.3, esbuild 0.28.1, and openapi-typescript 7.10.1.

Run from the repository root:

```sh
node --version
npm --version
npm --prefix frontend ci
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Expected versions: `v22.23.3` / `12.2.0`. `npm ci` installs the committed lockfile;
routine setup checks generated declarations rather than rewriting them.
Clean Linux installation, API freshness, typecheck, both render tests and build
passed in G01C. `generate:api` is for coordinated contract/type updates only.

## Windows PowerShell setup and run

Prerequisites: Windows x64, PowerShell 7, Git, Node **22.23.3** on PATH, registry
access and a writable checkout. The shared coordination/backend checks additionally
require CPython **3.14.8** and `requirements.txt`; see `backend/README.md`.
Run these commands from the repository root in a fresh checkout:

```powershell
node --version
npm.cmd install --global npm@12.2.0
npm.cmd --version
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run check:api
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run dev
```

Expect `v22.23.3`, npm `12.2.0`, no type diagnostics, **2 passing tests** and
`frontend/dist/index.html`, `frontend/dist/assets/main.js` and `main.css`.
Open `http://127.0.0.1:5173` while the dev server runs: the workspace shell shows
no selected case and unavailable case access, without mock domain data or API
traffic. Stop with Ctrl+C. `npm.cmd`/`npx.cmd` bypass PowerShell's script-wrapper
execution-policy issue without changing machine policy. npm global installation
requires write access to its configured prefix.

The shared `.github/workflows/contract.yml` runs all coordination/backend/frontend
checks on `ubuntu-latest` (Bash) and `windows-latest` (PowerShell), with these exact
Node/npm pins and Python from `backend/.python-version`. Native Windows and hosted
CI execution are pending; configuring a matrix is not a passing runner result.
Exact full-suite commands and actual Linux evidence are in
[G01C verification](../docs/PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18).

Known limits: only the pinned runtime/toolchain is covered by local evidence.
Keep optional dependencies enabled so esbuild receives the appropriate native
binary for the OS; do not copy `node_modules` between Windows and Linux. The local
npm 12 install warned that esbuild's postinstall was blocked by its script policy;
build/test still passed using the installed platform binary, without relaxing
that policy. Native Windows/browser rendering and accessibility have not been
verified in this session. No auth, API client runtime, models or domain workflows
exist yet; the server smoke and static render tests cover the skeleton only.

## Available scripts

- `npm --prefix frontend run generate:api`: Generates TypeScript interfaces from `specs/openapi.yaml` into `frontend/src/api/schema.d.ts`.
- `npm --prefix frontend run check:api`: Verifies that `src/api/schema.d.ts` matches `specs/openapi.yaml`.
- `npm --prefix frontend run typecheck`: Runs `tsc --noEmit` across all TypeScript files.
- `npm --prefix frontend run test`: Runs unit tests via Node test runner (`node --test test/*.test.mjs`).
- `npm --prefix frontend run build`: Checks API freshness, runs typecheck, and bundles assets with esbuild into `dist/`.
- `npm --prefix frontend run dev`: Runs local dev server on `http://127.0.0.1:5173`.

## How you can test it

- [ ] Run `npm --prefix frontend ci`, then `npm --prefix frontend run check:api`
  and `npm --prefix frontend run typecheck`: exit 0, declarations fresh, no type errors.
- [ ] `npm --prefix frontend run test`: exit 0, **2 passing tests** rendering the
  real shell and checking honest unavailable access without API traffic.
- [ ] `npm --prefix frontend run build`: exit 0, assets appear under `frontend/dist/`.
- [ ] Run `npm --prefix frontend run dev` and open the URL above; stop with Ctrl+C.
  Linux HTTP startup/asset delivery is recorded separately from browser inspection.
- [ ] Failure case on Windows, using a temporary stale declaration only:

  ```powershell
  $probe = Join-Path $env:TEMP 'evora-g01c-stale-api.d.ts'
  Set-Content -Path $probe -Value '// Synthetic stale declaration' -Encoding utf8
  npx.cmd --yes openapi-typescript@7.10.1 specs/openapi.yaml -o "$probe" --check
  # Expect a nonzero exit and a stale/not up-to-date declaration error.
  Remove-Item -LiteralPath $probe
  ```

  The source spec and committed generated declarations stay unchanged. The
  equivalent Linux failure was exercised; PowerShell execution remains pending.
- [ ] Run `git diff --check`: exit 0. For the complete checkpoint regression,
  follow the G01C verification record linked above.

Generated `dist/`, `node_modules/` and `.test-build/` are local build artifacts;
tests use synthetic content only. No original evidence is needed.
