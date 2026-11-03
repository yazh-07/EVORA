# EVORA scoped agent assignment templates


### U05D assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | U05D / 1C / M4 Investigator Application / JebasJ; explicit bounded user handoff; execution 2026-11-04 |
| Branch/common contract base | Initially clean `feat/u05d-start-analysis-ui`; actual HEAD and local `docs/coordination-foundation` **d49a6baa84a0a919131963efdd918634eb0e4856**. Supplied full SHA `d49a6ba2e604ce19ad37c15243aa71ec5053f1d8` differs. OpenAPI 0.3.0 unchanged |
| Allowed paths | `frontend/src/cases/`, `frontend/test/`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; explicit shared-document handoff. No spec/backend/dependency edits or stage/commit/push/merge authorization |
| Real dependency versions | U01 merge f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029; A05 266f39f4df18e261a156240ff4d828f74afafe2b; F08B d49a6baa84a0a919131963efdd918634eb0e4856. A01B/A05B/A06/A15 and completed 0/1A/1B producers are merged ancestors |
| Interface/dependency handling | U01 typed bodyless startAnalysis plus UUID header -> A05 accepted AnalysisRun -> serial getAnalysisRun -> confirmed completed workspace pin. Real HTTP/FastAPI/SQLite/processing/analysis acceptance, explicit transactional Neo4j double |
| Acceptance | Explicit action, unique UUID keys and busy guard, queued/running/failed/completed states, default 750 ms serial polling, terminal stop, completed GET before atomic pin, prior completed pin survives new pending/failed work, safe 400/401/404/network alerts and fresh-key retry, case/session/unmount abort and stale-delivery rejection |
| Resolved producer/consumer handoff | M3 whale2186 A05 produces immutable completed runs; M4 JebasJ U05D exposes `useAnalysisWorkspace` in `frontend/src/cases/StartAnalysis.tsx` with caseId and nullable analysis_run_id. U06/U07/U07B must consume this pin for every read/page, reject mismatched IDs and reset view data on pin changes. No downstream UI implementation or I01 closure claimed; no unresolved U05D contract gate |
| State/next | In Progress pending review/publication. Verification and limitations in PREIMPLEMENTATION_REVIEW.md. Next bounded consumer task U06; U07/U07B retain their own acceptance, then I01 exit evidence. Checkpoint 1C and M4 remain open |



### A06 assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | A06 / 1C / M3 Evidence Fusion and Adaptive Triage / whale2186; explicit bounded user handoff; execution 2026-11-04 |
| Branch/common contract base | Clean initial `feat/a06-triage-history-endpoints`, actual HEAD **ca6e379ffd0c73332f47fdf6ce3132d1dfc39c99**. Supplied full SHA `ca6e37901ea2bdfad73bc87e9ecbf483015a6b0c` differs. Unchanged OpenAPI 0.3.0 |
| Allowed paths | `backend/triage_endpoints.py` (chosen), `backend/app.py`, `backend/tests/test_triage_endpoints.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec/frontend/dependency edits or stage/commit/push/merge |
| Real dependency versions | A04 7858cce3cc21dbf0efe680094b28c3182b72d336, A05 266f39f4df18e261a156240ff4d828f74afafe2b, A01B ba7db7faa449e62a3ee0e3a74ddd8ef8b4f58887, A05B ca6e379ffd0c73332f47fdf6ce3132d1dfc39c99; preceding G02/A01/A02/A03/A03B/G01D and completed checkpoint producers are integrated ancestors |
| Interface/dependency handling | Real completed A05/A01B immutable SQL snapshots/results and A04 sorting -> listTriage/getTriageHistory -> M4 U06/U06B and I01. Real HTTP/SQLite/processing/analysis publication; explicit transactional Neo4j double |
| Acceptance | Exact snapshot membership/total, selected ID even empty/unscored, UTC/UUID completed selection, pinned score order then UUID with unscored last, precompletion live uploads, stable upload-between-pages behavior, immutable automated history and 400/401/404 negatives; actual OpenAPI schema validation |
| Communication queue: U09 storage handoff | No override table/producer exists at this base. Conditional `priority_overrides` reader uses PriorityOverride wire columns, same-case evidence and latest UTC/UUID; no migration/write API introduced. Test-only schema-derived storage double proves live overlay ordering/history behavior. M4 JebasJ U09 must coordinate its actual storage adapter/migration with M3 whale2186 A06 and prove authorized append/audit plus I02B override-between-pages. This future producer gate does not block completed automated reads or imply real U09 integration |
| State/next | In Progress pending review/publication; exact verification/limitations in PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 and M3 remain open. Next dependency-ready M4 handoff U06, followed by I01 integration when its other dependencies are ready; later M3 A07 retains its 2A/P06 gate |

### A05B assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | A05B / 1C / M3 Evidence Fusion and Adaptive Triage / whale2186; explicit user assignment; execution 2026-11-04 |
| Branch/common contract base | Clean initial `feat/a05b-expose-graph-findings`, actual HEAD **266f39f4df18e261a156240ff4d828f74afafe2b**. Supplied full SHA `266f39fec07172fe4fecfdb33f20ee43dbd0fa2d` differs. OpenAPI 0.3.0 unchanged |
| Allowed paths | `backend/findings.py` (chosen), `backend/app.py`, `backend/tests/test_graph_findings.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no frontend/spec/dependency edits or stage/commit/push/merge |
| Real dependency versions | A05 266f39f, A01B ba7db7f, G01D b0fd1f9, A04 7858cce, A03B 2eca04b, A03 ec4ab3c, A02 51ee2ed, A01 11961c4, G02 d1f16ef and completed checkpoint producers in actual common base |
| Interface/dependency handling | A05/A01B verified completed immutable SQL outputs -> getGraph/listFindings -> M4 U07/U07B and A06 same-run consumers. Real processing/analysis/publication logic; default tests explicitly double Neo4j and synthetic actors/data |
| Acceptance | Completed same-case selectors, UTC-created-time/UUID latest ordering, hidden pending/failed output, historical pinning across newer publication, empty selected IDs, authoritative pagination totals and OpenAPI validation, 400/401/404 negatives |
| Read policy/queue | Explicit user instructions resolve this task to SQL graph_json/findings_json reads after A01B completion; no live Neo4j read/rebuild is performed by these endpoints. Consumers receive the exact SQL-published snapshot. A01B live-projection verification/rebuild helper remains separate. No unresolved A05B contract choice |
| State/next | In Progress pending review/publication; actual results/limitations in PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 and M3 remain open. Next bounded M3 handoff A06; M4 U07/U07B and I01 retain their own acceptance |

### A05 assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | A05 / 1C / M3 Evidence Fusion and Adaptive Triage / whale2186; explicit user assignment; execution 2026-11-04 |
| Branch/common contract base | Clean `feat/a05-analysis-run-lifecycle`, actual HEAD **ba7db7faa449e62a3ee0e3a74ddd8ef8b4f58887**, matching the A01B merge; supplied full hash `ba7db7fa3c15eb18a2bc4b8686d1a166ad292ff2` does not exist locally. No fetch or publication claimed. Draft OpenAPI 0.3.0 unchanged |
| Allowed paths | `backend/analysis.py`, `backend/app.py`, `backend/tests/test_analysis.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec/frontend/dependency edits; no stage/commit/push/merge |
| Real dependencies | A01B ba7db7f, G01D b0fd1f9, A04 7858cce, A03B 2eca04b, A03 ec4ab3c, A02 51ee2ed, A01 11961c4, G02 d1f16ef and completed 0/1A/1B producers are integrated ancestors of the exact base above; F00/P14/P14C real authorization/provenance/publication paths consumed |
| Acceptance | Bodyless UUID-key acceptance/replay before freeze; current new-key snapshot with exact sorted manifest hash; digest-based contract triggers; immutable pipeline outputs and verified A01B publication; polling, failure/restart/race/source/case negatives |
| Interface | M2 completed immutable processing outputs → A05 frozen inputs → A01/A02/A03/A03B/A04/A01B → U05D polling and later A05B/A06 reads; backend owns SQLite/Neo4j |
| Decision queue | User-requested AnalysisRunPage/pagination conflicts with the sole OpenAPI listAnalysisRuns array and no query parameters. Asked whether to retain the existing contract or authorize coordinated schema/types/fixtures scope. Producer A05 and M4 run-history consumers cannot use different response shapes. This gate affects the list endpoint only |
| Regression handoff | Existing `backend/tests/test_skeleton.py` exact startup-table assertion omits the two required analysis tables. One-line expected-list update requested because that file is outside allowed paths; no unauthorized edit |
| Verification/state | In Progress; actual commands/results and test doubles in `PREIMPLEMENTATION_REVIEW.md`. Checkpoint 1C/I01 stays open; next bounded tasks A05B/A06 and F08B/U05D integration after A05 review |

### A01B assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | A01B / 1C / M3 Evidence Fusion and Adaptive Triage / whale2186; explicit user assignment and shared-file handoff; execution 2026-11-04 |
| Branch/common contract base | Clean `feat/a01b-versioned-graph-projection`, actual HEAD **b0fd1f983c7369247cd915f6f94b68685a1d4629**; supplied `b0fd1f91b4ca2efb72b834e565983758b97d1b32` differs. No fresh fetch claimed. Unchanged OpenAPI draft 0.3.0 |
| Allowed paths | `backend/graph_projection.py`, `backend/tests/test_graph_projection.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. No spec/frontend/dependency edits or stage/commit/push/merge authorization |
| Real dependency commits | A01 **16e6429a22fa6250fdeebc4c47f6ab0a4d0349bf**, A02 **ca6cb6727bcb87a31bc8b1b9cc18efbc42d99ed0**, A04 **7dd450610b279cc77a39ff6b0e9e5c4132183d2e**, G01D **421f10ec4d229c909522bf9d65f06e063f65d115** are integrated ancestors; G02/A03/A03B and Checkpoints 0/1A/1B preserved |
| Interface handoff | M1/M2 immutable SQLite sources and frozen accepted run -> M3 SQL outputs -> G01D evora-graph/1 `Node`/`Edge` partition -> verified SQL completed pointer -> A05/A05B/A06. Reuse existing constrained labels instead of introducing unconstrained `CaseGraphNode`/`CONNECTED` storage. All requested wire properties retained |
| Acceptance/dependency handling | SQL running run/output committed first; atomic idempotent Neo4j replacement and exact count/property/endpoint verification; SQL completion last. Failures use safe errors; reads hide noncompleted partitions. Rebuild uses immutable SQL. A05 acceptance/auth/idempotency API is absent: tests explicitly supply its frozen accepted record, never invent production actor/key/snapshot. Real merged processing/A01/A02/A03/A03B/A04 and real Neo4j acceptance are exercised separately from synthetic driver controls |
| State/next | In Progress, locally verified pending review/integration. 17 A01B tests pass with real Neo4j (16 pass/one skip by default); 327 completed-checkpoint regressions and required contract/frontend checks pass. Exact commands/broader NLP limitations in PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C stays open. A05 is the next bounded M3 handoff, including startup worker scheduling/auth/trigger/algorithm metadata and F08B audit integration. No later task started |

