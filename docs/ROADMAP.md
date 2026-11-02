# EVORA phased roadmap and execution ledger

**Checkpoint 0 and Checkpoint 1A are Complete.** All four foundation tasks (G00, G01, G01B, G01C) passed Ubuntu and Windows CI (Run 39102433077). All fifteen tasks of Checkpoint 1A (M1: F00, F01, F02, F03, F04, F05, F06, F07, F09; M4: U01, U02, U02B, U03, U04; Joint: I00) are merged and verified green. Real HTTP/SQLite smoke test exercises case creation, streaming upload of synthetic CSV, SHA-256 matching, original byte download roundtrip, audit event listing (`uploadEvidence`), actor isolation, and 400/401/404 error responses. Checkpoint 1A is **Complete**; Checkpoint 1B (M2: P01, P02, etc.) is now **unblocked and active**. The original proposal, four modules and selected architecture remain unchanged. Draft OpenAPI 0.3.0 coordinates the explicit user-approved initial-scope addition: local audio/video speech transcription, timestamped source segments, playback/search/candidate extraction and audited human corrections. This is not retroactively an original proposal requirement; all five new tasks remain Backlog, with no domain implementation or model installation claimed.

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
| 1A | F00, F01, F02, F03, F04, F05, F06, F07, F09, U01, U02, U02B, U03, U04, I00 | I00 | I00 proves real authorized create/list/upload/hash/metadata/download and safe intake audit, two actors/cases and negative access/input paths. Verified green with full smoke. | Complete |
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

### I00 live record — 2026-11-01

**I00 / Checkpoint 1A / whale2186 / joint integration coordination / Complete.**
Explicit user assignment on `feat/i00-authorized-intake-gate`; clean starting
HEAD and reviewed common contract/base are
**c0561bbb3978e37395218bf1a771ecd562d3c2dd**. OpenAPI draft 0.3.0 and
`docs/INTEGRATION.md` are unchanged. All dependencies below are real merged
producers/consumers on that base. This is the current Checkpoint 1A task state;
earlier session records retain historical local/integration statuses.

| Task | Owner/boundary | State on reviewed candidate |
|---|---|---|
| F00 | sharmelas-925 / M1 authentication and case access | Complete |
| F01 | sharmelas-925 / M1 case creation | Complete |
| F02 | sharmelas-925 / M1 case list/detail | Complete |
| F03 | sharmelas-925 / M1 original intake | Complete |
| F04 | sharmelas-925 / M1 evidence metadata | Complete |
| F05 | sharmelas-925 / M1 original download | Complete |
| F06 | sharmelas-925 / M1 append-only intake accounting | Complete |
| F07 | sharmelas-925 / M1 authorized audit list | Complete |
| F09 | sharmelas-925 / M1 access/error regression | Complete |
| U01 | JebasJ / M4 typed authenticated client | Complete |
| U02 | JebasJ / M4 case list/detail | Complete |
| U02B | JebasJ / M4 case creation | Complete |
| U03 | JebasJ / M4 upload/metadata | Complete |
| U04 | JebasJ / M4 verified original download | Complete |
| I00 | whale2186 / joint real intake exit verification | Complete |

The real HTTP/SQLite smoke exercises the M4 client/stores/download controller
against merged M1 producers and serves the built UI at the API origin. Case
creation, immediate listing, Unicode codepoints, whitespace 400 errors, two-actor
isolation, foreign/missing 404, invalid limit 400, and invalid token 401 pass.
Multipart streaming upload, exact SHA-256 calculation, original byte-for-byte
download roundtrip, empty original support, oversize 413 rejection, and safe
intake audit trail listing (`action=uploadEvidence`) pass. Read-only SQL/file
snapshots, multi-event UTC monotonic ordering, and actor isolation pass.

**116 backend, 122 coordination and 48 frontend tests pass** on this Linux
candidate. OpenAPI lint/bundle, verifier, generated strict types, frontend
freshness/typecheck/build, DESIGN and whitespace checks pass. Checkpoint 1A is
**Complete**. Checkpoint 1B (M2: P01, P02, etc.) is now **unblocked and active**.

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

## U02B reconciliation state — 2026-10-31

User-requested reconciliation is **In Progress** on `feat/u02b-reconcile` from
published shared base **d24312f939877e6959c6ff46d3e1d81051e474a6**. F03/F04,
U02B/U03 and F05 are implemented merged ancestors, despite historical session
statuses below. Original local U02B edits are preserved in their original
worktree. The reconciliation reuses the integrated case form and carries over
Unicode length/error-handling improvements without replacing U03 evidence UI.
41 frontend tests pass; 70 backend tests run (69 pass, symlink escape skipped
because this Windows account cannot create symlinks); real U02B/U03 HTTP/SQLite
integration, build/types/contract/DESIGN pass. Verification and exact synthetic
checklist: PREIMPLEMENTATION_REVIEW.md, U02B reconciliation section. No new
browser/hosted CI claim; no commit/push/merge. Next eligible M4 row is U04 after
this review and its own bounded assignment. Checkpoint 1A remains open.

## U04 current handoff — 2026-10-31

