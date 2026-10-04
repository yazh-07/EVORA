# EVORA pre-implementation review for the four-person team

## Verdict

**Ready to discuss and assign modules; not yet a shared implementation baseline.** Four people each work on one of M1–M4; one of those four coordinates integration while working on their module. No personal names or leadership titles are required. The full proposed feature scope is planned in stages. The network/GPS/message CSVs are an initial integration tracer, not the completed product.

This repository currently contains planning documents, a **draft** OpenAPI contract, synthetic fixtures and contract-lint CI. It does **not** contain the FastAPI backend, React frontend, tested scoring, a Windows installation or a running end-to-end system. The local coordination branch has not been committed/pushed; remote `main` remains at its initial README-only commit. Do not give coding agents an unpublished local file as if it were a shared commit.

## Checks actually performed

- Compared the feature map against the proposal's 40-section outline: intake/integrity, multimodal processing, entities/events, graph, adaptive triage, conflicts/gaps/clusters/anomalies, uncertainty/explanation, grounded Q&A, human review, audit and evaluation are represented. Complete timeline reconstruction is explicitly future work.
- Counted **25 unique OpenAPI operations** and **90 unique task IDs**; checked task references for missing IDs and dependency cycles (none found). The common G00–G03 setup entries precede affected tickets.
- Ran Redocly 2.57.0 lint and bundle on `specs/openapi.yaml`, and generated TypeScript declarations with openapi-typescript 7.10.1. All succeeded. Lint reported one non-blocking `info-license` warning; no repository license was invented.
- Parsed all three synthetic CSV files: network has `D-7` and `D-9`, GPS has `D-8`, and the later message mentions `D-7` and `D-8`. This supports a candidate link **only after** the message arrives; it does not prove identity, guilt or a numerical rerank without a scoring policy and executed tests.
- Checked Markdown local links, trailing whitespace, Git diff whitespace and common stale team-title labels. No failures found. Performed a basic plaintext credential-pattern scan of the reviewed coordination files; no match found. This is not a full security audit.
- Traced the six-step synthetic runbook to bounded tickets: intake/processing/graph/triage (`I01`), later-message rerank (`I02`), review/override (`I02B`), and grounded/unsupported Q&A (`I02C`), followed by Windows/CI (`I03`). Their real software tests have **not** run because the app does not exist yet.

## Decisions before dependent coding tickets

See [`COMMUNICATION.md`](COMMUNICATION.md) for exact ticket/module impact and verification. Its initial entries cover: **C-01** immutable analysis-input snapshot; **C-02** validation status/body and missing error responses; **C-03** identity, token and case-access policy; **C-04** first-format limits/parse failures; **C-05** scoring functions, missing-factor behavior and a measured rerank fixture; **C-06** Q&A provider/privacy/fallback. Resolve only the choices needed by the next tickets; later-format details can wait for their tickets. Record wire decisions in `specs/openapi.yaml`, policy in the relevant docs, and prove changes with tests.

## Communication rule

A Markdown communication file is a good **issue/handoff channel**, not an alternative contract. An agent reports the exact missing parameter, operation/schema, affected modules, fixture and failing test. Affected module contributors settle the interface, update the versioned OpenAPI spec and relevant producer/consumer/tests, then a bounded corrective ticket fixes existing code if needed. Another agent must not silently reimplement a whole module from a note in that file.

## Share/implementation gate

1. Record one person against each of M1–M4; the person coordinating integration remains one of those four. No module for that person has been assumed in these documents.
2. Settle G00 choices needed by first coding tickets, review the common draft contract across affected modules, and publish **one authorized Git commit** containing the agreed docs/spec/fixtures. This is synchronization, not a four-person approval ceremony.
3. Have agents branch from that exact commit for **one small ticket at a time**. Check spec-derived types, producer/consumer integration, case isolation, synthetic fixture outputs and negative tests in PRs. Windows and full end-to-end claims require real execution later.

**Sharing note:** These documents are currently only on the local `docs/coordination-foundation` branch. A repository link to remote `main` will not show them until publication is explicitly authorized and completed. No commit, push or merge was performed in this review.
