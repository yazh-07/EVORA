# EVORA scope/contract verification and implementation readiness

## Current state

**Implementation has not started.** This repository contains planning, contracts, synthetic inputs and validation tooling, not a running FastAPI/React application or executed ASR/scoring/RAG system. All product tasks/checkpoints remain Backlog. A standalone visual prototype outside this Git tree is not product implementation.

Prepublication verification covered the transcription and simplified Codex-prompt revision on `docs/coordination-foundation`, originally based on `d36ac5cd63b5dcf431af6fca34411653a6ffe50f`. Before publication the branch fast-forwarded to `815b2eca5b0b5a77af93d4db69e12793bd48144b`, whose tree is identical; collaborator history was preserved. The inspected local main tree contains only README. Publication is tracked by the exact Git commit/remote ref and its CI run, not by a self-referential commit ID here. No main merge or Windows application run is claimed. G00 must record the reviewed common base before implementation branches depend on it.

## Approved scope addition

The full original proposal remains required and is preserved verbatim. The user subsequently approved local audio/video speech transcription as **additional initial scope**, not an original proposal requirement:

- P16/P16B in 3B: local speech extraction, original-media timestamped segments and candidate entity/event extraction.
- U14/U14B/U14C in 3C: authorized playback, all-page local source-transcript search and audited append-only corrections/history.
- Corrections atomically publish a new complete processing materialization with rebuilt candidates and safe audit linkage. Machine text, original bytes/hash, prior runs and frozen analysis never mutate. New-key analysis selects corrected inputs; original-key replay retains old inputs.
- Video visuals/speech coexist in one selected complete output. Derivatives/revisions are not independent corroboration; media offsets do not imply capture UTC or the time a spoken event occurred.
- Silence/no-audio differs from decoder/model failure; unclear speech is unverified. Speaker identification, voice matching, emotion inference, diarization and translation are excluded.

[CONTRACTS.md](CONTRACTS.md) owns policy and [OpenAPI](../specs/openapi.yaml) the wire contract. [FEATURE_SCOPE.md](FEATURE_SCOPE.md), [ROADMAP.md](ROADMAP.md), [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) and [INTEGRATION.md](INTEGRATION.md) define acceptance, exact membership, dependencies and real execution proof. [PROPOSAL_TRACEABILITY.md](PROPOSAL_TRACEABILITY.md) distinguishes the addition from source requirements.

## Preservation checks actually executed

- All **121 pre-change tasks** and all prior dependency edges remain. Exactly five tasks were added: P16, P16B, U14, U14B, U14C. **126 unique tasks** occur exactly once across **18 checkpoints**, with no dependency cycle or later-checkpoint prerequisite.
- All original feature identities remain; two addition rows bring the inventory to **39**. Roadmap/catalog/runbook and derived feature checkpoint coverage are checked together.
- All **40 proposal sections** and **40 source mappings** remain. `docs/PROPOSAL.md` and the three original CSV fixtures are byte-for-byte unchanged from pre-change HEAD.
- Draft **0.3.0** preserves the original 25 operations and adds only `appendTranscriptRevision` and `listTranscriptRevisions`: **27 total**. No search/playback endpoint or start-command request body was added.
- React/TypeScript, FastAPI/Python, authoritative SQLite/private originals and derived Neo4j topology is unchanged. Full chronological timeline reconstruction remains future.

## Local validation actually executed

The run used **Python 3.14.7 / Node 26.7.0**, with **jsonschema 4.25.1 / Ruff 0.12.12** pinned in a scratch virtual environment. No product models were installed. This is not a fresh Python 3.12 / Node 22 CI or Windows run.

- Redocly **2.57.0** lint and fresh bundle: passed.
- openapi-typescript **7.10.1** generation and TypeScript **5.9.3** `--noEmit --strict` declaration compilation: passed.
- Coordination verifier: passed contract/task/DAG/phase/runbook/feature/source/link/fixture checks and transcription/full-scope handoffs.
- **122 unittest checks passed**, including synthetic schema examples, CLI mutations and new speech/correction planning regressions. New handoff tests were exercised failing before verifier implementation. An operation-name mismatch was detected and fixed before the combined pass.
- Ruff over `scripts`: passed. DESIGN **0.4.0** lint: zero errors/warnings. `git diff --check`: passed.

Existing nonblocking warning: OpenAPI `info.license` is missing; no project license is invented. These are artifact checks, not model accuracy, application authorization/transaction atomicity, playback, browser/accessibility or forensic certification. Earlier phase-plan results are historical in Git and do not certify this revised draft.

## Remaining gates

- C-03 identity/token/membership/client handling before protected tasks, including playback/corrections.
- C-04 tested format/limits/failure policy before each adapter. P16/P16B/U14 need local model/runtime/version/license, languages/codecs, track/offset policy, duration/byte/compute limits, private derivative cleanup and browser compatibility. Whisper is a candidate, not a selected/installed model.
- C-05 precise scoring/independence/confidence/goldens; do not double-count audio/video/transcripts.
- Approved local retrieval/grounding/privacy before deterministic Q&A; C-06/G03 before final generation. Local speech does not depend on the final LLM provider; no cloud speech transfer is authorized.
- G00/task handoffs need exact shared commit, assignee/paths and dependency versions. Confirmed module owners remain in ROADMAP; ownership is not completion.
- G01/G01B/G01D pin real product package/database versions. G01C/I03/I09B prove Windows/CI scopes. I03B proves real media/correction behavior; I08 measures speech errors/alignment and other research metrics; I09/I09B/I06 retain full integration/reproducibility/report closure.

Use the earliest dependency-ready bounded task and [agent assignment card](AGENT_TASKS.md). Disclosed schema-derived doubles permit independent work, not integrated completion. Rerun every completed checkpoint regression before an authorized main promotion; verify the merged commit/CI/smoke results afterward. Artifact checks cannot close product milestones.
