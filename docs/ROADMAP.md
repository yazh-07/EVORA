# EVORA phased roadmap and execution ledger

**Checkpoint 0 is Complete.** All four foundation tasks (G00, G01, G01B, G01C) have passed verification on both Ubuntu and Windows CI runners (Run 39102433077). Checkpoint 0 is **Complete**; Checkpoint 1A tasks (M1 F00, M4 U01) are now unblocked. The original proposal, four modules and selected architecture remain unchanged. Draft OpenAPI 0.3.0 coordinates the explicit user-approved initial-scope addition: local audio/video speech transcription, timestamped source segments, playback/search/candidate extraction and audited human corrections. This is not retroactively an original proposal requirement; all five new tasks remain Backlog, with no domain implementation or model installation claimed.

## Start here

EVORA's workflow is **preserve evidence → extract/normalize → connect and prioritize → discover/re-triage → explain and review**, with source traceability throughout. Phases make that workflow progressively testable; they do not reduce the feature goal or finish modules one at a time.

This file is the **single authority for phase order, checkpoint membership and milestone status**. [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) owns each task's dependencies, contract and acceptance; its Checkpoint column mirrors this ledger and is checked automatically. [INTEGRATION.md](INTEGRATION.md) owns the real execution procedure and negative checks. [FEATURE_SCOPE.md](FEATURE_SCOPE.md) and [PROPOSAL_TRACEABILITY.md](PROPOSAL_TRACEABILITY.md) retain feature/source coverage. Do not create a second phase list or treat a phase as an agent prompt.

1. Use the confirmed GitHub-handle assignments in the module table below. `whale2186` coordinates shared edits alongside M3; no fifth person or personnel title. Ownership alone does not complete G00 or an implementation task.
2. G00 establishes one reviewed, published common contract/base commit **before task branches depend on it**. Current remote main has only a README; do not branch implementation from a README-only base. Land the planning/contracts through an authorized PR or use an explicitly chosen shared coordination base. No automatic main merge is authorized by this plan.
3. Select one bounded task in the earliest unfinished checkpoint, resolve only its needed choices, fill the assignment card in [AGENT_TASKS.md](AGENT_TASKS.md), and use a short-lived task branch.
4. Implement/test and integrate frequently. A test double permits independent work, not checkpoint completion. Run real producers/consumers and all previously completed checkpoint regressions before promotion.
5. Record results, remaining limitations and next task. Do not mark a phase complete until **every assigned task and its exit evidence** is complete. Windows failure blocks a Windows/reproducibility claim, not unrelated fixture-based development.

## Phase outcomes

| Phase | Outcome | Checkpoints | Not yet claimed |
|---|---|---|---|
| 0 | Common contract and runnable backend/frontend skeletons | 0 | Domain features, installed models or full-system reproducibility |
| 1 | Authorized originals → network/GPS processing → source-backed graph and explained initial triage in the UI | 1A, 1B, 1C | Adaptive feedback, all modalities or final RAG |
| 2 | New-evidence adaptation, human review/override and deterministic source-grounded interaction | 2A, 2B, 2C | Detector/deeper-processing feedback or full LLM generation |
| 3 | All initial modality adapters connected to common outputs and the existing investigation workflow | 3A, 3B, 3C | Complete detector assembly or final RAG |
| 4 | Test remaining analytical producers (4A); assemble/publish all factors/findings and complete real-API panels/inspector, then detector feedback/evaluation (4B); prove deeper-existing-evidence feedback (4C) | 4A, 4B, 4C | Final verified generative interface |
| 5 | Full case-context retrieval and approved, verified LLM answers with private provenance | 5A, 5B | Full-scope consolidated evaluation/reproducibility |
| 6 | Consolidated measured evaluation, all-feature integration, clean reproducibility and final report | 6A, 6B, 6C | Timeline reconstruction or forensic certification |

## Exact checkpoint ledger

Comma-separated IDs below are **exhaustive assignments**, not ranges. Each catalog task occurs exactly once. Order means integrated-completion order; within each row use the dependency DAG. Exit evidence supplements, never replaces, every task's acceptance. Checkpoints are deliberately smaller than phases so the first usable evidence path is tested before graph/triage work is finished.

