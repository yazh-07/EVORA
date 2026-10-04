# EVORA full initial feature and verification map

The **entire initial proposal is the fixed build goal**, delivered through bounded tasks, not a reduced CSV product. [Preserved proposal](PROPOSAL.md) and [all 40 sections](PROPOSAL_TRACEABILITY.md) are local sources. This map is an inventory, not a module-wide prompt. No feature is implemented by appearing here. Published coordination-branch draft; actual artifact verification is in PREIMPLEMENTATION_REVIEW.

## Complete feature ownership and acceptance

| Initial capability | Accountable module | Concrete tasks/stage | Evidence needed to claim it works |
|---|---|---|---|
| Case creation/catalog/access | M1 | F00/F01/F02/F04/F09; U02/U02B | Stable case IDs, correct authorized pagination and foreign-case/no-existence-leak negatives |
| Immutable original intake/hash/download/source metadata | M1 | F03/F05/F06; U03/U04 | Byte/hash/size round trip, unsafe/oversized failures, private storage and same-case trace |
| Private provenance/audit foundations | M1 with producers | F06/F07/F08/F08B/F08C/F08D/F08E; P14/U10C | Actor/action/source/run references plus private versioned model/parser/prompt/parameters/input/output/time/verification; no raw sensitive logs |
| Network records | M2 | P01/P04/P14B/P14D | Actual documented adapter, device/IP/event/time/raw row locator, malformed control |
| GPS/spatial records | M2 | P02/P03/P14D | Preserved coordinates/time, unambiguous normalized UTC, invalid/no-zone controls |
| Messages/device mentions | M2 | P06/P13/P13B | Source spans, candidate keys/events; co-mention not identity |
| Documents/reports/text | M2 | P07/P13/P13B | Agreed supported encoding/layout, source lines/pages/spans, empty/invalid tests |
| OCR for scanned document/image text | M2 | P08 | Actual selected OCR model/version/confidence and source region/page, false-positive/failure controls |
| Image object/person/vehicle detection | M2 | P09 | Pretrained permitted model/sample, bounded category/region, confidence; no named-person identity claim |
| CCTV/video observations | M2 | P10 | Frame/time locators, model/version/resource limits and malformed/unavailable-media behavior |
| Mobile logs | M2 | P11 | Supported exported device/auth/activity layout, source-located events; no physical acquisition |
| Transactions | M2 | P12 | Account/amount/currency/time/transaction source links, boundary failures; no live bank access |
| Common normalized observations/entities/events | M2 | P03/P03B/P03C/P05/P05B/P05C/P13/P13B | All adapter outputs retain raw/source time/location and source Evidence/observation IDs; candidate identity and uncertainty |
| Processing lifecycle/full dispatch/deeper existing processing | M2 | P04/P04B/P14/P14B/P14C/P14D/P15 | Idempotency/failure atomicity, latest and historical completed outputs; new-key deeper policy leaves old outputs/original unchanged |
| Versioned graph storage/projection recovery | M3 | G01D/A01/A01B/A02/A05 | Source UUID nodes, observation-backed edges; SQL pending→Neo4j case+run→verify→SQL completed pointer, hidden partials and safe rebuild |
| Cross-source relationship reasoning | M3 | A02/A07 | Real supported candidate links/common identifiers and unrelated/weak controls, same-case locators |
| Relevance and graph-connectivity factors | M3 | G02/A03/A03B | Deterministic reviewed functions, reasons/source support; connectivity not culpability |
| Temporal-proximity factor | M3 | G02/A03C | Actual supported timestamps/precision/timezone handling and absent-time policy |
| Independent corroboration factor/findings | M3 | G02/A08 | Independent-source definition; duplicates not independent; source-backed counterexamples |
| Source quality, extraction confidence/count and uncertainty | M3 with M2 | G02/A09/P14/A08/A10; U13B | Distinct extraction/source/association measures, counts/confidence used only per policy, unknown disclosed |
| Potential conflicts and conflict-aware priority | M3 | A10/A10B/A17/A19; U12A | Overlap/location uncertainty, contrary sources and actual factor/rank effect; no source falsely declared invalid |
| Evidence gaps and gap-relevant priority | M3 | A11/A11B/A17/A19; U12B | Bounded insufficient information, candidate available evidence, actual score impact; no absence-as-proof |
| Clusters and cluster prioritization | M3 | A12/A12B; U12C | Deterministic Evidence/entity membership and explained scored-evidence review order |
| Anomaly detection and triage feedback | M3 | A13/A13B/A17/A19; U12D | Tested selected deterministic/rule/statistical or approved pretrained detector, false positives and existing-factor policy mapping; abnormal not guilt |
| Alternative hypothesis comparison | M3 | A14; U12E | Both supporting/contradictory evidence and missing_information, human review and uncertainty |
| Explainable initial scores and analysis/history | M3 | A04/A05/A05B/A06/A15 | Factor sum/bands/ties/version and source locator trace; frozen snapshot/idempotency/trigger and coherent pinned reads; no fabricated missing factors |
| Adaptive new-upload AND detector/deeper-existing-evidence loop | M3 with M2 | A07/A17/A18/A19/P15; I02/I07/I07B | Actual justified earlier rank changes after new discovery/detector feedback/reprocess; new snapshots, immutable old results and same original hash |
| Faithful findings/triage/model explanations | M3 | A15/I08 | Reasons correspond to contributing features; input-removal counterfactual; feature importance/SHAP where valid for selected models, not obligatory inapplicable output |
| Full retrieval context and grounded LLM RAG | M3 retrieval/M4 generation | A16 tracer then A16B/U10B/U10C/U11B/G03/I05C | Graph/entities/events/triage/findings/metadata retrieval, actual approved generation, verified claim locators, unsupported fallback and private prompt/output provenance |
| Case/evidence overview and commands/status | M4 | U01/U02/U02B/U03/U04/U05/U05B/U05C/U05D/U13 | Real API create/upload/download/start/poll; all-page counts/types/status, not invented summary endpoint |
| Priority/history/graph/finding/uncertainty/entity-event inspectors | M4 | U06/U06B/U07/U07B/U13B/U13C | Completed analysis_run_id pinned across all pages/views; observation-run history/source navigation, honest unknown/not-scored/error states |
| Conflicts/gaps/clusters/anomalies/hypotheses panels | M4 | U12A/U12B/U12C/U12D/U12E | Real same-run findings/observations and source links, missing/contradictory data, no fabricated success |
| Human review and manual priority override | M4 with M1 audit/M3 history | U08/U08B/U09/U09B/F08C | Accepted/rejected/needs_investigation plus required reason/actor/time and audit; automatic history unchanged |
| One accessible evidence-first React dashboard | M4 | G01B/all U rows; I09 | DESIGN.md shared styles, keyboard/focus/contrast/responsive behavior, safe untrusted text and API-only storage boundary; no Streamlit second dashboard |
| Synthetic/permitted datasets and actual research evaluation | All modules | I04/I05/I05B/I05C/I08 | Labeled extraction/link P/R/F1; top-k/precision@k/MRR/consistency/effort/reranks/weight sensitivity; detector misses/false positives; faithful explanations; final RAG grounding/citations with actual counts/versions |
| Full integration and clean reproducibility | All modules | I09/I09B after tracer I01–I03 | Every F/P/A/U row reachable and real producers exercised; pinned snapshots/recovery/privacy/security; tested pinned versions on clean Windows and CI |
| Comparative/threat/provenance/limitations report | Four contributors | I06 after full gates | Cited positioning, measured limitations/resource/privacy threats; no claimed invention of established techniques/certification/admissibility |

