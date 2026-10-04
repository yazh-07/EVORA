# EVORA contract and implementation-policy register

**Published coordination-branch draft, version 0.2.0; not a tested application.** `specs/openapi.yaml` is the sole wire authority for the same 25 operationIds. This register explains declared semantics and unresolved policy, not an alternative field list. [Proposal](PROPOSAL.md), [traceability](PROPOSAL_TRACEABILITY.md), [integration](INTEGRATION.md) and [task catalog](TASK_BREAKDOWN.md) preserve full initial scope.

## Declared draft behavior (implementation/tests still required)

### Validation, authorization and selectors

All operations declare 400 `ApiError` for invalid path/query/body input. G01/F00 implement the shared FastAPI mapping rather than leaking default 422 responses. Authentication failures are 401; inaccessible/nonexistent case-scoped resources are 404 without existence leakage. Upload/idempotency/unsupported-format errors use only the responses declared on the operation. C-02 is resolved at the **wire-contract** level, not by already executed backend tests.

`getGraph`, `listFindings` and `listTriage` accept optional `analysis_run_id`: a same-case **completed** run is pinned; missing/foreign/pending/failed selector is 404. Without the selector, choose latest completed by `(created_at UTC, id UUID)`, never completion-order races. `Graph`, `FindingPage` and `TriagePage` must return `analysis_run_id` whenever a completed snapshot is selected, including an empty selected result/page. Schema conditionals require it for nonempty graphs, nonempty findings or positive finding totals, and scored triage entries. Before any completed analysis, empty graph/findings and unscored triage may omit it; unscored triage may list uploaded evidence. Related reads and every page use one pinned completed run; UI validates IDs and never mixes snapshots. Poll completion, pin that run, then load all three views. Switching to a newer run is an explicit coherent refresh.

`listObservations` defaults to latest completed processing output per evidence; optional `processing_run_id` pins an authorized completed historical output. It does not expose pending/failed partial data. Old run resources/results remain accessible and immutable.

### Bodyless analysis freezes required input

`startAnalysis` has **no body**. At acceptance, the server freezes required `AnalysisRun.input_snapshot`, an `AnalysisInputSnapshot` object:

- `case_id` is the authorized case UUID.
- `evidence_ids` includes **every uploaded case evidence item at acceptance**, not just processed/scored items.
- For each evidence item choose latest completed processing run by `(finished_at UTC, id UUID)`; `processing_run_ids` contains selected runs.
- `observation_ids` contains those selected runs' completed immutable observations. No pending/failed output participates. Evidence lacking observations remains in the input manifest but is not scored under G02.
- UUID arrays are unique, lexically sorted and may be empty. Freeze all values before worker execution; later upload/processing does not alter an accepted run.
- `sha256` is lowercase SHA-256 of UTF-8 compact JSON with `sort_keys=True`, separators `(',', ':')`, for exactly `{case_id, evidence_ids, processing_run_ids, observation_ids}` using the sorted arrays. The digest field itself is excluded. It never changes original `Evidence.sha256`.

Python reference canonicalization for a validated manifest (not an app implementation):

```python
payload = {"case_id": case_id, "evidence_ids": sorted(set(evidence_ids)),
           "processing_run_ids": sorted(set(processing_run_ids)),
           "observation_ids": sorted(set(observation_ids))}
digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()
```

This example explains hashing, not permission to silently repair invalid request identifiers or mutate snapshots.

### Lifecycle, idempotency and trigger derivation

Completed or failed `ProcessingRun`/`AnalysisRun` resources require `finished_at`; failed resources also require a nonempty `error`. Queued/running state is not completion. Terminal fields support deterministic latest-completed selection and honest failure UI, but runtime timing/state transitions still need tests.

Keys are scoped to authenticated actor + case + operation. Fingerprint the **request** method/path/explicit parameters/body; processing's evidence target is part of the path. Reusing a processing key for another evidence target is 409. Same key/fingerprint returns the **same original run before any resnapshot**, even if current server data changed or that run failed. Changing current evidence/output data is not a changed request fingerprint. A new key permits a new accepted run and current snapshot.

Server derives trigger against previous latest completed analysis: none → `initial`; changed input snapshot digest → `new_observations` (including reprocessing existing evidence); identical digest → `manual` (including an algorithm-version change). Caller does not supply trigger or snapshot in a body. Tie-break selection and snapshot/trigger/replay behavior need actual A05/F00/I01/I07B tests; C-01 is resolved as declared policy, not executable success.

### Graph/findings/triage publication

SQLite is authoritative. Persist pending SQL run/output; write the `(case_id, analysis_run_id)` Neo4j partition idempotently; verify source records, references and coherent graph/findings/triage; **only then** publish the SQL completed pointer. No distributed transaction or dual-write success assumption. Hide partial/failed partitions. Retry/rebuild from immutable SQL safely; do not serve graph from a different run than findings/triage.

