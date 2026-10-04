# EVORA

EVORA is a proposed **AI-assisted multimodal forensic evidence fusion and investigation support** research prototype. It is not a certified forensic tool and does not determine guilt. The repository currently contains **coordination artifacts only**, not a running application.

## Start here

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — four module boundaries and workflow.
- [`docs/FEATURE_SCOPE.md`](docs/FEATURE_SCOPE.md) — whole-project proposed capability inventory, first tracer versus later work, and evaluation.
- [`specs/openapi.yaml`](specs/openapi.yaml) — **local draft** case-scoped HTTP routes and shared wire models; publish one shared version as the coding base.
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — proposed stack, API behavior, synthetic tracer and cross-module test gates.
- [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — technical choices to resolve when their implementation tickets need them.
- [`docs/CONTRACT_REVIEW.md`](docs/CONTRACT_REVIEW.md) — producer/consumer map and technical recommendations, not a separate approval gate.
- [`docs/PREIMPLEMENTATION_REVIEW.md`](docs/PREIMPLEMENTATION_REVIEW.md) — checked readiness, open choices and what remains unverified before coding.
- [`docs/COMMUNICATION.md`](docs/COMMUNICATION.md) — open cross-module questions and bounded correction handoffs; the versioned spec remains the API authority.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — module assignment/task ledger and first reviewable task sequence.
- [`docs/TASK_BREAKDOWN.md`](docs/TASK_BREAKDOWN.md) — small, dependency-ordered tickets for **every module**, plus integration and evaluation. A module is not one agent prompt.
- [`docs/AGENT_TASKS.md`](docs/AGENT_TASKS.md) and [`AGENTS.md`](AGENTS.md) — per-task prompt templates and rules for coding agents.
- [`fixtures/synthetic-case/`](fixtures/synthetic-case/) — synthetic CSV inputs; never substitute real case evidence for committed fixtures.

## Before implementation

FastAPI/SQLite/React is the selected stack. **The whole proposed initial feature scope is the build goal**, delivered as small module tickets; the three synthetic CSVs are only the first integrated test, not a reduced product. Four people each work on one of M1–M4; one of those people coordinates integration alongside their module. Put one shared contract on a common Git base before **individual ticket** branches use it; record that commit so agents cannot drift. Document later format/model choices when those tickets are reached. No implementation branches or runnable software are supplied by these documents.

## Contract lint (requires Node.js)

```sh
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
```

This validates the API description, **not** implementation behavior. Windows teammates can run the same command from PowerShell after installing Node.js. Do not claim end-to-end tests pass until there is a running app and the `docs/INTEGRATION.md` tracer has been exercised.
