# EVORA proposal-to-task traceability

Source: [`PROPOSAL.md`](PROPOSAL.md), preserving the entire original proposal wording with trailing whitespace removed only. All 40 numbered sections appear exactly once below. The full **initial** proposal is fixed build scope; stage sequencing is not scope reduction. Source technology suggestions/diagram order are preserved in the source but clarified by [architecture](ARCHITECTURE.md), [contract policy](CONTRACTS.md), [full feature map](FEATURE_SCOPE.md) and [DESIGN.md](../DESIGN.md).

Concrete task IDs refer to [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md); its Checkpoint column links every task to the canonical [ROADMAP.md](ROADMAP.md) phase ledger. This mapping preserves proposal coverage; it is not a competing phase schedule. Acceptance below describes future required proof, not measured outcomes or implemented features. I09/I09B close over every F/P/A/U task; I06 follows those full-scope gates. C-03–C-06, assignments and tested package/Windows setup remain targeted gates.

| Section | Proposal heading | Concrete tasks | Acceptance/proof | Initial vs future/context |
|---|---|---|---|---|
| 1 | Introduction | G00, I09, I06 | Demonstrate integrated multimodal adaptive investigation support with traceability/human control; state no guilt/certification claim | Initial objective/context |
| 2 | Problem Statement | I04, I05, I08, I06 | Measure cross-source/priority benefit against labeled cases and report manual effort/false associations/limitations | Initial research problem/context |
| 3 | Proposed Solution | P05C, A17, A18, A19, U10C, I09 | Common entities/events feed real graph/detectors/factors and feedback plus grounded generation | Initial |
| 4 | Evidence Acquisition and Intake | F01, F03, F04, U02B, U03, U13 | Case/upload stable Evidence IDs, source/type/metadata and all-page processing overview | Initial |
| 5 | Evidence Integrity and Provenance | F05, F06, P14, F08D, F08E | Original byte/hash invariance; private input/output/model/parser/parameters/time and Q&A provenance | Initial |
| 6 | Multimodal Evidence Processing | P01, P02, P06, P07, P08, P09, P10, P11, P12, P14D, I08 | Real supported adapters for all named modalities with locators/uncertainty and malformed controls | Initial |
| 7 | Entity and Event Extraction | P03B, P03C, P13, P13B, P05C, U13C | Candidate entities/events cite original Evidence/observations and tested kinds/time/participants | Initial |
| 8 | Common Evidence Representation | P03, P05C, P14, G02 | Raw and normalized identifiers/time/location/confidence/source representation interoperates across adapters | Initial |
| 9 | Forensic Knowledge Graph | G01D, A01, A01B, A02, A05B, U07 | Versioned Neo4j graph source UUIDs and observation-backed relationships; verified SQL publication/rebuild | Initial |
| 10 | Cross-Source Relationship Analysis | A02, A07, A08, A03C, U07B, I04 | Detect supported cross-source candidate links with negative controls, source locators and temporal uncertainty | Initial |
| 11 | Adaptive Evidence Triage System | G02, A03, A03B, A03C, A08, A09, A10B, A11B, A17 | All reviewed factors, confidence/count/quality policy and explained priorities actually assembled | Initial |
| 12 | Triage Scoring | G02, A04, A17, I05 | Version exact experimental functions/weights/bands/ties/absent factors and sum/bound tests; measured weight sensitivity | Initial; source numbers examples, not standards |
| 13 | Evidence Relevance Analysis | G02, A03, A15, U06B | Deterministic supported relevance to candidate case entities with source-backed reason/missing controls | Initial |
| 14 | Evidence Connectivity Analysis | G02, A03B, A01B, U06B | Meaningful graph connectivity from supported relationships, no culpability inference | Initial |
| 15 | Evidence Corroboration Analysis | G02, A08, A17, U13B | Independent-source corroboration contributes actual factor; same-source duplicates not counted as independent | Initial |
| 16 | Evidence Conflict Analysis | A10, A10B, A17, A19, U12A, I07 | Potential conflict evidence/time-zone/clock/location uncertainty and real existing-evidence priority feedback | Initial |
| 17 | Evidence Gap Detection | A11, A11B, A17, A19, P15, U12B, I07B | Bounded gaps, available evidence suggestions and actual gap/deeper-processing rank effect, not non-occurrence | Initial; not full timeline reconstruction |
| 18 | Evidence Cluster Prioritization | A12, A12B, U12C, I09 | Deterministic source-backed cluster Evidence/entity membership and explained review order | Initial |
| 19 | Adaptive Re-Triage | A07, A17, A18, A19, P15, I02, I07, I07B | New discoveries/detectors/deeper existing-file processing alter earlier ranks; preserve original and historical outputs | Initial core feedback loop |
| 20 | "Why Was This Evidence Prioritized?" Explanation | A15, A06, U06B, I08 | Displayed priority reasons reflect actual factors/weights/source locators/previous results and uncertainty | Initial |
| 21 | Anomaly Detection | A13, A13B, A17, A19, U12D, I05B, I07 | Selected detector measured with false positives; anomalies feed reviewed existing factor without guilt/new enum | Initial; named algorithms candidates, not mandatory duplicates |
| 22 | Evidence Reliability and Uncertainty | G02, P14, A09, A08, A10, U13B | Source quality, extraction confidence, corroboration and contrary support remain distinct and unknown disclosed | Initial |
| 23 | Alternative Hypothesis Analysis | A14, U12E, U08B, I09 | Both hypotheses show support, contradiction, missing_information and need for verification; no unsupported narrative | Initial |
| 24 | Explainable Artificial Intelligence | A15, I08, U06B, U07B | Faithful rule/factor/model reasons and input-removal counterfactual; feature importance/SHAP when valid for chosen model | Initial explainability; technique applicability contextual |
| 25 | Evidence-Grounded RAG | G03, A16B, U10B, U10C, U11B, F08E, I05C | Retrieve full case graph/entity/event/triage/finding/metadata context, approved LLM, verify every claim/citation and private provenance | Initial full RAG; deterministic tracer not replacement |
| 26 | Evidence-Based Natural-Language Investigation | A16B, U10B, U10C, U11B, I05C | Questions on entities/devices/accounts/relationships/priority/detectors return grounded source locators or honest unsupported result | Initial |
| 27 | Investigator Dashboard | U13, U05C, U05D, U06B, U07B, U12A, U12B, U12C, U12D, U12E, U13B, U13C, U11B, I09 | All dashboard sections real API data, all-page overview, pinned completed runs, source navigation and uncertainty | Initial; React/DESIGN implementation |
| 28 | Human Verification | U08, U08B, U09, U09B, F08C, I02B | Accepted/rejected/needs_investigation reviews and reasoned overrides audited; automatic history unchanged | Initial human control |
| 29 | Audit and Provenance Management | F06, F07, F08, F08B, F08C, F08D, F08E, P14, U10C | Intake/extraction/normalization/graph/detectors/triage/explanations/RAG/decisions linked to private versioned provenance and safe public audit | Initial |
| 30 | Technology Requirements | G01, G01B, G01C, G01D, A01B, P14D, G03, I09B | Test/pin selected Python/model/Neo4j/React stack and private SQLite/file setup; no installation claim | Initial technology context; React replaces suggested Streamlit, SQLite selected |
| 31 | Dataset and Experimental Environment | I01, I04, I05, I05B, I05C, I08 | Synthetic/permitted labeled related/unrelated/noisy/conflicting/gap/weak/corroborating cases with known priorities, no real private data | Initial experimental dataset |
| 32 | Evaluation | I04, I05, I05B, I05C, I08, I09B, I06 | Actually executed extraction/link P/R/F1, ranking/top-k/MRR/effort/reranks, detector false positives, explanation faithfulness and final RAG grounding | Initial evaluation |
| 33 | Comparison with Existing Systems | I06 | Cited accurate competitor comparison with actual EVORA results and limits; no replacement/first-technique claim | Context/research reporting, not external-platform integration |
| 34 | Comparative Uniqueness of EVORA | A17, A18, A19, I07, I07B, I05, I06 | Demonstrate graph/gap/conflict/anomaly-driven feedback and human-verifiable explanation, compare measured value not asserted uniqueness | Initial research identity/context |
| 35 | Proposed Research Contribution | I08, I09, I09B, I06 | Unified heterogeneous/adaptive workflow tested and evaluated with source traceability/human control | Initial contribution to evaluate, not proven outcome |
| 36 | Uniqueness of the Proposed System | A17, A18, A19, A15, F08D, F08E, I06 | Auditable adaptive architectural method backed by actual tests; established component technologies acknowledged | Initial methodology/context, no first-of-kind claim |
| 37 | Research Scope | P14D, A17, U10C, I08, I09, I09B, I06 | Every core initial feature built/tested, pretrained permitted models and reproducible synthetic/public data; explicit exclusions retained | Initial full scope; acquisition/disk/live banks/large training/admissible production outside |
| 38 | Future Enhancement: Timeline Reconstruction | P03, A03C, A10, A11, U13C | Preserve basic time/temporal reasoning now; do not claim chronological reconstruction/timeline visualizer delivered | Future full timeline reconstruction; initial prerequisites only |
| 39 | Final Working of EVORA | A05, A17, P15, A18, A19, U10C, U08B, I09 | Full intake→processing→graph/factors→triage→feedback→grounded interaction→human verification/private audit; graph-dependent score follows graph | Initial complete working; source diagram preserved but ordering clarified |
| 40 | Conclusion | I08, I09, I09B, I06 | Full adaptive evidence-grounded auditable prototype with measured limits and source trace, not autonomous guilt judgment | Initial conclusion/context; timeline future |

## Explicit design interpretations, not source edits

- Section 30's suggested Streamlit dashboard is superseded by one React + TypeScript dashboard; FastAPI/Python, SQLite authoritative metadata/outputs/audit, private originals and Neo4j derived graph are the selected architecture. Package/model techniques are tested selections, not invented installations or a mandate to duplicate every suggested algorithm.
- Sections 19/39 have conceptual ordering: actual initial graph-dependent triage follows supporting extraction/graph construction. G02 handles unavailable factors and not-scored items; A17 adds all detector/factor stages explicitly. No fabricated cold-start score.
- Section 25's generative RAG is mandatory full initial scope; deterministic U10/U11 is only the first tracer. Full context/provider/claim verification/private provenance/UI/evaluation remain explicit tasks.
- Section 38 alone marks full timeline reconstruction/visualization future. Timestamp normalization, temporal factor and conflict/gap reasoning elsewhere remain initial scope.
- Sections 33–36 are comparative research/context, not promises that EVORA is first-of-kind or integrates competitor products. Sections 37/40 preserve prototype limits and human judgment.
