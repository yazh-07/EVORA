# EVORA scope/contract verification and implementation readiness

### G01D verification — 2026-11-03

G01D / Checkpoint 1C / M3 / whale2186, locally verified pending review/integration
on `feat/g01d-neo4j-connection-setup`. Execution date 2026-11-04. Clean initial
HEAD/common contract base **7858cce3cc21dbf0efe680094b28c3182b72d336**, matching
local `docs/coordination-foundation`; supplied full hash
`7858ccefc692c89f5bc5cf935f111ba716a5a92a` is absent locally. Direct dependency
G01 **e0257a6ad231105b93ae98a97f176ed233a25412** is a verified merged ancestor.
Seven authorized files only; no spec/frontend or other dependency changes.

Implemented `backend/graph_db.py`: frozen validated backend environment config,
required private password, lazy reusable explicitly closed driver, safe typed
config/connectivity/auth/schema/cleanup failures, explicit configured database,
bounded connect/acquisition/write settings and zero automatic retries/telemetry.
Connectivity consumes a real query; schema consumes each static idempotent DDL
result and never reports partial failure as success. Internal evora-graph/1
has two composite uniqueness constraints and four indexes: Node nodes and Edge
relationships each partition by case/run and index case/source ID. Schema setup
does not write evidence, score anything or publish an analysis.

Actual setup/read-back: installed **neo4j 6.4.1**, **pytz 2026.1** and
**jsonschema 4.25.1** into `/tmp/evora-g01d-validation`; read back distribution
versions and Neo4j's required `pytz` dependency. Ran a disposable private
loopback-only **Neo4j 5.26.0 Community** Docker container, read actual version
through `dbms.components()`, created schema twice, read both constraints and all
four ONLINE indexes. Image digest:
`sha256:5a015e53de1895e7eee1574ae0325cf8c4b89587222778108c594bdd45a474b5`.
Ephemeral generated service credentials stayed in private `/tmp` configuration
and process environment, with no credentials in Git/test output. No existing
service/database was modified. The disposable container and credential file
were removed after verification.

Actual node/relationship writes use parameterized synthetic UUIDs: one source ID
coexists in two cases and two runs, while duplicate Node and Edge identity in
the same case/run is rejected by actual database constraints. Synthetic data is
removed by case/source-scoped cleanup. Wrong password and nonexistent database
fail with safe `Neo4jUnavailableError`. Real refused-port and accepted-but-stalled
Bolt sockets use subprocess hard deadlines; acquisition is set to 0.35 seconds
for these controls and both assert failure under two seconds. Invalid-auth also
asserts under two seconds. No mock is substituted for these socket/auth/schema
acceptances. Other failure/lifecycle/partial-DDL/consume-error tests use explicit
driver/session doubles, with deferred failures consumed before success.

Local runtime: Linux, **Python 3.14.9, Node 22.23.4, npm 12.2.1, FastAPI 0.162.0,
Pydantic 2.14.2, HTTPX 0.28.1**. These preexisting application versions differ
from several setup pins. Exact new graph/validation pins were tested in the
scratch target; this does not certify a clean full `requirements.txt` install,
Windows or new hosted CI. `backend/README.md` documents Linux and PowerShell
configuration, disposable-service setup and focused testing; Windows commands
were not executed here.

Actual required verification sequence (the exported path selects the scratch
driver and exact jsonschema rather than the host jsonschema 4.26.0):

```sh
export PYTHONPATH=/tmp/evora-g01d-validation
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_neo4j_setup.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_aggregation.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_links.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
git diff --check
```

Results: default G01D **13 PASS / 4 opt-in skips**; with private `NEO4J_*`
configuration and `EVORA_NEO4J_INTEGRATION=1`, **17 PASS / zero skips**.
Requested A04 **12**, A02 **13**, A01 **19**, G02 **33**, coordination **122**
and frontend **101** tests PASS. Coordination verifier passes 27 operations /
126 tasks / 18 checkpoints / 39 capabilities / 40 proposal mappings.
No ResourceWarning was observed. Additional completed-checkpoint and existing
A03/A03B regression: **355 tests PASS**, zero skips/failures:

```sh
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit backend.tests.test_relevance_factor backend.tests.test_connectivity_factor
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-g01d-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-g01d-api.d.ts
npx --yes @google/design.md@0.4.0 lint DESIGN.md
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
```

Contract lint/bundle, generated TypeScript 5.9.3 strict compilation, API-type
freshness, frontend typecheck/build, DESIGN and whitespace checks PASS. Existing
OpenAPI missing-license warning remains; DESIGN 0.4.0 has zero errors/warnings.
Actual HTTP/SQLite/UI-controller smoke passes I00/I00B intake/processing/source
inspection with original byte/hash roundtrip and two-actor/case negatives.
Those real merged producers are used; unit UI Fetch/render fixtures remain
labeled doubles, with no mounted-browser/accessibility certification. Later NLP
model-suite limitations previously recorded under I00B were not resolved or
retested by this bounded change.

Limits/handoff: driver/server timeouts are not hard OS deadlines for arbitrary
DNS or a server stalling after acquisition; only the specified local failure
cases have measured two-second assertions. Schema statements auto-commit
individually and must be rerun after partial failure. Uniqueness does not enforce
nonnull fields, valid source UUIDs/observations or endpoints; A01B validates and
persists/rebuilds case/run projections, and A05 controls SQL completion after
verification. No cross-store transaction, completed graph, new endpoint, scoring,
I01 exit or module closure is claimed. G01D stays In Progress pending review/
integration; Checkpoint 1C remains open. No stage/commit/push/merge was authorized
or performed. Next bounded M3 task is A01B after the G01D handoff; none started.

### A01 verification — 2026-11-03

A01 / Checkpoint 1C / M3 / whale2186, `feat/a01-case-graph-nodes`, locally
verified and awaiting review/integration. Clean initial HEAD/common contract base
is **d1f16ef02a62c2ce94bdd19539037a7b60cecabf**, also the local coordination
merge-base. The supplied full hash differs. Direct dependencies P03B
**c58e7f24e4f7c21fc5120dc7288d02f960b58006** and P03C
**bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca** are merged, with real processing
readers/publication, I00B **740f40662158caeed41b2de963cbb185b69fa51d** and G02
available in the reviewed base. Six allowed files changed; no contract, frontend,
dependency, database or other producer changes.

Actual focused read-back: upload the committed synthetic network/GPS originals,
start and read completed processing, then read Evidence/Entity/Event/Observation
APIs and build **10 nodes: 2 Evidence, 5 candidate Entities, 3 source Events**.
Every node keeps its exact source UUID/kind/label and same-case Evidence IDs.
Entity/Event observation references join back to the same-case Evidence and
nonblank source locators. D-7/D-8/D-9 remain separate candidates. Downloaded
original bytes and hashes are unchanged. Foreign actor/case metadata access is
404; spliced foreign records and forged Evidence references fail in the builder.

Unit controls cover empty/evidence-only cases; UUID preservation and malformed/
uppercase/compact/braced/URN/nonstring rejection; missing fields and nonmapping
records; blank labels/kinds; empty/invalid/foreign references; duplicate source
unions; conflicting duplicate category/kind/label; distinct UUIDs with identical
labels; stable kind/UUID ordering under reordering; immutable inputs/results and
detached serialization; strict GraphNode extra-field/schema negatives. No node
observation IDs are required. The unchanged GraphNode schema permits empty labels;
the builder rejects them as the requested stricter internal policy. Graph-envelope
tests use an explicitly synthetic analysis UUID solely to check the schema's
nonempty-graph analysis-ID requirement; no analysis publication is claimed.

Actual verification commands below use the existing scratch **jsonschema 4.25.1**
installation through `PYTHONPATH=/tmp/evora-u13-validation` for Python checks
(module path and distribution version read back). No dependency installation or
manifest change was made. Local runtime: **Python 3.14.9, Node 22.23.4, npm 12.2.1,
FastAPI 0.162.0, Pydantic 2.14.2, HTTPX 0.28.1**. These differ from several pinned
setup versions; this is local behavioral verification, not clean pinned setup,
Windows or hosted-CI proof.

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
PYTHONPATH=/tmp/evora-u13-validation python scripts/verify_coordination.py /tmp/evora-openapi.json
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-a01-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-a01-api.d.ts
npx --yes @google/design.md@0.4.0 lint DESIGN.md
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
git diff --check
```

Results: **19 A01, 33 G02, 122 coordination and 101 frontend tests PASS**.
Verifier passes 27 operations / 126 tasks / 18 checkpoints / 39 capabilities /
40 proposal mappings. Contract lint/bundle, generated TypeScript 5.9.3 strict
compilation, frontend API freshness/typecheck/build and whitespace checks pass.
OpenAPI lint retains the existing missing-license warning; DESIGN 0.4.0 reports
zero errors/warnings. Real HTTP smoke exits 0 and prints the I00 and I00B gate
PASS messages. These results were checked again for final edited documentation.

Completed-checkpoint regression command: **327 PASS**, no skips or failures:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```

Doubles/limits: synthetic CSVs and identities only. Focused successful producers
use real FastAPI/SQLite/private storage/parsers/normalizers/candidate projectors/
publication/read APIs through in-process ASGI; none are replaced. Separate prior
checkpoint suites retain their labeled fault injections/selection fixtures and
frontend Fetch/static-render controls; the independent HTTP smoke uses actual
servers/UI controllers. The full later-adapter backend suite was not rerun:
I00B's recorded NLP/model failures are not resolved or certified by these checks.
No Neo4j projection, graph HTTP endpoint, scoring assembly, frozen analysis
publication, mounted browser, Windows, hosted CI or performance claim.

No unresolved policy gate affects A01. No staging/commit/push/merge or post-merge
smoke was performed. Checkpoint 1C remains In Progress; next bounded M3 task is
A02 under a separate handoff. A01B/A05/I01 still own projection/publication and
the checkpoint exit. Full proposal and approved speech scope remain required.

### G02 verification — 2026-11-03

G02 / Checkpoint 1C / M3 / whale2186, `feat/g02-triage-scoring-policy`.
Base: `740f406` (`docs/coordination-foundation`).
Implementation: Pure factor and triage scoring library in `backend/triage/`:
- `backend/triage/policy.py`: 7 factor scoring functions, base weights summing to 1.0, proportional re-weighting, score capped at 100.0, P1-P4 priority bands, tie-breaking by evidence UUID ascending, source independence engine.
- `backend/triage/goldens.py`: synthetic golden positive and counterexample fixtures matching OpenAPI wire schemas.
- `backend/tests/test_triage_policy.py`: 33 unit tests validating mathematical rigor, OpenAPI schema compliance, negative validation, and tie-breaking.
Verification:
- 33 triage unit tests passing in 0.08s.
- 101 frontend tests passing.
- 122 coordination tests passing.
- Strict OpenAPI bundling and generated TypeScript types clean.

### F08 verification — 2026-11-02

F08 / 1B / M1 / sharmelas-925, `feat/f08-processing-audit`, In Progress pending
review/integration. Clean initial HEAD/common contract base:
**6980b4d0b2fd14a6bf372ae84cb7ab8e78b38d93**. The supplied full hash
`6980b4df3ea582d909ca3a628a55dbb8214309a4` does not resolve locally;
`git rev-parse HEAD` and existing integrated producers establish the actual base.
No fresh remote/hosted CI verification is claimed. Assignment/dependency commits
are recorded in AGENT_TASKS. Only seven allowed files changed; contract, frontend
and package manifests remain unchanged.

Actual read-back: completed processing has exactly one UUID `startProcessing`
event with matching actor/case/Evidence ID, terminal time, run ID and processor
version; private versioned provenance joins on run/case/Evidence/time. Malformed
CSV records `failed`/`CSV_INVALID_IP`, with no partial output/provenance. Startup
recovery audits queued/running runs once with `PROCESSING_INTERRUPTED`. Repeated
keys, duplicate/concurrent workers and repeated startup do not duplicate events.
No historical terminal backfill is fabricated. Failure configuration stays in
private frozen processing_runs; no completed provenance is invented for failure.

Existing HTTP audit listing returns UTC chronological whole/fractional timestamps,
coherent paginated totals, correct actors and safe fields. Two real synthetic
actors/cases, foreign/missing/revoked-case 404 ApiError, UPDATE/DELETE/REPLACE/
UPSERT denial, and absence of source/filename/path/token/parameter values from
public audit/application logs pass. Unknown injected diagnostics are reduced to
`PROCESSING_FAILED` in audit rather than copied as arbitrary strings.

Publication failure after inserting audit, audit insertion failure, deferred
commit failure and recovery audit failure all roll back terminal state/audit and
completion outputs/provenance together. If failure accounting cannot persist,
the run stays nonterminal until successful startup recovery; no false success is
recorded. These are real SQLite trigger/foreign-key failures plus labeled test
injections, not a hardware power-loss or production deployment claim.

Commands executed from repository root (Python below selected via the clean
temporary `/tmp/evora-f08-clean` venv, installed from unchanged requirements):