**U04 / 1A / M4 JebasJ / Complete**, user authorized finish, commit/push and
merge of the existing feat/u04-evidence-download task only. Integrated at
**9444ef703ea88cba52280024c11887492b6053bd** with passing post-merge tests/build/real API smoke. Common base updated
to **d2879c6e1e236add391fb6af40480b9940d22555** preserving original draft and
upstream U02B reconciliation. Real U03/F05 dependencies integrated. Selected
metadata now provides an explicit original download with source size/SHA-256
verification, safe failures, duplicate/session/selection protection and URL
cleanup. No schema/backend/scope/dependency changes.
48 frontend pass; 70 backend run (69 pass/1 Windows symlink skip); real F05
and U03 HTTP/SQLite regression and actual browser attachment byte/hash read-back
pass. Contract/types/build/DESIGN pass with existing license warning. Exact
results/limits: PREIMPLEMENTATION_REVIEW.md U04 verification. Checklist in
frontend/README.md. 122 coordination tests pass on the final documentation candidate.
No hosted CI/production auth/formal screen-reader claim. Checkpoint 1A remains
open: I00 requires M1 F06/F07/F09 and explicit shared-task assignee. No next row.

## F06 current handoff — 2026-11-01

**F06 / 1A / M1 / sharmelas-925 / Complete**, automatically selected after
fetching all origin branch refs and fast-forwarding the clean local common base
to **3eab939ada44363de5420d542ead711198ccea0f**, exactly matching origin before
task-state inspection/branch creation. Branch: `feat/f06-intake-audit`.
Real F03 intake and F00/F01/F04/F05 are merged code dependencies; F06 is the
earliest unclaimed M1 row in unfinished Checkpoint 1A. The F06 assignment card
bounds atomic append-only audit/private intake provenance and tests. No F07 API,
processing/provider decision or feature-scope reduction is included.
The upload transaction now appends one safe server-authored audit event and a
linked private versioned source snapshot. Failed metadata/audit/provenance/
commit operations publish no records and remove the new upload file. SQL
guards reject update/delete/replacement of accounting history; startup preserves
legacy originals without inventing historical actors/events. The upload wire
response, full feature scope, schemas and dependency manifests are unchanged.

**17 focused F06 pass; 87 backend run (86 pass, one known Windows symlink skip);
122 coordination and 48 frontend pass.** OpenAPI lint/bundle, generated strict
types, API freshness/typecheck/build, verifier, DESIGN and whitespace pass.
Real localhost F06 audit/source/byte read-back and existing case/create/upload/
download HTTP/client regressions pass; selected provenance rollback failure
passes. Exact commands, synthetic inputs and limits are recorded in the F06
verification section of PREIMPLEMENTATION_REVIEW. No new browser, power-loss
recovery or tamper-resistant database-owner guarantee is claimed.

User-authorized commit/push/merge completed through **PR #12** into
`docs/coordination-foundation` at **1b5166d91e0f3b86b85585d714a917a3efc82d44**,
containing task commit **203c4d5809300ac4b08e82b22856ad4614a12b97**. Ubuntu and
Windows PR CI passed (Run **41297980571**). The local base fast-forwarded cleanly
to that merge; its tree equals the tested task tree. Post-merge real HTTP/SQL
audit/source/original read-back and case/create/upload/download client
regressions pass, with own servers stopped and synthetic data cleaned up.
F06's bounded intake acceptance is **Complete**. Next M1 row is **F07**;
F09 waits for F07 and shared I00 requires an explicit assignee. Checkpoint 1A
stays open. No F07 implementation is authorized or started here.

## F07 current handoff — 2026-11-01

**F07 / 1A / M1 / sharmelas-925 / Complete**, explicitly assigned by the
user with commit/push/merge authorization after verification. Fresh `git fetch
origin` and clean Git status preceded task-state inspection; local common base
and origin matched **441d37de6db68f1f459aa11eb1bf6bd5864f5b77**. Separate branch:
`feat/f07-case-audit-list`. Real F06 intake audit and F00/F01/F03 dependencies
are integrated; no producer double is needed. The F07 assignment card bounds
the existing audit-list route, focused tests and documentation. No private
provenance API, wire/schema/full-scope change or F09 implementation is included.
`listAuditEvents` now uses current case access, a safe-column projection,
oldest-first creation/ID ordering and a single SQLite read snapshot for total
and page. Existing limit/offset validation, shared 400/401/non-leaking 404,
no-store responses and optional reason omission are exercised. Private source
provenance is not queried. No frozen-history selector or new wire field is added.

**15 F07 pass; 102 backend run (101 pass, one known Windows symlink skip);
122 coordination and 48 frontend pass.** Contract lint/bundle/generated strict
types, freshness/typecheck/build, verifier, DESIGN and whitespace pass. Real
localhost audit API/SQL read-back and prior case/upload/download client
integration pass; selected foreign/missing denial test passes. Exact commands
and synthetic fixture/concurrency disclosures are in F07 verification in
PREIMPLEMENTATION_REVIEW.

User-authorized commit/push/merge completed through **PR #13** at
**6687d7cbd820fc4db820d85e4dcd518dd941c99d**, containing final task commit
**e7cd61402e87d2afbed1eafa8ab930e2597dea2b** (including the fractional timestamp
ordering regression). Both Ubuntu and Windows PR CI passed, Run
**41299455397**. The clean local common branch fast-forwarded to that merge;
its tree matches the CI-tested task head. Exact merged-tree real audit API/SQL/
original-byte smoke and prior case/create/upload/download client checks pass,
with own test servers stopped and temporary data removed. F07 is **Complete**.
Next M1 task is **F09**, not started; I00 still needs an explicit shared-task
assignee. Checkpoint 1A stays open.

