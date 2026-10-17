# EVORA producer/consumer contract review

**Branch-draft contract 0.3.0; no new approval ceremony.** The original 25 operations plus `appendTranscriptRevision`/`listTranscriptRevisions` (27 total) are in `specs/openapi.yaml`; this map reviews their producers/consumers, not a second API. Four people each work on one module; confirmed GitHub-handle assignments and integration coordination are in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). Full initial proposal scope is fixed; fixture-sized integration does not cut scope.

Canonical delivery order is [ROADMAP.md](ROADMAP.md); task checkpoint/dependency/acceptance lives in the catalog. Processing/analysis lifecycle completion requires early immutable provenance and audit; deterministic retrieval records safe audit before any generative provider is required. Draft 0.3.0 adds only the two explicit transcript-revision operations; local media playback, segment search and candidate extraction reuse existing APIs.

4A validates remaining analytical producer components, not their published real-API panels. U12A/U12B/U12C/U12D/U12E/U13B all retain existing prerequisites and add A17: integrated completion is in 4B after assembled findings/factors are coherently published through A01B/A05 and read through the existing APIs. Earlier schema-derived UI fixtures cannot certify 4A as real API; 4B completes those views before detector feedback/evaluation.

## Every operation and its concrete consumer

| operationId | Backend producer/task | Consumer/task | Required shared verification |
|---|---|---|---|
| `createCase` | M1 F01 | U02B | Authorized stable case, invalid title 400, list refresh |
| `listCases` | M1 F02 | U02 | Authorized-only pagination |
| `getCase` | M1 F01 | U02/U13 | Same case or indistinguishable 404 |
| `uploadEvidence` | M1 F03 | U03 | Private immutable bytes/hash/limits |
| `listEvidence` | M1 F04 | U13 and evidence views | All-page counts/types, not first-page totals |
| `getEvidence` | M1 F04 | U03/U04 | Source metadata/hash, no foreign-case leak |
| `downloadEvidence` | M1 F05 | M2 source access/U04/U14 | Original byte/hash round trip and authorization |
| `startProcessing` | M2 P04/P14D/P15/P16 | U05C; internal deeper policy | Correct adapter, new key vs original-key replay, no invented processing body |
| `listProcessingRuns` | M2 P04 | U05/U13 | Actual immutable run/status history |
| `getProcessingRun` | M2 P04 | U05 | Poll real queued/running/completed/failed state |
| `listObservations` | M2 P04B | M3 A01/A16/P16B, U05B/U14 | Latest completed by default or historical processing_run_id; source locators/pagination |
| `appendTranscriptRevision` | M4 backend U14B with M2 immutable output materialization/P16B | U14C | Original machine observation/run and same-case IDs, stale base/revision 409, idempotency, atomic derived completed output/audit, old snapshots unchanged |
| `listTranscriptRevisions` | M4 backend U14B | U14C/U14 | Authorized immutable original-segment history, ordered pagination and original machine comparison |
| `listEntities` | M2 P05/P05C | A01/A16B/U13C | Candidate IDs, same-case source observation joins |
| `listEvents` | M2 P05B/P05C | A01/A16B/U13C | Source time/participants, no invented time/identity |
| `startAnalysis` | M3 A05/A17 | U05D | No body; immutable snapshot/hash/trigger and request-based idempotency |
| `listAnalysisRuns` | M3 A05 | UI run/history context | Old resources retained, deterministic latest completed ordering |
| `getAnalysisRun` | M3 A05 | U05D | Poll completed coherence before pinning ID |
| `getGraph` | M3 A05B/A01B | U07/A16B | Completed analysis_run_id selector, nonempty run ID, source-backed nodes/edges |
| `listFindings` | M3 A05B/A17 | U07B/U12A–E/U13B/A16B | Same pinned run across pages, source observation locators and uncertainty |
| `listTriage` | M3 A06 | U06/U13B/A16B | Same pinned run, not-scored vs result/override, actual factor sums |
| `getTriageHistory` | M3 A06 | U06B | Append-only automated history distinct from override |
| `reviewFinding` | M4 backend U08 | U08B/M1 F08C | Reason/actor/action audited once, immutable prior decisions |
| `listFindingReviews` | M4 backend U08 | U08B | Authorized append-only review history |
| `setPriorityOverride` | M4 backend U09 | U09B/M1 F08C | Effective priority separate, no automated-history rewrite |
| `askCaseQuestion` | M4 backend U10/U10B/U10C with M3 retrieval | U11/U11B/M1 F08E | Claim citations, fallback and private provenance; approved LLM exercised for full scope |
| `listAuditEvents` | M1 F07 | Authorized audit inspection/I09 | Safe case-scoped paginated actor/action/target/reason; not raw private provenance |

