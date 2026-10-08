# EVORA

## Implementation starts here

**Implementation has not begun.** The full proposal will be delivered in phases, with four people each working on one module. Start with [the phased roadmap](docs/ROADMAP.md): it owns exact checkpoint membership and completion gates. The [task catalog](docs/TASK_BREAKDOWN.md) supplies bounded assignments; [agent cards](docs/AGENT_TASKS.md) explain how to execute one safely.

Phase outcomes: **0 shared skeleton → 1 first network/GPS workflow → 2 adaptive/human-control tracer → 3 all modalities → 4 complete analytical feedback → 5 verified full RAG → 6 evaluation/reproducibility/report**. Checkpoints divide these outcomes into smaller verifiable deliveries; do not assign a whole phase/module to an agent.

In Phase 4, 4A tests remaining analytical producers; 4B assembles/publishes them with A17 and completes U12A/U12B/U12C/U12D/U12E/U13B against real APIs, then detector feedback/evaluation. Earlier fixture-based UI component work cannot close 4A as real API. 4C proves deeper processing of existing evidence.

Before coding, G00 records one shared contract/base commit. Main currently has only a README: use the authorized shared base containing contracts, not a README-only branch. Test combined changes and previous checkpoint regressions **before** promotion to main; smoke-test the merged commit afterward. Later independent tasks may use disclosed schema-derived fixtures, but completion requires real producers.

The published coordination baseline is a draft; this phase revision remains local until published. No application, Windows, model or benchmark success is claimed.

EVORA is an **AI-assisted multimodal forensic evidence fusion and investigation-support research prototype**. The full proposed initial system is the build goal, delivered in stages. It does not determine guilt, replace professional judgment or claim forensic certification. This repository currently holds coordination artifacts, schema and synthetic inputs, not a running application.

## Read first

- [Original proposal](docs/PROPOSAL.md) — preserved wording, trailing whitespace removed only.
- [Proposal traceability](docs/PROPOSAL_TRACEABILITY.md) — all 40 numbered sections mapped to concrete tasks and acceptance.
- [Full feature scope](docs/FEATURE_SCOPE.md), [architecture](docs/ARCHITECTURE.md) and [design tokens](DESIGN.md).
- [API contract](specs/openapi.yaml) — published **coordination-branch draft**, version 0.2.0; one authority for the same 25 HTTP operations and schemas, not evidence of implemented routes.
- [Phased roadmap](docs/ROADMAP.md) — one authoritative sequence; [task catalog](docs/TASK_BREAKDOWN.md) — exact checkpoint/dependency/acceptance; [scoped agent prompts](docs/AGENT_TASKS.md) — one assignment, not a mega-prompt.
- [Contract policy](docs/CONTRACTS.md), [producer/consumer review](docs/CONTRACT_REVIEW.md), [decision queue](docs/COMMUNICATION.md) and [integration gates](docs/INTEGRATION.md).
- [Preimplementation review](docs/PREIMPLEMENTATION_REVIEW.md) — actual artifact verification and remaining readiness limits, not app benchmarks.
- [Agent rules](AGENTS.md) and [synthetic CSV inputs](fixtures/synthetic-case/).

## Scope, stack and readiness

Four people each work on one module; the confirmed GitHub-handle assignments and integration coordination are recorded in [ROADMAP.md](docs/ROADMAP.md#module-assignment-and-live-task-state). Assignment does not complete G00 or implementation work. Use React + TypeScript for the frontend, FastAPI/Python for the backend, SQLite for authoritative metadata/processing outputs/audit, private files for originals and Neo4j for a versioned/rebuildable derived graph projection. Only the backend accesses databases; Neo4j is graph storage/querying, **not** the triage scoring algorithm. No second Streamlit dashboard is planned.

The three-CSV tracer validates the first path, not the whole product. Full delivery also includes documents/OCR/images/CCTV/mobile/transactions, entities/events, all triage factors, detector-driven and existing-evidence reprocessing feedback, clusters, hypotheses, uncertainty, explanations, approved grounded LLM RAG, human review, private provenance, dashboard and measured evaluation. Full timeline reconstruction is future work.

Ready for review, setup and unaffected scoped work. Auth/membership and client token handling (C-03), CSV limits/malformed behavior (C-04), precise scoring/golden outputs (C-05), RAG provider/privacy (C-06), task-specific handoffs and tested package/Windows setup are not an agreed implementation baseline. Independent work may use accepted-schema fixtures; integrated completion requires real producers. Record the exact common contract commit before task branches depend on it.

## Coordination verification (not application tests)

Run from repository root with Node.js and Python available; use an isolated virtual environment (recommended) and install the pinned validation dependency first. Generated outputs below are disposable examples:

```sh
python -m venv /path/to/scratch/evora-coordination-venv
. /path/to/scratch/evora-coordination-venv/bin/activate
python -m pip install jsonschema==4.25.1
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /path/to/scratch/evora-openapi.json
python scripts/verify_coordination.py /path/to/scratch/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/path/to/scratch/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py' -v
```

The negative/schema-example suite includes `scripts/test_verify_coordination.py` and `scripts/test_contract_examples.py` and uses `jsonschema==4.25.1`. In PowerShell activate the venv with `& /path/to/scratch/evora-coordination-venv/Scripts/Activate.ps1`, run the same pip install, and set `$env:EVORA_CONTRACT_BUNDLE` to the bundled path before the same Python unittest command. Use the checked workflow for client generation, TypeScript compilation and `@google/design.md@0.4.0` DESIGN lint. These validate documents/contracts only. Pin tested backend/frontend/Neo4j/model versions in G01/G01B/G01D and verify Windows skeleton setup in G01C; full-scope execution/reproducibility is I09/I09B. Do not report an installed stack, passing app tests or measured research metrics from document lint.