`GraphNode.id` is source Evidence/Entity/Event UUID within case; no anonymous invented IDs and no required node observation_ids. `GraphEdge` and `Finding` have required unique nonempty `observation_ids` leading to original source locators. `Finding.missing_information` is optional string array for hypotheses; `Finding.entity_ids` is optional UUID array for cluster membership. Use these fields, not invented endpoints.

For `listTriage`, membership is **exactly** the selected completed `AnalysisRun.input_snapshot.evidence_ids`, including evidence without observations; `total` is that manifest's count, not the current upload count or only scored items. Each `latest_result`, when present, belongs to that selected run. Later uploads, processing and completed analyses cannot alter a pinned run's membership, total or automated results. Sort before slicing `limit/offset`: scored entries by pinned computed `latest_result.score` descending, ties by evidence UUID lexically ascending; unscored entries last by evidence UUID ascending. G02 still chooses score functions, score-level tie/band policy and goldens, but cannot replace this fixed pagination order with effective-priority ordering.

Only before any completed analysis, an unselected `listTriage` read lists live uploaded case evidence with live total, ordered by evidence UUID ascending, without `latest_result`; UI shows **not scored**, not computed P4. This pre-analysis list is not snapshot-pinned. Evidence without observations in a completed snapshot likewise has no automated result.

`override` is a **live overlay**, not part of the automated snapshot: on each read select the latest authorized same-case override for that evidence by `(created_at UTC, id UUID)`. `effective_priority` is its priority when present, otherwise the selected automated priority, and is omitted if neither exists. An override does not make an item scored. Override changes may update these overlay fields even for an old pinned run, but must not change membership/total, reorder the list or cause pagination duplicates/skips; clients must not re-sort by effective priority. `getTriageHistory` remains append-only immutable automated results, never rewritten or overlaid by overrides. A04 aggregates initial available factors; later factors and detector feedback are explicitly wired in A17. Neo4j is not the scoring algorithm.

### Grounding and private provenance

Supported `CaseAnswer` requires at least one citation; unsupported requires zero citations and no unsupported factual assertion. Claim-by-claim grounding still requires runtime verification: valid schema cannot prove a source supports a claim. `model_version`, `prompt_template_version` and `provenance_id` are optional wire fields for full generation. Deterministic U10/U11 first tracer does not complete full LLM RAG.

Private versioned processing provenance records inputs, output references, model/parser/version, parameters and timestamp. Q&A adds prompt template/version, retrieved IDs+locators, generated response and verification. Store in a private authorized store linked to safe audit references; do not publish this rich internal schema by default or put raw sensitive data in application logs/public AuditEvent fields. F08D/F08E test it.

## Implementation gates, not feature-scope renegotiation

| Gate | Needed by | Still to record and test |
|---|---|---|
| C-03 auth and case membership | F00/F01/U01, all case APIs | Local/other bearer provider, token issue/expiry/revocation/storage, case access rules, two test actors/cases; no hard-coded production token |
| C-04 formats/limits/failures | F03/P04/P14B then full adapters | CSV byte/row limits, UTF-8 BOM, missing/extra columns, malformed rows, kind/content handling, 415-before-run vs failed accepted run; later modality layouts/models/resources before their rows |
| C-05 scoring/goldens | G02 and factor/aggregation/retriage rows | Exact functions, source independence, confidence/count/quality treatment, absent factors, weights/bands/ties, detector→factor mapping, reproducible golden rank changes and negative controls |
| C-06 LLM RAG/privacy | G03/A16B/U10B/U10C/I05C | Approved provider/model, private data boundary, prompt versions, thresholds/fallback, credential/cost, retrieval scope, real-provider and no-paid CI testing |
| Assignees/common base | Task handoff | One person per module, one also coordinating; exact common spec commit and bounded allowed paths |
| Tested setup | G01/G01B/G01C/G01D/I09B | Pin tested package/model/Neo4j versions, Windows commands/resources, actual clean setup/full execution evidence |

P08/P09/P10 resolve their own approved OCR/image/video adapter/model/version, format/resource and private data-boundary decisions under C-04 and task acceptance; they do not depend on G03's final generative provider choice. Deterministic U10 requires approved authorized local retrieval/grounding and privacy behavior, not that provider choice. C-06/G03 remains required for full generative U10B/U10C (transitively through U10B) and related final RAG gates.

Selected stack: React/TypeScript, FastAPI/Python, authoritative SQLite, private originals, derived Neo4j graph. These are architecture choices, not proof that every policy/provider/package is agreed or installed. Source proposal weights/bands are experimental examples, not standards or executed results. Work on unrelated setup/review/schema-derived tasks can proceed while dependent gates remain open.
