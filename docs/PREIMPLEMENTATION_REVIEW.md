# EVORA scope/contract verification and implementation readiness

## Current state

**Product implementation has not started.** This repository contains planning, contracts, synthetic inputs and validation tooling, not a running FastAPI/React application or executed ASR/scoring/RAG system. G00 and Checkpoint 0 are In Progress; G01/G01B/G01C and other product tasks/checkpoints remain Backlog. A standalone visual prototype outside this Git tree is not product implementation.

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

## Historical prepublication validation

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
- G00's local record below supplies its exact shared commit, assignee/paths and validation versions; review/publication of these edits remains pending. Later task handoffs still need their own scoped assignments. Confirmed module owners remain in ROADMAP; ownership is not completion.
- G01/G01B/G01D pin real product package/database versions. G01C/I03/I09B prove Windows/CI scopes. I03B proves real media/correction behavior; I08 measures speech errors/alignment and other research metrics; I09/I09B/I06 retain full integration/reproducibility/report closure.

Use the earliest dependency-ready bounded task and [agent assignment card](AGENT_TASKS.md). Disclosed schema-derived doubles permit independent work, not integrated completion. Rerun every completed checkpoint regression before an authorized main promotion; verify the merged commit/CI/smoke results afterward. Artifact checks cannot close product milestones.

## G00 verification — 2026-10-18

Task **G00 / Checkpoint 0**, explicitly assigned to **whale2186** for shared integration coordination on `feat/g00-coordination-base`. Exact reviewed common contract/base: **114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb** (`origin/docs/coordination-foundation`). Starting `git status --short --branch` was clean; `git rev-parse HEAD` and `git show-ref --verify refs/remotes/origin/docs/coordination-foundation` both returned this SHA. This reads back the available local remote-tracking ref, not a fresh network fetch or remote CI result. Local main contains only README and was not used as the task base. Dependencies: none; the base's actual artifacts are the inputs. [Assignment/allowed paths](AGENT_TASKS.md#g00-assignment--2026-10-18) and [live state](ROADMAP.md#g00-live-record--2026-10-18) remain **In Progress**, pending review/publication.

### Current targeted gates

| Gate | Current status and exact producer/consumer impact | Resolve before |
|---|---|---|
| C-03 | **Open.** M1 F00/F01 must choose identity issuance, expiry/revocation and case membership; M4 U01 must handle those tokens/errors safely. Tests must cover two actors/cases, invalid/expired identity and foreign/missing resources without existence leaks. BearerAuth alone does not choose the mechanism. | Protected routes/client integration in 1A, including later source playback/corrections |
| C-04 | **Open.** M1 F03 intake and M2 P04/P14B need compatible byte/row/BOM/column/content validation and reject-before-run versus failed-accepted-run policy; M4 U03/U05 consume the corresponding errors/states. Later M2 adapters must pin layouts/models/runtime/resources/private boundaries for M3 source consumption and M4 source/playback views, including local speech offsets/codecs/silence/failure controls. | First CSV intake/processing in 1A/1B; later decisions before their own adapters in 3A/3B |
| C-05 | **Open.** M3 G02 must version functions, absent inputs, weights/bands/ties, confidence/count/source-quality/independence treatment and positive/counterexample goldens. M2 lineage must support those rules; M4 must explain actual factors, without treating source derivatives as independent corroboration. Fixed listTriage pagination policy remains authoritative. | G02 and scoring/factor implementation in 1C, then later factor wiring |
| C-06 | **Open.** G03 must record provider/model/privacy/cost/credentials/prompt/verification/fallback policy for M3 retrieval, M4 generation/verification and M1 private provenance. Real approved-provider tests differ from no-paid CI adapters. | 5A/5B final RAG; does not block local speech or independently approved deterministic retrieval |

No future policy was selected for G00, no four-signoff ceremony is required, and no blanket all-clear is claimed. Existing queue entries in COMMUNICATION retain the unresolved questions.

### Commands and observed results

Local runtime: **Linux, Node 22.23.3, npm 12.2.0, Python 3.14.8**. The default Python environment has jsonschema 4.26.0; it was not used for the passing suite. A scratch `/tmp/evora-g00-venv` with system site packages uses **jsonschema 4.25.1**, copied with its distribution metadata from the existing uv cache after pip installation failed DNS resolution. Package metadata and the imported module path were checked. This is an offline cache workaround, not clean installation or Python 3.12/Windows/CI proof.

All five requested npx invocations were attempted and exited **1**, failing registry DNS resolution with `EAI_AGAIN`; npm also could not write its default home log directory. An offline npx retry lacked registry metadata (`ENOTCACHED`). The TypeScript attempt used `npm_config_fetch_retries=0` and writable `/tmp` logs to avoid repeated network waits. No tool version or API change was made to bypass validation. Existing cached package manifests confirmed the exact requested versions, and direct Node CLI equivalents produced these results:

