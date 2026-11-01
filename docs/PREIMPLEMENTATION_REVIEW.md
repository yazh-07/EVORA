# EVORA scope/contract verification and implementation readiness

### I00 verification — 2026-11-01

**I00 / Checkpoint 1A final exit gate / whale2186 / joint integration
coordination / Complete.** User-assigned branch
`feat/i00-authorized-intake-gate` started clean at
**c0561bbb3978e37395218bf1a771ecd562d3c2dd**, confirmed by Git status, HEAD and
merge-base read-back. Required proposal/architecture/scope/contracts/runbook,
checkpoint ledger and matching task row were inspected. All fourteen named
dependencies are merged on this base, including F06/F07/F09 and U04. The
unchanged draft 0.3.0 is the sole HTTP authority. Only the five assigned paths
are edited; no backend/spec/dependency, stage/commit/push/merge or later task.

#### Real producer/consumer read-back and gate closure

`frontend/test/cases.integration.mjs` uses M4's actual generated typed client,
case/evidence stores and original-download controller over localhost HTTP to
the existing `frontend/test/serve-cases.py` wrapper, real FastAPI, SQLite and
private original files. It serves the built UI at the API origin (HTTP 200).
Two synthetic bearer identities map to investigator-1/investigator-2; all case
and evidence data are synthetic. No case/evidence/audit producer is mocked.

Assertions call the existing `listAuditEvents` HTTP operation after case
creation and evidence upload, asserting the authoritative `action=uploadEvidence`
emitted by F06 intake accounting. Safe public fields, preserved earlier events,
two real successful uploads in chronological UTC RFC3339 order (fractional
precision preserved), repeated identical listing and actor-1 denial of actor-2
cases pass. Foreign and missing cases both return exact 404 ApiError:
`{"code":"NOT_FOUND","message":"Resource not found."}`.
Harness-only read-only SQLite dumps and original-file SHA-256 snapshots before
and after successful/repeated/denied audit listing are identical. No event is
inserted by the harness. Invalid and oversized uploads add no intake events.
The original/hash/size/metadata/empty-original, pagination and 400/401/404/413
regressions also pass. Owned server and temporary data are cleaned on exit.

**The integration command exits 0**, with complete passing smoke.

#### Commands and actual results

| Executed command | Actual result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | Exit 0, bundle created |
| `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` | Exit 0, existing info-license warning |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | Exit 0, 27 operations, 126 tasks, 15 in 1A, 39 features, 40 proposal/traceability sections |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | Exit 0, **122 tests, OK**, no skips, jsonschema 4.25.1 |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v` | Exit 0, **116 tests, OK**, no skips |
| `npm --prefix frontend run test` | Exit 0, **48 tests pass**, no skips; emits `.test-build` used by integration |
| `npm --prefix frontend run build` | Exit 0, declaration freshness, typecheck and production assets |
| `node frontend/test/cases.integration.mjs` | **Exit 0**, full smoke passes including audit target/actor read-back |
| `npx @google/design.md@0.4.0 lint DESIGN.md` | Exit 0, zero errors/warnings, one info |
| `git diff --check` | Exit 0 |

Checkpoint 1A is **Complete**. Checkpoint 1B is **Active**.

## F09 verification — 2026-11-01

**F09 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f09-m1-access-regressions`. User explicitly authorized implementation,
commit, push and merge of this one task. Before reading task states, `git fetch
origin` and clean status confirmed common local/origin HEAD
**53bac04ed4b94f10334dc92a5ecead2c11dfecad**. Accepted F00/F05/F07 and real
F01/F02/F03/F04/F06 are present. No F09 branch/worktree existed. Required
proposal/scope/contract/runbook sources were read earlier in this chat and their
diff against the previously inspected base is empty. Assignment bounds existing
M1 tests plus demonstrated route-error corrections; no other task is started.

### Coverage and demonstrated correction

The operation-level matrix in `backend/tests/test_m1_access.py` compares all
three M1 routers with eight shared-contract operations: createCase, listCases,
getCase, uploadEvidence, listEvidence, getEvidence, downloadEvidence,
listAuditEvents. It checks successful actor-owned reads/writes, declared schemas
and original byte/hash/audit read-back, then every operation's missing/invalid/
malformed/duplicate/replaced identity. All six scoped operations reject foreign,
missing and revoked cases; the two evidence-resource reads also reject a target
from another case even when the actor belongs to both cases. Create/list have
no case-ID parameter: their applicable checks prove owned membership, filtered
listing and rejected forged body IDs instead of inventing nonexistent-ID errors.

Denied requests compare exact snapshots of cases, case_members, evidence,
audit_events, intake_provenance and every private original byte. Two real
synthetic actors, three real cases and distinct originals prevent a constant
denial or wrong-original response from passing as correct isolation. Error
responses are declared flat ApiError and omit private input/resource details.
No timing-equality claim is made. Runtime route-inventory coverage fails if an
M1 operation is added without a matrix entry.

The first run's only failures were listCases/listEvidence at a valid offset of
10**30: Python-to-SQLite integer binding overflow, not a contract-invalid input.
Each route now skips the page SELECT when offset is beyond total, preserving
the actual total/limit/offset in an empty success page. This mirrors accepted
F07 behavior; no new upper bound, status, route or schema is introduced. All
authorization/isolation checks passed before that correction and the full
corrected suite passed afterward.

### Actual checks and environment

Windows / Python **3.14.8** / SQLite **3.50.4** / Node **22.23.3** / npm
**12.2.0** / jsonschema **4.25.1**, existing isolated environment/locked frontend
dependencies. No dependency, model, system configuration or API-contract change.

| Check | Actual result |
|---|---|
| F09 focused matrix | **14 pass**, no skips; every current M1 operation inventoried, both actors and exact state/byte assertions |
| Selected foreign/missing failure case | **One pass**, all six scoped operations for both actors; equal application 404 bodies/headers, no effects |
| Full backend regression | **116 run: 115 pass, one skip**, prior F05 Windows symlink permission limitation |
| Coordination verifier/tests | **Pass / 122 pass**, no skips |
| Frontend tests | **48 pass**, no skips |
| Contract/generated strict TypeScript | **Pass**, pinned Redocly 2.57.0/openapi-typescript 7.10.1/TypeScript 5.9.3; existing license warning |
| Frontend freshness/typecheck/build | **Pass**, generated types unchanged |
| DESIGN/whitespace | **Pass**, DESIGN 0.4.0 zero errors/warnings |
| Real localhost M1 matrix | **Pass**, all eight reject missing header, six scoped operations have equal foreign/missing 404, no denied-create/upload effects; original/hash/audit and valid huge offsets read back |
| Existing real-client regression | **Pass**, U02/U02B create/list/pagination/isolation; U03 upload/metadata/400/413/404; U04 original byte/hash/empty-file download |

All case/access/upload/audit/database/filesystem producers are real. Only
identities and data are synthetic; no endpoint or database result is mocked.
Revocation removes actual temporary membership or replaces the existing
synthetic verifier. This proves rejected/replaced credentials, not automatic
production token expiry. No issuer/expiry policy is invented. Each test removes
temporary data; real HTTP/client smoke stops its own server. Browser/persistent
storage acceptance and I00's full API/UI exit evidence remain separate.

### How you can test it

Open `.\.cache\setup\evora-shell.cmd` from the repository root, then in that
prepared CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_m1_access -v
python -W error::ResourceWarning -m unittest backend.tests.test_m1_access.M1AccessTests.test_all_case_routes_have_identical_foreign_and_missing_denials_for_both_actors -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expected: 14 focused pass, one selected failure case pass, 116 backend tests
run with the known platform skip above. Inputs are network.csv, distinct
synthetic binary originals, two actors and three cases (two owned by one actor).
The selected failure proves foreign and missing IDs are indistinguishable for
every scoped M1 operation and denied writes leave all records/originals intact.
Full shared checks ran via `.cache/setup/verify.ps1`; output is
`.cache/f09/shared-regressions.log` plus per-step logs in `.cache/setup/`.
Initial red matrix and corrected outputs: `.cache/f09/initial-m1-tests.log`,
`.cache/f09/m1-access-tests.log`; final corrected positives also ran in the full
backend suite. Selected failure: `.cache/f09/failure-case.log`.

Real localhost smoke command:
`& .\.venv\Scripts\python.exe -W error::ResourceWarning .cache/f09/http_smoke.py`.
Client regression uses pinned Node on `frontend/test/cases.integration.mjs`
after tests/build, with EVORA_TEST_PYTHON pointing to the absolute local venv
interpreter. Both passed; logs are under `.cache/f09/`. No new browser/hosted CI
claim at this pre-publication stage. Spec, generated client, frontend, manifests,
proposal and complete FEATURE_SCOPE including approved additions are unchanged.

### F09 publication and integrated acceptance — 2026-11-01

User-authorized task commit **4a69cafae6fb02c770f552c13b14430ac57e5e99** was
pushed on `feat/f09-m1-access-regressions`. Both Ubuntu and Windows PR CI
passed, Run **41301012667**
(`https://github.com/yazh-07/EVORA/actions/runs/41301012667`). PR #14 merged
into `docs/coordination-foundation` at
**868d697f297748614befdcc6af8a66370b48240b**. The clean local base fast-forwarded
to that exact merge; `git diff --exit-code` confirms equality with the tested
task tree. Post-merge real HTTP checks reject missing identity on all eight
operations and foreign/missing cases on six scoped operations, preserve
records/originals on denial and return correct huge-offset pages. Existing real
case/create/upload/metadata/error/download client checks pass. Logs are
`.cache/f09/merged-http-smoke.log` and `.cache/f09/merged-client-integration.log`;
own servers stopped and temporary synthetic data was removed.

**F09 is Complete. Next process is I00**, the shared real API/UI authorized-
intake integration gate, requiring an explicit assignee. It is not solely M1
and was not started. Later M1 F08 also needs real M2 P04/P14 processing.
Checkpoint 1A remains open; F09 completion does not complete the entire M1
module or the agreed product scope. The existing platform/production-expiry/
browser limitations remain as disclosed above.

## F07 verification — 2026-11-01

**F07 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f07-case-audit-list`. The user explicitly assigned F07 and authorized its
commit, push and merge after verification. `git fetch origin` preceded task
state inspection; clean local HEAD and origin common base both matched
**441d37de6db68f1f459aa11eb1bf6bd5864f5b77**. Real accepted F06
**203c4d5 / merge 1b5166d** and F00/F01/F03 producers are included. No local or
remote F07 branch existed. The bounded assignment card records paths and gates.
All required proposal/feature/architecture/contract/runbook sources were read
earlier in this chat; their diff against the previously inspected base is empty.

### Implemented boundary

- `backend/audit.py` adds the existing GET `listAuditEvents`, exact `AuditPage`
  and `AuditEvent` response models, safe explicit column selection and an index
  supporting authorized case/creation/ID reads. Current `require_case_access`
  protects the route; app wiring exposes no additional operation.
- Existing contract defaults/bounds apply: limit 20 (1–100), offset 0
  (nonnegative). Results use UTC creation time ascending, then ID ascending (fractional precision normalized); count and page share one
  read transaction. Empty/beyond-end/very large valid offsets return correct
  totals and empty items. This does not freeze history across separate requests.
- Optional null reason is omitted. Response headers are no-store. Private
  provenance is not joined or serialized. Shared safe 400/401/404 behavior is
  retained; unavailable storage fails instead of returning a fictional empty
  audit. Listing performs no write. Only F06's obsolete assertion that the
  future F07 route was absent was removed; private-route absence is still tested.

### Actual validation and disclosures

Windows / Python **3.14.8** / SQLite **3.50.4** / Node **22.23.3** / npm
**12.2.0** / jsonschema **4.25.1**, using the prepared isolated environment and
locked frontend dependencies; no installation or manifest/model change.

| Check | Actual result |
|---|---|
| F07 focused acceptance | **15 pass**, no skips; real F03 upload/F06 audit -> authorized list, bundled schema validation, actor/target/time read-back |
| Selected cross-case failure | **One pass**; foreign/missing cases have identical 404 status/body/headers |
| Full backend regression | **102 run: 101 pass, one skip**; existing F05 Windows symlink permission limitation, all F07 tests execute |
| Coordination verifier/tests | **Pass / 122 pass**, no skips |
| Frontend tests | **48 pass**, no skips |
| OpenAPI/generated strict TypeScript | **Pass**; pinned Redocly 2.57.0, openapi-typescript 7.10.1, TypeScript 5.9.3; existing missing-license warning |
| Frontend freshness/typecheck/build | **Pass**, generated declarations unchanged |
| DESIGN/whitespace | **Pass**, DESIGN 0.4.0 has zero errors/warnings |
| Real F07 HTTP/SQL smoke | **Pass**, real upload event visible via API, safe fields, paginated/empty pages, 400/401/foreign-missing 404 and original byte/hash download |
| Existing real-client integration | **Pass**, U02/U02B case/create/pagination/isolation, U03 multipart/metadata/400/413/404, U04 original controller byte/hash and empty download |

The tests exercise real FastAPI, HTTPX, SQLite and private files. Synthetic
identities and CSV/binary data are used. Chronological tie/optional reason
fixtures are explicit synthetic audit rows. A WAL concurrency test uses
connection tracing only to schedule a real second-connection append after the
count/before the page query: the first response stays coherent and the next
request sees the new event. Neither query nor result is mocked. Private-field
exclusion is also verified after dropping the private provenance fixture table;
storage failure is induced by dropping the temporary audit table. Temporary
data clean up automatically. No production identity, new browser/accessibility
or hosted CI result is claimed at this pre-publication stage.

### How you can test it

Open `.\.cache\setup\evora-shell.cmd` from the repository root to select the
prepared local toolchain, then in its CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_audit_list -v
python -W error::ResourceWarning -m unittest backend.tests.test_audit_list.AuditListTests.test_two_cases_are_filtered_and_foreign_missing_denials_are_indistinguishable -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expect 15 focused passes, one selected failure pass and 102 combined backend
tests run with the one known platform skip. Synthetic inputs are network.csv,
21 small upload originals, two actors/cases and explicit ordering/reason event
fixtures. The failure test confirms a foreign actor receives exactly the same
404 as a missing case; no private source fields are exposed. Full shared checks
ran via `.cache/setup/verify.ps1`, output `.cache/f07/shared-regressions.log`.
Individual current outputs are in `.cache/setup/`; focused/failure/smoke/client
logs are in `.cache/f07/`.

The exact local HTTP/SQL smoke command was
`& .\.venv\Scripts\python.exe -W error::ResourceWarning .cache/f07/http_smoke.py`.
Existing client integration ran with `EVORA_TEST_PYTHON` set to the absolute
`.venv\Scripts\python.exe` path and pinned Node executing
`frontend/test/cases.integration.mjs` after frontend tests/build. Own servers
stop and temporary synthetic data is removed. Contract/schema, generated
declarations, dependencies, proposal and full FEATURE_SCOPE including approved
additions remain unchanged.

### F07 publication and integrated acceptance — 2026-11-01

The user authorized implementation, commit, push and merge of this one task.
Initial task commit **48ab5e9** was followed by boundary correction
**e7cd61402e87d2afbed1eafa8ab930e2597dea2b**, covering whole-second and fractional
UTC timestamps with microsecond ordering retained. Final focused 15 tests and
all 102 backend tests ran successfully (the one known local symlink skip
remains). The final documentation verifier passed. Open PR #13's description
was updated to the final implementation/results before merge.

Both Ubuntu and Windows checks passed on that final task head, Run
**41299455397** (`https://github.com/yazh-07/EVORA/actions/runs/41299455397`).
PR #13 merged into `docs/coordination-foundation` at
**6687d7cbd820fc4db820d85e4dcd518dd941c99d**. The clean local common branch
fast-forwarded to this exact commit; `git diff --exit-code` confirms the merged
tree equals the CI-tested task head. Post-merge real HTTP F07 audit read-back,
pagination/safe-fields/400/401/404 checks, F06 SQL/source accounting and original
download passed. The prior U02/U02B/U03/U04 real-client regressions also passed.
Own servers stopped and temporary synthetic data cleaned up. Logs:
`.cache/f07/merged-http-smoke.log`, `.cache/f07/merged-client-integration.log`.

