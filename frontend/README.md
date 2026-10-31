# U04 original download — 2026-10-31

U04 / Checkpoint 1A / M4 JebasJ, branch `feat/u04-evidence-download`.
Original draft d24312f was checkpointed and updated to verified shared base
**d2879c6e1e236add391fb6af40480b9940d22555**. User explicitly authorized finishing,
committing, pushing and merging this task. Integration status is in ROADMAP.
The older session notes below are historical.

Selected evidence metadata now offers **Download original**. An explicit click
uses the existing authenticated downloadEvidence operation with no-store Fetch.
The controller checks original byte size and SHA-256 against selected metadata
before requesting an attachment save via a short-lived Blob URL. It never
renders evidence HTML, opens an original inline or persists bytes/tokens in
browser application storage. The browser's user-requested downloaded file is
intentional output, not an application cache. URL cleanup is idempotent and
runs on timeout, retry, failure or unmount. Selection/case/session changes abort
pending reads and discard late responses; pending clicks cannot duplicate reads.
Success says download requested, not that the browser completed a disk save.
Empty originals are supported. Size/hash mismatch stops the save. Missing or
revoked access has a safe error and a manual retry; no invented HTTP interface.

## How you can test U04

PowerShell at repository root; use pinned Python 3.14.8, Node 22.23.3, npm
12.2.0 and existing requirements/lockfile. Install if needed with
`python -m pip install -r requirements.txt` and `npm.cmd --prefix frontend ci`.
This task reused installed dependencies; no clean reinstall claim.

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
$env:EVORA_TEST_PYTHON = (Get-Command python).Source
Push-Location frontend
node test/cases.integration.mjs
Pop-Location
```

Expect **48 frontend tests passing** and **PASS U04 real F05** plus U02/U02B/U03
regression messages. The real integration creates synthetic cases/evidence,
retrieves original binary bytes through the actual download controller,
compares size/hash/bytes, handles empty original and denies foreign originals.
It cleans its own server and temporary database. The save callback is a
labeled test boundary there; actual browser saving was tested separately.
Negative Fetch/save/DOM doubles test size/hash mismatches (no save), network/
500/404/protocol errors and retry, duplicate clicks, session/selection disposal,
StrictMode-style reconnect and temporary URL cleanup. These are not real
production identities, backend failures or browser-save measurements.

To test the actual browser, serve the unchanged real backend with the existing
local same-origin synthetic wrapper:

```powershell
$env:EVORA_API_BASE_URL = 'http://127.0.0.1:8766'
npm.cmd --prefix frontend run build
$u04Demo = Join-Path $env:TEMP ("evora-u04-demo-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $u04Demo | Out-Null
$u04Db = Join-Path $u04Demo 'cases.sqlite3'
python frontend/test/serve-cases.py --database $u04Db --port 8766
```

In a second PowerShell terminal make a synthetic original:

```powershell
$u04Fixture = Join-Path $env:TEMP ("u04-original-" + [guid]::NewGuid() + '.bin')
[IO.File]::WriteAllBytes($u04Fixture, [byte[]](0,255,10,65))
Get-FileHash -Algorithm SHA256 -LiteralPath $u04Fixture
```

1. Open `http://127.0.0.1:8766`, use **u02-synthetic-one**, and create
   **Synthetic U04 review**. In its evidence form choose the generated fixture,
   kind **document**, source **Synthetic U04 source**, then **Upload evidence**.
2. Select the evidence. Expect ID, filename, **4 bytes** and its source SHA-256.
   Select **Download original**. Expect a verified/requested message and a file
   in browser downloads. Compare its hash to the source using Get-FileHash.
3. Use keyboard Tab/Enter to reach/activate the button. Check desktop and narrow
   widths: metadata wraps, controls remain visible and no horizontal overflow.
4. Failure case: with the inspector still selected, stop the local server and
   select Download original. Expect a connection error and no successful save.
   Restart the same synthetic database and manually retry. This outage branch
   was covered by doubles, not a browser outage during Codex execution.
5. End session and enter **u02-synthetic-two**: no access to the first actor's
   case or download. Reload clears token/case state. Actual revoked membership
   was also exercised in Codex's disposable browser fixture: real F05 returned
   404 and the inspector showed an unavailable-original error, with no save.

Stop the wrapper with Ctrl+C. Remove only the exact synthetic paths you created
including the uniquely created `$u04Demo` directory and `$u04Fixture`, plus the corresponding
synthetic file from browser downloads. Reset EVORA_API_BASE_URL if desired.

Codex's actual browser fixture was **25 bytes**, SHA-256
`fd57bc669c70f7ec86ac82d14b89edf1cb022a38eaba2e754f4c3d84c4d2438f`.
A real saved file was read back from Downloads and matched both values. Desktop
and 390x844 narrow layout were inspected; narrow content/client width both 375.
48 frontend tests pass. Backend: 70 run, 69 pass/1 skip (Windows cannot create
symlink for F05 escape test). Formal screen-reader coverage, full browser matrix,
production authentication, clean reinstall and new hosted CI are unverified.
Full FEATURE_SCOPE including approved transcription additions is unchanged.
Checkpoint 1A still needs F06/F07/F09 and the explicitly assigned shared I00
integration gate before automatic later-checkpoint work. No next task is taken.

---


## U02B reconciliation — 2026-10-31

The user's reconciliation request is implemented on `feat/u02b-reconcile` in
an isolated worktree based on freshly fetched shared commit
**d24312f939877e6959c6ff46d3e1d81051e474a6**. The original
`EVORA` worktree/`feat/u02b-case-creation` and every uncommitted local file remain
untouched. This supersedes the earlier claim that F03/F04 block M4: actual
merged ancestry now includes U02B 1b7d928, F03 e5273a6, F04 69f2e82, U03
c5c9b5a and F05 d24312f. Older In Progress session records are historical;
this reconciliation does not assign or rewrite another contributor's task.

Reused the integrated CaseCreation/createCaseStore implementation rather than
adding the older parallel form/store. Carried over the remaining local U02B
improvements: codepoint title/description limits (including supplementary
Unicode), removal of conflicting UTF-16 HTML maxlength limits, safe 400 field
failure guidance and uncertain network/server-response guidance to refresh
before another explicit POST. No automatic write retry or new wire fields.
U03 EvidenceWorkspace and all newer F03/F04/F05 producers remain present.
Full FEATURE_SCOPE and approved additions, contract, backend and dependency
manifests are unchanged. No U04 implementation is included.

Actual checks: **41 frontend tests pass**, no skips; freshness/typecheck/build,
contract lint/bundle/generated strict types and DESIGN pass. Real HTTP/FastAPI/
SQLite integration passes U02/U02B creation and new Unicode boundaries plus
U03 multipart upload/hash/metadata/50MiB-limit/400/404/413 regressions. Backend
suite runs **70 tests: 69 pass, 1 skipped**. Skip is F05's symlink-escape test:
this Windows account cannot create symlinks. No success claimed for that case.
State/failure tests use explicit Fetch doubles; real integration uses real
producers with synthetic identity/data. No new browser, clean npm install,
production identity or hosted CI claim. Existing installed node_modules is
reused via an ignored junction; no dependency change. Initial new assertion
incorrectly matched the word description with /script/; narrowed the pattern,
then all frontend tests passed.

**In Progress**, uncommitted reconciliation pending review/integration.
Original draft is preserved for comparison and must not be blindly reapplied
on top of the shared implementation. No stage/commit/push/merge was performed.
Next dependency-ready M4 row is U04, since U03 and F05 are integrated; it still
needs its own fresh scoped assignment. Do not start it during reconciliation.

How you can test this worktree (PowerShell, pinned Node/Python on PATH):

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
$env:EVORA_TEST_PYTHON = (Get-Command python).Source
Push-Location frontend
node test/cases.integration.mjs
Pop-Location
```

Expect 41 frontend tests and PASS messages for case creation and U03 intake.
Synthetic boundary input is 200 supplementary Unicode title characters and a
5000-character description: create succeeds, source text survives, case appears
in the actual list. Add one title character: local validation rejects with no
extra POST. Network/500 failure tests must show uncertainty/refresh guidance
and exactly one write attempt. Existing integration cleans its synthetic DB
and server. The original checkout's local edits remain unchanged.

---

# U02 case list and detail UI — 2026-10-31

U02 / Checkpoint 1A / M4 / JebasJ, branch `feat/u02-case-list-ui`.
Common base: `909009d21198fd751db49863f581b032875fa5e0`.
Real U01/F00/F01/F02 are merged in this base. Earlier U01 notes below describe
its original fixture-only handoff. U02 is **Complete**, integrated by user-authorized
merge `9f2cc8ac64426ef2b0bb9d917fd7afdb777b606f` into `docs/coordination-foundation`
and verified with real HTTP/SQLite smoke. No Checkpoint 1A closure is claimed.

The UI reads `listCases` and `getCase` through the existing generated typed
client. It shows API totals, 20-item pages, empty/loading/retry states and
selected case details. New pages clear prior detail; stale/cancelled responses
cannot replace newer data. The provider remounts all case state on a token
change, logout or 401. Tokens are entered in a password field, reset at submit,
and retained only in the existing memory client. There is no token issuer,
case creation, evidence upload or persistent token/evidence storage added.

## How you can test it

Use PowerShell at the repository root with **Python 3.14.8**, **Node 22.23.3**
and **npm 12.2.0** on PATH. In this checkout Codex used the matching runtimes
under `../work/evora-tools/`; Python's SQLite reports 3.50.4. The following
commands use your PATH executables. The existing pinned requirements and
frontend lockfile are unchanged.

```powershell
python -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
$env:EVORA_TEST_PYTHON = (Get-Command python).Source
Push-Location frontend
node test/cases.integration.mjs
Pop-Location
```

- Expect **25 frontend tests passing**, including synthetic transport failure,
  malformed-page, old-session/late-response, 404, 401 and escaped-content tests.
- The explicit integration command starts a loopback server with real
  FastAPI/F00/F01/F02/SQLite, creates **21 synthetic actor-one cases and one
  actor-two case via createCase**, and exercises the actual client/store.
  Expect `PASS U02 real HTTP/SQLite...`: 20+1 distinct records, correct totals,
  correct detail, empty/out-of-range pages, no cross-actor cases, identical
  foreign/missing 404s, invalid limit 400 and invalid-token 401.
- It stops its server and removes only its own temporary synthetic database.
  Unit tests use disclosed Fetch doubles; the integration command has no
  case/membership producer double. Authentication is the approved synthetic
  verifier, not a production identity provider.

For browser verification, build for a same-origin local demo (the existing
backend does not configure cross-origin browser access). Use a fresh synthetic
SQLite path and leave this server running in the first terminal:

```powershell
$env:EVORA_API_BASE_URL = 'http://127.0.0.1:8765'
npm.cmd --prefix frontend run build
$u02Database = Join-Path $env:TEMP ("evora-u02-demo-" + [guid]::NewGuid() + '.sqlite3')
python frontend/test/serve-cases.py --database $u02Database --port 8765
```

In a second terminal, seed synthetic records through the real API:

```powershell
$headers = @{Authorization='Bearer u02-synthetic-one'}
1..21 | ForEach-Object {
  $body = @{title="Synthetic browser case $_"; description='Permitted synthetic fixture'} | ConvertTo-Json
  Invoke-RestMethod http://127.0.0.1:8765/api/v1/cases -Method Post -Headers $headers -ContentType application/json -Body $body | Out-Null
}
```

- Open `http://127.0.0.1:8765`, enter **u02-synthetic-one**, and select
  **Open cases**. Expect total 21 and page 1 showing 20 cases. Select a title:
  the inspector shows its real ID, description and original created timestamp,
  and receives focus. **Back to cases** returns to the list. **Next** shows the
  remaining case and disables Next; Previous returns to the first page.
- **End session**, then enter **u02-synthetic-two**. In this browser demo it has
  no cases: expect total zero and an honest empty state. No actor-one records
  remain. Reload returns to token entry, because the token is memory-only.
- Failure case: enter **invalid-synthetic-token**. The real API returns 401;
  the client clears the session and the UI returns to token entry without old
  case data. Network failures instead show a safe error and **Try again**.
- Use Tab/Enter to operate controls. Inspect at narrow and desktop widths;
  controls wrap, IDs break safely, and detail selection moves focus to the
  inspector so it can be reached below the list on narrow layouts.
- Stop the demo with Ctrl+C. Remove the exact synthetic database named by
  `$u02Database` using `Remove-Item -LiteralPath $u02Database` after shutdown.
  Reset the build origin with `Remove-Item Env:EVORA_API_BASE_URL` if desired.

Codex exercised the frontend tests/build, explicit real HTTP integration and
browser list/detail/pagination, empty-account, invalid-token, reload/logout and
detail-focus steps on Windows. The observed browser viewport was about 700px;
full desktop/mobile breakpoint coverage, formal screen-reader testing, clean
frontend reinstall, new hosted CI and production authentication were not run.
The demo static mount/no-store middleware is test tooling, not a deployment or
CORS policy change. No real evidence or external service is used.

Next M4 task is **U02B**, on the updated verified shared base with its own scoped assignment. The entire initial scope and approved additions remain unchanged in
`docs/FEATURE_SCOPE.md`.

---

# EVORA frontend skeleton and shared API client

## U01 authenticated client — independent work, awaiting F00 integration

**U01 / Checkpoint 1A / M4 / JebasJ**, branch `feat/u01-authenticated-api-client`,
common contract/base `6496c5e9e17f2000b64a64f79d2fb166c6ce2094`.
The real G01B skeleton is present; F00 is not implemented in this base.
Client tests use explicitly synthetic, generated-schema-derived Fetch/localhost
fixtures. They do not establish real backend authentication, membership or CORS.
U01 remains **In Progress**, pending review and real producer integration.

`src/api/client.ts` derives method/path/path-parameter/query/header/body/result
types from the committed generated `schema.d.ts`. It adds no routes or wire
schemas and installs no new packages. JSON responses, multipart requests and
in-memory Blob downloads share one transport; this is not implementation of the
later upload, processing, analysis or source-playback workflows. Compile-only
negative assertions in `client.type-test.ts` reject invented routes/fields,
missing path parameters/idempotency keys, and an analysis request body.
Successful JSON has compile-time contract types, not full runtime schema
validation. Invalid JSON/content types fail as protocol errors.

`ApiProvider` supplies one client to the React tree. `useApiClient()` obtains it
in future views. The public server origin is configured when building/starting:

```powershell
$env:EVORA_API_BASE_URL = 'http://127.0.0.1:8000'
npm.cmd --prefix frontend run dev
```

The default is the OpenAPI local server origin `http://127.0.0.1:8000`.
Supply an HTTP(S) origin, optionally with a trailing slash, without credentials,
path, query or fragment. Generated paths already contain `/api/v1`; do not append
it to the base URL. Restart/rebuild after changing the environment variable.
This value is public in the browser bundle; never put a token in it.
Real browser requests need same-origin hosting or an explicitly configured
backend CORS policy; no permissive backend change is made by this task.

The client starts without a token and makes no startup request. A future
authorized caller supplies a token with `client.setToken(token)`; there is no
invented login/refresh endpoint or built-in demo credential. Tokens are held in
a closure, never persistent browser storage. `clearToken()`, token replacement,
and HTTP 401 abort pending requests and invalidate late data from the old
session. The provider remounts descendants on session changes to discard prior
actor/case UI state. That React browser remount behavior still needs browser
integration verification; session invalidation and provider rendering are
covered by the automated tests.

All requests omit cookies, disable HTTP caching/referrers, and refuse redirects;
the configured origin cannot be changed through a request. Required caller
idempotency keys are preserved; the client does not retry writes or issue keys.
`ApiHttpError` exposes actual HTTP status and, where valid, `ApiError`; 401/404
use the non-leaking C-03 messages. Other non-JSON/malformed error bodies are not
exposed as a wire error. `ApiClientError.kind` distinguishes local configuration,
request, authentication, changed-session, protocol and network failures.
Cancellation throws `AbortError`. Error messages do not include request URLs,
tokens, evidence or raw server bodies. Consumers must render server error text
as untrusted plain text and must not log private payloads.

### How you can test U01

From the repository root with pinned Node 22.23.3/npm 12.2.0 and dependencies
installed (use `.\.cache\setup\evora-shell.cmd` on this prepared local machine):

- [ ] `npm.cmd --prefix frontend run check:api` and
  `npm.cmd --prefix frontend run typecheck`: exit 0, committed types fresh;
  generated request/result signatures and compile-only negatives pass.
- [ ] `npm.cmd --prefix frontend run test`: expect all frontend tests to pass.
  Synthetic inputs are two UUID cases, two memory-only test tokens, one 5-byte
  artifact and schema-derived `ApiError`/queued-run responses. Tests exercise
  JSON/query/headers/multipart/byte read-back, shared error handling, no-token
  rejection, cancellation, token replacement/logout, late old-actor responses,
  and an actual Fetch request to a temporary localhost fixture server.
- [ ] Failure case: after the test build, from repository root run
  `node --test --test-name-pattern="401 invalidates" frontend/test/api-client.test.mjs`.
  Expect one passing selected test: synthetic HTTP 401 clears the token, aborts
  another pending request, rejects late old-session data and prevents another
  request. No real F00 authorization is claimed.
- [ ] `npm.cmd --prefix frontend run build`: exit 0, assets under
  `frontend/dist/`. `npm.cmd --prefix frontend run dev` serves the unchanged
  no-case/unavailable-access workspace at `http://127.0.0.1:5173`; there is no
  case sign-in/list/upload feature yet. Stop with Ctrl+C; unset the temporary
  origin setting with `Remove-Item Env:EVORA_API_BASE_URL` if it was set.
- [ ] Run Checkpoint 0 regressions using the shared workflow: OpenAPI
  lint/bundle, scratch generated strict TypeScript compilation, coordination
  verifier/122 Python tests, 14 warning-strict backend tests, DESIGN lint and
  whitespace checks. On Windows use the explicit DESIGN binary alias:
  `npx.cmd --yes --package @google/design.md@0.4.0 designmd lint DESIGN.md`.

Test servers close automatically and use no real evidence or external provider.
After review, integrate and verify against real F00 before claiming U01 Complete.
U02 additionally waits for F02; U02B/U03/U04 retain their existing dependencies.
The entire initial scope and approved speech/correction addition remain in
FEATURE_SCOPE, unchanged by this client task.

## G01B foundation verification record

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

## U02B case creation

After opening an authorized session, the New case form accepts a required title
(up to 200 characters) and an optional description (up to 5000 characters).
Empty or whitespace-only titles show `Title cannot be empty` without an API
request. Inputs and submit are disabled during creation/list refresh, with a
store guard against duplicate submissions. API error messages render as text;
failed submissions retain inputs for correction. No automatic write retry occurs.

A successful createCase response clears both fields, refreshes listCases and
selects the returned case in the inspector, moving focus to Case details. A
created case outside the first list page remains visible in the inspector.
If list refresh fails, confirmed case details remain visible with a retry message;
no case total is invented. Session replacement/logout discards pending results
and remounts the form without retaining the prior actor's input.

Run from repository root:

```sh
npm --prefix frontend run test
npm --prefix frontend run build
(cd frontend && node test/cases.integration.mjs)
```

Unit tests use schema-derived Fetch doubles plus server-rendered markup. The
integration runner starts the existing local server with real FastAPI/SQLite,
synthetic identities and a temporary database; it verifies creation HTTP 201,
immediate list read-back, title rejection HTTP 400 and actor isolation as well
as the existing U02 pagination/detail checks. The runner removes its own database.
For manual browser testing, use the same-origin demo setup above: submit blank
and whitespace titles, create a synthetic title/description, inspect the new
case and cleared inputs, and tab through labels/controls and focused details.
No new browser, screen reader, Windows or hosted CI verification is claimed.

## U03 evidence upload and metadata inspection

After opening an authorized session and selecting a case (or creating one),
the workspace shows its evidence list and a one-file upload form. Choose the
original file, one of the nine contract kinds and a source label (maximum 200
characters). Acquisition date/time is optional and explicitly entered in UTC;
leave it blank if unknown. Upload sends actual multipart bytes to F03. The
current backend limit is 50 MiB; it stores opaque originals without validating
content format. A kind/MIME label does not verify content or source reliability.

Missing files and blank/whitespace labels produce accessible local errors.
Inputs and submit are disabled while uploading. Server errors, including size
and unsupported-type responses, appear as escaped alert text. After success,
the form resets, the first evidence page refreshes and the inspector shows the
confirmed Evidence ID, case ID, server SHA-256, byte size, kind, filename, media
type and source/acquisition/upload metadata. A failed list refresh retains
confirmed upload metadata and offers refresh without repeating the write.

The list supports previous/next pages using actual API totals. Selecting an
item fetches `getEvidence`; an empty case says “No evidence uploaded yet for
this case”. Changing case/session discards prior data and pending results.
No evidence/token browser persistence is introduced. Original download belongs
to U04/F05, and processing is not implemented by U03.

Run from the repository root:

```sh
npm --prefix frontend run test
npm --prefix frontend run build
EVORA_TEST_PYTHON=/tmp/evora-f03-pinned/bin/python node frontend/test/cases.integration.mjs
```

Use your own Python environment with `requirements.txt` installed in place of
that local interpreter path. The integration helper starts a localhost real API,
uses synthetic identities/bytes, and removes its owned temporary SQLite/private
storage afterward. It verifies 201/hash/size/list/detail, local missing-file and
blank-label validation, real 400/413 and case/actor 404 isolation, alongside
U02/U02B regressions. Unit tests use synthetic Fetch responses and static React
rendering, including 400/413/415 alerts, escaping and request races; they do not
establish browser events/focus/reset behavior. Browser and native Windows
verification remain outstanding. U03 remains In Progress pending review and
integration; no Checkpoint 1A closure is implied.

### U02B reconciliation publication authorization — 2026-10-31

The user explicitly authorized committing, pushing and merging this
reconciliation into the configured shared GitHub repository yazh-07/EVORA.
Earlier no-publication statements describe the previous handoff and are
superseded by this request. The checked combined candidate passes 41 frontend
and 122 coordination tests, plus real case/create/U03 upload integration and
build/contract/types/DESIGN. Backend results remain 69 pass and 1 Windows
symlink-permission skip. Preserve the original dirty U02B checkout.

A local worktree inventory found U04 already assigned to JebasJ and In Progress
on feat/u04-evidence-download in work/evora-u04. Continue that existing task;
do not duplicate it or overwrite its edits. No U04 work is included here.

### U02B reconciliation integrated — 2026-10-31

**Complete:** user-authorized reconciliation integrated into
`docs/coordination-foundation` at merge **328da3370e6033465297117be9d31c166f7817ea**,
containing task commit fe2af26. Post-merge real HTTP/SQLite case-creation and
U03 multipart/hash/metadata/400/404/413 smoke passes on that merge commit.
Pre-merge checks: 41 frontend and 122 coordination pass; backend 69 pass,
1 Windows symlink-permission skip. Contract/types/build/DESIGN pass with the
existing missing-license warning. New hosted CI is not verified. This record
supersedes earlier reconciliation In Progress/no-publication statements;
Checkpoint 1A remains open. Original dirty checkout and active U04 worktree
are untouched. Next work is continuing the existing assigned U04 task, not
starting a second U04 implementation. No U04 changes were merged here.
