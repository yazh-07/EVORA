# EVORA scoped agent assignment templates

Coordination-branch draft 0.3.0, not a running app. Four people each work on one module; confirmed GitHub-handle assignments and integration coordination are in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). Full initial proposal scope is fixed. Use the canonical phase/checkpoint ledger in [ROADMAP.md](ROADMAP.md). Assign one catalog row, not an entire module, milestone or full dashboard. Codex fills the task card from recorded repository decisions before editing. Missing common-base/allowed-path choices or a shared G/I assignee need a short clarification, not a guessed assignment.

### F05 assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and acceptance | **F05 / 1A**: authorized original download; byte/hash round trip; traversal, foreign-case and missing-file reads rejected safely |
| Module/person | **M1 Evidence Foundation / sharmelas-925**, matching ROADMAP's module table; user explicitly authorizes these bounded implementation/shared-record edits |
| Branch/common contract commit | `feat/f05-evidence-download`; clean starting HEAD and local `docs/coordination-foundation` both **c5c9b5a5aefff113db6592996da4af1c780d88df**, unchanged OpenAPI draft 0.3.0 |
| Allowed paths | `backend/evidence.py`, `backend/tests/test_evidence.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec, frontend or dependency edits |
| Dependencies | Real merged F03 via **e5273a6** (including Windows path correction **6622959**) and F00 **94aa2a8** are ancestors of this base; existing real F01/F02/F04 producers are consumed, no evidence/storage/access doubles |
| Input/output | Consume F03 SQLite storage metadata/private bytes and F00 case grant; produce existing `downloadEvidence` full-byte API for M2 source access and M4 U04/U14 |
| Gate | No unresolved choice blocks F05. Existing flat INVALID_INPUT/NOT_FOUND policy is explicitly confirmed; unsafe or absent stored paths return the same 404. Later format/scoring/provider choices stay with their rows |
| Acceptance/tests | Synthetic network.csv, binary/empty originals, MIME/cache headers, UUID/auth errors, two actors/cases, immediate membership revocation, external/traversal/prefix-collision/other-case/directory/missing/NUL/symlink paths; real FastAPI/SQLite/files with automatic temporary cleanup |
| Verification/handoff | Exact commands/results in PREIMPLEMENTATION_REVIEW's F05 record; **In Progress**, pending review/integration. No stage/commit/push/merge authorized. Next M1 row F06 requires a separate assignment; U04 can consume F05 after accepted handoff. Checkpoint 1A/I00 exit remains open |

## Copy this into Codex

Open Codex inside the EVORA repository. Replace only `[GITHUB_HANDLE]`. Codex selects and implements the next eligible task; you do not need to find or enter its ID.

```text
I am [GITHUB_HANDLE], working on EVORA.

Read AGENTS.md and follow its instructions. Use docs/ROADMAP.md
and docs/TASK_BREAKDOWN.md to select my next eligible task using
the automatic-selection rules in docs/AGENT_TASKS.md.

Briefly state the task ID and why it is next, fill its assignment
card from the repo, then implement and test it without asking me
to choose a task. Preserve existing work and the API contract.