| Checkpoint | Exact task membership | Exit gate IDs | Exit evidence | State |
|---|---|---|---|---|
| 0 | G00, G01, G01B, G01C | G00, G01, G01B, G01C | G00 records the shared base; G01/G01B start and pass real skeleton tests/type checks; G01C proves clean skeleton Windows/CI setup. Verified green on both ubuntu-latest and windows-latest (Run 39102433077). | Complete |
| 1A | F00, F01, F02, F03, F04, F05, F06, F07, F09, U01, U02, U02B, U03, U04, I00 | I00 | I00 proves real authorized create/list/upload/hash/metadata/download and safe intake audit, two actors/cases and negative access/input paths. | Backlog |
| 1B | P01, P02, P03, P03B, P03C, P04, P04B, P05, P05B, P14, P14B, P14C, F08, U05C, U05, U05B, U13, I00B | I00B | I00B proves UI start/poll and immutable network/GPS observations/entities/events, raw/normalized source values, private provenance, atomic retries/failures and all-page overview. | Backlog |
| 1C | G01D, G02, A01, A02, A03, A03B, A04, A01B, A05, A05B, A06, A15, F08B, U05D, U06, U07, U07B, I01 | I01 | I01 proves coherent SQL/Neo4j publication, source-backed graph/findings and initial relevance/connectivity scores, explanations, pinned reads/pagination and crash/recovery/auth negatives. | Backlog |
| 2A | P06, A07, U06B, I02 | I02 | I02 proves the message creates a previously absent D-7/D-8 candidate link and changes an earlier priority/rank under recorded golden outputs; historical runs stay intact. | Backlog |
| 2B | U08, U08B, U09, U09B, F08C, I02B | I02B | I02B proves audited reviews and overrides, live override overlay with stable pinned page membership/order and unchanged automated history. | Backlog |
| 2C | A16, U10, U11, I02C, I03 | I02C, I03 | I02C proves claim/source-locator navigation and unsupported answers with safe retrieval audit; I03 proves clean tracer Windows/CI execution, not full LLM RAG. | Backlog |
| 3A | P07, P11, P12, P13, P13B, I04 | I04 | Supported text/mobile/transaction adapters and text entities/events pass real source/failure tests; I04 executes labeled extraction/link evaluation with actual counts. | Backlog |
| 3B | P08, P09, P10, P16, P16B | P08, P09, P10, P16, P16B | Approved OCR/image/video-visual and local audio/video-speech adapters pass source region/page/frame/original-media timestamp, uncertainty, malformed/unavailable-model and resource-limit tests; P16/P16B prove silence/no-audio versus failure, timestamp alignment and source-backed candidate extraction/search support. No named-person or speaker identification. | Backlog |
| 3C | P05C, P14D, F08D, U13C, U14, U14B, U14C, I03B | I03B | I03B proves full supported dispatch/common entity-event outputs, private provenance, real locator-to-original UI navigation and transcript playback/all-page local search plus audited append-only corrections/history; machine outputs and frozen analysis remain intact; earlier checkpoints rerun. | Backlog |
| 4A | A03C, A08, A09, A10, A10B, A11, A11B, A12, A12B, A13, A13B, A14 | A03C, A08, A09, A10B, A11B, A12B, A13B, A14 | Every remaining analytical factor/detector producer has real positive/negative/source tests. Component success is not assembled publication, real-API panel/inspector completion or pipeline feedback completion. Earlier declared-fixture UI work cannot close 4A as real API. | Backlog |
| 4B | A17, A19, U12A, U12B, U12C, U12D, U12E, U13B, I07, I05B | A17, U12A, U12B, U12C, U12D, U12E, U13B, I07, I05B | A17 assembles every stage and coherently publishes factors/findings; U12A/U12B/U12C/U12D/U12E/U13B complete real-API same-run panels/uncertainty inspection with positive/negative/source, empty/error and immutable snapshot-source tests. Then I07 proves detector → actual factor → earlier priority/history changes; I05B measures false positives/misses and controls. | Backlog |
| 4C | P15, A18, I07B, I05 | I07B, I05 | I07B proves same Evidence/hash with deeper processing, new frozen snapshot and justified rerank plus failure/replay fallback; I05 measures all feedback paths and weight sensitivity. | Backlog |
| 5A | G03, A16B | G03, A16B | G03 records approved provider/privacy/verification/no-paid-CI policy; A16B retrieves authorized full context filtered to the chosen immutable analysis inputs. | Backlog |
| 5B | U10B, U10C, F08E, U11B, I05C | F08E, U11B, I05C | U10B/U10C/U11B operate together: no unverified answer release; F08E proves private provenance; I05C exercises the real approved provider plus citation/fallback/injection/privacy checks and measures final RAG. | Backlog |
| 6A | I08 | I08 | I08 consolidates all-modality extraction/link/ranking/detector/explanation/final-RAG evaluation with actual labels/counts/versions and limitations. | Backlog |
| 6B | I09, I09B | I09, I09B | I09 exercises every feature/operation with real producers; I09B proves clean full-scope Windows and CI setup/build/run and distinguishes test adapters from actual provider runs. | Backlog |
| 6C | I06 | I06 | I06 reports measured threats/provenance/resource/privacy/competitor limitations after the full-scope gates; no invented metrics/originality/admissibility claims. | Backlog |

