# EVORA full initial feature and verification map

The **entire initial proposal is the fixed build goal**, delivered through bounded tasks, not a reduced CSV product. [Preserved proposal](PROPOSAL.md) and [all 40 sections](PROPOSAL_TRACEABILITY.md) are local sources. This map is an inventory, not a module-wide prompt. No feature is implemented by appearing here. Published coordination-branch draft; actual artifact verification is in PREIMPLEMENTATION_REVIEW.

Canonical phase order/exact assignment is [ROADMAP.md](ROADMAP.md). Checkpoint coverage below is derived from the referenced catalog tasks; features can span phases. This is a feature inventory, not permission to implement all cells in one agent task.

4A covers remaining analytical producer component tests; U12A/U12B/U12C/U12D/U12E/U13B real-API acceptance completes in 4B after additional prerequisite A17 assembles/coherently publishes their findings/factors, then detector feedback/evaluation. Earlier declared-fixture UI components do not certify 4A as real API. Feature evidence and full initial scope remain unchanged.

## Complete feature ownership and acceptance

| Initial capability | Accountable module | Concrete tasks/stage | Evidence needed to claim it works | Checkpoint coverage |
|---|---|---|---|---|
| Case creation/catalog/access | M1 | F00/F01/F02/F04/F09; U02/U02B | Stable case IDs, correct authorized pagination and foreign-case/no-existence-leak negatives | 1A |
| Immutable original intake/hash/download/source metadata | M1 | F03/F05/F06; U03/U04 | Byte/hash/size round trip, unsafe/oversized failures, private storage and same-case trace | 1A |
| Private provenance/audit foundations | M1 with producers | F06/F07/F08/F08B/F08C/F08D/F08E; P14/U10C | Actor/action/source/run references plus private versioned model/parser/prompt/parameters/input/output/time/verification; no raw sensitive logs | 1A, 1B, 1C, 2B, 3C, 5B |
| Network records | M2 | P01/P04/P14B/P14D | Actual documented adapter, device/IP/event/time/raw row locator, malformed control | 1B, 3C |
| GPS/spatial records | M2 | P02/P03/P14D | Preserved coordinates/time, unambiguous normalized UTC, invalid/no-zone controls | 1B, 3C |
| Messages/device mentions | M2 | P06/P13/P13B | Source spans, candidate keys/events; co-mention not identity | 2A, 3A |
| Documents/reports/text | M2 | P07/P13/P13B | Agreed supported encoding/layout, source lines/pages/spans, empty/invalid tests | 3A |
| OCR for scanned document/image text | M2 | P08 | Actual selected OCR model/version/confidence and source region/page, false-positive/failure controls | 3B |
| Image object/person/vehicle detection | M2 | P09 | Pretrained permitted model/sample, bounded category/region, confidence; no named-person identity claim | 3B |
| CCTV/video observations | M2 | P10 | Frame/time locators, model/version/resource limits and malformed/unavailable-media behavior | 3B |
| Mobile logs | M2 | P11 | Supported exported device/auth/activity layout, source-located events; no physical acquisition | 3A |
| Transactions | M2 | P12 | Account/amount/currency/time/transaction source links, boundary failures; no live bank access | 3A |
| Common normalized observations/entities/events | M2 | P03/P03B/P03C/P05/P05B/P05C/P13/P13B | All adapter outputs retain raw/source time/location and source Evidence/observation IDs; candidate identity and uncertainty | 1B, 3A, 3C |
| Processing lifecycle/full dispatch/deeper existing processing | M2 | P04/P04B/P14/P14B/P14C/P14D/P15 | Idempotency/failure atomicity, latest and historical completed outputs; new-key deeper policy leaves old outputs/original unchanged | 1B, 3C, 4C |
| Versioned graph storage/projection recovery | M3 | G01D/A01/A01B/A02/A05 | Source UUID nodes, observation-backed edges; SQL pending→Neo4j case+run→verify→SQL completed pointer, hidden partials and safe rebuild | 1C |
| Cross-source relationship reasoning | M3 | A02/A07 | Real supported candidate links/common identifiers and unrelated/weak controls, same-case locators | 1C, 2A |
| Relevance and graph-connectivity factors | M3 | G02/A03/A03B | Deterministic reviewed functions, reasons/source support; connectivity not culpability | 1C |
| Temporal-proximity factor | M3 | G02/A03C | Actual supported timestamps/precision/timezone handling and absent-time policy | 1C, 4A |
| Independent corroboration factor/findings | M3 | G02/A08 | Independent-source definition; duplicates not independent; source-backed counterexamples | 1C, 4A |
| Source quality, extraction confidence/count and uncertainty | M3 with M2 | G02/A09/P14/A08/A10; U13B | Distinct extraction/source/association measures, counts/confidence used only per policy, unknown disclosed | 1B, 1C, 4A, 4B |
| Potential conflicts and conflict-aware priority | M3 | A10/A10B/A17/A19; U12A | Overlap/location uncertainty, contrary sources and actual factor/rank effect; no source falsely declared invalid | 4A, 4B |
| Evidence gaps and gap-relevant priority | M3 | A11/A11B/A17/A19; U12B | Bounded insufficient information, candidate available evidence, actual score impact; no absence-as-proof | 4A, 4B |
| Clusters and cluster prioritization | M3 | A12/A12B; U12C | Deterministic Evidence/entity membership and explained scored-evidence review order | 4A, 4B |
| Anomaly detection and triage feedback | M3 | A13/A13B/A17/A19; U12D | Tested selected deterministic/rule/statistical or approved pretrained detector, false positives and existing-factor policy mapping; abnormal not guilt | 4A, 4B |
| Alternative hypothesis comparison | M3 | A14; U12E | Both supporting/contradictory evidence and missing_information, human review and uncertainty | 4A, 4B |
| Explainable initial scores and analysis/history | M3 | A04/A05/A05B/A06/A15 | Factor sum/bands/ties/version and source locator trace; frozen snapshot/idempotency/trigger and coherent pinned reads; no fabricated missing factors | 1C |
| Adaptive new-upload AND detector/deeper-existing-evidence loop | M3 with M2 | A07/A17/A18/A19/P15; I02/I07/I07B | Actual justified earlier rank changes after new discovery/detector feedback/reprocess; new snapshots, immutable old results and same original hash | 2A, 4B, 4C |
| Faithful findings/triage/model explanations | M3 | A15/I08 | Reasons correspond to contributing features; input-removal counterfactual; feature importance/SHAP where valid for selected models, not obligatory inapplicable output | 1C, 6A |
| Full retrieval context and grounded LLM RAG | M3 retrieval/M4 generation | A16 tracer then A16B/U10B/U10C/U11B/G03/I05C | Graph/entities/events/triage/findings/metadata retrieval, actual approved generation, verified claim locators, unsupported fallback and private prompt/output provenance | 2C, 5A, 5B |
| Case/evidence overview and commands/status | M4 | U01/U02/U02B/U03/U04/U05/U05B/U05C/U05D/U13 | Real API create/upload/download/start/poll; all-page counts/types/status, not invented summary endpoint | 1A, 1B, 1C |
| Priority/history/graph/finding/uncertainty/entity-event inspectors | M4 | U06/U06B/U07/U07B/U13B/U13C | Completed analysis_run_id pinned across analytical pages/views; U13C is a processing-source view, not a historically pinned analysis; observation-run history/source navigation, honest unknown/not-scored/error states | 1C, 2A, 3C, 4B |
| Conflicts/gaps/clusters/anomalies/hypotheses panels | M4 | U12A/U12B/U12C/U12D/U12E | Real same-run findings/observations and source links, missing/contradictory data, no fabricated success | 4B |
| Human review and manual priority override | M4 with M1 audit/M3 history | U08/U08B/U09/U09B/F08C | Accepted/rejected/needs_investigation plus required reason/actor/time and audit; automatic history unchanged | 2B |
| One accessible evidence-first React dashboard | M4 | G01B/U01/U02/U02B/U03/U04/U05/U05B/U05C/U05D/U06/U06B/U07/U07B/U08/U08B/U09/U09B/U10/U10B/U10C/U11/U11B/U12A/U12B/U12C/U12D/U12E/U13/U13B/U13C; I09 | DESIGN.md shared styles, keyboard/focus/contrast/responsive behavior, safe untrusted text and API-only storage boundary; no Streamlit second dashboard | 0, 1A, 1B, 1C, 2A, 2B, 2C, 3C, 4B, 5B, 6B |
| Synthetic/permitted datasets and actual research evaluation | All modules | I04/I05/I05B/I05C/I08 | Labeled extraction/link P/R/F1; top-k/precision@k/MRR/consistency/effort/reranks/weight sensitivity; detector misses/false positives; faithful explanations; final RAG grounding/citations with actual counts/versions | 3A, 4B, 4C, 5B, 6A |
| Full integration and clean reproducibility | All modules | I09/I09B after tracer I01/I02/I02B/I02C/I03 | Every F/P/A/U row reachable and real producers exercised; pinned snapshots/recovery/privacy/security; tested pinned versions on clean Windows and CI | 1C, 2A, 2B, 2C, 6B |
| Comparative/threat/provenance/limitations report | Four contributors | I06 after full gates | Cited positioning, measured limitations/resource/privacy threats; no claimed invention of established techniques/certification/admissibility | 6C |