```sh
python -m pip install -r requirements.txt
python -m pip check
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-f08-api.d.ts
npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-f08-api.d.ts
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_processing_audit -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm --prefix frontend run test
npm --prefix frontend run build
EVORA_TEST_PYTHON=/tmp/evora-f08-clean/bin/python node frontend/test/cases.integration.mjs
npx --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

Results: **13 focused F08 PASS; full backend 420 PASS with no skips;
coordination 122 PASS; frontend 48 PASS.** Real I00 HTTP intake/hash/original/
audit/actor/error smoke PASS. Bundle, lint, verifier (27 operations, 126 tasks,
39 capabilities), generated strict type compilation, frontend API freshness/
typecheck/build and DESIGN (0 errors/0 warnings) PASS. Lint retains the existing
missing-license warning. Whitespace/scope review PASS.

Environment: Linux CPython **3.14.9**, SQLite **3.54.1**, Node **22.23.4**, npm
**12.2.1**; pinned requirements installed into a clean venv, including FastAPI
0.143.1, Starlette 1.8.0, Pydantic 2.14.1, HTTPX 0.28.1 and jsonschema **4.25.1**;
`pip check` PASS. Unversioned requested bundle used Redocly 2.72.1; lint used
workflow-pinned 2.57.0. Earlier exploratory checks used host packages and a
system-site-packages venv; authoritative full regression used the clean venv.
Initial focused-test errors were fixture issues (registry patched during intake
and timestamp string normalization); both fixed before final verification.
This does not certify the documented 3.14.8/22.23.3/12.2.0 runtime, native Windows
or hosted CI. Temporary tests clean their own databases/originals/servers.

Tests use only synthetic evidence/authentication and real merged source/parser/
publication/provenance/list producers. Scheduling holds, registry rejection,
post-publication exceptions and SQLite failure triggers are explicit test-only
controls. No real evidence, production identity provider, model, full processing
UI/I00B, graph/analysis or new checkpoint exit is claimed. No staging/commit/
push/merge. Next: review/integrate F08 and finish I00B prerequisites; F08B waits
for A05 and a separate scoped assignment. Full initial scope remains required.

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

## P02 verification — 2026-11-01

P02 / 1B / M2 yazh-07, feat/p02-gps-csv, clean fetched common base
4bc8f307a039d7c91bcc687bb64267fbe80fb6b8. User approved GPS source/coordinate/
zone policy and bounded backend parser/test/README/policy/ledger scope, and
explicitly authorized implement/test/commit/push/merge of P02 only. Real G01
and F05 prerequisites merged. P01's four-column scanner is reused unchanged;
no P01 producer, frontend, schema, dependency or FEATURE_SCOPE edits. Original
dirty checkout and other worktrees untouched.

Policy is recorded in COMMUNICATION: strict UTF-8 optional BOM/exact GPS header,
50 MiB/100000-row limits and atomic rejection, finite exact Decimal bounds,
valid calendar time/explicit offsets, missing zone remains unknown. Raw numeric
precision/exponents/signed zero and timestamps retained; no UTC/entity_key.
Frozen gps.device/gps.latitude/gps.longitude use existing Observation fields;
score 0 means unavailable, not model measurement or accuracy/source reliability.
No endpoint/run/storage/event/scoring producer is fabricated. P04/P14 own them.

### Actual execution

Existing Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0;
pip check PASS; ignored junction reuses installed frontend dependencies.
No new package/model/provider, clean reinstall or TLS workaround.

| Check | Actual result |
|---|---|
| Pinned warning-strict Python unittest backend.tests.test_gps_csv -v with bundle | 17 PASS, no skips; actual resource bounds, decimal bounds/raw precision, unknown/raw valid zones, malformed time/offset/CSV, immutable/schema/source results and real original integration |
| Full warning-strict backend discovery with bundle | 147 run: 146 PASS / 1 existing Windows symlink SKIP |
| npm frontend test | 48 PASS, no skips |
| npm frontend build | PASS API declaration freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=<pinned interpreter> node test/cases.integration.mjs from frontend | PASS I00 actual loopback HTTP audit/intake/hash/original/actor/error regressions, U04/U03/U02B read-back |
| Redocly 2.57.0 lint/bundle | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 + TypeScript 5.9.3 strict temporary declarations | PASS |
| DESIGN 0.4.0 lint | PASS zero errors/warnings |

The first focused run caught the pinned runtime accepting 24:00:00. Added explicit
00–23/00–59/00–59 clock checks rather than relying on implicit runtime handling;
all 17 focused and subsequent full-backend tests pass. Explicit timezone minute
checks also prevent normalization of offsets such as +01:99 into another value.
Validation never outputs the datetime/Decimal conversions; source text is kept.

Focused integration uses actual FastAPI/F00/F01/F03/F05/SQLite/private files via
HTTPX ASGI, synthetic identities and an explicitly synthetic caller run UUID.
Real upload/download content/hash stay unchanged before/after parsing; foreign
404 and invalid auth 401 deny source reads. No parser/case/storage double or
completed ProcessingRun/public Observation API is claimed. Prior unrelated
suites retain their labeled doubles. I00 separately uses actual loopback HTTP;
all completed Checkpoint 0/1A regressions retained. No new browser check needed
or claimed for this pure backend component.

Strict parsing translates P01 CSV diagnostic codes without source cells; excess
columns/bad quotes reject atomically. Frozen tuples/dataclasses provide fresh
wire copies; no global CSV/decimal context changes or hidden field-size cap.
Repeated parsing is not lifecycle idempotency. Bounds were tested at actual
approved constants, not reduced test doubles. No benchmark result invented.

P02 In Progress pending actual authorized merge/read-back. Exact commands,
three GPS fixture observations, invalid latitude line-2 failure, no-zone policy
and cleanup are in backend/README.md How you can test P02 (plain file reference
for planning-only fixture compatibility). New hosted CI/clean installation/
other OS/runtime and P04 publication remain untested. Entire initial scope and
approved additions unchanged. Next M2 row P03 consumes real P01/P02 for time/
coordinate normalization and raw/uncertainty preservation; no P03 work started.

Final P02 documentation candidate: 122 coordination tests PASS, no skips, with
EVORA_CONTRACT_BUNDLE and the shared discovery command. Final coordination
verifier and whitespace PASS. All required prior 0/1A regressions pass, with
the existing disclosed Windows symlink skip only. No new hosted CI claimed.

### P02 integrated acceptance — 2026-11-01

User-authorized task commit **5684056eb34f2d9e42acb1ade8379bda60ab4b78** was
pushed to feat/p02-gps-csv and merged without conflicts into the shared branch
at **389652c358fab4b3b20565d592db520549028b8f**. On that exact merge, 17 focused
GPS tests, coordination verifier and real I00 loopback intake/audit/original
regression smoke PASS. Pre-merge matrix: 146 backend PASS / 1 Windows symlink
skip, 48 frontend PASS, 122 coordination PASS; contract/types/build/DESIGN PASS
with existing missing-license warning. No required P02 acceptance remains;
P03 normalization and P04 publication are separate task rows.

P02 Complete after actual prerequisite integration and authorized merge;
Checkpoint 1B remains open. This supersedes the pending-integration handoff.
New hosted CI is not yet claimed. Full initial scope/approved additions and
all original dirty work are preserved. Next M2 row P03 consumes both actual
P01/P02 for raw-preserving time/coordinate normalization and zone uncertainty.
No P03 implementation or subsequent task is started during this assignment.


## P03 verification — 2026-11-01

P03 / 1B / M2 yazh-07, feat/p03-normalization, exact verified common base
**ac432e10a6a1c4ff19ae36b49cded514d0e78846**. Actual P01/P02/F03/F05/G01
producers integrated, Checkpoints 0/1A Complete; no prerequisite skipped.
User approved the recorded normalization policy and explicitly authorized
implementation/test/commit/push/merge. Allowed paths and internal envelope are
in AGENT_TASKS.md and COMMUNICATION.md; no spec/producer/dependency/UI changes.
FEATURE_SCOPE.md retains the entire agreed initial scope and approved additions.

### Actual execution on Windows

Pinned Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0; existing
installed dependencies reused via ignored junction. No new package/model/provider.
Exact cached CLI versions used, no registry-resolution/clean-reinstall claim.

| Command/check | Actual result |
|---|---|
| python -W error::ResourceWarning -m unittest backend.tests.test_normalization -v (with EVORA_CONTRACT_BUNDLE) | 18 PASS, no skips |
| python -W error::ResourceWarning -m unittest discover -s backend/tests -v (same bundle) | 165 run: 164 PASS / 1 existing Windows symlink-permission SKIP |
| python -m pip check | PASS, no broken requirements |
| npm --prefix frontend test | 48 PASS, no skips |
| npm --prefix frontend run build | PASS API declaration freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=pinned interpreter; node test/cases.integration.mjs from frontend | PASS actual I00 loopback HTTP intake/audit/hash/original, actor/input/error paths, U02/U02B/U03/U04 regressions |
| Redocly 2.57.0 lint specs/openapi.yaml and bundle to TEMP/evora-p03-openapi.json | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 specs/openapi.yaml to TEMP/evora-p03-api.d.ts; TypeScript 5.9.3 --noEmit --strict on that file | PASS |
| python scripts/verify_coordination.py TEMP/evora-p03-openapi.json | PASS all planning artifact checks |
| EVORA_CONTRACT_BUNDLE=same bundle; python -m unittest discover -s scripts -p test_*.py -v | 122 PASS, no skips |
| DESIGN 0.4.0 lint DESIGN.md | PASS zero errors/warnings |
| git diff --check | PASS |

Goldens exercise explicit UTC offsets, date/year/leap-day rollover, fractional
seconds beyond microseconds, known versus unknown zero offset, missing/named/
ambiguous/invalid zones, invalid calendar/24:00/leap-second clocks and UTC range
overflow. Raw values always survive; unresolved time omits optional UTC on wire.
Coordinates exercise exact bounds/precision under low Decimal context precision,
signed zero, canonical insignificant zeros, scientific/plain boundary and extreme
exponents without huge expansion. Invalid inputs reject atomically with safe fixed
codes; source UUID contexts, locators, kind and score stay unchanged. Frozen
results/fresh schema-valid wire copies and pure-value idempotence are checked;
this does not claim processing-run replay, case authorization or public status.

Integration uses actual FastAPI/F00/F01/F03/F05/SQLite/private files, real P01/P02
parsers, synthetic tokens and explicitly unpersisted caller run UUIDs. HTTPX ASGI
is an in-process transport. Upload/read-back original bytes and hashes, immutable
SQL evidence snapshots, post-normalization download, foreign 404 and invalid
auth 401 all pass. No parser/storage/case double. Separate I00 test uses actual
loopback HTTP and real frontend client/stores. Earlier unrelated suites retain
their labeled doubles. No P04 processing lifecycle/publication, P14 provenance
store, identity keys, events, graph/scoring, new browser check or clean install
is claimed. Existing Windows symlink skip remains disclosed; hosted CI pending.

How you can test P03, exact setup/commands, synthetic inputs and expected results
plus invalid-coordinate and unresolved-time cases are in backend/README.md
(plain reference for planning-only fixture compatibility). No historical output
or original storage mutation. P03 In Progress pending actual merge/read-back;
Checkpoint 1B remains open. Next M2 row P03B candidate keys/entities, retaining
D-7 and D-8 as distinct candidates; no subsequent task starts here.


### P03 integrated acceptance — 2026-11-01

User-authorized task commit **d186af38f84479794889d309765f60be189cf790** pushed
to feat/p03-normalization, then merged without conflicts into the recorded
shared branch docs/coordination-foundation at
**e9f01f586916f38c480a40ffc8aa3eb72fd146ff**. On that exact merge, 18 focused
normalization tests, coordination verifier and actual I00 loopback HTTP intake/
audit/original/actor/failure smoke PASS. The combined candidate had already
passed full prior checkpoint regressions: 164 backend PASS/1 existing Windows
symlink SKIP, 48 frontend PASS, 122 coordination PASS; contract/types/build/
DESIGN PASS with existing missing-license warning. Scope guard confirms no
FEATURE_SCOPE/spec/frontend/producer/dependency changes. Original dirty checkout
and other worktrees preserved. No required P03 acceptance remains unintegrated.

P03 Complete; Checkpoint 1B remains open. This supersedes earlier pending-merge
statements. New hosted CI is not yet claimed at this recording point. No P04
lifecycle/publication, P14 provenance persistence, clean install or real-evidence
benchmark claim. Synthetic auth/run context and ASGI versus loopback transport
limits remain as disclosed above. Next eligible M2 task P03B candidate identifier
keys/entity records; D-7/D-8 stay distinct, source IDs retained and no inferred
person identity. No next task started; waiting for user review.


## P03B verification — 2026-11-01

P03B / 1B / M2 yazh-07; feat/p03b-candidate-entities from exact freshly fetched
shared base **59de4686f4a59bff25528d386ce458d259d96e6c**. Real P01/P02/P03
producers integrated; Checkpoints 0/1A Complete. No active P03B claim existed.
User approved the recorded bounded scope/key policy and explicitly authorized
implementation/test/commit/push/merge. Only new candidate module/tests, backend
README and bounded four coordination records changed. FEATURE_SCOPE.md and all
approved additions are preserved; no producer/spec/API/DB/dependency/UI edits.

### Actual execution

Pinned Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0. Existing
installed dependencies reused through ignored junction; exact cached CLI tools.
No new package/model/provider or clean installation claimed.

| Command/check | Actual result |
|---|---|
| EVORA_CONTRACT_BUNDLE=TEMP/evora-p03b-openapi.json; python -W error::ResourceWarning -m unittest backend.tests.test_candidate_entities -v | 15 PASS, no skips |
| npm --prefix frontend test | 48 PASS, no skips |
| npm --prefix frontend run build | PASS API freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=pinned interpreter; node test/cases.integration.mjs from frontend | PASS actual I00 loopback HTTP intake/audit/hash/original/actor/input/error and U02/U02B/U03/U04 regressions |
| Redocly 2.57.0 lint specs/openapi.yaml and bundle to TEMP/evora-p03b-openapi.json | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 specs/openapi.yaml to TEMP/evora-p03b-api.d.ts; TypeScript 5.9.3 --noEmit --strict on that file | PASS |
| python scripts/verify_coordination.py TEMP/evora-p03b-openapi.json | PASS |
| EVORA_CONTRACT_BUNDLE=same bundle; python -m unittest discover -s scripts -p test_*.py -v | 122 PASS, no skips |
| DESIGN 0.4.0 lint DESIGN.md | PASS zero errors/warnings |
| git diff --check and protected-path diff guard | PASS |

Focused behavior proves exact D-7/D-8/D-9 separation; identical-key grouping
within a case and across supplied evidence, unique sorted source UUIDs and
namespace/case/whitespace/Unicode/IP spelling controls. Nonidentifier GPS/event
cells infer no entity; source fields, time uncertainty and extraction score stay
unchanged. Entity confidence remains unavailable 0 with no repeated-mention boost.
Frozen records and fresh wire copies validate against actual Observation/Entity
schemas; reordered inputs keep content/order with fresh unpublished record IDs.
Pure projection is not lifecycle replay or verified identity. Reject mixed cases,
duplicate observation IDs, evidence/run conflicts, invalid context/kind/source/
IP, blank/changed identifier and preassigned key conflicts atomically with safe
fixed diagnostics. Documented synthetic network example prints four exact keys,
confidence 0/one source each. Duplicate example exits nonzero with
DUPLICATE_OBSERVATION, as documented in backend/README.md.

Actual integration uses F00/F01/F03/F05, FastAPI, SQLite/private files, real P01/
P02 parsing and P03 normalization. Synthetic auth tokens and unpersisted caller
run UUIDs are explicit test context; HTTPX ASGI transport is in process. No parser,
case/storage or normalization double. Original bytes/hashes, SQL evidence rows,
immutable input observations and same-case source references are checked before/
after projection; foreign download 404 and invalid auth 401 pass. I00 separately
uses real loopback HTTP/client/stores; earlier suites retain their labeled doubles.
P04 processing publication, P05 Entity listing, P14 private persistence and P03C
events remain separate required tasks. No real-evidence benchmark, new browser
check or production auth claim. How you can test P03B exact commands, synthetic
inputs/results and failure case are in backend/README.md (plain file reference
for planning-only fixture compatibility).

P03B In Progress pending complete regression and actual merge/read-back; no
unintegrated Complete claim. Hosted CI pending. Next M2 P03C source-backed event
projection; no next task started. Entire initial scope/approved additions retained.


P03B final combined-candidate regression: warning-strict backend discovery with
EVORA_CONTRACT_BUNDLE passed **180 run: 179 PASS / 1 existing Windows symlink-
permission SKIP**; python -m pip check PASS, no broken requirements. All completed
0/1A regressions pass, with that disclosed skip; no unsupported symlink result
claimed. Other-OS/clean-install results await hosted CI. Integration still pending.


### P03B integrated acceptance — 2026-11-01

User-authorized task commit **afed7256991aa7cd7c3037aa5d4e318f82019fbe** pushed
to feat/p03b-candidate-entities, then merged without conflicts into the recorded
shared branch docs/coordination-foundation at
**c58e7f24e4f7c21fc5120dc7288d02f960b58006**. On that exact merge, 15 focused
candidate tests, coordination verifier and actual I00 loopback HTTP intake/audit/
original/actor/failure smoke PASS. Final pre-merge docs candidate: 122 coordination
PASS; full prior 0/1A backend/frontend regressions and contract/types/build/DESIGN
pass as recorded above. Scope guard confirms full FEATURE_SCOPE/spec/frontend/
existing parsers/dependencies unchanged. Original dirty checkout and other work
preserved. No required P03B acceptance remains unintegrated.

P03B Complete; Checkpoint 1B/M2 remain open. This supersedes the earlier pending-
merge handoffs. Hosted CI not yet claimed at this recording point. Synthetic auth/
unpersisted run UUIDs and focused ASGI transport remain disclosed; real processing
publication/list APIs/provenance persistence stay with P04/P05/P14. No full-system
completion or real-evidence benchmark claimed. Next eligible M2 P03C source-backed
event projection, with actual P01/P02/P03 prerequisites integrated. No next task
started; waiting for user review. Full agreed initial scope/additions preserved.


## P03C verification — 2026-11-01

P03C / 1B / M2 yazh-07, feat/p03c-source-events from verified shared base
**e68969df9f19f8f78320a708bc3cb80a3c05b85d**, matched freshly fetched origin.
Actual P01/P02/P03 prerequisites merged, plus actual P03B participant records;
completed Checkpoints 0/1A regressed. User approved the exact bounded file scope
and source-event policy, then explicitly authorized implementation/test/push/merge.
New source-event module/test, backend README and bounded four records only.
Full FEATURE_SCOPE/additions, existing producers/spec/DB/dependencies/UI unchanged.

### Actual execution

Existing Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0;
exact cached CLI versions and ignored frontend dependency junction reused.
No new package/model/provider, clean local reinstall or TLS bypass.

| Command/check | Actual result |
|---|---|
| EVORA_CONTRACT_BUNDLE=bundle; python -W error::ResourceWarning -m unittest backend.tests.test_source_events -v | 15 PASS, no skips |
| EVORA_CONTRACT_BUNDLE=TEMP/evora-p03c-openapi.json; python -W error::ResourceWarning -m unittest discover -s backend/tests -v | 195 run: 194 PASS / 1 existing Windows symlink-permission SKIP |
| python -m pip check | PASS, no broken requirements |
| npm --prefix frontend test | 48 PASS, no skips |
| npm --prefix frontend run build | PASS API freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=pinned interpreter; node test/cases.integration.mjs from frontend | PASS actual I00 loopback HTTP intake/audit/hash/original/actor/error and U02/U02B/U03/U04 regressions |
| Redocly 2.57.0 lint specs/openapi.yaml and bundle to TEMP/evora-p03c-openapi.json | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 specs/openapi.yaml to TEMP/evora-p03c-api.d.ts; TypeScript 5.9.3 --noEmit --strict on that file | PASS |
| python scripts/verify_coordination.py TEMP/evora-p03c-openapi.json | PASS |
| EVORA_CONTRACT_BUNDLE=same bundle; python -m unittest discover -s scripts -p test_*.py -v | 122 PASS, no skips |
| DESIGN 0.4.0 lint DESIGN.md | PASS zero errors/warnings |
| git diff --check; protected-path diff guard | PASS |

Focused cases exercise three real fixture row reports, all source/actual Entity
references, distinct D-7/D-8 participants, exact source-report summaries, multiline
locators/untrusted text and identical-content distinct rows. Preserve nanosecond
fractions/offset UTC and raw/uncertain missing/named/-00:00/invalid time without
fabrication. Entity/event confidence stays unavailable 0. Reordered inputs keep
source content/order with fresh unpublished Event record IDs, not lifecycle replay.
Frozen Event/envelope and fresh wire arrays validate actual Event schema, with no
extra internal fields. Incomplete/duplicate row fields, malformed/wrong-column/
header/overlapping/huge locators, inconsistent raw/UTC/uncertainty/coordinates,
mixed cases/adapters/run contexts, duplicate observations, missing/foreign/altered/
duplicate Entity records or unsupported projection versions reject atomically with
fixed safe codes. Existing producer/key validation is reused, not copied/changed.
Temporary validation Entity IDs are discarded; only actual supplied IDs are linked.

Real integration uses F00/F01/F03/F05/FastAPI/SQLite/private originals and actual
P01/P02/P03/P03B producers. Synthetic tokens and explicitly unpersisted caller run
UUIDs supply context; focused HTTPX ASGI transport is in process. No parser/storage/
normalizer/Entity producer double. Tests read back original bytes/hash, unchanged
SQL evidence rows and frozen source observations before/after projection; Event
references join to same-case source/actual Entity IDs, foreign 404 and invalid
auth 401 pass. Separate I00 uses real loopback HTTP and frontend client/stores.
Earlier unrelated suites retain their labeled doubles. No P04 run publication,
P05B list API, P14 private persistence, real-evidence benchmark or new browser
check claimed. All prior completed checkpoint checks pass with disclosed skip.
Hosted CI/other-OS fresh install not yet claimed at this recording point.

backend/README.md How you can test P03C provides exact setup/commands, synthetic
network fixture -> two network.activity reports with 3 observation/2 participant
IDs and UTC times; example executed as written. Both listed failure/time-control
commands PASS: INCOMPLETE_ROW/DUPLICATE_ROW_FIELD and invalid time raw/no UTC.
Plain backend README reference preserves planning-only fixture compatibility.
P03C In Progress pending actual authorized merge/read-back; Checkpoint 1B remains
open. Next M2 row P04 processing lifecycle requires its own bounded policy review;
no next task started. Entire agreed initial scope including additions preserved.


### P03C integrated acceptance — 2026-11-01

User-authorized task commit **f75ffa32a154987db82bdcdd8b28047ee05bf054** pushed
to feat/p03c-source-events and merged without conflicts into the recorded shared
branch docs/coordination-foundation at
**bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca**. On that exact merge, 15 focused
source-event tests, coordination verifier and real I00 loopback HTTP intake/audit/
original/actor/failure smoke PASS. Final pre-merge docs candidate: 122 coordination
PASS; full prior completed 0/1A backend/frontend regressions and contract/types/
build/DESIGN pass as recorded above. Protected-path guard confirms full FEATURE_SCOPE/
spec/frontend/existing producers/dependencies unchanged. Original dirty checkout
and other work preserved. No required P03C acceptance remains unintegrated.

P03C Complete; Checkpoint 1B and M2 remain open. This supersedes pending-merge
handoffs. New hosted CI not yet claimed at this recording point. Synthetic auth/
unpersisted run UUIDs, ASGI focused transport versus separate real HTTP smoke,
Windows symlink skip and remaining P04/P05B/P14 publication/listing/persistence
boundaries stay disclosed. No verified occurrence/identity or full-system claim.
Next M2 P04 processing lifecycle, subject to its own bounded scope and needed
C-04 lifecycle/error policy review. Its real F00/F05/P01/P02 dependencies are
integrated. No next task started; waiting for user review. Entire initial scope
including all approved additions remains preserved.


## P04 verification — 2026-11-01

P04 / 1B / M2 yazh-07, feat/p04-processing-lifecycle from exact verified shared
base **9bec1653525694c01ef82c6a3cd12f2beea8493c**, matched freshly fetched origin.
Actual F00/F05/P01/P02 prerequisites integrated, plus P03/P03B/P03C real outputs;
completed 0/1A regressions retained. User approved the bounded paths/lifecycle
policy and explicitly authorized implement/test/commit/push/merge. New processing
module/focused tests, app router/startup, necessary skeleton processing-table
inventory, backend README and bounded four records only. M1 tables/producers,
existing parser modules, FEATURE_SCOPE/additions, spec/frontend/dependencies
unchanged. No task after P04 is included or marked Complete.

### Actual execution

Existing Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0;
exact cached CLI versions and ignored frontend dependency junction reused.
No new dependency/model/provider or clean local reinstall claimed.

| Command/check | Actual result |
|---|---|
| EVORA_CONTRACT_BUNDLE=TEMP/evora-p04-openapi.json; python -W error::ResourceWarning -m unittest backend.tests.test_processing -v | 21 PASS, no skips; actual ASGI and separate localhost HTTP processing |
| Same bundle; python -W error::ResourceWarning -m unittest discover -s backend/tests -v | 216 run: 215 PASS / 1 existing Windows symlink-permission SKIP |
| python -m pip check | PASS, no broken requirements |
| npm --prefix frontend test | 48 PASS, no skips |
| npm --prefix frontend run build | PASS API freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=pinned interpreter; node test/cases.integration.mjs from frontend | PASS actual I00 loopback intake/audit/hash/original/actor/error and U02/U02B/U03/U04 regressions, including rerun on final serialized-worker candidate |
| Redocly 2.57.0 lint specs/openapi.yaml and bundle to TEMP/evora-p04-openapi.json | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 specs/openapi.yaml to TEMP/evora-p04-api.d.ts; TypeScript 5.9.3 --noEmit --strict on that file | PASS |
| python scripts/verify_coordination.py TEMP/evora-p04-openapi.json | PASS |
| Same bundle; python -m unittest discover -s scripts -p test_*.py -v | 122 PASS, no skips |
| DESIGN 0.4.0 lint DESIGN.md | PASS zero errors/warnings |
| git diff --check; protected-path diff guard | PASS |

Actual producers publish network fixture six observations/four entities/two
events and GPS three observations/one entity/one event. Every output validates
actual wire schema and joins same-case Evidence/real P04 run/source Observation/
actual Entity IDs; raw/time/locators/confidence and original bytes/hash remain.
Header-only CSV completes with real empty output. start returns 202 queued,
GET polls real state, history lists oldest first. Tests execute queued/running/
completed/failed, frozen private configuration/limits, no private wire fields,
same-key replay before changed metadata/config, different-target 409, new-key
retry and immutable completed history. Scope keys by actor/case/operation; six
concurrent same-key requests schedule one job/run. Local jobs serialize while
API reads remain responsive; GET/replay never schedules work.

Negatives cover unsupported 415 without run/key, supported malformed CSV safe
failed/CSV_INVALID_IP, missing/duplicate/empty/overlong keys, nonempty body/query
and invalid UUID 400, all new-route auth 401/foreign/missing 404, mismatched run/
evidence/case joins and membership revocation before/during parsing/publication.
Changed frozen execution version cannot complete. Synthetic original tamper,
missing/unsafe private file, invalid participant/source paths and post-publication
exception leave no completed partial output; new-key retry works and prior
terminal resource remains stable. SQL triggers reject frozen configuration/
terminal run/output mutation/deletion and completion without output.

Test doubles are explicitly bounded: held scheduling callbacks expose queued
state; a parser gate invokes the actual parser then allows running-state polling;
a worker gate proves serialization/responsiveness. A post-insert/pointer-update
exception proves actual SQLite transaction rollback; version and membership
changes are controlled fault injections. Persisted queued/running interruption
fixtures exercise actual startup recovery on a second real app/database, preserving
completed history and replaying failed originals. This is not an OS power-loss,
multi-process/distributed queue or full P14C crash matrix. The local deployment
policy is one app process. If SQLite itself is inaccessible, nonterminal state
may remain until startup recovery; no fictional completed status is produced.

Focused API tests use actual FastAPI/F00/F01/F03/F05/SQLite/private originals and
real P01/P02/P03/P03B/P03C. Auth identities/tokens are synthetic; run UUIDs are
actually produced and persisted by P04, not unpersisted parser context doubles.
Separate ProcessingLoopbackTests launches actual Uvicorn and tests real localhost
HTTP start/poll/list for network/GPS completion and malformed CSV failure; server
and temp storage clean up automatically. I00 separately exercises earlier real
client/stores/intake/audit. Prior unrelated suites retain documented doubles.

backend/README.md How you can test P04 gives exact setup/test commands, synthetic
fixtures/expected counts, real HTTP smoke and malformed-IP failure/replay command.
P04B/P05/P05B public output listing, F08 public processing audit, P14 richer private
provenance, P14B dispatch registration and P14C full recovery/atomic-publication
gates remain separate required rows; P04 basic actual pipeline/atomicity does not
complete them. No full UI processing workflow, production auth, new model, local
clean reinstall or real-evidence benchmark claimed. Hosted CI pending at this
recording point. Full agreed initial scope including additions preserved.
P04 In Progress pending actual authorized merge/read-back; Checkpoint 1B remains
open. Next M2 P04B source-backed latest/historical Observation listing; no next
task started. Existing original dirty checkout and other worktrees preserved.


### P04 integrated acceptance — 2026-11-01

User-authorized task commit **32d78e588d1fc02078834cd62b57a176608ea16a** pushed
to feat/p04-processing-lifecycle and merged without conflicts into the recorded
shared branch docs/coordination-foundation at
**f851dd11fd8f7e11140317cf44d022a9999044dd**. On that exact merge, all 21 P04
focused tests (including actual Uvicorn/localhost network/GPS/malformed start/
poll/list), coordination verifier and actual I00 loopback intake/audit/original/
actor/error regressions PASS. Final pre-merge docs candidate: 122 coordination
PASS; full 215 backend PASS/1 Windows symlink SKIP, frontend 48 PASS; contract/
types/build/DESIGN PASS as recorded above. Scope guard confirms full FEATURE_SCOPE/
spec/frontend/M1 tables and producer modules/existing parsers/dependencies unchanged;
only approved app wiring, new processing-owned schema and required inventory test
changed. Original dirty checkout and other worktrees preserved.

P04 Complete after actual prerequisite integration and authorized merge/smoke;
no required P04 acceptance remains unintegrated. Checkpoint 1B/M2 remain open.
This supersedes pending-integration handoffs. New hosted CI not yet claimed at
this recording point. Single-process worker, synthetic auth, bounded scheduling/
fault/restart fixtures, ASGI versus real loopback transport and Windows symlink
skip remain disclosed above. No OS power-loss/distributed-worker/production-auth
or full processing UI claim. P04B/P05/P05B listing, F08 audit, P14/P14B/P14C richer
provenance/dispatch/full recovery gates remain required separate tasks.
Next eligible M2 P04B exposes case-scoped latest completed and processing_run_id-
pinned historical observations with pagination/source values and no partial/
foreign outputs. Its actual P04 prerequisite is integrated. No next task started;
waiting for user review. Entire agreed initial scope/additions preserved.


## P04B verification — 2026-11-01

P04B / 1B / M2 yazh-07, feat/p04b-observation-list from exact verified shared
base **bb3928440ebf39d016e14fb328f045d98fd68bb9**, matched freshly fetched origin.
Actual P04 prerequisite integrated, with underlying real F00/F03/F05/P01/P02/
P03/P03B/P03C; 0/1A Complete. User approved bounded paths/read policy and explicitly
authorized implementation/test/commit/push/merge. New observations module/tests,
app router wiring, backend README and bounded four records only. Full agreed
FEATURE_SCOPE/additions, DB/schema, producers/spec/dependencies/frontend unchanged.

### Actual execution

Existing Windows Python 3.14.8/jsonschema 4.25.1, Node 22.23.3/npm 12.2.0;
exact cached CLI tools and ignored frontend dependency junction reused. No new
package/model/provider or clean local reinstall claimed.

| Command/check | Actual result |
|---|---|
| EVORA_CONTRACT_BUNDLE=TEMP/evora-p04b-openapi.json; python -W error::ResourceWarning -m unittest backend.tests.test_observations -v | 16 PASS, no skips; final focused run includes selected-empty-latest versus older pin regression |
| Same bundle; python -W error::ResourceWarning -m unittest discover -s backend/tests -v | 232 run: 231 PASS / 1 existing Windows symlink-permission SKIP |
| python -m pip check | PASS, no broken requirements |
| npm --prefix frontend test | 48 PASS, no skips |
| npm --prefix frontend run build | PASS API freshness, TypeScript and esbuild |
| EVORA_TEST_PYTHON=pinned interpreter; node test/cases.integration.mjs from frontend | PASS actual I00 loopback intake/audit/hash/original/actor/error and U02/U02B/U03/U04 regressions |
| Redocly 2.57.0 lint specs/openapi.yaml and bundle to TEMP/evora-p04b-openapi.json | PASS, existing missing-license warning |
| openapi-typescript 7.10.1 specs/openapi.yaml to TEMP/evora-p04b-api.d.ts; TypeScript 5.9.3 --noEmit --strict on that file | PASS |
| python scripts/verify_coordination.py TEMP/evora-p04b-openapi.json | PASS |
| Same bundle; python -m unittest discover -s scripts -p test_*.py -v | 122 PASS, no skips |
| DESIGN 0.4.0 lint DESIGN.md | PASS zero errors/warnings |
| git diff --check; protected-path diff guard | PASS |

Real P04 network/GPS processing publishes six/three observations; default returns
nine exact stored wire values, same-case/evidence/run IDs, row locators, raw/
normalized values/keys and nanosecond UTC fractions unchanged. evidence_id and
processing_run_id filters, latest per evidence and historical replay work with
actual producer IDs. Tests cover 27-observation all-page totals/no duplicate or
skipped IDs, limit 1–100/default 20, offset boundaries/huge beyond-end integers,
selected empty outputs and valid unprocessed/empty cases. A selected empty latest
run never falls back to older nonempty output; the older explicit pin stays valid.

Negative controls cover bad/duplicate/unknown query parameters and invalid UUID/
limit/offset safe 400, missing/invalid/duplicate auth 401, foreign/missing/mismatched
resources and revoked membership identical 404. Pending/running/failed selectors
404 and expose no partial output; newer failed retry leaves completed selection
intact. Unknown private fields, bad record types/context/UUID/score/time, duplicate
Observation IDs, malformed/missing JSON or foreign output metadata fail the whole
read with safe 404, not private content or a silent older-run fallback. Reads do
not mutate runs/outputs/evidence/audit/private originals or schedule processing.

Exact UTC completion ranking preserves sub-microsecond fractions; offset-equivalent
instants tie by UUID and zero fractional spelling does not sort after later
fractions. Page order is canonical evidence UUID then Observation UUID. One real
read transaction keeps selection/total/items coherent during a real writer-thread
publication attempt; subsequent default read selects its newer completed output.
Across separate requests clients pin a historical run for stable pagination;
no case-wide snapshot field or misleading default cross-request freeze claimed.

The first focused run exposed strict datetime validation rejecting valid stored
ISO timestamp strings. Corrected that validation while retaining explicit wire
string/date-time checks; serialization returns the original JSON, preserving all
fractional digits rather than the parsed datetime. All final focused/full checks
above pass. ObservationPage examples validate actual bundled OpenAPI schema.

Doubles/fault fixtures: synthetic auth tokens only; actual P04 runs/outputs for
core ASGI and localhost tests. Scheduler gates expose queued/running records;
a publication fault exercises a real failed retry. Selection-only SQL fixtures
supply controlled 2099/equal/fractional completion instants, UUID ties and empty
latest output. Temp-only corruption fixtures bypass immutable triggers to test
fail-closed reads. A schema-derived transcript segment proves existing optional
wire/conditional compatibility, not an implemented ASR/correction producer.
Core tests use real FastAPI/SQLite/private files and actual extraction/normalization/
Entity/Event producers. HTTPX ASGI is in process; ObservationLoopbackTests launches
actual Uvicorn/HTTP and proves upload/process/default/filter/pin/pagination and
failed-selector behavior without producer doubles. Prior unrelated suites retain
documented doubles. No OS power-loss/distributed worker/production auth, full
Observation UI, maximum-size performance benchmark or real-evidence claim.

backend/README.md How you can test P04B supplies exact setup/commands, synthetic
network/GPS counts, independent real HTTP smoke and pending/failed/corrupt history
failure controls. No DB/schema or producer change. Hosted CI/other-OS fresh install
not yet claimed at this recording point. P04B In Progress pending actual merge/
read-back; Checkpoint 1B/M2 remain open. Next M2 P05 candidate Entity listing (actual
P03B and P04B dependencies after integration); no next task started. Entire scope/
additions and existing original dirty checkout/other worktrees preserved.


### P04B integrated acceptance — 2026-11-01

User-authorized task commit **5baa2f631f788466f6787d331734adda0f26dfca** pushed
to feat/p04b-observation-list and merged without conflicts into the recorded
shared branch docs/coordination-foundation at
**c29e517f218c0851a9959cfa389b093242a255ab**. On that exact merge, all 16 P04B
focused tests including real Uvicorn/localhost process-to-Observation reads,
coordination verifier and actual I00 loopback intake/audit/original/actor/error
regressions PASS. The final focused suite includes empty latest versus older
nonempty pin and invalid stored UUID regressions. Final pre-merge docs candidate:
122 coordination PASS; full 231 backend PASS/1 Windows symlink SKIP, frontend
48 PASS; contract/types/build/DESIGN PASS as recorded above. Protected-path guard
confirms full FEATURE_SCOPE/spec/frontend/DB schema/producers/dependencies remain
unchanged. Only approved app router wiring is shared runtime work. Original dirty
checkout and other worktrees preserved.

P04B Complete after actual P04 prerequisite integration and authorized merge/smoke;
no required P04B acceptance remains unintegrated. Checkpoint 1B/M2 remain open.
This supersedes pending-integration handoffs. New hosted CI not yet claimed at
this recording point. Synthetic auth/scheduler/publication/corruption/selection
fixtures and transcript schema-only compatibility, ASGI versus real HTTP smoke,
Windows skip, no maximum-size benchmark/production-auth/full Observation UI claim
remain disclosed above. Whole-read validation protects shape/context/public wire,
not a claim that arbitrary database tampering establishes source authenticity.

Next eligible M2 P05 candidate Entity listing: real P03B/P04B prerequisites are
integrated. P05B Event listing follows by the catalog/dependency order; later
provenance/dispatch/recovery/UI/full-scope gates remain required. No next task
started; waiting for user review. Entire agreed scope/additions preserved.


### P05 verification — 2026-11-02

Continuation of the approved 2026-11-01 P05 / Checkpoint 1B / M2 yazh-07
assignment. Isolated feat/p05-entity-list from verified common base
abeb516ba879636afb18aaa2a800b2143915e0f7. Fetch on continuation confirms remote
shared docs/coordination-foundation remains at that base. Real P03B/P04B and P04
source chain are integrated prerequisites, not schema-only substitutes.

Actual commands/results on final source:
- Python 3.14.8 / jsonschema 4.25.1, pip check: no broken requirements.
- EVORA_CONTRACT_BUNDLE set to Redocly 2.57.0 bundled specs/openapi.yaml;
  python -W error::ResourceWarning -m unittest backend.tests.test_entities -v:
  17 PASS, no skips, including real localhost Uvicorn upload/process/read-back.
- python -W error::ResourceWarning -m unittest discover -s backend/tests -v:
  249 run, 248 PASS and one pre-existing Windows symlink-permission SKIP.
  Host suspension inflated elapsed wall time; no performance benchmark claimed.
- python scripts/verify_coordination.py <bundled-json-path>: PASS;
  python -m unittest discover -s scripts -p 'test_*.py' -v: 122 PASS, no skips.
- Node 22.23.3/npm 12.2.0: frontend npm test 48 PASS; npm run build PASS
  (API freshness/TypeScript/esbuild); real I00 cases.integration.mjs loopback PASS
  with EVORA_TEST_PYTHON pinned to the tested interpreter.
- Redocly lint/bundle PASS (existing missing-license warning); openapi-typescript
  7.10.1 and strict TypeScript 5.9.3 declaration compilation PASS;
  DESIGN 0.4.0 lint PASS, zero errors/warnings. git diff --check PASS.

Actual network/GPS originals traverse F03/F05/P01/P02/P03/P03B/P03C/P04/P04B
into immutable SQL Entity records: exact IDs/keys/labels/scores/source arrays,
same-case Evidence/Observation joins, actual Event participant UUIDs. Real HTTP
smoke totals 4 then 5 then 9 after duplicate network input; malformed supported
CSV fails and total stays 9. limit=2/offset=2 returns two items/total9. Identical
keys stay separate with score0, not inferred identity/corroboration. All-page
28-record controls verify totals/order/no duplicate or skipped IDs; empty latest
never falls back. Pending/running/failed partial outputs invisible; failed retry
retains prior completed output. Reprocessing changes selected IDs, preserves history.

Negatives cover unknown/duplicate query keys and invalid limits/UUIDs safe400,
missing/invalid/duplicate auth401, revoked/foreign/missing case404; missing/corrupt
output, malformed Entity/Observation fields/UUIDs/scores, duplicate IDs/references,
stale/foreign/missing citations, Evidence mismatch and inconsistent entity_key
fail the whole read safe404. Exact fractional UTC selection and UUID ties match
P04B. A real writer-thread publication attempt during the held read transaction
keeps response selection/total/items coherent; next read sees fresh outputs.
Repeated reads preserve runs/outputs/audit/originals and schedule no work. Query
plan probe confirms automatic covering indexes on observation_id and entity_id;
no persistent schema/index change or throughput claim.

Doubles/limits: synthetic auth actors/tokens and synthetic CSV only. Core tests
use real FastAPI/SQLite/private files and actual producers; HTTPX ASGI is in
process, and the separate Uvicorn subprocess exercises real HTTP. Scheduler and
publication gates expose pending/failure states; selection-only SQL fixtures use
controlled 2099 timestamps/UUID ties; temp-only corruption bypasses immutable
triggers to test fail-closed reads. Generic account/text wire compatibility is
schema-only, not an implemented producer. Existing unrelated test doubles remain
disclosed in earlier records. No production auth, full Entity UI, OS power-loss,
distributed worker, maximum-size benchmark or real-evidence claim. Shape/context/
join validation does not establish source authenticity after arbitrary DB tampering.

backend/README.md contains exact commands, synthetic inputs/counts, real HTTP
smoke and stale/foreign-citation failure control. Full agreed FEATURE_SCOPE and
approved additions preserved; no schema/spec/producer/dependency/frontend edits.
Original dirty checkout and other worktrees preserved. P05 In Progress pending
actual integration/smoke; Checkpoint 1B/M2 remain open. Next eligible M2 P05B
source-backed Event listing, with P03C/P04B integrated. No next task started.


### P05 integrated acceptance — 2026-11-02

User-authorized task commit **f67d840d84686ad3d07b4b479971621e7dc8cc40** pushed to
feat/p05-entity-list; clean shared docs/coordination-foundation merged without
conflicts at **04af24f1c44abbc8059b0c006d9079d271ced947**. On that exact merge:
17 focused tests PASS (including real Uvicorn processing/Observation/Entity HTTP),
coordination verifier PASS, real I00 intake/audit/hash/original/actor/error smoke
PASS. No runtime changes after the full regression matrix recorded above.
Protected scope/spec/frontend/schema/producers/dependencies unchanged; original
dirty checkout and other worktrees preserved. P05 Complete after actual prerequisite
integration and merged smoke; this supersedes the pending handoff. Checkpoint
1B/M2 remain open; no whole-module or full UI claim. Doubles/limits/Windows skip
remain disclosed above. New hosted CI not yet claimed at this recording point.
Next eligible M2 P05B source-backed Event listing (P03C/P04B integrated), no next
task started. Entire agreed scope including approved additions retained.


### P05B verification — 2026-11-02

P05B / Checkpoint 1B / M2 yazh-07. User approved bounded files/read policy and
explicitly authorized implementation/test/commit/push/merge. Isolated branch
feat/p05b-event-list from clean fetched common base
b5cb37b8d3dbe3d8f23b29a6516162c407cf4335 (local/remote read-back equal).
Actual integrated P03C bb2d18f/P04B c29e517 plus P05 04af24f/P04/source chain;
completed 0/1A regressions retained. No other active P05B branch/claim found.

Commands/results on final runtime/test source:
- CPython 3.14.8/jsonschema 4.25.1; python -m pip check PASS, no broken requirements.
- Redocly 2.57.0 lint/bundle specs/openapi.yaml PASS (existing license warning).
  EVORA_CONTRACT_BUNDLE points to the fresh temporary P05B JSON bundle.
- python -W error::ResourceWarning -m unittest backend.tests.test_events -v:
  20 PASS/no skips, including real Uvicorn localhost end-to-end producer/read test.
- python -W error::ResourceWarning -m unittest discover -s backend/tests -v:
  269 run, 268 PASS/one existing Windows symlink-permission SKIP.
- python scripts/verify_coordination.py <bundled-json-path> PASS;
  python -m unittest discover -s scripts -p 'test_*.py' -v: 122 PASS/no skips.
- Node 22.23.3: frontend test 48 PASS/no skips; build (API freshness, TypeScript,
  esbuild) PASS. Pinned npm 12.2.0 CLI runs the test command; initial build's nested
  npm used bundled 10.9.9. Separate tool shim outside repo selects 12.2.0 for the
  final pinned build; no dependency/workflow change. Registry certificate retries
  fell back to cached package data; TLS verification was not disabled. This local
  cache reuse is not a claim of a clean online install; fresh hosted CI remains
  to verify after publication.
- openapi-typescript 7.10.1 generation and strict TypeScript 5.9.3 declaration
  compile PASS. DESIGN 0.4.0 lint PASS, zero errors/warnings.
- EVORA_TEST_PYTHON pinned to tested interpreter, Node frontend/test/cases.integration.mjs
  PASS: actual U02/U02B/U03/U04/I00 localhost case/intake/audit/original/hash/actor/
  validation/error regressions. No upstream producer double.

P05B real synthetic network/GPS source read-back: exact immutable stored Event
wire, IDs/kinds/summaries/score0/raw/UTC/fractional strings and source arrays.
Two network events plus one GPS event total3; each cites all three row observations
with actual original Evidence IDs/locators. Participant IDs resolve real P05
Entities and share Event source observations; GPS D-8 stays distinct. Repeated
rows/Evidence remain distinct reports and IDs, no inferred identity/corroboration
or confidence boost. Real HTTP totals2/3/5 after network/GPS/duplicate network;
malformed supported CSV accepts a failed run and total stays5. HTTP limit2/offset2
returns2/total5 and joins actual Observation/Entity APIs. No fabricated Event time.

Full pagination over27 events verifies Evidence UUID then Event UUID order,
default20/max100, all-page totals/no duplicates/skips, beyond-end and 10**100
offsets. Empty/unprocessed/header-only and controlled empty latest return honest
empty results with no older fallback. Actual newer processing selects new IDs;
old immutable outputs/historical Observation pin remain unchanged. New-key failed
retry leaves completed selection unchanged; scheduler-held queued/running/failed
partial JSON invisible. Completion selection preserves sub-microsecond fractions,
offset-equivalent instants and UUID ties. A real writer-thread publication during
a held read transaction preserves coherent old sources/participants/total/page;
subsequent read sees new IDs. Repeated reads preserve SQL/history/audit/originals
and schedule no processing.

Negatives: unknown/duplicate queries/selectors/invalid UUID/limits/offsets safe400;
missing/invalid/duplicate auth401; inaccessible/missing/revoked case404. Corrupt
selected JSON/shape/UUID/case/run/score/type/time, missing required fields, unknown
private fields, duplicate IDs/source/participant refs, missing latest output,
Evidence mismatch, invalid Entity/source joins, stale/foreign/missing/unrelated
participants and Observation citations fail whole read safe404 without leaked
content/partial pages or fallback. Generic Event wire fixture permits empty
participants/omitted timestamps and preserves a nonzero stored score; it is
schema-only compatibility, not another implemented adapter.

First focused run:19 tests,18 PASS/one fixture error because blank required CSV
timestamp was incorrectly expected to publish. Corrected the fixture to respect
existing P01 rejection; added explicit failed-run/no-publication blank-time case.
Final20 and full269 checks pass. Malformed timestamp text/missing timezone/unknown
-00:00 offset are preserved with no UTC; valid fractions remain exact. No existing
parser/normalizer changed to make the fixture pass.

Doubles/limits: synthetic actors/tokens/CSV only; actual FastAPI/SQLite/private
files and full F03/F05/P01/P02/P03/P03B/P03C/P04/P04B/P05 producer chain. Core HTTPX
ASGI is in process; separate Uvicorn subprocess is real HTTP with temp cleanup.
Scheduler/publication gates, controlled 2099 selection metadata, temporary DB
corruption bypassing immutable triggers and held-read race are explicit fixtures.
Generic text Event is schema-only; prior suites retain their documented doubles.
No production auth/full Event UI/OS power-loss/distributed worker/maximum-size
benchmark/real-evidence claim. Wire/context/joins do not prove factual source
truth or authenticity after arbitrary DB tampering. Exact commands/synthetic
counts/failure control and cleanup in backend/README.md How you can test P05B.

Only approved router wiring is shared runtime change; no DB/schema/spec/producer/
dependency/frontend change. Full FEATURE_SCOPE/additions and original dirty
checkout/other worktrees preserved. P05B In Progress pending integration/smoke,
Checkpoint1B/M2 remain open. Next eligible M2 P14 private versioned parser/model
provenance (P04 integrated); no next task started.


### P05B integrated acceptance — 2026-11-02

User-authorized task commit **b6dddc721f056fd9542049bc5f314dc32b2e0cc1** pushed to
feat/p05b-event-list. Shared docs/coordination-foundation read back clean at the
verified base and merged without conflicts at
**c0e25d401651b468d05a60ff5f5e3525e87e6f5f**. On that exact merge:20 focused Event
tests PASS (including real Uvicorn process-to-source/Event/participant reads),
coordination verifier PASS, real I00 intake/audit/hash/original/actor/error smoke
PASS. No runtime/test changes after the full regression matrix recorded above.
Protected-path guard confirms full FEATURE_SCOPE/spec/frontend/schema/producers/
dependencies unchanged; original dirty checkout and other worktrees preserved.
P05B Complete after actual prerequisite integration and merged smoke; this
supersedes the pending handoff. Checkpoint1B/M2 remain open. Existing Windows
symlink skip and all doubles/setup/deployment/UI/performance limits remain
explicit above. New hosted CI not yet claimed at this recording point.
Next eligible M2 P14 private versioned parser/model provenance (P04 integrated);
no next task started. Entire agreed initial scope/approved additions retained.


### P14 verification — 2026-11-02

P14 / Checkpoint1B / M2 yazh-07. User approved bounded file/private-provenance
policy and explicitly authorized implement/test/commit/push/merge. Isolated
feat/p14-processing-provenance from clean fetched common base
98a28260f2fb2d91dd803c2f1835de264c5d0973; latest fetch still matches. Real P04
f851dd1, P01/P02/P03/P03B/P03C/F00/F03/F05 plus P04B/P05/P05B are integrated,
not planning-only prerequisites. Checkpoints0/1A regressions preserved.

Actual commands/results on final runtime/test source:
- CPython3.14.8, SQLite3.50.4, jsonschema4.25.1; python -m pip check PASS,
  no broken requirements. Node22.23.3/npm12.2.0 read back; existing local cached
  tools/dependencies reused, not a fresh online-install claim.
- Redocly2.57.0 lint/bundle specs/openapi.yaml PASS (existing missing-license
  warning); EVORA_CONTRACT_BUNDLE set to fresh temporary P14 bundle.
- python -W error::ResourceWarning -m unittest backend.tests.test_processing_provenance -v:
  18 PASS/no skips, including independent real Uvicorn HTTP/private SQL smoke.
- python -W error::ResourceWarning -m unittest discover -s backend/tests -v:
  287 run,286 PASS/one existing Windows symlink-permission SKIP.
- python scripts/verify_coordination.py <bundled-json-path> PASS;
  python -m unittest discover -s scripts -p 'test_*.py' -q:122 PASS/no skips.
- npm --prefix frontend test:48 PASS/no skips; npm --prefix frontend run build
  PASS (API freshness, TypeScript, esbuild). Generated openapi-typescript7.10.1
  declarations and strict TypeScript5.9.3 compilation PASS.
- DESIGN0.4.0 lint PASS, zero errors/warnings. git diff --check PASS.
- EVORA_TEST_PYTHON pinned to tested interpreter; Node frontend/test/cases.integration.mjs
  PASS actual localhost U02/U02B/U03/U04/I00 case/intake/audit/hash/original/actor/
  error regressions. Initial compatibility run:44 P14/processing/skeleton PASS;
  then two additional provenance boundary/real HTTP tests included in final18/287.

Actual network/GPS originals traverse real F03/F05/P01/P02/P03/P03B/P03C/P04
and publish processing-provenance/1 with processing-lifecycle/2. Network6/4/2
Observation/Entity/Event IDs and GPS3/1/1 exactly match private manifests. Input
Evidence/run/case/hash/size/kind, frozen parser/normalizer/projector/processor
versions, byte/row parameters, accepted/completion timestamps and exact stored
output digest read back correctly. Deterministic method/model=null honestly
records no model use. Empty successful CSV has three empty ID manifests, not a
failed-run disguise. All observations retain original run/source locators.

Provenance, immutable output and completed pointer commit in one transaction,
with identical completion time and SQL gate. Injected failure before provenance,
after private insert and after completion update rolls back both private/output
rows and leaves safe PROCESSING_FAILED, never completed/visible partial output.
Missing/mismatched-time provenance blocks SQL completion. Duplicate output IDs,
wrong source run and missing source/participant references cannot publish a
provenance success. Same-key replay preserves one original record/failure; new
key retries with new immutable output IDs, old input/hash/history unchanged.

Private reader rechecks actual SQLite membership and exact same-case Evidence/
run/output joins under one read snapshot. Foreign/missing/mismatched/pending/
failed/legacy/revoked references and corrupt payload/version/context/digest/
manifest/model/output JSON return identical safe404. No fallback or
private content in error messages. UPDATE/DELETE/REPLACE/UPSERT collisions and
hidden-rowid bypass blocked by WITHOUT ROWID and append-only triggers. Startup
adds empty private table, preserves existing completed history without fabricated
backfill, leaves old Observation/Entity/Event APIs usable and new processing
provenance functional. Interrupted queued jobs fail per existing P04 policy,
never fabricate success. Frozen config/safe errors remain available on failed runs.

Real localhost Uvicorn test executes actual upload/start/poll/list for network/
GPS and malformed CSV, directly reads its real private SQL records and matching
run/evidence/hash/time/manifests, verifies failed run has no success record and
undeclared provenance HTTP path404. Separate internal-reader controls exercise
real membership revocation/case isolation. Public ProcessingRun schema unchanged
except the existing processor_version value bump; public audit unchanged. A log
capture using synthetic source/key/token/path sentinels confirms no raw private
content/credentials in processing/audit responses or application logs. The
manifest stores IDs/digests/configuration, not raw source text/locators or paths.

Doubles/limits: synthetic actors/tokens/CSV only. Core FastAPI/SQLite/private
files and actual parser/normalizer/Entity/Event chain are real, HTTPX ASGI is in
process. Independent Uvicorn test is real HTTP/private SQL read-back, not an
invented private route. Scheduler/publication faults and temp corruption bypassing
immutability are explicit fixtures. Upgrade uses controlled pre-P14 schema/version
fixture built from actual outputs, not an actual historic-deployment migration.
No real evidence/model/provider, production identity, OS power-loss/distributed
worker, full provenance UI or maximum-size benchmark claim. Hash/link validation
is not a signature/certified chain of custody or authenticity after arbitrary
DB tampering. Existing unrelated doubles remain disclosed in earlier records.
Exact commands, synthetic counts, real HTTP smoke, atomic failure control and
cleanup are in backend/README.md How you can test P14.

Only approved processing initialization/publication and skeleton table-inventory
line changed outside new private module/tests/docs. No M1 table, parser, spec,
frontend, dependency or source-read API change. Full FEATURE_SCOPE/additions and
original dirty checkout/other worktrees preserved. P14 In Progress pending actual
merge/smoke; hosted CI not yet claimed. Checkpoint1B/M2 remain open. F08 audit and
P14B dispatch/P14C full failure-recovery remain required. Next eligible M2 P14B
(P04/P01/P02 integrated); no next task started.


### P14 integrated acceptance — 2026-11-02

User-authorized task commit **aee4220dd6e16de377591a95fcf86f23b7c4a1f1** pushed to
feat/p14-processing-provenance. Clean shared docs/coordination-foundation remained
at the verified common base; merged without conflicts at
**c03361b8171e6506d2c160a85cc1e89e76315fb3**. On that exact merge:18 focused
provenance tests PASS (including real Uvicorn HTTP/private SQL smoke), coordination
verifier PASS, real I00 intake/audit/hash/original/actor/error smoke PASS. No runtime
or test changes after final full287 matrix above. Protected-path guard confirms
full FEATURE_SCOPE/spec/frontend/M1 tables/parsers/dependencies/source read APIs
unchanged; original dirty checkout and other worktrees preserved. P14 Complete
after real prerequisite integration and merged acceptance; supersedes pending
handoff. Checkpoint1B/M2 remain open. The Windows symlink skip and all synthetic/
fault/schema-fixture/setup/deployment/model/UI/performance limits remain explicit
above. New hosted CI not yet claimed at this recording point. Next eligible M2
P14B network/GPS dispatch (real P04/P01/P02 integrated); P14C/F08 and later full
modality/model tasks remain required. No next task started; entire initial scope
and approved additions preserved.


### P14B verification — 2026-11-02

P14B / Checkpoint1B / M2 yazh-07. User approved bounded file handoff/unchanged
recorded C-04 policy and explicitly authorized implement/test/commit/push/merge.
Isolated feat/p14b-processing-dispatch from clean fetched common base
acf07fec95442c8ae8b9c099dda827a9f68c9a5d. Real P04 f851dd1/P01 cab08f1/P02
389652c, source chain and P14 c03361b are integrated, not planning documents.
No active competing P14B claim/branch found. Completed0/1A regressions preserved.

Actual final source commands/results:
- CPython3.14.8/jsonschema4.25.1, python -m pip check PASS/no broken requirements;
  Node22.23.3/npm12.2.0, reused tested local cached tools/dependencies.
- Redocly2.57.0 lint/bundle specs/openapi.yaml PASS (existing missing-license
  warning); EVORA_CONTRACT_BUNDLE set to fresh temporary P14B bundle.
- python -W error::ResourceWarning -m unittest backend.tests.test_processing_dispatch
  backend.tests.test_processing -v:35 PASS/no skips (14 new P14B tests plus21
  existing processing tests; real Uvicorn HTTP/private SQL smoke included).
- python -W error::ResourceWarning -m unittest discover -s backend/tests -v:
  301 run,300 PASS/one existing Windows symlink-permission SKIP.
- python scripts/verify_coordination.py <bundled-json-path> PASS;
  python -m unittest discover -s scripts -p 'test_*.py' -q:122 PASS/no skips.
- npm --prefix frontend test:48 PASS/no skips; npm --prefix frontend run build
  PASS (API freshness/TypeScript/esbuild). openapi-typescript7.10.1 generated
  declarations/strict TypeScript5.9.3 compile PASS. DESIGN0.4.0 lint PASS with
  zero errors/warnings; git diff --check PASS.
- EVORA_TEST_PYTHON pinned to tested interpreter; Node frontend/test/cases.integration.mjs
  PASS actual localhost U02/U02B/U03/U04/I00 intake/audit/hash/original/actor/error
  regressions. No source producer double in successful chain or HTTP smoke.

Immutable mapping/frozen descriptors bind actual parser callables and producer-
owned versions/limits; no duplicate hardcoded parser version or dynamic filename/
MIME fallback. Real network/GPS originals publish6/4/2 and3/1/1 Observation/Entity/
Event records through actual P04/P14, with matching input hash, selected parser
version/limits and private completion/manifests. Valid network bytes named gps.csv
with image/png MIME still use network parser; valid GPS bytes named network.bin
with application/pdf MIME still use GPS. Actual content, not metadata, validates
success. Upload alone creates no processing run/provenance/derived observations.
BOM, CRLF/multiline quoting, raw cell values/source locators, uncertain GPS time
and unchanged original bytes/hash survive the complete pipeline. Matching
header-only CSV is genuine empty success with empty private output manifests.

Opposite-kind layout on both registered kinds accepts then fails safe
CSV_INVALID_HEADER, never silently reroutes. Every other currently declared kind
(document/image/video/audio/message/mobile_log/transaction) returns415 before
run/key creation, even with valid network bytes; rejected key can subsequently
start a supported target. Malformed UTF-8/quotes/NUL/IP/GPS coordinate/timestamp
controls fail safely without private cell text, output or success provenance.
Actual100001-row uploads on both adapters fail CSV_ROW_LIMIT with no partial
prefix or private record. Existing full parser regressions exercise inclusive
50MiB/100000-row boundaries and overflow; P14B does not claim a maximum-size
successful normalized/published full-pipeline benchmark.

Frozen current selection matches accepted kind/parser version/byte-row limits.
Test-only selected-descriptor version/limit changes fail before parser invocation.
Same-key replay precedes current lookup, retaining original run/private record
even with a test-only unavailable selection; fresh key evaluates selection and
can retry after restoration. Failed late row/new-key failures expose no prefix
and preserve older successful sources/private provenance. Actual F00 denies
foreign/missing/invalid actor cases before selection/run creation. Existing P04
running/revocation tests retain assertions/real source execution; only two
injection points/imports now wrap selected descriptor instead of mutating the
removed private _PARSERS dictionary.

Real Uvicorn HTTP/private SQL smoke uses misleading .bin/octet-stream metadata,
executes network/GPS success, malformed and both cross-layout failures, and
unsupported document415/no run. Exactly two success-provenance records; actual
public read totals9 Observations/5 Entities/3 Events, with matching private
input/hash/time/manifest IDs and no new private endpoint. No mere-upload success.

Doubles/limits: synthetic actors/tokens/CSV only; real FastAPI/SQLite/private
files/P01/P02/P03/P03B/P03C/P04/P14. Core HTTPX ASGI is in process; independent
Uvicorn is real localhost HTTP/private SQL. Held scheduler and replaced selection/
version/limit/parser wrappers are labeled test-only controls, not substitute
successful producers. Prior suites retain their disclosed fault/schema fixtures.
No real evidence/model/provider/production identity, OS power-loss/distributed
worker/full processing UI or maximum-size successful pipeline benchmark claim.
Existing C-04 behavior/config/provenance/wire/parser/processor versions remain
unchanged; source format/limits were not loosened to pass a test. Exact commands,
synthetic inputs/counts, real HTTP smoke, wrong-layout failure and cleanup are in
backend/README.md How you can test P14B.

Protected-path guard confirms no parser/P14 format/schema/spec/frontend/dependency/
M1 table/read API/full FEATURE_SCOPE/addition change. Original dirty checkout and
other worktrees preserved. P14B In Progress pending integration/smoke/hosted CI;
Checkpoint1B/M2 remain open. F08 audit/P14C full failure-retry-recovery gate and
all later adapters remain required. Next eligible M2 P14C after this integration
(P04 already integrated); no next task started.


### P14B integrated acceptance — 2026-11-02

User-authorized task commit **2c7af4b68284f7d7c63e9b9c01d76da2d2c5caf9** pushed to
feat/p14b-processing-dispatch. Clean shared docs/coordination-foundation remained
at verified base; merged without conflicts at
**d7a4315377cc1fdae63200780bd7728c583a14dd**. On that exact merge:14 focused
P14B tests PASS, including actual100001-row overflow and real Uvicorn HTTP/private
SQL dispatch; coordination verifier PASS; real I00 intake/audit/hash/original/
actor/error smoke PASS. No runtime/test changes after final full301 matrix above.
Protected-path guard confirms full FEATURE_SCOPE/additions/spec/frontend/schema/
parsers/P14 format/dependencies/M1 tables/source-read APIs unchanged. Original
dirty checkout and other worktrees preserved. P14B Complete after actual
prerequisite integration and merged acceptance; supersedes pending handoff.
Checkpoint1B/M2 remain open. Windows symlink skip and all synthetic/selection/
scheduler/fault/setup/UI/model/performance limits remain disclosed above. New
hosted CI not yet claimed at this recording point. Next eligible M2 P14C
failure/retry atomicity and full publication/recovery gate (P04/P14B integrated);
F08 audit and all later modality tasks remain required. No next task started.


### P14C verification — 2026-11-02

P14C / Checkpoint1B / M2 yazh-07. User approved bounded file/lifecycle handoff
and implement/test/commit/push/merge authorization. Isolated feat/p14c-atomic-processing
from clean fetched common base fb52aba41310ae644bb9a12bd4884862367932cc;
latest fetch still matches. Actual P04 f851dd1/P14B d7a4315/P14 c03361b and full
source/read/access chain integrated; no planning-only producer substituted.
Completed0/1A regressions retained; no competing P14C branch/claim found.

Actual commands/results on final runtime/test source:
- CPython3.14.8/jsonschema4.25.1, pip check PASS/no broken requirements;
  Node22.23.3/npm12.2.0, reused tested local cached tools/dependencies.
- Redocly2.57.0 lint/bundle specs/openapi.yaml PASS (existing missing-license
  warning). EVORA_CONTRACT_BUNDLE set to fresh temporary P14C JSON bundle.
- python -W error::ResourceWarning -m unittest backend.tests.test_processing_publication
  backend.tests.test_processing -v:34 PASS/no skips (13 new P14C and21 existing
  processing tests), including seven marker-verified hard-exit subcases and real
  Uvicorn HTTP/private SQL smoke.
- python -W error::ResourceWarning -m unittest discover -s backend/tests -v:
  314 run,313 PASS/one existing Windows symlink-permission SKIP.
- python scripts/verify_coordination.py <bundled-json-path> PASS;
  python -m unittest discover -s scripts -p 'test_*.py' -q:122 PASS/no skips.
- npm --prefix frontend test:48 PASS/no skips; npm --prefix frontend run build
  PASS (API freshness/TypeScript/esbuild). Generated openapi-typescript7.10.1
  declarations/strict TypeScript5.9.3 compile PASS. DESIGN0.4.0 lint PASS,
  zero errors/warnings; git diff --check PASS.
- EVORA_TEST_PYTHON pinned to tested interpreter; Node frontend/test/cases.integration.mjs
  PASS actual localhost U02/U02B/U03/U04/I00 intake/hash/original/audit/actor/error
  regressions. No source producer double on the successful source or HTTP chain.

Real network/GPS processing publishes6/4/2 and3/1/1 Observation/Entity/Event IDs,
with actual SQL output/private provenance present while the run is still running.
The verifier reads back run/frozen fields, exact output JSON/private uncertainty,
case/Evidence/run context and reconstructs P14 source/participant manifests/digest/
time from SQL before exactly one running row can become completed. It does not
trust only candidate values or successful INSERT. Missing/corrupt output/private
rows, altered bytes/context/payload/time/frozen config fail the publication and
roll back; safe PROCESSING_FAILED, no partial output/private rows. DDL corruption
controls also roll back and normal retry works. Completion-row-count fault cannot
pretend success. All public fields/status/error contracts remain unchanged.

A held verified transaction proves outsiders see prior completed run/outputs only,
no staged new output/private record; after release/commit, completed/new output/
private data become visible together. Old historical pins and private data stay
unchanged. Verification failure preserves earlier completed output; same key
replays original failed resource without a worker call; new key retries. Eight
concurrent same-key starts execute/publish exactly once using an actual parser
wrapped only for counting. Same-key different-target concurrency returns202/409
with one source-coherent output. Four distinct keys keep all histories; three
racing worker claims on one queued run still publish once.

Actual child Python processes run the real pipeline and hard-exit via os._exit(97)
at seven marker-verified boundaries: queued, claimed running, output insert,
provenance insert, verified SQL, completed pointer before transaction commit,
and after committed publication. No graceful connection cleanup at hard exit.
For all six pre-commit boundaries, actual SQLite rollback leaves no new output/
private rows visible; prior completed default output stays unchanged. Fresh
application lifespan on the same DB marks original queued/running resource failed
PROCESSING_INTERRUPTED, same key replays it and new key successfully retries.
Post-commit exit preserves actual completed resource/private record through fresh
startup; replay retains it and new key creates new IDs. Existing original input
hash/history and historical Observation IDs survive every boundary. SQLite
integrity_check and foreign_key_check pass after every interruption/retry.

Processing-owned INSERT guards reject run-ID/actor-case-key/REPLACE/UPSERT/hidden-
rowid collisions, supplementing original UPDATE/DELETE immutability. Tested old
completed output replacement into a new running target (previous context-only
INSERT guard would allow it), and failed-run hidden-rowid replacement (no output
FK to protect it). Both reject and preserve actual historical resources/private
data. No new table, column or M1-table modification.

Independent real Uvicorn HTTP smoke executes actual network/GPS upload/start/poll/
list and private SQL read-back, malformed run failed without success provenance,
public totals9 Observations/5 Entities/3 Events and no new private HTTP endpoint.
F00 foreign actor reads remain safe404; a verification failure exposes no public
partial observations/entities/events or raw exception text. Existing full P14
privacy/source-validation tests remain applicable.

Doubles/limits: synthetic actors/tokens/CSV only; real FastAPI/SQLite/private files
and P01/P02/P03/P03B/P03C/P04/P14/P14B. Core HTTPX ASGI is in process; independent
Uvicorn is real HTTP/private SQL. Held scheduler/verification gates, parser-count
wrappers, transactional corruption temporarily bypassing immutable triggers and
child crash-hook replacements are explicit test controls. Successful producers
execute actual adapters/normalization/projectors. Hard exit/SQLite rollback and
fresh app startup are real process-interruption tests, not hardware/OS power-loss
certification or distributed deployment proof. Earlier suites retain documented
doubles. No real evidence/model/production auth, full processing UI or maximum-
size successful full-pipeline benchmark claim. Exact commands, synthetic counts,
child-exit and corrupt-SQL failures plus cleanup in backend/README.md How you can
test P14C. Only test-created children exit; user applications are not terminated.

Protected paths preserve full FEATURE_SCOPE/additions/spec/frontend/parsers/P14
format/dependencies/M1 tables and existing source-read APIs/tests. Original dirty
checkout/other worktrees preserved. P14C In Progress pending integration/hosted CI; Checkpoint1B/M2 remain open. This is last M2 row in1B; F08 processing
audit, M4 processing/overview and I00B remain required. No automatically eligible
M2 row remains in earliest unfinished1B after this integration. Next catalog M2
P06 is2A: automatic selection also awaits earlier1B/I00B and1C/I01 exits, while
allowed independent work requires its own explicit handoff. No next task started.


### P14C integrated acceptance — 2026-11-02

User-authorized task commit **5b80124e488661c0f7efe320f386a2871dcfd9e4** pushed to
feat/p14c-atomic-processing. Clean shared docs/coordination-foundation stayed at
verified base and merged without conflicts at
**920331d95fdd359f1e20cfbcfba48fc6e2afb292**. On that exact merge:13 focused P14C
tests PASS, including all seven actual child hard-exit boundaries and real
Uvicorn HTTP/private SQL smoke; coordination verifier PASS; real I00 intake/
audit/hash/original/actor/error smoke PASS. No runtime/test changes after full314
matrix above. Protected-path guard confirms entire FEATURE_SCOPE/additions/spec/
frontend/parsers/P14 format/dependencies/M1 tables/previous source APIs/tests
unchanged. Original dirty checkout and other worktrees preserved.

P14C Complete after actual prerequisite integration and merged acceptance;
supersedes pending handoff. Windows symlink skip and all synthetic/scheduler/
counting/corruption/crash-hook controls plus OS power-loss/distributed deployment/
UI/auth/model/performance limits remain disclosed above. New hosted CI not yet
claimed at this recording point. This completes M2 rows in1B, not the module or
checkpoint. F08, M4 processing/overview rows and shared I00B still required.
No automatically eligible M2 task remains in earliest unfinished1B. P06(2A)
message candidate mentions is next M2 catalog work; automatic selection awaits
remaining1B/I00B and1C/I01 exits, or an earlier allowed independent-work assignment
must be explicitly recorded separately. No next task started; full scope retained.


### P06 independent implementation verification — 2026-11-02

P06 / 2A / M2 yazh-07 on feat/p06-message-mentions, exact reviewed common base
9454430a56502dfa8dad791e3d3f420c05424509. User explicitly assigned independent
work and approved format/extraction/resource policies and bounded shared file
handoff, including commit/push/merge into docs/coordination-foundation. Real P04
prerequisite and P14/P14B/P14C/read/access chain integrated. Earlier1B/I00B and
1C/I01 remain open; independent P06 cannot seal those gates or2A/I02.

Actual message adapter parses authorized immutable original bytes and publishes
source-preserving metadata/body/mention Observations and exact candidate keys.
Synthetic messages.csv yields5/2/0 Observation/Entity/Event records; actual
network/GPS/message fixtures yield14/7/3 with distinct persisted Entity UUIDs
across originals. Body locators retain physical row spans and half-open Unicode
code-point offsets, not CSV byte offsets. Same-case body and occurrence IDs are
cited; no sender identification, ownership, identity or Event inference. P03 raw
invalid/uncertain time and unavailable confidence0 are preserved. Header-only
success is genuinely empty. Duplicate rows/occurrences stay separate source IDs.

Limits50MiB/100000 rows/100000 mention occurrences are explicit, bounded and
atomic. New message config/private record freezes all three parameters,
messages-csv/1, message-candidates/1, processing-lifecycle/3 and no Event/model
execution. Existing network/GPS processor2/private records stay unchanged. Two
processing-owned version guards upgrade transactionally; no new table/column,
public route/field, M1 table, dependencies or frontend changes. Real old-version
trigger fixture upgrades successfully with prior output/provenance unchanged.

Initial focused command (messages plus dispatch) passed37 tests; separate added
old-trigger migration test passed1. Full backend/coordination checks are pending
at this recording point, not inferred from focused success. OpenAPI lint/bundle
passed (one existing missing-license warning); generated TypeScript compilation,
DESIGN lint (0errors/0warnings), frontend48 tests/build and real I00 loopback
intake/hash/download/audit/actor/error smoke passed. Final results recorded below
only after actual completion. Source/API/schema/digest/manifest/versions/limits,
replay/new-key/history, malformed/late invalid/overflow, wrong layout, case/auth,
no sensitive body/key in public logs/audit, rollback/forbidden Event and safe
corrupt-private-read controls are exercised by focused tests.

Doubles/limits: only synthetic fixtures/identities/tokens. Real FastAPI/SQLite/
private original storage/parsers/projection/publication/readers run; HTTPX ASGI
is in process, independent Uvicorn is actual loopback HTTP/private SQL. Explicit
scheduler holds, changed registry, verifier/forbidden-Event injections and
trigger-bypassing corruption occur only in temporary test databases. No successful
message producer is substituted. Older suites retain their documented controls,
including real dedicated-child process exits around P14C publication boundaries.
No real evidence, production identity provider, model, full processing UI,
distributed deployment, hardware power-loss or maximum-size successful pipeline
benchmark claim. Real parser byte/row/mention boundaries and actual processing
row/mention overflow are tested, not reduced-cap substitutes. Exact commands and
synthetic expected/failure outputs are in backend/README.md How you can test P06;
tests clean temporary files/servers, optional TEMP-bundle cleanup is separate.

Protected paths preserve full FEATURE_SCOPE/additions/spec/frontend/old parsers/
normalizer/source-read APIs/dependencies/M1 tables. Existing original dirty
checkout and all other worktrees preserved. P06 remains In Progress pending
actual integration; next M2 catalog row P07(3A) requires earlier checkpoint exits
for automatic selection or its own explicit independent handoff and decisions.


### P06 pre-integration results — 2026-11-02

Actual Windows combined candidate: full backend337 run,336 PASS/1 existing SKIP
(creating symlinks unavailable on this platform/account),318.106s. The added
old-version-guard migration test ran separately and PASS1; it was added after the
full run's discovery, so it is not falsely counted in337. Initial focused P06/
dispatch37 PASS. No runtime changes after this full matrix. Coordination122 PASS;
verifier PASS (27 operations/126 tasks/39 capabilities); frontend48 PASS/build/API
freshness/typecheck PASS; actual I00 real HTTP intake/audit/hash/download/actor/
error smoke PASS. OpenAPI lint/bundle PASS with one existing missing-license
warning; fresh generated types compile; DESIGN0 errors/0 warnings; pip check PASS;
whitespace/protected-path checks PASS. CPython3.14.8/SQLite3.50.4/jsonschema4.25.1,
Node22.23.3/npm12.2.0. Exact commands in backend/README.md; documented doubles and
limits above apply. P06 still In Progress until authorized integration and
post-merge checks. Hosted CI not yet claimed. Full scope/additions preserved.


### P06 integrated acceptance — 2026-11-02

User-authorized implementation283d5a3 and whitespace-only849d12b (task head
**849d12b085681c92507eabc4da8a72ca09324c4a**) pushed to feat/p06-message-mentions.
Clean shared docs/coordination-foundation remained at the verified base and
merged without conflicts at **1b938d93c09ad82f2ef5af8eac214026d7a820f7**. On that
exact merge:24 focused P06 PASS (including old-version trigger upgrade and real
Uvicorn HTTP/private SQL); coordination verifier PASS; real I00 intake/audit/
hash/original/actor/error smoke PASS. Full337 backend matrix and separately added
upgrade test above remain valid; no runtime changes after that matrix. Final
whitespace/protected-path guard PASS. Entire FEATURE_SCOPE/additions/spec/
frontend/old parsers/normalizer/M1 tables/dependencies remain unchanged; original
dirty checkout and other worktrees preserved.

P06 Complete after actual prerequisite integration and merged acceptance;
supersedes pending status. All synthetic/scheduler/registry/verification/SQL
corruption controls and production-auth/model/UI/performance/power-loss limits
above still apply. Existing local Windows symlink skip disclosed. Hosted CI not
yet claimed at this recording point. This independent task does not close1B,
1C or2A; F08/M4 processing/overview/shared I00B (explicit assignee required),
1C/I01, and A07/U06B/I02 remain required. Next M2 catalog row P07(3A) is not
automatically eligible until preceding gates, including2A/2B/2C, exit; an earlier
independent handoff requires explicit assignment and format/resource/file-scope
decisions. No next task started; full product scope preserved.


### P07 independent implementation verification — 2026-11-02

P07 / 3A / M2 yazh-07, feat/p07-document-text from verified common base
97564aea28775c96679439dd5ffc22077ea75a64. Explicit user independent assignment,
approved plain-text policy/files and additional fixture-only unsupported-kind
updates in test_processing/test_processing_provenance; commit/push/merge into
docs/coordination-foundation authorized after acceptance. P04 and source/private
provenance/read/atomic-publication prerequisites are real integrated producers.
Earlier checkpoints remain open, not waived by this independent assignment.

Focused final-runtime P07 tests18 PASS. Actual source/line/code-point offsets,
UTF-8/BOM/newlines/blanks/whitespace/duplicates/empty behavior, no timestamp/entity/
event inference and private frozen byte/line parameters are verified. Real parser
50MiB/100000-line limits and actual processing100001-line failure, invalid UTF-8/
NUL atomic failure and safe errors, replay/conflict/new-key/history, source/membership/
body validation, restart/interrupted retry, old processor2/3 guard upgrade, no
private-record completion, corrupted private404 and publication rollback controls.
Independent Uvicorn uses real HTTP/private SQL. Synthetic BOM plus
'😀 D-7  \r\n\rsecond\nsecond\n' yields4/0/0, spans0:7,9:9,10:16,17:23;
combined actual network/GPS/message/document yields18/7/3. Source originals/hash
unchanged; existing output/private records byte-for-byte preserved across upgrade.
Full regression results pending at this initial recording point, not inferred
from focused success. Exact commands and expected/failure results in backend/README.md.

Doubles/limits: synthetic actors/tokens/text, real FastAPI/SQLite/private files/
parser/publication/read/provenance. In-process HTTPX ASGI plus real independent
Uvicorn. Explicit scheduler/registry/verifier controls, temp-only SQL corruption
and old-guard recreation; no successful parser replacement. Earlier suites retain
their documented controls, including P14C dedicated-child exits. No real evidence,
production auth, processing UI, PDF/DOCX/OCR/model, distributed deployment,
hardware power-loss or maximum-size successful pipeline benchmark claim. Real
parser caps are tested, actual line-overflow processing uses original cap. Tests
clean temporary files/servers; optional TEMP bundle cleanup separately.

Protected full FEATURE_SCOPE/additions/spec/frontend/M1 tables/dependencies/old
parsers/normalizer/source-read APIs remain unchanged; original dirty checkout and
other worktrees preserved. P07 In Progress until actual authorized integration and
merged acceptance. Next M2 catalog row P11(3A) requires its own mobile format/policy/
file handoff; no automatic eligibility while earlier checkpoints unfinished. P13
retains actual Entity extraction, P13B Event extraction; no scope removed/deferred.


### P07 pre-integration results — 2026-11-02

Final runtime candidate full backend356 run:355 PASS/1 existing Windows SKIP
(creating symlinks unavailable on this platform/account),256.425s. Focused P07
18 PASS, including independent Uvicorn HTTP/private SQL. All prior-checkpoint
regressions and old adapter/publication/crash controls ran in the full suite.
Frontend48 PASS; coordination122 PASS; verifier PASS (27 operations/126 tasks/
39 capabilities); actual I00 real HTTP intake/audit/hash/original/actor/error
smoke PASS. OpenAPI lint/bundle PASS with one existing missing-license warning;
fresh generated declarations compile; frontend API freshness/typecheck/build
PASS; DESIGN0 errors/0 warnings; pip check PASS; whitespace/protected-path checks
PASS. CPython3.14.8/SQLite3.50.4/jsonschema4.25.1/Node22.23.3/npm12.2.0.
No runtime changes after the full matrix. Exact commands, expected outputs,
cleanup and synthetic/failure-control/untested limits above and backend/README.md
apply. P07 In Progress until authorized integration and post-merge acceptance;
hosted CI not yet claimed. Full scope/additions preserved, no later task started.


### P07 integrated acceptance — 2026-11-02

User-authorized task commit **213565a98d6688a01ab450707a23162e25f9f0de** pushed to
feat/p07-document-text. Clean shared docs/coordination-foundation stayed at
verified base and merged without conflicts at
**c8b5331465a25175e6ee0e470795061fa786ce70**. On that exact merge:18 focused P07
PASS, including real Uvicorn HTTP/private SQL and old-guard upgrade; coordination
verifier PASS; real I00 intake/audit/hash/original/actor/error smoke PASS. Full356
backend matrix above remains valid; no runtime changes after it. Final whitespace/
protected-path guard PASS: full FEATURE_SCOPE/additions/spec/frontend/old parsers/
normalizer/source-read APIs/M1 tables/dependencies unchanged. Original dirty
checkout and other worktrees preserved. Both explicitly approved old unsupported-
kind fixture substitutions retain original415/replay/no-publication assertions.

P07 Complete after actual prerequisite integration and merged acceptance;
supersedes pending status. Existing local Windows symlink skip and synthetic/
scheduler/registry/verifier/SQL/old-guard controls plus auth/UI/OCR/model/performance/
power-loss limits above remain disclosed. Hosted CI not yet claimed at this
recording point. This independent row closes neither earlier gates nor3A. Next
M2 catalog task P11(3A) requires one approved mobile-record format/resource/file
handoff; automatic eligibility still waits for earlier checkpoint exits, or
explicit independent work must be separately assigned. P13 now has real P06/P07
prerequisites but its own extraction/evaluation acceptance remains required;
P12/P13/P13B/P08 and every initial modality/approved addition remain required.
No next task started; full scope preserved.


### P11 independent implementation verification — 2026-11-02

P11 / 3A / M2 yazh-07, feat/p11-mobile-records from verified common base
c12deb1fa58863b333bbb6fe2b835e848dfa504d. User explicitly assigned independent
work and approved mobile layout/output/time/resource/files plus commit/push/merge
after acceptance. Real P04 and source/access/provenance/read/atomic publication
prerequisites integrated. Earlier checkpoint exits remain open, no milestone
closure from this independent row. Full FEATURE_SCOPE/additions preserved.

Final focused P11+dispatch36 PASS (P11 contributes22). Initial run had35 PASS/1
test-helper error (async page-collection generator); corrected eager collection,
then36 PASS. First frontend invocation raced ignored dependency-junction setup
and failed to find esbuild; rerun after setup passed48/build/real I00 smoke. These
were verification harness/setup errors, not passing application claims. Runtime
parser/projection successful paths were not replaced or relaxed. OpenAPI lint/
bundle PASS (one existing missing-license warning), fresh generated declarations
compile; DESIGN0 errors/0 warnings, pip check PASS. Full backend/coordination
results pending at this initial recording point, not inferred from focused tests.

Actual synthetic two-row mobile source yields6/2/2 Observation/Entity/Event
records, case-sensitive device:D-007/device:D-8 keys, exact raw values/row locators,
first precise UTC2026-01-12T10:00:00.123456789Z, second unknown UTC omitted. Every
Event reports source label, cites all3 row Observations and a real same-case
candidate Entity sharing device source. Actual five adapters together22/9/5,
separate originals retain separate identical-key Entity UUIDs/confidence0. Exact
source hash/bytes, private manifests/versions/parameters and old output/private
record read-back, all-page source APIs, replay/conflict/new-key/historical IDs,
concurrent replay/duplicate worker, restart/interrupted retry and old2/3/4 guard
upgrade are exercised. Real byte/row limits and actual processing100001-row
failure, malformed/wrong-layout/late blank/encoding controls publish no partial
output/provenance. Raw invalid/uncertain time is not fabricated into UTC.

Doubles/limits: synthetic actors/tokens/CSV; actual FastAPI/SQLite/private files/
parsers/time/projectors/provenance/publication/readers. In-process HTTPX ASGI and
independent Uvicorn real HTTP/private SQL. Explicit scheduler/registry/verifier/
missing-participant injections, temporary old-guard recreation and trigger-
bypassing SQL corruption; no successful producer substitution. Earlier suites
retain documented controls, including P14C dedicated-child real hard exits.
No real acquisition/evidence, production auth, model, full UI/graph workflow,
distributed deployment, hardware power-loss or maximum-size successful pipeline
benchmark claim. Exact commands/inputs/outputs/failures/cleanup in backend/README.md.
Tests clean temporary files/servers; optional TEMP bundle cleanup separately.

Protected FEATURE_SCOPE/additions/spec/frontend/M1 tables/dependencies/old parsers/
normalizer/source-read APIs unchanged; existing dirty checkout and other worktrees
preserved. Only bounded existing dispatch expectations and P07 old-guard fixture
change. P11 In Progress until actual integration and post-merge acceptance.
Next M2 catalog P12(3A) needs its own format/policy/file handoff and preceding
checkpoint exits for automatic selection, or explicit independent assignment;
no next task started. All remaining scope stays required.


### P11 pre-integration results — 2026-11-02

Final combined Windows candidate full backend378 run:377 PASS/1 existing SKIP
(creating symlinks unavailable on this platform/account),261.223s. Focused36
P11/dispatch PASS, P11 contributes22. No runtime changes after full matrix.
Frontend48 PASS; coordination122 PASS; verifier PASS (27 operations/126 tasks/
39 capabilities). Fresh OpenAPI lint/bundle PASS with one existing missing-license
warning; generated declarations compile; frontend API freshness/typecheck/build
PASS; DESIGN0 errors/0 warnings; actual I00 real HTTP intake/audit/hash/original/
actor/error smoke PASS; pip check and whitespace/protected-path guards PASS.
CPython3.14.8/SQLite3.50.4/jsonschema4.25.1/Node22.23.3/npm12.2.0.
Initial test-helper/setup failures and their successful reruns are recorded above.
Exact commands and synthetic/failure-control/untested limits remain applicable.
P11 In Progress pending actual integration/post-merge acceptance; hosted CI not
yet claimed. Full scope/additions preserved; no next task started.


### P11 integrated acceptance — 2026-11-02

User-authorized task commit **4f0099b5003d45db81b1d20f50dd341735e80eba** pushed to
feat/p11-mobile-records. Clean shared docs/coordination-foundation stayed at
verified base and merged without conflicts at
**212a5e204437ca02b40be08b3187d2f17c6c9577**. On that exact merge:22 focused P11
PASS including actual Uvicorn HTTP/private SQL, complete source/participant joins
and old-version upgrade; coordination verifier PASS; real I00 intake/audit/hash/
original/actor/error smoke PASS. Full378 matrix above remains valid; no runtime
changes after it. Final whitespace/protected-path guards PASS. Full FEATURE_SCOPE/
additions/spec/frontend/M1 tables/dependencies/old parsers/normalizer/source-read
APIs unchanged. Original dirty checkout and other worktrees preserved. Only
approved existing dispatch expectations and P07 old-version guard fixture changed.

P11 Complete after actual prerequisite integration and merged acceptance;
supersedes pending status. Existing Windows symlink skip, initial verification
helper/setup fixes, synthetic/scheduler/registry/verifier/participant/SQL/old-guard
controls and production-auth/physical-acquisition/model/UI/graph/performance/
power-loss limits remain disclosed above. Hosted CI not yet claimed at this
recording point. Independent row closes no earlier gate or3A/I04. Next M2 catalog
P12(3A) needs approved transaction format/resource/file handoff; automatic
selection waits for earlier checkpoint exits, or earlier independent work needs
its own explicit assignment. Every remaining modality/feature/approved addition
remains required. No next task started; full scope preserved.


### P12 independent implementation verification — 2026-11-02

P12 / 3A / M2 yazh-07, feat/p12-transaction-csv from verified common base
bd1e03de15a7f212e77dac391b5efd8d6fc7af07. User explicitly assigned independent
work and approved transaction layout/decimal/currency/time/resource/source-output
policy and bounded files, including commit/push/merge after acceptance. Real P04
and access/source/private provenance/read/verified atomic publication prerequisites
integrated. Full FEATURE_SCOPE/additions preserved; earlier checkpoints stay open.

Focused P12+dispatch43 PASS (P12 contributes29). Actual source/API/SQL/participant/
private parameters/manifests/versions/hash read-back, exact128-character high-
precision decimal/sign/zero/negative-zero handling without floating conversion or
rounding; test Decimal precision2 cannot change normalization. Currency label
shape only, no ISO/minor-unit/FX claim. Malformed amount/currency/129-character
literals/late invalid rows/wrong layouts/encoding/actual100001-row source fail
atomically with safe CSV_* and no partial output/provenance. Real50MiB/100000-row
parser caps, byte/row/amount +1 controls, strict BOM/quoting/whitespace/context/time
and source-locator tests; same-case actual account participants, separate-source
identical account keys stay distinct/unboosted, schema/all-page APIs, replay/
conflict/retry/history, concurrency/duplicate worker, restart/interrupted failure,
old2/3/4/5 guard upgrade and old immutable records preserved. Real Uvicorn HTTP.

Synthetic two-row transaction yields6/2/2 Observation/Entity/Event, exact keys
account:AC-007/account:AC-8, raw amounts preserved and normalized strings
123456789012345678901234567890.12 / -1.23. First UTC2026-01-12T10:00:00.123456789Z,
second unknown UTC omitted. Six actual adapters together28/11/7; account candidate
link is not identity, verified transfer, fraud or guilt. Full backend/coordination
results pending here, not inferred from focused success. Frontend48/build/API
freshness/typecheck/real I00 smoke PASS; OpenAPI lint/bundle/generated compilation
PASS (existing missing-license warning); DESIGN0errors/0warnings PASS.

Doubles/limits: synthetic actors/tokens/CSV, real FastAPI/SQLite/private files/
parser/P03 time/exact decimal/projector/provenance/publication/read APIs; in-process
HTTPX ASGI and independent Uvicorn HTTP/private SQL. Explicit scheduler/registry/
verifier/participant injections, temp-only old-guard recreation/trigger-bypassing
SQL corruption; pure test Decimal context mutation, no successful producer stub.
Earlier suites retain documented controls including P14C dedicated-child hard exits.
No live bank/real evidence/production auth/model/full UI/graph workflow/distributed
deployment/hardware power-loss or maximum-size successful pipeline benchmark.
Exact commands/inputs/expected results/failures/cleanup in backend/README.md.
Tests clean temporary files/servers; optional TEMP bundle cleanup separately.

Protected FEATURE_SCOPE/additions/spec/frontend/M1 tables/dependencies/old parsers/
normalizer/source-read APIs unchanged; original dirty checkout and other worktrees
preserved. Existing tests change only bounded dispatch and old-guard fixtures.
P12 In Progress until actual integration and post-merge acceptance. Next M2
catalog P13(3A) has real P06/P07 prerequisites but needs its own extraction/
evaluation/path decisions and earlier exits for automatic selection or a separately
explicit independent assignment. All remaining scope stays required; no next task
started.


### P12 pre-integration results — 2026-11-02

Final combined Windows candidate full backend407 run:406 PASS/1 existing SKIP
(creating symlinks unavailable on this platform/account),396.205s. Focused43
P12/dispatch PASS, P12 contributes29. No runtime changes after full matrix.
Frontend48 PASS; coordination122 PASS; verifier PASS (27 operations/126 tasks/
39 capabilities). OpenAPI lint/bundle PASS with existing missing-license warning;
fresh generated declarations compile; frontend API freshness/typecheck/build PASS;
DESIGN0errors/0warnings PASS; real I00 HTTP intake/audit/hash/original/actor/error
smoke PASS; pip check/whitespace/protected-path guards PASS. CPython3.14.8/
SQLite3.50.4/jsonschema4.25.1/Node22.23.3/npm12.2.0. Exact commands, synthetic inputs/
outputs/failures and disclosed controls/untested limits above remain applicable.
P12 In Progress until authorized integration and post-merge acceptance; hosted CI
not yet claimed. Full scope/additions preserved; no next task started.


### P12 integrated acceptance — 2026-11-02

User-authorized task commit **e46a7a8361f971d9f27527e3516d7b3bfddfe590** pushed to
feat/p12-transaction-csv. Clean shared docs/coordination-foundation stayed at
verified base and merged without conflicts at
**c1165793cb791fe0e7eccaded43e7c8daa6ee498**. On that exact merge:29 focused P12
PASS including actual Uvicorn HTTP/private SQL, exact signed/zero/128-character
decimal strings, source/account participants and old-version upgrade; coordination
verifier PASS; real I00 intake/audit/hash/original/actor/error smoke PASS. Full407
matrix above remains valid; no runtime changes after it. Final whitespace/
protected-path guards PASS. Entire FEATURE_SCOPE/additions/spec/frontend/M1 tables/
dependencies/old parsers/normalizer/source-read APIs unchanged; original dirty
checkout and other worktrees preserved. Existing tests change only approved
bounded dispatch expectations and P07/P11 old-version fixtures.

P12 Complete after actual prerequisite integration and merged acceptance;
supersedes pending status. Existing Windows symlink skip and synthetic/scheduler/
registry/verifier/participant/SQL/old-guard/Decimal-context controls plus live-bank/
production-auth/model/UI/graph/performance/power-loss limits remain disclosed.
Hosted CI not yet claimed at this recording point. Independent row closes neither
earlier checkpoints nor3A/I04. Next M2 catalog P13(3A) has actual P06/P07 but needs
its own agreed text extraction/evaluation/file handoff; automatic selection awaits
earlier exits, or earlier independent work must be separately explicitly assigned.
P13B and every remaining modality/initial feature/approved addition stay required.
No next task started; full scope preserved.

### U05C verification — 2026-11-03

**U05C / Checkpoint 1B / M4 JebasJ / In Progress pending review/publication.**
Branch `feat/u05c-start-processing-ui`; initial tree clean. Actual HEAD and local
`docs/coordination-foundation` base are **747d223b1b04d134edaea6384e0c3cfcb1b40c5e**.
The supplied full hash beginning 747d223 does not equal actual Git; the verified
commit is used throughout this assignment. Real U03
**c5c9b5a5aefff113db6592996da4af1c780d88df** and P04 merge
**f851dd11fd8f7e11140317cf44d022a9999044dd** are verified ancestors; current
publication/provenance/audit producers are present. No spec/backend/dependency or
out-of-scope file edits, and no stage/commit/push/merge.

Implemented `frontend/src/cases/StartProcessing.tsx` and
`frontend/src/cases/processingController.ts`, wired into the selected evidence
inspector. The existing generated typed client requires singular `header` and
`Idempotency-Key` spelling; this is used instead of the prompt's illustrative
`headers` object. Each explicit bodyless action generates a fresh UUID key, busy
state blocks repeated clicks, and accepted state retains the returned ProcessingRun
for U05 consumption. Context/shape checks reject foreign/malformed responses;
fixed safe errors never expose raw server messages. Abort/session guards suppress
late responses, including dispose/reconnect. No optimistic run or completion state
is invented; the UI labels the status as the value at acceptance.

| Actual command/check | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | PASS |
| `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` | PASS; existing missing-license warning only |
| `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-u05c-api.d.ts` and `frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-u05c-api.d.ts` | PASS generated declaration and strict compilation |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | PASS: 27 operations, 126 tasks and all coordination checks |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | PASS: 122 tests |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v` | PASS: 420 tests, no skips |
| `npm --prefix frontend run test` | PASS: 55 tests, including seven U05C tests; prior 48 preserved |
| `npm --prefix frontend run build` | PASS: generated declaration freshness, TypeScript and production bundle |
| `node frontend/test/cases.integration.mjs` | PASS: real local HTTP/FastAPI/SQLite; U05C start/read-back/repeat/errors and prior I00 create/list/upload/download/hash/audit/isolation regressions |
| `npx --yes @google/design.md@0.4.0 lint DESIGN.md` | PASS: zero errors/warnings |
| `git diff --check` | PASS |