## Work in parallel without breaking the sequence

Four people keep their module responsibility and contribute the part needed for the active checkpoint. M2/M3 have heavier work; scoped help is allowed with one accountable interface. Nobody waits for an entire module to finish.

- A task can start when its actual contracts/choices are ready, using disclosed schema-derived fixtures if producers are not yet merged. It cannot be marked integrated-complete until real prerequisites pass.
- Later independent tasks may start early; finish/publish phase milestones in ledger order. In particular eligible factors/detectors may be developed during modality work, but A17/I07 require P05C's complete modality handoff. P15/A18 additionally require full dispatch and analytical assembly.
- U12A/U12B/U12C/U12D/U12E/U13B may start component work against declared fixtures before 4B. All retain their earlier prerequisites and additionally require real A17 assembly/publication for integrated completion in 4B; fixture panels cannot certify 4A as real API.
- G01D is needed for 1C graph projection, not 1A intake. G02 is needed before score implementation; define golden positive/counterexamples early. G03 is needed for full generation in 5A/5B, not deterministic 2C or OCR/image/video adapters.
- Security, safe rendering, provenance and honest error states apply from their first producer/view. F06 precedes integrated intake; P14/F08 precede integrated processing; F08B/A15 precede integrated analysis; U08/U09 write their own audit records before F08C regression.
- Build labeled positive/negative fixtures and threat/privacy controls alongside each feature. I04/I05B/I05/I05C execute in the phases that introduce the measured behavior. Phase 6 consolidates evaluation; it is not the first testing phase.

Speech segments retain original Evidence/hash/run and original-timeline media offsets; video clock origin may remain uncertain, not an invented wall-clock event time. Silence/no-audio is honest empty output; decoding/model failure is failed processing. Unclear speech remains unverified and model confidence is not generic probability. Original video and its audio derivative are not independent corroboration. No speaker identification, voice matching, emotion inference, diarization or translation in initial scope. U14B/U14C use only draft 0.3.0 listTranscriptRevisions/appendTranscriptRevision for immutable append-only human corrections separately from machine outputs and frozen analysis; base transcripts remain Observation/ProcessingRun with downloadEvidence for playback.

I08 measures speech transcription errors and segment timestamp alignment with labeled controls plus correction/history preservation; I09 closes every new task P16/P16B/U14/U14B/U14C. I09B demonstrates clean local speech model/runtime/language/codec/resource setup and offline execution. I06 reports measured speech/hallucination/alignment/clock-origin/language/codec/correction limitations, not fabricated accuracy or forensic certainty.

## Promotion and regression procedure