## Source technology choices and scope boundaries

Architecture baseline is **React + TypeScript**, **FastAPI/Python**, authoritative **SQLite** metadata/outputs/audit, **private original files**, and a derived versioned/rebuildable **Neo4j** graph. Source section 30 names Streamlit/SQL alternatives as possible technologies; the shared architecture selects React, not a second dashboard, and SQLite, not dual SQL stores. Neo4j is included through G01D/A01B, not quietly removed as optional. Pandas/NumPy, OCR, OpenCV/pretrained detection, NLP, scikit-learn/SHAP and retrieval embeddings/vector indexes are candidates where appropriate; select/pin/test required packages/models in their setup/adapter policy, not claim every package is installed or every named technique must be duplicated.

Full timeline reconstruction/chronological visualization is explicitly **future** (section 38). Initial timestamp normalization, temporal proximity and conflict/gap reasoning remain mandatory. Physical acquisition, disk imaging, live banking, custom large/LLM training and court-admissible production deployment are outside initial scope. Optional extra provider/model adapters such as Jev require separate privacy/evaluation decisions and do not replace core capability.

## Staged delivery and real completion

1. Common base/setup and targeted policy gates, then first network/GPS/message tracer with command UI and pinned reads.
2. All modality adapters/common outputs, complete detector/factor assembly and feedback on existing evidence including optional deeper processing.
3. Full dashboard/approved LLM RAG/private provenance.
4. Full-modality evaluation, all-feature integration, clean Windows/CI and final limitations report.

Stages are delivery order, not permission to remove unfinished features. C-03–C-06, assignments and tested package/setup choices remain dependent gates; ready review/setup/unaffected schema-derived work is not an agreed implementation baseline. App completion requires real producers and actual tests, not a valid schema or first tracer alone.
