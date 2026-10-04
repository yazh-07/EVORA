# EVORA task prompts — templates, not permission to implement yet

**Synchronization:** Four people each work on one module; one of them coordinates integration. Affected module contributors record the spec, auth behavior and format choices needed by a ticket, then give agents the same published contract commit. These files are currently a **local draft**, not a working app. Future formats need not be decided before the first ticket. Fill placeholders from the shared commit and start a fresh agent session for each task, not one enormous module-wide request.

## Common prefix for every agent

> You are working on EVORA in `[REPO_PATH]` on `[BRANCH]` at `[SHARED_CONTRACT_COMMIT]`. Read `AGENTS.md`, `docs/TASK_BREAKDOWN.md`, `docs/ARCHITECTURE.md`, `docs/FEATURE_SCOPE.md`, `docs/ROADMAP.md`, `docs/CONTRACTS.md`, `docs/CONTRACT_REVIEW.md`, `docs/COMMUNICATION.md`, `docs/INTEGRATION.md`, and the versioned `specs/openapi.yaml` before editing. `docs/CONTRACT_REVIEW.md` contains recommendations only; use the behavior recorded in the common spec/policy. Inspect Git status and relevant code. Implement **only** `[TASK_ID AND ACCEPTANCE CHECKS]` within `[ASSIGNED FILES/COMPONENT]`. All routes and schemas must strictly match the common OpenAPI spec; never invent alternate endpoint names (e.g. `/get/usernames` versus `/api/v1/users`). Use only providers recorded in the shared policy; if a needed choice is TBD, record its exact impact in `docs/COMMUNICATION.md` or the PR and raise it with affected module contributors instead of guessing. A note alone does not alter the shared spec. Preserve source Evidence IDs/provenance, case isolation and uncertainty where this ticket produces derived data. Write failing behavior tests before implementation, then run relevant build/test commands and report actual output. Use synthetic fixtures or spec-derived test doubles if another module is incomplete; never hard-code fabricated runtime results. Update this task's handoff (changed files, interfaces, tests, limitations) in its PR; coordinate any `docs/ROADMAP.md` edits with the person coordinating integration. Inspect the diff for secrets and unrelated changes. Do not push unless explicitly authorized; never merge into `main`.

## M1 — Evidence Foundation

> Implement **one assigned Fxx ticket** against its reviewed schema and API. Apply the relevant invariant only: case authorization for F00/F01; immutable original bytes/hash for F03/F05; or append-only audit/provenance for F06–F08C. Add the failure tests specified by that row. Do not implement other Fxx tickets to make yours appear complete; use a test double for an unfinished producer and disclose it.

## M2 — Multimodal Processing

> Implement **one assigned Pxx ticket** according to its reviewed Observation/Entity/Event interface. For a parser ticket, use its documented synthetic input and retain original values and source locations; for lifecycle/list tickets, test state and case scoping; for normalization/model tickets, test uncertainty and provenance. Do not claim identity from generic person/vehicle detection, or quietly implement another format.

## M3 — Evidence Fusion and Adaptive Triage

> Implement **one assigned Axx ticket** against its reviewed observation/finding/triage contract. Support that ticket's links or factors with Evidence IDs and uncertainty. Do not implement scoring, reranking, detectors and explanation together: factor tickets test one factor; A04 tests aggregation; A07 specifically tests the later-evidence rank change.

## M4 — Investigator Application

> Implement **one assigned Uxx ticket** against the reviewed API: a single view, command or endpoint as named by its row. Display citations when this view shows findings; audit review/override actions only in their own tickets; reject unsupported answers in U10/U11. Test relevant loading/empty/error paths. Do not hard-code fabricated results or quietly duplicate backend scoring.

## Reviewer checklist

- Does every result refer to valid same-case Evidence IDs and original source records?
- Do API/schema names match the reviewed spec exactly?
- Can another module consume this output without guessing?
- Do tests actually run, include failure cases, and check changed ranks/grounding when relevant?
- Are private evidence, generated outputs, model prompts and secrets handled according to policy?
- Are decisions and incomplete features reported honestly?

## Assignment cards — one ticket per session, never an entire module

`docs/TASK_BREAKDOWN.md` is the task catalog for **all four modules and integration**. The old F1/P1/A1/U1 *milestone bundles* are not valid single-agent assignments. First publish the common base and the appropriate shared skeleton task; then copy the common prefix above, add **one catalog row** and fill in the assigned module/person, shared contract commit, allowed directories/files, fixture and exact test command. Coordinate skeletons, shared config, migrations and roadmap edits across modules; agents must not each scaffold a project or rewrite the same spec.

Example of a properly bounded assignment (only after its dependencies are implemented/tested or supplied as declared test doubles):

> **Task F03 — upload and hash one evidence file.** Branch `feat/f03-evidence-upload` from `[SHARED_CONTRACT_COMMIT]`. Module/person: `M1 / [ASSIGNED PERSON]`. Edit only `[M1 EVIDENCE PATHS + FOCUSED TEST PATHS]`. Implement `uploadEvidence` and the `Evidence` response exactly as in `specs/openapi.yaml`, using the completed F00/F01 foundation. Use `fixtures/synthetic-case/network.csv`: upload it, download through the existing F05 route *only after that task lands*, and verify SHA-256/size from original bytes. Before F05 exists, assert stored bytes/hash through the Foundation storage test boundary; do not implement download in this ticket. Reject unsafe filename/invalid or oversized content. Write failing tests first, run them and the relevant suite, report output, and stop if auth/upload limits are still undecided. Do not edit M2/M3/M4, shared contract, migrations or roadmap without cross-module coordination.

**Other first tickets:** F00 (case-access guard) → F01 (case record) → F03 (upload); P01 (network parser) and P02 (GPS parser) are separate tasks; M3 starts with G02 policy and A01 graph nodes, **not** a graph+score+re-triage mega-prompt; M4 starts with G01B frontend skeleton and U01 client config, **not** the full dashboard. Find each dependency and acceptance test in `docs/TASK_BREAKDOWN.md`. A downstream team can work with accepted-schema fixtures before a producer lands, but the PR cannot be called integrated until it uses the real merged producer.
