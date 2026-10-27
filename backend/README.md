# EVORA backend

## F02 authorized case listing

`GET /api/v1/cases` (`listCases`) requires `authenticated_actor` and returns
200 `CasePage` with `items`, `total`, `limit`, `offset`. Only current SQLite
`case_members` memberships for the authenticated actor are returned. Cases sort
by `created_at DESC, id ASC`; absent descriptions are omitted. Count and page
share one database read snapshot. `total` counts all accessible cases before
pagination. No cases or an offset at/beyond total returns empty `items` while
preserving the total and requested pagination values.

`limit` defaults to 20 (1–100), `offset` to 0 (minimum 0). Invalid pagination
returns 400 `{"code":"INVALID_INPUT","message":"Invalid request input."}`;
missing/invalid bearer credentials return the existing 401 ApiError.
No production identity provider is configured by default.

To test with synthetic identities and automatically cleaned temporary SQLite:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_cases -v
```

Use the pinned requirements environment. Expect 14 tests to pass, including
23-case pagination with timestamp ties, actor isolation/revocation, empty pages,
limit boundaries and rejected `limit=0/101/abc`, `offset=-1`, missing/invalid auth.
See [F02 verification](../docs/PREIMPLEMENTATION_REVIEW.md#f02-verification--2026-10-25).

## F01 case persistence (current behavior)

**F01 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f01-case-persistence`, exact common base
`86f14eedc575032d636a77233b19f13bf665c077` (includes merged F00).
The earlier F00/G01 sections below retain their historical verification results;
F01 supersedes their statements that domain routes/tables are absent.

Startup initializes `cases(id TEXT PRIMARY KEY, title TEXT NOT NULL,
description TEXT, created_at TEXT NOT NULL)` and
`case_members(case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
actor_id TEXT NOT NULL, PRIMARY KEY(case_id, actor_id))`. Both writes commit in
one SQLiteDatabase unit of work; failed membership insertion rolls back the case.
Connections remain request-owned and always close. Startup is repeatable and
preserves existing cases. SQLite is authoritative; there is no in-memory store.

- `POST /api/v1/cases` (`createCase`) requires `authenticated_actor` and returns
  201 with a UUID4, unchanged title/description and UTC `created_at`. The creating
  actor receives membership. Title is a strict string of 1–200 characters and
  must contain non-whitespace text; optional description is a strict string of
  at most 5000 characters. Explicit null and additional properties are rejected.
  Absent description is omitted from the response.
- `GET /api/v1/cases/{caseId}` (`getCase`) uses `require_case_access` and returns
  the persisted Case. `SQLiteCaseAccess` is the default adapter, queries current
  membership on every request and uses the same indexed query for foreign and
  nonexistent UUIDs. Both denials use the existing fixed 404 body and no-store
  headers. Storage failures propagate as server errors. Identical code/query
  paths avoid existence-specific branches; no constant-time guarantee is claimed.

Authentication still defaults to rejecting all tokens. Configure the existing
`SyntheticTokenVerifier` privately for the two local synthetic actors; no token
issuance or production provider is introduced. Explicit case-access injection
remains available. F02 adds listing above; upload remains outside these tasks.

The unchanged contract currently requires flat `ApiError` bodies, for example
`{"code":"NOT_FOUND","message":"Resource not found."}`. Validation uses the
existing flat `INVALID_INPUT` mapping. The task request's nested `error` envelope
and `BAD_REQUEST` conflict with that contract and F00/U01 consumers; the F01
assignment records the pending decision. Current checks verify the existing
contract, not the requested alternate envelope.

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_cases
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
```

Use the pinned requirements environment described below. Focused tests use real
FastAPI, file-backed SQLite, synthetic identities and temporary directories that
clean up after tests. They cover persistence across app restart, absent optional
fields, validation/authentication/path negatives, same-response case isolation,
revocation, rollback, foreign keys/cascade and real membership-storage failure.
Case and error responses validate against the bundle when configured. See the
[F01 verification record](../docs/PREIMPLEMENTATION_REVIEW.md#f01-verification--2026-10-25)
for actual results and limits. Next M1 task is F02 after F01 acceptance;
Checkpoint 1A and browser integration are not complete.


## F00 authentication and case-access dependencies

**F00 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f00-auth-case-guard`, common contract/base
`f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029`.

`backend.auth.authenticated_actor` accepts one well-formed HTTP bearer header.
Missing, malformed, duplicate or rejected credentials return HTTP 401 with
`{"code":"UNAUTHORIZED","message":"Authentication required."}` and
`WWW-Authenticate: Bearer`. Query parameters, cookies and actor headers cannot
supply identity. `require_case_access` validates the contract's UUID `caseId`
path parameter and checks current membership before the route handler runs.
Foreign and missing cases return identical HTTP 404 bodies and headers:
`{"code":"NOT_FOUND","message":"Resource not found."}`. Both access errors
use `ApiError` and `Cache-Control: no-store`; malformed authenticated case IDs
use the existing safe 400 mapping. No submitted credential or case ID is echoed
by these errors or logged by the guards.