**F07 is Complete. Next M1 task is F09**, not started. Shared I00 still requires
an explicit assignee and Checkpoint 1A remains open. No new browser/production
authentication or database-owner tamper-resistance claim is made; original
full feature scope and approved additions remain intact.

## F06 verification — 2026-11-01

**F06 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f06-intake-audit`. Before task-state inspection, `git fetch origin` fetched
all branch refs with the configured `+refs/heads/*:refs/remotes/origin/*`
refspec. The clean local common base was 27 commits behind and fast-forwarded
from `86f14ee` to **3eab939ada44363de5420d542ead711198ccea0f**. Local HEAD and
`origin/docs/coordination-foundation` matched before selecting/branching F06.
The actual base contains merged F01–F05 and U02/U02B/U03/U04, despite older
historical In Progress records. F06 was unclaimed with no local/remote task
branch. It is the earliest dependency-ready M1 row in unfinished Checkpoint 1A.
The F06 assignment card records paths and contract/producer boundaries.

### Implementation and integrity boundary

- `backend/audit.py` initializes `audit_events` and linked private
  `intake_provenance`. It records the authenticated actor, case, Evidence ID,
  server UTC intake timestamp and the existing `uploadEvidence` operation name.
  Source metadata/hash/size/acquisition text are read from the actual inserted
  evidence row, scoped to the authorized case, into an immutable private
  `intake-source.v1` snapshot. No raw bytes, token or model output is stored by
  this hook; public audit contains only safe references, with no source text.
- The F03 upload hook uses the same SQLite transaction as evidence insertion;
  audit/provenance/commit failure rolls all metadata/accounting back and removes
  the newly created original file through the existing F03 cleanup path. No
  success event is recorded for rejected/failed uploads. Read/download operations
  do not fabricate a second intake event. Each successful separate upload still
  creates its own Evidence ID; no new idempotency/deduplication behavior.
- Startup wiring adds empty tables without replacing existing originals or
  inventing pre-F06 upload actors/history. SQLite append-only triggers cover
  UPDATE, DELETE, UPSERT and INSERT OR REPLACE; WITHOUT ROWID also avoids hidden
  rowid replacement. Database owners who alter/drop schema are outside this
  write-protection claim. Hard-crash/power-loss recovery between filesystem and
  SQLite remains untested; request-time exceptions/rollback were exercised.
- F07's `listAuditEvents` route is deliberately absent. No private provenance
  API or model/parser/RAG producer is added. Existing intake response/schema,
  frontend, requirements, proposal and complete FEATURE_SCOPE (including approved
  transcription/correction additions) have an empty diff against the common base.

### Environment and actual results

Native Windows, PowerShell 7.6.5, Git 2.53.0.windows.3, CPython **3.14.8**,
SQLite **3.50.4**, Node **22.23.3**, npm **12.2.0**, jsonschema **4.25.1**.
The existing isolated `.venv` lacked the newly fetched manifest's
`python-multipart==0.0.32`; `python -m pip install -r requirements.txt` installed
that documented pin. No manifest, system-wide tool or model change. The frontend
lockfile/package pins were unchanged; the prepared local dependencies were used.

| Check | Actual result |
|---|---|
| F06 focused suite | **17 pass**, no skips; real multipart/FastAPI/SQLite/private filesystem and bundled schema assertions |
| Selected provenance insert failure | **One test pass**; real SQLite trigger aborts after audit insertion, leaving zero evidence/audit/provenance rows and no file |
| All backend tests | **87 run: 86 pass, one skip**; the prior F05 symlink-escape test cannot create symlinks on this Windows account; all F06 tests execute |
| Shared coordination | Verifier passes; **122 tests pass**, no skips |
| Frontend tests | **48 pass**, no skips |
| OpenAPI / generated TypeScript | Redocly 2.57.0 lint/bundle and fresh openapi-typescript 7.10.1 / strict TypeScript 5.9.3 compilation pass; existing missing-license warning |
| Frontend API freshness/typecheck/build | **Pass**, generated declarations unchanged |
| DESIGN / whitespace | **Pass**, DESIGN 0.4.0 has zero errors/warnings; `git diff --check` passes |
| Real F06 localhost smoke | **Pass**, real case/upload 201, original/hash/size download 200, foreign upload 404 and SQL read-back of one matching event/source pair |
| Existing U02/U02B/U03/U04 real-client integration | **Pass**, case creation/listing/pagination/isolation, multipart/metadata/400/413/404, download-controller byte/hash read-back and empty original |

Doubles: synthetic bearer identities/fixture bytes only; negative tests patch the
upload byte limit to 64 KiB and use genuine SQLite triggers/deferred constraints
to force failures. No mocked upload, database, filesystem, audit or provenance
producer is used. New tests cover mutation/replacement rejection, each insertion
and commit rollback, failed-attempt retry, two-case joins, ignored forged actor/
time/action form fields, safe logs, startup idempotence and existing-evidence
upgrade. F06's localhost check spawns the repository's synthetic identity test
server and reads actual SQLite after API responses; it stops its own process.
The first ignored smoke-harness attempt left its read-back connection open;
explicit closure fixed it, and the rerun passed with clean temporary cleanup.
The first attempt's leftover synthetic file/directory was removed.

### Reproduce / How you can test it

From the repository root, launch `.\.cache\setup\evora-shell.cmd` to select the
prepared isolated Python/Node/npm tools in a CMD shell, then:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_audit -v
python -W error::ResourceWarning -m unittest backend.tests.test_audit.IntakeAuditTests.test_provenance_insert_failure_rolls_back_event_evidence_and_original -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expected: 17 focused pass, one selected failure test pass, 87 backend tests run
with the one platform skip described above. Inputs are the synthetic network CSV,
two synthetic actors/cases and binary/private-marker fixtures; no real evidence
or credentials. Tests automatically remove their temporary databases/files.
Exact shared commands were run via `.cache/setup/verify.ps1` (PowerShell), with
combined output in `.cache/f06/shared-regressions.log` and individual logs in
`.cache/setup/`. F06/failure/HTTP logs are in `.cache/f06/`.

The existing real-client integration command was:

```powershell
$env:EVORA_TEST_PYTHON = (Resolve-Path '.venv\Scripts\python.exe').Path
& .\.cache\setup\node_modules\node-v22.23.3-win-x64\node.exe frontend/test/cases.integration.mjs
```

This ran after frontend tests/build; its temporary server/data clean up
automatically. The local F06 SQL read-back smoke command was
`& .\.venv\Scripts\python.exe -W error::ResourceWarning .cache/f06/http_smoke.py`.
No new browser/rendering/accessibility result is claimed. F07 audit listing
and the I00 end-to-end intake gate are not delivered by these checks.

### F06 publication and integrated acceptance — 2026-11-01

The user explicitly authorized finishing, committing, pushing and merging F06.
The remote target still matched the verified common base. Fresh focused
**17 F06 tests**, the coordination verifier and real localhost SQL/byte smoke
passed before publication. Task commit
**203c4d5809300ac4b08e82b22856ad4614a12b97** was pushed on
`feat/f06-intake-audit`, then **PR #12** merged into
`docs/coordination-foundation` at **1b5166d91e0f3b86b85585d714a917a3efc82d44**.
Both Ubuntu and Windows PR CI jobs passed, Run **41297980571**:
`https://github.com/yazh-07/EVORA/actions/runs/41297980571`.

The clean local common base fast-forwarded to that exact merge. Its tree matches
the task commit, verified with `git diff --exit-code`. Post-merge real HTTP/SQL
upload/audit/source/original-byte/hash read-back passed, as did the existing
U02/U02B/U03/U04 real-client case/create/pagination/upload/metadata/errors/download
integration. Output is in `.cache/f06/merged-http-smoke.log` and
`.cache/f06/merged-client-integration.log`; own servers stopped and temporary
synthetic databases/files cleaned up. F06 uses real merged F03 intake, access,
SQLite and filesystem producers; there is no pending producer double for its
bounded acceptance.

**F06 is Complete. F07 is the next M1 task.** F09 depends on F07; I00 remains a
shared task requiring an explicit assignee. Checkpoint 1A remains open. No F07
or other implementation task was started. The documented symlink/browser/
hard-crash/tamper-resistance limits remain unchanged by publication.

### F05 verification — 2026-10-31

**F05 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f05-evidence-download`. Clean starting HEAD and local coordination base
were both **c5c9b5a5aefff113db6592996da4af1c780d88df**. Real merged F00 and
F03 (via **e5273a6**, including **6622959**) are dependencies; F01/F02/F04
provide real case membership/intake/metadata for acceptance. The unchanged
`specs/openapi.yaml` draft 0.3.0 remains the sole HTTP authority. No fetch,
staging, commit, push or merge was performed.

Implemented `downloadEvidence` using the existing case-access dependency and a
case/evidence-scoped SQLite lookup. Successful reads return original bytes as
an octet-stream attachment with `Cache-Control: no-store`. Resolved paths must
be regular files strictly inside the configured storage root's authorized case
directory. Unsafe paths and missing files receive the same flat 404 as missing
resources; path/UUID validation uses the existing flat 400 handler.

Linux acceptance used the existing isolated environment at
`/tmp/evora-f03-pinned`: CPython **3.14.8**, SQLite **3.54.0**, FastAPI
**0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, httpx **0.28.1**,
jsonschema **4.25.1**. Node **22.23.4** and npm **12.2.1** differ from the
repository's setup pins 22.23.3/12.2.0; no dependencies were changed. An initial
23-test evidence run also passed in the older local Python 3.12.14 environment;
the recorded full acceptance below uses the pinned Python 3.14.8 environment.

From the repository root, activate the pinned environment with
`source /tmp/evora-f03-pinned/bin/activate` (or use an interpreter with
`requirements.txt` installed). Actual commands/results:

| Command | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | Pass; real contract bundle produced |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | Pass; 27 operations, 126 tasks, 18 checkpoints |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | 122 tests pass, no skips |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests` | 70 tests pass, no skips; 23 evidence tests including seven new F05 tests |
| `npm --prefix frontend run test` | 39 tests pass, no skips |
| `npx @google/design.md@0.4.0 lint DESIGN.md` | Zero errors/warnings |
| `npx @redocly/cli lint specs/openapi.yaml` | Pass; existing missing info.license warning only |
| `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-f05-api.d.ts` | Generated declarations from unchanged contract |
| `npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-f05-api.d.ts` | Pass |
| `npm --prefix frontend run build` | API declaration freshness, TypeScript and production build pass |
| `git diff --check` | Pass; only the six allowed files changed, nothing staged |

Read-back uses real ASGI/FastAPI/F00/F01/F03/F04, SQLite and private temporary
files; identities and fixture bytes are synthetic. There are no download,
storage or authorization producer doubles. Uploaded `fixtures/synthetic-case/network.csv`
is downloaded byte-for-byte and its SHA-256 equals the upload's stored hash.
Empty and multi-chunk binary originals also match exactly. Uploaded text/csv
and text/html MIME types still download as application/octet-stream with
no-store and attachment headers; metadata is unchanged after download.

Negative read-back: missing/invalid credentials return schema-valid 401;
invalid case/evidence UUIDs return exact 400 INVALID_INPUT. Actor B reading
Actor A's case, evidence under another authorized case, nonexistent case or
evidence, and foreign evidence under Actor B's own URL all return identical
404 body/headers. Membership revocation immediately denies subsequent reads.
Tampered SQLite paths to an external file, traversal, sibling prefix collision,
another case's file, directory, missing file, NUL path and escaping symlink
return the standard 404 without server paths or external bytes. Symlink
creation succeeded on this Linux run; that dedicated test explicitly skips
where OS/account privileges disallow creation. Temporary databases/files use
resolved roots and clean up through unittest contexts.

How to test F05 specifically: after bundling, run
`EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v`.
Expect 23 passing tests on a symlink-capable host, including the real CSV/hash
round trip. For a focused failure case use
`EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_evidence.EvidenceTests.test_download_tampered_storage_paths -v`;
expect 404 for every injected unsafe/missing path and unchanged external bytes.

Limits: local Linux application/artifact checks are not native Windows,
interactive browser or hosted CI proof. The private filesystem is assumed to
remain under backend control; path checking is not a filesystem sandbox against
a concurrent privileged writer replacing files during a response. No media
playback/download UI, processing, audit or scoring implementation is claimed.
Earlier completed Checkpoint 0's local checks are rerun; its historical Windows
proof is not replaced. F05 awaits review/integration; Checkpoint 1A and I00's
assembled intake/audit/download/UI exit remain open. Next M1 task is F06 under
a separate assignment; U04 can consume F05 after an accepted handoff.

### F02 verification — 2026-10-25

**F02 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f02-case-listing`, clean starting HEAD/common contract base
**a10a81ecf4820b2330bd04edfba7f15d2764c745**, including real merged F00/F01. Execution date:
**2026-10-27, Linux**. No remote fetch, staging, commit, push or merge.

Implemented `listCases`/`CasePage` using authenticated actor membership, SQLite
count/page read snapshot, deterministic created_at DESC/id ASC ordering and
omitted absent descriptions. Tests use real FastAPI/SQLite/F00/F01, synthetic
bearer identities, and temporary databases removed automatically. No case
producer double, spec/frontend/package changes or new error envelope.

Commands below exited 0. Python commands use the existing isolated pinned
requirements environment `/tmp/evora-f01-venv` (jsonschema 4.25.1), rather than
the shell's jsonschema 4.26.0.

```sh
export PATH=/tmp/evora-f01-venv/bin:$PATH
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
npm --prefix frontend run test
npm --prefix frontend run build
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

| Check | Actual result |
|---|---|
| Bundle/lint | Pass; existing missing info.license warning only |
| Coordination verifier | Pass; 27 operations, 126 tasks |
| Coordination suite | 122 tests, OK, no skips |
| Warning-strict backend suite | 47 tests, OK, no skips; 14 case tests including 3 new F02 tests |
| CasePage/Case/ApiError validation | Pass against actual bundle, including nested Case references and format checking |
| Listing read-back | Only caller memberships, immediate revocation, default 20/0, 23 cases across pages, timestamp tie ID ordering, preserved description, absent description omitted, limit 1/100, empty actor and offset at/beyond total |
| Negative read-back | limit 0/101/abc and offset -1 return exact flat 400 INVALID_INPUT; missing/malformed/rejected auth returns 401 ApiError |
| Frontend regression | 19 tests pass, no skips; generated declarations freshness, TypeScript and production build pass |
| DESIGN | Zero errors/warnings |
| Diff review | Allowed six files only; whitespace clean; no staged changes |

How you can test: use the pinned requirements environment and bundle command
above, then run `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W
error::ResourceWarning -m unittest backend.tests.test_cases -v` on one line.
Expect 14 passing tests; synthetic cases/tokens are defined in the test file.
The invalid-pagination test verifies the relevant failure responses. Temporary
SQLite directories clean up automatically. These API/component checks were
exercised; interactive browser, native Windows, hosted CI and full Checkpoint
1A exit evidence were not. F02 awaits review; next M1 task is F03 subject to
its own gate and dependency review.

### F01 verification — 2026-10-25

**F01 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f01-case-persistence`, clean starting HEAD/common contract base
**86f14eedc575032d636a77233b19f13bf665c077**. This includes F00
**94aa2a8** through its reviewed merge. Local branch/base were read back;
no remote fetch, commit, push or merge was performed. Execution date was
**2026-10-27 (Linux)**; the heading retains the requested assignment date.

Implemented real POST/GET case operations, startup tables, default SQLiteCaseAccess,
atomic case/membership creation, strict request validation, omitted absent
description and unchanged persisted source values. Updated G01 skeleton assertions
only where F01 introduces tables/routes; connection cleanup, startup failure,
foreign keys and per-app isolation checks remain. No spec, frontend or package
file changes. F01 uses real F00 guards/storage; only bearer identities are synthetic.
Earlier F00 tests retain explicitly test-only membership producers.

F01-E01 is pending in the assignment/communication queue: requested nested error
objects and BAD_REQUEST conflict with the unchanged flat ApiError/F00/U01 wire.
User clarification was requested. All results below exercise the existing flat
contract and INVALID_INPUT mapping, not the alternate requested wire shape.
No constant-time result is claimed: denied requests share the same membership
query/control flow and exact HTTP status/body/headers; runtime latency varies.

Environment: CPython **3.14.8**, SQLite **3.54.0**, Node **22.23.3**, npm
**12.2.1** (workflow pin is 12.2.0). A clean isolated venv at
`/tmp/evora-f01-venv` installed all unchanged requirements, including FastAPI
**0.143.1**, Pydantic **2.14.1**, jsonschema **4.25.1**; pip check passed.
Initial shell packages differed (FastAPI 0.156.8/jsonschema 4.26.0), so recorded
backend/coordination acceptance uses the isolated pinned environment.

Commands/results (all listed final checks exit 0):

```sh
python -m venv /tmp/evora-f01-venv
/tmp/evora-f01-venv/bin/python -m pip install -r requirements.txt
/tmp/evora-f01-venv/bin/python -m pip check
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-f01-api.d.ts
npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-f01-api.d.ts
/tmp/evora-f01-venv/bin/python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-f01-venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-f01-venv/bin/python -W error::ResourceWarning -m unittest backend.tests.test_cases -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-f01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests
npm --prefix frontend run test
npm --prefix frontend run build
npx --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

- Bundle succeeded using Redocly **2.71.2** selected by the requested unversioned
  command. Workflow-pinned Redocly **2.57.0** lint passed with the existing single
  missing-license warning. Generated strict TypeScript compilation passed.
- Coordination verifier passed (27 operations, 126 tasks); **122 tests, OK**,
  no skips, with jsonschema 4.25.1. These are artifact checks.
- Focused F01: **11 tests, OK**, no skips. Combined backend: **44 tests, OK**,
  no skips, ResourceWarning promoted to errors. Case/ApiError responses validate
  against the actual bundle. Temporary database directories clean up automatically.
- Read-back proves UUID4 stability, exact title/description/UTC timestamp through
  API/SQL and app restart, omitted optional description, validation boundaries,
  empty/whitespace/oversized/non-string/extra/null failures, missing/malformed
  authentication, malformed UUID, identical foreign/missing 404, immediate
  revocation, atomic failed membership rollback, FK/cascade and real SQLite
  membership failure returning 500 rather than granting access or false 404.
- Frontend **19 tests pass**, no skips; API declaration freshness, typecheck and
  production build pass. Frontend files were not edited. DESIGN lint reports
  zero errors/warnings. Whitespace check passes.

An initial shell-package run found two outdated skeleton assertions after F01
startup changes; their final updated checks pass with pinned packages. No hosted
CI, native Windows, browser/CORS integration or full Checkpoint 1A exit is claimed.
F01 remains In Progress pending F01-E01 resolution/review; next M1 task is F02
once F01 is accepted. Default identity still rejects tokens, and no production
identity provider, list/upload API or other task is implemented.


## F00 verification — 2026-10-25

**F00 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f00-auth-case-guard`. The user requested automatic selection of one eligible
task. M1 ownership, earliest unfinished Checkpoint 1A and Backlog F00 identify
this row; C-03's later declared synthetic policy supplies its current gate.
The starting checkout was clean at **f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029**,
matching freshly fetched `origin/docs/coordination-foundation`. G00
**1721bfff9640263d2799434455cdb9c4f345ac35** and G01
**e0257a6ad231105b93ae98a97f176ed233a25412** were verified ancestors. A separate
task branch was created at that common base; main was not used or changed.
The F00 assignment card records allowed paths and dependency handling.

### Implemented boundary and dependency disclosure

- `backend/auth.py`: immutable internal actor/grant values, injectable token and
  membership interfaces, explicit caller-configured synthetic token verifier for
  C-03's two development identities, and reusable request/case dependencies.
  No built-in credential; synthetic token digests are retained instead of raw
  tokens. The factory defaults to rejecting all credentials and case access.
- `backend/app.py` wires per-app adapters and the safe access-error handler;
  `backend/errors.py` emits exact C-03 401/404 `ApiError` bodies, no-store headers
  and a Bearer challenge on 401. Duplicate/malformed headers fail before a
  membership query. Case UUID validation uses the existing 400 handler. Every
  authorized request checks membership; storage failure cannot grant access.
- `backend/tests/test_auth.py` uses real FastAPI dependency resolution, HTTPX
  ASGI transport, shared bundled `ApiError`, real temporary SQLite and synthetic
  two-actor/two-case fixtures. Its `/_test/...` routes, memberships and write probe
  are **test-only F01 producer doubles**, never production routes/tables. F01 owns
  case persistence; real F01/U01/browser integration remains absent. No evidence
  logic, wire route, package, production provider or token issuance/automatic
  expiry policy is implemented. No real evidence, credentials or external service.

### Commands and actual results

Native Windows / PowerShell 7.6.5 / Git 2.53.0.windows.3, local CPython **3.14.8**,
SQLite **3.50.4**, Node **22.23.3**, npm **12.2.0**, jsonschema **4.25.1**.
The existing isolated `.venv` and locked frontend installation were used;
`pip check` passes. No new dependency or model installation was needed.

| Check | Observed result |
|---|---|
| F00 focused suite | **19 pass**, no skips; two identities/cases, malformed/duplicate credentials, no query/cookie/actor impersonation, default denial, app isolation, membership/token replacement, failed membership lookup and safe errors |
| Selected foreign/missing failure | **1 test pass**; both actors get identical 404 bodies/headers for foreign and nonexistent cases |
| All backend regressions | **33 pass**, no skips, `-W error::ResourceWarning`; includes previous 14 skeleton/validation tests |
| All coordination tests | **122 pass**, no skips, using the fresh contract bundle and jsonschema 4.25.1 |
| Frontend regression suite | **19 pass**, no skips; existing U01 fixtures remain fixtures |
| OpenAPI 2.57.0 lint/bundle | **Pass**; one existing missing `info.license` warning |
| Scratch generated types / strict TypeScript | **Pass**, openapi-typescript 7.10.1 and TypeScript 5.9.3 |
| Frontend API freshness/typecheck/build | **Pass**; committed declarations unchanged |
| Coordination verifier | **Pass**, full task/checkpoint/source/feature/fixture checks; planning-artifact verification only |
| DESIGN 0.4.0 / whitespace | **Pass**, zero DESIGN errors/warnings; `git diff --check` passes |
| Real skeleton localhost startup | **Pass**: Uvicorn root 404 with synthetic SQLite; frontend root/JS/CSS 200; own servers stopped |

From the repository root in the prepared shell
(`.\.cache\setup\evora-shell.cmd`), the reproducible CMD commands are:

```bat
npx.cmd --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_auth -v
python -W error::ResourceWarning -m unittest backend.tests.test_auth.AuthenticationTests.test_foreign_and_missing_cases_have_identical_status_body_and_headers -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
python scripts/verify_coordination.py "%EVORA_CONTRACT_BUNDLE%"
python -m unittest discover -s scripts -p "test_*.py" -v
npx.cmd --yes openapi-typescript@7.10.1 specs/openapi.yaml -o .cache\setup\evora-api.d.ts
frontend\node_modules\.bin\tsc.cmd --noEmit --strict .cache\setup\evora-api.d.ts
npm.cmd --prefix frontend run check:api
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build
npx.cmd --yes --package @google/design.md@0.4.0 designmd lint DESIGN.md
git diff --check
```

These commands were exercised directly or through the ignored local
`.cache/setup/verify.ps1` equivalent, with output in `.cache/f00/checkpoint0.log`
and `.cache/setup/*-tests.log`. Focused/failure logs are in `.cache/f00/`.
The native localhost smoke used the ignored `.cache/f00/smoke.py`; it starts
only its own processes and stops them in `finally`. No rendered browser,
accessibility, production auth, actual F01 membership persistence or remote CI
on this uncommitted candidate is certified. The selected synthetic verifier has
no automatic expiry; future production authentication requires its own approved
provider/issuance/expiry/revocation policy. The default app still exposes no
domain operations; the reusable guards must be attached to future routes.

All initial features and approved transcription/correction additions remain
unchanged in FEATURE_SCOPE. Spec, generated declarations, requirements, frontend
and proposal diff against the common base are empty. Nothing staged, committed,
pushed or merged. **F00 remains In Progress**, locally verified and awaiting user
review plus real producer/client integration. **F01** is the next M1 row after
an accepted F00 dependency handoff; it was not started. Checkpoint 1A stays Backlog.
The user subsequently authorized committing/pushing F00 and merging it into
`docs/coordination-foundation` on 2026-10-25. Publication does not itself close
the real-producer/client integration limits above; F00 remains In Progress.

## Current state

**G01C is locally implemented/verified and In Progress pending native Windows/hosted CI evidence and review.** The user accepted committed common base `328c103d0f0383c7b4979bd8199b4201408e2a68`, containing G00/G01/G01B. The tree includes real FastAPI/SQLite and React/TypeScript skeletons, with clean Linux dependency installs and combined regression checks recorded below. Checkpoint 0 remains In Progress until all four exit gates pass, including native Windows/CI execution. Domain tasks/checkpoints remain Backlog; no domain routes, ASR/scoring/RAG system or main merge is claimed. Earlier verification records retain their historical environment/results; the G01C record is current.

Prepublication verification covered the transcription and simplified Codex-prompt revision on `docs/coordination-foundation`, originally based on `d36ac5cd63b5dcf431af6fca34411653a6ffe50f`. Before publication the branch fast-forwarded to `815b2eca5b0b5a77af93d4db69e12793bd48144b`, whose tree is identical; collaborator history was preserved. The inspected local main tree contains only README. Publication is tracked by the exact Git commit/remote ref and its CI run, not by a self-referential commit ID here. No main merge or Windows application run is claimed. G00 must record the reviewed common base before implementation branches depend on it.

## Approved scope addition

The full original proposal remains required and is preserved verbatim. The user subsequently approved local audio/video speech transcription as **additional initial scope**, not an original proposal requirement:

- P16/P16B in 3B: local speech extraction, original-media timestamped segments and candidate entity/event extraction.
- U14/U14B/U14C in 3C: authorized playback, all-page local source-transcript search and audited append-only corrections/history.
- Corrections atomically publish a new complete processing materialization with rebuilt candidates and safe audit linkage. Machine text, original bytes/hash, prior runs and frozen analysis never mutate. New-key analysis selects corrected inputs; original-key replay retains old inputs.
- Video visuals/speech coexist in one selected complete output. Derivatives/revisions are not independent corroboration; media offsets do not imply capture UTC or the time a spoken event occurred.
- Silence/no-audio differs from decoder/model failure; unclear speech is unverified. Speaker identification, voice matching, emotion inference, diarization and translation are excluded.

[CONTRACTS.md](CONTRACTS.md) owns policy and [OpenAPI](../specs/openapi.yaml) the wire contract. [FEATURE_SCOPE.md](FEATURE_SCOPE.md), [ROADMAP.md](ROADMAP.md), [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) and [INTEGRATION.md](INTEGRATION.md) define acceptance, exact membership, dependencies and real execution proof. [PROPOSAL_TRACEABILITY.md](PROPOSAL_TRACEABILITY.md) distinguishes the addition from source requirements.

## Preservation checks actually executed

- All **121 pre-change tasks** and all prior dependency edges remain. Exactly five tasks were added: P16, P16B, U14, U14B, U14C. **126 unique tasks** occur exactly once across **18 checkpoints**, with no dependency cycle or later-checkpoint prerequisite.
- All original feature identities remain; two addition rows bring the inventory to **39**. Roadmap/catalog/runbook and derived feature checkpoint coverage are checked together.
- All **40 proposal sections** and **40 source mappings** remain. `docs/PROPOSAL.md` and the three original CSV fixtures are byte-for-byte unchanged from pre-change HEAD.
- Draft **0.3.0** preserves the original 25 operations and adds only `appendTranscriptRevision` and `listTranscriptRevisions`: **27 total**. No search/playback endpoint or start-command request body was added.
- React/TypeScript, FastAPI/Python, authoritative SQLite/private originals and derived Neo4j topology is unchanged. Full chronological timeline reconstruction remains future.

## Historical prepublication validation

The run used **Python 3.14.7 / Node 26.7.0**, with **jsonschema 4.25.1 / Ruff 0.12.12** pinned in a scratch virtual environment. No product models were installed. This is not a fresh Python 3.12 / Node 22 CI or Windows run.

- Redocly **2.57.0** lint and fresh bundle: passed.
- openapi-typescript **7.10.1** generation and TypeScript **5.9.3** `--noEmit --strict` declaration compilation: passed.
- Coordination verifier: passed contract/task/DAG/phase/runbook/feature/source/link/fixture checks and transcription/full-scope handoffs.
- **122 unittest checks passed**, including synthetic schema examples, CLI mutations and new speech/correction planning regressions. New handoff tests were exercised failing before verifier implementation. An operation-name mismatch was detected and fixed before the combined pass.
- Ruff over `scripts`: passed. DESIGN **0.4.0** lint: zero errors/warnings. `git diff --check`: passed.

Existing nonblocking warning: OpenAPI `info.license` is missing; no project license is invented. These are artifact checks, not model accuracy, application authorization/transaction atomicity, playback, browser/accessibility or forensic certification. Earlier phase-plan results are historical in Git and do not certify this revised draft.

## Remaining gates

- C-03 identity/token/membership/client handling before protected tasks, including playback/corrections.
- C-04 tested format/limits/failure policy before each adapter. P16/P16B/U14 need local model/runtime/version/license, languages/codecs, track/offset policy, duration/byte/compute limits, private derivative cleanup and browser compatibility. Whisper is a candidate, not a selected/installed model.
- C-05 precise scoring/independence/confidence/goldens; do not double-count audio/video/transcripts.
- Approved local retrieval/grounding/privacy before deterministic Q&A; C-06/G03 before final generation. Local speech does not depend on the final LLM provider; no cloud speech transfer is authorized.
- The G01C handoff accepts exact committed G00/G01/G01B ancestry and records scoped assignee/paths. G01C edits await review and native Windows/hosted CI evidence. Later task handoffs still need their own assignments. Confirmed module owners remain in ROADMAP; ownership is not completion.
- G01/G01B package pins are now exercised together on Linux; G01D still needs Neo4j setup proof. G01C/I03/I09B prove their respective Windows/CI scopes. I03B proves real media/correction behavior; I08 measures speech errors/alignment and other research metrics; I09/I09B/I06 retain full integration/reproducibility/report closure.

Use the earliest dependency-ready bounded task and [agent assignment card](AGENT_TASKS.md). Disclosed schema-derived doubles permit independent work, not integrated completion. Rerun every completed checkpoint regression before an authorized main promotion; verify the merged commit/CI/smoke results afterward. Artifact checks cannot close product milestones.

## G00 verification — 2026-10-18

Task **G00 / Checkpoint 0**, explicitly assigned to **whale2186** for shared integration coordination on `feat/g00-coordination-base`. Exact reviewed common contract/base: **114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb** (`origin/docs/coordination-foundation`). Starting `git status --short --branch` was clean; `git rev-parse HEAD` and `git show-ref --verify refs/remotes/origin/docs/coordination-foundation` both returned this SHA. This reads back the available local remote-tracking ref, not a fresh network fetch or remote CI result. Local main contains only README and was not used as the task base. Dependencies: none; the base's actual artifacts are the inputs. [Assignment/allowed paths](AGENT_TASKS.md#g00-assignment--2026-10-18) and [live state](ROADMAP.md#g00-live-record--2026-10-18) remain **In Progress**, pending review/publication.

### Current targeted gates

| Gate | Current status and exact producer/consumer impact | Resolve before |
|---|---|---|
| C-03 | **Open.** M1 F00/F01 must choose identity issuance, expiry/revocation and case membership; M4 U01 must handle those tokens/errors safely. Tests must cover two actors/cases, invalid/expired identity and foreign/missing resources without existence leaks. BearerAuth alone does not choose the mechanism. | Protected routes/client integration in 1A, including later source playback/corrections |
| C-04 | **Open.** M1 F03 intake and M2 P04/P14B need compatible byte/row/BOM/column/content validation and reject-before-run versus failed-accepted-run policy; M4 U03/U05 consume the corresponding errors/states. Later M2 adapters must pin layouts/models/runtime/resources/private boundaries for M3 source consumption and M4 source/playback views, including local speech offsets/codecs/silence/failure controls. | First CSV intake/processing in 1A/1B; later decisions before their own adapters in 3A/3B |
| C-05 | **Open.** M3 G02 must version functions, absent inputs, weights/bands/ties, confidence/count/source-quality/independence treatment and positive/counterexample goldens. M2 lineage must support those rules; M4 must explain actual factors, without treating source derivatives as independent corroboration. Fixed listTriage pagination policy remains authoritative. | G02 and scoring/factor implementation in 1C, then later factor wiring |
| C-06 | **Open.** G03 must record provider/model/privacy/cost/credentials/prompt/verification/fallback policy for M3 retrieval, M4 generation/verification and M1 private provenance. Real approved-provider tests differ from no-paid CI adapters. | 5A/5B final RAG; does not block local speech or independently approved deterministic retrieval |

No future policy was selected for G00, no four-signoff ceremony is required, and no blanket all-clear is claimed. Existing queue entries in COMMUNICATION retain the unresolved questions.

### Commands and observed results

Local runtime: **Linux, Node 22.23.3, npm 12.2.0, Python 3.14.8**. The default Python environment has jsonschema 4.26.0; it was not used for the passing suite. A scratch `/tmp/evora-g00-venv` with system site packages uses **jsonschema 4.25.1**, copied with its distribution metadata from the existing uv cache after pip installation failed DNS resolution. Package metadata and the imported module path were checked. This is an offline cache workaround, not clean installation or Python 3.12/Windows/CI proof.

All five requested npx invocations were attempted and exited **1**, failing registry DNS resolution with `EAI_AGAIN`; npm also could not write its default home log directory. An offline npx retry lacked registry metadata (`ENOTCACHED`). The TypeScript attempt used `npm_config_fetch_retries=0` and writable `/tmp` logs to avoid repeated network waits. No tool version or API change was made to bypass validation. Existing cached package manifests confirmed the exact requested versions, and direct Node CLI equivalents produced these results:

| Check | Observed result |
|---|---|
| Redocly 2.57.0 lint | **Pass, exit 0**; one existing `info-license` warning, no license invented |
| Redocly 2.57.0 bundle | **Pass, exit 0**; fresh `/tmp/evora-openapi.json` |
| openapi-typescript 7.10.1 generation | **Pass, exit 0**; fresh `/tmp/evora-api.d.ts` |
| TypeScript 5.9.3 `--noEmit` compilation | **Pass, exit 0** |
| `verify_coordination.py /tmp/evora-openapi.json` | **Pass, exit 0**; 27 operations, 126 tasks, 18 checkpoints, 39 capabilities, 40 proposal sections/mappings; fixture rows network=2, GPS=1, messages=1 |
| `unittest discover -s scripts -p 'test_*.py' -v` with bundle and jsonschema 4.25.1 | **Pass, exit 0; 122 tests**, including malformed contracts, missing 400/snapshot/source links, duplicate/cyclic/misordered tasks, case-shaped synthetic examples and transcription handoffs |
| DESIGN 0.4.0 lint | **Pass, exit 0**; zero errors, zero warnings, one token-summary info |

Edited-tree read-back: the coordination verifier passed again and the full suite returned **122 tests, OK, no skips**. The focused missing-400 negative also passed. `git diff --check` and the base-to-working-tree spec comparison exited 0; `git status`/diff showed only the four authorized documentation files on `feat/g00-coordination-base`. No file was staged, committed, pushed or merged.

Exact successful offline commands (package paths are this machine's pre-existing cache, not new repository dependencies):

```sh
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js lint specs/openapi.yaml
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js bundle specs/openapi.yaml --output /tmp/evora-openapi.json
node /home/whale2186/.npm/_npx/2ffac754ed3026da/node_modules/openapi-typescript/bin/cli.js specs/openapi.yaml -o /tmp/evora-api.d.ts
node /home/whale2186/.npm/_npx/a322a253dbd59f36/node_modules/typescript/bin/tsc --noEmit /tmp/evora-api.d.ts
/tmp/evora-g00-venv/bin/python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g00-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
node /home/whale2186/.npm/_npx/453056feeae89689/node_modules/@google/design.md/dist/index.js lint DESIGN.md
```

Only schema-derived synthetic fixtures and planning mutations were exercised. No FastAPI/React app, DB transaction, authorization enforcement, model, provider, browser or Windows behavior is verified. No previously completed checkpoint exists to regress. Canonical package-download/clean-environment checks remain subject to network availability; no remote CI result or new publication is claimed. G00's documentation is locally prepared; **Checkpoint 0 stays In Progress**, and **G01/G01B/G01C stay Backlog**. After G00 review/handoff acceptance, G01 and independent G01B are next dependency-ready scopes with explicit G/I assignee/paths still required; G01C needs both real skeletons. This session does not start another task.

### How you can test it

Run from the repository root. The canonical commands need registry access or populated package caches. Setup commands below are for a network-enabled environment; this session used the scratch cached environment described above.

- [ ] Read back the base: `git rev-parse HEAD` and `git rev-parse origin/docs/coordination-foundation`. In this uncommitted task checkout both should print `114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb`.
- [ ] Create an isolated checker: `python -m venv /tmp/evora-g00-review-venv`, then `. /tmp/evora-g00-review-venv/bin/activate` (POSIX), then `python -m pip install jsonschema==4.25.1`. Confirm `python -c 'import importlib.metadata as m; print(m.version("jsonschema"))'` prints `4.25.1`.
- [ ] `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` — exit 0, one existing missing-license warning.
- [ ] `npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json` — exit 0, fresh JSON bundle.
- [ ] `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts` — exit 0, generated declaration file.
- [ ] `npx --yes --package typescript@5.9.3 tsc --noEmit /tmp/evora-api.d.ts` — exit 0, no type diagnostics.
- [ ] `python scripts/verify_coordination.py /tmp/evora-openapi.json` — exit 0 with the counts recorded above and artifact-only scope.
- [ ] `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py' -v` — 122 tests, `OK`, no skips.
- [ ] `npx --yes @google/design.md@0.4.0 lint DESIGN.md` — zero errors/warnings.
- [ ] Failure case: `PYTHONPATH=scripts EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest test_verify_coordination.ContractAuditTests.test_missing_error_response_is_rejected -v` — one test `OK`: removing required 400 from an in-memory contract copy raises the expected validation error. The source spec is never edited. This negative is also exercised by the full suite.
- [ ] `git diff --check` and `git diff --exit-code 114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb -- specs/openapi.yaml` — exit 0; `git diff --name-only` lists only the four authorized documentation paths. Checkpoint 0 must read In Progress and G01/G01B/G01C Backlog.

All artifact equivalents and the full negative suite were exercised locally. The canonical npx commands failed in this environment; the clean review-venv installation and remote/Windows runs are untested. Scratch artifacts remain under `/tmp`; no original evidence or repository-generated client was written.

## G01 verification — 2026-10-18

**G01 / Checkpoint 0 / whale2186 / shared integration coordination / In Progress**, locally verified and pending review/integration. Task branch **feat/g01-backend-skeleton**; exact common contract/base and dependency **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**. Starting `git status --short --branch` was clean; `git rev-parse HEAD origin/feat/g00-coordination-base` read back this SHA twice. The user explicitly selected this committed common base; no fresh network fetch, remote CI or main merge is claimed. Allowed paths and dependency handling are in the [G01 card](AGENT_TASKS.md#g01-assignment--2026-10-18).

### Implementation and actual boundaries

- `backend/app.py`: factory, environment/explicit SQLite file configuration, real connection check on lifespan startup and shared validation registration. No public health/docs/OpenAPI/domain routes and no application tables/migrations.
- `backend/database.py`: per-unit-of-work SQLite connections, foreign keys, commit/rollback and unconditional close. Tests read back actual persisted synthetic rows and verify failure/connection isolation; this is not F00 case-access verification.
- `backend/errors.py`: invalid path/query/header/body or malformed JSON produces **400**, exactly `{"code":"INVALID_INPUT","message":"Invalid request input."}`. No submitted input/exception dump is echoed or logged; response-validation errors remain 500. This uses the [documented FastAPI RequestValidationError override](https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions).
- Tests invoke the real FastAPI application through HTTPX async ASGI transport with explicit lifespan contexts and real temporary SQLite files. The `/_test/...` handlers are synthetic test-only validation probes; production apps have zero registered routes. Every invalid response is validated against `ApiError` from the actual shared bundle; no local replacement wire schema or application producer double is claimed. Missing bundle fails tests instead of skipping schema assertions.
- `requirements.txt` pins all **22** runtime/test dependency distributions; `backend/.python-version` pins **CPython 3.14.8**. Local SQLite is **3.54.0**, FastAPI **0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, Uvicorn **0.54.0**, HTTPX **0.28.1**, jsonschema **4.25.1**. Every pin matched observed distribution metadata. The backend README (`backend/README.md`) defines setup/run/configuration and the backend test command.

### Commands and observed results

Environment: Linux, Python **3.14.8**, Node **22.23.3**, npm **12.2.0**. `python -m venv --system-site-packages /tmp/evora-g01-venv` succeeded. Initial `/tmp/evora-g01-venv/bin/python -m pip install --disable-pip-version-check --retries 0 --timeout 8 jsonschema==4.25.1` failed with no matching distribution available from the index. Copied `jsonschema` and `jsonschema-4.25.1.dist-info` from the pre-existing cache `/home/whale2186/.cache/uv/archive-v0/Vs02wiBg28l1Fmlz` into that scratch environment. The full `pip install -r requirements.txt` then exited 0 with every pin already satisfied. This is a tested existing-package/cache environment, **not a clean index installation**.

| Check | Observed result |
|---|---|
| Backend suite below, also with `-W error::ResourceWarning` | **Pass, 14 tests, no skips**; startup/database success and failure, persistence/rollback/close/foreign keys, app isolation, absent routes, valid request, invalid body/path/query/header/JSON, schema shape/redaction and server-error separation |
| Uvicorn factory with `--lifespan on --no-access-log` | Real **startup complete and shutdown complete**; exit 3 when localhost binding was denied. A separate ephemeral socket bind returned `PermissionError`, errno 1 (`Operation not permitted`); no external HTTP listener claimed |
| Redocly 2.57.0 lint/bundle | **Pass**, fresh `/tmp/evora-openapi.json`; one pre-existing `info-license` warning |
| openapi-typescript 7.10.1 / TypeScript 5.9.3 `--noEmit --strict` | **Pass**, fresh `/tmp/evora-api.d.ts`; no repository client/type files written |
| Coordination verifier | **Pass**, 27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 source mappings |
| Coordination unittest suite with jsonschema 4.25.1 | **Pass, 122 tests, no skips**; full output `/tmp/evora-g01-coordination-tests.log` |
| Requested `npx --yes @google/design.md@0.4.0 lint DESIGN.md` | **Failed**, registry DNS `EAI_AGAIN`; writable logs and zero retries used |
| Cached exact DESIGN 0.4.0 CLI | **Pass**, zero errors/warnings |
| `git diff --check`; spec comparison against exact G00 base | **Pass**, unchanged `specs/openapi.yaml`; only allowed paths changed |

Initial synchronous Starlette TestClient startup stalled inside its cross-thread portal; a bounded reproduction timed out. The passing suite uses HTTPX async ASGI transport and explicit real lifespan startup/shutdown, avoiding that portal. An initial test-owned SQLite read-back connection produced a ResourceWarning; it was corrected with explicit closing, and the final warning-strict suite passed. No application failure is hidden by a skipped test.

Exact locally successful verification commands, from the repository root:

```sh
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js lint specs/openapi.yaml
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js bundle specs/openapi.yaml --output /tmp/evora-openapi.json
node /home/whale2186/.npm/_npx/2ffac754ed3026da/node_modules/openapi-typescript/bin/cli.js specs/openapi.yaml -o /tmp/evora-api.d.ts
node /home/whale2186/.npm/_npx/a322a253dbd59f36/node_modules/typescript/bin/tsc --noEmit --strict /tmp/evora-api.d.ts
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
/tmp/evora-g01-venv/bin/python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
node /home/whale2186/.npm/_npx/453056feeae89689/node_modules/@google/design.md/dist/index.js lint DESIGN.md
git diff --check
git diff --exit-code 1721bfff9640263d2799434455cdb9c4f345ac35 -- specs/openapi.yaml
```

The cached CLI paths above are machine-local tool locations; the canonical shared-workflow equivalents use `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml`, `npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json`, `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts`, `npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-api.d.ts`, and `npx --yes @google/design.md@0.4.0 lint DESIGN.md`. Use an activated environment with the pinned requirements for both Python suites. No previously completed checkpoint exists to regress beyond these G00 artifact checks.

### How you can test it

The backend checklist in `backend/README.md` contains exact setup, run, success and malformed-JSON/database failure commands, expected results and cleanup. The backend command is `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s backend/tests -v` (**14 tests, OK**); coordination uses `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py' -v` (**122 tests, OK**). Run the verifier and shared workflow commands above, then `git diff --check` and the exact-base spec comparison. All local test/CLI equivalents were exercised; new package downloads, external HTTP listening, Windows, Python 3.12 application compatibility and remote CI remain unverified.

No unresolved policy blocks this G01 implementation. C-03–C-06 remain open only for their dependent domain rows. G01C must reconcile this tested Python baseline with the current Python 3.12 artifact-only workflow and prove clean Windows/CI skeleton setup; no changes outside G01 paths were made to preempt it. **G01 stays In Progress awaiting review/integration; Checkpoint 0 stays In Progress.** Next dependency-ready task is **G01B**, with an explicit assignee/path handoff; G01C depends on both skeletons. No stage, commit, push, merge, main smoke or another task is authorized or claimed.

## G01B verification — 2026-10-18

Task **G01B / Checkpoint 0**, explicitly assigned to **whale2186** for shared integration coordination on `feat/g01b-frontend-skeleton`. Exact reviewed common base: **e0257a6ad231105b93ae98a97f176ed233a25412** (`feat/g01-backend-skeleton`, which includes G00 at `1721bff`). Starting `git status` was clean; `git rev-parse HEAD` read back this SHA. Allowed paths: `frontend/`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`.

### Implemented architecture and design adherence

- Created React + TypeScript frontend skeleton under `frontend/` using esbuild bundling/serving and React 19.3.0, TypeScript 5.9.3.
- Generated TypeScript interfaces from unchanged `specs/openapi.yaml` (draft 0.3.0) via `openapi-typescript 7.10.1` into `frontend/src/api/schema.d.ts`. A dedicated typecheck suite (`frontend/src/api/schema.type-test.ts`) verifies compile-time contract adherence (e.g. bodyless `startAnalysis` and required `ApiError` properties).
- Adheres to `DESIGN.md` tokens: colors (`#17212B`, `#52606D`, `#175CD3`, `#F5F7FA`, `#FFFFFF`, `#D5DCE5`), fonts (IBM Plex Sans, IBM Plex Mono), semantic landmarks (`<main id="workspace">`, `<aside aria-labelledby="inspector-heading">`, accessible skip link).
- The skeleton renders honest unavailable states when no case is selected or when case access is not yet implemented; it makes zero API requests and presents no mock domain action buttons.

### Commands and observed results

Runtime: **Node 26.7.0, npm 11.19.0, Python 3.14.8**.

| Check | Observed result |
|---|---|
| `npm --prefix frontend run generate:api` | **Pass, exit 0**; types generated fresh from `specs/openapi.yaml` |
| `npm --prefix frontend run check:api` | **Pass, exit 0**; declarations match schema |
| `npm --prefix frontend run typecheck` (`tsc --noEmit`) | **Pass, exit 0**; clean declaration checking |
| `npm --prefix frontend run test` | **Pass, exit 0; 2 tests passed** in 82ms |
| `npm --prefix frontend run build` | **Pass, exit 0**; produces `dist/assets/main.js` and `dist/assets/main.css` |
| Coordination verifier (`verify_coordination.py`) | **Pass, exit 0**; 27 operations, 126 tasks, 18 checkpoints, 17 markdown files |
| Coordination unittest suite (`scripts/test_*.py`) | **Pass, exit 0; 122 tests OK** |
| Backend unittest suite (`backend/tests`) | **Pass, exit 0; 14 tests OK** with `-W error::ResourceWarning` |
| DESIGN 0.4.0 lint | **Pass, exit 0**; 0 errors, 0 warnings |
| Whitespace & spec check | **Pass, exit 0**; unchanged `specs/openapi.yaml` |

### How you can test it

1. `npm --prefix frontend run typecheck` — exit 0, no type diagnostics.
2. `npm --prefix frontend run test` — exit 0, 2 passing tests.
3. `npm --prefix frontend run build` — exit 0, bundle created in `dist/`.
4. Run all backend tests: `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v` — 14 tests, `OK`.
5. Run all coordination tests: `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` — 122 tests, `OK`.
6. Negative check: in `frontend/src/api/schema.type-test.ts`, uncomment an invalid property or omit `code` from `ApiError`; `npm --prefix frontend run typecheck` will fail with diagnostic error.
7. `git diff --check` and `git diff --exit-code e0257a6ad231105b93ae98a97f176ed233a25412 -- specs/openapi.yaml` — exit 0.

Checkpoint 0 remains **In Progress**; G01C remains **Backlog**. Next task is **G01C** (Verify skeleton Windows and CI setup).

## G01C verification — 2026-10-18

**G01C / Checkpoint 0 / whale2186 / shared integration coordination / In Progress.** Branch `feat/g01c-skeleton-ci`; exact user-selected common contract/base **328c103d0f0383c7b4979bd8199b4201408e2a68** (`feat/g01b-frontend-skeleton`). Starting `git status --short` was empty, and branch/HEAD matched the assignment. `git log` and local branch refs read back real **G01 e0257a6ad231105b93ae98a97f176ed233a25412**, **G01B 328c103d0f0383c7b4979bd8199b4201408e2a68** and **G00 1721bfff9640263d2799434455cdb9c4f345ac35** in the accepted ancestry. No fresh remote fetch or hosted CI/main result is inferred. See [assignment](AGENT_TASKS.md#g01c-assignment--2026-10-18) and [live exit-gate record](ROADMAP.md#g01c-live-record--2026-10-18).

### Changes and supported baseline

- `.github/workflows/contract.yml`: one matrix runs **ubuntu-latest/Bash** and **windows-latest/PowerShell**, with fail-fast disabled so one OS cannot cancel the other's evidence. Read-only repository permission and existing PR/push triggers remain. Each command has a separate step; native command failures cannot be hidden by a later successful PowerShell command.
- CPython **3.14.8** comes from `backend/.python-version`; Node **22.23.3** and npm **12.2.0** match the frontend manifest, replacing the old Python 3.12 artifact-only workflow and reconciling the frontend README's historical Node 26/npm 11 claim. CI asserts runtime versions, prints SQLite, installs `requirements.txt`, runs `pip check`, and clean-installs the committed frontend lockfile with `npm ci`.
- Both OS legs run OpenAPI lint/bundle, independent generated declaration compilation, coordination verifier/negative/schema tests, warning-strict backend tests, frontend `check:api`/`typecheck`/`test`/`build`, DESIGN lint and commit whitespace checks. Bundle paths are quoted and use `runner.temp` in step contexts. Actionlint initially rejected `runner.temp` at job-env scope; moving the bundle env to each Python suite's step resolved it.
- `PYTHONUTF8=1` is explicit in both legs and PowerShell instructions because existing tests use default-encoding reads of UTF-8 planning files. Backend/frontend READMEs contain exact native PowerShell setup/run/negative commands and version/platform limits. No cross-directory Markdown link from `docs/` to a backend/frontend file was added; these paths are code mentions.
- Only the six authorized files changed. `specs/openapi.yaml` 0.3.0, requirements, frontend package/lockfile, generated API types and application/tests remain unchanged. No new domain producers or doubles were introduced. Backend probes exercise real FastAPI/HTTPX/SQLite with synthetic test-only routes; frontend tests render the real React shell without domain/API data.

### Commands and observed results

Local host: **Linux, CPython 3.14.8 / SQLite 3.54.0, Node 22.23.3 / npm 12.2.0**. Unlike earlier sessions, package-registry access worked. A new `/tmp/evora-g01c-clean-venv` was created with **no system site packages**; installation from `requirements.txt` passed, using ordinary registry downloads/cache, without manual package copying. All **22 pins** matched distribution metadata, including FastAPI **0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, Uvicorn **0.54.0**, HTTPX **0.28.1**, jsonschema **4.25.1**. `pip check` found no broken requirements. Frontend `npm ci` installed the lockfile with React/React DOM **19.3.0**, TypeScript **5.9.3**, esbuild **0.28.1**, openapi-typescript **7.10.1**; it reported zero vulnerabilities at this run.

| Check | Actual result |
|---|---|
| Clean backend install / pip check / metadata read-back | **Pass**, 22 pins match in isolated venv |
| `npm --prefix frontend ci` | **Pass**, lockfile unchanged; npm warned that esbuild's postinstall was blocked by its script policy, but the installed platform binary supported all subsequent tests/builds without a policy override |
| Redocly **2.57.0** lint and fresh JSON bundle | **Pass**, one pre-existing missing `info.license` warning |
| openapi-typescript **7.10.1** generation / TypeScript **5.9.3** `--noEmit --strict` | **Pass**, scratch declarations compile; committed types unchanged |
| Coordination verifier | **Pass**, 27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 proposal mappings; 18 Markdown files |
| Full `scripts/test_*.py` suite, jsonschema **4.25.1** | **Pass, 122 tests, no skips**; includes mutation negatives and synthetic wire examples; log `/tmp/evora-g01c-coordination-tests.log` |
| Backend warning-strict suite, clean venv | **Pass, 14 tests, no skips**, real SQLite read-back/rollback/close/isolation/startup failure and HTTP 400 schema validation |
| Requested backend regression using `/tmp/evora-g01-venv/bin/python` | **Pass, 14 tests**, `-W error::ResourceWarning` |
| Frontend API freshness / typecheck / test / build | **Pass**, 2 tests, no skips; `dist/index.html`, `dist/assets/main.js` and `main.css` produced |
| DESIGN **0.4.0** via requested npx command | **Pass**, zero errors/warnings |
| Actionlint **1.7.7** on final workflow | **Pass**, no diagnostics; installed only under `/tmp/evora-g01c-bin` |
| Missing-bundle negative | **Pass**, deliberately missing scratch bundle makes the focused backend schema test exit **1** with `FileNotFoundError`; it cannot silently skip validation |
| Stale declaration negative | **Pass**, scratch stale declaration makes openapi-typescript `--check` exit **1**, `Generated types are not up-to-date!`; scratch contents and source declarations stay unchanged |
| Localhost server smoke | **Pass**: Uvicorn on `127.0.0.1:18000` completed startup, created temporary SQLite, returned **404** for `/`, then completed shutdown (exit 0); frontend dev server on `127.0.0.1:5173` returned **200** with the root mount element, then was stopped with SIGINT |
| Whitespace, exact-base spec/package/type comparison and index check | **Pass**, only authorized paths changed; nothing staged |

Exact successful Linux commands, from the repository root (the environment below already exists from this run):

```sh
python -m venv /tmp/evora-g01c-clean-venv
/tmp/evora-g01c-clean-venv/bin/python -m pip install --disable-pip-version-check --retries 0 --timeout 10 -r requirements.txt
/tmp/evora-g01c-clean-venv/bin/python -m pip check
node --version
npm --version
npm --prefix frontend ci
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts
npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-api.d.ts
python scripts/verify_coordination.py /tmp/evora-openapi.json
PYTHONUTF8=1 EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npx --yes @google/design.md@0.4.0 lint DESIGN.md
/tmp/evora-g01c-bin/actionlint .github/workflows/contract.yml
git diff --check
git diff --exit-code 328c103d0f0383c7b4979bd8199b4201408e2a68 -- specs/openapi.yaml requirements.txt frontend/package.json frontend/package-lock.json frontend/src/api/schema.d.ts
git diff --cached --exit-code
```

The local npx/npm network attempts set `npm_config_fetch_retries=0` and `npm_config_fetch_timeout=10000` to bound registry waits; the same pinned commands passed with normal cache/download resolution. Actionlint setup was `GOBIN=/tmp/evora-g01c-bin go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.7`. This optional local workflow lint is not a substitute for hosted runner execution.

### Windows PowerShell reproduction — pending execution

Supported target: **Windows x64, PowerShell 7, CPython 3.14.8 with `py` launcher, Node 22.23.3, npm 12.2.0**, writable checkout/temp/package prefix and package-registry access. No clean Windows execution is claimed here. Use a fresh checkout without an existing `.venv`; run from the repository root. Commands use `.cmd` wrappers and the venv executable directly, avoiding activation-script policy changes.

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
npm.cmd --prefix frontend ci
$env:EVORA_CONTRACT_BUNDLE = Join-Path $env:TEMP 'evora-openapi.json'
$apiTypes = Join-Path $env:TEMP 'evora-api.d.ts'
npx.cmd --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output "$env:EVORA_CONTRACT_BUNDLE"
npx.cmd --yes openapi-typescript@7.10.1 specs/openapi.yaml -o "$apiTypes"
npx.cmd --yes --package typescript@5.9.3 tsc --noEmit --strict "$apiTypes"
& .\.venv\Scripts\python.exe scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
& .\.venv\Scripts\python.exe -m unittest discover -s scripts -p 'test_*.py' -v
& .\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm.cmd --prefix frontend run check:api
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build
npx.cmd --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

Each command must exit **0**; stop if `$LASTEXITCODE` is nonzero before continuing manually. Expected: versions above (record actual bundled SQLite), no broken requirements, jsonschema **4.25.1**, verifier counts above, **122 coordination / 14 backend / 2 frontend tests**, generated types compile, build assets exist, DESIGN zero errors/warnings. The existing missing-license warning is nonblocking. CI runs commands in separate steps and fails the leg on any nonzero exit.

Run backend in one window with `& .\.venv\Scripts\python.exe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log`, then `curl.exe -i http://127.0.0.1:8000/` in another: expect startup completion and **404**. Run `npm.cmd --prefix frontend run dev` and open `http://127.0.0.1:5173`: expect the shell's no-case/unavailable-access state. Stop each with Ctrl+C. These native Windows/server/browser steps remain untested in this session.

Known setup boundaries: wrong/missing runtime, unwritable package prefix/private storage, registry failure or unavailable native wheels/binaries must fail setup rather than justify changing pins or bypassing checks. Keep esbuild optional platform dependencies enabled and do not reuse Linux `node_modules` on Windows. SQLite is bundled with Python and can differ by build. POSIX mode 0700 does not establish Windows ACLs; use private synthetic storage and do not infer production privacy from this skeleton. No native Windows/browser/accessibility, Neo4j, model/provider or full-scope reproducibility result is established here. The npm esbuild script-policy warning above did not block Linux build/test and no policy was relaxed.

### How you can test it

- [ ] Run the complete Linux sequence above in the pinned environment: expect every positive command to exit **0**, with **122 / 14 / 2 tests** and unchanged contract/package/type artifacts. Linux commands and combined regression were exercised here; use a new scratch venv path to independently repeat a clean install.
- [ ] Run the PowerShell sequence and server steps above on native Windows: expect the same checks/counts, startup/404 and the honest frontend shell. **Pending**, not demonstrated by the Linux tests or actionlint.
- [ ] Failure case, after building the bundle, run `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v`: expect one test **OK**, proving malformed synthetic JSON returns schema-valid **400** without echoing input. PowerShell equivalent: `& .\.venv\Scripts\python.exe -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v` with the bundle env already set. The Linux negative was exercised in both full backend suites.
- [ ] Check the freshness failure without editing repository files: `printf '%s\n' '// Synthetic stale declaration' > /tmp/evora-g01c-stale-api.d.ts`, then `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-g01c-stale-api.d.ts --check`: expect exit **1** and `Generated types are not up-to-date!`. Remove only that scratch probe with `rm /tmp/evora-g01c-stale-api.d.ts`. The same negative passed using an automatically cleaned temporary directory; exact PowerShell equivalent is in `frontend/README.md`.
- [ ] When publication is separately authorized, inspect both matrix jobs on the exact reviewed commit/PR. Record CI run/commit, OS, versions and each suite result in this record; a workflow definition or push alone is not success. Current triggers run on PRs and pushes to `main`/`docs/coordination-foundation`; a feature-branch push alone does not trigger it. This session made no stage/commit/push/merge or hosted run.

Tests use synthetic content and clean their temporary SQLite/probe files. Manual server use leaves an ignored `storage/evora.sqlite3`; remove only your own synthetic database after shutdown. Bundle/types/env artifacts stay in ignored or scratch locations. Backend and frontend runtime smoke cover HTTP startup and shell delivery, not an end-to-end domain application or browser audit.

**Checkpoint 0 exit evidence is complete.** Both `ubuntu-latest` and `windows-latest` CI jobs passed on GitHub Actions PR #1 (Run ID **39102433077**). Checkpoint 0 is **Complete**. Next active checkpoint is **1A**: **F00 / sharmelas-925** requires C-03 identity policy before protected APIs; **U01 / JebasJ** consumes F00. No new shared task is automatically assigned to whale2186. G01D/G02 in 1C need a separate handoff.

## U01 verification — 2026-10-22

**U01 / Checkpoint 1A / M4 / JebasJ / In Progress**, branch
`feat/u01-authenticated-api-client`, exact published coordination base
**6496c5e9e17f2000b64a64f79d2fb166c6ce2094**. Clean starting HEAD and freshly
fetched `origin/docs/coordination-foundation` matched; remote main was inspected
and still contains only the initial README. No other active U01 branch was
published. The base includes accepted G01B **328c103d0f0383c7b4979bd8199b4201408e2a68**
and G01 **e0257a6ad231105b93ae98a97f176ed233a25412** ancestry. The task is selected
under the user's one-task automatic assignment; no M1 or shared G/I work is taken.
See [assignment](AGENT_TASKS.md#u01-assignment--2026-10-22) and
[live state](ROADMAP.md#u01-live-record--2026-10-22).

The shared typed Fetch client derives its API from committed generated `paths`,
with one configurable server origin, closure-held bearer token, shared
HTTP/protocol/network errors, explicit JSON/multipart/byte transport and session
invalidation. Token replacement/logout/401 abort requests and reject late old
session data; a stale old-session 401 cannot clear the new actor's token.
The React provider shares the client and resets descendant UI state on session
changes. No login/refresh endpoint, hard-coded runtime token, case UI, backend
route or new package is added. The sole API/schema, generated types, dependency
manifests, backend and entire FEATURE_SCOPE (including approved transcription
and corrections) remain unchanged. Only the assignment/live/result entries in
shared docs are changed for this task.

**Dependency disclosure:** F00 is absent. The automatic-selection reference
allows U01 against a disclosed fixture. Fetch doubles and temporary localhost
HTTP servers serve only schema-derived synthetic responses for transport tests;
they do not implement or prove backend authentication, token expiry/revocation,
membership or browser CORS. C-03's later declared resolution supplies bearer,
memory-only token and 401/404 handling; no unresolved provider choice is guessed.
Successful JSON is statically typed, not fully schema-validated by the runtime
client. The seven synthetic fixture objects were separately validated against
the actual bundled contract using jsonschema 4.25.1 plus format checking.

Actual Windows environment: **Python 3.14.8 / SQLite 3.50.4 / Node 22.23.3 /
npm 12.2.0 / jsonschema 4.25.1**, existing isolated `.venv` and locked frontend
dependencies prepared earlier. `pip check` passes. No system configuration,
new dependency installation, model/provider execution or new hosted CI run.

| Check | Actual result |
|---|---|
| Frontend generated API freshness/typecheck/build | **Pass**, no type errors; committed declarations unchanged; compile negatives enforce path/method/body/query/header/result contract |
| Frontend suite including prior skeleton regressions | **19 tests pass, no skips**: client transport/session/failure tests, provider/static rendering and original two shell tests |
| Focused `401 invalidates` failure case | **1 selected test passes**: clears token, aborts outstanding work, rejects late prior-session response, no retry/refresh |
| Real Fetch/HTTP fixture | **Pass**, actual localhost response read-back and redirect refused before destination receives any request; fixture is not F00 |
| Synthetic fixtures checked against bundle | **7 responses pass** Draft 2020-12 validation and format checking (`Case` x2, `CasePage` x2, `ApiError`, `Evidence`, `AnalysisRun`) |
| OpenAPI lint/bundle and scratch generated strict TypeScript | **Pass**, existing missing `info.license` warning remains |
| Coordination verifier | **Pass**, 27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 proposal mappings / 18 Markdown files |
| Full coordination Python suite | **122 tests pass, no skips**; `.cache/u01/coordination-tests.log` |
| Warning-strict backend regression | **14 tests pass, no skips**; real SQLite/FastAPI probes, `.cache/u01/backend-tests.log` |
| DESIGN 0.4.0 | **Pass**, zero errors/warnings, explicit `designmd` alias avoids Windows name collision with DESIGN.md |
| Real skeleton startup/HTTP regression | **Pass**, backend startup creates temporary synthetic SQLite and returns 404 `/`; frontend serves root/JS/CSS with 200; own server processes stop and synthetic DB is removed |
| Diff/scope/whitespace/index review | **Pass**, allowed frontend/docs paths only; full scope/spec/generated declarations/package pins/backend unchanged; nothing staged |

### How you can test it

From `C:\Users\jebas\EVORA\EVORA`, start the prepared tool shell with
`.\.cache\setup\evora-shell.cmd` (local helper only; no system changes).
The checked frontend/backend READMEs supply fresh-machine prerequisites. Run:

```powershell
npm.cmd --prefix frontend run check:api
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build
node --test --test-name-pattern="401 invalidates" frontend/test/api-client.test.mjs
npx.cmd --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache/u01/evora-openapi.json
npx.cmd --yes openapi-typescript@7.10.1 specs/openapi.yaml -o .cache/u01/evora-api.d.ts
npx.cmd --yes --package typescript@5.9.3 tsc --noEmit --strict .cache/u01/evora-api.d.ts
$env:EVORA_CONTRACT_BUNDLE = Join-Path (Get-Location) '.cache/u01/evora-openapi.json'
& .\.venv\Scripts\python.exe scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
& .\.venv\Scripts\python.exe -m unittest discover -s scripts -p 'test_*.py' -v
& .\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
npx.cmd --yes --package @google/design.md@0.4.0 designmd lint DESIGN.md
git diff --check
```

- [ ] Expect positive commands to exit 0, **19 / 122 / 14** full-suite passes,
  **1** focused 401 test pass, no type diagnostics, the existing license warning
  only, and successful JS/CSS build. These commands were actually exercised.
- [ ] Synthetic inputs are two UUID cases/tokens and original bytes
  `[0,255,10,13,42]`; fixtures and expected errors live in `frontend/test/`.
  The selected 401 test is the relevant failure case; no real evidence required.
- [ ] `$env:EVORA_API_BASE_URL='http://127.0.0.1:8000'` then
  `npm.cmd --prefix frontend run dev`: expect the existing no-case/unavailable
  shell at `http://127.0.0.1:5173`, not a functioning sign-in/case workflow.
  Stop with Ctrl+C and remove that process-local environment setting if set.
  Automated HTTP smoke was exercised; interactive browser/accessibility and
  React DOM remount verification were **not** exercised.
- [ ] After F00 is available, run client tests against the real producer with
  its approved synthetic identities and same/foreign/missing cases, browser
  origin/CORS and session changes. This real integration remains **untested**
  and is required before U01 can be Complete; a fixture is not that proof.

The prior Checkpoint 0 regressions passed locally, but no new Linux/Windows
hosted CI run, production identity or end-to-end investigation is claimed.
U01 remains **In Progress**, awaiting user review and real F00 integration.
U02 is the next catalog row, blocked on accepted U01 and real F02; F00 remains
M1/sharmelas-925's prerequisite. The user subsequently authorized committing and
pushing this scoped task branch on 2026-10-22. No second task or merge is authorized;
publication does not establish real F00 integration or mark U01 Complete.

## U02 verification — 2026-10-31

Task U02 / 1A / M4 / JebasJ, branch `feat/u02-case-list-ui`, clean common base
`909009d21198fd751db49863f581b032875fa5e0`, matching live origin. U01
42d03125b710ee37b7505361388fb15792ffe306 and F02 c8077f5 are verified ancestors;
F00/F01/G01B are real merged dependencies. User approved scoped implementation
and commit/push to configured yazh-07/EVORA; no merge or second task.

### Actual results

Windows execution with Node 22.23.3, Python 3.14.8/SQLite 3.50.4 and jsonschema
4.25.1. Installed all 22 existing Python pins using the scratch Python runtime;
`python -m pip check` passed. Existing frontend node_modules/lockfile used;
no clean frontend reinstall or new hosted CI is claimed.

| Check | Actual result |
|---|---|
| `npm.cmd --prefix frontend test` | **25/25 pass**, no skips; 7 new state/race/negative tests plus shell/client/provider regressions |
| `npm.cmd --prefix frontend run build` | API freshness, TypeScript and esbuild pass; no generated/schema changes |
| `node test/cases.integration.mjs` from frontend, EVORA_TEST_PYTHON selecting installed scratch runtime | PASS real loopback Fetch to FastAPI/SQLite: empty account; create 21 actor-one + 1 actor-two synthetic cases through real API; 20+1 pagination/detail, out-of-range page, isolation, identical foreign/missing 404, invalid limit 400, invalid-token 401, built same-origin UI HTTP 200; server/owned scratch database cleaned |
| `python scripts/verify_coordination.py <bundle>` | PASS 27 operations, 126 tasks, 18 checkpoints, 39 capabilities, 40 proposal mappings |
| `EVORA_CONTRACT_BUNDLE=<bundle> python -m unittest discover -s scripts -p 'test_*.py' -v` | **122/122 pass**, no skips |
| `EVORA_CONTRACT_BUNDLE=<bundle> python -W error::ResourceWarning -m unittest discover -s backend/tests -v` | **47/47 pass**, no skips, real SQLite/FastAPI; existing F00 isolated membership doubles remain labeled in their tests |
| Redocly 2.57.0 lint/bundle | PASS; one pre-existing info-license warning |
| openapi-typescript 7.10.1 generate + TypeScript 5.9.3 `tsc --noEmit --strict <generated.d.ts>` | PASS |
| DESIGN 0.4.0 lint | PASS zero errors/warnings |
| Browser smoke against same-origin synthetic demo | PASS 21-case list/detail, 20+1 pagination, actor-two empty state, logout/reload clearing session, invalid-token return to entry, selected detail keyboard focus; screenshot visually inspected at about 700px width |

The first typecheck caught a mistaken case path placeholder; corrected to the
existing `{caseId}` contract before the passing runs. Initial focused tests
failed on that mistake, then all passed. Browser inspection caught an encoding
artifact in range punctuation; fixed, rebuilt and rechecked. One helper build
was invoked from the wrong directory and failed; correct frontend-directory
build passed. Initial Python probe had no FastAPI; installing unchanged pins
resolved it. No failed result is being presented as a passing check.

Exact tool versions were run through cached CLI entry points as well as npx;
registry-backed npx resolution was slow and its TypeScript fetch failed with
UNABLE_TO_VERIFY_LEAF_SIGNATURE. No TLS bypass was used. The installed exact
TypeScript 5.9.3 CLI subsequently passed strict generated-type compilation;
the cached DESIGN 0.4.0 CLI passed independently. Commands mirror the shared workflow.
Previous completed Checkpoint 0 coordination/backend/frontend regressions are
included on this combined candidate; real loopback startup/HTTP was exercised.
No main merge smoke or checkpoint promotion is claimed.

### Doubles, limitations and handoff

Frontend state tests use explicit schema-derived Fetch doubles for failures,
malformed responses, unsafe text and races; server rendering checks markup.
The separate integration runner uses real HTTP, auth guard, case membership,
case persistence/listing and SQLite. Only identities/data are synthetic.
The browser demo mounts the unchanged backend and built UI on one loopback
origin; its static/no-store wrapper is test tooling, not new application routes
or a cross-origin deployment policy. Production authentication, formal screen
reader/accessibility audit, full desktop/mobile breakpoint matrix and new
hosted CI remain untested. No evidence/model/provider services were involved.

All full initial capabilities and approved transcription additions remain
unchanged in FEATURE_SCOPE, proposal, task catalog and OpenAPI. U02 stays
**In Progress** pending review/integration. The user authorized commit/push,
not merge. Next M4 row U02B requires accepted U02 or explicit dependency
handoff. The How you can test it section in `frontend/README.md` contains
exact setup/commands, synthetic inputs, expected output, 401 failure and cleanup.

### U02 pre-merge revalidation — 2026-10-31

The authorized merge rerun caught seven coordination-fixture failures after
U02's final documentation edits: CLI mutation tests copy planning artifacts,
not the frontend README, so new relative Markdown links to that file failed
inside those isolated fixtures. Replaced only those two new links with plain
repository file references; no verifier/test scope or product behavior changed.
The earlier 122-test pass preceded those final links; the merge must use the
corrected-tree rerun rather than rely on that historical result.

Corrected-tree revalidation: **122 coordination / 47 backend / 25 frontend
tests pass**, no skips. Real HTTP/SQLite integration, API freshness/typecheck/
build, contract lint/bundle/generated strict types, verifier, DESIGN and diff
checks pass. Existing info-license warning remains. No product code changed
for this correction and no initial scope was removed or deferred.

### U02 authorized integration — 2026-10-31

The user explicitly requested merging U02 after the task push. Verified clean
worktree and fetched origin: shared base remained 909009d21198fd751db49863f581b032875fa5e0.
Committed the bounded planning-reference correction as 3bbbd63, then merged
U02 without conflicts into `docs/coordination-foundation` at
**9f2cc8ac64426ef2b0bb9d917fd7afdb777b606f**. No main merge, force push,
branch deletion or second task is involved.

The corrected combined candidate passes **122 coordination, 47 backend and
25 frontend tests**, no skips, plus real API integration, freshness/typecheck/
build, lint/bundle/generated strict types, verifier and DESIGN. Post-merge
smoke on that exact merge commit again passes real HTTP/SQLite 21+1-case
pagination/detail/actor isolation/empty/400/401/404 checks and static UI HTTP
200; coordination verifier and merge whitespace checks pass. The current
ledger now records U02 Complete after actual dependency integration and user
acceptance. Checkpoint 1A remains open. U02B is the next M4 row with a fresh
scoped assignment on the updated verified shared base. New hosted CI remains
pending and earlier documented production-auth/accessibility/viewport limits
are unchanged; no new browser test is claimed in this merge-only turn.

### U02B verification — 2026-10-31

Task **U02B / Checkpoint 1A / M4 / JebasJ**, branch
`feat/u02b-case-creation-ui`, exact reviewed starting common base
**16975127177f3c609249bd648455d364e0bfc46c**. Starting status was clean;
HEAD and merge-base with local `docs/coordination-foundation` matched. No
remote fetch, commit, push or merge was performed. Real U02/F01 and
U01/F00/F02 are integrated ancestors. Only the explicitly allowed frontend
paths and three bounded documentation records changed. Backend, OpenAPI,
package manifests and lockfile remain unchanged.

| Exact command from repository root | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | Exit 0; bundle produced |
| `npx @redocly/cli lint specs/openapi.yaml` | Exit 0; existing info-license warning |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | Exit 0; planning/contract verification |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | Exit 0; 122 tests pass |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests` | Exit 0; 47 tests pass |
| `npm --prefix frontend run check:api` | Exit 0; generated API types current |
| `npm --prefix frontend run typecheck` | Exit 0 |
| `npm --prefix frontend run test` | Exit 0; 31 tests pass, no skips |
| `npm --prefix frontend run build` | Exit 0; includes API freshness and TypeScript checks |
| `(cd frontend && node test/cases.integration.mjs)` | Exit 0; real HTTP/FastAPI/SQLite creation 201, immediate list read-back, invalid whitespace title 400 and actor isolation; prior U02 regression passes |
| `npx @google/design.md@0.4.0 lint DESIGN.md` | Exit 0; zero errors/warnings |
| `git diff --check` | Exit 0 |

Frontend unit/state tests use schema-derived Fetch doubles and server-rendered
React markup. They check labeled/constrained controls, blank/whitespace and
length validation without requests, exact valid payload, busy/duplicate guard,
400 message safe rendering, confirmed selection/list refresh, refresh failure,
replaced/disposed sessions and late-list race protection. Real integration
uses the existing synthetic local identity verifier with real F00/F01/F02
HTTP and SQLite, not substituted producer behavior; the temporary database
is cleaned up. Read-back confirms the returned case ID, title and description,
and its presence in listCases. No application evidence or credentials used.

The UI clears inputs after success; its existing detail-heading focus effect
handles confirmed selection, and failed submissions focus Title. New browser
interaction/focus, screen reader, viewport, Windows and hosted CI runs were not
performed. Static markup/state tests do not establish those behaviors in a
browser. No main-merge smoke or checkpoint exit is claimed. Documentation
uses plain repository file references across directories. U02B stays
**In Progress** pending review/integration; Checkpoint 1A remains open.
Next M4 row is U03; no second task was implemented. Full proposal and approved
transcription scope remain unchanged.

Verification environment: the default Python had jsonschema 4.26.0. Installed
4.25.1 only into `/tmp/evora-u02b-jsonschema` with
`python -m pip install --target /tmp/evora-u02b-jsonschema jsonschema==4.25.1`;
exported `PYTHONPATH=/tmp/evora-u02b-jsonschema` for the final Python checks
above. The system environment and repository dependencies were not changed.
The initial root-directory integration invocation failed to locate the server;
the runner now resolves its server directory relative to its own file. Both
root and frontend-directory invocations subsequently pass. The initial unit
run preceded the two added race/retry regressions; final results above include
both regressions and the final documentation tree.

### F03 verification — 2026-10-31

F03 / 1A / M1 / sharmelas-925 is **In Progress**, implemented locally for
review on `feat/f03-evidence-upload`. Clean starting HEAD/common contract
`1b7d92826a5af23431f3936c1c6152f3ad634065` includes real merged F00/F01/F02,
U01/U02/U02B; no fixture case-access/database producer. Tests use synthetic
authentication identities and permitted synthetic evidence. No staging, commit,
push or merge. Checkpoint 1A remains open; next M1 row F04 after review.

F03 intake policy is now bounded: preserve opaque original bytes (including
empty files); 50 MiB limit; reject unsafe filename traversal/separators/control
characters and portable path punctuation; reject unknown kinds, blank labels,
and invalid or empty acquisition timestamps. Keep valid source labels and
RFC 3339 acquisition values unchanged. M2 P04/P14B still own CSV parsing,
UTF-8/BOM/row/layout validation and accepted-run failure semantics. Those C-04
choices remain open and do not block opaque preservation. M4 U03 consumes the
existing 400/413 ApiError outcomes; neither content verification nor parser
support is implied by client-supplied kind/media type.

Read-back verifies 201 Evidence against the bundled draft 0.3.0 schema,
fixture SHA-256/size, exact private file bytes and SQLite values, no public path,
unique uploads without overwrites, omitted acquisition time and preserved
explicit acquisition text. Negatives cover missing/invalid auth, identical
foreign/missing case response bodies and headers, invalid UUID, missing fields,
kind/label/timestamp failures, traversal, partial-copy failure and SQL insert
rollback with unlink. Size boundaries exercise the real chunk loop at a patched
64 KiB limit (exact boundary accepted, one extra byte rejected); this is not a
50 MiB load benchmark. Startup regression now includes the evidence table.

Executed on Linux, CPython 3.14.8. A clean isolated pinned environment was
installed with:

```sh
uv venv --python /usr/bin/python3.14 /tmp/evora-f03-pinned
uv pip install --python /tmp/evora-f03-pinned/bin/python -r requirements.txt
source /tmp/evora-f03-pinned/bin/activate
```

Actual versions: FastAPI 0.143.1, Starlette 1.8.0, Pydantic 2.14.1,
httpx 0.28.1, jsonschema 4.25.1, python-multipart 0.0.32.
Node 22.23.4 / npm 12.2.1 were used (repository engine pins are
22.23.3 / 12.2.0). Initial system-Python checks also passed after correcting
the startup-table assertion; final Python verification uses the clean pinned
environment rather than its newer FastAPI/Starlette/jsonschema packages.

All final commands exit 0:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
npm --prefix frontend run test
npm --prefix frontend run build
npx @redocly/cli lint specs/openapi.yaml
npx @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

Results: **122 coordination / 56 backend (9 focused F03) / 31 frontend tests**,
no skips. Build includes generated API freshness and TypeScript compilation.
OpenAPI has only the existing missing-license warning; DESIGN has no errors
or warnings. No schema/generated-type/frontend behavior changes.

How you can test it:

- [ ] Install/activate the pinned environment and run the commands above;
  expect all exit 0 and the counts above.
- [ ] Run `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v`;
  expect nine passing tests using temporary SQLite and private storage, including
  synthetic network.csv exact hash/size/bytes and automatic cleanup.
- [ ] Failure case: `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_evidence.EvidenceTests.test_database_failure_cleans_file -v`;
  expect one passing test proving an actual SQLite trigger abort removes the file.

Limits: this verifies real in-process ASGI/FastAPI/SQLite/filesystem integration,
not a browser upload or native Windows/hosted CI run. UploadFile multipart is
parsed/spooled before handler execution; 50 MiB is a stored-file limit, not an
ingress body limit. Exclusive UUID-only files and absent mutation APIs provide
application immutability, not service-account/WORM tamper protection. Process
crash recovery between filesystem and SQLite publication is not implemented.
F05 download, F06 audit, U03 upload UI and I00 real assembled intake/runbook exit
evidence remain separate tasks; no phase closure is claimed.

### F04 verification — 2026-10-31

**F04 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f04-evidence-metadata`. Starting status was clean; HEAD and merge-base
with `docs/coordination-foundation` were exactly
**e5273a61e444a2fdf46b236e1f4a56700ac52f57**. This common contract/base
includes real merged F03 and F00/F01/F02/U01/U02/U02B. Only the six assigned
paths changed. No staging, commit, push or merge was performed.

`listEvidence` counts and pages authorized SQLite evidence in one read snapshot,
ordered by `created_at DESC, id ASC`. `getEvidence` joins the evidence UUID to
the granted case UUID. Both reuse current membership authorization and the
existing flat 400/401/404 errors. Public responses omit private storage paths
and absent acquisition times; stored acquisition text remains unchanged.
The sole wire authority remains unchanged `specs/openapi.yaml` draft 0.3.0.
No unresolved decision blocks this row or changes a producer/consumer contract.
M4 U03/U04 consume metadata; U13 consumes paginated evidence and accurate totals.
Future parser, download and audit tasks remain outside this implementation.

All commands below exited 0 on Linux. Python commands used the existing
isolated pinned environment, activated with
`source /tmp/evora-f03-pinned/bin/activate`; repository dependencies were not
changed. Actual runtime: CPython 3.14.8, FastAPI 0.143.1, Starlette 1.8.0,
Pydantic 2.14.1, httpx 0.28.1, jsonschema 4.25.1 and python-multipart 0.0.32.
Node 22.23.4/npm 12.2.1 were used; repository pins remain 22.23.3/12.2.0.

| Exact command from repository root | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | Exit 0; bundle produced |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | Exit 0; planning/contract checks |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | Exit 0; 122 tests pass |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests` | Exit 0; 63 tests pass |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v` | Exit 0; 16 tests pass, including seven F04 tests |
| `npm --prefix frontend run test` | Exit 0; 31 tests pass |
| `npm --prefix frontend run build` | Exit 0; generated API freshness, TypeScript compilation and build pass |
| `npx @redocly/cli lint specs/openapi.yaml` | Exit 0; existing missing-license warning |
| `npx @google/design.md@0.4.0 lint DESIGN.md` | Exit 0; zero errors/warnings |
| `git diff --check` | Exit 0 |

Read-back uses real in-process HTTP/ASGI/FastAPI, file-backed SQLite and F03
multipart uploads, with synthetic bearer identities and permitted synthetic
bytes. No schema-derived upload/database/case-access double is used. The
seven added tests compare every metadata field to the upload response, with
and without acquisition text; check absent private fields; exercise default
20/0 pagination, 23 uploaded items, timestamp ties, limit 1/100, multiple pages,
empty cases and offsets at/beyond total; and verify case/actor isolation,
revoked membership, invalid UUIDs, rejected pagination and missing/invalid auth.
Ordering tests set controlled timestamps on real uploaded test rows to avoid
platform clock-resolution assumptions. Foreign cases, mismatched evidence and
missing resources return identical 404 bodies and headers; no constant-time
certification is claimed. Every response checked by the test helper validates
against the bundled schema when EVORA_CONTRACT_BUNDLE is set.

Reproduction and negative checks:

- Run the focused evidence command above in the pinned environment; expect
  16 passing tests with temporary SQLite/private files cleaned up afterward.
- Run `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_evidence.EvidenceTests.test_metadata_case_and_resource_isolation -v`;
  expect one passing test proving cross-actor denial and same-actor/case URL
  mismatch handling without disclosing evidence in the wrong case.

Limits: no native Windows, hosted CI or browser execution was performed in
this task. All filesystem Path constructions in the evidence tests use
`.resolve()` for Windows short-path compatibility; Linux success does not
establish native Windows execution. Frontend tests retain their existing
transport doubles; backend F04 acceptance uses real producers. Checkpoint 0
local regressions pass, but no new Windows setup proof is claimed. I00's full
assembled intake/download/audit/UI exit evidence remains outstanding;
Checkpoint 1A stays open. F04 remains In Progress pending review/integration.
Next M1 row is F05 under its own assignment; no second task was implemented.

### U03 verification — 2026-10-31

**U03 / Checkpoint 1A / M4 / JebasJ / In Progress**, locally verified pending
review/integration. Starting branch `feat/u03-evidence-upload-ui` was clean at
**69f2e8269b6e6d639889941926bc604a415e3f05**, matching local
`docs/coordination-foundation`; no fresh fetch or remote CI claimed. Real
U01/F03/F04 and F00/F01/F02/U02/U02B are ancestors of that common base. Only
user-allowed frontend and three documentation paths changed; no backend,
specification, dependency or generated-type edits. Nothing staged/committed/
pushed/merged. Draft 0.3.0 remains the sole HTTP authority.

The selected-case UI uses `uploadEvidence`, `listEvidence` and `getEvidence`
through the existing generated client. It sends real FormData file bytes,
validates required file/nonblank label before HTTP, constrains source labels
to 200 characters, disables the upload fieldset/button while submitting and
renders server errors as escaped alert text. Optional acquisition time is
explicitly labeled UTC and sent as RFC 3339; unknown time is omitted. Successful
uploads reset form controls, refresh the first page and display server-computed
ID/hash/size in the inspector. Confirmed metadata survives refresh failure.
Case/session changes abort reads/uploads and discard late responses; development
StrictMode effect reconnect is covered. Pagination uses real server totals and
empty/out-of-range states; detail responses must match selected case/item.

All commands below exited 0 on Linux. Python commands used
`source /tmp/evora-f03-pinned/bin/activate` (existing isolated pinned environment),
with CPython 3.14.8, FastAPI 0.143.1, Starlette 1.8.0, Pydantic 2.14.1,
httpx 0.28.1, python-multipart 0.0.32 and **jsonschema 4.25.1**. The system
Python has newer FastAPI/jsonschema and was not used for acceptance tests.
Node 22.23.4/npm 12.2.1 were used; repository pins remain 22.23.3/12.2.0.
No package/model installation or Windows setup result is claimed.

| Exact command from repository root | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | Bundle produced |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | Planning/contract verifier passes |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | 122 tests pass |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests` | 63 tests pass |
| `npm --prefix frontend run check:api` | Committed generated types fresh |
| `npm --prefix frontend run typecheck` | TypeScript passes |
| `npm --prefix frontend run test` | 39 tests pass, no skips; eight new U03 tests |
| `npm --prefix frontend run build` | API check, TypeScript and production bundle pass |
| `EVORA_TEST_PYTHON=/tmp/evora-f03-pinned/bin/python node frontend/test/cases.integration.mjs` | Real U03 and U02/U02B HTTP integration passes |
| `npx @redocly/cli lint specs/openapi.yaml` | Pass; existing missing-license warning |
| `npx @google/design.md@0.4.0 lint DESIGN.md` | Zero errors/warnings |
| `git diff --check` | Pass |

Read-back: the real localhost FastAPI process uses F00 memberships, F01/F02
cases, F03 original-byte intake and F04 reads with SQLite/private files in an
owned temporary directory. Identity tokens and data are synthetic; no API,
database or evidence producer doubles are used for integration. A synthetic
`network.csv` File is uploaded through the UI's store/client; HTTP 201 is
observed, the expected SHA-256 is independently computed from original bytes,
size equals byte length, the refreshed list equals confirmed metadata and
`getEvidence` returns the same record. Acquired UTC is read back exactly.
Missing-file/blank-label local checks send no request. Direct real invalid
kind/blank-label uploads return 400. An actual 50 MiB + 1 byte upload returns
413, surfaces the server message and leaves the count unchanged. Another actor
cannot list/get that evidence, and an evidence UUID under the wrong case returns
404. Prior U02/U02B creation/pagination/session/isolation HTTP checks also pass.
The helper stores originals beside its temporary database and cleans both up.

Unit tests use synthetic Fetch responses and static React rendering, explicitly
including simulated 400/413/415, malicious text escaping, refresh failure,
malformed/foreign metadata, duplicate submit prevention, pagination, late
responses, session replacement/disposal and effect reconnect. The real F03
accepts opaque MIME content; a simulated 415 proves display handling only,
not backend content-type detection. There is no fabricated content-verification
or scoring result. Artifact lint is separate from these application tests.

Reproduce the targeted negative check after the test build:
`node --test --test-name-pattern='400, 413 and 415' frontend/test/evidence.test.mjs`.
Expect one passing selected test with escaped alerts. Run the integration command
above for real byte-limit/invalid-kind/blank-label and cross-case failures.
Use an interpreter with `requirements.txt` installed if the local temporary
pinned environment is unavailable.

Limits: no browser event/focus/form-reset execution, native Windows or hosted CI
was performed. Those browser behaviors are implemented but static render/store
checks do not prove DOM events. Earlier completed Checkpoint 0 local artifact/
build/backend regressions pass; this does not replace its historical Windows
proof. Checkpoint 1A remains open pending remaining rows and I00's assembled
intake/download/audit/UI exit evidence. U03 stays **In Progress** for review and
integration. Next M4 row U04 needs real F05 and its own bounded assignment;
no additional task was implemented.

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

## U04 verification — 2026-10-31

U04 / 1A / M4 JebasJ, existing feat/u04-evidence-download worktree. User explicitly
authorized finish/commit/push/merge of this one row. Preserved its original draft
as a082eda before updating to shared **d2879c6e1e236add391fb6af40480b9940d22555**
with merge 10c8560. Resolved AGENT_TASKS append conflict by retaining upstream
records and the U04 card. Original dirty U02B checkout is untouched. Real U03
c5c9b5a and F05 d24312f are merged prerequisites; schema/producer/scope unchanged.

### Actual results

Existing Windows Node 22.23.3/npm 12.2.0, Python 3.14.8, jsonschema 4.25.1;
no new packages/models/provider. Shared workflow CLI versions ran from their
existing exact-version cached entry points; no TLS bypass or new CI claim.

- `npm.cmd --prefix frontend test`: **48/48 pass**, no skips, including all prior
  case/upload tests and seven new original-download tests. Initial build failed
  on Windows case-insensitive OriginalDownload/originalDownload resolution;
  renamed controller to downloadController, then reran successfully.
- `npm.cmd --prefix frontend run build`: API freshness/typecheck/esbuild PASS.
- `EVORA_TEST_PYTHON=<pinned Python> node test/cases.integration.mjs` in frontend:
  PASS real F05/controller binary original byte/hash/size and empty read-back,
  foreign original 404/no save; U02/U02B/U03 regressions including 50 MiB rejection
  and source metadata/hash read-back PASS. Real HTTP/FastAPI/SQLite/filesystem;
  synthetic identities/data only. Save callback is a disclosed boundary double.
- `EVORA_CONTRACT_BUNDLE=<bundle> python -W error::ResourceWarning -m unittest
  discover -s backend/tests`: 70 run, **69 PASS / 1 SKIP**; skipped F05 symlink
  escape because this Windows account cannot create symlinks.
- Redocly 2.57.0 lint/bundle PASS, existing info-license warning only;
  openapi-typescript 7.10.1 and TypeScript 5.9.3 strict temporary declarations PASS;
  DESIGN 0.4.0 PASS zero errors/warnings; diff whitespace PASS.
- Browser real same-origin wrapper: select synthetic case/evidence, explicit
  download action triggers actual browser attachment save. Saved file
  `u04-synthetic.bin` in Downloads is **25 bytes**, SHA-256
  fd57bc669c70f7ec86ac82d14b89edf1cb022a38eaba2e754f4c3d84c4d2438f,
  read back using Get-FileHash/Get-Item and matching source. Desktop/narrow
  390x844 inspected, document content/client widths both 375. Revoked only this
  disposable case's synthetic membership, activated download with Enter: real
  404 shown as unavailable original, no success/save. No real evidence involved.

### Integrity and limits

Explicit command only; authenticated no-store client, size/SHA-256 verified
before save, no inline execution or persistent app cache. Temporary Blob URL
revoked idempotently on timeout/retry/unmount/failure. Pending duplicate clicks
are blocked; abort and session-version checks discard stale selection/session
responses. UI reports verified/requested, never assumes OS save completion.
Empty originals supported. Failures never substitute fixture bytes. Fetch/DOM/
save doubles cover integrity mismatch, unavailable/network/server/protocol,
401, cancellation and URL lifecycle; actual browser saving is distinct proof.

Formal screen reader, other browser engines, clean installation and production
identity are untested. Exact setup, synthetic inputs, expected read-back, failure
case and cleanup are in frontend/README.md, How you can test U04 section (plain
file reference so planning-only test fixtures remain self-contained).

U04 remains In Progress until user-authorized tested integration/publication.
All agreed scope and approved additions are preserved; no checkpoint/module
closure. Next checkpoint gate I00 still needs M1 F06/F07/F09 and an explicit
shared assignee; no later M4 work is started in this assignment.

U04 final coordination rerun: `EVORA_CONTRACT_BUNDLE=<bundle> python -m unittest
discover -s scripts -p 'test_*.py'` passes **122/122**, no skips; coordination
verifier PASS 27 operations/126 tasks/18 checkpoints/39 capabilities/40 proposal
mappings. All current-task negatives and previous completed Checkpoint 0
regressions pass with the single explicitly disclosed backend symlink skip.

### U04 integrated completion — 2026-10-31

User-authorized task commit **16a9391252acdc72cdc66c126f284a2629c424ef** was
pushed to feat/u04-evidence-download, then merged without conflicts into the
verified shared branch at **9444ef703ea88cba52280024c11887492b6053bd**.
Post-merge 48 frontend tests, API freshness/typecheck/build and real F05
original/controller byte/hash/size/empty/access-denial smoke plus U03/U02B
regressions pass. Pre-merge 122 coordination and 69 backend pass/1 disclosed
Windows symlink skip; contract/generated strict types/DESIGN pass. Existing
missing-license warning remains. U04 is Complete after actual integration;
Checkpoint 1A remains open. This supersedes the earlier pending-integration
handoff. No new hosted CI, production identity or formal screen-reader claim.
Original uncommitted U02B checkout remains untouched. No next task started.

## P01 verification — 2026-11-01

P01 / 1B / M2 yazh-07, feat/p01-network-csv, clean fetched shared base
22673d909b0860663b001269cefa2ac6f302a881. User approved bounded parser/test/
README/assignment/policy/verification paths and authorized commit/push/merge of
this one row. Real G01 e0257a6/F05 d24312f are integrated prerequisites; original
dirty checkout untouched. No spec/dependency/frontend/full-scope changes.

COMMUNICATION records approved UTF-8/BOM/exact-header/strict-CSV/50 MiB/100000-row
atomic policy. Immutable network.device/network.ip/network.event observations
retain raw logical cells/timestamps and original physical row/column spans.
normalized_value initially equals raw; extraction score 0 means unavailable,
not measured confidence/reliability. No UTC/entity_key/processing API is invented.
P04/P14 own lifecycle/output publication/private provenance. Existing Observation
schema validates parser outputs; no competing wire fields or routes.

### Actual checks

Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0. Existing pins
reused; pip check PASS. No package/model/provider added. CLIs use existing
exact-version cached entry points; no fresh registry install/TLS workaround.

| Check | Actual result |
|---|---|
| Pinned Python warning-strict unittest backend.tests.test_network_csv -v, bundle set | 14 PASS, no skips; real 50 MiB/100000-row bounds, fixture/schema/IDs/locators/raw cells, quote/BOM/encoding/IP/malformed/later-row atomicity, immutability and authorized original integration |
| Pinned Python warning-strict full backend discovery with bundle | 130 run: 129 PASS / 1 Windows symlink SKIP |
| npm frontend test | 48 PASS, no skips |
| npm frontend build | PASS generated API freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=<pinned interpreter> node test/cases.integration.mjs in frontend | PASS actual loopback HTTP I00 intake/audit/hash/original/actor/400/401/404/413 and U04/U03/U02B read-back |
| Redocly 2.57.0 lint/bundle | PASS; existing missing-license warning |
| openapi-typescript 7.10.1 + TypeScript 5.9.3 strict temporary declarations | PASS |
| DESIGN 0.4.0 lint | PASS zero errors/warnings |

P01 original integration uses real FastAPI/F00/F01/F03/F05/SQLite/private storage
with HTTPX ASGI transport; only identities and run UUID context are synthetic.
Downloads reproduce source bytes/SHA-256 before and after parsing; foreign actor
404 and invalid identity 401 block access. No parser/case/storage producer double
or real completed ProcessingRun is claimed. Existing unrelated suites retain
their labeled doubles. I00 loopback smoke regresses completed Checkpoints 0/1A.
No new browser test is needed/claimed for this pure parser row.

The bounded local CSV scanner avoids process-global field-limit changes and
implicit small field caps; excess columns reject early. Errors never echo cells.
Source bytes stay immutable; frozen tuple/dataclasses expose fresh wire copies.
Observation UUIDs are not lifecycle idempotency; P04 will publish real runs.
No timing/performance benchmark data is invented. Exact commands, six fixture
observations, INVALID_IP row-2 failure and cleanup are in backend/README.md,
How you can test P01 (plain reference for planning-fixture compatibility).

P01 remains In Progress pending actual authorized merge/read-back. All initial
scope and approved additions remain unchanged. Checkpoint 1B is open. Next M2
row is P02 GPS parsing with its own bounded source/validation policy; P03 can
normalize after both parsers exist. No P02 implementation here. Clean install,
new hosted CI, other OS/runtime and P04 publication remain untested.

Final P01 documentation candidate: coordination verifier PASS and **122/122
coordination tests PASS**, no skips, using EVORA_CONTRACT_BUNDLE and the shared
unittest discovery command. Diff whitespace passes. All required earlier
checkpoint regressions pass, with only the documented existing F05 Windows
symlink skip. New hosted CI is not claimed.

### P01 integrated acceptance — 2026-11-01

User-authorized task commit 894465ad4105c9910f9ecff9d4c2da18e0619ad5 was pushed
to feat/p01-network-csv and merged without conflicts into the verified shared
branch at **cab08f1c38745255ca1c0a210636476b84bad43c**. On that exact merge,
14 focused parser tests, coordination verifier and real I00 loopback HTTP intake/
audit/original regression smoke PASS. Pre-merge matrix: 129 backend PASS / 1
Windows symlink skip, 48 frontend PASS, 122 coordination PASS, full contract/
type/build/DESIGN PASS with existing missing-license warning. No required P01
acceptance remains; P04 processing/run publication is a separate task.

P01 is Complete after real prerequisite integration and authorized merge;
Checkpoint 1B remains open. This supersedes the earlier pending integration
handoff. New hosted CI is not yet claimed. Full initial scope and approved
additions and the original dirty checkout are unchanged. Next M2 task P02
requires its own GPS source/validation handoff, then P03 needs both parsers.
No P02 work is included or started here.
