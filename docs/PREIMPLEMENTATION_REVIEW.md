# EVORA phase-plan verification and implementation readiness

## State and scope

**Implementation has not started.** The repository contains planning/contract/fixture/validation artifacts, not a FastAPI backend, React application, live Neo4j projection, executed AI/scoring or research benchmarks. A standalone visual prototype outside this Git tree is not product implementation.

The published baseline is `f0099ca908cc119ad744f417399deb0c426b929e` on `docs/coordination-foundation`; main is `5c92da0f9dc49ee422d94fed0c550b56dd5fd0ba` with only README. This phase revision is local until explicitly authorized publication. Authorization to commit does not authorize a push or main merge; the plan itself authorizes neither. Read back remote/CI for the exact later commit before claiming publication.

## What the phase revision changes

- [ROADMAP.md](ROADMAP.md) is the single phase authority: **Phase 0–6**, with smaller checkpoints and exhaustive task membership, truthful Backlog state, targeted decisions and promotion/regression rules.
- [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) mirrors checkpoint membership and preserves all existing tasks. Three bounded integration gates are added: I00 authorized intake, I00B first immutable processing, I03B full modalities through the existing investigation workflow.
- [INTEGRATION.md](INTEGRATION.md) uses the same checkpoint order and defines real producer/API/UI/source/failure evidence. Full modality handoff precedes complete detector assembly under the existing dependencies; new-upload feedback is distinct from detector feedback and deeper processing.
- Early prerequisite gaps are made explicit: F08 needs P14; A05 needs P14/P14C; I01 needs early audit/provenance/access/explanation and source-navigation checks; deterministic U10 needs safe F06-backed retrieval/Q&A audit. P06 registers its real message adapter, not merely parser output. I09 includes the full-modality checkpoint.
- Initial intake, processing and analysis are separate checkpoints, not one oversized agent assignment. Explanations, original hashes, private provenance, safe rendering, access controls and labeled counterexamples start with the features they protect.
- Candidate entity/event list APIs stay processing views. Full-context retrieval and analysis-linked uncertainty resolve frozen snapshot source records rather than mixing live processing with a historical analysis. No new selector or HTTP operation is invented.
- README, AGENTS.md, assignment cards, feature/source traceability and PR/CI instructions point to the same plan. Four people retain module boundaries; one coordinates shared work alongside their module. No personnel names/titles, fifth person or four-signoff ceremony is introduced.

## Preservation checks actually executed

- All **118 baseline tasks** remain; the catalog now has **121 unique tasks**, including the three integration gates. Every task is assigned exactly once across **18 checkpoints** and has no dependency pointing to a later checkpoint.
- All **37 feature-map capability rows** retain their original names/order. All **40 proposal sections** and **40 source mappings** remain. The preserved proposal was compared with the provided original, allowing trailing-whitespace removal only.
- `docs/PROPOSAL.md`, `specs/openapi.yaml`, `DESIGN.md`, `docs/CONTRACTS.md`, the wire-example test file and all three original CSV fixtures are byte-for-byte unchanged from the baseline. Every existing task's contract cell is unchanged.
- OpenAPI remains **0.2.0 with 25 operations**. Architecture/topology, immutable evidence/history, snapshot/idempotency/pagination, privacy and human-judgment boundaries remain intact. Full timeline reconstruction remains future; initial temporal reasoning is retained.

## Local validation actually executed

Baseline: Redocly lint/bundle and the original **43 tests** passed before edits.

The first candidate passed **61 tests**, but independent review still found a missing causal publication dependency and fail-open Markdown/mirror checks. Those results were not treated as final approval. U12A/U12B/U12C/U12D/U12E/U13B now explicitly require A17 and complete real-API acceptance in 4B, after coherent publication; 4A proves analytical producer components only. Earlier fixture UI work remains possible without a false integration claim.

The corrected candidate passed fresh Redocly 2.57.0 lint/bundle, openapi-typescript 7.10.1 generation, TypeScript 5.9.3 declaration compilation, Ruff 0.12.12, DESIGN 0.4.0 lint, coordination checks, Git diff whitespace and **102 unit/CLI-negative/synthetic-schema tests** on the workflow's **Python 3.12 / Node 22** runtime families. New failure checks were exercised red before their verifier fixes; mutations operate only on temporary copies. An added-line/new-file static pattern scan found no secrets or unsafe execution patterns; this is not a complete security audit.

Canonical table parsing now validates named sections, exact headers/separators/widths, IDs/states and duplicates rather than silently skipping malformed rows. Required capability identities are unique and exhaustive; task ranges are rejected. Roadmap exit-gate IDs are structured and unique, and runbook sets must match exactly. The verifier also checks exact task membership, dependency order/DAG, early immutable/audit handoffs, analytical UI publication dependencies, full-scope/final-report closure and derived feature coverage, alongside existing contract/source/fixture/link/whitespace checks. Parent preservation checks confirmed no original dependency removal or changed scope/contract cells; four acceptance rows add dispatch/grounding/audit/snapshot clarification. Markdown-it rendered all six catalog tables, the feature table and roadmap/runbook tables with matching widths.

Initial checks used Python 3.14.7/Node 26.7.0; corrected target-runtime execution used **Python 3.12.14/Node 22.23.3**. Clean-copy verification used a temporary Git index and byte-matched source checkout without staging in the user's actual index. Post-correction independent phase and code reviews returned **no blockers, security concerns or logic errors**. Their remaining suggestions were applied: F03/F05 integration now points to the earlier I00 intake gate, the feature map distinguishes processing-source U13C from pinned analytical views, and a positive CLI test preserves mirrored canonical gate changes. The final local checks were repeated after these small clarifications/test additions; repeat verification after any subsequent change before publication. No remote GitHub CI or Windows application/skeleton run is claimed. Validation runtimes/dependencies were installed in isolated scratch directories; disposable bundles/client/log outputs remain outside the repository.

Non-blocking existing warning: Redocly reports missing `info.license`; no project license is invented. DESIGN lint reports zero errors/warnings, but is not rendered browser/interaction/accessibility testing.

## What remains open

- Module owners and integration coordination are now recorded by GitHub handle in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). Allowed paths, bounded shared G/I assignees and the exact shared reviewed contract/base commit still require G00/task handoff; ownership alone does not complete G00. Do not start from a README-only main or unpublished local instructions.
- C-03 auth/token/membership before protected tasks; C-04 first CSV policy before intake/processing and later format/model/resource policies before their adapters; C-05 exact scoring/goldens before scores; approved local grounding/privacy before deterministic Q&A; C-06/G03 before full generation.
- G01/G01B/G01D must establish actual tested package/database versions and commands; G01C/I03/I09B must prove their respective Windows/CI scopes. No installed product stack is implied here.
- All product tasks and checkpoints remain Backlog. Real producers, browser behavior, model/provider execution, accuracy, latency/security/recovery and research results must be exercised during their implementation phases. A valid spec or this plan cannot certify them.

## Handoff rule

Use the exact checkpoint ledger, select one dependency-ready row, fill the [agent assignment card](AGENT_TASKS.md), implement/test with disclosed fixtures if needed and integrate with real producers before completion. Preserve earlier capabilities and rerun all completed checkpoint regressions before an authorized main promotion, then verify the merged commit/CI/smoke results. Independent later work may proceed when its own interfaces/choices permit; do not block all modules for a downstream provider choice or call a first tracer the full product.