Python verification commands above used `PYTHONPATH=/tmp/evora-u05c-validation`:
`python -m pip install --target /tmp/evora-u05c-validation jsonschema==4.25.1`
installed the required validator outside the repository, without modifying package
manifests or the global installation. The host has jsonschema 4.26.0; isolated
4.25.1 was used for coordination/backend validation. pip printed host-package
resolver notices; the target install exited successfully. Local runtime read-back:
Python **3.14.9**, Node **22.23.4**, npm **12.2.1**, FastAPI **0.162.0**, Starlette
**1.10.0**, uvicorn **0.54.0**. These differ from the setup baseline's Python
3.14.8/Node 22.23.3/npm 12.2.0/FastAPI 0.143.1/Starlette 1.8.0. This is actual
Linux candidate verification, not clean pinned setup, Windows or remote CI proof.

Unit tests use explicit Fetch doubles and static React rendering. They invoke the
button's dispatch handler and controller, check disabled/alert markup, keys,
accepted run IDs/status, safe 400/401/404/409/415/server/network errors and retries,
authentication reset, foreign/malformed response rejection, late success/error
suppression on disposal/session change, and effect-style dispose/reconnect.
They do not mount a browser or certify visual/keyboard/accessibility behavior.

The real smoke uploads committed permitted `fixtures/synthetic-case/network.csv`
through U03, starts through the actual U05C controller/generated client and asserts
POST **202**, exact case/evidence association and initial **queued** status. It
reads the same run back through the spec's `getProcessingRun` path with bounded
harness-only polling and observes **completed** from the real producer. Another explicit action yields a different
run ID. Empty key **400**, missing/foreign evidence **404** and invalid identity
**401** are exercised; prior invalid-token case-list regression remains included.
The test-only SQLite/file snapshots and synthetic identities are harness controls;
application code remains API-only. Own temporary files are cleaned up.

