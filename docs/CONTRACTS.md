# EVORA contract and implementation-policy register

**Coordination-branch draft, version 0.3.0; not a tested application.** `specs/openapi.yaml` is the sole wire authority for the original 25 operationIds plus only `appendTranscriptRevision` and `listTranscriptRevisions` (27 total). This register explains declared semantics and unresolved policy, not an alternative field list. [Proposal](PROPOSAL.md), [traceability](PROPOSAL_TRACEABILITY.md), [integration](INTEGRATION.md) and [task catalog](TASK_BREAKDOWN.md) preserve full initial scope.

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

### Media-output completeness

For video with enabled visual and speech adapters, the selected completed processing output contains both branches, not competing latest outputs. Compose and verify the complete output before publication; a retry/correction preserves unaffected visual observations and candidate source references. A no-audio/silence status does not remove visual results. An enabled branch failure follows C-04 atomic publication policy rather than silently publishing a speech-only or visual-only success. P14D/I03B exercise these cases through latest-completed and historical selectors.

### Initial local audio/video transcription and immutable corrections

This is planned initial implementation scope, not an implemented ASR service. **3B P16** adds approved local speech transcription for uploaded `audio` and existing `video`; **3B P16B** normalizes timestamped segments and source-backed candidate entity/event extraction/search support. **3C U14** presents transcript/source playback and local text search; **3C U14B** supplies the revision backend; **3C U14C** supplies correction entry, original/effective comparison and immutable history. The task catalog owns dependencies/acceptance and ROADMAP owns checkpoint membership. No application, acquisition service or proposal text is changed by this draft.

P16 emits `Observation.kind=transcript.segment` through existing completed processing output/list APIs. `source_locator` stays a string: canonical `media:start_ms=1250;end_ms=3500` means elapsed milliseconds **on the original evidence media timeline**, not capture UTC. Schema validates syntax; runtime validates increasing nonnegative bounds against decoded duration and accounts for extracted audio track/clip offsets. Omit `observed_at_utc`/`observed_at_raw` unless separate source capture metadata supports a documented time mapping; ASR offsets alone never imply a recording date, UTC instant or event date mentioned in speech. Machine `raw_value` remains preserved; `normalized_value` supplies effective text. Unclear speech uses `[unclear]` without fabricated words. Missing audio track and silent media produce `transcript.status` with `no_audio` and `silence` respectively, **zero speech segments/candidates**, an original-artifact locator and private diagnostic provenance; these are successful empty-content results, not invented speech. Corrupt media, unavailable models and limits follow the separately recorded C-04 rejection/failed-run policy and never masquerade as silence.

`extraction_confidence` is an **uncalibrated model score**, not a calibrated probability, source reliability, speaker identity or conclusion certainty. Where unavailable, 0 is a documented unavailable-score sentinel with private provenance, not a measured confidence. A correction never increases this machine score or establishes identity. P16/P16B must record model/version, local execution/data boundary, language support, decoder/model parameters, input hash, original/derived offsets, output references and times privately; safe public audit contains only authorized references, not transcript text, correction reason contents or media bytes. Unsupported language is explicit, not translated text. No remote evidence transfer, speaker identification, voice matching, emotion inference, translation or diarization is included.

U14 pins one completed `processing_run_id` and pages `listObservations` with `evidence_id` across **all pages** before claiming complete source-transcript search. Searching only loaded pages must be labeled partial; a refresh changes the pinned run explicitly. This is client-side, source-inspector text search, not a new server search endpoint or case-wide retrieval. P16B candidate entities/events join to the same segment IDs/locators; uncertain mentions are candidates, never attributed speakers. Full case retrieval remains A16B, filtered to frozen analytical inputs. Transcript mentions, visual observations, OCR, machine/corrected variants and repeated runs of **one underlying source** are not independent corroboration; duplicated recordings also require C-05 source-origin checks, not merely different Evidence IDs.

U14 plays original authorized `downloadEvidence` bytes with an ephemeral memory Blob/object URL, seeks using media-time locators and revokes the URL on disposal/case switch/logout. No persistent browser evidence cache, remote URL or additional playback route is introduced. Current contract promises full-byte 200 download, not Range/206 streaming. C-04/U14 must select tested browser codecs and bounded download/resource limits; show unsupported playback honestly while preserving authorized download/source access.

**U14B correction contract:** the sole additions are append/list operations at `/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions`. The path always identifies the **original machine** segment. A submission carries that original completed `processing_run_id`, the expected latest complete same-evidence `base_processing_run_id`, explicit nullable expected latest revision, replacement text and nonblank reason. Actor/time are server-authored. All evidence/observation/run/revision joins must be same-case and same-evidence; nonexistent/foreign/mismatched references are 404 without leakage; non-transcript targets/invalid input are 400. Stale base/revision or a latest base no longer containing the original segment lineage is 409: no automatic rebase across re-transcription. Correction edits text only, not original offsets/hash or speaker labels. Idempotency fingerprints request/path/body: identical replay returns original 201 revision before stale checks, different payload under the key is 409, and authorization is rechecked.