All validation failures use the declared 400 ApiError wire shape; backend mapping/tests are future work. analysis_run_id selector foreign/missing/pending/failed yields 404. UI pins the completed run after polling and through every graph/findings/triage page; mismatches cannot be merged. Historic processing outputs use processing_run_id. Reprocess/new upload changes snapshot only for a new analysis key, never replay of an original key.

## Local transcription producer/consumer handoff

P16/P16B belong to 3B; U14/U14B/U14C belong to 3C. P16 is local audio/video speech ASR under its own C-04 model/language/codec/resource/private-boundary policy, not G03. P16B publishes source-backed candidate extraction through existing observations/entities/events. U14 pages one completed processing output for client-side source transcript search and plays authorized original download bytes with ephemeral object URLs, never persistent evidence cache. Full case retrieval is A16B; no new search/playback route is implied.

The canonical policy in [CONTRACTS.md](CONTRACTS.md#initial-local-audiovideo-transcription-and-immutable-corrections) and schema define original-timeline millisecond locators, no-audio/silence/unclear controls, uncalibrated confidence, single-source non-corroboration and exclusions (remote evidence transfer, speaker ID/voice matching/emotion/translation/diarization). U14B appends against the original machine segment/run with same-case/same-evidence joins and explicit expected base/revision checks. A successful 201 atomically publishes a new complete derived completed processing output plus immutable revision/audit, rebuilding affected candidates and retaining machine text/hash/provenance. U14C reads that exact output back and keeps original/effective/history distinct. Corrections affect new-key analytical snapshots through existing latest-completed selection, never a live overlay or mutation of completed outputs/old snapshots. Both existing start commands stay bodyless. All these are implementation acceptance requirements, not behavior proven by schema examples.

## Fixed declarations versus remaining choices

- **Declared:** bodyless immutable analysis snapshot/digest, request fingerprint/idempotency scope, server-derived trigger, latest completed ordering/selectors, 400 mapping, observation locator trace, supported/unsupported citation cardinality. These require real implementation tests; lint alone does not execute them.
- **Selected architecture:** React/TypeScript, FastAPI/Python, authoritative SQLite/private originals, derived versioned Neo4j. G01D/A01B handle setup/partition recovery; Neo4j is not scoring. No Streamlit duplicate UI.
- **Still open C-03:** choose bearer provider/local policy, expiration/revocation/case membership and frontend token handling. A safe local synthetic-only option is opaque hashed expiring tokens with explicit memberships and two actors/cases; this is a recommendation, **not an agreed mechanism**.
- **Still open C-04:** first CSV validation limits/BOM/columns/malformed behavior and later adapter layouts/resources. MIME/name/source_label are not proof of content or independent origin.
- **Still open C-05:** version exact G02 functions, absent factors, experimental weights/bands/ties and goldens. A04 initial factors are expanded in A17; A10B/A11B/A13B prove real conflict/gap/anomaly score effects. Co-mention and abnormality are not identity/guilt.
- **Still open C-06:** approve provider/private retrieval boundary and claim verification fallback. Deterministic tracer is permissible but cannot replace A16B/U10B/U10C/U11B/I05C final grounded generation.
- **Still open:** exact shared base/task handoffs, bounded G/I assignees and tested package/Windows setup. Module owners are already recorded in ROADMAP. Pin versions in future setup tasks; do not invent installation outcomes.

## Change and verification path

Affected module contributors settle a needed technical choice and record it in the canonical spec/policy. One person keeps shared versions/changes synchronized alongside their module; there is no fifth person or four-signoff requirement. Update producer/consumer/types/fixtures/checks together, run the checked lint/bundle/type/coordination/negative/design workflow and record the exact common commit.

Independent implementation may use schema-derived fixtures while producers are incomplete. Integration completion requires real merged producers and read-back. Review/setup and unaffected scoped work are ready; dependent unresolved decisions are neither blanket permission to guess nor a reason to stop every task. Full-scope closure is I09/I09B and final evidence/limitations I06, not the first tracer.
