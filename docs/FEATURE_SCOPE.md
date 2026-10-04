# EVORA full-project feature map

**Source:** teammate's `EVORA CompleteWorking new.md` (40 sections). The four-person team intends to implement the full proposed initial feature scope in stages; this map does not claim those features already exist. The official name is EVORA. The first integration tracer is three synthetic CSV inputs; that is **not** a reduced project scope. This table is a feature map, **not agent tasks**; use individual IDs in `docs/TASK_BREAKDOWN.md`. Full timeline reconstruction remains a future enhancement.

## Scope and module ownership

| Proposed capability | Module | Delivery slice / dependency | Evidence needed to claim it works |
|---|---|---|---|
| Case creation, case isolation and evidence catalog | M1 | F00–F04 | CRUD/read behavior, same-case/foreign-case tests |
| Original evidence storage, ID, SHA-256, metadata | M1 | F03–F05 | Byte-for-byte/hash round trip, immutable original |
| Provenance and processing/audit history | M1 + producers | F06–F09 and all modules | Actor/operation/source/version trace; do not claim certified chain of custody |
| Documents, text and message extraction | M2 | P06–P08, P13/P13B | Source-linked fields + bad-input tests; agreed formats first |
| Network and mobile records | M2 | P01 then P11 | Validated adapter per declared layout; no device acquisition claim |
| GPS and spatial observations | M2 | P02–P03; richer formats later | Time/location normalization with source/raw value retained |
| Transactions and financial records | M2 | P12 | Synthetic schema, provenance, currency/time handling; no live banking access |
| Images/CCTV, detection and OCR | M2 | P08–P10 | Synthetic or permitted samples, model/version, false-positive review |
| Entity and event extraction + normalization | M2 | P03B/P03C/P05/P05B/P13/P13B | Candidate IDs, observations/events and original location/time; uncertainty recorded |
| Case-scoped knowledge graph and cross-source links | M3 | A01–A02 | Source-backed nodes/edges; weak association not presented as identity |
| Relevance, graph connectivity and source quality factors | M3 | G02, A03/A03B/A09 | Versioned, deterministic factor definitions and missing-data rules |
| Corroboration, independent-source checks | M3 | A08 | Multiple records from one source not counted as independent |
| Explainable weighted initial triage | M3 | A04–A06/A15 | Score/band and contributing values/weights/source IDs agree with policy |
| Adaptive re-triage after new discoveries | M3 | A07 + P06 | Old/new runs preserved and a justified rank/priority change in synthetic test |
| Clusters and cluster prioritization | M3 | A12/A12B | Reproducible membership and supported priorities |
| Conflict, gap and anomaly detection | M3 | A10/A11/A13 | Positive and false-positive cases; unknown is not absence or guilt |
| Reliability, extraction confidence and uncertainty | M2 + M3 | P14/A09 throughout | Separate source/extraction/association measures shown honestly |
| Alternative hypothesis comparison | M3 | A14 | Supporting, contradicting and missing evidence; human verification |
| Finding/priority explanations and optional advanced XAI | M3 | A15; SHAP/counterfactual later if justified | Explanation faithfully matches actual rule/model inputs |
| Case overview, evidence/priority/graph views | M4 | U01–U07B | Live API data, empty/error states and click-through to cited original |
| Human finding review and manual priority override | M4 + M1 audit + M3 | U08/U08B/U09/U09B | Actor/reason logged; automated history not overwritten |
| Evidence-grounded question/answer interface | M4, with M3 retrieval | A16, U10/U11 | Source IDs for every factual claim, unsupported-answer behavior |
| Synthetic evaluation datasets and research benchmarks | All modules | I04/I05 | Extraction/link precision-recall/F1; triage top-k/precision@k/MRR and rerank; gap/conflict/anomaly false positives; answer citation/grounding rates. Publish actual measured results, never invented metrics. |
| Windows installation, packaging, CI and reproducibility | All modules | G01C/I03 | Clean Windows setup, deterministic CI, synthetic E2E run and documented limits |
| Comparative research/positioning | Four-person team | I06 report, not runtime software | Cite existing products accurately; do not claim EVORA invented graphs/AI/triage |

**Future, not initial project requirement:** complete timeline reconstruction and visualization; optional Jev-assisted candidate matching/citation checking (only after privacy and benchmark review); physical mobile acquisition; forensic disk imaging; live banking access; large model training; court-admissible production deployment. Basic timestamp preservation and temporal reasoning *are* part of the proposed current workflow.

## Sequencing without hidden scope cuts

- **Common base:** affected module contributors record OpenAPI/auth/case/initial-format details needed by the first tickets and publish one shared contract commit. Four people each take one module; one also coordinates integration. FastAPI/SQLite/React and the three-CSV *first tracer* are selected; this does not reduce the agreed full feature goal. Windows setup must still be tested.
- **Tracer:** follow `G00 → G01/G01B/G02 → Fxx/Pxx/Axx/Uxx → I01/I02/I02B/I02C` in `docs/TASK_BREAKDOWN.md`, adding network/GPS first and message evidence later for re-triage, review and grounded Q&A. This validates the architecture but is **not** the full multimodal research system.
- **Expansion:** use the initial ticket catalog in `docs/TASK_BREAKDOWN.md`; further split any ticket that still spans unrelated behaviors. Do not assign this feature table as an agent prompt; each PR names exact input/output/test and a human reviews any contract change.
- **Research gate:** run reproducible labeled synthetic/publicly permitted datasets, report measured baselines and false positives. A capability is incomplete until exercised; a route appearing in OpenAPI is only a contract slot.

`docs/ROADMAP.md` is the live task ledger; `specs/openapi.yaml` is the *local draft* wire contract (authoritative for agents once a common version is published). The full initial feature goal is decided; detailed algorithms, exact file layouts and evaluation thresholds still require decisions and experiments as their tickets arise, not guesses.