1. Use `feat/<task-id>-<slug>` PRs, not one huge module/phase implementation branch. Shared skeleton/migration/spec/generated-client/ledger edits are serialized or explicitly partitioned.
2. Combine changes frequently through tested PRs. A temporary `integration/phase-<n>` branch is optional when dependent branches need joint testing; do not keep a permanent extra branch without a reason.
3. Before an authorized merge into main, run task tests, contract/planning checks, the active checkpoint's real end-to-end checks and **all previously completed checkpoint regressions** on the combined candidate. No stub producer at a completion gate. Unimplemented future actions must be absent/clearly unavailable, never a broken or fictional successful UI.
4. After merge, read back the exact main commit/CI result and run smoke checks on that merged tree; record checkpoint, task/PRs, contract commit, commands/results and limitations. Optionally tag the verified phase milestone. Never mark success from a push alone.
5. Next task branches start from the updated verified common base; refresh/generated client and contract commit together. A failed milestone remains open with a bounded corrective task; do not silently bypass it or revert unrelated collaborator work.

## Targeted decisions still open

| Gate | Resolve before | Required record |
|---|---|---|
| C-03 | F00/U01 in 1A and every protected API | **Resolved (coordination policy 2026-10-18):** synthetic bearer token verifier (`investigator-1`, `investigator-2`), in-memory client token handling, and non-leaking 404 case-membership guard. Implementation in F00/U01; no hard-coded shared production token |
| C-04 first CSV | F03 in 1A; P04/P14B in 1B | **Open:** M1 F03 intake and M2 P04/P14B processing need compatible content/byte/row/BOM/malformed/unsupported/failure policy and fixtures; M4 U03/U05 must display the declared rejection/failed-run outcomes |
| C-04 later adapters | Their 3A/3B tasks, including P16/P16B | **Open:** supported layouts/models/versions/resources and private data boundaries, independent of final LLM provider; select/test approved local pretrained speech model/version/runtime/languages/codec support and duration/compute/memory limits, not chosen or installed here; M2 outputs feed M3 analysis and M4 source/playback/correction views; no external evidence transfer |
| C-05/G02 | A03/A03B/A04 in 1C, then later factor wiring | **Open:** M3 G02 must version factor/missing/weight/band/tie/independence/confidence policy and goldens for M2 source-lineage inputs and M4 explanations; proposal numbers remain experimental examples |
| Local deterministic grounding/privacy | A16/U10 in 2C | Authorized retrieval/claim support/unsupported and safe audit policy; no final provider requirement |
| C-06/G03 | 5A/5B generation and evaluation | **Open:** approved provider/model/private boundary/cost/credentials/thresholds/fallback and actual-provider vs no-paid CI proof for M3 retrieval, M4 generation/verification and M1 private provenance; deterministic/local speech work does not choose this provider |
| Assignment/common base/setup | Each task handoff | Module/person, allowed paths, exact common spec commit and tested commands/versions; no guessed installation |

See [COMMUNICATION.md](COMMUNICATION.md) and [CONTRACTS.md](CONTRACTS.md) for concrete choices; this ledger does not choose them by implication.

## Module assignment and live task state

| Module | Assigned GitHub handle | Accountable boundary | State |
|---|---|---|---|
| M1 Evidence Foundation | sharmelas-925 | Case/access, private originals/hash, metadata and audit/provenance foundations | Backlog |
| M2 Multimodal Processing | yazh-07 | Adapters, normalization/entities/events, immutable processing runs and deeper processing | Backlog |
| M3 Fusion and Adaptive Triage | whale2186 | Derived graph, factors/detectors/snapshots/retriage and retrieval context | Backlog |
| M4 Investigator Application | JebasJ | React UI plus review/override and grounded-generation/verification backend APIs | Backlog |

`whale2186` coordinates shared files/integration alongside M3. G/I work is bounded shared work assigned to an existing contributor, not automatically to the person coordinating and not a fifth module/person. A module is not standalone software and not an agent mega-task. The user explicitly assigned G00/G01/G01B/G01C as recorded below; other shared-task assignees and paths still need their own handoffs. G01C is In Progress; G00/G01/G01B are accepted dependencies in its committed common base. All domain tasks remain Backlog. Earlier session records below retain their historical states; the G01C record supplies the current handoff and remaining exit evidence.