## F09 current handoff — 2026-11-01

**F09 / 1A / M1 / sharmelas-925 / Complete**, user-assigned with commit/push/
merge authorization after verification. Fresh `git fetch origin` and clean
status preceded task-state inspection; common local/origin HEAD matched
**53bac04ed4b94f10334dc92a5ecead2c11dfecad**. Branch:
`feat/f09-m1-access-regressions`. Real accepted F00/F05/F07 and other M1 intake
producers are integrated. The assignment card bounds all eight current M1
operations, case/resource isolation, error behavior and no denied-write effects.
No product scope, contract, identity provider, other module or shared gate is
changed. The route inventory covers all eight M1 operations, including both
actors' positives, missing/invalid/duplicate/replaced identity, foreign/missing/
revoked cases, mismatched resources, safe error schemas and unchanged records/
originals on denial. Collection create/list correctly use ownership/filtering
checks rather than invented case-ID semantics. The matrix exposed SQLite
overflow on contract-valid huge offsets in case/evidence lists; both now return
proper beyond-end empty pages without adding a contract limit.

**14 F09 pass; 116 backend run (115 pass, one known Windows symlink skip);
122 coordination and 48 frontend pass.** Contract lint/bundle/generated strict
types, freshness/typecheck/build, verifier, DESIGN and whitespace pass. Real
localhost all-eight missing-auth/scoped isolation/no-side-effect SQL/file checks
and prior case/upload/download client integration pass. Exact commands/limits
are in F09 verification in PREIMPLEMENTATION_REVIEW.

User-authorized PR #14 merged into `docs/coordination-foundation` at
**868d697f297748614befdcc6af8a66370b48240b**, containing task commit
**4a69cafae6fb02c770f552c13b14430ac57e5e99**. Both Ubuntu and Windows PR CI
passed, Run **41301012667**. The clean local common branch fast-forwarded to
the exact merge; its tree matches the tested task head. Merged-tree real HTTP
eight-operation auth/scoped isolation/no-side-effect/offset checks and prior
case/upload/download client regressions pass, with own servers stopped and
temporary data removed. **F09 is Complete. Checkpoint 1A stays open.**
Next gate **I00** is shared real API/UI intake verification and requires an
explicit assignee. It is not M1-only and has not been started. Later M1 F08
waits for P04/P14; full M1/product scope is not complete.

## P01 current handoff — 2026-11-01

P01 / 1B / M2 yazh-07 / Complete, feat/p01-network-csv, verified clean shared
base 22673d909b0860663b001269cefa2ac6f302a881. User approved bounded backend
parser/test/README/policy/ledger paths and authorized finish/test/push/merge.
Real G01/F05 prerequisites integrated; completed 0/1A regressions retained.
UTF-8 optional BOM, exact columns, strict quoted CSV, 50 MiB/100000-row limits,
atomic rejection; raw cells/timestamps and physical source rows preserved.
Frozen candidate observations only; no P04 lifecycle/public routes/UTC/identity.
Score 0 means unavailable, not measured confidence or source quality.
14 focused pass; full backend 130 run (129 pass/1 Windows symlink skip),
48 frontend and full real I00 HTTP intake/audit/original smoke pass.
Contract/types/build/DESIGN pass; existing license warning. Exact proof/limits:
PREIMPLEMENTATION_REVIEW P01 verification and backend README synthetic checklist.
122 coordination tests and the final coordination verifier pass. No schema/dependency/full-scope change,
new hosted CI/clean install/processing publication claim. P01 integrated at cab08f1c38745255ca1c0a210636476b84bad43c with passing post-merge focused tests/verifier/I00 smoke; Checkpoint 1B stays open. Next M2 task P02, then P03 after both
parsers are ready. No other row is implemented during this assignment.

## P02 current handoff — 2026-11-01

P02 / 1B / M2 yazh-07 / Complete, feat/p02-gps-csv, verified shared base
4bc8f307a039d7c91bcc687bb64267fbe80fb6b8. User approved scope/GPS policy and
explicit finish/test/push/merge. Actual G01/F05 prerequisites integrated; P01
CSV helper reused unchanged. Frozen source-located GPS device/latitude/longitude
observations retain raw time/precision, finite coordinate ranges and explicit
bad-zone/time errors; missing zone unknown, no UTC or measured-confidence claim.
17 focused tests PASS; 147 backend run (146 PASS/1 Windows symlink SKIP),
48 frontend and full real I00 HTTP audit/intake/original regression PASS.
Contract/types/build/DESIGN PASS, existing license warning. Exact proof/limits
in PREIMPLEMENTATION_REVIEW P02 section; synthetic checklist in backend README.
122 coordination tests and final verifier PASS. No schema/dependency/full-scope or P01 changes,
no new hosted CI/clean install/processing-publication claim. P02 integrated at 389652c358fab4b3b20565d592db520549028b8f with passing focused/verifier/I00 post-merge smoke; Checkpoint 1B remains open. Next M2 P03 normalizes time/
coordinates using both parsers while preserving raw/unknown-zone information.
No other task is implemented or started here.

### P03 live handoff — 2026-11-01

