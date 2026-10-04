# EVORA roadmap, assignment and execution ledger

**Published coordination-branch draft, not a running system.** The full initial proposal is fixed build scope. Four people each work on one module; one coordinates integration alongside their module. Assignees remain TBD; no fifth person or personnel title is implied.

## Scope and readiness

| Item | State | Next evidence |
|---|---|---|
| Full proposal scope/40-section coverage | Fixed initial goal; source preserved and mapped | `PROPOSAL.md`, `PROPOSAL_TRACEABILITY.md`, feature/catalog closure |
| React/TypeScript + FastAPI/Python + SQLite/private originals + derived Neo4j | Architecture selected | G01/G01B/G01D establish tested pinned versions, connections and commands |
| Version 0.2.0 / same 25 operationIds | Published coordination-branch draft | Exact shared contract commit recorded in each assignment; actual checks in PREIMPLEMENTATION_REVIEW |
| Snapshot/idempotency/trigger/400/selectors | Declared draft contract | A05/F00/A05B/A06/P04B/I01/I07B real behavior/race/failure tests |
| C-03 auth/membership/token handling | Open dependent gate | F00/U01 need chosen tested policy |
| C-04 CSV limits/BOM/malformed/failure semantics | Open dependent gate | F03/P04/P14B need chosen fixtures/error policy; later formats before respective rows |
| C-05 scoring/golden reranks | Open dependent gate | G02 functions/missing/ties/independence/weights/detector mapping and positive/counterexample tests |
| C-06 full RAG provider/privacy | Open dependent gate | G03 approved policy/provider; final U10B/U10C/I05C execution |
| One assignee per M1–M4; one also coordinates | TBD | Record assignments without titles; scoped help for heavier M2/M3 |
| Windows/packages/models/resources | Unverified | Skeleton G01C then full-scope I09B real clean execution |

Ready for review/setup and unaffected scoped work. Independent implementation may use accepted-schema fixtures/test doubles; real producers are required for integration completion. Open targeted gates are neither blanket all-clear nor blanket stop. Coordination artifact checks are not app tests or benchmark results.

## Stage ledger

| Stage | Concrete tasks/gates | State | Completion means |
|---|---|---|---|
| Shared base/setup | G00/G01/G01B/G01C/G01D; G02/G03 targeted policy | Backlog | One exact common spec version, tested package/connection setup and needed policy |
| First CSV tracer | F00–F09/P01–P06/A01–A07/U01–U11 and relevant lettered rows; I01/I02/I02B/I02C/I03 | Backlog | Real intake→start processing→start analysis→pinned UI, rank change, review/override, deterministic grounded Q&A and tracer-only reproducibility |
| Full processing | P07–P14D/P05C/F08D | Backlog | All modality adapters produce common immutable source-located outputs and private provenance |
| Complete analytical feedback | A03C/A08–A19, P15, I07/I07B | Backlog | All factors wired, detectors alter existing priorities, optional deeper existing-evidence processing changes snapshot/rank while preserving history |
| Full dashboard and approved LLM RAG | A16B/U10B/U10C/U11B/U12A–E/U13/U13B/U13C/F08E | Backlog | API-only complete dashboard plus real approved generation/verification/private provenance |
| Full evaluation/integration/reproducibility | I04/I05/I05B/I05C/I08/I09/I09B | Backlog | Actual full-modality metrics and all features tested with real producers; clean Windows/CI full-scope execution |
| Final research/threat/limitations report | I06 | Backlog | Completed full-scope gates, actual limitations and cited comparison, no originality/admissibility overclaim |

`TASK_BREAKDOWN.md` is the authoritative ID/dependency/acceptance catalog. The stage rows are milestones, never one-agent assignments or evidence that omitted lettered tasks are optional. All catalog rows start Backlog. I09/I09B dependency closure includes **every** F/P/A/U task; I06 follows full-scope gates, not merely I03.

## Module assignment ledger

| Module | Assigned person | Interface responsibility | Branch pattern | State |
|---|---|---|---|---|
| M1 Foundation | TBD | Case/access, originals/hash, metadata, private provenance/audit | `feat/f<id>-<slug>` | Backlog |
| M2 Processing | TBD | Adapters, entities/events/normalization, immutable runs and deeper processing | `feat/p<id>-<slug>` | Backlog |
| M3 Fusion/Triage | TBD | Versioned graph projection, detectors/factors/snapshots/retriage/retrieval | `feat/a<id>-<slug>` | Backlog |
| M4 Investigator Application | TBD | React UI and commands, backend review/override, generation/verification | `feat/u<id>-<slug>` | Backlog |

Integration is shared work coordinated by one of these four alongside their own module, not a separate person/module. Use scoped G/I task branches where needed. Heavier M2/M3 work may receive bounded help while retaining accountable interfaces.

## Per-task live ledger and handoff

When a row is assigned, add `task ID | module/person | branch/common spec commit | state | consumed/produced interface | actual tests/result | PR/next dependency` here or in its linked PR. Serialize shared ledger changes. States: **Backlog**, **In Progress**, **Complete** (implemented, real dependency integration tested and reviewed), or **Blocked** with exact needed decision. Never mark complete from only schema lint or test doubles.

Definition of done: one bounded scope/allowed paths; success/failure/security tests appropriate to the row actually run; no secrets/unrelated diffs; contract impact and generated types coordinated; actual output and source/provenance trace reported; reviewed merge to chosen base only under authorization. No long-lived module-wide mega-prompt, autonomous main changes or fabricated status/metrics.

Full timeline reconstruction is future. Basic timestamp normalization/temporal reasoning, all initial dashboard/LLM/feedback features and evaluation remain initial scope. See source traceability rather than quietly reclassifying unfinished features as future.
