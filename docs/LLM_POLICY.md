# EVORA LLM RAG & Analytical Context Retrieval Policy (G03)

## 1. Scope and Authority
This document defines the governing boundary, privacy invariants, and citation verification rules for evidence-grounded question answering and Retrieval-Augmented Generation (RAG) across the EVORA workstation.

## 2. Privacy Boundary and Data Sovereignty
- **Default Offline Execution:** All analytical retrieval, embedding lookups, entity extraction, and deterministic grounding execute locally. No unencrypted evidence, raw bytes, or sensitive investigative queries leave the workstation boundary by default.
- **Approved Providers:** Any external generative inference must use explicitly approved, zero-data-retention enterprise endpoints with client-side credential controls. Real case evidence is never used for external model training.
- **Audit Masking:** Application logs and public `audit_events` record safe references (`action='askCaseQuestion'`, `target_id=<UUID>`), strictly redacting raw question strings, generated text, and source contents.

## 3. Retrieval Invariants (A16B)
- Retrieval is strictly scoped to the authorized case and the latest completed analysis run (`AnalysisInputSnapshot`).
- Multi-context retrieval aggregates:
  1. Source-located candidate observations (`row`, `chars`, `time`, `media` locators).
  2. Incident graph nodes and candidate edges.
  3. Labeled findings (`corroboration`, `conflict`, `gap`, `cluster`, `anomaly`, `hypothesis`).
  4. Pinned triage scores and contributing factor breakdowns.
- Cross-case leakage is structurally impossible: queries without same-case matches return `supported=False` with zero citations.

## 4. Citation Verification and Grounding (U10C)
- **Supported Answers:** If `supported=True`, every factual claim in the answer must carry at least one valid `AnswerCitation` linking to a verified same-case Evidence ID and exact `source_locator`.
- **Unsupported Inquiries:** If evidence is absent, contradictory, or requests subjective guilt/identity conclusions, the system falls back to `supported=False`, provides an honest uncertainty notice, and emits zero citations.
- **Provenance Linkage:** Complete retrieval snapshots, prompt templates, model versions, and verification results are persisted immutably in authorized private storage (`qa_provenance`).