U05C is locally implemented and verified, awaiting authorized review/publication.
U05 remains the next separately assigned task for polling; no polling/history UI
is claimed here. Aborting client delivery does not cancel accepted server work;
unknown transport failure is labeled uncertain and a new action can create a new
run. Checkpoint 1B/I00B and the full proposal remain open.

### U05 verification — 2026-11-03

**U05 / Checkpoint 1B / M4 JebasJ / In Progress pending review/publication.**
User-assigned branch `feat/u05-processing-status-ui` began clean at actual HEAD
and local `docs/coordination-foundation` base
**f6d5c17f1f23d17048bd9b582e1f64d20ce27c1a**. The supplied full hash differs;
the actual reviewed Git commit is recorded here. Real U05C merge at that commit
(task **d7e9ecfed43f8a3f4f21fef219b1190560302c0d**) and P04 merge
**f851dd11fd8f7e11140317cf44d022a9999044dd** are committed ancestors.
Current publication/private provenance/audit producers remain integrated.
Only allowed frontend and documentation paths changed. No spec/backend/package
dependency edits or stage/commit/push/merge.

`frontend/src/cases/ProcessingStatus.tsx` and
`frontend/src/cases/processingStatusController.ts` consume the accepted U05C run.
Generated-client GET requests use the exact case/evidence/run selector, immediately
then serially 750 ms after each nonterminal success. Completed/failed stops the
loop. Actual API status, created/finished time and processor version display
without local estimates; failed diagnostics render escaped text. Invalid or
foreign successful payloads never replace the last valid run. Network/server/
protocol failures pause with an explicit same-run retry and stale-value wording;
404 stops with a safe alert; 401 clears the shared token and status data. Timers
and requests cancel on disposal/session changes; stale deliveries are discarded,
including dispose/reconnect. Client abort does not cancel server processing.