**P03 / 1B / M2 yazh-07 / Complete.** Isolated feat/p03-normalization from
verified common base **ac432e10a6a1c4ff19ae36b49cded514d0e78846**, with actual
merged P01/P02 and completed 0/1A. Approved bounded assignment/policy are in
AGENT_TASKS.md and COMMUNICATION.md. New immutable normalized values preserve
raw cells/timestamps/IDs/locators; exact UTC only for known explicit offsets,
unknown/ambiguous/invalid zones remain unresolved with internal reason. Exact
GPS decimal canonicalization has lossless scientific fallback; no stored output
mutation, API change, identity/event projection or processing publication.
18 focused PASS, full backend 164 PASS/1 existing Windows symlink SKIP, frontend
48 PASS and coordination 122 PASS; contract/types/build/DESIGN and actual I00
loopback HTTP regressions PASS. Integrated at **e9f01f586916f38c480a40ffc8aa3eb72fd146ff**;
18 focused tests/verifier/real I00 post-merge smoke PASS on that exact merge.
Exact verification/doubles/limits in PREIMPLEMENTATION_REVIEW.md. Checkpoint 1B
remains open; entire initial scope/approved additions remain required.
Next eligible M2 task P03B candidate identifier keys/entity records;
P03C also consumes P03, with no later task started here.

### P03B live handoff — 2026-11-01

**P03B / 1B / M2 yazh-07 / Complete.** Isolated feat/p03b-candidate-entities
from verified common base **59de4686f4a59bff25528d386ce458d259d96e6c**, with
real merged P01/P02/P03 and completed 0/1A. User approved exact case-sensitive
device/IP candidate keys, same-case grouping and bounded file scope; assignment
and policy in AGENT_TASKS.md/COMMUNICATION.md. Frozen observation copies and
Entity records retain all source IDs/locators/raw/normalized/time uncertainty;
D-7/D-8 stay distinct, confidence 0 unavailable, no inferred person identity.
15 focused PASS, full backend 179 PASS/1 Windows symlink SKIP, frontend 48 PASS
and coordination 122 PASS; contract/types/build/DESIGN and real I00 HTTP
regressions PASS. Actual original/P01/P02/P03 source chain tested, synthetic run
context disclosed in PREIMPLEMENTATION_REVIEW.md. Integrated at
**c58e7f24e4f7c21fc5120dc7288d02f960b58006**; 15 focused tests/verifier/real I00
HTTP post-merge smoke PASS on that exact commit. Checkpoint 1B remains open. Entire initial
scope/approved additions preserved. Next M2 P03C source-backed event projection;
no next task started. P04/P05/P14 publication/listing/provenance remain separate.

### P03C live handoff — 2026-11-01

**P03C / 1B / M2 yazh-07 / Complete.** Isolated feat/p03c-source-events from
verified shared base **e68969df9f19f8f78320a708bc3cb80a3c05b85d**. Real P01/P02/
P03 prerequisites and actual P03B participant records integrated; 0/1A Complete.
Approved bounded scope/policy in AGENT_TASKS.md/COMMUNICATION.md. One candidate
source report per complete network/GPS row, all source IDs and actual participant
Entity IDs, preserved raw/P03 UTC/time uncertainty, confidence 0 unavailable.
No verified identity/occurrence or publication/listing claim. 15 focused tests
PASS, including real originals/parsers/normalization/entities source chain.
Full backend 194 PASS/1 Windows symlink SKIP, frontend 48 PASS, coordination
122 PASS; contract/types/build/DESIGN and real I00 HTTP regressions PASS.
Exact commands/doubles/limits in PREIMPLEMENTATION_REVIEW.md. Integrated at
**bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca**; 15 focused tests/verifier and real I00
HTTP post-merge smoke PASS on that exact commit. Checkpoint 1B remains open. Entire
initial scope/additions retained. Next M2 P04 processing lifecycle; P05B listing
and P14 persistence remain required later rows. No next task started.

### P04 live handoff — 2026-11-01

**P04 / 1B / M2 yazh-07 / Complete.** Isolated feat/p04-processing-lifecycle
from verified shared base **9bec1653525694c01ef82c6a3cd12f2beea8493c**. Real
F00/F05/P01/P02 prerequisites and P03/P03B/P03C producers integrated; 0/1A Complete.
Approved bounded scope/lifecycle policy in AGENT_TASKS.md/COMMUNICATION.md. Actual
bodyless keyed start, poll/list, frozen input/config, background states and atomic
immutable SQL output publication; safe malformed failure/unsupported 415, replay/
conflict/retry and interrupted-run startup failure. 21 focused PASS; full backend
215 PASS/1 Windows symlink SKIP, frontend 48 PASS, coordination 122 PASS;
contract/types/build/DESIGN and actual processing/I00 HTTP smoke PASS. Exact
commands/doubles/limits in PREIMPLEMENTATION_REVIEW.md. Integrated at
**f851dd11fd8f7e11140317cf44d022a9999044dd**; 21 focused/verifier/real processing/I00
post-merge HTTP smoke PASS on that exact commit. Checkpoint 1B remains open.
Full initial scope/additions unchanged. Next M2 P04B observation
list; P14/P14B/P14C/P05/P05B remain required later rows. No next task started.

### P04B live handoff — 2026-11-01

