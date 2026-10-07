# EVORA scoped agent assignment templates

Published coordination-branch draft, not a running app. Four people each work on one module; one coordinates integration alongside their module. Full initial proposal scope is fixed. Use the canonical phase/checkpoint ledger in [ROADMAP.md](ROADMAP.md). Assign one catalog row, not an entire module, milestone or full dashboard. Assignees/common commit/allowed paths are filled before delegation.

## Common prefix

> Work on EVORA in `[REPO_PATH]`, branch `[TASK_BRANCH]`, common contract commit `[COMMIT]`. Read AGENTS.md, docs/PROPOSAL.md, docs/PROPOSAL_TRACEABILITY.md, docs/ARCHITECTURE.md, docs/FEATURE_SCOPE.md, docs/TASK_BREAKDOWN.md, docs/ROADMAP.md, docs/CONTRACTS.md, docs/CONTRACT_REVIEW.md, docs/COMMUNICATION.md, docs/INTEGRATION.md, DESIGN.md and specs/openapi.yaml. Inspect actual Git status/files before editing. Confirm `[CHECKPOINT]` matches the task catalog and ROADMAP; follow actual dependency edges, not file row order. Implement only `[TASK_ID + acceptance]` for `[MODULE/PERSON]` within `[ALLOWED PATHS]`. Use canonical OpenAPI 0.2.0 operations/schemas, never alternate endpoints/fields/enums. Needed unresolved gates must be recorded/resolved with affected contributors, not guessed. Write relevant failing behavior tests, then implement and exercise success/failure/case-isolation paths. Use `[FIXTURE]` and `[REAL DEPENDENCY OR DECLARED SCHEMA-DERIVED DOUBLE]`; independent fixture work is allowed, but integrated completion requires real producers. Preserve originals/hash/source locators/immutable completed outputs, case scope and uncertainty where relevant. Frontend uses API only; backend alone accesses SQLite/private storage/derived Neo4j. Report actual commands/results/test doubles/limitations, inspect diff for secrets/unrelated edits and coordinate ledger updates. Do not commit/push/merge beyond explicit branch authorization; never edit main autonomously.

## Assignment card (required fields)

| Field | Fill from catalog/shared base |
|---|---|
| Task/checkpoint and exact acceptance | One ID/row matching ROADMAP and the catalog, success and negative assertions |
| Module/person and coordination | One accountable module; assignee, scoped help if needed |
| Branch/common commit | Short-lived `feat/<id>-<slug>`, exact common spec commit |
| Paths | Actual component/tests after skeleton; no unrelated module/spec/migration overwrite |
| Dependencies | Exact prerequisite IDs and commits; real merged producer or disclosed schema-derived fixture; no false integrated claim |
| Input/output | Existing operation/schema/internal policy and fixture/source locators |
| Gate | Only needed C-03–C-06/setup choice; unaffected work may proceed |
| Commands and proof | Exact implementation test/build/contract commands, read-back, current checkpoint checks and prior completed checkpoint regressions |
| Handoff | Changed paths/interfaces, known limits, next ticket/PR and coordinated status |

## Choosing the next task

Start in the earliest unfinished checkpoint with a dependency-ready bounded row. G00 is the first common task. After the shared base is recorded, G01 and G01B can proceed independently; G01C verifies their skeletons. In 1A, F00 needs C-03 and U01 needs real F00 or a disclosed fixture. In 1B, adapter/lifecycle/UI rows follow actual dependencies; I00B is their real integration gate. In 1C, G01D/G02 precede projection/scoring; I01 requires early provenance/audit and explanations. Never prompt an agent with all checkpoint IDs as one implementation request.

G/I work is assigned to an existing contributor with explicit shared paths. Do not infer a person from a task prefix. Future tasks can be developed independently when their own choices/interfaces are ready, but cannot close a milestone against test doubles. Unimplemented future actions must remain unavailable rather than fake successful.

In 4A select remaining analytical producer rows for component tests, not real-API panel closure. U12A/U12B/U12C/U12D/U12E/U13B can begin fixture-based component work earlier, but their integrated-completion checkpoint is 4B and A17 is an additional prerequisite for each. In 4B verify A17 assembly/coherent publication, complete all six real-API views, then detector feedback/evaluation; retain every existing task acceptance.

## Row-specific module suffixes

### M1 — one Fxx row

> Apply only this row's invariants: F00/F01 authorization; F03/F05 original bytes/hash; F06–F08E append-only audit/private provenance; F09 owning-route regression. Rich model/parser/prompt parameters/input/output/time/verification remain private authorized data, not public audit fields/raw application logs. Shared 400 ApiError mapping is declared contract requiring tests. Do not implement unrelated routes to make the task appear complete.

### M2 — one Pxx row

> For adapter rows, document supported format/model/limits first, then source-located raw/normalized outputs and uncertainty; detection is not a person's identity. Lifecycle rows test idempotency/atomic completed publication, latest completed selection and processing_run_id historical output. P14/P14D preserve private versioned provenance; P15 selects deeper/reconfigured existing-evidence processing internally with a new key, unchanged original and immutable old output. Never invent processing request fields or claim another modality from a single CSV test.

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