The app factory accepts keyword-only `token_verifier` and `case_access` adapters.
It defaults to rejecting every token and denying all case access. Explicit local
development callers can supply `SyntheticTokenVerifier({token: actor_id})` for
C-03's two synthetic identities, `investigator-1` and `investigator-2`. Supply
opaque tokens privately; actor IDs themselves are not built-in credentials.
The verifier copies configuration and retains token digests, not plaintext
tokens. No shared token, token issuance/login route, automatic expiration or
production identity provider is implemented. Replacing the verifier applies on
the next request without a cached identity. Future adapters must enforce their
selected expiry/revocation policy and return `None` for rejected credentials.

Future case routes use `Depends(authenticated_actor)`; case-scoped routes use
`Depends(require_case_access)`, whose immutable internal result carries the
authenticated actor and authorized case UUID. F01 must supply a `CaseAccess`
adapter whose `allows(actor_id, case_id)` returns true only for an existing case
with that actor's authoritative membership. Membership is checked on every
request; storage errors propagate as server failures without reaching the route
handler. This dependency adds no persistence schema or public operation. Child
resource producers must still check their own same-case joins. Protect every
future route explicitly; F00 does not automatically authenticate arbitrary routes.

### How you can test F00

Use the pinned Python 3.14.8 environment and `requirements.txt` installation
described below. On the locally prepared machine, open
`.\.cache\setup\evora-shell.cmd` from the repository root to select the isolated
Python/Node/npm toolchain. In that CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_auth -v
python -W error::ResourceWarning -m unittest backend.tests.test_auth.AuthenticationTests.test_foreign_and_missing_cases_have_identical_status_body_and_headers -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expected: **19 focused F00 tests**, **1 selected foreign/missing failure-case
test**, and **33 combined backend tests** pass without skips. The tests exercise
real FastAPI dependency resolution, HTTPX ASGI transport, the shared contract's
`ApiError` schema and real temporary file-backed SQLite. Inputs are two synthetic
tokens/actors and two UUID cases plus one missing UUID. Test-only `/_test/...`
routes and SQLite membership tables stand in for the absent F01 producer; they
are never registered/created by the application factory. Denied synthetic writes
leave the test table empty; a failed membership lookup returns a server error
and never reaches a protected handler. Temporary databases clean up automatically.

The default server still exposes no public operations: `GET /` returns 404,
and no sign-in/case/evidence UI can be tested end to end yet. F01 persistence,
real U01/browser/CORS integration, production authentication and remote CI on this
uncommitted branch are unverified. Full initial scope and approved additions are
unchanged. F00 stays In Progress pending review and real producer integration.

## G01 backend skeleton

Task **G01 / Checkpoint 0**, `whale2186`, branch `feat/g01-backend-skeleton`,
common contract/base `1721bfff9640263d2799434455cdb9c4f345ac35`.

The factory in `backend.app` creates a FastAPI application and checks a real
file-backed SQLite connection at startup. It registers no HTTP routes, including
health, documentation or generated OpenAPI endpoints. Domain APIs and schemas
start in later tasks. `specs/openapi.yaml` draft 0.3.0 remains the HTTP authority.

## Tested environment and setup

The local tested baseline is **CPython 3.14.8**, recorded in
`backend/.python-version`, with **SQLite 3.54.0** from this Python build.
`requirements.txt` pins runtime/test packages and their transitive dependencies:
FastAPI 0.143.1, Starlette 1.8.0, Pydantic 2.14.1, Uvicorn 0.54.0,
HTTPX 0.28.1 and jsonschema **4.25.1**. SQLite comes from Python's standard
library; check its actual version for each Python build.

Run everything from the repository root. With CPython 3.14.8 installed:

```sh
python --version
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

G01C clean-installed all 22 pins in a new isolated Linux environment
(`/tmp/evora-g01c-clean-venv`, without system site packages); `pip check`, package
metadata read-back and all 14 warning-strict backend tests passed. Earlier G01
cache-only results remain historical in the verification record.

The shared `.github/workflows/contract.yml` now selects CPython **3.14.8** from
`backend/.python-version`, Node **22.23.3** and npm **12.2.0**, and runs coordination,
backend and frontend checks on `ubuntu-latest` (Bash) and `windows-latest`
(PowerShell). Windows is a configured target awaiting a native runner result;
this Linux session cannot certify Windows or hosted CI. Other Python versions
are unverified. SQLite's bundled version can differ by OS/build.
See [G01C verification](../docs/PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18).

## Windows PowerShell setup and run

Prerequisites: Windows x64, PowerShell 7, Git, CPython **3.14.8** with the `py`
launcher, Node **22.23.3** on PATH, package-registry access and a writable checkout.
Run from the repository root in a fresh checkout without an existing `.venv`.
Use the venv executable directly; activation/execution-policy changes are unnecessary.
Use `npm.cmd`/`npx.cmd` to avoid PowerShell choosing their `.ps1` wrappers.

```powershell
py -3.14 -c "import platform; print(platform.python_version()); assert platform.python_version() == '3.14.8'"
node --version
npm.cmd install --global npm@12.2.0
npm.cmd --version
py -3.14 -m venv .venv
$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -c "import sqlite3; from importlib.metadata import version; print('SQLite', sqlite3.sqlite_version, 'jsonschema', version('jsonschema'))"
$env:EVORA_CONTRACT_BUNDLE = Join-Path $env:TEMP 'evora-openapi.json'
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output "$env:EVORA_CONTRACT_BUNDLE"
& .\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
& .\.venv\Scripts\python.exe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log
```

Expected: Node `v22.23.3`, npm `12.2.0`, `pip check` reports no broken requirements,
jsonschema `4.25.1`, **14 tests, OK**, then `Application startup complete`.
In a second PowerShell window, `curl.exe -i http://127.0.0.1:8000/` should return
**404**. Stop the server with Ctrl+C. It creates only the ignored local
`storage/evora.sqlite3`; no domain API is available. Exact full coordination
commands are in the G01C verification record linked above.