Unit tests in `frontend/test/processing-status.test.mjs` use declared synthetic
Fetch doubles, Node mock timers and React static rendering. They cover queued →
running → completed, running → failed with escaped MALFORMED_CSV diagnostic,
terminal stop, 401/404/network/500, same-run retry button dispatch, scheduled and
in-flight disposal, session replacement, late success/error after reconnect,
nonoverlap, malformed/context mismatches and an initially terminal run. These
are controller/static-render checks, not mounted browser/effect, visual, keyboard,
accessibility or Windows proof. Node emits its experimental MockTimers warning.
Prior U05C tests now render the status component inside the shared API provider
and check the new last-reported wording; prior action/error/race coverage remains.

The real local HTTP/FastAPI/SQLite smoke uploads permitted synthetic network.csv,
starts through U05C, then polls via the actual U05 status controller with a 10 ms
test interval. It verifies exact run/case/evidence/version, completed status,
finished_at and all fields against a repeated API read; terminal state issues no
further GET. A nonexistent UUID run, mismatched case and foreign actor return 404.
Earlier intake/create/pagination/upload/download/hash/audit/auth/error regression
checks remain included. No backend producer is doubled here. Test-only SQL/file
snapshots and synthetic identities are harness controls; application code uses
only HTTP. Harness-owned temporary storage is removed. All four status transitions
are deterministic unit coverage; live HTTP timing need not expose running before
completion. No run-history/observation view or I00B checkpoint closure is claimed.