Ask only if a required decision, assignment or safe shared base
is missing. Do not guess, skip dependencies or take another person's work.
Report actual results, blockers and the next eligible task when finished.
Include a "How you can test it" checklist with exact setup/run commands
or UI steps, synthetic test inputs, expected results and one failure case.
Clearly label anything you could not test. Wait for my review before
starting another task; do not mark unintegrated work Complete.
Do not commit, push or merge unless I explicitly ask.
```

This authorizes **automatic selection and implementation of one bounded task per run**, not an unlimited loop or automatic publication. Start a fresh session for the next task after the previous change has been reviewed/integrated or an explicit safe dependency handoff has been recorded. A prompt alone is not a background scheduler.

The detailed sections below are **reference for Codex**, not extra text the user needs to paste. All AGENTS.md reading, privacy, evidence-integrity, dependency and verification rules still apply.

### Optional: choose a specific task

Add `Use task [TASK_ID] instead of automatic selection.` to the prompt. All ownership, dependency and readiness checks still apply.

## Assignment card (Codex fills this before editing)

| Field | Fill from catalog/shared base |
|---|---|
| Task/checkpoint and exact acceptance | One ID/row matching ROADMAP and the catalog, success and negative assertions |
| Module/person and coordination | Module owner from ROADMAP; explicit G/I assignee and scoped help if needed |
| Branch/common commit | Short-lived `feat/<id>-<slug>`, exact common spec commit |
| Paths | Actual component/tests after skeleton; no unrelated module/spec/migration overwrite |
| Dependencies | Exact prerequisite IDs and commits; real merged producer or disclosed schema-derived fixture; no false integrated claim |
| Input/output | Existing operation/schema/internal policy and fixture/source locators |
| Gate | Only needed C-03–C-06/setup choice; unaffected work may proceed |
| Commands and proof | Exact implementation test/build/contract commands, read-back, current checkpoint checks and prior completed checkpoint regressions |
| Handoff | Changed paths/interfaces, known limits, next ticket/PR and coordinated status |

## Choosing the next task

### F02 assignment — 2026-10-25

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **F02 / 1A**: list authorized cases with correct total/limit/offset, deterministic pagination, empty pages and authentication/validation negatives |
| Module/person and coordination | **M1 / sharmelas-925**; user-authorized bounded implementation and these documentation records |
| Branch/common commit | `feat/f02-case-listing`; clean starting HEAD/common contract base **a10a81ecf4820b2330bd04edfba7f15d2764c745**, `docs/coordination-foundation`, including merged F00/F01 |
| Paths | Only `backend/cases.py`, `backend/tests/test_cases.py`, `backend/README.md`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec/frontend/dependency changes |
| Dependencies | Real F01 at **a10a81ecf4820b2330bd04edfba7f15d2764c745**, including F00 through merge **86f14eedc575032d636a77233b19f13bf665c077**; no case producer double; synthetic bearer identities only |
| Input/output | Consume draft 0.3.0 `listCases`, `CasePage`, `Case`, existing authenticated_actor and SQLiteDatabase; produce authorized paginated GET API |
| Gate | User confirms existing flat INVALID_INPUT mapping for F02; no unresolved choice blocks this row |
| Commands and proof | [F02 verification](PREIMPLEMENTATION_REVIEW.md#f02-verification--2026-10-25): bundled-schema API tests, all backend/coordination/frontend regressions, lint/bundle, types/build, DESIGN and diff checks |
| Handoff | **In Progress**, locally verified for review; Checkpoint 1A remains open. No commit/push/merge authorized. Next M1 row F03 requires its own dependency/policy review |

### G00 assignment — 2026-10-18

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **G00 / 0**: record the published common base, actual lint/bundle/type/coordination/unittest/DESIGN results and targeted C-03–C-06 gates; no all-policy settlement or four-signoff ceremony |
| Module/person and coordination | Shared integration coordination explicitly assigned by the user to **whale2186**, alongside the existing M3 ownership in ROADMAP; no additional contributor |
| Branch/common commit | `feat/g00-coordination-base`; exact common contract/base **114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb** (`origin/docs/coordination-foundation`); clean starting HEAD and local remote-tracking ref both read back at this commit |
| Paths | Only `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`, `docs/COMMUNICATION.md`, `docs/AGENT_TASKS.md`; generated bundle/types and environment tooling stay in `/tmp` |
| Dependencies | None (—); real published Git base contains the planning artifacts and draft 0.3.0 contract. No application producer, model or API test double is used or claimed |
| Input/output | Consume unchanged `specs/openapi.yaml` draft 0.3.0, shared workflow and planning/fixture checks; produce an assignment, verification record and bounded handoff. No HTTP interface change |
| Gate | C-03 auth, C-04 adapter policy, C-05 scoring and C-06 RAG/privacy remain **Open**, with producer/consumer impact recorded in PREIMPLEMENTATION_REVIEW and ROADMAP; none requires selecting future policy to review this base |
| Commands and proof | [G00 verification and test checklist](PREIMPLEMENTATION_REVIEW.md#g00-verification--2026-10-18): cached exact-version tools pass artifact checks and 122 tests with jsonschema 4.25.1; requested npx invocations fail registry DNS resolution. No earlier completed checkpoint exists to regress |
| Handoff | **In Progress**, locally verified documentation awaiting review/publication; no commit/push/merge authorized. Checkpoint 0 stays In Progress; G01/G01B/G01C stay Backlog. Next scopes are G01 or independent G01B after G00 handoff acceptance, each requiring explicit shared-task assignee/paths; G01C needs both real skeletons |

This card records the user's bounded shared-file handoff before the G00 ledger/review edits. Final results are in PREIMPLEMENTATION_REVIEW; local verification does not publish these changes or complete a product milestone.

### G01 assignment — 2026-10-18

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **G01 / 0**: shared FastAPI/Python + SQLite skeleton, tested pinned versions and test command, real startup/database test and shared HTTP 400 `ApiError` request-validation mapping with schema assertions; no domain features or new public routes |
| Module/person and coordination | Shared integration coordination explicitly assigned by the user to **whale2186**, alongside M3; this handoff authorizes the bounded shared scaffold and three ledger edits |
| Branch/common commit | `feat/g01-backend-skeleton`; exact common contract/base **1721bfff9640263d2799434455cdb9c4f345ac35** (`feat/g00-coordination-base`); starting clean HEAD and local `origin/feat/g00-coordination-base` both read back at this commit |
| Paths | Only `backend/`, `pyproject.toml` / `requirements.txt`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; leave `specs/openapi.yaml` unchanged; generated artifacts/environments under `/tmp` |
| Dependencies | **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**, explicitly accepted as the common base by this user handoff. Actual committed coordination artifacts are consumed; no remote CI/main integration claim |
| Input/output | Consume draft 0.3.0 `ApiError` and shared stack policy; produce app factory, SQLite connection/lifespan foundation, validation handler, tests and local run instructions. Test-only routes exercise actual FastAPI validation; they are synthetic probes, not domain producers |
| Gate | No unresolved choice blocks G01. C-03–C-06 remain open for their dependent rows. No health endpoint exists in the contract, so startup/SQLite are tested directly without adding one |
| Commands and proof | [G01 verification](PREIMPLEMENTATION_REVIEW.md#g01-verification--2026-10-18): **14 backend / 122 coordination tests pass**, real SQLite and synthetic test-only HTTP validation probes, verifier/lint/bundle/generated strict TypeScript/cached DESIGN checks pass. CPython 3.14.8 and 22 tested package pins; Uvicorn startup succeeds but socket binding is denied. Clean index installation/Windows/remote CI remain unverified; no earlier completed checkpoint exists |
| Handoff | **In Progress**, locally implemented/verified, awaiting review/integration; no stage/commit/push/merge. Exact commands and failure checklist in `backend/README.md` (see [G01 verification](PREIMPLEMENTATION_REVIEW.md#g01-verification--2026-10-18)). G01B remains the independent Checkpoint 0 candidate with an explicit shared-task handoff; G01C needs both skeletons and Python-baseline/Windows/CI setup proof |

### G01B assignment — 2026-10-18

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **G01B / 0**: pinned tested Node/packages and lockfile; React/TypeScript/Vite shell; generate declarations from unchanged draft 0.3.0; start/build/`tsc --noEmit`; real render test and negative checks; DESIGN tokens and API-only boundary; preserve shared/backend checks |
| Module/person and coordination | Shared integration coordination explicitly assigned by the user to **whale2186**, alongside M3. M4 remains owned by **JebasJ**; this bounded scaffold does not assign M4 domain work |
| Branch/common commit | `feat/g01b-frontend-skeleton`; exact common contract/base **e0257a6ad231105b93ae98a97f176ed233a25412** (`feat/g01-backend-skeleton`); clean starting worktree and HEAD read back at this SHA |
| Paths | Only `frontend/`, `package.json`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; lockfile stays under `frontend/`; do not modify `specs/openapi.yaml`, backend, workflow or other shared files |
| Dependencies | **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**, included in user-accepted **G01 at e0257a6ad231105b93ae98a97f176ed233a25412**. Real committed skeleton/contract consumed; no main merge or remote CI claim |
| Input/output | Consume sole HTTP authority `specs/openapi.yaml` 0.3.0 and DESIGN.md. Produce generated declarations and a frontend setup shell, commands/tests/docs; no invented API routes, wire fields or domain producer doubles |
| Gate | No C-03–C-06 decision blocks the static shell/type generation. Auth/base URL/runtime error client belongs to U01 after F00. No health endpoint or domain routes exist in G01; do not probe or fabricate availability |
| Commands and proof | Frontend install/generation freshness/typecheck/render test/build/start; shared OpenAPI lint/bundle, coordination verifier/unittests with jsonschema 4.25.1, warning-strict backend suite, DESIGN lint and `git diff --check`. Actual results recorded in PREIMPLEMENTATION_REVIEW; registry DNS currently unavailable, investigate cache installation without claiming network/Windows reproducibility |
| Handoff | **In Progress**, implementation authorized but stage/commit/push/merge prohibited. Checkpoint 0 stays In Progress. Next candidate **G01C** after reviewed G01B handoff, requiring its own bounded shared-task assignment and real Windows/CI evidence |

### G01C assignment — 2026-10-18

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **G01C / 0**: Linux and Windows CI must clean-install pinned backend/frontend dependencies and run coordination lint/bundle/generated types/verifier/unit tests/DESIGN plus both real skeleton suites/build. Document exact PowerShell setup/run commands, versions and failures; close Checkpoint 0 only with all four exit gates verified |
| Module/person and coordination | Shared integration coordination explicitly assigned by the user to **whale2186**, alongside M3; module ownership remains unchanged |
| Branch/common commit | `feat/g01c-skeleton-ci`; exact user-selected common contract/base **328c103d0f0383c7b4979bd8199b4201408e2a68** (`feat/g01b-frontend-skeleton`); starting branch/HEAD and clean worktree read back at this SHA |
| Paths | Only `.github/workflows/`, `backend/README.md`, `frontend/README.md`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec, requirements, lockfile or application changes |
| Dependencies | Real **G01 at e0257a6ad231105b93ae98a97f176ed233a25412** and **G01B at 328c103d0f0383c7b4979bd8199b4201408e2a68**, including **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**, accepted by the user's exact-base handoff. These are committed ancestors, not domain API doubles or a main-merge claim |
| Input/output | Skeleton build/test commands and unchanged draft 0.3.0; produce a two-OS CI matrix, setup/run documentation and actual verification record. Backend tests use real SQLite/FastAPI with test-only validation probes; frontend tests render the real shell without domain producers |
| Gate | No C-03–C-06 choice blocks skeleton CI. Use backend's CPython **3.14.8** and frontend manifest's Node **22.23.3** / npm **12.2.0**. Native Windows and hosted CI results must be read back before claiming G01C/Checkpoint 0 Complete |
| Commands and proof | [G01C verification](PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18): clean isolated backend install/all 22 pins/pip check and lockfile frontend install pass on Linux; **122 coordination / 14 backend / 2 frontend tests**, lint/bundle/generated strict types/freshness/typecheck/build/DESIGN/actionlint pass. Real server startup/HTTP responses and scratch stale-type/missing-bundle negatives exercised; all G00/G01/G01B checks rerun on the combined candidate |
| Handoff | **Complete**. Multi-OS workflow verified green on GitHub Actions PR #1 (Run 39102433077) across ubuntu-latest and windows-latest. Checkpoint 0 is Complete. Next active checkpoint is 1A (M1 F00 / sharmelas-925, M4 U01 / JebasJ) |

### U01 assignment — 2026-10-22

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **U01 / 1A**: configure the authenticated API base URL and typed client in the shared frontend; generated client types compile, auth/error handling is shared, no hard-coded bearer tokens |
| Module/person and coordination | **M4 / JebasJ**, selected automatically from the user's one-task assignment; no M1 or shared G/I work taken |
| Branch/common commit | `feat/u01-authenticated-api-client`, exact published coordination base **6496c5e9e17f2000b64a64f79d2fb166c6ce2094**, the user-selected starting branch `docs/coordination-foundation`; clean HEAD and freshly fetched origin ref matched; remote main is still README-only |
| Paths | `frontend/src/api/` except generated `schema.d.ts`, `frontend/src/main.tsx`, `frontend/scripts/build.mjs`, `frontend/scripts/build-test.mjs`, `frontend/test/`, `frontend/tsconfig.json`, `frontend/README.md`; only this assignment/status/result record in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. No spec, full-scope, backend or dependency-manifest change |
| Dependencies | Real **G01B 328c103d0f0383c7b4979bd8199b4201408e2a68** and its accepted G00/G01 ancestry are included in the base. **F00 is not implemented** in the published base or remote main. AGENT_TASKS permits U01 with a disclosed schema-derived fixture; Fetch/HTTP fixtures exercise client behavior only, never actual backend authorization |
| Input/output | Consume generated `paths`/`operations`/`ApiError` from unchanged OpenAPI draft 0.3.0. Produce one reusable Fetch client and React provider, configurable server origin, memory-only token/session lifecycle and shared HTTP/protocol/network errors. No login endpoint, case UI, domain producer or fabricated API result |
| Gate | C-03's declared resolution in ROADMAP/COMMUNICATION supplies bearer format, memory-only tokens and 401/404 policy; older open-queue entries are historical inconsistencies, not a new provider choice. Real F00 integration remains required; no token issuance/expiry/revocation mechanism is invented |
| Commands and proof | **19 frontend / 122 coordination / 14 backend tests pass**, no skips in the full suites; frontend API freshness/typecheck/build, OpenAPI lint/bundle, scratch generated strict types, verifier, DESIGN and whitespace pass. Seven synthetic responses validate against the bundle; focused 401 negative passes. Real Fetch reaches a localhost fixture and rejects redirects; actual skeleton HTTP smoke returns backend 404/frontend 200. [Exact results and commands](PREIMPLEMENTATION_REVIEW.md#u01-verification--2026-10-22); real F00/browser integration and new hosted CI remain untested |
| Handoff | **In Progress**; independent client work only, awaiting review and real F00 integration. Preserve every feature and approved addition in FEATURE_SCOPE. Do not mark U01 or Checkpoint 1A Complete. The user subsequently authorized committing and pushing this scoped task branch on 2026-10-22; no merge authorized |

### F01 assignment — 2026-10-25

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **F01 / Checkpoint 1A**: persist/read one case with stable UUID, reject invalid title, deny another actor |
| Module/person and coordination | **M1 / sharmelas-925**; bounded case persistence and existing authentication integration |
| Branch/common commit | `feat/f01-case-persistence`, clean starting HEAD **86f14eedc575032d636a77233b19f13bf665c077**, matching the user-specified merged F00 coordination base; no fresh fetch claimed |
| Paths | `backend/cases.py`, `backend/app.py`, SQLite manager documentation in `backend/database.py`, `backend/tests/test_cases.py`, F01 startup/route expectations in `backend/tests/test_skeleton.py`, `backend/README.md`; bounded records in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. No spec, frontend or dependency edits |
| Dependencies | Real F00 **94aa2a8** included through merge **86f14ee**; real G01 SQLiteDatabase and safe validation handler from the same base |
| Input/output | Consume unchanged draft 0.3.0 `CreateCase`, `Case`, `ApiError`, bearer identity and case grant; produce `createCase`, `getCase` and authoritative SQLite membership |
| Gate | **F01-E01 pending**: task requests nested `error` bodies and BAD_REQUEST, while unchanged ApiError/F00/U01 require flat code/message and existing INVALID_INPUT. M1 error producer and M4 generated/client error consumers would need a coordinated spec/types/fixture/test change for an envelope change. User clarification requested; current verification retains the existing contract pending resolution |
| Dependency handling | Real F00 guards and SQLite connections used; synthetic verifier supplies only test identities. No membership producer double in F01 tests. Earlier F00 tests retain their disclosed isolated doubles |
| Commands and proof | 11 focused F01 / 44 combined backend / 122 coordination / 19 frontend tests pass; OpenAPI bundle/lint, generated strict types, frontend freshness/typecheck/build, verifier, DESIGN and whitespace checks pass. Exact commands/environment and limits in [F01 verification](PREIMPLEMENTATION_REVIEW.md#f01-verification--2026-10-25) |
| Handoff | **In Progress** pending F01-E01 resolution and review. No staging, commit, push or merge authorized. Next M1 row F02 after F01 acceptance; no Checkpoint 1A completion or real browser integration claimed |

### F00 assignment — 2026-10-25

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **F00 / Checkpoint 1A**: authenticate requests and enforce a case-access guard without evidence logic; missing/invalid identity is 401, foreign and missing cases have indistinguishable 404 responses |
| Module/person and coordination | **M1 / sharmelas-925**, automatically selected from the user's one-task assignment; no shared G/I task or other module's work taken |
| Branch/common commit | `feat/f00-auth-case-guard`, verified published coordination base **f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029**; clean HEAD matched freshly fetched `origin/docs/coordination-foundation` |
| Paths | `backend/auth.py`, auth wiring in `backend/app.py`, access-error mapping in `backend/errors.py`, `backend/tests/test_auth.py`, `backend/README.md`; bounded assignment/live-result records in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. No schema, package, frontend, case-persistence or feature-scope changes |
| Dependencies | Real G00 **1721bfff9640263d2799434455cdb9c4f345ac35** and G01 **e0257a6ad231105b93ae98a97f176ed233a25412** are verified ancestors; use the real FastAPI factory/validation mapping and isolated SQLite connection foundation |
| Input/output | Consume unchanged `bearerAuth`/`ApiError` and C-03's declared local synthetic policy; produce reusable authentication and same-case dependencies, no new public HTTP operation |
| Gate | Later ROADMAP/COMMUNICATION C-03 resolution supplies two synthetic identities (`investigator-1`, `investigator-2`) and exact 401/404 policy. No production provider, token issuance/expiry or frontend login is selected. Default configuration must deny access; explicit development tokens are supplied by the caller, never built in |
| Dependency handling | F01 owns real cases/membership persistence and is not implemented. Exercise an explicitly test-only SQLite membership producer with two actors/cases; expose a deny-by-default membership interface for F01, without claiming F01 or U01 integration |
| Commands and proof | **19 F00 / 33 combined backend / 122 coordination / 19 frontend tests pass**, no skips; focused foreign/missing failure case passes. OpenAPI lint/bundle, scratch generated strict TypeScript, API freshness/typecheck/build, coordination verifier, DESIGN and whitespace checks pass. Real skeleton localhost smoke returns backend 404/frontend 200 and stops both servers. Exact commands, fixtures and limits are in the F00 verification record |
| Handoff | **In Progress**, locally verified; F01 membership persistence and real U01/browser integration remain absent. No production identity/expiry mechanism or integrated completion claimed. Next M1 row is F01 after accepted F00 dependency handoff. The user subsequently authorized committing, pushing and merging this scoped branch into `docs/coordination-foundation` on 2026-10-25; no second task is authorized |

### F06 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and acceptance | **F06 / 1A**: append-only source/provenance and intake audit; server-authored actor/action/target/time, no evidence contents or secrets in logs |
| Module/person | **M1 / sharmelas-925**, automatic selection from the user's one-task request; no shared G/I work taken |
| Branch/common contract commit | `feat/f06-intake-audit` / **3eab939ada44363de5420d542ead711198ccea0f**, verified clean local `docs/coordination-foundation` after `git fetch origin` and fast-forward; HEAD exactly matched origin before task-state selection and branching |
| Paths | `backend/audit.py`, upload transaction hook in `backend/evidence.py`, audit startup wiring in `backend/app.py`, `backend/tests/test_audit.py`, startup table assertion in `backend/tests/test_skeleton.py`, `backend/README.md`; bounded F06 records in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md` |
| Dependencies | Real merged F03 upload producer and F00/F01/F04/F05 guards/cases/metadata/downloads are present in the verified base. F06 is unclaimed; no local or remote F06 branch existed. Older session In Progress records do not erase merged code |
| Input/output | Existing `uploadEvidence` transaction, server identity and `Evidence` metadata → one safe `AuditEvent` plus linked private versioned intake-source snapshot; unchanged upload response and contract. Reuse `uploadEvidence` as the action identifier |
| Gate/boundary | No unresolved auth/parser/scoring/provider choice is needed for intake accounting. Audit and private provenance append atomically with evidence metadata; append failure rolls back metadata and removes this upload's file. No fabricated backfill for originals uploaded before F06. F07 owns audit-list API; processing/model/RAG provenance remains with its later producer tasks |
| Verification | **17 focused F06 pass**; **87 combined backend run: 86 pass, one known Windows symlink skip**; **122 coordination and 48 frontend pass**. Contract lint/bundle/generated strict types, freshness/typecheck/build/DESIGN/whitespace pass. Real localhost F06 SQL/byte read-back and existing U02/U02B/U03/U04 HTTP/client regressions pass; selected provenance rollback failure passes. Exact evidence/limits in F06 verification in PREIMPLEMENTATION_REVIEW |
| Handoff | **Complete**, user-authorized integration through PR #12 into `docs/coordination-foundation` at **1b5166d91e0f3b86b85585d714a917a3efc82d44**, containing task commit **203c4d5809300ac4b08e82b22856ad4614a12b97**. Ubuntu and Windows PR CI pass (Run **41297980571**); exact merged-tree real HTTP/SQL intake and case/upload/download client regressions pass. Next M1 row is F07; F09 waits for F07; I00 still needs an explicit shared-task assignee. No F07 implementation or checkpoint completion included |

