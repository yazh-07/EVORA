# EVORA agent instructions

EVORA is investigative support, not an autonomous guilt or admissibility decision. Do not present uncertain findings as facts. The full initial proposal is fixed build scope; the CSV tracer is a first slice only.

## Before editing

1. Read `docs/PROPOSAL.md`, `docs/PROPOSAL_TRACEABILITY.md`, `docs/ARCHITECTURE.md`, `docs/FEATURE_SCOPE.md`, `docs/TASK_BREAKDOWN.md`, `docs/ROADMAP.md`, `docs/CONTRACTS.md`, `docs/CONTRACT_REVIEW.md`, `docs/COMMUNICATION.md`, `docs/INTEGRATION.md`, `DESIGN.md` and `specs/openapi.yaml`.
2. Check the actual Git status/branch/base and relevant existing files. Published branch-draft docs/schema are not a working application. Never infer implemented behavior or installed packages from a planned ticket.
3. Read the exact checkpoint ledger in `docs/ROADMAP.md`; locate the task in the matching `TASK_BREAKDOWN.md` Checkpoint column. Take one task ID with checkpoint, assigned module/person, exact common contract commit, allowed paths, dependency handling and acceptance tests. Use a fresh session and short-lived feature branch; never assign an entire module to one agent or edit `main` autonomously.
4. Record a needed unresolved choice in the PR/communication queue with exact producer/consumer impact. Resolve that task's gate, not unrelated future choices. Independent implementation against schema-derived fixtures is allowed; real producer integration is required before completion.

## Phase execution rules

- ROADMAP.md alone defines phase/checkpoint order and membership; TASK_BREAKDOWN.md owns row dependencies/acceptance. Table order is not execution order; use the dependency DAG. All implementation starts Backlog. Never skip a gate or claim a whole phase from a subset.
- G00 establishes the common contract/base containing these artifacts before task branches. Do not start from a README-only main or treat uncommitted local phase edits as published instructions. Record the exact reviewed base in the assignment.
- Work on one bounded row in a fresh task branch. Later independent rows may use declared schema-derived doubles; finish checkpoints in order with real producers. Do not wait for full modules to integrate.
- 4A tests remaining analytical producers. U12A/U12B/U12C/U12D/U12E/U13B fixture components may start earlier, but all retain existing dependencies plus A17 and complete integrated real-API acceptance in 4B after coherent assembly/publication, before detector feedback/evaluation. Fixture UI cannot close 4A as real API.
- Preserve earlier capabilities: run current-task negatives and every previously completed checkpoint regression on the combined candidate before an authorized main merge; run smoke checks on the merged commit. Temporary integration branches are optional.
- Security, source provenance, safe rendering and labeled evaluation fixtures start with their producers. Full report/evaluation at the end does not postpone those checks. Generation U10B must not be exposed as verified before U10C fallback/citation checks pass.
- Coordinate shared scaffolding/migrations/spec/generated types/ledger edits; do not overwrite another agent's files or invent a parallel contract. A missing decision blocks affected rows only; record it in COMMUNICATION.md.

## Architecture and integrity invariants

- React + TypeScript frontend uses the API only. FastAPI/Python backend alone accesses SQLite, Neo4j and private original storage. SQLite is authoritative for metadata, immutable processing outputs, analysis snapshots/results and audit. Neo4j is a versioned/rebuildable projection, not the scoring algorithm. Do not create a competing Streamlit dashboard.
- `specs/openapi.yaml` 0.2.0 is the published coordination-branch draft and sole HTTP authority. Do not invent routes, request bodies, fields or enum values. Generate client types from it. A contract change updates spec, producer/consumer, types, fixtures and checks together.
- All operations declare invalid input as 400 ApiError. Shared FastAPI validation must explicitly map default validation errors to that contract; the chosen wire mapping is declared, not already implemented/tested.
- Preserve original private bytes, Evidence.sha256 and source timestamps/values. Every derived edge/finding carries required nonempty unique observation_ids joining to same-case source locators; GraphNode.id is source Evidence/Entity/Event UUID, not an anonymous identifier. Do not require observation_ids on graph nodes.
- Processing outputs and analysis snapshots/results remain immutable. startAnalysis has **no request body**; freeze AnalysisInputSnapshot per `docs/CONTRACTS.md`. Replay the original run for a repeated key before resnapshotting; new key selects new inputs.
- SQL pending run/output → idempotent Neo4j case+analysis-run partition → projection verification → SQL completed publication pointer. Hide partial/failed graph partitions. Retry/rebuild safely; never assume distributed transactions or claim success after only one DB write.
- After polling a completed analysis, UI pins its analysis_run_id across getGraph/listFindings/listTriage and every page. Omitted selector chooses latest completed; pending/failed/missing/foreign selector returns 404. Reject/refetch mismatches, never display mixed runs. listObservations can pin historical completed outputs with processing_run_id.
- Separate extraction confidence, source reliability, corroboration and conclusion uncertainty. Co-mentions/detections are candidate relationships, not verified identity or guilt. Uploaded evidence without observations is not scored under G02; no fabricated factors or P4 placeholders.
- Supported answers cite each factual claim to same-case Evidence ID/source_locator; unsupported responses make no unsupported factual assertion and have no citations. Deterministic tracer is not final LLM RAG. Keep versioned model/parser/prompt/parameters/input/output/time/verification provenance in a private authorized store, not raw application logs/public audit fields.
- Use only synthetic/publicly permitted fixtures. No real evidence, credentials, prompt contents or tokens in Git/logs. No external transfer of real evidence without explicit privacy/provider policy.

## Work and verification

Four people each own one module; confirmed GitHub handles and integration coordination are in `docs/ROADMAP.md` under "Module assignment and live task state". Use that table in each task card; G/I assignments and allowed shared paths still require an explicit handoff. Coordinate shared scaffolding, migrations, spec and roadmap changes; do not invent personnel titles or a fifth member. Any help stays bounded with one accountable interface owner.

Write behavior tests appropriate to the ticket, including its negative/failure/case-isolation paths. Run actual commands, inspect the diff and report results and test doubles honestly. Full integration requires real merged producers; artifact lint is not application verification. Report task/checkpoint, dependency versions, actual read-back and tests, known limitations and next task; checkpoint completion also requires the runbook exit evidence. Coordinate roadmap status changes; never mark a module complete from one row.

Run OpenAPI lint/bundle, generated client/type compilation, `scripts/verify_coordination.py <bundled-json-path>`, the `test_*.py` unittest suite with EVORA_CONTRACT_BUNDLE set to that bundle (jsonschema==4.25.1) and DESIGN lint according to the shared workflow. Package/model versions and Windows support must be demonstrated in setup tasks. No fabricated benchmark data.

Commit/push only when explicitly authorized for the scoped branch; never stage, commit, push or merge outside the user's scope. Keep changes reviewable. Contract/policy decisions belong in versioned source, not a second prose wire schema or agent memory.
