# EVORA architecture outline — draft

**Status:** design outline; not an implementation claim. Source: the team's `EVORA CompleteWorking new.md` proposal. The official name is EVORA. Timeline reconstruction is explicitly future work.

## Investigation flow

1. **Evidence Foundation** accepts a case and source files, creates stable Evidence IDs, preserves originals, computes hashes, stores metadata and audit/provenance records.
2. **Multimodal Evidence Processing** parses supported documents, images/video, messages, mobile/network records, transactions and GPS data. It emits normalized, source-linked entities, events and observations, or a recorded processing failure.
3. **Fusion and Adaptive Triage** builds evidence/entity/event relationships; detects corroboration, clusters, conflicts, gaps and anomalies; represents uncertainty; computes explained priorities. After new information arrives, an analysis run can produce a new ranking, retaining the prior ranking and why it changed. Automatic scheduling is a separate implementation decision. Alternative hypotheses keep both supporting and contradicting records.
4. **Investigator Application** displays case/evidence detail, relationships, priorities and explanations; offers evidence-grounded case Q&A; records human review and priority overrides through audited operations.

Each module is a **boundary**, not a mandatory separate service or repository. A modular monolith is acceptable if contracts and tests keep boundaries explicit.

## Module interfaces (design requirements, not frozen fields)

| Producer | Consumer | Required exchange |
|---|---|---|
| Foundation | Processing | Case-scoped Evidence ID, original artifact access, type/source and provenance |
| Processing | Fusion | Case-scoped observation/entity/event with original + normalized values, confidence, source Evidence IDs and processing metadata |
| Fusion | Application | Supported links, findings, score factors/priority, rationale and score-change history |
| Application | Foundation/Fusion | Authenticated review decisions, manual override and explicit analysis-run requests, with audit provenance |

`specs/openapi.yaml` proposes exact v1 HTTP paths and wire models. `docs/CONTRACTS.md` lists unresolved technical choices; `docs/INTEGRATION.md` proposes behavior and a tracer. Publish one versioned common contract before independent consumer implementations; this is synchronization, not a leadership assignment or a reduction of the full build scope. Do not infer additional schemas from the prose examples here.

## Order of operations

Foundation records identity and original bytes first. The v1 tracer computes initial triage only after extraction and initial graph construction; before that, evidence is marked **not scored**. Graph-dependent factors require observations and a graph. A subsequent explicit analysis run after new observations produces re-triage, preserving old results, run version/trigger and explanations. An automatic scheduler or cold-start metadata score would need its own reviewed policy and tests.

## Module split (not yet assigned to people)

- M1 Foundation & shared contracts — moderate effort.
- M2 Processing & normalization — very hard; split by format in small tasks.
- M3 Fusion, adaptive triage & analysis — very hard; prioritize testable graph/scoring and retriage contracts.
- M4 Investigator app, grounded retrieval & review — hard; integration is a whole-team obligation, not M4's alone.

Each person works on one module and keeps its interface coherent with the shared spec. One of the four coordinates integration alongside their module. No one silently changes common contracts.

## Out of initial scope per proposal

Full timeline reconstruction; physical-device acquisition; forensic disk imaging; real banking-system access; custom large-model training; claims of court-admissible deployment.
