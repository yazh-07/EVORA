# EVORA scoped agent assignment templates

Coordination-branch draft 0.3.0, not a running app. Four people each work on one module; confirmed GitHub-handle assignments and integration coordination are in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). Full initial proposal scope is fixed. Use the canonical phase/checkpoint ledger in [ROADMAP.md](ROADMAP.md). Assign one catalog row, not an entire module, milestone or full dashboard. Codex fills the task card from recorded repository decisions before editing. Missing common-base/allowed-path choices or a shared G/I assignee need a short clarification, not a guessed assignment.

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