Python checks use `PYTHONPATH=/tmp/evora-u05c-validation`, the existing isolated
validator directory, read back as **jsonschema 4.25.1** (host version 4.26.0).
No dependency installation or package-manifest changes were needed. Actual Linux
runtime: Python **3.14.9**, SQLite **3.54.1**, Node **22.23.4**, npm **12.2.1**,
FastAPI **0.162.0**, Starlette **1.10.0**, uvicorn **0.54.0**. These differ from
the pinned setup baseline; this is local candidate verification, not clean pinned
setup, Windows or remote CI certification.

| Actual command/check | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | PASS |
| `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` | PASS; existing missing-license warning only |
| `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-u05-api.d.ts` and `frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-u05-api.d.ts` | PASS |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | PASS: 27 operations, 126 tasks |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | PASS: 122 tests |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v` | PASS: 420 tests, no skips |
| `npm --prefix frontend run test` | PASS: 66 tests, including 11 U05 tests; prior 55 preserved |
| `npm --prefix frontend run build` | PASS: generated declaration freshness, TypeScript, production bundle |
| `node frontend/test/cases.integration.mjs` | PASS: real status controller and existing intake/start/download/audit/auth regressions |
| `npx --yes @google/design.md@0.4.0 lint DESIGN.md` | PASS: zero errors/warnings |
| `git diff --check` | PASS after final documentation read-back |

U05 remains local pending review/publication. Checkpoint 1B/I00B and full proposal/
approved additions remain open. Next bounded M4 row U05B requires its own handoff;
no next task started and no module-complete claim.
### P13 independent verification — 2026-11-03

The task started from verified shared base `6980b4d` and incorporated `f6d5c17`
with F08 processing audit and U05C before acceptance. The combined frontend
suite passed all 55 tests. API declaration freshness, typecheck, frontend
build, real I00/U05C HTTP smoke and all 122 coordination verifier tests passed.
Contract lint and bundling, fresh TypeScript declaration compilation and
design lint passed on the original base.

The eight focused tests use the actual pinned CPU model and a real local worker.
The synthetic evaluation checks exact span and type on eight labeled documents.
It found 13 true positives, two false positives and one miss, yielding 86.7%
precision, 92.9% recall and 89.7% F1. The false positives were `d-7` as a person
and the button label `May` as a date. The missed person mention was
`quinn sample`. This small synthetic evaluation measures neither live evidence
quality nor the separate I04 link and event criteria.

The suite exercises actual processing, SQLite, private provenance and source
reads. The failure controls inject a corrupt manifest and shortened deadline or
held queue lock. The history control seeds processor 4 via the real P07 parser
and publication code with version and scheduling overrides. The successful
inference path uses the installed model. P13B remains the separate text Event
task. Earlier checkpoint exits and the full agreed initial scope stay open.

The combined Windows backend run discovered 428 tests. It passed 427 with the existing Windows symlink skip. Cross-platform GitHub Actions verification is tracked on the shared integration commit.

P13 merged in c5647755b84a25fd4a976ee3207e0e32324de896 from task head 1d57842. All nine focused and document loopback tests passed on the merge, together with the coordination verifier and real I00/U05C smoke after rebuilding frontend test assets.


### U05B verification — 2026-11-03

**U05B / Checkpoint 1B / M4 JebasJ / In Progress pending review/publication and
full backend environment verification.** Clean starting branch
`feat/u05b-observation-inspector-ui` and local `docs/coordination-foundation` both
read back at **32b8adeecec8903edc1dde5ae56ad8a175a61607**; this actual Git commit
differs from the supplied full hash. Real U05 task
**50a5e9c4a36afc986f20200b2adfa28f1a938002** and P04B merge
**c29e517f218c0851a9959cfa389b093242a255ab** are confirmed ancestors. Assignment,
allowed paths and shared-document handoff are in AGENT_TASKS.md. No spec/backend/
package dependency edits, staging, commit, push, merge or fresh remote read-back.

Implemented the API-only selected-evidence observation inspector with exact
kind/source locator/raw/normalized/source time/UTC/confidence and output-run ID.
Unknown times display as not provided. Values render as escaped React text,
including hostile markup and preserved raw whitespace; confidence remains
separate from source reliability and conclusion uncertainty. Pagination uses
server total/limit/offset; no completed output and empty later pages are distinct.
Fixed alerts cover 400/401/404/500/network failures and retry the current page;
after 401 reopen an authorized session/reselect evidence. Session changes clear
values. Selection, optional run selector and completion-refresh changes dispose
the controller, abort in-flight requests and ignore stale delivery; the inspector
creates no timers. Existing U05 owns polling and terminal/disposal timer cleanup.
Completed-status callbacks refresh latest observations. Optional historical pin
captures that completed run and retains it across pages/newer completions.
Unpinned reads intentionally follow the existing per-request latest policy, so
concurrent reprocessing can change unpinned page membership; pin for stable pages.
No new contract choice or producer/consumer mismatch was needed.

Actual Linux environment: **Python 3.14.9, SQLite 3.54.1, Node v22.23.4,
npm 12.2.1**. The system jsonschema was 4.26.0; verification instead uses
`/tmp/evora-u05b-venv` created with `python -m venv --system-site-packages` and
installed **jsonschema 4.25.1**, without editing repository requirements. Pip
reported an inherited unrelated gns3-gui requirement for jsonschema >=4.26.0;
this is not a clean full-dependency setup claim. The committed P13 worker requires
Python 3.14.8 and exact spaCy 3.8.18/thinc 8.3.14/numpy 2.5.4/model 3.8.0.
The local environment lacks spaCy/model; the full suite therefore cannot certify
that producer here. Available alternate Python installations are 3.11/3.12,
not the pinned 3.14.8. No manifest weakening or synthetic model substitution.

| Actual command (repository root; temporary environment activated for Python checks) | Result |
|---|---|
| `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json` | PASS; requested unpinned invocation resolved Redocly 2.73.0 |
| `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` | PASS; existing missing info.license warning |
| `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-u05b-api.d.ts` and `frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-u05b-api.d.ts` | PASS |
| `python scripts/verify_coordination.py /tmp/evora-openapi.json` | PASS; 27 operations / 126 tasks / complete phase/DAG/link/scope checks |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` | PASS, **122 tests** |
| `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -v` | **428 run: 413 pass, 7 failures, 8 errors**; existing document/NLP model-unavailable paths and dependent old-adapter-history tests |
| Same Python flags with `-m unittest backend.tests.test_observations backend.tests.test_processing backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_m1_access backend.tests.test_validation -v` | PASS, **131 tests**; real current producers and prior intake/access/validation regressions |
| `npm --prefix frontend run test` | PASS, **79 tests**, including **13 U05B tests** |
| `npm --prefix frontend run build` | PASS; generated declaration freshness, TypeScript and bundle |
| `node frontend/test/cases.integration.mjs` | PASS; real FastAPI/SQLite/client/controller plus prior I00/U02/U02B/U03/U04/U05C/U05 smoke |
| `npx --yes @google/design.md@0.4.0 lint DESIGN.md` | PASS, 0 errors/warnings |
| `git diff --check` | PASS |

