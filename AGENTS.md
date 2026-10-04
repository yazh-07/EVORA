# EVORA agent instructions

This repository is the shared source of truth for the four-person EVORA team. EVORA is an investigative support research prototype, not a system for determining guilt. Do not portray an unverified finding as fact.

## Before editing

1. Read `docs/ARCHITECTURE.md`, `docs/FEATURE_SCOPE.md`, `docs/TASK_BREAKDOWN.md`, `docs/ROADMAP.md`, `docs/CONTRACTS.md`, `docs/CONTRACT_REVIEW.md`, `docs/COMMUNICATION.md`, `docs/INTEGRATION.md`, and `specs/openapi.yaml`.
2. Check `git status`, your branch, and the current repository content. Do not assume features or frameworks exist because they appear in the proposal.
3. Take exactly one task ID from `docs/TASK_BREAKDOWN.md` with an assigned person/module, allowed paths, dependencies and acceptance check. Work in a fresh task branch/session, not `main`; a whole module or milestone is **never** one agent assignment. Do not modify another task's files without coordination.
4. If a contract, technology, supported format, or module assignment is marked **TBD**, do not invent a permanent choice. Record the exact issue in `docs/COMMUNICATION.md` or the PR, and describe compatibility impact to affected module contributors. The person coordinating integration keeps the resulting shared spec/version synchronized; they need not design every technical detail. A note is not authorization to reimplement another module or change the accepted contract silently.

## Shared invariants

- Use the official name **EVORA**. Old proposal text may use another name; do not reintroduce it.
- Every derived observation, relationship, finding, triage reason, generated answer and investigator decision must retain case scope and supporting Evidence IDs. Preserve original input bytes and original timestamp/source values alongside normalized data.
- Keep extraction confidence, source quality, and conclusion reliability distinct. A linked record is an investigative lead, not proof. Avoid claims of forensic certification or court admissibility.
- Do not invent endpoints, field names, enum values or persistence types. `specs/openapi.yaml` is a **local draft** until one common version is published; after that it is the single authority for HTTP paths and wire models. Coordinate changes with affected module contributors and update consumers and contract tests.
- Handle uploaded evidence as sensitive: validate type/size, isolate cases, avoid logging file contents, and never send real case evidence to external AI services without an approved policy. Do not commit real evidence, credentials, model keys, or local secrets.
- Use synthetic/publicly permitted fixtures for tests. No fake test or benchmark output.

## Working agreement

- One person works on each of the four modules. If a bounded task needs help, coordinate without creating competing implementations. Do not have two agents write the same branch at once.
- Each task: state inputs/outputs and acceptance criteria; implement and test; inspect the diff; document actual commands/results and any contract impact; update `docs/ROADMAP.md` in the PR. The person coordinating integration serializes edits to shared documents to prevent conflicts.
- Push only to a reviewed feature branch when authorized. Open a PR; never merge or push directly to `main` autonomously. No `develop` branch is required unless the team chooses a staging branch.
- When a decision is blocked, stop and report the precise question rather than silently filling gaps.

## Current status

The repository initially contained only `README.md`. These files establish coordination, not a working implementation. FastAPI/SQLite/React is selected; the full proposed initial feature scope is the build goal, with a three-CSV **first tracer only**. The API remains an unpublished draft. Technical settings needed by each initial ticket must be documented and one common base published. Windows setup, scoring policy and module assignments remain open in `docs/ROADMAP.md`; none is a request for new feature-scope approval.