Known limits: these PowerShell commands and native Windows execution remain
unverified locally. `PYTHONUTF8=1` matches CI and ensures existing tests read the
UTF-8 planning documents consistently across Windows locales. Python installation
must include SQLite; package downloads
and native dependency wheels must be available for the selected runtime/OS.
The directory mode 0700 applies on POSIX; this skeleton does not configure Windows
ACLs. Use a private writable local directory for synthetic work. No Neo4j, model,
authentication or full-system Windows support is established by skeleton tests.

## Run and configuration

```sh
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log
```

Expected: `Application startup complete`, then Uvicorn listens on localhost.
`GET /` returns 404 because G01 has no operations. Stop with Ctrl+C.
The default database is `storage/evora.sqlite3`, relative to the working directory;
the repository already ignores this local directory and SQLite files.

`EVORA_DATABASE_PATH` selects another SQLite file. `create_app(database_path=...)`
overrides the environment for embedded use/tests. Empty values and `:memory:`
are rejected; each connection represents a unit of work over a persistent file.
Startup creates missing parent directories (the final directory uses mode 0700
on POSIX), opens/checks SQLite and closes the connection. An inaccessible or
invalid database path fails startup. The skeleton creates no application tables
or migrations and does not serve storage files.

Future routes can use `Depends(get_database)` from `backend.app` to obtain the
configured `SQLiteDatabase`. Use `with database.connect() as connection:` within
one unit of work; connections enable foreign keys, commit on success, roll back
transactions on failure and always close. Do not pass a connection between
threads or retain it in application state. Domain migrations and access policy
belong to their assigned tasks.

## Validation behavior and tests

The factory overrides FastAPI's `RequestValidationError` handler. Invalid
path/query/header/body data, including malformed JSON, produces HTTP **400**:

```json
{"code":"INVALID_INPUT","message":"Invalid request input."}
```

The handler does not echo/log submitted values, bodies, field names or validation
exception details. Server response-validation errors remain server errors.
Later domain routes still need their declared constraints, authorization and
explicit domain errors; G01 does not implement F00 or generic HTTP error policy.

Build the shared bundle and run the backend command:

```sh
npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s backend/tests -v
```

The suite must report **14 tests, OK** without skips. Missing/invalid bundle input
fails instead of bypassing schema checks. On Windows use a writable bundle path
and set `$env:EVORA_CONTRACT_BUNDLE` to it before running the same unittest command.
HTTPX's async ASGI transport exercises the real application and FastAPI
validation, with explicit lifespan contexts and temporary SQLite files. Synthetic
`/_test/...` routes exist only in tests and do not implement domain operations.
The suite proves database read-back, transaction rollback/close, foreign-key
enforcement, isolated app configuration, startup failure and route absence.
Every invalid request response is validated against the shared bundle's
`ApiError`, including its required properties and `additionalProperties: false`.

## How you can test it

- [ ] Run the setup commands above with CPython 3.14.8; installation should exit 0.
  Clean isolated Linux installation passed in G01C; native Windows is pending.
- [ ] Build the bundle and run the backend command above: **14 tests, OK**.
  Locally exercised with clean-installed packages. To repeat using G01C's environment:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v`.
- [ ] Run the Uvicorn command: expect startup completion and a localhost listener;
  `curl -i http://127.0.0.1:8000/` should return 404. Startup/shutdown was exercised
  in G01; G01C records its own localhost smoke result in the verification record.
- [ ] Failure case:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v`.
  Expect one test `OK`: synthetic malformed JSON returns HTTP 400 with exactly
  `code` and `message`, validates against `ApiError`, and never reaches the probe.
- [ ] Database failure:
  `python -m unittest backend.tests.test_skeleton.SkeletonTests.test_database_open_failure_prevents_startup -v`.
  Expect one test `OK`: using a directory as the SQLite file raises an actual
  `sqlite3.OperationalError` before startup completes. Both negatives were exercised.
- [ ] Run the shared artifact commands in
  [the G01C verification record](../docs/PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18)
  and `git diff --check`; expect no new errors. Native Windows and remote CI
  are pending; the Linux results are recorded separately.

Tests clean up their temporary files. A manual server run leaves its ignored
SQLite file for inspection; remove only your own synthetic test file when finished.