## Source technology choices and scope boundaries

Architecture baseline is **React + TypeScript**, **FastAPI/Python**, authoritative **SQLite** metadata/outputs/audit, **private original files**, and a derived versioned/rebuildable **Neo4j** graph. Source section 30 names Streamlit/SQL alternatives as possible technologies; the shared architecture selects React, not a second dashboard, and SQLite, not dual SQL stores. Neo4j is included through G01D/A01B, not quietly removed as optional. Pandas/NumPy, OCR, OpenCV/pretrained detection, NLP, scikit-learn/SHAP and retrieval embeddings/vector indexes are candidates where appropriate; select/pin/test required packages/models in their setup/adapter policy, not claim every package is installed or every named technique must be duplicated.

Full timeline reconstruction/chronological visualization is explicitly **future** (section 38). Initial timestamp normalization, temporal proximity and conflict/gap reasoning remain mandatory. Physical acquisition, disk imaging, live banking, custom large/LLM training and court-admissible production deployment are outside initial scope. Optional extra provider/model adapters such as Jev require separate privacy/evaluation decisions and do not replace core capability.

## Phased delivery and real completion

Use [ROADMAP.md](ROADMAP.md) for Phase 0–6 outcomes, exact checkpoint membership, open gates and promotion. Source/feature coverage stays here; dependency and acceptance stays in [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md). No unfinished initial feature becomes future merely because its phase has not completed.

The first deliveries prove authorized intake, immutable network/GPS processing and coherent initial analysis separately (I00/I00B/I01). I02 then proves new-upload adaptation; I07 proves detector feedback and I07B deeper processing of existing evidence after full modality handoff. Final RAG requires the actual approved generation/verification pipeline, not the deterministic tracer. I09/I09B and the final report retain full-scope closure.

C-03–C-06, assignments and tested package/setup choices remain targeted gates. Planning checks validate coverage/order, not application behavior or benchmarks.