**P04B / 1B / M2 yazh-07 / Complete.** Isolated feat/p04b-observation-list
from verified shared base **bb3928440ebf39d016e14fb328f045d98fd68bb9**, with real
P04 and underlying F00/F03/F05/P01/P02/P03/P03B/P03C producers; 0/1A Complete.
Approved paths/read policy in AGENT_TASKS.md/COMMUNICATION.md. Actual
listObservations latest-completed per evidence/exact UTC tie selection, historical
run/evidence filters, stable page order/total within a read snapshot, no pending/
failed/foreign or partial/corrupt outputs. 16 focused PASS; full backend 231 PASS/
1 Windows symlink SKIP, frontend 48 PASS; contract/types/build/DESIGN and actual
processing/Observation/I00 HTTP smoke PASS; coordination 122 PASS. Exact
commands/doubles/limits in PREIMPLEMENTATION_REVIEW.md. Integrated at
**c29e517f218c0851a9959cfa389b093242a255ab**; 16 focused/verifier and actual Observation/
I00 post-merge HTTP smoke PASS. Checkpoint 1B remains open. Entire scope/additions
preserved. Next M2 P05 candidate
Entity list, then P05B Event list by dependency/catalog order. No next task started.

### P05 live handoff — 2026-11-01

**P05 / 1B / M2 yazh-07 / Complete.** Isolated feat/p05-entity-list from
verified shared base **abeb516ba879636afb18aaa2a800b2143915e0f7** with actual
P03B/P04B prerequisites and P04/source producer chain; 0/1A Complete. Approved
scope/read policy in AGENT_TASKS.md/COMMUNICATION.md. Actual listEntities keeps
persisted IDs/keys/labels/confidence and validates same-case selected Observation/
Evidence citations; duplicate keys remain distinct records. Live latest-completed
selection, deterministic pagination, one read snapshot and fail-closed invalid
references. 17 focused PASS including real HTTP; full backend 248 PASS/1 Windows
symlink SKIP, frontend 48 PASS, coordination 122 PASS; contract/types/build/DESIGN
and real I00 loopback PASS. Integrated at 04af24f1c44abbc8059b0c006d9079d271ced947;
17 focused/verifier/real I00 post-merge smoke PASS. Checkpoint 1B/M2 remain open.
Full scope/additions retained.
Next M2 P05B source-backed Event list, no next task started.

### P05B live handoff — 2026-11-02

**P05B / 1B / M2 yazh-07 / Complete.** Isolated feat/p05b-event-list from
verified shared base **b5cb37b8d3dbe3d8f23b29a6516162c407cf4335**; actual
P03C/P04B prerequisites and P05 participant validation integrated. User approved
bounded paths and Event read policy in AGENT_TASKS.md/COMMUNICATION.md; authorized
push/merge after tests. 20 focused PASS; backend268 PASS/1 Windows symlink SKIP,
frontend48/coordination122 PASS, contract/types/build/DESIGN/real I00 loopback PASS.
Integrated at c0e25d401651b468d05a60ff5f5e3525e87e6f5f;
20 focused/verifier/real I00 post-merge smoke PASS. Preserve
entire agreed scope/additions. Next M2 P14 private versioned provenance; no next
task started. Checkpoint 1B/M2 remain open.

### P14 live handoff — 2026-11-02

**P14 / 1B / M2 yazh-07 / Complete.** Isolated feat/p14-processing-provenance
from verified shared base **98a28260f2fb2d91dd803c2f1835de264c5d0973** with
real P04 and source-chain prerequisites integrated. User approved bounded file/
private-provenance policy in AGENT_TASKS.md/COMMUNICATION.md and authorized push/
merge after verification. 18 focused PASS; full backend286 PASS/1 Windows symlink
SKIP, frontend48/coordination122 PASS; contract/types/build/DESIGN/real I00
loopback PASS. Integrated at c03361b8171e6506d2c160a85cc1e89e76315fb3;
18 focused/verifier/real I00 post-merge smoke PASS. Full
scope/additions retained; Checkpoint1B/M2 remain open. Next M2 P14B network/GPS
dispatch, no next task started.

### P14B live handoff — 2026-11-02

**P14B / 1B / M2 yazh-07 / Complete.** Isolated feat/p14b-processing-dispatch
from verified base **acf07fec95442c8ae8b9c099dda827a9f68c9a5d** with real
P04/P01/P02 and P14 prerequisites integrated. User approved bounded files and
unchanged C-04 dispatch policy; authorizes push/merge after tests. 14 P14B/21
processing PASS, backend300 PASS/1 Windows symlink SKIP, frontend48/coordination122
PASS; contract/types/build/DESIGN/real I00 loopback PASS. Integrated at
d7a4315377cc1fdae63200780bd7728c583a14dd;14 focused/verifier/real I00
post-merge smoke PASS. Full scope/additions preserved;
Checkpoint1B/M2 remain open. Next M2 P14C, no next task started.

### P14C live handoff — 2026-11-02

**P14C / 1B / M2 yazh-07 / Complete.** Isolated feat/p14c-atomic-processing
from verified shared base **fb52aba41310ae644bb9a12bd4884862367932cc**, with
actual P04/P14B/P14 and source chain integrated. User approved bounded handoff/
existing recovery policy and push/merge after tests. 13 P14C/21 processing PASS;
backend313 PASS/1 Windows symlink SKIP, frontend48/coordination122 PASS; contract/
types/build/DESIGN/real I00 loopback PASS. Integrated at
920331d95fdd359f1e20cfbcfba48fc6e2afb292;13 focused/verifier/real I00
post-merge smoke PASS.
Full scope/additions retained. This is last M2 row
in1B; no later M2 task automatically eligible now. P06(2A) is next catalog work
after earlier1B/I00B and1C/I01 exits (or its own explicit allowed independent-work
handoff); no next task started, Checkpoint1B/M2 remain open.

