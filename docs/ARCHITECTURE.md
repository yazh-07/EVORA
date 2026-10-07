# EVORA architecture

**Published coordination-branch draft; no implementation claim.** [Proposal](PROPOSAL.md), [all-section traceability](PROPOSAL_TRACEABILITY.md), [full scope](FEATURE_SCOPE.md), [task catalog](TASK_BREAKDOWN.md) and [DESIGN.md](../DESIGN.md) define the build. Same 25 API operations, version 0.2.0, live only in `specs/openapi.yaml`.

## Topology and data authority

```text
React + TypeScript investigator UI
             | case-scoped HTTP API only
FastAPI/Python modular backend
   |             |                       |
SQLite       private original files   Neo4j
(authority)  (immutable bytes/hash)    (derived case+run graph)
```

A modular monolith preserves four ownership boundaries without four services or a second dashboard. Backend alone opens DB/storage connections; no browser Neo4j driver, Cypher credentials or direct SQL. SQLite is authoritative for cases/access metadata, Evidence metadata, completed processing outputs, immutable analysis input snapshots/findings/triage/history, private versioned provenance and audit. Private original files are immutable; SQL references and hashes identify them. Neo4j stores queryable case-scoped graph partitions that can be rebuilt from authoritative SQL and source references.

Neo4j helps store/query relationships. Relevance/connectivity/corroboration/temporal/source-quality/conflict/gap calculations, anomaly mappings, weights and aggregation are versioned backend algorithm policy, not a database feature.

Delivery sequence is owned by [ROADMAP.md](ROADMAP.md), not this architecture: phases span module boundaries. Exact task/checkpoint/dependency/acceptance is in the catalog; this rewrite changes sequencing, not topology or wire semantics.

4A tests remaining analytical producer components; 4B A17 assembles and coherently publishes them before U12A/U12B/U12C/U12D/U12E/U13B complete real-API panels/uncertainty inspection, followed by detector feedback/evaluation. Earlier fixture-based UI work is independent component work, not 4A real-API completion. No architecture or publication boundary changes are implied.

## Four modules, four people

| Module | Accountable boundary | Main producer/consumer handoff |
|---|---|---|
| M1 Evidence Foundation | Cases/access, immutable originals/hash, metadata, private provenance/audit foundations | Authorized source access to M2; evidence/audit APIs to M4; provenance hooks to all |
| M2 Multimodal Processing | Tested adapters for network/GPS/messages/text/OCR/images/CCTV/mobile/transactions; raw/normalized observations/entities/events | Source-located immutable completed outputs to M3 and M4 |
| M3 Fusion and Adaptive Triage | Source-backed graph, relationships/detectors/factors, versioned coherent analysis and retriage, retrieval context | Completed pinned graph/findings/triage to M4; feedback to optional deeper processing policy |
| M4 Investigator Application | One React dashboard, command/status/read views, audited review/override APIs, grounded generation and verification | API-only UI, same-case claim citations/private Q&A provenance and human decisions |

Each person works on one module; one coordinates integration alongside their own module. Assignees remain TBD. M2/M3 are the heaviest boundaries: loan bounded adapter/factor/test help rather than create competing implementations or a fifth person. A module is not an agent prompt.

## Publish and recover without pretending SQL/Neo4j are one transaction

1. Accept analysis after authorization/idempotency lookup, freeze SQL input snapshot and algorithm version, persist pending run plus candidate outputs in SQL.
2. Write Neo4j partition `(case_id, analysis_run_id)` idempotently using source UUID references. Do not mutate a previously completed graph partition or expose pending writes.
3. Verify nodes/edges and source locators against the frozen SQL snapshot and findings/triage references. Only after success publish SQL `completed` state/pointer; graph/findings/triage APIs select that same run.
4. A failure retains nonpublished state and error/provenance. Crash tests cover each boundary, including graph written but SQL not yet published. Same-key replay returns original resource; workers retry idempotently or a new key starts a new run.
5. Rebuild a selected partition from authoritative immutable SQL inputs/outputs and verify before serving it. An unavailable/corrupt projection must not yield fabricated success or silently mix older graph with newer findings. Recovery/read failure behavior must follow the declared API or receive a coordinated spec change.

There is no distributed transaction assumption. A successful Neo4j call alone is not completed analysis. G01D establishes connection/index/setup; A01B proves partition/recovery; A05 freezes and coherently publishes; A17 assembles all analytical stages.

## Data and adaptive workflow

Intake/hash → processing/normalization → frozen snapshot → graph and available factors → initial triage. No graph-dependent score before supporting observations/graph exist. G02 controls absent factors; uploaded items without observations remain not scored. Proposal diagram ordering does not justify fabricated cold-start scores.

Analysis adds relationships/corroboration/conflicts/gaps/clusters/anomalies/hypotheses/uncertainty/explanations, then feeds actual detector outputs into all reviewed factor calculations (A17/A19). Optional deeper/reconfigured processing of **existing Evidence** uses internal backend policy and a new processing key (P15), leaving original bytes/old outputs unchanged; latest completed output enters a new analysis snapshot and changes justified priorities (A18). New file upload (A07) is one feedback path, not the whole adaptive research contribution.

UI starts processing and bodyless analysis, polls resources, then pins the completed analysis ID across graph/findings/triage and all pages. Historical observations are accessed via processing_run_id. Every edge/finding joins observation IDs to original source locators; node IDs are original Evidence/Entity/Event record UUIDs. Alternative hypotheses use optional missing_information and contradictory evidence; clusters may expose entity_ids. Timestamp normalization/basic temporal reasoning are initial scope, not full timeline reconstruction.

For full-context retrieval and analysis-linked uncertainty views, resolve source records through the selected analysis snapshot's immutable observation/processing-run set. Entity/event list APIs have no analysis selector: do not invent one or display their live lists as a historical analysis snapshot. Candidate entity/event inspection is a processing view; historical analytical sources use snapshot references and `listObservations` processing_run_id where applicable.

## Grounded RAG and privacy

Deterministic source retrieval answers are allowed for the first tracer. Full scope requires A16B retrieval across graph, entities/events, triage, findings, observations and metadata; U10B approved provider grounding; U10C factual-claim citation verification/unsupported fallback and private provenance; U11B final UI; I05C final generative evaluation. The LLM is an evidence interface, not an autonomous forensic decision maker.

Processing/model provenance records inputs, output refs, versions, parameters and time internally. Q&A additionally stores prompt template/version, retrieved IDs+locators, generated response and verification privately. Public audit fields are safe actor/action/target/time/reason references, not raw prompts/content. F08D/F08E test linkage/privacy.

## Scope and unresolved implementation details

The full initial feature set is fixed. Future-only: complete timeline reconstruction/visualization, physical acquisition/disk imaging/live banking, custom large-model training and court-admissible deployment; optional additional model integrations need independent privacy/evaluation review.

C-03–C-06, assignments and tested package/Windows setup remain gates for dependent work. This architecture declares coordination policy; it does not claim completed app tests or an agreed auth/scoring/RAG baseline.
