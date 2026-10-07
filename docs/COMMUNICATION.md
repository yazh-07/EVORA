# EVORA cross-module decision and handoff queue

Four people each work on one module; one also coordinates integration. This file is a queue for exact questions/mismatches, **not another API authority** or permission to rewrite another module. The spec/docs are published as a coordination-branch draft; the application does not exist yet.

## Use

1. Record task, operation/schema, observed versus required behavior, affected producer/consumer, proposed bounded correction and fixture/test. Avoid private evidence, credentials, raw model prompts/responses and personally identifying case data.
2. Affected module contributors choose one compatible behavior; one person synchronizes shared edits alongside their module. There is no personnel title, fifth member or signoff ceremony.
3. Wire changes go into `specs/openapi.yaml`; internal policy goes into versioned policy/task acceptance. Update producer/consumer/types/fixtures/tests together. A queue comment does not change the API.
4. On implemented code, file a bounded corrective task rather than a module rewrite. Remove verified resolutions from the open queue; preserve their policy/test/PR/Git record. Serialize queue edits or submit in PRs.
5. A dependent task cannot guess an unresolved policy. Unaffected scoped work/review/setup and schema-derived test doubles can proceed; integrated completion requires real producers.

Entry shape: `ID | affected tickets/modules | exact question | versioned resolution + actual proof needed`.

Phase/checkpoint membership and promotion rules live only in [ROADMAP.md](ROADMAP.md). Include the affected checkpoint on new queue entries; an open decision blocks its dependent row, not an entire unrelated phase.

## Open gates

| ID | Affected tickets/modules | Exact question | Resolution and proof needed |
|---|---|---|---|
| C-03 | G00/F00/F01/U01; all case APIs | Bearer auth exists in the wire contract, but issue/expiry/revocation, case membership, local test identities and UI token handling are not chosen | Record a safe provider/local synthetic-only policy; test missing/invalid/expired identity, two actors/cases, foreign IDs and no leaked existence; no shared production token |
| C-04 | F03/P04/P14B/P14D; M1/M2 | CSV byte/row limits, BOM, missing/extra columns, malformed rows and kind/content validation; 415 before run versus accepted failed run | Record first-format policy and actual valid/malformed/unsupported/oversized/retry tests; later adapters choose documented layouts/models/limits before their rows |
| C-05 | G02/A03–A19/I02/I05/I07/I07B; M3 with M2/M4 | Exact factor functions/quality/count/confidence/missing inputs, independence/weights/bands/ties, anomaly mapping and goldens remain open | Version actual scoring policy and positive/counterexamples; prove new-upload, detector feedback and existing-evidence reprocessing change earlier ranks with faithful explanations/history; no silent new factor enum |
| C-06 | G03/A16B/U10B/U10C/U11B/I05C/F08E; M3/M4/M1 privacy | Approved LLM provider/model, retrieval/privacy boundary, prompt versions, verification thresholds and fallback | Record policy and exercise approved generation + verification; no-paid CI adapter labeled test-only; same-case claim locators, unsupported zero citations and private provenance audited without raw public logs |

Assignees and tested package/Windows/Neo4j/model setup are also open readiness items in `ROADMAP.md`; no names or installation success are implied.

Gates are targeted: P08/P09/P10 need approved OCR/image/video adapter/model/version and private data-boundary decisions under C-04/task acceptance, not G03's final generative provider choice. Deterministic U10 needs approved authorized local retrieval/grounding/privacy behavior, not that choice; full U10B/U10C generation/verification retains G03/C-06. C-05/G02 retains score functions/bands/score-level tie policy; `listTriage` pagination order is already fixed by pinned computed score descending, then evidence UUID ascending, with unscored UUID-ordered items last, never live effective priority.

## Declared resolutions, not running-code claims

C-01 is resolved in draft policy/schema: required frozen AnalysisInputSnapshot, latest completed processing selection, canonical digest, request-based idempotency before resnapshot, derived trigger and immutable historic output. A05/A18/I01/I07B still must execute these tests.

C-02 is resolved in draft wire mapping: **all** operations declare 400 ApiError. G01/F00 still must implement and test FastAPI validation mapping rather than default 422.

Completed-run selectors pin related reads and pages; pending/failed/foreign/missing selectors are 404. A05B/A06/U05D/U06/U07/I01 test consistent analysis_run_id, P04B/U05B test processing_run_id history. These are declared contract behaviors, not observed app failures or completed tests.

The same 25 operationIds remain. Full proposal scope is not awaiting renewed feature approval; unresolved settings block their dependent rows only. Artifact verification status belongs in `PREIMPLEMENTATION_REVIEW.md`, not invented application metrics here.