Unit coverage uses synthetic Fetch doubles, static React rendering and actual
panel pagination/retry handlers: source/raw/normalized/time/confidence and markup
escaping, server-authoritative totals/bounds, genuine empty versus later empty,
400/401/404/500/network failures, per-page historical selector, foreign response
rejection, request replacement, selection/disposal late success/error and session
change. No browser-mounted interaction, visual, screen-reader, Windows, hosted
CI or production identity verification is claimed.

Real integration uploads permitted `fixtures/synthetic-case/network.csv`, starts
and polls real merged P04, then reads six real P04B observations. Exact expected
locators/raw values: row 2 device_id D-7, ip_address 203.0.113.7, event connected;
row 3 device_id D-9, ip_address 203.0.113.9, event connected. Raw/normalized,
source/UTC time and confidence 0 match the producer. Pinned pages at offsets
0/2/4/6 preserve all six unique IDs/order and authoritative total; the actual
inspector controller reads the exact completed output. A newer real run completes:
default reads select it, while pinned historical output remains exactly equal.
Unprocessed evidence returns total 0. Invalid limit returns 400; missing run,
same-case mismatched evidence/run and foreign case return safe 404 ApiError.
Original byte/hash/private intake-audit regression remains green.

Baseline control: archived committed **32b8adeecec8903edc1dde5ae56ad8a175a61607**
to `/tmp/evora-u05b-base-32b8ade` using `git archive HEAD` (no repository backend
edits), then ran the same full backend command/environment there. It also ran
**428 tests with the identical 7 failure / 8 error test names**. All 15 failing
paths therefore reproduce on the unchanged task base; the candidate introduces
no additional backend failures in this environment. This does not make the
required full backend regression green.

No checkpoint completion is claimed. Full backend model-runtime verification
remains unavailable locally; Checkpoint 1B still needs U13 and real joint I00B
exit evidence under their own bounded handoffs. Full initial proposal/additions
remain required; this session starts no next task.

### U13 verification — 2026-11-03

Task **U13 / Checkpoint 1B / M4 JebasJ**, local branch
`feat/u13-case-evidence-overview`, actual clean initial common base
**138fd791808571c60ee7dc5ef831684c84d09d67**. This is the actual local
coordination head; the supplied full hash differs. Dependency hashes, allowed
paths and explicit shared-doc handoff are in AGENT_TASKS.md. No contract,
backend or package dependency changes; no staging/commit/push/merge.

Implemented all-page evidence aggregation, same-case/unique-ID/page-total
checks, serial per-item processing histories, latest attempt by the specified
oldest-first list order, all kind/status counts and zero-item messaging.
401 uses shared-client session clearing; 404 and network errors expose fixed
safe alerts. Refresh retries all reads; no partial totals survive failure.
Abort/generation/session guards discard late responses on replacement/disposal.

Executed checks:

- `npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json`: PASS.
- `python scripts/verify_coordination.py /tmp/evora-openapi.json`: PASS,
  27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 mappings.
- `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'`:
  122 PASS (system jsonschema 4.26.0); pinned 4.25.1 rerun recorded below.
- `npm --prefix frontend run test`: 101 PASS, including 22 new U13 tests.
- `npm --prefix frontend run build`: PASS, generated client freshness,
  TypeScript compilation and bundle.
- `node frontend/test/cases.integration.mjs`: PASS through real FastAPI/SQLite
  and generated client; prior I00/U02/U02B/U03/U04/U05C/U05/U05B checks pass.
  U13 uploads 23 items across two evidence pages: document 1, image 20,
  network_log 2, all other kinds 0; completed 1, unprocessed 22, other statuses
  0. Completed state uses the real network parser and processing lifecycle;
  empty case has total 0. No SQL processing/output doubles.
- `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml`: PASS with existing
  missing-license warning. DESIGN 0.4.0 lint: PASS, zero errors/warnings.

Unit tests use synthetic Fetch responses and static React rendering. They cover
all status buckets, newer attempts superseding older completions, multi-page
counts, zero evidence, invalid/foreign/duplicate/inconsistent responses,
401/404/network failures at case/page/history stages, retries, session changes,
request replacement and selection/unmount disposal at each request stage.
No browser-mounted visual/accessibility or new Windows verification is claimed.
Counts are live at selection/explicit refresh, not an atomic analysis snapshot;
concurrent evidence total changes require retry. Sequential history reads can be
slow for large cases. I00B runbook exit remains required; 1B stays open.

Additional verification: installed jsonschema **4.25.1** into isolated
`/tmp/evora-u13-validation` (no repository dependency change) and reran all
122 coordination tests with `PYTHONPATH=/tmp/evora-u13-validation` and the same
EVORA_CONTRACT_BUNDLE: PASS. Fresh openapi-typescript 7.10.1 declarations in
`/tmp/evora-u13-api.d.ts` compile with TypeScript 5.9.3 `--strict --noEmit`.
Final edited-doc coordination verifier and `git diff --check`: PASS.
An extra backend regression attempt initially omitted EVORA_CONTRACT_BUNDLE;
its missing-environment errors are not product verification. Corrected rerun
results are recorded below.

Corrected extra backend regression:
`PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests`
ran 428 tests: **7 failures, 8 errors** (413 passed). Failures/errors occur in
unmodified document/text-entity and old adapter history tests; the explicit
local model error is `MODEL_UNAVAILABLE` / `NLP_MODEL_UNAVAILABLE`, with expected
completed outputs consequently absent and the corruption test seeing unavailable
rather than invalid. Full backend regression is therefore **not green** in this
environment; no model installation or baseline comparison was performed.
This does not replace the passing requested U13/I00 real HTTP integration.
No checkpoint/main promotion is claimed. Final frontend rerun: 101 PASS,
build PASS, real HTTP integration PASS, whitespace PASS.


### I00B verification — 2026-11-03

**I00B / Checkpoint 1B / joint integration coordination / whale2186.** Clean
initial branch `feat/i00b-processing-inspection-gate`; actual reviewed common
contract/base **1517b4d9479e2062ce2c85cb380fe43d7b512aa6**, matching local
`docs/coordination-foundation`. The supplied full hash differs from the Git
object; no base was silently substituted. All 17 integration commits in the
I00B live-record table were checked with `git merge-base --is-ancestor` and pass.
I00/earlier foundations are inherited integrated producers. Sole HTTP authority
remains unchanged draft 0.3.0; runbook is INTEGRATION.md. Assignment and exact
five-path shared-file handoff are in AGENT_TASKS.md. No spec, backend, package
dependency or implementation outside the smoke changed.

Real HTTP/FastAPI/SQLite smoke now checks four network candidates including
`device:D-7`/`device:D-9`, two row/time events, nonempty unique observation IDs,
same-case Evidence links and source joins to the completed run. Event participant
IDs resolve to returned entities. `listAuditEvents` returns exactly one first-run
`startProcessing` event for investigator-2 and the source Evidence, with
`created_at == finished_at` and exact safe `run:...;status:completed;version:...`
reason. Repeat audit reads preserve SQL records/original hashes. Actor 1 gets
the same 404 ApiError for foreign and missing entity/event cases. A separate GPS
case exercises actual UI upload/start/status/observation controllers and real
candidate APIs: D-8, three exact raw/normalized device/latitude/longitude values,
row locators and source UTC. Both use committed permitted synthetic fixtures.
Network historical pin remains unchanged after a new run; U13's network case
retains 23-item/two-page kinds/latest-status counts and an honest empty case.
The final success marker appears only after all prior I00 and current checks.

Observed local runtime: Node **22.23.4**, npm **12.2.1**, Python **3.14.9**,
SQLite **3.54.1**, FastAPI **0.162.0**, Starlette **1.10.0**, Pydantic
**2.14.2**, Uvicorn **0.54.0**, HTTPX **0.28.1**. These installed versions
were read back, not inferred from requirements. They differ from the pinned
setup baseline; no clean pinned setup or new Windows compatibility claim is
made. The required jsonschema **4.25.1** was read back from the existing scratch
install and used for the pinned coordination and 327 checkpoint regressions.

Executed required sequence (all PASS):

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
npm --prefix frontend run test
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
git diff --check
```

- Verifier: 27 operations, 126 tasks, 18 checkpoints, 39 capabilities and all
  40 proposal mappings; docs/links/membership/dependency checks pass.
- Coordination suite: 122 pass with system jsonschema 4.26.0, then 122 pass
  with required **4.25.1**, using existing isolated scratch install:
  `PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'`.
- Frontend: 101 pass, zero skipped; build includes generated API freshness,
  TypeScript typecheck and real UI assets. Real smoke exits zero and prints
  `PASS I00B verified first network/GPS processing and source inspection gate.`
- `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml`: pass, existing
  missing-license warning only. `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-i00b-api.d.ts`
  and `frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-i00b-api.d.ts`:
  pass. `npx --yes @google/design.md@0.4.0 lint DESIGN.md`: zero errors/warnings.

Checkpoint regression command (all **327 pass**, no skips):

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```

These exercise earlier 0/1A capabilities and every 1B producer: network/GPS
positive/negative source parsing, real localhost processing and candidate APIs,
private SQL provenance versions/inputs/output manifests/digest/time, immutable
history, selectors/pagination/case isolation, malformed/wrong-layout/unsupported
and limits, same-key replay/conflict/new-key retry, failed-output isolation,
verified atomic publication, concurrent keys, startup recovery and actual child
process hard-exit rollback/durability. SQL corruption, deliberate write failures,
held scheduling and synthetic historical selection records are labeled negative
test fixtures; they are not claimed as unmodified production failures. Private
provenance is verified internally, never exposed as a new HTTP field. Frontend
unit Fetch doubles/static rendering prove failure/race behavior separately from
the real HTTP controller smoke. No browser mount, native disk-save, new Windows,
clean install, hosted CI, OS power-loss, graph or scoring proof is claimed.

Additional full backend attempt:
`EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests`
ran **428: 413 passed, 7 failures, 8 errors**. Failures/errors are in
`test_documents`, `test_text_entities`, and document-dependent upgrade-history
checks in `test_mobile`/`test_transactions`; the local model reports
`MODEL_UNAVAILABLE` / `NLP_MODEL_UNAVAILABLE`, causing expected completed outputs
to be absent and the invalid-model test to see unavailable instead. This matches
the earlier U13 result on the unchanged backend. No backend/model repair or
installation was made within I00B. The full suite is explicitly **not green**;
its later independent adapter acceptance/CI needs a separate environment/task
handoff. These tests belong to later checkpoints; all 327 regressions covering
0/1A/1B pass. Checkpoint completion is scoped to the runbook's 1B membership,
not approval to promote a candidate with failing full CI.

**Checkpoint 1B is Complete; Checkpoint 1C is unblocked and active**, with all
18 exact member IDs preserved in ROADMAP.md. Next dependency-ready scopes are
G01D and G02 under their own explicit handoffs; no implementation task was
started by changing checkpoint state. No unresolved choice affects this gate;
C-05 remains for G02/M3 factor policy and M4 explanations. All changes remain
uncommitted; no staging/push/merge or merged-commit smoke is claimed. Full
proposal and approved speech addition remain required; no module/phase closure.

### A02 verification — 2026-11-03

**A02 / Checkpoint 1C / M3 / whale2186** on
`feat/a02-candidate-link-rule`, actual reviewed clean common contract/base
**11961c4ab4c1167e1d0ad8c83fe52440b2466a9a**, matching local
`docs/coordination-foundation`. The prompt's different full hash is not a local
Git object. Real A01 task **16e6429a22fa6250fdeebc4c47f6ab0a4d0349bf** is
merged at HEAD, with G02 merge **d1f16ef02a62c2ce94bdd19539037a7b60cecabf**
and all 1B/I00B producers as ancestors. Six user-authorized paths only; unchanged
OpenAPI draft 0.3.0; no dependency/frontend/spec edits. Records retain the
requested handoff date; commands were executed locally on 2026-11-04.

Implementation read-back: frozen GraphEdge/Finding values serialize exact
contract fields, retain source Entity UUID endpoints and unique sorted source
references, with deterministic case/run/rule/endpoint UUIDv5 IDs and output
ordering. Exact P03B keys preserve namespace/spelling/case; no speculative
identity normalization. Missing or foreign sources, empty/duplicate/forged joins,
conflicting record IDs and mixed processing-run selections fail atomically.
Confidence 0 is unassessed association, not probability/reliability/extraction
confidence. Candidate summaries disclose verification and identity/guilt limits.

Resolved review discrepancy: `candidate_match` is absent from the sole
FindingKind enum. Output uses `relationship` with rule
`candidate_link_shared_identifier:v1`; strict negative tests reject the requested
invalid enum. Producer/consumer impact is recorded in the A02 assignment review
queue. The original GPS fixture contains only D-8; original network/GPS remain
an explicit no-match control. A labeled in-test GPS variant adds D-7 and retains
D-8 for the positive case. No fixture or contract was changed.

Requested sequence, all exit zero:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_links.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
git diff --check
```