### F07 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and acceptance | **F07 / 1A**: expose case audit-event list; logged actions visible, correct pagination and case isolation |
| Module/person | **M1 / sharmelas-925**, user explicitly assigned this one task and authorized its commit, push and merge after verification |
| Branch/common commit | `feat/f07-case-audit-list` / **441d37de6db68f1f459aa11eb1bf6bd5864f5b77**, clean local `docs/coordination-foundation` matched freshly fetched origin before selection/branching; no existing local/remote F07 branch |
| Allowed paths | `backend/audit.py`, router wiring in `backend/app.py`, `backend/tests/test_audit_list.py`, update only the obsolete F07-absent assertion in `backend/tests/test_audit.py`, `backend/README.md`; bounded F07 records in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md` |
| Dependencies | Real F06 **203c4d5**, merge **1b5166d** and accepted receipt **441d37d**, with real F03 intake, F00/F01 case authorization, authoritative SQLite and private files |
| Input/output | Unchanged `listAuditEvents` → `AuditPage`/`AuditEvent`; only existing limit (default 20, 1–100) and offset (default 0, nonnegative); safe selected columns, optional null reason omitted |
| Implementation policy | Existing current membership guard, 400/401/non-leaking 404. Deterministic oldest-first `created_at ASC, id ASC`; total/page share one read snapshot. No private-source join, payload logging, new filter/selector or frontend feature |
| Required proof | Real F03 upload → authorized list/schema read-back, empty/beyond-end/default/boundary/tied pagination, two actors/cases/current membership, malformed input/auth, foreign/missing equivalence, no private values/storage fields, read-only listing and storage failure; shared contract/coordination/backend/frontend regressions |
| Verification | **14 focused F07 pass**, selected foreign/missing failure passes; **101 backend run: 100 pass, one existing Windows symlink skip**; **122 coordination and 48 frontend pass**. Contract lint/bundle/generated strict types, API freshness/typecheck/build, DESIGN and whitespace pass. Real localhost upload/audit API/SQL/original read-back and prior case/upload/download real-client integration pass |
| Handoff | **In Progress**, locally verified pending the user-authorized commit/push/merge and exact merged-tree acceptance. Full agreed initial scope unchanged. F09 is next after F07 acceptance; shared I00 still requires an explicit assignee. No F09 implementation authorized |

### Automatic-selection rules

1. Read the live module-owner and task state in ROADMAP, the exact checkpoint ledger, catalog dependencies and relevant communication gates. Read Git status and verify the recorded common-base commit is available and includes the required shared contract. An uncommitted draft is not an implementation base.
2. Limit candidates to the caller's module, or a G/I task explicitly assigned to that handle. Coordination responsibility does not automatically assign shared tasks. Do not take another person's task or an already active branch. Resume an existing In Progress task only when its recorded assignee/branch and the user's session match.
3. In the earliest unfinished checkpoint, choose an unclaimed Backlog task whose prerequisites, base and required decisions are ready. If several qualify, use catalog row order as a tie-break only after checking dependencies. Do not ask the user to pick among equally eligible tasks. Later independent fixture work needs an explicit recorded assignment; automatic selection must not skip checkpoint gates.
4. Fill the card with the exact task/checkpoint/owner/base, allowed paths and tests from recorded decisions. Briefly announce the selection, then work without another approval request. If a necessary base/path/policy decision is absent, ask one focused question; if no task is eligible, report the blocking dependency rather than inventing work or polling indefinitely.
5. Use a fresh task branch from the verified common base. Do not move, stash, reset or overwrite unrelated local changes to make the checkout fit. If existing edits prevent isolation, stop and ask for a safe branch/worktree handoff. Coordinate any shared ledger claim before edits to avoid two agents choosing the same row.
6. Execute the task's real acceptance/negative tests and required prior-checkpoint regressions. Report fixture-only work as such. A locally passing unintegrated change is not integrated Complete; record branch/results and pending integration honestly under ROADMAP's state rules.
7. Finish with the task ID, actual tests, blockers, a **How you can test it** checklist and next eligible ID (or exact dependency blocking it). The checklist supplies prerequisites, exact setup/run commands or UI actions, synthetic/permitted input, expected observable results, one relevant failure case and any cleanup. Do not expose secrets or require real evidence. State which steps Codex actually exercised and which remain untested; a manual checklist is not proof those steps passed. If the full UI or upstream dependency is absent, give the available component/API verification and label what cannot yet be tested end to end. Do not automatically commit/push/merge or mark a whole checkpoint complete. Stop for user review after this bounded task; the next fresh run re-reads current state rather than assuming the previously suggested next task is still available.

Start in the earliest unfinished checkpoint with a dependency-ready bounded row. G00 is the first common task. After the shared base is recorded, G01 and G01B can proceed independently; G01C verifies their skeletons. In 1A, F00 needs C-03 and U01 needs real F00 or a disclosed fixture. In 1B, adapter/lifecycle/UI rows follow actual dependencies; I00B is their real integration gate. In 1C, G01D/G02 precede projection/scoring; I01 requires early provenance/audit and explanations. Never prompt an agent with all checkpoint IDs as one implementation request.

G/I work is assigned to an existing contributor with explicit shared paths. Do not infer a person from a task prefix. Future tasks can be developed independently when their own choices/interfaces are ready, but cannot close a milestone against test doubles. Unimplemented future actions must remain unavailable rather than fake successful.

In 4A select remaining analytical producer rows for component tests, not real-API panel closure. U12A/U12B/U12C/U12D/U12E/U13B can begin fixture-based component work earlier, but their integrated-completion checkpoint is 4B and A17 is an additional prerequisite for each. In 4B verify A17 assembly/coherent publication, complete all six real-API views, then detector feedback/evaluation; retain every existing task acceptance.

## Row-specific module suffixes

### M1 — one Fxx row

> Apply only this row's invariants: F00/F01 authorization; F03/F05 original bytes/hash; F06–F08E append-only audit/private provenance; F09 owning-route regression. Rich model/parser/prompt parameters/input/output/time/verification remain private authorized data, not public audit fields/raw application logs. Shared 400 ApiError mapping is declared contract requiring tests. Do not implement unrelated routes to make the task appear complete.

### M2 — one Pxx row

> For adapter rows, document supported format/model/limits first, then source-located raw/normalized outputs and uncertainty; detection is not a person's identity. Lifecycle rows test idempotency/atomic completed publication, latest completed selection and processing_run_id historical output. P14/P14D preserve private versioned provenance; P15 selects deeper/reconfigured existing-evidence processing internally with a new key, unchanged original and immutable old output. Never invent processing request fields or claim another modality from a single CSV test.

P16/P16B add local audio/video speech with segment offsets, private model/decoder provenance and candidate extraction. Resolve C-04 model/language/codec/resources before adapter work, not G03. U14/U14B/U14C add playback/search and append-only corrections under the canonical contract. Preserve machine text and frozen analytical sources; no automatic speaker identity or spoken-event truth, and no double-counted video/audio/transcript corroboration.

### M3 — one Axx row

> A factor row tests that one G02 function and controls, not the full scoring system. A04 aggregates initial available factors; A17 explicitly wires all reviewed factors/detectors. A01B tests pending SQL→idempotent case+run Neo4j→verify→SQL completed pointer and recovery, without distributed transaction claims. A05 tests bodyless frozen snapshot/hash/trigger and original-key replay before resnapshot. A05B/A06 test analysis_run_id pinned completed reads and selector 404. A18/A19 prove existing-evidence reprocessing/detector-driven rank changes with immutable history. A16 deterministic retrieval does not replace A16B full context/final LLM RAG.

### M4 — one Uxx row

> Implement exactly the view/command/API named by the row. U05C starts processing, U05D starts bodyless analysis and polls. Pin completed analysis_run_id across graph/findings/triage and pagination; never combine mixed-run data. U13 counts/types/status aggregate all pages; U13B/U13C expose distinct uncertainty/candidate sources. U10/U11 deterministic tracer remains separate from required U10B/U10C/U11B approved generation/citation verification/private provenance. Review/overrides audit actor/reason and never overwrite automated scores. Apply DESIGN.md shared components, keyboard/focus/contrast/responsive requirements, safe text rendering and in-memory token/evidence handling. Test loading/empty/busy/error paths for this row only; no frontend DB connection, scoring duplicate or Streamlit dashboard.

### Cross-module — one G/I row

> Prove this row's real dependency closure, not a plausible subset. I00 proves intake and I00B proves immutable initial processing before I01 proves source-backed graph/triage/pinned read paths. I03B proves all modalities through actual command/source-inspection UI. I07 detector feedback and I07B same-evidence deeper processing are distinct from new-upload I02. I08 evaluates every modality and final RAG; I09 covers all F/P/A/U features; I09B clean full Windows/CI; I06 follows full gates. No fake metrics, fabricated provider result or passing app claim from document lint.

## Example bounded F03 assignment

> Implement F03 upload/hash on `feat/f03-evidence-upload` from `[COMMON_COMMIT]`, M1 `[ASSIGNEE]`, only `[EVIDENCE IMPLEMENTATION + FOCUSED TEST PATHS]`. Use real F01/F00 or explicitly declared schema-derived tests. Follow C-04 limits/type policy; stream immutable private bytes, stable UUID, exact Evidence response and source metadata. Test network.csv hash/size/bytes plus unsafe filename/oversized/invalid content/foreign-case failures. If F05 has not landed, assert bytes at the storage test boundary rather than implement download in F03. Exercise real F05 integration before the intake gate I00. Report actual tests and stop only the needed unresolved gate, not unrelated work.

## Reviewer checks

- Exact ID/checkpoint/allowed scope/common contract, dependency-ready row, appropriate negatives and actual test output?
- Valid same-case source observation IDs/locators and original Evidence hashes?
- Declared validation/status/idempotency/snapshot/selectors used without invented wire fields?
- No partial graph/results, cross-run display, raw sensitive logs or silently changed old output?
- Real producer/provider exercised where claiming integrated/full-scope completion; doubles disclosed?
- Accurate uncertainty, no guilt/certification/originality claims or fabricated benchmarks?

Coordination checks: lint/bundle, generated client/TypeScript compilation, `scripts/verify_coordination.py <bundled-json-path>`, the `test_*.py` unittest suite with EVORA_CONTRACT_BUNDLE set to that bundle (jsonschema==4.25.1) and DESIGN lint via the shared workflow. Those are artifact checks, not substitutes for selected row's application tests. G01/G01B/G01D pin tested versions; clean full-scope Windows proof is I09B.

### U02 assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **U02 / 1A**: authorized paginated case list and getCase detail; real API, loading/empty/error states, actor isolation |
| Module/person and coordination | **M4 / JebasJ**; user approved the proposed bounded scope and subsequent commit/push; subsequent explicit merge authorization, no second task |
| Branch/common commit | `feat/u02-case-list-ui`, verified clean published `docs/coordination-foundation` **909009d21198fd751db49863f581b032875fa5e0**; live remote matched |
| Paths | `frontend/src/cases/`, `frontend/src/App.tsx`, `frontend/src/styles.css`, frontend tests and `scripts/build-test.mjs`, frontend README; bounded U02 records in AGENT_TASKS, ROADMAP and PREIMPLEMENTATION_REVIEW |
| Dependencies | Real U01 **42d03125b710ee37b7505361388fb15792ffe306**, F02 **c8077f5**, F00/F01 and G01B are merged ancestors. Historical In Progress records do not negate actual Git integration; real integration will be exercised |
| Input/output | Unchanged draft 0.3.0 listCases/getCase, CasePage/Case and shared ApiProvider/client; memory-only synthetic-session entry, no issuance route or creation/upload feature |
| Gate | C-03 recorded policy applies; user approved missing path/base handoff. No C-04/C-05/C-06 decision needed |
| Commands and proof | 25 frontend / 47 backend / 122 coordination tests pass; real HTTP/SQLite two-actor integration and browser smoke pass; contract/types/build/DESIGN pass. [Actual verification and limits](PREIMPLEMENTATION_REVIEW.md#u02-verification--2026-10-31) |
| Handoff | **Complete** after user-authorized integration at merge 9f2cc8ac64426ef2b0bb9d917fd7afdb777b606f and passing post-merge real HTTP/SQLite smoke; retain full FEATURE_SCOPE including approved transcription addition. Checkpoint 1A stays open; new hosted CI pending; no second task |

### U02B assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **U02B / 1A**: case-creation UI; valid/invalid title behavior and created case appears in list |
| Module/person and coordination | **M4 / JebasJ**; explicit user handoff for the bounded implementation and three shared documentation records |
| Branch/common commit | `feat/u02b-case-creation-ui`; clean HEAD and merge-base with `docs/coordination-foundation` both **16975127177f3c609249bd648455d364e0bfc46c**; no remote fetch claimed |
| Paths | `frontend/src/cases/`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/test/`, `frontend/scripts/build-test.mjs`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md` |
| Dependencies | Real U02 and F01 are integrated in the exact common base, alongside U01/F00/F02; real HTTP/FastAPI/SQLite integration required, no producer substitutes |
| Input/output | Unchanged draft 0.3.0 createCase/listCases and generated CreateCase/Case/CasePage types through shared client.request; local validation, safe errors, confirmed details and refreshed list |
| Gate | Existing C-03 synthetic local-session policy; no unresolved contract choice needed for this row |
| Commands and proof | Exact commands/results and declared transport doubles in [verification](PREIMPLEMENTATION_REVIEW.md#u02b-verification--2026-10-31); frontend/README.md records test procedure |
| Handoff | **In Progress**, pending review/integration; no commit/push/merge authorization, no checkpoint promotion. Next M4 row U03; no additional row implemented |

### F03 assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint | F03 / 1A: stream private immutable originals; exact hash/size/bytes; reject invalid, oversize and unsafe filenames |
| Module/person | M1 / sharmelas-925; user-authorized bounded implementation and shared records |
| Branch/common contract commit | `feat/f03-evidence-upload` / `1b7d92826a5af23431f3936c1c6152f3ad634065` on `docs/coordination-foundation`; clean starting tree |
| Paths | `backend/evidence.py`, `backend/app.py`, `backend/tests/test_evidence.py`, `backend/tests/test_skeleton.py` (startup table regression), `backend/README.md`, `requirements.txt`, these three task records; no spec/frontend changes |
| Dependencies | Real F01/F00 and F02 merged in the exact common base above; real FastAPI, SQLite and private filesystem, synthetic bearer identities only |
| Input/output | Draft 0.3.0 uploadEvidence multipart → 201 Evidence; existing flat ApiError and require_case_access |
| Gate | F03 intake policy: 50 MiB original bytes, opaque content without inline parsing, reject traversal/separators/control characters/unsafe portable filename punctuation; RFC 3339 acquisition text preserved. P04/P14B own parser/BOM/row/layout validation; U03 consumes 400/413. Remaining C-04 parser choices stay open |
| Verification | Required shared commands plus OpenAPI lint, generated type freshness/typecheck/build; actual results in PREIMPLEMENTATION_REVIEW.md |
| Handoff | In Progress for review; no commit/push/merge; next M1 task F04 after review, F05 and real I00 integration still required |

### F04 assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and exact acceptance | **F04 / 1A**: read evidence metadata and list case evidence; case-scoped records, pagination and not-found behavior tested |
| Module/person and coordination | **M1 / sharmelas-925**; user-authorized bounded implementation and documentation handoff |
| Branch/common commit | `feat/f04-evidence-metadata`; clean starting HEAD and merge-base with `docs/coordination-foundation`: **e5273a61e444a2fdf46b236e1f4a56700ac52f57** |
| Paths | Only `backend/evidence.py`, `backend/tests/test_evidence.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec, frontend or dependency edits |
| Dependencies | Real F03 at **e5273a61e444a2fdf46b236e1f4a56700ac52f57**, with merged F00/F01/F02/U01/U02/U02B; real FastAPI/SQLite/upload producer, synthetic authentication identities only |
| Input/output | Unchanged draft 0.3.0 `listEvidence`, `getEvidence`, `EvidencePage`, `Evidence`; existing `require_case_access` and SQLite metadata; omit absent acquisition time and private storage paths |
| Gate | Existing flat INVALID_INPUT 400 and NOT_FOUND 404 mapping confirmed by user; no unresolved choice blocks F04. Future parser/provider policy remains outside this row |
| Commands and proof | Required bundle, coordination verifier/tests, warning-strict backend tests, frontend tests, OpenAPI lint, generated API/type compilation, DESIGN lint and diff checks; actual results in F04 verification in `PREIMPLEMENTATION_REVIEW.md` |
| Handoff | **In Progress**, pending review/integration; no staging/commit/push/merge authorized. Checkpoint 1A remains open; next M1 row F05 needs a separate assignment |

