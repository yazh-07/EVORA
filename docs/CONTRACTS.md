# EVORA technical decision checklist — local draft

**Do not implement from this checklist alone.** `specs/openapi.yaml` is a local draft HTTP contract; `docs/INTEGRATION.md` describes proposed behavior and a synthetic first-stage tracer. `docs/CONTRACT_REVIEW.md` gives technical recommendations to resolve across the affected modules—not a new leadership title or approval process. The full proposed initial feature scope is already the goal and is built in stages. Record choices needed by the next tickets in the single versioned spec/policy, publish a common base, and let all agents derive their interfaces from it. Later-format details are resolved when their tickets are reached, not removed. `docs/ROADMAP.md` tracks status.

## Shared record goals (not wire fields)

The bullets below describe design intent from the proposal. They are **not an alternate field list**. Some goals (e.g. case status, verified entity identity, detailed chain of custody) are not modeled in the v1 draft. Agents must use only fields in `specs/openapi.yaml` and submit a reviewed schema change when a goal needs more data. In particular, an evidence hash plus audit trail is useful traceability, **not** full forensic chain-of-custody certification.

- **Case:** stable ID, access scope, status, created/updated timestamps.
- **Evidence:** stable ID, case ID, type, original filename/source, acquisition metadata, immutable storage reference, size, SHA-256, original timestamps, processing status.
- **Entity:** stable identity **within a case**; type, original identifiers, normalized identifiers, candidate-match status and confidence. Do not conflate a face/object detection with a named person.
- **Event / Observation:** type, source Evidence ID, source location (page/offset/frame/row), original value/time/zone, normalized value/time/zone, location where available, extraction confidence, model/parser version and processing provenance.
- **Relationship / Finding:** case ID, subject/predicate/object or typed finding, supporting and contradictory Evidence IDs, basis/rule, confidence or uncertainty, review state.
- **TriageResult:** case/evidence ID, run ID/version, trigger, scored factor values and weights, missing-factor handling, score/priority band, supporting Evidence IDs and human-readable rationale. Keep previous runs; never overwrite the history.
- **ReviewDecision / AuditEvent:** actor, time, case, target, action, reason, previous/new state. Manual priority overrides must remain distinguishable from automated scores.
- **Answer:** case ID, question, each factual claim mapped to same-case Evidence ID and source locator (optional observation ID), response, model/template version if generative, and supported/unsupported status. Refuse or qualify unsupported statements.

## Decisions needed before parallel implementation

- [x] FastAPI/SQLite/React selected in `docs/INTEGRATION.md`. [ ] Verify Windows setup and pin tested package versions.
- [ ] Review UUIDs, normalization/time zones, versioning, coordinate systems, deduplication and the wire schemas in `specs/openapi.yaml`.
- [x] Three initial CSV layouts selected in `fixtures/synthetic-case/` as the first tracer, **not the whole build**. [ ] M2 and affected modules to define each later format, limits, failure behavior and Windows-compatible model before its implementation ticket.
- [ ] Review triage prerequisites, weights, priority bands and trigger semantics in `docs/INTEGRATION.md`. M3 must publish precise factor functions and missing-factor behavior before scoring code is merged.
- [ ] Define independent-source/corroboration rules; distinguish weak matches, temporal uncertainty and contradictions.
- [ ] M1 and affected modules to settle API routes/status/errors and first-ticket job lifecycle in `specs/openapi.yaml`; choose a bearer identity provider, case permissions, local test-auth strategy, upload size limits and file streaming policy before dependent tickets.
- [ ] Decide whether LLM/RAG runs locally or remotely; protect real evidence and document cost/credential handling. The synthetic tracer must work without paid external services. Approve claim-level citation behavior and tests before implementing Q&A.
- [ ] Record one person for each module; one of those four coordinates integration and shared-file changes alongside their module work.
- [ ] Review the synthetic CSV inputs and the behavioral assertions in `docs/INTEGRATION.md`; after M2/M3 choose normalization and scoring rules, publish precise expected observations and score/ranking changes as golden fixtures.

As each choice is resolved, link its **versioned spec/policy and passing contract tests**. Examples in the proposal are not forensic standards. The published shared spec is the authoritative API for coding agents; remaining choices are handled as their tasks arise.
