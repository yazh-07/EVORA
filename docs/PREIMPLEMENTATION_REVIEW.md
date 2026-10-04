# EVORA pre-implementation review

## Verdict and actual implementation state

**A full-scope coordination plan, not an implemented EVORA system.** Four contributors work on M1–M4; one of those same four coordinates integration alongside their module. Names and module assignments must be recorded by the team. Independent bounded module work is expected, using the same contract commit and schema-derived fixtures.

The branch contains the source proposal, proposal-to-task traceability, architecture, task catalog, a draft OpenAPI 0.2.0 contract, UI design rules, synthetic fixtures and executable planning checks. It does **not** contain the FastAPI backend, React frontend, Neo4j integration, executed scoring, model inference or a running end-to-end application. The CSV tracer is the first integration slice; it is not an MVP replacing the agreed full proposal scope.

The earlier draft was already published at `88d2cc43b293cc40f15eff7137c40f09883a283e` on `docs/coordination-foundation`. This rewrite is to be shared on the same branch. Publication and GitHub CI must be verified from the exact remote commit after push; local tests alone do not prove either. Nothing in this report authorizes merging into `main`.

## Gaps addressed by this rewrite

- Explicit processing and analysis command UI tickets, not merely status polling and result views; returned run IDs, idempotency and terminal failure states are part of acceptance.
- Analysis assembly depends on scoring and detectors and publishes graph/findings/available triage only after the same-case/run Neo4j projection verifies. Partial or failed outputs cannot look like completed analysis.
- An immutable acceptance-time input snapshot, deterministic manifest hashing, server-derived triggers, replay semantics and completed-run selectors prevent moving inputs or mixed-version graph/findings/triage views.
- Named triage factors have calculation/wiring ownership; conflicts, gaps, anomalies and deeper processing feed the triage-analysis-retriage workflow. A rerun without changed inputs must not invent a ranking change.
- Full RAG retrieval plus model generation and verification is distinct from the deterministic first-slice Q&A fixture. Model/prompt/retrieval provenance and sensitive audit retention are explicit work, not invented optional output fields.
- Later full-scope integration/evaluation/reproducibility gates include expansion adapters, algorithms and views. Completion of the CSV tracer does not mark the full project complete.
- React/TypeScript, FastAPI, Neo4j as a derived graph projection, canonical metadata/audit storage and private immutable originals have distinct boundaries. Neo4j does not automatically implement scoring or uncertainty.
- `DESIGN.md` constrains the real investigator workspace: evidence table and inspector first, reusable tokens/components, truth-backed states, source links and accessibility; no gradients, blinking, fictional status or fabricated metrics.
- The full 40-section original proposal is preserved in [`PROPOSAL.md`](PROPOSAL.md) and mapped in [`PROPOSAL_TRACEABILITY.md`](PROPOSAL_TRACEABILITY.md). Complete timeline reconstruction remains future work.

## Reproducible checks and their limits

The exact commands live in [`AGENTS.md`](../AGENTS.md) and CI in [`.github/workflows/contract.yml`](../.github/workflows/contract.yml):

1. Redocly 2.57.0 lint/bundle; openapi-typescript 7.10.1 generation and TypeScript 5.9.3 declaration checking.
2. `scripts/verify_coordination.py`: local schema references, shared errors, critical snapshot/provenance invariants, unique tasks, dependency DAG, task contract names, command UI ownership, scoring assembly and full-scope dependency closure, Markdown links/whitespace, proposal-section coverage and synthetic CSV semantics.
3. Unit/negative tests for the verifier and JSON Schema validation of explicitly synthetic wire examples using jsonschema 4.25.1. These examples are **not** responses returned by a running backend.
4. `@google/design.md` 0.4.0 token/reference/contrast lint. This is **not** rendered browser, interaction or accessibility testing.
5. Git diff whitespace and staged-secret/local-evidence inspection before publication. A basic pattern scan is **not** a complete security audit.

The rewrite's local checks passed after review corrections: **25 operations, 118 unique tasks, 40 preserved proposal sections and 40 traceability mappings; 43 verifier/CLI-negative/synthetic-schema tests passed**. Redocly lint/bundle, generated TypeScript compilation, Ruff script lint, DESIGN lint and document/fixture/DAG checks passed. The copied proposal was compared programmatically against the provided original, permitting trailing-whitespace removal only; wording was unchanged. These outcomes validate the planning artifacts, not a running backend, browser, Windows installation or research benchmark. Independent review identified and corrected unrelated final-provider dependencies and unstable pinned-triage membership/override paging; publication and CI still require read-back of the exact pushed commit.

OpenAPI retains 25 operations. Redocly reports the non-blocking missing `info.license` warning; no project license is invented. Tool outputs, not this prose, determine any later task/test counts and success. CI must exercise the committed tree; it does not validate future application behavior.

The synthetic network fixture contains D-7/D-9 and GPS contains D-8, with no shared device ID. The later message co-mentions D-7/D-8 and may support a **candidate** connection. Identity, guilt, calibrated confidence and numerical re-ranking require actual policy and execution; they cannot be inferred from the fixture alone.

## Remaining gates before affected implementation tickets

Use [`COMMUNICATION.md`](COMMUNICATION.md) for precise decision status and affected tickets. Authentication/case access, format limits/failure policies, scoring/missing-factor policy, model/provider/privacy and any unresolved graph/runtime or detector decisions must be settled by the contributors implementing those boundaries. The coordinator keeps the shared version aligned, not personally designs every API or algorithm.

Start setup and unblocked bounded tickets; do not block all four modules for a choice that affects only a later task. Shared wire changes must update OpenAPI, generated types, producers, consumers and tests together. Do not silently create alternative routes, use fake observations/confidence or present an unresolved policy as implemented behavior.

## Handoff and completion rules

1. Record one contributor for each module and the exact shared commit used by each task branch.
2. Resolve only prerequisite choices for the next bounded ticket; use [`TASK_BREAKDOWN.md`](TASK_BREAKDOWN.md), not a whole-module mega-prompt.
3. Use declared schema-conforming fixtures while a producer is unavailable; replace them with real integration and case-isolation tests before closing integration gates.
4. Verify the initial tracer, then the full-scope modality/analysis/RAG/UI/evaluation gates separately. Windows installation, browser behavior, accuracy, latency and research benchmarks require real runs later.
5. Keep original bytes and completed output histories immutable. Human review and overrides remain append-only; priorities are attention order, not conclusions about guilt.
