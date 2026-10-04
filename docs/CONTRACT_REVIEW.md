# EVORA producer/consumer contract review

**Published branch-draft contract 0.2.0; no new approval ceremony.** The same 25 operations are in `specs/openapi.yaml`; this map reviews their producers/consumers, not a second API. Four people each work on one module; one also coordinates integration. Assignees remain TBD. Full initial proposal scope is fixed; fixture-sized integration does not cut scope.

## Every operation and its concrete consumer

| operationId | Backend producer/task | Consumer/task | Required shared verification |
|---|---|---|---|
| `createCase` | M1 F01 | U02B | Authorized stable case, invalid title 400, list refresh |
| `listCases` | M1 F02 | U02 | Authorized-only pagination |
| `getCase` | M1 F01 | U02/U13 | Same case or indistinguishable 404 |
| `uploadEvidence` | M1 F03 | U03 | Private immutable bytes/hash/limits |
| `listEvidence` | M1 F04 | U13 and evidence views | All-page counts/types, not first-page totals |
| `getEvidence` | M1 F04 | U03/U04 | Source metadata/hash, no foreign-case leak |
| `downloadEvidence` | M1 F05 | M2 source access/U04 | Original byte/hash round trip and authorization |
| `startProcessing` | M2 P04/P14D/P15 | U05C; internal deeper policy | Correct adapter, new key vs original-key replay, no invented processing body |
| `listProcessingRuns` | M2 P04 | U05/U13 | Actual immutable run/status history |
| `getProcessingRun` | M2 P04 | U05 | Poll real queued/running/completed/failed state |
| `listObservations` | M2 P04B | M3 A01/A16, U05B | Latest completed by default or historical processing_run_id; source locators/pagination |
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

## Fixed declarations versus remaining choices

- **Declared:** bodyless immutable analysis snapshot/digest, request fingerprint/idempotency scope, server-derived trigger, latest completed ordering/selectors, 400 mapping, observation locator trace, supported/unsupported citation cardinality. These require real implementation tests; lint alone does not execute them.
- **Selected architecture:** React/TypeScript, FastAPI/Python, authoritative SQLite/private originals, derived versioned Neo4j. G01D/A01B handle setup/partition recovery; Neo4j is not scoring. No Streamlit duplicate UI.
- **Still open C-03:** choose bearer provider/local policy, expiration/revocation/case membership and frontend token handling. A safe local synthetic-only option is opaque hashed expiring tokens with explicit memberships and two actors/cases; this is a recommendation, **not an agreed mechanism**.
- **Still open C-04:** first CSV validation limits/BOM/columns/malformed behavior and later adapter layouts/resources. MIME/name/source_label are not proof of content or independent origin.
- **Still open C-05:** version exact G02 functions, absent factors, experimental weights/bands/ties and goldens. A04 initial factors are expanded in A17; A10B/A11B/A13B prove real conflict/gap/anomaly score effects. Co-mention and abnormality are not identity/guilt.
- **Still open C-06:** approve provider/private retrieval boundary and claim verification fallback. Deterministic tracer is permissible but cannot replace A16B/U10B/U10C/U11B/I05C final grounded generation.
- **Still open:** assignees, exact shared base handoff and tested package/Windows setup. Pin versions in future setup tasks; do not invent installation outcomes.

## Change and verification path

Affected module contributors settle a needed technical choice and record it in the canonical spec/policy. One person keeps shared versions/changes synchronized alongside their module; there is no fifth person or four-signoff requirement. Update producer/consumer/types/fixtures/checks together, run the checked lint/bundle/type/coordination/negative/design workflow and record the exact common commit.

Independent implementation may use schema-derived fixtures while producers are incomplete. Integration completion requires real merged producers and read-back. Review/setup and unaffected scoped work are ready; dependent unresolved decisions are neither blanket permission to guess nor a reason to stop every task. Full-scope closure is I09/I09B and final evidence/limitations I06, not the first tracer.
