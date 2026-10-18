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

On Windows PowerShell the activation command is `.\.venv\Scripts\Activate.ps1`.
These are setup instructions, not Windows verification. The existing
coordination workflow selects Python 3.12 and runs artifact checks only; **G01C
must reconcile/test the shared Python baseline and add actual skeleton CI and
Windows evidence after G01B**. No Python 3.12 application compatibility is claimed.

This session could not install dependencies from the package index. Tests used
`/tmp/evora-g01-venv`, a Python 3.14.8 environment with system site packages and
jsonschema 4.25.1 copied, with distribution metadata, from the existing cache.
Every requirements pin was checked against imported distribution metadata.
This demonstrates execution with those packages, not clean-install reproducibility.
See [actual verification](../docs/PREIMPLEMENTATION_REVIEW.md#g01-verification--2026-10-18).

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
  Package-index installation was unavailable here; it remains unverified.
- [ ] Build the bundle and run the backend command above: **14 tests, OK**.
  Locally exercised with cached packages. To repeat using this session's environment:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -m unittest discover -s backend/tests -v`.
- [ ] Run the Uvicorn command: expect startup completion and a localhost listener;
  `curl -i http://127.0.0.1:8000/` should return 404. Startup/shutdown was exercised
  here, but the sandbox forbids socket binding, so external HTTP was not verified.
- [ ] Failure case:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v`.
  Expect one test `OK`: synthetic malformed JSON returns HTTP 400 with exactly
  `code` and `message`, validates against `ApiError`, and never reaches the probe.
- [ ] Database failure:
  `python -m unittest backend.tests.test_skeleton.SkeletonTests.test_database_open_failure_prevents_startup -v`.
  Expect one test `OK`: using a directory as the SQLite file raises an actual
  `sqlite3.OperationalError` before startup completes. Both negatives were exercised.
- [ ] Run the shared artifact commands in
  [the G01 verification record](../docs/PREIMPLEMENTATION_REVIEW.md#g01-verification--2026-10-18)
  and `git diff --check`; expect no new errors. DESIGN npx requires registry access;
  the cached exact-version CLI passed locally.

Tests clean up their temporary files. A manual server run leaves its ignored
SQLite file for inspection; remove only your own synthetic test file when finished.