### U03 assignment — 2026-10-31

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and acceptance | **U03 / 1A**: one-file upload and metadata UI; real bytes, visible size/type failures, Evidence ID/hash/size read-back |
| Module/person | **M4 / JebasJ**; explicit user handoff includes bounded shared documentation edits; whale2186 remains integration coordinator |
| Branch/common contract commit | `feat/u03-evidence-upload-ui`; clean starting HEAD and local `docs/coordination-foundation` both **69f2e8269b6e6d639889941926bc604a415e3f05**; unchanged `specs/openapi.yaml` draft 0.3.0; no fresh remote fetch claimed |
| Allowed paths | `frontend/src/cases/`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/test/`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md` |
| Dependencies | Real U01/F03/F04 and merged F00/F01/F02/U02/U02B are ancestors in the exact base; existing generated client supports FormData; integration uses real FastAPI, SQLite and private filesystem |
| Producer/consumer contract | M1 F03/F04 → M4 U03 using `uploadEvidence`, `listEvidence`, `getEvidence` and generated Evidence/EvidencePage; no new routes/fields/packages |
| Gate/policy | Existing C-03 session policy and F03 50 MiB opaque-byte intake apply. Optional datetime is explicitly entered as UTC and sent as RFC 3339; no inferred source timezone. Server 400/413/415 alerts use escaped text. Real F03 does not reject arbitrary file content by MIME; a 415 UI transport double does not establish backend type detection |
| Verification | Exact commands, read-back, doubles and limits recorded under U03 verification in `PREIMPLEMENTATION_REVIEW.md`; real integration covers 201/hash/size/list/detail/400/413/404 |
| Handoff | **In Progress**, locally verified pending review/integration. No staging/commit/push/merge authorized. Checkpoint 1A remains open; next M4 row U04 also requires real F05 and its own assignment |