### G01D assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | G01D / 1C / M3 Evidence Fusion and Adaptive Triage / whale2186, explicit user assignment and shared-file handoff |
| Branch/common contract base | Clean `feat/g01d-neo4j-connection-setup` at **7858cce3cc21dbf0efe680094b28c3182b72d336**, matching local `docs/coordination-foundation`; supplied hash `7858ccefc692c89f5bc5cf935f111ba716a5a92a` is absent locally. Unchanged OpenAPI draft 0.3.0. Execution date 2026-11-04 |
| Allowed paths | `requirements.txt`, `backend/graph_db.py`, `backend/tests/test_neo4j_setup.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; only new dependency pins `neo4j==6.4.1`, `pytz==2026.1`. No spec/frontend edits or stage/commit/push/merge authorization |
| Dependencies | G01 **e0257a6ad231105b93ae98a97f176ed233a25412**, real merged backend skeleton in the reviewed base; completed Checkpoints 0/1A/1B and merged A01/A02/A03/A03B/A04/G02 remain regression dependencies. G01D needs no processing/model/scoring/provider choice |
| Internal producer/consumer | Private backend config/driver/schema harness -> A01B partition persistence/recovery, then A05 publication. Schema version 1 uses `Node` nodes and `Edge` relationships, each unique by `(case_id, analysis_run_id, id)`, with both case/run and case/source-ID indexes. Fixed DDL identifiers, no interpolated evidence/config values |
| Acceptance/tests | Validated environment/defaults, required private password, bounded acquisition/connect/write and no automatic retries, typed sanitized connectivity/auth/schema failures, explicit lifecycle, idempotent constraints/indexes; mocked fault controls plus actual refused/stalled sockets and optional disposable real Neo4j integration. Exact results/versions/doubles/limitations in PREIMPLEMENTATION_REVIEW.md |
| State/next | In Progress; no checkpoint/module completion. Next bounded M3 handoff is A01B after G01D review/integration; A05 follows. No later task started |

Coordination-branch draft 0.3.0, not a running app. Four people each work on one module; confirmed GitHub-handle assignments and integration coordination are in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). Full initial proposal scope is fixed. Use the canonical phase/checkpoint ledger in [ROADMAP.md](ROADMAP.md). Assign one catalog row, not an entire module, milestone or full dashboard. Codex fills the task card from recorded repository decisions before editing. Missing common-base/allowed-path choices or a shared G/I assignee need a short clarification, not a guessed assignment.

### A01 assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | A01 / 1C / M3 Fusion and Adaptive Triage / whale2186, matching the ROADMAP module table and explicit user handoff |
| Branch/reviewed common contract base | `feat/a01-case-graph-nodes`, clean initial HEAD **d1f16ef02a62c2ce94bdd19539037a7b60cecabf** on the coordination history. Supplied full hash `d1f16ef6ba9132204c311c6d3bc8f15d2a764d26` differs from the actual Git object. Unchanged `specs/openapi.yaml` draft 0.3.0 is the sole HTTP contract |
| Allowed paths/shared handoff | `backend/graph_nodes.py`, `backend/tests/test_graph_nodes.py`, `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. User authorizes these bounded shared ledger edits; no spec/frontend/dependency changes or staging/commit/push/merge authorization |
| Real dependencies | P03B **c58e7f24e4f7c21fc5120dc7288d02f960b58006**, P03C **bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca** are merged ancestors. Real F03/F04/P04/P04B/P05/P05B producers and completed I00B **740f406** are present, plus G02 merge at the reviewed base |
| Producer/consumer handoff | M2 normalized candidate Entity/Event wire mappings and M1 Evidence metadata -> pure source-UUID node builder -> M3 A02, then A01B/A05. Caller authorizes/selects coherent completed inputs; supplied Evidence records define the same-case reference allowlist |
| Acceptance/policy | Preserve source UUID/text; no anonymous nodes or node observation-ID requirement; strict canonical UUID/case/reference/nonblank checks; unique sorted evidence unions; deterministic `(kind,id)` order; conflicting duplicate category/kind/label fails closed. Five-field immutable node serialization validates against the real OpenAPI bundle |
| Tests/dependency handling | Synthetic negative fixtures and real merged FastAPI/SQLite network/GPS processing through source APIs, source-locator joins, original-byte/hash read-back, and foreign-case rejection. Actual command results and environment limits are recorded in A01 verification in PREIMPLEMENTATION_REVIEW.md |
| State/next | In Progress, locally verified and awaiting review/integration; 19 A01, 33 G02, 122 coordination, 101 frontend and 327 completed-checkpoint backend tests pass, with build/real HTTP smoke/contract/types/DESIGN checks. Checkpoint 1C remains In Progress. Next bounded M3 row A02 requires a separate handoff; no next task started |

### G02 assignment — 2026-11-03

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | G02 / 1C / M3 Fusion and Adaptive Triage / whale2186 |
| Scope & Acceptance | Version all seven factor functions/ranges, independence/confidence/count/quality rules, proportional missing-factor weights, score cap/bands/ties and canonical positive/counterexample outputs; unprocessed evidence not scored. Resolves C-05 policy. |
| Branch & Base | `feat/g02-triage-scoring-policy` off `740f406` (`docs/coordination-foundation`) |
| Allowed Paths | `backend/triage/`, `backend/tests/test_triage_policy.py`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`, `docs/COMMUNICATION.md` |
| Verification | 33 triage unit tests passing in `test_triage_policy.py`, 101 frontend tests, 122 coordination tests, strict OpenAPI bundling and types. |

### F08 assignment — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/module/owner | F08 / 1B / M1 Evidence Foundation / sharmelas-925, per confirmed ROADMAP module table and explicit user assignment |
| Branch/reviewed common contract base | `feat/f08-processing-audit`, clean starting HEAD **6980b4d0b2fd14a6bf372ae84cb7ab8e78b38d93** on the local coordination history; unchanged OpenAPI draft 0.3.0 and CONTRACTS.md. User-supplied full hash `6980b4df3ea582d909ca3a628a55dbb8214309a4` is unavailable locally; exact actual HEAD recorded rather than claiming that object |
| Allowed paths | `backend/audit.py`, `backend/processing.py`, `backend/tests/test_processing_audit.py` (or test_audit.py), `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. No spec/frontend/dependency edits; no staging/commit/push/merge authorization |
| Real dependencies | F06 merge **1b5166d91e0f3b86b85585d714a917a3efc82d44**; P04 merge **f851dd11fd8f7e11140317cf44d022a9999044dd**; P14 merge **c03361b8171e6506d2c160a85cc1e89e76315fb3**. P14C verified publication merge **920331d95fdd359f1e20cfbcfba48fc6e2afb292** and F07 list API also present in actual base |
| Producer/consumer handoff | M2 terminal processing/recovery -> M1 safe append-only AuditEvent -> existing authorized F07 list API and I00B. Run/version reference joins to private frozen configuration and successful versioned provenance; failed runs have no fabricated completed provenance |
| Acceptance | Exactly one terminal event with original actor/case/Evidence/run/version/state/time, safe diagnostic only; no sensitive audit/log contents; atomic status/output/provenance/audit rollback, replay/concurrency/recovery deduplication, case isolation and UTC listing, SQL append-only guards |
| Tests/doubles | 13 focused tests and full 420 backend tests PASS, 122 coordination and 48 frontend PASS; real HTTP intake regression and contract/types/build/DESIGN checks PASS. Real ASGI/SQLite/original/parser/provenance producers; synthetic identities/fixtures, explicit scheduler/registry/SQL/commit failure injections only. Exact commands and environment caveats in PREIMPLEMENTATION_REVIEW |
| State/next | In Progress pending review/integration; no checkpoint/module completion. Next handoff is I00B after its remaining real UI dependencies; later M1 F08B requires A05 and its own assignment. No next task started |

### I00 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint | **I00 / 1A final exit gate**: real authorized create/list/upload/hash/metadata/download/audit across M1 and M4 |
| Owner | **whale2186 / joint integration coordination**, explicitly assigned by the user alongside the existing M3 responsibility; M1 owner sharmelas-925 and M4 owner JebasJ retain their interfaces |
| Branch/common contract commit | `feat/i00-authorized-intake-gate`, clean starting HEAD **c0561bbb3978e37395218bf1a771ecd562d3c2dd**; unchanged `specs/openapi.yaml` draft 0.3.0 and `docs/INTEGRATION.md` |
| Allowed paths | `frontend/test/cases.integration.mjs`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no backend, spec or dependency edits |
| Dependencies | F00, F01, F02, F03, F04, F05, F06, F07, F09, U01, U02, U02B, U03, U04 integrated on c0561bb. Direct catalog prerequisites F09/F07/U02B/U04 are real merged producers; no producer doubles |
| Acceptance | Preserve existing real HTTP/SQLite intake regression; verify `uploadEvidence` action with same-case target and actor, UTC monotonic timestamps, safe fields, repeated reads, exact unchanged SQL/original-file snapshots and standard foreign/missing 404 ApiError. Run the full verification matrix before sealing 1A |
| Completion | **Complete**. All requested test assertions pass; real integration exits 0. 116 backend, 122 coordination, 48 frontend tests pass; full smoke passes. Checkpoint 1A is sealed and Complete |
| Next handoff | Checkpoint 1B is unblocked and active. Next tasks: M2 P01/P02 parsers |

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
| Implementation policy | Existing current membership guard, 400/401/non-leaking 404. Deterministic oldest-first UTC creation time ascending, then ID ascending (fractional precision normalized); total/page share one read snapshot. No private-source join, payload logging, new filter/selector or frontend feature |
| Required proof | Real F03 upload → authorized list/schema read-back, empty/beyond-end/default/boundary/tied pagination, two actors/cases/current membership, malformed input/auth, foreign/missing equivalence, no private values/storage fields, read-only listing and storage failure; shared contract/coordination/backend/frontend regressions |
| Verification | **15 focused F07 pass**, selected foreign/missing failure passes; **102 backend run: 101 pass, one existing Windows symlink skip**; **122 coordination and 48 frontend pass**. Contract lint/bundle/generated strict types, API freshness/typecheck/build, DESIGN and whitespace pass. Real localhost upload/audit API/SQL/original read-back and prior case/upload/download real-client integration pass |
| Handoff | **Complete**, user-authorized PR #13 merged into `docs/coordination-foundation` at **6687d7cbd820fc4db820d85e4dcd518dd941c99d**, containing final task commit **e7cd61402e87d2afbed1eafa8ab930e2597dea2b**. Ubuntu/Windows CI pass (Run **41299455397**); exact merged-tree audit API/SQL and prior case/upload/download client checks pass. Full initial scope unchanged. Next M1 task F09; shared I00 still requires an explicit assignee. No F09 implementation included |