For each assigned task record `task ID | checkpoint | module/person | branch/common spec commit | state | consumed/produced interface | actual commands/results + test doubles | PR/next task`. Serialize ledger edits. States: **Backlog**, **In Progress**, **Complete** (acceptance and real dependency integration verified), **Blocked** (exact needed decision). Current task state defaults to Backlog; no implementation completion is claimed here.

### U01 live record — 2026-10-22

**U01 / Checkpoint 1A / M4 / JebasJ / In Progress.** Automatically selected from
the user's one-task assignment on `feat/u01-authenticated-api-client`, from exact
published coordination base **6496c5e9e17f2000b64a64f79d2fb166c6ce2094**. Clean HEAD
matched the freshly fetched origin branch; remote main is still README-only.
The base includes real G01B **328c103d0f0383c7b4979bd8199b4201408e2a68** and its
accepted G00/G01 ancestry. F00 is absent, so this is independent client work with
explicitly disclosed schema-derived Fetch/localhost fixtures under AGENT_TASKS,
not real backend authorization or integrated completion. C-03's later declared
resolution supplies memory-only bearer handling and 401/404 policy; no provider,
token issuance or expiry mechanism is chosen here.

Allowed paths and acceptance are in [the U01 assignment](AGENT_TASKS.md#u01-assignment--2026-10-22).
Consumes unchanged draft 0.3.0 generated API types; produces a shared typed Fetch
client and React provider with a configurable origin, in-memory token lifecycle,
safe shared failures and old-session response invalidation. No domain routes,
case UI, models, package pins or full-scope feature decisions change.
**19 frontend / 122 coordination / 14 backend tests pass**, no skips; frontend
freshness/typecheck/build, OpenAPI lint/bundle/generated strict types, verifier,
DESIGN and whitespace checks pass. Seven synthetic responses validate against
the contract; focused 401 negative and real Fetch redirect refusal pass.
Actual skeleton localhost smoke returns backend 404/frontend 200 and stops both
servers. [Exact commands and limits](PREIMPLEMENTATION_REVIEW.md#u01-verification--2026-10-22)
distinguish fixtures/HTTP checks from absent real F00 and browser integration.
U01 stays **In Progress**, awaiting review and real F00 integration; Checkpoint
1A stays Backlog. U02 requires accepted U01 and F02; no second task is started.

### G00 live record — 2026-10-18

Historical G00 session record follows. **Current dependency handoff:** the subsequent G01 user assignment explicitly accepts committed G00 **1721bfff9640263d2799434455cdb9c4f345ac35** (`feat/g00-coordination-base`) as the shared base. G01 read back clean HEAD and the local `origin/feat/g00-coordination-base` at that exact commit; no new fetch, remote CI or main merge is claimed. The historical no-commit result below describes the earlier session, not the current Git history.

**G00 / Checkpoint 0 / shared integration coordination / whale2186 / In Progress.** The user assigned `feat/g00-coordination-base` from exact shared base **114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb**, matching both starting HEAD and local `origin/docs/coordination-foundation`. The base contains the coordination artifacts and unchanged `specs/openapi.yaml` draft 0.3.0. Dependencies: none. Allowed paths: `docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`, `docs/COMMUNICATION.md`, `docs/AGENT_TASKS.md`; see the [filled assignment](AGENT_TASKS.md#g00-assignment--2026-10-18).

Verification on Linux with Node 22.23.3, npm 12.2.0, Python 3.14.8 and scratch jsonschema 4.25.1: requested npx commands failed registry DNS (`EAI_AGAIN`); equivalent cached **Redocly 2.57.0** lint/bundle, **openapi-typescript 7.10.1** generation, **TypeScript 5.9.3** compilation and **DESIGN 0.4.0** lint passed. Lint retains one nonblocking missing-license warning; DESIGN has zero errors/warnings. The coordination verifier passed **27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 proposal mappings**; **122 unittests passed**, including mutation negatives and synthetic schema fixtures. Final edited-tree checks and exact commands are recorded in [G00 verification](PREIMPLEMENTATION_REVIEW.md#g00-verification--2026-10-18). These are artifact checks, with no application doubles presented as real producers. No earlier checkpoint is complete.

C-03/C-04/C-05/C-06 remain **Open** with the targeted producer/consumer effects above and in the review/communication queue. This task does not settle auth, adapters, scoring or providers. Local documentation is ready for review; no new commit, push, merge, remote CI or Windows/skeleton run is claimed. Checkpoint 0 remains **In Progress**, with **G01/G01B/G01C Backlog**. Next dependency-ready scopes after G00 handoff acceptance are **G01**, or independent **G01B**; explicit G/I assignee/allowed-path records are still required. G01C waits for both real skeletons. Do not infer G01/G01B ownership from module coordination or start them in this session.

### G01 live record — 2026-10-18

**G01 / Checkpoint 0 / shared integration coordination / whale2186 / In Progress (locally verified, awaiting review/integration).** Branch `feat/g01-backend-skeleton`, exact common contract/base and dependency **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**. Starting HEAD and local G00 remote-tracking ref matched this commit with a clean tree. Allowed paths: `backend/`, `pyproject.toml` / `requirements.txt`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. The [assignment](AGENT_TASKS.md#g01-assignment--2026-10-18) records the user's explicit shared-file handoff.

Produced a FastAPI app factory, file-backed SQLite lifespan/connection foundation and shared request-validation handler returning HTTP 400 `ApiError` with `code=INVALID_INPUT`. No HTTP routes or domain tables were added; schema-derived ApiError validation uses the unchanged draft 0.3.0 bundle. Synthetic test-only routes exercise real FastAPI request parsing; real temporary SQLite files prove commit/read-back, rollback/close, foreign keys, separate app configuration and failed startup. These probes do not implement F00/F01 or prove case authorization.

Tested **CPython 3.14.8 / SQLite 3.54.0**, FastAPI **0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, Uvicorn **0.54.0**, HTTPX **0.28.1** and jsonschema **4.25.1**; all 22 requirements pins match observed distribution metadata. **14 backend tests and 122 coordination tests passed**, no skips. Verifier, exact-version cached OpenAPI lint/bundle, generated TypeScript strict compilation, DESIGN lint and whitespace checks passed. One existing missing-license warning remains. [Actual commands/results](PREIMPLEMENTATION_REVIEW.md#g01-verification--2026-10-18) and the backend setup/run/failure checklist in `backend/README.md` distinguish local execution from clean installation.

Uvicorn completed real startup/shutdown; the sandbox denied socket binding, so an external HTTP listener was not verified. Package-index installation was unavailable; the tested scratch environment reuses system packages and cached jsonschema. Requested DESIGN npx failed DNS; cached DESIGN **0.4.0** passed with zero errors/warnings. Windows, Python 3.12 application compatibility and new remote CI are untested. G01C must reconcile the Python baseline with existing artifact-only CI and prove clean skeleton setup after G01B. C-03–C-06 remain open for affected domain rows; no G01 implementation decision is blocked by them.

No commit, push, merge or staging was performed. **Checkpoint 0 stays In Progress; G01C stays Backlog.** Next dependency-ready scope is independent **G01B**, requiring an explicit shared-task assignee/allowed-path handoff; G01C waits for both real skeletons and their accepted integration/handoff.

### G01B live record — 2026-10-18

**G01B / Checkpoint 0 / shared integration coordination / whale2186 / In Progress (locally verified, awaiting review/integration).** Branch `feat/g01b-frontend-skeleton`, exact common contract/base and dependency **G01 at e0257a6ad231105b93ae98a97f176ed233a25412** (including G00 at `1721bff`). Starting HEAD matched this commit with a clean tree. Allowed paths: `frontend/`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. The [assignment](AGENT_TASKS.md#g01b-assignment--2026-10-18) records the user's explicit shared-file handoff.

Produced a React + TypeScript frontend skeleton under `frontend/` using esbuild bundling/serving and React 19.3.0, TypeScript 5.9.3, and openapi-typescript 7.10.1. Client types generated into `frontend/src/api/schema.d.ts` from unchanged `specs/openapi.yaml` 0.3.0. The skeleton enforces DESIGN.md design tokens (IBM Plex Sans, color tokens, semantic landmarks) with an accessible skip-link and contextual evidence details inspector. Tests verify workspace mounting and honest unavailable-state rendering without API traffic or synthetic domain buttons.

Tested on **Node 26.7.0 / npm 11.19.0 / esbuild 0.28.1 / TypeScript 5.9.3**. Frontend test suite (`node scripts/build-test.mjs && node --test test/*.test.mjs`) passed (2/2 tests, OK in 82ms); `tsc --noEmit` and build script passed. In addition, all 14 backend tests, all 122 coordination tests, verifier, OpenAPI lint/bundle, DESIGN lint, and git whitespace checks passed. Actual commands/results in [G01B verification](PREIMPLEMENTATION_REVIEW.md#g01b-verification--2026-10-18) and setup/run steps in `frontend/README.md`.

No commit, push, merge or staging was performed. **Checkpoint 0 stays In Progress; G01C stays Backlog.** Next dependency-ready scope is **G01C** (Verify skeleton Windows and CI setup), requiring both real skeletons and explicit CI/Windows verification. Stop for G01B review before another task.

### G01C live record — 2026-10-18

**G01C / Checkpoint 0 / shared integration coordination / whale2186 / Complete.** Branch `feat/g01c-skeleton-ci`; exact common contract/base **328c103d0f0383c7b4979bd8199b4201408e2a68** (`feat/g01b-frontend-skeleton`). Starting branch/HEAD matched the assignment and worktree was clean. Real committed dependencies: **G01 e0257a6ad231105b93ae98a97f176ed233a25412**, **G01B 328c103d0f0383c7b4979bd8199b4201408e2a68**, transitively **G00 1721bfff9640263d2799434455cdb9c4f345ac35**. Allowed paths: `.github/workflows/`, `backend/README.md`, `frontend/README.md`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`. See [assignment](AGENT_TASKS.md#g01c-assignment--2026-10-18).

The workflow clean-installs `requirements.txt` and the frontend lockfile on **ubuntu-latest/Bash** and **windows-latest/PowerShell**, using CPython **3.14.8**, Node **22.23.3**, npm **12.2.0**, jsonschema **4.25.1** and UTF-8 Python mode. Each OS runs all shared coordination checks, warning-strict backend tests and frontend freshness/typecheck/test/build. Line endings are normalized via `.gitattributes` to LF. Both jobs passed green on GitHub Actions PR #1 (Run ID **39102433077**): `windows-latest` passed in 2m53s and `ubuntu-latest` passed in 51s.

Current exit-gate evidence:

| Gate | Evidence on the accepted combined candidate | Status |
|---|---|---|
| G00 | Exact common-base ancestry read back; lint/bundle/generated strict types/verifier/122 coordination tests/DESIGN pass | Complete |
| G01 | Clean isolated requirements install, all 22 pins read back, pip check, 14 warning-strict tests; real SQLite and localhost Uvicorn startup/404/shutdown | Complete |
| G01B | Lockfile clean install, generated API freshness/typecheck, 2 real shell render tests/build and localhost dev-server HTTP 200 | Complete |
| G01C | Multi-OS workflow, actionlint, PowerShell instructions and verified green CI run on both ubuntu-latest and windows-latest (Run 39102433077) | Complete |

**Checkpoint 0 is Complete.** All four foundation tasks G00, G01, G01B, G01C have satisfied their exit evidence.

The next active checkpoint is **1A**: **F00 / sharmelas-925** (Evidence Foundation authentication and case guards) requires C-03 identity policy before protected APIs; **U01 / JebasJ** (Case workspace UI) follows F00. No new shared task is automatically assigned to whale2186. G01D/G02 are Checkpoint 1C and need separate handoffs.

Full timeline reconstruction/chronological visualization remains future. Basic time normalization, temporal factors, conflict/gap reasoning and event inspection remain initial scope. Completion of Phases 1/2 is an integration slice, not completion of the full proposal. I09/I09B cover every feature task; I06 follows full closure.