### U02B reconciliation assignment — 2026-10-31

- Owner: M4 / JebasJ, explicit user reconciliation request, one U02B follow-up.
- Branch/base: feat/u02b-reconcile / d24312f939877e6959c6ff46d3e1d81051e474a6,
  freshly fetched shared base; isolated worktree preserves original dirty tree.
- Allowed scope: existing approved frontend cases/tests/README and bounded
  AGENT_TASKS/ROADMAP/PREIMPLEMENTATION_REVIEW records only.
- Real dependencies: merged U02B/F03/F04/U03/F05; preserve the integrated form
  and evidence UI, apply Unicode validation and safe creation-failure behavior.
- Verification: 41 frontend pass, 69 backend pass/1 Windows symlink skip;
  real case/create and U03 upload regressions, contract/types/build/DESIGN pass.
  Exact commands/limits in PREIMPLEMENTATION_REVIEW's reconciliation section.
- State: In Progress, uncommitted pending review; no commit/push/merge or U04.

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

### U04 assignment — 2026-10-31

| Field | Assignment |
|---|---|
| Task/checkpoint/owner | U04 / 1A / M4 JebasJ; original authorized download from selected evidence, correct bytes/hash and no persistent client cache |
| Base/branch | `d2879c6e1e236add391fb6af40480b9940d22555`, updated verified shared base (original draft d24312f); `feat/u04-evidence-download` in isolated worktree; original uncommitted U02B preserved |
| Paths | Existing approved frontend case/test/documentation boundary: frontend/src/cases, frontend tests, scripts/build-test.mjs, frontend README; bounded AGENT_TASKS/ROADMAP/PREIMPLEMENTATION_REVIEW records only |
| Dependencies | Real U03 merge c5c9b5a and F05 merge d24312f, with real F00/F03/F04; unchanged draft 0.3.0 downloadEvidence |
| Gate | No missing policy; user explicitly requested U04. Synthetic auth only, backend remains access authority |
| Acceptance/tests | Selected metadata download; original byte/size/hash read-back; failures, duplicates, selection/session cancellation; URL cleanup; real producer integration and previous-checkpoint regressions |
| Handoff | Complete after user-authorized merge 9444ef703ea88cba52280024c11887492b6053bd and post-merge real API smoke; 48 frontend pass, 69 backend pass/1 Windows symlink skip, real API/browser original read-back and contract/types/build/DESIGN pass; exact evidence in PREIMPLEMENTATION_REVIEW U04 section. User now explicitly authorizes finishing, committing, pushing and merging U04 only; preserve full FEATURE_SCOPE |