### F09 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint and acceptance | **F09 / 1A**: cross-case access and error regression across every implemented M1 read/write operation; foreign-case, missing identity and nonexistent-ID checks where the operation has case/resource identifiers |
| Module/person | **M1 / sharmelas-925**, explicitly assigned by the user with commit/push/merge authorization after verification |
| Branch/common commit | `feat/f09-m1-access-regressions` / **53bac04ed4b94f10334dc92a5ecead2c11dfecad**, clean local base matched freshly fetched origin before task inspection/branching; no existing F09 branch/worktree |
| Allowed paths | `backend/tests/test_m1_access.py`, `backend/README.md`, bounded records in `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. Bounded corrections in existing `backend/cases.py`/`backend/evidence.py` if the suite demonstrates a declared-contract error regression; no unrelated routes or new feature/schema |
| Dependencies | Accepted merged F00/F05/F07, real F01/F02/F03/F04/F06, current case membership, SQLite/private originals and shared ApiError from unchanged draft 0.3.0 |
| Coverage boundary | createCase/listCases/getCase/uploadEvidence/listEvidence/getEvidence/downloadEvidence/listAuditEvents. Create/list have no case-ID parameter: test authenticated actor ownership/filtering and rejected forged body IDs, not invented foreign-ID semantics. Route inventory must match the suite |
| Required proof | Valid same-case read/write baselines; missing/invalid/duplicate/replaced identity; both actors against foreign/missing cases, mismatched/absent resources, revoked membership; declared input errors and pagination boundaries; safe bodies/schema; no denied-write metadata/audit/private-file changes; required shared regressions and real HTTP/client smoke |
| Gate | C-03's synthetic development policy applies; no automatic token expiry/provider is invented. Actual production expiry remains outside this task. No decision blocks these existing M1 route regressions |
| Verification | **14 F09 tests pass**; full **116 backend run: 115 pass, one known Windows symlink skip**; **122 coordination and 48 frontend pass**. Shared lint/bundle/types/freshness/typecheck/build/DESIGN/whitespace pass. Real eight-operation localhost auth matrix, scoped isolation/no-side-effect checks and existing client integration pass. The matrix caught case/evidence list SQLite overflow on valid huge offsets; two bounded beyond-end corrections now return proper empty pages |
| Handoff | **Complete**, user-authorized PR #14 merged at **868d697f297748614befdcc6af8a66370b48240b**, containing task commit **4a69cafae6fb02c770f552c13b14430ac57e5e99**. Ubuntu/Windows CI pass (Run **41301012667**); exact merged-tree real M1 API matrix and prior client regressions pass. No F08, M2/M4 task or shared I00 implementation included. Next I00 is a shared API/UI intake gate requiring an explicit assignee; later M1 F08 also waits for real P04/P14 processing prerequisites |

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

### P01 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P01 / 1B / M2 yazh-07; parse synthetic network CSV into source-located candidate observations, known device/IP/raw time/row read-back and invalid header/row rejection |
| Branch/common base | feat/p01-network-csv / **22673d909b0860663b001269cefa2ac6f302a881**, freshly fetched shared docs/coordination-foundation; isolated worktree preserves original dirty checkout |
| Paths | User approved backend/parsers/network_csv.py, backend/tests/test_network_csv.py, backend/README.md and bounded assignment/policy/verification records in docs/AGENT_TASKS.md, docs/COMMUNICATION.md, docs/ROADMAP.md, docs/PREIMPLEMENTATION_REVIEW.md; no other producers/spec/dependencies/frontend |
| Dependencies | Real G01 e0257a6 and F05 d24312f merged in verified base, with completed 0/1A; actual F00/F01/F03/F05 used for authorized upload/download integration |
| Policy/gate | User approved UTF-8 optional BOM, exact ordered timestamp/device_id/ip_address/event columns, strict CSV atomic rejection, nonblank required values, valid IP, 50 MiB bytes and 100000 data rows; raw timestamps/values retained, P03 normalization separate |
| Input/output | Existing Observation schema only; immutable network.device/network.ip/network.event observations per row, observed_at_raw retained, normalized_value initially identical to logical CSV cell; source locator row/column including physical line span; 0 unavailable extraction-score sentinel, never a measured probability or source reliability. Caller supplies case/evidence/run UUID context; P04 owns real run persistence/idempotency |
| Verification | 14 focused pass; full backend 129 pass/1 Windows symlink skip, 48 frontend pass; real original/I00 intake regression and contract/types/build/DESIGN pass; exact proof/limits in PREIMPLEMENTATION_REVIEW P01 section. No fake processing API/run producer |
| Handoff | Complete after merge cab08f1c38745255ca1c0a210636476b84bad43c and passing post-merge focused/real I00 smoke; user explicitly authorized finish/test/push/merge for P01 only. Preserve entire FEATURE_SCOPE and approved additions. P02 is next M2 row subject to fresh handoff |

### P02 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P02 / 1B / M2 yazh-07: parse synthetic GPS into source-located observations; device/raw time/coordinates match; invalid coordinates/zone explicit |
| Branch/base | feat/p02-gps-csv / **4bc8f307a039d7c91bcc687bb64267fbe80fb6b8**, clean fetched shared base; isolated worktree leaves all existing work untouched |
| Allowed paths | backend/parsers/gps_csv.py, backend/tests/test_gps_csv.py, backend/README.md and bounded records in AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW; no P01 producer/spec/frontend/dependency edits |
| Dependencies | Real G01 e0257a6/F05 d24312f integrated; P01 cab08f1 source CSV reader available unchanged as internal helper, not a new catalog gate; 0/1A regressions required |
| Approved policy | User approved P01-equivalent strict UTF-8/BOM CSV and 50 MiB/100000-row caps; exact timestamp/device_id/latitude/longitude columns, nonblank fields; finite decimal latitude [-90,90]/longitude [-180,180]; reject malformed timestamps/bad explicit offsets, missing timezone stays unknown; no UTC normalization |
| Output | Existing Observation fields only: frozen gps.device/gps.latitude/gps.longitude per record, decoded logical raw cells/time, normalized_value initially raw, no observed_at_utc/entity_key, 0 unavailable-score sentinel; caller case/evidence/run UUID context only |
| Proof | 17 focused PASS; full backend 146 PASS/1 Windows symlink SKIP, 48 frontend PASS; real original/I00 regressions and contract/types/build/DESIGN PASS. Exact commands/doubles/limits in PREIMPLEMENTATION_REVIEW P02 section; run UUID context explicitly synthetic |
| Handoff | Complete after merge 389652c358fab4b3b20565d592db520549028b8f and passing post-merge smoke; explicit user authorization to implement/test/commit/push/merge P02 only; preserve FEATURE_SCOPE. Next M2 row P03 after real P01/P02 integration; no P03 implementation here |

### P03 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P03 / 1B / M2 yazh-07: exact source time/GPS normalization preserving originals, timezone uncertainty explicit |
| Branch/base | feat/p03-normalization / **ac432e10a6a1c4ff19ae36b49cded514d0e78846**, clean fetched common base, isolated worktree; no P03 claim active |
| Allowed paths | backend/parsers/normalization.py, backend/tests/test_normalization.py, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records; no parser producer/spec/frontend/dependency edits |
| Dependencies | Actual integrated P01 cab08f1 and P02 389652c (publications 4bc8f30/ac432e1), real originals from F03/F05/G01, completed 0/1A regression |
| Approved policy | Explicit numeric-offset/Z timestamps to UTC without fractional rounding; missing/ambiguous/invalid/-00:00 unresolved, raw retained/no UTC, reason internal; exact GPS normalization with scientific fallback to avoid excessive expansion; new immutable values preserve IDs/locators/raw, no historical DB mutation |
| Inputs/outputs | P01/P02 frozen observations -> frozen normalized observation plus internal time/coordinate status envelope; existing Observation wire only; unchanged score/kind/UUID context; no entity keys/processing API/public status fields |
| Proof | 18 focused PASS; full backend 164 PASS/1 Windows symlink SKIP; frontend 48 PASS, coordination 122 PASS, real I00 HTTP smoke and contract/types/build/DESIGN PASS. Goldens/unknown/precision/immutability/schema and actual original/P01/P02 integration; synthetic run UUIDs, in-process ASGI focused transport and remaining limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge e9f01f586916f38c480a40ffc8aa3eb72fd146ff and passing 18 focused/verifier/real I00 post-merge smoke; task commit d186af38f84479794889d309765f60be189cf790 pushed. Explicit user authorization covers P03 only. Preserve full FEATURE_SCOPE; Checkpoint 1B open. Next M2 P03B, no following task started |


### P03B assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P03B / 1B / M2 yazh-07: candidate identifier keys and source-backed Entity records; D-7/D-8 distinct, no inferred person identity |
| Branch/base | feat/p03b-candidate-entities / **59de4686f4a59bff25528d386ce458d259d96e6c**, clean fetched shared docs/coordination-foundation; isolated worktree preserves existing work |
| Allowed paths | User approved backend/parsers/candidate_entities.py, backend/tests/test_candidate_entities.py, backend/README.md; bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No producer/API/database/dependency/frontend edits |
| Dependencies | Actual merged P01 cab08f1, P02 389652c and P03 e9f01f5 with publication 59de468; completed 0/1A and real F03/F05 originals |
| Policy | Approved exact case-sensitive device:<value> and ip:<P01 normalized_value>, one explicit case, identical-key grouping only; immutable copies retain source IDs and uncertainty; confidence 0 unavailable; mixed-case/conflicting inputs reject atomically |
| Input/output | Real P03 NormalizationResult tuple -> new immutable source-preserving observations with existing entity_key plus existing-schema Entity tuples; no stored output mutation or processing/list API claim |
| Proof | 15 focused PASS; full backend 179 PASS/1 existing Windows symlink SKIP, frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN and real I00 HTTP regressions PASS. Actual original/P01/P02/P03 chain and negative/source/schema/immutability controls; synthetic auth/run context and ASGI transport disclosed in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c58e7f24e4f7c21fc5120dc7288d02f960b58006 and passing 15 focused/verifier/real I00 post-merge smoke; task commit afed7256991aa7cd7c3037aa5d4e318f82019fbe pushed. P03B only; preserve FEATURE_SCOPE including additions. Checkpoint 1B open. Next M2 P03C; no later task started |


### P03C assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P03C / 1B / M2 yazh-07: source-backed row events/time/participants with original Observation/Evidence references; invalid time never fabricated |
| Branch/base | feat/p03c-source-events / **e68969df9f19f8f78320a708bc3cb80a3c05b85d**, clean fetched shared docs/coordination-foundation, isolated worktree; no active P03C claim |
| Allowed paths | User approved backend/parsers/source_events.py, backend/tests/test_source_events.py, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records; no API/DB/dependency/existing-producer/frontend edits |
| Dependencies | Actual integrated P01 cab08f1, P02 389652c, P03 e9f01f5; additionally consume actual P03B c58e7f2 Entity IDs for participant joins. Completed 0/1A; real F03/F05 source chain |
| Approved policy | One candidate per complete network/GPS row, source-report summaries, network.activity/gps.location; all row observation/evidence IDs; actual same-case Entity participants; raw/P03 UTC/uncertainty preserved, confidence 0 unavailable; atomic rejection of invalid row/context/time/participants |
| Input/output | Real P03B CandidateProjection over P01/P02/P03 -> frozen source-event envelopes carrying existing Event wire only; no synthetic identity, stored-output mutation or processing/list API |
| Proof | 15 focused PASS; full backend 194 PASS/1 existing Windows symlink SKIP, frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN and real I00 HTTP regressions PASS. Actual source chain/schema/source/participant/immutability and negative controls; synthetic run/auth and ASGI transport disclosed in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca and passing 15 focused/verifier/real I00 post-merge smoke; task commit f75ffa32a154987db82bdcdd8b28047ee05bf054 pushed. P03C only; preserve entire FEATURE_SCOPE/additions. Checkpoint 1B open. Next M2 P04, no next task started |


### P04 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P04 / 1B / M2 yazh-07: one actual processing lifecycle via startProcessing/getProcessingRun/listProcessingRuns; stable replay/conflict, immutable outputs, no partial success |
| Branch/base | feat/p04-processing-lifecycle / **9bec1653525694c01ef82c6a3cd12f2beea8493c**, clean fetched shared docs/coordination-foundation, isolated worktree |
| Allowed paths | Approved backend/processing.py, focused backend/tests/test_processing.py and necessary processing table inventory in backend/tests/test_skeleton.py, backend/app.py router/startup, processing-owned SQLite tables, backend/README.md; bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. M1 tables/producers/spec/frontend/dependencies unchanged |
| Dependencies | Real F00 94aa2a8/F05 d24312f/P01 cab08f1/P02 389652c plus integrated P03/P03B/P03C actual output chain; completed 0/1A regressions |
| Approved policy | Bodyless/keyed start, frozen input hash/config, local background queued/running/completed or failed; network/GPS actual adapters; unsupported kind 415 before acceptance, supported malformed CSV accepted failed with safe code; actor/case/operation replay/conflict/new-key retry; interrupted queued/running jobs fail on restart |
| Input/output | Authorized original -> actual P01/P02/P03/P03B/P03C -> immutable private atomic SQL outputs/completed run. Existing ProcessingRun wire only; no listObservations/entities/events endpoints here |
| Proof | 21 focused PASS; full backend 215 PASS/1 existing Windows symlink SKIP, frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN and real processing/I00 HTTP smoke PASS. Fault/scheduler doubles and deployment/test limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge f851dd11fd8f7e11140317cf44d022a9999044dd and passing 21 focused/verifier/real processing/I00 post-merge HTTP smoke; task commit 32d78e588d1fc02078834cd62b57a176608ea16a pushed. P04 only; preserve full FEATURE_SCOPE/additions. Checkpoint 1B open. P04B next; P14/P14B/P14C/P05/P05B remain required later work |


### P04B assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P04B / 1B / M2 yazh-07: listObservations over real latest completed or explicitly pinned historical processing outputs; filters/pagination/history, no pending/failed/foreign output |
| Branch/base | feat/p04b-observation-list / **bb3928440ebf39d016e14fb328f045d98fd68bb9**, clean fetched shared docs/coordination-foundation; isolated worktree, no active P04B claim |
| Allowed paths | Approved backend/observations.py, backend/tests/test_observations.py, backend/app.py router wiring, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No DB/schema/producer/spec/frontend/dependency edits |
| Dependencies | Actual P04 merge f851dd1/publication bb39284, real F00/F03/F05/P01/P02/P03/P03B/P03C chain; completed 0/1A regression |
| Approved policy | Existing contract selectors/limits; exact UTC finished_at then UUID latest per evidence; evidence UUID then Observation UUID page order; one consistent read snapshot per response; invalid/foreign/incomplete/mismatched selectors 404; no completed output empty; selected missing/corrupt output fails closed, no silent fallback/partial data |
| Input/output | Real immutable P04 SQL -> existing ObservationPage only; raw/normalized/time/source/run/Entity keys preserved, no new public field or listEntities/listEvents API |
| Proof | 16 focused PASS; full backend 231 PASS/1 Windows symlink SKIP, frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN and real Observation/processing/I00 HTTP regressions PASS. Selection/scheduler/corruption/transcript-schema fixtures and limits disclosed in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c29e517f218c0851a9959cfa389b093242a255ab and passing 16 focused/verifier/real Observation/I00 post-merge HTTP smoke; task commit 5baa2f631f788466f6787d331734adda0f26dfca pushed. P04B only; preserve full FEATURE_SCOPE/additions. Checkpoint 1B open. Next M2 P05; no next task started |


### P05 assignment — 2026-11-01

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P05 / 1B / M2 yazh-07: listEntities from actual source-backed candidate records, every Evidence/Observation citation same-case, no cross-case leakage |
| Branch/base | feat/p05-entity-list / **abeb516ba879636afb18aaa2a800b2143915e0f7**, clean fetched shared docs/coordination-foundation, isolated worktree; no active P05 claim |
| Allowed paths | Approved backend/entities.py, backend/tests/test_entities.py, backend/app.py router wiring, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No DB/schema/producer/spec/dependency/frontend/Event API edits |
| Dependencies | Actual P03B c58e7f2 and P04B c29e517 (publication abeb516), real P04/F00/F03/F05 and source parser/normalizer/event chain; completed 0/1A regressions |
| Approved policy | Latest completed per evidence via exact UTC/UUID selection, unchanged persisted Entity IDs/keys/labels/confidence/references; identical keys with different record IDs remain separate. Same-case selected Observation/Evidence citations validated; missing/corrupt data fails whole read safe 404. Contract pagination, candidate_key then Entity UUID order, one read snapshot per response; no new selectors |
| Input/output | Actual immutable P04 Entities and cited Observations -> existing EntityPage only; no identity inference, confidence boost, regrouping/regeneration or source/history mutation |
| Proof | 17 focused PASS including real Uvicorn HTTP; full backend 248 PASS/1 existing Windows symlink-permission SKIP (249 run), frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN and real I00 loopback PASS. Actual processing/source citations, negatives, exact selection/concurrent publication/read-only history; doubles and limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge 04af24f1c44abbc8059b0c006d9079d271ced947 and passing 17 focused/verifier/real I00 post-merge smoke; task commit f67d840d84686ad3d07b4b479971621e7dc8cc40 pushed. P05 only; full FEATURE_SCOPE/additions preserved. Checkpoint 1B/M2 remain open. Next M2 P05B; no next task started |


### P05B assignment — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P05B / 1B / M2 yazh-07: source-backed listEvents; every event cites same-case Evidence/Observation IDs and real participants |
| Branch/base | feat/p05b-event-list / **b5cb37b8d3dbe3d8f23b29a6516162c407cf4335**, clean fetched shared docs/coordination-foundation, isolated worktree; no prior active claim |
| Allowed paths | User approved backend/events.py, backend/tests/test_events.py, backend/app.py router wiring, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No DB/schema/producer/spec/dependency/frontend edits |
| Dependencies | Actual P03C bb2d18f and P04B c29e517; integrated P05 04af24f supplies participant-read validator, real P04/F00/F03/F05 and source parser/normalizer/Entity/Event chain; completed 0/1A regressions |
| Approved policy | Latest completed output per Evidence via exact UTC finished_at/UUID; preserve stored Event wire/time/score/IDs, no inference or merging. Same-case selected Observation/Evidence joins and actual selected Entity participants, each sharing a cited Observation. Missing/corrupt/stale/foreign references fail whole read safe404. Contract limit/offset; Evidence UUID then Event UUID order; one read snapshot per response, no new selectors |
| Input/output | Real immutable P04 SQL Events and cited source/participant records -> existing EventPage only; no source/history mutation |
| Proof | 20 focused PASS including real Uvicorn HTTP; full backend 268 PASS/1 existing Windows symlink SKIP, frontend48/coordination122 PASS; contract/types/build/DESIGN and real I00 loopback PASS. Actual sources/time/participants, negatives, history/concurrent snapshot; doubles and setup limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c0e25d401651b468d05a60ff5f5e3525e87e6f5f and passing 20 focused/verifier/real I00 post-merge smoke; task commit b6dddc721f056fd9542049bc5f314dc32b2e0cc1 pushed. Full scope/additions preserved. Checkpoint1B/M2 remain open. Next eligible M2 P14, no next task started |


### P14 assignment — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P14 / 1B / M2 yazh-07: immutable private versioned processing provenance, exact input/output/run joins and no sensitive public logs |
| Branch/base | feat/p14-processing-provenance / **98a28260f2fb2d91dd803c2f1835de264c5d0973**, clean fetched shared docs/coordination-foundation; isolated worktree, no prior active claim |
| Allowed paths | User approved backend/processing_provenance.py, backend/tests/test_processing_provenance.py, backend/processing.py initialization/publication, backend/tests/test_skeleton.py table inventory, backend/README.md and bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No M1 table/spec/frontend/dependency/parser edits |
| Dependencies | Real P04 merge f851dd11fd8f7e11140317cf44d022a9999044dd and P01/P02/P03/P03B/P03C/F00/F03/F05; integrated P04B/P05/P05B source validators/readback, completed 0/1A regressions |
| Approved policy | One processing-owned append-only table; success provenance/input hash-size/frozen versions-parameters/model-not-used/output ID manifests-digest/completion timestamp commit atomically with output/completed pointer. Bump new-run processor version. No fabricated legacy backfill; failed runs retain config/safe errors without success provenance. Internal reader rechecks membership and exact same-case Evidence/run joins; unavailable/corrupt safe404, no public route/field |
| Input/output | Real immutable originals/frozen P04 config/output -> versioned private record; original/source bytes/history unchanged; F08 public audit and P14B/P14C remain separate required tasks |
| Proof | 18 focused PASS including real Uvicorn HTTP/private SQL; full backend286 PASS/1 existing Windows symlink SKIP, frontend48/coordination122 PASS; contract/types/build/DESIGN/real I00 loopback PASS. Exact real inputs/outputs/config/time/digest, rollback/immutability/auth/privacy/history and labeled migration/corruption controls; limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c03361b8171e6506d2c160a85cc1e89e76315fb3 and passing 18 focused/verifier/real I00 post-merge smoke; task commit aee4220dd6e16de377591a95fcf86f23b7c4a1f1 pushed. Entire scope/additions preserved. Checkpoint1B/M2 remain open. Next M2 P14B, no next task started |


### P14B assignment — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P14B / 1B / M2 yazh-07: explicit network/GPS dispatch through actual registered adapters and private versioned provenance |
| Branch/base | feat/p14b-processing-dispatch / **acf07fec95442c8ae8b9c099dda827a9f68c9a5d**, clean fetched shared docs/coordination-foundation; isolated worktree, no prior active claim |
| Allowed paths | Approved backend/processing_dispatch.py, backend/tests/test_processing_dispatch.py, backend/processing.py, two injection points/imports in backend/tests/test_processing.py, backend/README.md, bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records; no parser/provenance format/schema/spec/frontend/dependency edits |
| Dependencies | Real P04 f851dd1/P01 cab08f1/P02 389652c with P03/P03B/P03C/F00/F03/F05/P04B/P05/P05B; P14 c03361b private provenance. Completed0/1A regressions |
| Approved policy | Reuse existing C-04 unchanged: kind selects immutable registered adapter; actual content must pass exact parser, no filename/MIME success or cross-kind fallback. Unsupported kind415 before run; malformed/wrong-layout supported input accepted failed with safe errors. Existing50MiB/100000 rows, frozen kind/version/parameters and P14 provenance/history/replay preserved |
| Input/output | Authorized original -> actual network-csv/1 or gps-csv/1 -> existing normalized immutable outputs/private provenance; upload alone is not processing success |
| Proof | 14 P14B plus21 existing processing PASS, real Uvicorn HTTP/private SQL; full backend300 PASS/1 Windows symlink SKIP, frontend48/coordination122 PASS, contract/types/build/DESIGN/real I00 loopback PASS. Actual source/provenance, cross-layout/unsupported/row-overflow/frozen selection/replay/case negatives; doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge d7a4315377cc1fdae63200780bd7728c583a14dd and passing 14 focused/verifier/real I00 post-merge smoke; task commit 2c7af4b68284f7d7c63e9b9c01d76da2d2c5caf9 pushed. Entire scope/additions retained. Checkpoint1B/M2 remain open. Next M2 P14C, no next task started |


### P14C assignment — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P14C / 1B / M2 yazh-07: failed runs expose no partial output; stable replay/new-key retry/history; SQL verification precedes completed publication |
| Branch/base | feat/p14c-atomic-processing / **fb52aba41310ae644bb9a12bd4884862367932cc**, clean fetched shared docs/coordination-foundation; isolated worktree, no prior active claim |
| Allowed paths | Approved backend/processing_publication.py, backend/tests/test_processing_publication.py, backend/processing.py SQL verification/replacement protections, backend/README.md, bounded AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No new table/field/API/provenance format/parser/dependency/frontend/M1-table changes |
| Dependencies | Real P04 f851dd1 and P14B d7a4315, P14 c03361b private provenance; actual source producers/readers/F00/F03/F05 and completed0/1A regressions |
| Approved policy | Re-read/verify actual SQL run/output/P14 provenance including same-case Evidence/run IDs, exact output strings/manifests/digest/time inside publication transaction before completed pointer. Failure rolls back; old completed outputs immutable/readable; same key replays original, new key may retry. Restart interrupted queued/running jobs fail safely per existing P04 policy, no automatic resume/false completion |
| Input/output | Actual immutable originals/frozen dispatch -> verified SQL outputs/private provenance/completed run; no partial result, public schema unchanged |
| Proof | 13 P14C/21 existing processing PASS including seven real hard-exit boundaries and Uvicorn HTTP/private SQL; full backend313 PASS/1 existing Windows symlink SKIP, frontend48/coordination122 PASS; contract/types/build/DESIGN/real I00 loopback PASS. SQL readback/rollback/visibility/replay/retry/concurrency/replacement/history/source/auth controls; doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge 920331d95fdd359f1e20cfbcfba48fc6e2afb292 and passing13 focused/verifier/real I00 post-merge smoke; task commit 5b80124e488661c0f7efe320f386a2871dcfd9e4 pushed. Full scope/additions preserved. No further M2 row in1B; P06(2A) awaits earlier1B/I00B and1C/I01 exits for automatic selection, or its own explicit allowed independent-work handoff. No next task started |


### P06 explicitly assigned independent work — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P06 / 2A / M2 yazh-07, explicitly user-assigned independent work while earlier checkpoint gates stay open; candidate device mentions, real message dispatch/publication |
| Branch/base | feat/p06-message-mentions / **9454430a56502dfa8dad791e3d3f420c05424509**, clean fetched shared docs/coordination-foundation, isolated worktree; no competing P06 claim |
| Allowed paths | Approved backend/parsers/messages_csv.py, backend/parsers/message_entities.py, focused backend/tests/test_messages.py; backend/processing.py, backend/processing_dispatch.py, backend/processing_provenance.py including processing-owned version guards; bounded backend/tests/test_processing_dispatch.py expectations; backend/README.md and AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No public route/field/table/column/M1/dependency/frontend change |
| Dependencies | Real P04 f851dd1 plus actual P14/P14B/P14C source/provenance/atomic publication/read/access chain; earlier0/1A regressions. Earlier1B/I00B and1C/I01 exits remain required, not claimed by this independent row |
| Approved format/limits | UTF-8 optional BOM, exact message_id,timestamp,sender,body columns; all cells nonblank, header-only empty success, duplicate rows retained;50MiB/100000 rows/100000 device mention occurrences per file, atomic failure on overflow |
| Approved extraction | Standalone case-sensitive ASCII D-<digits> with Unicode word/hyphen boundaries, exact IDs/leading zeros, code-point half-open body spans; metadata/full body retained. Same-run identical-key grouping only; Entities cite same-case body/mention Observation/Evidence IDs, confidence0 unavailable, no sender identification/ownership/identity inference |
| Input/output | Real uploaded message CSV -> source-preserving Observations/Entities through actual startProcessing/dispatch/private provenance/SQL verification. Existing P03 raw/uncertain time preserved without invented UTC. No Events here; P13B remains required |
| Proof | Focused P06/dispatch37 PASS plus added old-trigger upgrade1 PASS; full backend337 run:336 PASS/1 existing Windows symlink SKIP. Frontend48/coordination122 PASS; contract/types/build/DESIGN/verifier/real I00 smoke PASS. Real API/SQL/source/private read-back, limits/history/replay/case/failure controls; doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge 1b938d93c09ad82f2ef5af8eac214026d7a820f7 and passing24 focused P06/verifier/real I00 post-merge smoke; pushed task head 849d12b085681c92507eabc4da8a72ca09324c4a (implementation283d5a3 plus whitespace-only follow-up). Independent P06 only; full scope/additions and checkpoint gates remain open. Next M2 catalog P07 requires preceding exits or separately explicit independent handoff/decisions; no later task started |


### P07 explicitly assigned independent work — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P07 / 3A / M2 yazh-07; explicit independent user assignment, earlier checkpoint exits remain open |
| Branch/base | feat/p07-document-text / **97564aea28775c96679439dd5ffc22077ea75a64**, verified fetched shared docs/coordination-foundation, isolated worktree, no competing claim |
| Allowed paths | Approved backend/parsers/text_document.py, backend/tests/test_documents.py; processing.py, processing_dispatch.py, processing_provenance.py including processing-owned version guards; bounded test_processing_dispatch.py expectations; backend/README.md and AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No public route/field/table/column/M1/existing-parser/dependency/frontend change |
| Dependencies | Real P04 f851dd1 and integrated P14/P14B/P14C/P04B/P05/P05B access/source/publication chain; P06 history must remain compatible. Earlier checkpoint0/1A regressions required; this row cannot close earlier gates |
| Approved policy | Document plain text only: strict UTF-8 with optional first BOM; invalid encoding/NUL atomic failure. LF/CRLF/CR lines including blanks/duplicates/whitespace preserved; terminators excluded from line values but included in zero-based half-open decoded Unicode code-point offsets after BOM. 1-based physical line locators, final terminator no extra line; empty/BOM-only zero-output success. 50MiB/100000 source lines |
| Input/output | Authorized original -> real registered text.line Observations, exact raw/normalized text, confidence0 unavailable, no invented timestamps/Entities/Events. P13/P13B retain required extraction. Frozen parser/byte-line parameters, immutable private provenance/replay/history/atomic publication |
| Acceptance/tests | Focused18 PASS; full backend356 run:355 PASS/1 existing Windows symlink SKIP. Frontend48/coordination122 PASS; contract/types/build/DESIGN/verifier/real I00 smoke PASS. Real source/API/SQL/private read-back, boundaries/negative/history/replay/migration/recovery controls; doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c8b5331465a25175e6ee0e470795061fa786ce70, task commit 213565a98d6688a01ab450707a23162e25f9f0de pushed;18 focused/verifier/real I00 post-merge smoke PASS. Independent row only, full scope/additions/earlier gates preserved. Next M2 catalog P11(3A) needs its own format/policy/file handoff or preceding exits for automatic selection; no later task started |

P07 additional user-approved handoff: fixture-only unsupported document -> image
updates in backend/tests/test_processing.py and test_processing_provenance.py;
retain existing415/replay/no-publication assertions unchanged.


### P11 explicitly assigned independent work — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P11 / 3A / M2 yazh-07, user explicitly assigned independent mobile-record work while earlier checkpoint gates remain open |
| Branch/base | feat/p11-mobile-records / **c12deb1fa58863b333bbb6fe2b835e848dfa504d**, verified fetched shared docs/coordination-foundation, isolated worktree, no competing P11 claim |
| Allowed paths | Approved backend/parsers/mobile_csv.py, mobile_events.py and backend/tests/test_mobile.py; backend/processing.py, processing_dispatch.py, processing_provenance.py including processing-owned version guards; bounded backend/tests/test_processing_dispatch.py expectations and old-version guard fixture in test_documents.py; backend/README.md and AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No public field/route/table/column/M1/existing-parser/dependency/frontend change |
| Dependencies | Real P04 f851dd1 and integrated P14/P14B/P14C/P04B/P05/P05B source/access/atomic publication chain; preserve actual P01/P02/P06/P07 producers/history. Previously completed0/1A regressions required; no earlier checkpoint closure claimed |
| Approved format | mobile_log activity CSV: strict UTF-8 optional initial BOM, exact timestamp,device_id,event,detail columns, all cells nonblank. Preserve raw values/device case/leading zeros/duplicates/physical row spans. Header-only empty success;50MiB/100000 data rows, malformed/overflow fails atomically |
| Approved outputs | Three Observations per row, same-run exact device:<raw ID> candidate Entity grouping only; one mobile.activity source-report Event per row cites all row Observation/Evidence IDs and actual same-case device Entity sharing its device Observation. Confidence0 unavailable; no owner/person identity/verified-occurrence claim. P03 raw invalid/uncertain time retained without invented UTC |
| Input/output | Authorized immutable original -> actual registered adapter/projector/normalization -> source/Entity/Event APIs and private frozen versions/byte-row parameters, verified atomic publication. No physical acquisition or model |
| Acceptance/tests | Focused P11/dispatch36 PASS, P11 contributes22; full backend378 run:377 PASS/1 existing Windows symlink SKIP. Frontend48/coordination122 PASS; contract/types/build/DESIGN/verifier/real I00 smoke PASS. Actual source/API/SQL/private refs/limits/history/replay/rollback/upgrade/recovery controls; initial verification fixes/doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge 212a5e204437ca02b40be08b3187d2f17c6c9577; task commit 4f0099b5003d45db81b1d20f50dd341735e80eba pushed.22 P11/verifier/real I00 post-merge smoke PASS. Independent row only; full scope/additions/earlier gates preserved. Next M2 catalog P12(3A) needs own transaction format/resource/file handoff and earlier exits for automatic selection, or separately explicit independent assignment. No next task started |


### P12 explicitly assigned independent work — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P12 / 3A / M2 yazh-07, explicit independent user assignment; earlier checkpoint gates stay open |
| Branch/base | feat/p12-transaction-csv / **bd1e03de15a7f212e77dac391b5efd8d6fc7af07**, verified fetched shared docs/coordination-foundation, isolated worktree, no competing claim |
| Allowed paths | Approved backend/parsers/transactions_csv.py, transaction_events.py; backend/tests/test_transactions.py; backend/processing.py, processing_dispatch.py, processing_provenance.py with processing-owned guards; bounded dispatch expectations and old-version fixtures in test_documents.py/test_mobile.py; backend/README.md and AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW records. No public route/field/table/column/M1/existing-parser/dependency/frontend change |
| Dependencies | Real P04 f851dd1 plus integrated source/access/private provenance/read/verified atomic publication chain; preserve P01/P02/P06/P07/P11 history. Completed0/1A regressions required; no earlier checkpoint closure |
| Approved format/limits | transaction CSV: UTF-8 optional initial BOM, exact timestamp,account_id,amount,currency columns, nonblank cells, raw values/account case/leading zeros/duplicates/physical row spans preserved. Header-only empty success;50MiB/100000 rows; amount literal max128 characters |
| Approved amounts/currency/time | Exact -?[0-9]+(decimal fraction)? literal, no floats/rounding/exponent/NaN/infinity/separators/plus/outer whitespace. Zero and negative amounts accepted, exact canonical decimal string, negative zero ->0. Three uppercase ASCII currency letters retained without ISO/minor-unit/FX claims. P03 raw invalid/uncertain time preserved without invented UTC |
| Approved outputs | Three Observations per row account/amount/currency, same-run exact account:<raw ID> candidate Entity grouping only, one transaction.record source-report Event per row citing all row Observation/Evidence IDs and actual same-case account Entity sharing its account Observation. Confidence0 unavailable; no owner/person/payment direction/verified transfer/fraud/criminality inference or live banking |
| Acceptance/tests | Focused43 P12/dispatch PASS, P12 contributes29; full backend407 run:406 PASS/1 existing Windows symlink SKIP. Frontend48/coordination122 PASS; contract/types/build/DESIGN/verifier/real I00 smoke PASS. Actual source/API/SQL/limits/decimal/history/replay/rollback/upgrade/concurrency controls; doubles/limits in PREIMPLEMENTATION_REVIEW |
| Handoff | Complete after authorized merge c1165793cb791fe0e7eccaded43e7c8daa6ee498; task commit e46a7a8361f971d9f27527e3516d7b3bfddfe590 pushed.29 P12/verifier/real I00 post-merge smoke PASS. Independent row only; full scope/additions/earlier gates preserved. Next M2 catalog P13(3A) has actual P06/P07 prerequisites but needs own extraction/evaluation/file handoff; automatic selection waits for earlier exits, or separately explicit independent assignment. No next task started |


### P13 explicitly assigned independent local NLP work — 2026-11-02

| Field | Recorded assignment |
|---|---|
| Task/checkpoint/owner | P13 / 3A / M2 yazh-07, explicitly user-assigned independent text candidate extraction; earlier checkpoint exits stay open |
| Branch/base | feat/p13-text-entities / **6980b4d0b2fd14a6bf372ae84cb7ab8e78b38d93**, verified fetched shared docs/coordination-foundation, isolated worktree, no competing claim |
| Allowed paths | Approved backend/text_ner.py, text_ner_worker.py, parsers/text_entities.py, models/text_ner.json; backend/tests/test_text_entities.py and labeled fixtures/text-entities; requirements.txt pins; processing.py, processing_dispatch.py, processing_provenance.py with processing-owned guards; bounded document-output/old-version/mixed-document expectations in test_documents.py/test_mobile.py/test_transactions.py; backend/README.md and AGENT_TASKS/COMMUNICATION/ROADMAP/PREIMPLEMENTATION_REVIEW. No public API/table/column/M1/frontend/other-producer change |
| Dependencies | Actual P06 merge1b938d9 and P07 c8b5331, existing P04/source/access/private provenance/verified publication/read chain and P01/P02/P11/P12 history; completed0/1A regressions required |
| Approved model/format | P07 UTF-8 plain-text document, local CPU spaCy3.8.18/en_core_web_sm3.8.0 English; official wheel SHA256 pinned, compatible dependencies locked. Public setup/CI downloads only, no evidence transfer or runtime downloads |
| Approved extraction | Model PERSON/ORG/GPE/LOC/FAC/DATE -> candidate person/organization/location/date mentions; supplement standalone D-[0-9]+, AC-[0-9]+, +8–15 ASCII-digit phone literals, validated IPv4/IPv6. Identifier priority over overlapping model spans, exact dedup/source text/case/zeros; canonical IP normalization only |
| Output/integrity | Preserve actual full-line Observations/IDs; add mention Observations with line/global half-open code-point spans and Entities citing real line/mention/Evidence IDs. Same-run identical kind/key grouping only, confidence0 unavailable; no identity/coreference/ownership/occurrence-UTC/truth/guilt inference. No Events; P13B remains required |
| Approved resources | Existing50MiB/100000-line parser caps plus NLP1000000 decoded source characters including separators,20000 characters/line,100000 mentions, one local worker per app process and120-second queue/inference deadline. Missing/wrong/corrupt model/timeout/overflow fails atomically, no silent rules fallback; functioning empty/no-mention input honest success |
| History/provenance | Old processor4 document records stay immutable/readable/replayable; new version freezes actual model/digest/versions/limits privately, verified atomic output/provenance/completion unchanged |
| Acceptance/tests | Real model/source/API/SQL/history/replay/rollback/resource/model-unavailable/timeout/case controls, actual labeled precision/recall/FP/misses, regressions and Windows/Ubuntu CI. No invented accuracy or model results |
| Handoff | Complete after integration in c564775 with nine focused/loopback passes, the coordination verifier and real I00/U05C smoke. Full feature scope and earlier checkpoint gates preserved. P13B requires a separate handoff |

### U05C assignment — 2026-11-03

| Field | Scoped assignment |
|---|---|
| Task/checkpoint/owner | **U05C / 1B / M4 / JebasJ**; explicit user handoff includes these bounded shared documentation edits; whale2186 retains integration coordination |
| Branch/common contract | `feat/u05c-start-processing-ui`; clean actual HEAD/base **747d223b1b04d134edaea6384e0c3cfcb1b40c5e**, matching local `docs/coordination-foundation`; unchanged `specs/openapi.yaml` draft 0.3.0. The prompt's full hash beginning 747d223 differs from actual Git; this record uses the verified commit |
| Allowed paths | `frontend/src/cases/`, `frontend/test/`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no backend/spec/package dependency edits |
| Dependencies | Real U03 **c5c9b5a5aefff113db6592996da4af1c780d88df** and P04 merge **f851dd11fd8f7e11140317cf44d022a9999044dd** are committed ancestors, along with subsequent processing publication/provenance/audit producers. No substitute producer in HTTP acceptance |
| Acceptance | Explicit bodyless generated-client start with unique UUID key per action; busy duplicate guard; retain accepted run ID and actual status; safe 400/401/404 alerts and retry; abort/ignore stale selection/unmount/session responses; real synthetic network CSV HTTP 202/read-back |
| Interface | Existing typed client uses singular `header` with generated `Idempotency-Key` spelling. Accepted ProcessingRun is retained in the exported controller state for U05; this bounded action displays status at acceptance only |
| Verification/state | **In Progress**, local verification results recorded in U05C verification in PREIMPLEMENTATION_REVIEW; no commit/push/merge authorized. Checkpoint 1B/I00B stays open; next bounded M4 task U05 polling requires its own handoff |

No unresolved contract choice is needed for this action: it consumes the existing
bodyless start and declared error/status contract. Network/protocol failure is
explicitly uncertain; another user action uses a new key and may start another
run. Fetch/static-render unit doubles are separate from real FastAPI acceptance.


### U05 assignment — 2026-11-03

| Field | Scoped assignment |
|---|---|
| Task/checkpoint/owner | **U05 / 1B / M4 / JebasJ**; user explicitly hands off the bounded shared documentation paths; whale2186 retains integration coordination |
| Branch/common contract | `feat/u05-processing-status-ui`; clean starting HEAD and local `docs/coordination-foundation`: **f6d5c17f1f23d17048bd9b582e1f64d20ce27c1a**; unchanged `specs/openapi.yaml` draft 0.3.0. Prompt's full hash beginning f6d5c17 differs; this is the actual reviewed Git base |
| Allowed paths | `frontend/src/cases/`, `frontend/test/`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no spec/backend/package dependencies |
| Dependencies | Real U05C merge **f6d5c17f1f23d17048bd9b582e1f64d20ce27c1a** (task **d7e9ecfed43f8a3f4f21fef219b1190560302c0d**) and P04 merge **f851dd11fd8f7e11140317cf44d022a9999044dd** are committed ancestors; current publication/private provenance/audit producers retained |
| Acceptance | Generated-client getProcessingRun polling; real queued/running/completed/failed display, exact version/timestamps, escaped diagnostics; terminal stop, 401/404/network alerts, same-run retry, abort and stale-response suppression on unmount/evidence/session change |
| Tests/integration | Schema-shaped Fetch doubles and deterministic timers plus real HTTP/FastAPI/SQLite status-controller poll of permitted network.csv; exact run/case/evidence/version/finished_at, missing-run/foreign-case 404; prior completed checkpoint regressions |
| State/handoff | In Progress pending review/publication; actual verification in U05 verification in PREIMPLEMENTATION_REVIEW.md. No stage/commit/push/merge authorized. Next M4 dependency row U05B requires its own handoff; Checkpoint 1B/I00B remains open |

No unresolved contract choice affects U05. Status fetch transport failures pause
with an explicit same-run retry; only the separate start action creates a new run.
No history endpoint or observation UI is added, and backend work is not cancelled
by client disposal. Full proposal and approved speech addition remain required.


### U05B assignment — 2026-11-03

| Field | Scoped assignment |
|---|---|
| Task/checkpoint/owner | **U05B / 1B / M4 Investigator Application / JebasJ**, user-assigned bounded observation inspector row |
| Branch/common contract commit | `feat/u05b-observation-inspector-ui`; clean actual starting HEAD/local `docs/coordination-foundation` **32b8adeecec8903edc1dde5ae56ad8a175a61607**. User-supplied full hash beginning 32b8ade differs from the actual Git object. Unchanged `specs/openapi.yaml` draft 0.3.0 is the sole HTTP authority |
| Allowed paths/shared handoff | `frontend/src/cases/`, `frontend/test/`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; user explicitly assigned these documentation paths. No backend/spec/dependency changes |
| Real dependencies | U05 task **50a5e9c4a36afc986f20200b2adfa28f1a938002**, integrated in starting HEAD; real P04B merge **c29e517f218c0851a9959cfa389b093242a255ab**, both committed ancestors. Existing P04 start/poll and real completed immutable outputs are consumed; no pending producer gate or new contract choice |
| Acceptance | Latest completed evidence observations, optional historical completed run pin, exact kind/locator/raw/normalized/raw time/UTC/confidence, authoritative pagination/empty state, fixed safe 400/401/404/500/network alerts, abort/stale/session disposal and completion refresh. Real six-observation network fixture, pinned history after newer completion, pagination and foreign-case rejection |
| Verification/state | In Progress pending review/publication. Exact commands/results and Fetch-double/static-render limits recorded in U05B verification in PREIMPLEMENTATION_REVIEW.md. No stage/commit/push/merge authorized |
| Next handoff | U13 / I00B remain separate bounded assignments; Checkpoint 1B remains open. No module/phase closure |

### U13 assignment — 2026-11-03

- Task/checkpoint: **U13 / 1B**, case evidence counts/types/processing status.
- Accountable interface owner: **JebasJ / M4 Investigator Application**, per
  ROADMAP.md module assignment; explicit user-scoped handoff in this session.
- Branch: `feat/u13-case-evidence-overview`, clean initial worktree. Actual
  reviewed common contract/base: **138fd791808571c60ee7dc5ef831684c84d09d67**,
  matching local `docs/coordination-foundation`. The prompt's supplied full hash
  differs; the actual checked-out base contains the required merged producers.
- Dependencies: U02 merge **9f2cc8ac64426ef2b0bb9d917fd7afdb777b606f**,
  U05 merge **32b8adeecec8903edc1dde5ae56ad8a175a61607**,
  F04 **69f2e8269b6e6d639889941926bc604a415e3f05**,
  P04 merge **f851dd11fd8f7e11140317cf44d022a9999044dd**;
  U05B is present at the reviewed base. Real producers are used for acceptance.
- Allowed paths: `frontend/src/cases/`, `frontend/test/`,
  `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. This authorizes the bounded shared-doc
  updates; no spec/backend/dependency edit or stage/commit/push/merge handoff.