### P06 independent handoff — 2026-11-02

**P06 / 2A / M2 yazh-07 / Complete (explicit independent row only).** Explicit user-assigned independent work
from verified **9454430a56502dfa8dad791e3d3f420c05424509**, isolated
feat/p06-message-mentions. Real P04 prerequisite and source/provenance/atomic
publication chain integrated. User approved bounded message policy/files and
push/merge after tests; integrated at **1b938d93c09ad82f2ef5af8eac214026d7a820f7** with
24 focused P06/verifier/real I00 post-merge smoke PASS. Full backend337 run:
336 PASS/1 existing Windows symlink SKIP, added upgrade1 PASS; frontend48/
coordination122/contract/types/build/DESIGN PASS. Earlier1B/I00B and1C/I01
exits remain required and open; no phase/checkpoint closure implied. Entire
FEATURE_SCOPE/additions retained. A07/U06B/I02 remain required;2A stays open.
Next M2 catalog P07(3A) requires preceding checkpoint exits (including2A/2B/2C)
for automatic selection or a separately explicit independent handoff with its
format/resource/allowed-file decisions. No later task started.

### P07 independent handoff — 2026-11-02

**P07 / 3A / M2 yazh-07 / In Progress.** User explicitly assigned independent
plain-text document parsing from verified **97564aea28775c96679439dd5ffc22077ea75a64**,
feat/p07-document-text. Real P04 prerequisite integrated; approved format/resource/
file-scope decisions in AGENT_TASKS/COMMUNICATION. Real source/publication/API and
regression proof required before authorized push/merge. Full FEATURE_SCOPE and
approved additions preserved; all earlier checkpoint gates remain open. No later
task started.

## Module assignment and live task state

| Module | Assigned GitHub handle | Accountable boundary | State |
|---|---|---|---|
| M1 Evidence Foundation | sharmelas-925 | Case/access, private originals/hash, metadata and audit/provenance foundations | Backlog |
| M2 Multimodal Processing | yazh-07 | Adapters, normalization/entities/events, immutable processing runs and deeper processing | Backlog |
| M3 Fusion and Adaptive Triage | whale2186 | Derived graph, factors/detectors/snapshots/retriage and retrieval context | Backlog |
| M4 Investigator Application | JebasJ | React UI plus review/override and grounded-generation/verification backend APIs | Backlog |

`whale2186` coordinates shared files/integration alongside M3. G/I work is bounded shared work assigned to an existing contributor, not automatically to the person coordinating and not a fifth module/person. A module is not standalone software and not an agent mega-task. The user explicitly assigned G00/G01/G01B/G01C as recorded below; other shared-task assignees and paths still need their own handoffs. G01C is In Progress; G00/G01/G01B are accepted dependencies in its committed common base. All domain tasks remain Backlog. Earlier session records below retain their historical states; the G01C record supplies the current handoff and remaining exit evidence.

For each assigned task record `task ID | checkpoint | module/person | branch/common spec commit | state | consumed/produced interface | actual commands/results + test doubles | PR/next task`. Serialize ledger edits. States: **Backlog**, **In Progress**, **Complete** (acceptance and real dependency integration verified), **Blocked** (exact needed decision). Current task state defaults to Backlog; no implementation completion is claimed here.

### F05 live record — 2026-10-31

**F05 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.** User-assigned
branch `feat/f05-evidence-download`, clean starting HEAD/common contract base
**c5c9b5a5aefff113db6592996da4af1c780d88df**, matching local
`docs/coordination-foundation`. Real merged F00/F03 dependencies and F01/F02/F04
producers are present. Allowed paths are `backend/evidence.py`,
`backend/tests/test_evidence.py`, `backend/README.md`, `docs/AGENT_TASKS.md`,
`docs/ROADMAP.md`, `docs/PREIMPLEMENTATION_REVIEW.md`; unchanged draft 0.3.0
`downloadEvidence` is the sole HTTP contract.

Authorized case-scoped lookup returns original bytes as an octet-stream
attachment with `Cache-Control: no-store`. Resolved paths must be regular files
strictly inside the configured storage root's authorized case directory;
unsafe/missing paths use the standard non-leaking 404. Tests use real upload,
membership, SQLite and private temporary files with synthetic identities/data.
Actual verification and limits are recorded in PREIMPLEMENTATION_REVIEW's F05
entry. No commit/push/merge or Windows/hosted CI result is claimed.
Checkpoint 1A remains open pending its remaining tasks and I00 exit evidence.
Next M1 row F06 needs its own scoped assignment; M4 U04 follows accepted F05.

### F04 live record — 2026-10-31

