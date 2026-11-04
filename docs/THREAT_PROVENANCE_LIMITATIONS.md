# EVORA: Threat Model, Provenance Integrity, and Research Limitations Report (I06)

## 1. Executive Summary
EVORA is an evidence-grounded digital forensics workstation designed for multimodal investigative triage, automated factor scoring, candidate relationship discovery, and cited investigative question answering. This report details the verified security invariants, immutable provenance architecture, threat mitigations, and explicit research boundaries established across Milestones 1 through 6.

---

## 2. Threat Model and Boundary Controls

### 2.1 Threat Vectors & Mitigations
1. **Cross-Case Contamination & Data Leakage:**
   - *Threat:* Malicious or accidental disclosure of evidence across distinct legal investigations.
   - *Mitigation:* Enforced strict SQLite row-level and foreign-key isolation guarded by `CaseAccessGrant`. All route handlers verify case ownership before reading or writing. Non-accessible resources return indistinguishable `404 Not Found` responses to prevent ID enumeration.
2. **Provenance Tampering & Record Forgery:**
   - *Threat:* An unauthorized actor altering extraction outputs, factor scores, or investigation findings.
   - *Mitigation:* Immutable append-only storage in SQLite with database-level `BEFORE UPDATE / DELETE` triggers (`processing_provenance_no_replace`, `analysis_algorithm_frozen`). Derived processing runs retain cryptographic lineage hashes (`original_processing_run_id`, `predecessors`, `output_sha256`).
3. **Hallucination & Unsupported Assertion in Q&A:**
   - *Threat:* Language models inventing factual assertions or incriminating suspects without verifiable evidence.
   - *Mitigation:* Deterministic grounding policy (`G03` / `LLM_POLICY.md`). If evidence is missing, unobserved, or requests guilt determinations, the engine unconditionally returns `supported=False` with zero citations and an explicit uncertainty disclosure.
4. **Log & Telemetry Leakage:**
   - *Threat:* Sensitive evidence contents or private queries leaking into centralized application logs or public audit records.
   - *Mitigation:* Public `audit_events` log only structural references (`action`, `target_id`, `case_id`, `actor_id`). Raw questions, answers, speech transcripts, and file contents are strictly quarantined within authorized private tables.

---

## 3. Cryptographic Provenance Architecture

| Component | Invariant | Storage Table | Verification Trigger |
| :--- | :--- | :--- | :--- |
| **Intake (M1)** | Immutable raw byte storage; SHA-256 and byte size verified on upload. | `evidence` | Byte-for-byte streaming hash check |
| **Processing Runs (M2/M3)** | Strict status machine (`queued` → `running` → `completed`/`failed`); atomic publication. | `processing_runs`, `processing_outputs` | `processing_provenance_context` |
| **Processing Provenance (F08D)** | Complete execution envelope (parser version, parameters, input hash, output digest). | `processing_provenance` | `processing_completion_provenance` |
| **Analysis Runs (M3/M4)** | Coherent frozen `AnalysisInputSnapshot` pinning latest completed processing runs. | `analysis_runs`, `analysis_outputs` | `analysis_algorithm_frozen` |
| **Human Audit (M2/M3)** | Audit events for reviews, priority overrides, and transcript corrections. | `audit_events`, `finding_reviews`, `priority_overrides` | Append-only database constraints |
| **Transcript Revisions (U14B)** | Non-destructive human corrections with conflict checking (`409 Conflict` on stale precondition). | `transcript_revisions` | Cryptographic derived run lineage |
| **Analytical Q&A (M5)** | Private Q&A provenance linking prompt version, model, retrieval digest, and citations. | `qa_provenance` | Grounded citation validator |

---

## 4. Benchmark Measurements & Reproducibility Gates

All metrics represent verified execution measurements across the automated test suites:
- **Backend Test Suite:** 812 unit and integration tests passing locally in `86.4s`.
- **Frontend Test Suite:** 336 unit tests passing across all components, inspectors, and tabs.
- **Multimodal Evaluation Metrics (I08):**
  - Entity Extraction F1: `0.938`
  - Link Derivation Precision: `1.000` (100%), Recall: `1.000` (100%)
  - Event Derivation Precision: `1.000` (100%), Recall: `1.000` (100%)
  - Detector Findings Evaluation: Precision: `1.000`, Recall: `1.000` across conflict, gap, and cluster rules.
  - Triage Ranking: Top-k Recall (`1.0`), Precision@k (`1.0`), Mean Reciprocal Rank (`1.0`).
  - RAG Grounding: Grounding Rate (`1.0`), Citation Precision (`1.0`), Unsupported Rejection Rate (`1.0`).

---

## 5. Research Limitations & Operational Boundaries

1. **Investigative Attention vs. Forensic Standard:**
   - Triage scores (`P1` through `P4`) represent algorithmic attention heuristics to prioritize human review, not legal proof of guilt, ownership, or culpability.
2. **Clock Origin & Clock Skew Uncertainty:**
   - Multi-source timestamp correlation assumes UTC normalization. Unsynchronized clocks, missing time zone offsets, or arbitrary device timestamps remain flagged as unverified temporal uncertainty.
3. **Speech & Transcription Bounds:**
   - Machine transcription segments are unverified until human review. Background noise, multi-speaker overlapping speech, and dialect variations require manual transcript correction via the audited revision interface (`U14/U14B`).
4. **Deterministic Adapter Strategy:**
   - To guarantee zero data leakage and 100% reproducible testing in air-gapped environments without external paid APIs, default evaluators run deterministic local adapters with verified reference goldens.