- Acceptance: all-page totals, per-item latest run breakdown and evidence kinds,
  honest empty state, safe 401/404/network retry, selection/unmount cancellation,
  and real HTTP synthetic aggregation. Unit doubles are explicitly separate
  from real acceptance. Results: U13 verification in PREIMPLEMENTATION_REVIEW.md.
- State: implemented locally, **In Progress pending review/publication**.
  No unresolved producer/consumer contract choice; oldest-first processing
  history is already specified. Next gate is joint I00B, not checkpoint closure.


### I00B assignment — 2026-11-03

| Field | Scoped assignment |
|---|---|
| Task/checkpoint/owner | **I00B / 1B final exit / whale2186 / joint integration coordination**, explicitly assigned by the user; module interface owners remain M1 sharmelas-925, M2 yazh-07, M3 whale2186, M4 JebasJ |
| Branch/common contract | `feat/i00b-processing-inspection-gate`; clean starting HEAD and local `docs/coordination-foundation` **1517b4d9479e2062ce2c85cb380fe43d7b512aa6**. Supplied full hash `1517b4dfb6df009406085a67bb13c054238e55ec` differs from the actual Git object; actual reviewed base is authoritative. Unchanged `specs/openapi.yaml` draft 0.3.0 and INTEGRATION.md govern acceptance |
| Allowed paths/shared handoff | Exactly `frontend/test/cases.integration.mjs`, `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; no backend/spec/dependency edits. User explicitly authorizes these shared ledger updates and checkpoint sealing after verification |
| Real dependencies | P01, P02, P03, P03B, P03C, P04, P04B, P05, P05B, P14, P14B, P14C, F08, U05C, U05, U05B, U13 plus prior I00 are committed ancestors. Exact integration versions and all 18 acceptance rows are recorded in the I00B live record in ROADMAP.md; no schema-derived producer substitute |
| Acceptance | UI network/GPS start/poll/inspection; immutable raw/normalized/source/time outputs; candidate Evidence/observation joins; safe processing audit actor/target/time/reason; actor-isolated 404 ApiError; private provenance, malformed/unsupported/replay/retry/failure/recovery regressions and all-page overview per INTEGRATION.md |
| Verification/dependency handling | Actual commands/results, private SQL read-back and labeled fault injections versus real HTTP acceptance are in I00B verification in PREIMPLEMENTATION_REVIEW.md. Later NLP model failures are recorded separately; no unresolved contract choice or producer gate affects network/GPS acceptance |
| State | **Complete**, locally verified against real merged dependencies; Checkpoint 1B sealed in the ledger, Checkpoint 1C active. Separate later NLP full-suite failures remain recorded |
| Publication/next handoff | No stage/commit/push/merge authorized or performed. Checkpoint completion is a locally verified ledger result, not a merged-commit smoke claim. Next checkpoint 1C becomes active after the gate; G01D/G02 require their own bounded assignments and policy/setup acceptance |

### A02 assignment — 2026-11-03

- **A02 / Checkpoint 1C / M3 Evidence Fusion and Adaptive Triage / whale2186**,
  explicitly assigned on `feat/a02-candidate-link-rule`; initially Backlog,
  now In Progress pending review/publication. Module interfaces remain M1
  sharmelas-925, M2 yazh-07, M3 whale2186 and M4 JebasJ.
- Clean actual reviewed common contract/base and local coordination ref:
  **11961c4ab4c1167e1d0ad8c83fe52440b2466a9a**. The supplied full hash
  `11961c47ea414ce558f6c91a3cfb8b7eb36ea6ad` is not a local Git object.
  The actual base contains real A01 merge at that HEAD (task
  **16e6429a22fa6250fdeebc4c47f6ab0a4d0349bf**), G02 merge
  **d1f16ef02a62c2ce94bdd19539037a7b60cecabf** and completed 1B/I00B
  at **740f40662158caeed41b2de963cbb185b69fa51d**. No producer substitute.
- Allowed paths: `backend/graph_links.py`, `backend/tests/test_graph_links.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`; explicit user handoff for shared docs.
  No spec/frontend/dependency edit or stage/commit/push/merge authorization.
- Acceptance: exact shared candidate key across distinct Evidence; deterministic
  source UUID endpoints; unique nonempty same-case Evidence/Observation citations
  resolving locators; D-9 unlinked; strict bundled GraphEdge/Finding validation;
  empty-input, case isolation and invalid-source controls. Real merged network/GPS
  processing and A01 nodes are integrated in acceptance.
- Resolved handoff discrepancy / producer-consumer review queue: unchanged draft
  0.3.0 requires Finding.kind `relationship`, not `candidate_match`; A02 produces
  `relationship` with a candidate summary and versioned rule. A03/A03B/A05B and
  M4 U07B consumers must use that existing enum. No new enum or spec change.
  Committed GPS contains only D-8: preserve the original negative control and use
  a labeled in-test D-7/D-8 synthetic variant for positive acceptance. No pending
  choice blocks A02. Nonempty entities require observations for checked joins.
- Exact verification/limitations are in A02 verification in
  PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 remains open; next bounded
  dependency-ready M3 handoff is A03 or A03B, separately assigned.


### A03 assignment — 2026-11-03

- **A03 / Checkpoint 1C / M3 Evidence Fusion and Adaptive Triage / whale2186**,
  explicitly assigned on clean `feat/a03-relevance-factor`; initially Backlog,
  now In Progress pending review/publication. Other accountable interfaces remain
  M1 sharmelas-925, M2 yazh-07 and M4 JebasJ.
- Exact actual reviewed common contract/base and local coordination ref:
  **51ee2ed3432b8956cf3af9ebd410a04483e917d7**. The supplied full hash
  `51ee2edca1ba2bc71946ebdf4ef139cc75e840d5` differs from the actual Git object.
  Unchanged `specs/openapi.yaml` draft 0.3.0 is the sole HTTP authority.
- Real dependencies: A02 merge at the common base (task
  **ca6cb6727bcb87a31bc8b1b9cc18efbc42d99ed0**), A01 merge
  **11961c4ab4c1167e1d0ad8c83fe52440b2466a9a**, G02 merge
  **d1f16ef02a62c2ce94bdd19539037a7b60cecabf**, completed 1B/I00B
  **740f40662158caeed41b2de963cbb185b69fa51d**. No producer substitute.
- Allowed paths: `backend/triage/`, `backend/tests/test_relevance_factor.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. Explicit user handoff covers shared docs;
  no spec/frontend/dependency change or staging/commit/push/merge authorization.