A successful append is an **atomic complete materialization**, not an in-place edit: prepare a new ProcessingRun with a versioned correction materializer, copy all unaffected latest-base observations with new IDs and private predecessor provenance (every copied transcript segment also exposes its original machine `source_observation_id`, even if never corrected), substitute this segment's effective text, carry other segments' effective revisions forward and rebuild affected candidates/events against the new observation IDs. Corrected segment keeps original machine `raw_value`, locator and machine confidence, with `source_observation_id` and `transcript_revision_id` identifying immutable lineage. Preserve the entire original completed output and every earlier materialization. Recheck expected base/revision at publication; transactionally persist the revision, complete derived output/run and exactly one safe audit reference or publish none. The response identifies the derived completed run/observation; UI reads them back before success. Assign completion ordering strictly after its base so ordinary `(finished_at UTC,id UUID)` selection chooses the new materialization. Concurrent reprocessing/publication must serialize the final base check. Failed preparation leaves the prior completed selection and revision history unchanged.

**Snapshot consumption is not a live correction overlay.** The new complete materialization participates in unchanged latest-completed selection. Bodyless new-key `startAnalysis` includes its new processing/observation IDs in the existing snapshot digest and derives `new_observations`; repeated analysis key returns its original snapshot. Existing snapshots/results, original-run `listObservations`, citations and old revisions remain unchanged. Analysis, source inspection and A16B consume the selected immutable output, never substitute latest correction text into an older analysis. `startProcessing` remains bodyless: no correction selector/configuration fields are invented. List revision history is ordered `(created_at UTC,id UUID)` before pagination; it is not the text selection mechanism for historical analysis.

Acceptance must execute real local permitted speech/video, silence/no-audio, noise/unclear and unsupported-language controls; original-timeline offsets with nonzero extracted-track offset; unavailable/failed model and resource bounds; all-page search and playback authorization/codec failure; candidate provenance and single-source non-corroboration; same-case joins and two-case rejection; whitespace/forged actor/time; revision ordering, concurrency/stale 409 and same-key replay; atomic rollback; unchanged machine transcript/hash and historical snapshots; new-key corrected snapshot/candidates and no mixed-run UI. Synthetic schema tests only validate shape/declared contract; they do not certify ASR quality, transactional behavior, authorization or playback.

## Implementation gates, not feature-scope renegotiation

| Gate | Needed by | Still to record and test |
|---|---|---|
| C-03 auth and case membership | F00/F01/U01, all case APIs | Local/other bearer provider, token issue/expiry/revocation/storage, case access rules, two test actors/cases; no hard-coded production token |
| C-04 formats/limits/failures | F03/P04/P14B then full adapters | CSV byte/row limits, UTF-8 BOM, missing/extra columns, malformed rows, kind/content handling, 415-before-run vs failed accepted run; later modality layouts/models/resources before their rows |
| C-05 scoring/goldens | G02 and factor/aggregation/retriage rows | Exact functions, source independence, confidence/count/quality treatment, absent factors, weights/bands/ties, detector→factor mapping, reproducible golden rank changes and negative controls |
| C-06 LLM RAG/privacy | G03/A16B/U10B/U10C/I05C | Approved provider/model, private data boundary, prompt versions, thresholds/fallback, credential/cost, retrieval scope, real-provider and no-paid CI testing |
| Assignees/common base | Task handoff | One person per module, one also coordinating; exact common spec commit and bounded allowed paths |
| Tested setup | G01/G01B/G01C/G01D/I09B | Pin tested package/model/Neo4j versions, Windows commands/resources, actual clean setup/full execution evidence |

P08/P09/P10/P16 resolve their own approved OCR/image/video adapter/model/version, format/resource and private data-boundary decisions under C-04 and task acceptance; they do not depend on G03's final generative provider choice. Deterministic U10 requires approved authorized local retrieval/grounding and privacy behavior, not that provider choice. C-06/G03 remains required for full generative U10B/U10C (transitively through U10B) and related final RAG gates.

Selected stack: React/TypeScript, FastAPI/Python, authoritative SQLite, private originals, derived Neo4j graph. These are architecture choices, not proof that every policy/provider/package is agreed or installed. Source proposal weights/bands are experimental examples, not standards or executed results. Work on unrelated setup/review/schema-derived tasks can proceed while dependent gates remain open.