| Check | Observed result |
|---|---|
| Redocly 2.57.0 lint | **Pass, exit 0**; one existing `info-license` warning, no license invented |
| Redocly 2.57.0 bundle | **Pass, exit 0**; fresh `/tmp/evora-openapi.json` |
| openapi-typescript 7.10.1 generation | **Pass, exit 0**; fresh `/tmp/evora-api.d.ts` |
| TypeScript 5.9.3 `--noEmit` compilation | **Pass, exit 0** |
| `verify_coordination.py /tmp/evora-openapi.json` | **Pass, exit 0**; 27 operations, 126 tasks, 18 checkpoints, 39 capabilities, 40 proposal sections/mappings; fixture rows network=2, GPS=1, messages=1 |
| `unittest discover -s scripts -p 'test_*.py' -v` with bundle and jsonschema 4.25.1 | **Pass, exit 0; 122 tests**, including malformed contracts, missing 400/snapshot/source links, duplicate/cyclic/misordered tasks, case-shaped synthetic examples and transcription handoffs |
| DESIGN 0.4.0 lint | **Pass, exit 0**; zero errors, zero warnings, one token-summary info |

Edited-tree read-back: the coordination verifier passed again and the full suite returned **122 tests, OK, no skips**. The focused missing-400 negative also passed. `git diff --check` and the base-to-working-tree spec comparison exited 0; `git status`/diff showed only the four authorized documentation files on `feat/g00-coordination-base`. No file was staged, committed, pushed or merged.

Exact successful offline commands (package paths are this machine's pre-existing cache, not new repository dependencies):

```sh
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js lint specs/openapi.yaml
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js bundle specs/openapi.yaml --output /tmp/evora-openapi.json
node /home/whale2186/.npm/_npx/2ffac754ed3026da/node_modules/openapi-typescript/bin/cli.js specs/openapi.yaml -o /tmp/evora-api.d.ts
node /home/whale2186/.npm/_npx/a322a253dbd59f36/node_modules/typescript/bin/tsc --noEmit /tmp/evora-api.d.ts
/tmp/evora-g00-venv/bin/python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g00-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
node /home/whale2186/.npm/_npx/453056feeae89689/node_modules/@google/design.md/dist/index.js lint DESIGN.md
```

Only schema-derived synthetic fixtures and planning mutations were exercised. No FastAPI/React app, DB transaction, authorization enforcement, model, provider, browser or Windows behavior is verified. No previously completed checkpoint exists to regress. Canonical package-download/clean-environment checks remain subject to network availability; no remote CI result or new publication is claimed. G00's documentation is locally prepared; **Checkpoint 0 stays In Progress**, and **G01/G01B/G01C stay Backlog**. After G00 review/handoff acceptance, G01 and independent G01B are next dependency-ready scopes with explicit G/I assignee/paths still required; G01C needs both real skeletons. This session does not start another task.

### How you can test it

Run from the repository root. The canonical commands need registry access or populated package caches. Setup commands below are for a network-enabled environment; this session used the scratch cached environment described above.

- [ ] Read back the base: `git rev-parse HEAD` and `git rev-parse origin/docs/coordination-foundation`. In this uncommitted task checkout both should print `114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb`.
- [ ] Create an isolated checker: `python -m venv /tmp/evora-g00-review-venv`, then `. /tmp/evora-g00-review-venv/bin/activate` (POSIX), then `python -m pip install jsonschema==4.25.1`. Confirm `python -c 'import importlib.metadata as m; print(m.version("jsonschema"))'` prints `4.25.1`.
- [ ] `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml` — exit 0, one existing missing-license warning.
- [ ] `npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json` — exit 0, fresh JSON bundle.
- [ ] `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts` — exit 0, generated declaration file.
- [ ] `npx --yes --package typescript@5.9.3 tsc --noEmit /tmp/evora-api.d.ts` — exit 0, no type diagnostics.
- [ ] `python scripts/verify_coordination.py /tmp/evora-openapi.json` — exit 0 with the counts recorded above and artifact-only scope.
- [ ] `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py' -v` — 122 tests, `OK`, no skips.
- [ ] `npx --yes @google/design.md@0.4.0 lint DESIGN.md` — zero errors/warnings.
- [ ] Failure case: `PYTHONPATH=scripts EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest test_verify_coordination.ContractAuditTests.test_missing_error_response_is_rejected -v` — one test `OK`: removing required 400 from an in-memory contract copy raises the expected validation error. The source spec is never edited. This negative is also exercised by the full suite.
- [ ] `git diff --check` and `git diff --exit-code 114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb -- specs/openapi.yaml` — exit 0; `git diff --name-only` lists only the four authorized documentation paths. Checkpoint 0 must read In Progress and G01/G01B/G01C Backlog.

All artifact equivalents and the full negative suite were exercised locally. The canonical npx commands failed in this environment; the clean review-venv installation and remote/Windows runs are untested. Scratch artifacts remain under `/tmp`; no original evidence or repository-generated client was written.