- Acceptance: deterministic G02 unique matched/known ratio, sorted candidate-key
  explanation/counts, target Evidence citation, default/explicit bounded weight,
  rounded contribution; empty/missing known or unanalyzed/no-observation target
  absent; evaluated zero preserved; strict bundled TriageFactor validation and
  source/case/UUID negatives; real merged processing/API/A02 integration.
- Resolved producer/consumer handoff: bare entity labels and an Evidence UUID
  cannot prove ownership. Internal builder requires P03B Entity wire mappings,
  complete same-case `evidence_records` and selected source `observations`.
  A04/A05 must authorize/select the complete coherent snapshot, pass these inputs
  and feed raw factor values into G02 aggregation for normalized weights.
  Source observations must carry the producer's exact `entity_key`; unsupported
  keyless inputs fail closed. No wire change or unresolved A03 gate.
- Actual verification/read-back and unit-versus-real acceptance limits are in
  A03 verification in PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 stays open;
  next bounded handoff is A03B, then A04 once its dependencies are ready.

### A03B assignment — 2026-11-03

- **A03B / Checkpoint 1C / M3 Evidence Fusion and Adaptive Triage / whale2186**,
  explicitly assigned on clean `feat/a03b-connectivity-factor`; initially Backlog,
  now In Progress pending review/publication. M1 sharmelas-925, M2 yazh-07 and
  M4 JebasJ retain their accountable interfaces.