**F04 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.** Scoped branch
`feat/f04-evidence-metadata`, clean starting HEAD/common contract base
**e5273a61e444a2fdf46b236e1f4a56700ac52f57** on `docs/coordination-foundation`.
Real F03 and F00/F01/F02/U01/U02/U02B are merged ancestors. User-authorized
paths cover evidence implementation/tests, `backend/README.md` and three
bounded documentation records; no spec/frontend/dependency changes.
Produces `listEvidence` and `getEvidence` against unchanged draft 0.3.0,
with current case membership, case-scoped metadata, deterministic pagination,
omitted absent acquisition time/private paths and existing 400/401/404 errors.
[Assignment](AGENT_TASKS.md#f04-assignment--2026-10-31) and
[verification](PREIMPLEMENTATION_REVIEW.md#f04-verification--2026-10-31)
record actual read-back and checks: 122 coordination, 63 backend (16 evidence)
and 31 frontend tests pass, plus bundle/lint/types/build/DESIGN checks.
Tests use real upload/SQLite/access producers and synthetic authentication;
native Windows/hosted CI remain unverified. No commit/push/merge authorized.
Review/integration is pending; Checkpoint 1A remains open. Next M1 row is F05
under a separate scoped assignment; I00 exit evidence is not claimed.

### U02B live record — 2026-10-31

**U02B / Checkpoint 1A / M4 / JebasJ / In Progress.** Scoped branch
`feat/u02b-case-creation-ui`, clean starting common base
**16975127177f3c609249bd648455d364e0bfc46c** on `docs/coordination-foundation`.
The user assigned bounded frontend and three documentation-record paths;
no commit/push/merge is authorized. Real U02, U01, F00, F01 and F02 are merged
ancestors. Uses unchanged draft 0.3.0 createCase/listCases through U01's typed
request interface; produces a validated creation form, confirmed case selection
and authoritative list refresh. No backend/spec/dependency changes.
[Assignment](AGENT_TASKS.md#u02b-assignment--2026-10-31) and
[verification](PREIMPLEMENTATION_REVIEW.md#u02b-verification--2026-10-31)
record commands, actual results and doubles. Review/integration is pending;
Checkpoint 1A remains open. Next M4 row is U03 after this scoped review;
no other task is started.

### U02 live record — 2026-10-31

**U02 / Checkpoint 1A / M4 / JebasJ / Complete**, user-approved integration
into `docs/coordination-foundation` at merge **9f2cc8ac64426ef2b0bb9d917fd7afdb777b606f**.
Post-merge real HTTP/SQLite smoke and coordination verification pass. Branch `feat/u02-case-list-ui`, clean published
common base **909009d21198fd751db49863f581b032875fa5e0**. Live origin ref matched;
U01 42d0312 and F02 c8077f5 are merged ancestors with real F00/F01/G01B.
Their older In Progress session records below are historical; no other task's
completion status is rewritten by this handoff. User approved the bounded
[assignment](AGENT_TASKS.md#u02-assignment--2026-10-31) and commit/push of this
one task, then explicitly authorized this merge; no subsequent task.

The UI uses unchanged listCases/getCase through the existing typed client,
20-item pages and authoritative totals, selected case details, honest
loading/empty/error states, memory-only session entry/logout, stale-response
rejection and accessible detail focus. No backend/spec/dependency/scope change.
**25 frontend / 47 backend / 122 coordination tests pass**, no skips. Explicit
real HTTP/FastAPI/SQLite integration passes two synthetic actors, 21+1 cases,
pagination/details/isolation/empty/400/401/404 cases. Browser smoke covers
list/detail/pagination, empty actor, invalid token, reload/logout and focus.
Contract lint/bundle, generated strict types, freshness/typecheck/build,
verifier and DESIGN pass; existing missing-license warning remains.
[Verification and limits](PREIMPLEMENTATION_REVIEW.md#u02-verification--2026-10-31)
and the exact test checklist in `frontend/README.md`.
Checkpoint 1A remains open. Next M4 row **U02B** can use the newly verified
shared base on a fresh assignment; no second task is started. New hosted CI
is pending separately; the documented local test limitations remain.

### F02 live record — 2026-10-25

**F02 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.** Scoped branch
`feat/f02-case-listing`, clean starting common contract/base
**a10a81ecf4820b2330bd04edfba7f15d2764c745**, includes merged F00/F01.
The [assignment](AGENT_TASKS.md#f02-assignment--2026-10-25) records bounded paths
and real dependencies. GET `listCases` uses current SQLite membership and a
shared read snapshot for total/page, ordered by created_at descending then ID
ascending. Optional absent descriptions are omitted. Existing flat validation
and authentication contracts are preserved.

**14 focused case / 47 backend / 122 coordination / 19 frontend tests pass**,
no skips. Lint/bundle, verifier, frontend generated-type freshness/typecheck/build,
DESIGN and whitespace pass; existing OpenAPI missing-license warning remains.
[Verification](PREIMPLEMENTATION_REVIEW.md#f02-verification--2026-10-25) records
Linux execution on 2026-10-27 with real FastAPI/SQLite and synthetic identities.
No browser/Windows/hosted CI or Checkpoint 1A closure is claimed. Changes await
review; nothing staged, committed or pushed. Next M1 row is F03 after review
and its own policy/dependency check.

### F01 live record — 2026-10-25

**F01 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.** Scoped branch
`feat/f01-case-persistence` started clean at exact common contract/base
**86f14eedc575032d636a77233b19f13bf665c077**, including real merged F00
**94aa2a8** and its G01 SQLite/authentication foundations. No fresh fetch claimed.
The [assignment](AGENT_TASKS.md#f01-assignment--2026-10-25) bounds paths,
acceptance, dependencies and the F01-E01 error-envelope decision.

Real `createCase`/`getCase` use SQLite cases/membership, atomic creation, stable
UUID4, UTC creation time, strict body validation and real F00 actor/case guards.
Default membership reads use SQLiteCaseAccess on every request; rejected tokens
remain the default identity configuration. Foreign/missing cases share one
membership query and identical status/body/headers. Timing equality is not
certified. Synthetic identities exercise real API/storage; no F01 producer double.

**11 focused F01 / 44 combined backend / 122 coordination / 19 frontend tests
pass**, with no skips. OpenAPI lint/bundle, generated strict types, frontend API
freshness/typecheck/build, verifier, DESIGN and whitespace checks pass. One
pre-existing OpenAPI missing-license warning remains. [Exact evidence and limits](PREIMPLEMENTATION_REVIEW.md#f01-verification--2026-10-25)
record Linux execution on 2026-10-27, not Windows/hosted CI/browser acceptance.
Current flat ApiError behavior is verified; the requested nested envelope conflicts
with the unchanged contract and awaits F01-E01 resolution. No schema, frontend,
package, full-scope, commit, push or merge change. F01 remains **In Progress**;
Checkpoint 1A remains open. Next M1 row is F02 after accepted F01 handoff.

### F00 live record — 2026-10-25

**F00 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.** Automatically selected
as the first unclaimed, dependency-ready M1 row in the earliest unfinished
checkpoint, on `feat/f00-auth-case-guard` from freshly fetched, clean coordination
base **f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029**. Verified G00/G01 ancestry and
C-03's later declared resolution; older open-gate entries are historical.
The [assignment](AGENT_TASKS.md#f00-assignment--2026-10-25) bounds auth/access
implementation and tests. Reusable guards reject malformed/missing/invalid bearer
identity, validate case UUIDs with the shared 400 mapping and check current
membership before handlers. Foreign and missing cases have identical 404 bodies
and headers. Defaults reject all credentials and case access; explicit local
synthetic configuration contains no built-in token. F01 persistence is absent;
test-only routes/SQLite memberships are disclosed producer doubles, not F01.

**19 focused F00 / 33 combined backend / 122 coordination / 19 frontend tests
pass**, no skips. Focused foreign/missing failure case, lint/bundle, generated
strict types, API freshness/typecheck/build, verifier, DESIGN and whitespace
checks pass. Backend/frontend localhost smoke returns expected 404/200 and stops
both servers. [Exact evidence and limits](PREIMPLEMENTATION_REVIEW.md#f00-verification--2026-10-25)
record local Windows results, not new hosted CI or browser acceptance. No public
route, package/spec/full-scope change, staging, commit, push or merge. F00 stays
**In Progress**, awaiting review and real producer/client integration; Checkpoint
1A stays Backlog. Next M1 row is F01 after accepted F00 dependency handoff.
The user subsequently authorized this scoped branch's commit, push and merge
into `docs/coordination-foundation` on 2026-10-25; that publication does not
establish real F01/U01 integration or mark F00 Complete.

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

### U03 live record — 2026-10-31

**U03 / Checkpoint 1A / M4 / JebasJ / In Progress.** Branch
`feat/u03-evidence-upload-ui`, exact common contract/base
**69f2e8269b6e6d639889941926bc604a415e3f05** on local
`docs/coordination-foundation`; clean starting tree. Real U01/F03/F04 and
F00/F01/F02/U02/U02B are integrated ancestors; draft 0.3.0 is unchanged.
The U03 assignment in `AGENT_TASKS.md` records the explicit bounded path handoff.

Selected cases expose one-file multipart intake, paginated evidence listing,
and authorized metadata inspection with ID/SHA-256/byte size. Required-file and
blank-label checks precede HTTP; busy controls prevent repeated submission;
server messages render as accessible plain-text alerts. Confirmed upload
metadata survives refresh failure. Case/session disposal rejects late data.
Acquisition input explicitly uses UTC; omitted acquisition time stays absent.

39 frontend, 63 backend and 122 coordination tests pass. Real HTTP/FastAPI/
SQLite/private-file integration verifies 201 and exact byte hash/size/list/detail,
blank-label/unsupported-kind 400, actual oversize 413 and actor/case isolation
404; existing U02/U02B integration also passes. Contract/API types/build/DESIGN
and diff checks pass; existing OpenAPI license warning remains. Exact commands,
test doubles and limits are in U03 verification in `PREIMPLEMENTATION_REVIEW.md`.
No browser/native Windows/hosted CI, commit/push/merge or checkpoint completion
is claimed. **Checkpoint 1A stays open** pending its remaining rows and I00.
Next M4 row U04 requires real F05 and a separate assignment.

### F03 live record — 2026-10-31

**F03 / Checkpoint 1A / M1 / sharmelas-925 / In Progress.**
Branch `feat/f03-evidence-upload`, exact common contract/base `1b7d92826a5af23431f3936c1c6152f3ad634065`
with real merged F00/F01/F02/U01/U02/U02B. Bounded paths and intake policy are
recorded in [assignment](AGENT_TASKS.md#f03-assignment--2026-10-31).
Produces uploadEvidence with private UUID-only original storage, streamed SHA-256
and size, SQLite metadata and cleanup on failed writes/publication.
See [verification](PREIMPLEMENTATION_REVIEW.md#f03-verification--2026-10-31).
No commit/push/merge authorized. Checkpoint 1A remains open; F04 is next after
review. F05 download, F06 audit and I00 integration are separate rows.

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