Results: **13 A02**, **19 A01**, **33 G02**, **122 coordination** and
**101 frontend** tests pass, no skips. Verifier confirms 27 operations, 126 tasks,
18 checkpoints, 39 capabilities and all 40 proposal mappings. Initial system
jsonschema was 4.26.0; required **4.25.1** was independently read back from the
existing scratch path and used successfully for the repeated coordination suite
and all 65 A02/A01/G02 tests:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_graph_links backend.tests.test_graph_nodes backend.tests.test_triage_policy
```

Real merged producer acceptance uses FastAPI ASGITransport, temporary SQLite and
private original storage: upload synthetic network and labeled GPS variant,
start/poll both real processing runs to completed, read complete Evidence/Entity/
Event/Observation pages, build A01 source nodes, derive exactly one D-7 edge and
finding, and resolve each cited observation's exact row/device column back to
original bytes. Both Evidence items are cited, endpoints exist among A01 nodes,
D-9/D-8 remain unlinked, repeat derivation and original downloads stay unchanged.
Two-actor foreign-case API reads return 404; injected foreign Entity/Observation
records raise ValueError. Unit negatives use parser-derived records plus labeled
mutations; they are separate from this real producer integration. Schema checks
use the actual bundle with Draft202012Validator/FormatChecker, required-field,
extra-field, UUID, enum, range, empty-array and duplicate-reference negatives.

Earlier completed checkpoint regressions: **327 tests pass, no skips**, using:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```

Additional checks all pass:

```sh
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-a02-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-a02-api.d.ts
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
npx --yes @google/design.md@0.4.0 lint DESIGN.md
```

OpenAPI retains its existing missing-license warning only; DESIGN has zero
errors/warnings. Frontend build verifies generated API freshness and application
TypeScript. Real localhost UI/API smoke passes I00/I00B and existing create/list/
upload/download/hash/audit/process/poll/source-inspection/overview/isolation.
Local runtime: CPython **3.14.9**, Node **22.23.4**, npm **12.2.1**. No clean
installation, Windows, browser mount, hosted CI or model/benchmark claim.
The later-adapter full backend suite was not rerun; previously documented NLP
model failures remain outside this task and are not claimed repaired.

A02 is locally verified, **In Progress pending review/publication**. Analysis UUIDs
in focused tests are explicitly unpersisted; A01B/A05 must supply SQL/Neo4j
partitioning, frozen inputs, coherent publication and lifecycle. Caller must
authorize and select inputs, with A01 checking the complete Evidence allowlist;
nonempty entity input without observations is rejected. No completed analysis
or I01/checkpoint/module closure is claimed. Next bounded handoff is A03 or A03B.
No staging, commit, push or merge was authorized or performed.


### A03 verification — 2026-11-03

**A03 / Checkpoint 1C / M3 / whale2186**, locally implemented on
`feat/a03-relevance-factor`, In Progress pending review/publication. Clean actual
starting HEAD/common contract/base is
**51ee2ed3432b8956cf3af9ebd410a04483e917d7**, matching the coordination ref;
the user-supplied full hash differs. Exact committed G02/A02/A01/1B dependency
versions and allowed shared paths are in A03 assignment in AGENT_TASKS.md.
The requested record date is retained; execution occurred 2026-11-04 local time.
Spec draft 0.3.0, frontend, dependencies and fixture bytes are unchanged.

The builder uses G02's exact ratio float, deduplicates exact namespaced keys,
intersects target with known keys, defaults to weight 0.25 and rounds only the
contribution to two decimal places. Sorted keys/counts explain the factor with
one canonical target Evidence citation. Missing known inputs, empty known set,
unevaluated target or target without observations is absent. An evaluated zero
retains a factor. Weights reject booleans, NaN, infinity and out-of-range inputs.
A01 validates case/Evidence/source UUID ownership; A03 checks source locators,
entity-to-observation keys/Evidence joins, unique citations, conflicting entity
UUIDs and selected processing-run consistency before any absent return.

Executed commands (Python validation uses the existing scratch installation;
no repository dependency edits or installs):

```sh
export PYTHONPATH=/tmp/evora-u13-validation
python -c "import importlib.metadata as m; print(m.version('jsonschema'))"
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_relevance_factor.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_links.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-a03-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-a03-api.d.ts
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
npx --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

Results: **14 A03, 13 A02, 19 A01, 33 G02, 122 coordination and 101 frontend
tests pass**, no skips. Strict real-bundle Draft202012Validator/FormatChecker
checks cover output and required-field/extra-field/name/type/range/UUID/duplicate
source negatives. Verifier checks 27 operations, 126 tasks, 18 checkpoints,
39 capabilities and all 40 proposal mappings. jsonschema **4.25.1** was read
back and used; system jsonschema is 4.26.0. OpenAPI lint passes with its existing
missing-license warning; DESIGN has zero errors/warnings. Generated strict
TypeScript, frontend API freshness/typecheck/build and whitespace checks pass.

Real merged producer acceptance uses FastAPI ASGITransport, temporary SQLite and
private original storage, without producer doubles: upload committed synthetic
network.csv and labeled GPS D-7/D-8 variant, start/poll completed processing,
read complete Evidence/Entity/Observation pages, derive A02's one candidate
link/finding, calculate network relevance **4/5 = 0.8** and GPS **2/5 = 0.4**.
Network includes candidate D-7, D-9 and two IPs; GPS adds D-8 while D-7 is
counted once. Resolve each matched entity through source Observation IDs and
exact row locators to original bytes. Repeated calculations, source dictionaries
and original downloads remain unchanged; foreign-actor Evidence read is 404.
Unit tests separately use real parsers/projectors and labeled mutations for
foreign/missing/forged sources, partial/full/zero, weight limits, absent data,
duplicates/order/generators, exact namespace/case/spacing and confidence controls.
G02 aggregation read-back proves the standalone factor's value yields weight 1
and score 80 when it is the only available factor; no-observation input stays
unscored. No extraction confidence or count boost is introduced.

Earlier completed checkpoint regressions: **327 tests pass**, no skips:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```

Real localhost UI/API smoke passes I00/I00B with upload/download/hash/audit,
network/GPS processing/poll/source inspection, paginated overview and actor
isolation. Local runtime: CPython **3.14.9**, Node **22.23.4**, npm **12.2.1**.
No Windows, clean installation, hosted CI, browser-mount or benchmark claim.
Later NLP adapter suites were not rerun; existing documented model limitations
remain outside A03. This is a pure internal factor, not an HTTP endpoint;
HTTP 400 mapping remains covered by existing validation regressions.

Internal handoff: callers must authorize case access and supply the complete
coherent selected known entity set, Evidence allowlist and observations. Bare
labels and keyless source observations fail closed; current P03B producers
satisfy the boundary. A04 must aggregate raw values through G02 normalized
weights. A05 owns frozen input selection; A01B/A05 own SQL/Neo4j persistence and
coherent publication. Real completed-analysis publication and I01 are not
claimed. Checkpoint 1C and M3 remain open. Next bounded handoff is A03B, then
A04 once dependency-ready. Changes remain unstaged/uncommitted; no commit,
push or merge was authorized or performed.

### A03B verification — 2026-11-03

**A03B / Checkpoint 1C / M3 / whale2186**, locally implemented on clean assigned
`feat/a03b-connectivity-factor`, In Progress pending review/publication. Actual
reviewed common contract/base **ec4ab3c153961c416785348edd73eb5f6ed4bd68**
matches local coordination ref; supplied
`ec4ab3c5c9ee2c6ebfd6e082878bf893e364024b` is not a local Git object.
Exact merged G02/A02/A01/A03 dependency task versions, allowed shared paths and
resolved internal handoff are in A03B assignment in AGENT_TASKS.md. Requested
date retained; commands ran 2026-11-04. No spec/frontend/dependency edits.

Read-back: G02 computes `min(len(unique_external_neighbor_ids) / 10, 1.0)`.
Target nodes are those citing target Evidence in the complete selected A01
node collection. Edges are undirected for degree; self/internal/parallel links
and repeated mentions do not boost it. Only contribution is rounded, with
bounded finite weight (standalone default 0.20). Explanations state the actual
candidate neighbor count and attention limits; unique sorted Evidence citations
union target, incident edges and neighbor nodes. Unknown/zero observation count
or None graph inputs stays absent; evaluated zero stays 0.0. Validation precedes
absent returns, checking canonical UUIDs, cases, nonempty unique source arrays,
edge confidence, conflicting IDs, endpoint resolution when nodes are available,
and target support on incident links. No scores feed topology.

Requested sequence executed successfully (Python commands use the pre-existing
scratch jsonschema **4.25.1**, independently read back; no install or repository
dependency change):

```sh
export PYTHONPATH=/tmp/evora-u13-validation
python -c "import importlib.metadata as m; print(m.version('jsonschema'))"
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_connectivity_factor.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_relevance_factor.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_links.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
git diff --check
```

Results: **14 A03B, 14 A03, 13 A02, 19 A01, 33 G02, 122 coordination and 101
frontend tests pass**, no skips. Verifier checks 27 operations, 126 tasks,
18 checkpoints, 39 capabilities and all 40 proposal mappings. Actual bundled
Draft202012Validator/FormatChecker validates every non-absent test result and
rejects missing/extra fields, invalid name/ranges/types/UUIDs/duplicate citations.
Unit controls cover 1/2/9/10/15 neighbors, distinct node versus Evidence counts,
multiple target nodes, reverse/self/internal/unrelated links, duplicates/order/
generators, immutable inputs/results, missing graph/observations, evaluated zero,
weights/count negatives, foreign cases including absent paths, dangling/forged
links and conflicts. G02 read-back normalizes a sole connectivity value 0.1 to
weight 1 and score 10; confidence and observation repetition do not affect it.

Real producer acceptance uses temporary SQLite/private original storage and
FastAPI ASGITransport with synthetic identities, without producer doubles:
upload committed network.csv and labeled in-test GPS D-7/D-8 variant, start/poll
both real processing runs to completed, read complete Evidence/Entity/Event/
Observation pages, build real A01 nodes and derive the real A02 candidate link.
Both targets produce value 0.1/contribution 2.0, citing both Evidence items.
Each edge Observation resolves to the same-case source device_id row containing
D-7 in original bytes. Producer-value and wire-mapping calculations agree;
repeat results, inputs and original downloads remain unchanged. Foreign actor
Evidence reads return 404. Analysis UUID is explicitly unpersisted: no completed
analysis, Neo4j partition or publication proof is claimed.

Additional shared checks pass:

```sh
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-a03b-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-a03b-api.d.ts
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
npx --yes @google/design.md@0.4.0 lint DESIGN.md
```

OpenAPI retains its existing missing-license warning only; DESIGN has zero
errors/warnings. Generated declarations compile strictly; frontend build checks
API freshness and TypeScript. Real localhost I00/I00B smoke passes original
upload/download/hash/audit, network/GPS process/poll/source inspection, paginated
overview and actor isolation. Local Python **3.14.9**; jsonschema **4.25.1** via
scratch path. No clean install, Windows, hosted CI, browser mount or benchmark
claim. The full later-adapter backend suite was not rerun; previously documented
NLP model limitations are outside A03B and are not claimed repaired.


Earlier completed-checkpoint backend regressions: **327 pass**, no skips:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```

Caller contract: authorize case access, supply coherent frozen full A01/A02
inputs and target observation count, and retain source ownership/locator checks
in those real producers. This signature cannot independently verify private
Evidence/Observation joins or establish a caller-supplied observation count.
A04 consumes raw factors through G02 normalized aggregation; A05/A01B own
snapshot selection, SQL/Neo4j persistence and coherent publication. No unresolved
A03B wire/policy gate. Checkpoint 1C/I01 and M3 stay open; next bounded handoff is
A04 when dependency-ready. Changes remain unstaged/uncommitted; no commit, push
or merge was authorized or performed.

### A04 verification — 2026-11-03

**A04 / Checkpoint 1C / M3 whale2186 / local acceptance verified, pending review
and publication.** Execution date 2026-11-04. Clean starting branch
`feat/a04-factor-aggregation-triage`; actual reviewed common contract/base
**2eca04b5634302b3c85e7e05e0ac7c48bc37e742** matches the local coordination
ref. The supplied full hash differs. Real A03B task
**bdba3065dda83f1d801c63af92da8966952fe6e6**, A03 task
**c9a36eaf5f59e15c577ae69a33b2875208e85848** and G02 task
**01daaed0cf1c2a95d443c01d6f459ce0d76f2fac**, plus A01/A02 and completed
1B/I00B, are ancestors. Unchanged OpenAPI draft 0.3.0 remains authoritative.
Assignment and explicit shared-document handoff are in AGENT_TASKS.md.

Implementation delegates all scoring to G02, recomputes producer weights and
contributions, preserves evaluated zero, and returns None for zero observations
or no available factors. Target/source evidence is checked against the authorized
same-case set even when unscored. Results have deterministic policy/case/run/
evidence UUIDv5 identity and UTC timestamp, without adding wire fields. A05 must
record the policy version and preserve accepted timestamps/results on replay.
Sorting emits complete frozen TriageEntry membership before pagination, ordered
by computed score descending then UUID, with unscored UUIDs last. It rejects
mixed case/run, duplicate and out-of-membership results without altering inputs.

Internal handoffs resolved in code and `backend/README.md`: unnamed FactorValue
objects cannot identify their factor. Use real producer dictionaries or a named
FactorValue/None mapping. Sorting uses TriageEntry wrappers so missing results
stay absent. These are internal interfaces, not HTTP contract changes. No
unresolved A04 gate; A05/A06 retain authorization, snapshot selection, persistence,
publication, history, override and pagination responsibilities.

All requested commands pass. Python commands below ran with
`PYTHONPATH=/tmp/evora-u13-validation`, the existing isolated jsonschema **4.25.1**
installation (system is 4.26.0); no dependency files changed.

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_aggregation.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_connectivity_factor.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_relevance_factor.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_links.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_graph_nodes.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests -p 'test_triage_policy.py' -v
npm --prefix frontend run test
git diff --check
```

Results: **122 coordination tests**, **12 A04 tests**, **14 connectivity**,
**14 relevance**, **13 links**, **19 nodes**, **33 G02 policy** and **101 frontend
tests** pass, no skips. Unit controls cover normalization, every priority band
boundary, rounding crossing a band, evaluated zero versus absent, explicit
additional available factors and the preserved 100.01 contribution sum capped
to 100.00. They cover deterministic identity/time, generators/input immutability,
invalid counts/UUIDs/factors/timestamps, foreign target/source on unscored paths,
canonical G02 golden order, complete unscored membership and mixed-run rejection.
Actual bundled TriageResult and TriageEntry schemas are used, including unknown
field/missing field negatives. First run exposed jsonschema silently skipping
`date-time` without its optional RFC3339 dependency. The A04 tests now explicitly
register a standard-library UTC timestamp format check alongside UUID checking;
all tests pass with no new packages.

Real producer acceptance uses temporary SQLite/private originals and FastAPI
ASGITransport with synthetic auth identities; no processing/graph/factor doubles.
Both committed network.csv and gps.csv upload, start/poll completed processing,
and read complete Evidence/Entity/Event/Observation pages. A01 builds nodes;
A02 correctly yields no initial cross-device link; relevance values .8/.2 and
evaluated connectivity zero aggregate to **44.44/P3** and **11.11/P4**. A separate
labeled synthetic GPS variant adds D-7 without modifying fixture files, derives
one real candidate edge/finding, gives relevance .8/.4 and connectivity .1/.1,
and aggregates to **48.88/P3** and **26.66/P4**. Every Observation locator resolves
to its original row/raw value, original bytes download unchanged, foreign actor
reads return 404, repeated aggregation agrees and producer inputs stay unchanged.
Analysis UUIDs here are deliberately unpersisted, not published completed runs.

Additional shared workflow checks pass:

```sh
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-a04-api.d.ts
frontend/node_modules/.bin/tsc --noEmit --strict /tmp/evora-a04-api.d.ts
npm --prefix frontend run build
node frontend/test/cases.integration.mjs
npx --yes @google/design.md@0.4.0 lint DESIGN.md
```

OpenAPI has only the existing missing-license warning; DESIGN has zero errors
or warnings. Generated declarations compile; frontend build checks declaration
freshness and TypeScript. Real localhost I00/I00B smoke passes authorized intake,
original/hash/download/audit, network/GPS processing/source inspection, paginated
overview and actor isolation. No Windows/clean-install/hosted-CI/browser/benchmark
claim. No completed analysis or Neo4j publication proof: A01B/A05/I01 and
Checkpoint 1C remain open. The later NLP/full-modality suite was not rerun;
previously documented model limitations are outside this ticket. Next bounded
M3 handoff is A01B with G01D, then A05/A06. Changes remain unstaged/uncommitted;
no commit, push or merge authorized or performed.

Earlier completed-checkpoint backend regressions: **327 pass**, no skips, using
real merged producers and ResourceWarning-as-error:

```sh
PYTHONPATH=/tmp/evora-u13-validation EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_skeleton backend.tests.test_validation backend.tests.test_auth backend.tests.test_cases backend.tests.test_evidence backend.tests.test_audit backend.tests.test_audit_list backend.tests.test_m1_access backend.tests.test_network_csv backend.tests.test_gps_csv backend.tests.test_normalization backend.tests.test_candidate_entities backend.tests.test_source_events backend.tests.test_processing backend.tests.test_observations backend.tests.test_entities backend.tests.test_events backend.tests.test_processing_provenance backend.tests.test_processing_dispatch backend.tests.test_processing_publication backend.tests.test_processing_audit
```