- Actual reviewed common contract/base (also local coordination ref):
  **ec4ab3c153961c416785348edd73eb5f6ed4bd68**, the A03 merge. Supplied hash
  `ec4ab3c5c9ee2c6ebfd6e082878bf893e364024b` is not a local Git object.
  Draft 0.3.0 remains the sole HTTP authority. Records retain the requested date;
  execution occurred 2026-11-04.
- Real committed dependencies: G02 policy task
  **01daaed0cf1c2a95d443c01d6f459ce0d76f2fac**, A02 task
  **ca6cb6727bcb87a31bc8b1b9cc18efbc42d99ed0**, A01 task
  **16e6429a22fa6250fdeebc4c47f6ab0a4d0349bf**; A03 task
  **c9a36eaf5f59e15c577ae69a33b2875208e85848** and completed 1B/I00B are
  ancestors. No producer doubles in real API acceptance.
- Allowed paths: `backend/triage/`, `backend/tests/test_connectivity_factor.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. User handoff explicitly covers shared docs;
  no spec/frontend/dependency edits or staging/commit/push/merge authorization.
- Acceptance: G02 unique non-self external degree/10 saturated at 1; deterministic
  source-backed count explanation, sorted target/neighbor citations, finite
  bounded weight and rounded contribution; absent unknown/zero observations or
  missing graph evaluation; evaluated zero retained. Strict actual-bundle factor
  validation, invalid UUID/case/reference negatives and real A01/A02 integration.
- Resolved internal producer/consumer handoff: `target_nodes` supplies the complete
  selected graph; target membership derives from Evidence citations, not labels.
  A01/A02 producers retain source validation; A04/A05 must authorize/select the
  coherent full graph and target observation count, since this signature cannot
  join private Evidence/Observation ownership independently. None means unknown;
  an empty evaluated graph is distinct. No unresolved A03B policy or wire gate.
  A04 must normalize raw factor weights through G02, never use neighbor scores.
- Actual verification and limits are in A03B verification in
  PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 and M3 remain open; next bounded
  dependency-ready handoff is A04. No later task started.

### A04 assignment — 2026-11-03

- **A04 / Checkpoint 1C / M3 Evidence Fusion and Adaptive Triage / whale2186**.
  User-assigned clean branch `feat/a04-factor-aggregation-triage`; initially
  Backlog, now In Progress pending review/publication. M1 sharmelas-925,
  M2 yazh-07 and M4 JebasJ retain their accountable boundaries.
- Exact actual reviewed common contract/base and local coordination ref:
  **2eca04b5634302b3c85e7e05e0ac7c48bc37e742**. Supplied full hash
  `2eca04bb97973ebfef4bcfb42e7616644f80998f` differs. Draft 0.3.0 remains
  unchanged. Requested record date retained; execution occurred 2026-11-04.
- Real dependency versions: A03B task **bdba306** at the common-base merge,
  A03 task **c9a36eaf5f59e15c577ae69a33b2875208e85848**, G02 task
  **01daaed0cf1c2a95d443c01d6f459ce0d76f2fac**; A01/A02 and completed
  1B/I00B are merged ancestors. Real API acceptance uses no producer doubles.
- Allowed paths: `backend/triage/`, `backend/tests/test_triage_aggregation.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. Explicit shared-document handoff only;
  no spec/frontend/package edits or stage/commit/push/merge authorization.
