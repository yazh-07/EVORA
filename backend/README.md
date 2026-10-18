# G01 backend skeleton

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
