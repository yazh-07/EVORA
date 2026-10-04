# EVORA roadmap and module assignments

**Status:** proposed scope, no features implemented in this repository yet. Four people each work on one module; one of those four coordinates integration alongside their module. Fill in module assignments when known; keep branch/task status updated in PRs.

## Common-base setup — before independent agent branches

| Decision / deliverable | Module(s) / coordination | State |
|---|---|---|
| Official name EVORA | Four-person team | Decided |
| Four modules and full proposed initial feature scope | Four-person team | Chosen; see `docs/ARCHITECTURE.md` and `docs/FEATURE_SCOPE.md` |
| Stack, Windows setup and local test commands | Module contributors | FastAPI/SQLite/React chosen; Windows install/test commands unverified |
| First integrated test inputs | Module contributors | Three CSV layouts chosen for first tracer; **all later proposed capabilities remain on the build roadmap** |
| Shared versioned data schemas and API | Affected module contributors; integration coordinated by one member | Local draft `specs/openapi.yaml`; publish one common version for agents, not four separate approvals |
| Auth/access scope and evidence/AI privacy policy | M1 and M4 contributors, with cross-module input | Recommendations in `docs/CONTRACT_REVIEW.md`; implementation details not yet fixed |
| Synthetic end-to-end case and expected outcomes | Four contributors; one coordinates integration | Three CSV inputs and behavioral tracer drafted; golden scores await tested M3 policy |
| One person assigned to each module | Four-person team | Names remain open; integration coordination is additional work for one of the four |

**Synchronization:** the people building affected modules resolve technical interface choices in one spec and publish a common commit before independent agents implement those interfaces. The person coordinating integration keeps that shared version aligned; technical choices are worked out with the affected modules. Do not assign agents conflicting endpoint names or claim unimplemented interface slots work. Details for later formats/algorithms are chosen before their own tickets, without holding up unrelated early work.

Open cross-module questions and correction handoffs are recorded in [`docs/COMMUNICATION.md`](COMMUNICATION.md); entries there do not replace `specs/openapi.yaml` or the relevant tested policy.

**Task granularity:** the four modules are not four agent jobs. The old F1/P1/A1/U1 shorthand described multi-PR *milestones*; do **not** give those bundles to a single agent or keep one long-lived branch per module. [`docs/TASK_BREAKDOWN.md`](TASK_BREAKDOWN.md) splits the whole agreed feature scope into individually testable task IDs with dependencies, contract references and acceptance checks. Each task gets a short-lived branch `feat/<task-id>-<slug>` and a fresh agent session. All catalog rows start **Backlog**; the person coordinating integration updates their status/assignment here to avoid conflicting edits.

| Next task ID | Module(s) / coordination | Depends on | State | Proof before handoff |
|---|---|---|---|---|
| G00 shared contract/auth baseline | Four contributors; integration coordinated by one member | Choices needed by first tickets recorded together | Open | Versioned common spec commit on base branch |
| G01 backend skeleton | M1 contributor; integration coordination | G00 | Backlog | Backend starts, trivial test runs |
| G01B frontend skeleton | M4 contributor; integration coordination | G00 | Backlog | Generated spec client compiles |
| G02 triage factor policy | M3 contributor | G00 | Backlog | Versioned deterministic policy + synthetic counterexample |
| F00 authentication/case guard | M1 contributor TBD | G01 | Backlog | Invalid identity/foreign-case tests |
| P01 network parser | M2 contributor TBD | G01 (real integration waits for F05) | Backlog | One fixture parsed with row/candidate references and failure test |
| U01 API-client configuration | M4 contributor TBD | G01B, F00 | Backlog | Auth/error behavior and generated client type-check |

The next tickets follow the dependency graph in `docs/TASK_BREAKDOWN.md`; consumers may develop against spec-derived tests before producers merge, but cannot claim integration complete until the actual producer passes. Cross-module checks and shared-file conflict resolution are coordinated by one of the four contributors.

## Module work ledger

| ID | Module / task sequence | Assigned person | Branch prefix after common base | Status | Dependencies | Check |
|---|---|---|---|---|---|---|
| M1 | Case intake → immutable file/hash → provenance/audit → access control | TBD | `feat/f*-*` | Backlog | Contracts | `F00–F09`, one row per PR |
| M2 | Document/text/OCR → log/transaction/GPS adapters → video/image → normalization | TBD | `feat/p*-*` | Backlog | Evidence + observation schemas | `P01–P14` and lettered subtasks |
| M3 | Links/graph → scoring → re-triage → conflicts/gaps/clusters/anomalies/hypotheses | TBD | `feat/a*-*` | Backlog | Normalized observations | `A01–A16` and lettered subtasks |
| M4 | Case/evidence UI → priority/graph views → reviews/overrides → cited Q&A | TBD | `feat/u*-*` | Backlog | API and analysis contracts | `U01–U12E`, one view/command per PR |
| INT | End-to-end case fixture, runbook, contract checks, CI and cross-module tests | Four contributors; one coordinates integration | Scoped integration task(s) | Backlog | M1–M4 | Full synthetic workflow and real test output |

## Definition of done for each task

- Scope and acceptance conditions in the PR; no unrelated edits.
- Tests of success and failure cases run with actual results in the PR.
- API/schema impact documented; affected module contributors update the common contract before they diverge.
- Updated status, files/interfaces and next dependency here (the person coordinating integration resolves simultaneous edits to this ledger).
- Reviewed PR merged to chosen integration/base branch; no autonomous merge to `main`.

## Scope from the proposal

The proposed initial system covers intake, hashing/provenance, multimodal extraction, normalization, cross-source graph, adaptive triage/re-triage, clusters, gaps, conflicts, anomalies, reliability/uncertainty, hypotheses, explanations, grounded Q&A, dashboard, human review, audit and evaluation. The full feature/module/test map is `docs/FEATURE_SCOPE.md`. The three-CSV tracer is an *integration starting point*, not a silent deletion of the other proposed capabilities. Full timeline reconstruction is **future** work in the proposal.