- Acceptance: G02 available-factor normalization, per-factor rounding/cap/bands,
  unscored missing/zero-observation items, canonical full membership ordering,
  strict actual-bundle results, invalid/source-isolation controls and real
  network/GPS processing -> A01 -> A02 -> A03/A03B -> A04/source read-back.
- Resolved internal handoff: FactorValue has no name. A03/A03B dictionaries or
  an explicit name-to-FactorValue mapping supply it; unnamed values fail closed.
  Sorting returns TriageEntry wrappers to retain unscored items without creating
  invalid TriageResults. Producer weights are recomputed by G02. No wire change
  or unresolved A04 gate. A05 supplies authorized frozen membership/count/time
  and records policy version; A06 consumes sorted entries before pagination.
- Actual verification/limitations are recorded in A04 verification in
  PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 stays open; next bounded
  dependency-ready M3 handoff is A01B (also requires G01D), then A05.

### A15 assignment — 2026-11-03

- **A15 / Checkpoint 1C / M3 Evidence Fusion and Adaptive Triage / whale2186**.
  User-assigned clean `feat/a15-explainable-triage-findings`; Backlog ->
  In Progress pending review/publication. Execution date 2026-11-04.
  M1 sharmelas-925, M2 yazh-07 and M4 JebasJ retain their accountable boundaries.
- Exact actual reviewed common contract/base and local coordination ref:
  **eb256aa8def4a3e7b453982e4b1413868db4a47c**. Supplied full SHA
  `eb256aab8a141b711d95e8b39bbcd203ffcfae2e` differs. Draft 0.3.0 unchanged.
- Real required dependency merges: A04
  **7858cce3cc21dbf0efe680094b28c3182b72d336**, A02
  **51ee2ed3432b8956cf3af9ebd410a04483e917d7**. G02
  **d1f16ef02a62c2ce94bdd19539037a7b60cecabf**, A03/A03B/A01,
  A05/A05B/A06 and completed Checkpoint 1B producers are merged ancestors.
- Allowed paths: `backend/triage/`, `backend/tests/test_explanations.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. Explicit shared-doc handoff; no
  spec/frontend/dependency edits or stage/commit/push/merge authorization.
- Acceptance: exact factor/base/normalized-weight/contribution/sum explanation,
  actual A02 rule/source locators and uncertainty, D-7 removal changing actual
  relevance/connectivity/link/score/explanation, strict bundled Finding and
  TriageResult validation, source/case/arithmetic failure controls and published
  real-producer API read-back. No fabricated SHAP/model-importance metric.
- Producer/consumer communication queue, A15 -> M4 U06/U07B/U06B and A17:
  TriageFactor has no observation IDs; evidence-to-observation joins cannot prove
  exact factor attribution. Resolved for this scoped implementation by explicitly
  labeling optional locator lists as evidence context only and preserving actual
  producer bases. Finding resolves exact observation IDs. **Exact per-factor
  observation attribution remains unavailable**; any future structured handoff
  requires coordinated producer/consumer review, not an invented wire field.
  Caller selects frozen observations; helpers cannot authorize case access or
  infer completed snapshot membership. Finding text is a helper return value,
  not an extra Finding field. No other future gate is pulled into this task.
- A04 now uses the detailed triage generator for new outputs; old completed
  outputs/history are never rewritten. Counterfactual helper is an unpersisted
  diagnostic, not analysis publication. Actual tests/doubles/limits are in
  PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 and M3 remain open; next bounded
  consumer handoffs are U06/U07B, then I01 after all its prerequisites/exit proof.

### F08B assignment — 2026-11-03

- **F08B / Checkpoint 1C / M1 Evidence Foundation / sharmelas-925**.
  Explicit user handoff on clean `feat/f08b-analysis-audit`, Backlog ->
  In Progress pending review/publication. Execution date 2026-11-04.
- Exact reviewed common contract/base and initial HEAD:
  **9184bed7f5b0ff1ab265452f54392aa168fbe6cc** on
  `docs/coordination-foundation`; OpenAPI draft 0.3.0 unchanged.
- Real dependency ancestors: F06
  **1b5166d91e0f3b86b85585d714a917a3efc82d44**, A05
  **266f39f4df18e261a156240ff4d828f74afafe2b**, A01B
  **ba7db7faa449e62a3ee0e3a74ddd8ef8b4f58887**, F08
  **747d223b1b04d134edaea6384e0c3cfcb1b40c5e**. All Checkpoint 1B
  tasks and A05B/A06/A15 are merged; no missing producer substituted.
- Allowed paths: `backend/audit.py`, `backend/graph_projection.py`,
  `backend/analysis.py`, `backend/tests/test_analysis_audit.py`,
  `backend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. Explicit M1-to-M3 hook/initializer and
  shared-doc handoff; no spec/frontend/dependency changes or publication.
- Acceptance: one append-only startAnalysis event per completed/failed run,
  authenticated actor/case and run target, safe status/version/error summary,
  atomic status/audit writes, authorized chronological paginated API read-back,
  private frozen-input/output linkage, replay/recovery and SQL failure controls.
- Producer/consumer communication queue, M1 F08B -> M3 A05/A01B and M4/I01:
  resolved within the authorized hook paths. Run ID is the private provenance
  reference to frozen algorithm/input snapshot and immutable output if produced;
  early failures have no output. No extra wire field or public source dump.
  Public errors allow only ANALYSIS_FAILED and GRAPH_PROJECTION_FAILED; unknown
  codes map to ANALYSIS_FAILED. Standalone A01B initialization now ensures F06
  audit storage and A05's existing legacy-a01b version default/freeze. Existing
  history is not backfilled with invented audit events. No unresolved F08B gate.
- Real HTTP/SQLite/processing/analysis acceptance uses an explicit transactional
  Neo4j double; live Neo4j remains opt-in. Results/limits in
  PREIMPLEMENTATION_REVIEW.md. Checkpoint 1C/I01 remains open; next consumer
  handoff is I01 after its remaining UI prerequisites and runbook exit evidence.

### U06 assignment — 2026-11-03

- **U06 / Checkpoint 1C / M4 Investigator Application / JebasJ**.
  User-assigned clean `feat/u06-priority-list-ui`, Backlog -> In Progress
  pending review/publication. Execution date 2026-11-04.
- Exact actual reviewed common contract/base and coordination ref:
  **291ccfc364126ea678b4a0113494d0acaa4ec731**. Supplied full SHA
  `291ccfce06b2f76fe3ce5926ecdbd0c8ec1712a7` differs. Draft 0.3.0 unchanged.
- Required real dependency merges: U01
  **f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029**, A06
  **eb256aa8def4a3e7b453982e4b1413868db4a47c**. Consumed workspace pin U05D
  **291ccfc364126ea678b4a0113494d0acaa4ec731**, A15 explanations
  **9184bed7f5b0ff1ab265452f54392aa168fbe6cc**. All are merged ancestors;
  completed checkpoints 0/1A/1B remain preserved. No missing producer substitute.
- Allowed paths: `frontend/src/cases/`, `frontend/test/`,
  `frontend/README.md`, `docs/AGENT_TASKS.md`, `docs/ROADMAP.md`,
  `docs/PREIMPLEMENTATION_REVIEW.md`. Explicit user shared-doc handoff;
  no spec/backend/dependency edits, stage/commit/push/merge authorization.
- Acceptance: typed listTriage, pinned completed snapshot on every page,
  server total/order, evidence IDs, automated bands/two-decimal scores/factors/
  explanations, honest unscored/empty states, separate live override indicator,
  fixed safe errors/retry and abort/disposal/session controls. Schema-derived
  Fetch doubles plus real HTTP/SQLite/processing/analysis acceptance, exact
  score/factor/history read-back and upload/new-completion between page reads.
- Producer/consumer queue A06/U05D -> U06 and future U07/U07B: resolved using
  existing selected-run response and workspace pin. A latest triage response
  adopts a completed ID only while the workspace has no pin; a confirmed newer
  analysis completion switches all consumers coherently. Refresh priorities
  retains the selected snapshot and refreshes live overlays, never re-sorts.
  Before any completed run the upload list is explicitly live/unscored. A15
  factors carry Evidence IDs, not observation IDs; no exact factor-level locator
  attribution or new route/field is invented. No unresolved U06 contract gate.
- Override mutation remains U09/2B; U06 overlay tests use declared synthetic
  responses. Actual verification/doubles/limits are in PREIMPLEMENTATION_REVIEW.md.
  Checkpoint 1C/I01 and M4 remain open; next bounded handoffs U07/U07B, then I01
  after all prerequisites and runbook exits. Other module owners unchanged.
