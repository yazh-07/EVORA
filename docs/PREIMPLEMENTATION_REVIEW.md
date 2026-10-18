# EVORA scope/contract verification and implementation readiness

## Current state

**G01C is locally implemented/verified and In Progress pending native Windows/hosted CI evidence and review.** The user accepted committed common base `328c103d0f0383c7b4979bd8199b4201408e2a68`, containing G00/G01/G01B. The tree includes real FastAPI/SQLite and React/TypeScript skeletons, with clean Linux dependency installs and combined regression checks recorded below. Checkpoint 0 remains In Progress until all four exit gates pass, including native Windows/CI execution. Domain tasks/checkpoints remain Backlog; no domain routes, ASR/scoring/RAG system or main merge is claimed. Earlier verification records retain their historical environment/results; the G01C record is current.

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
- The G01C handoff accepts exact committed G00/G01/G01B ancestry and records scoped assignee/paths. G01C edits await review and native Windows/hosted CI evidence. Later task handoffs still need their own assignments. Confirmed module owners remain in ROADMAP; ownership is not completion.
- G01/G01B package pins are now exercised together on Linux; G01D still needs Neo4j setup proof. G01C/I03/I09B prove their respective Windows/CI scopes. I03B proves real media/correction behavior; I08 measures speech errors/alignment and other research metrics; I09/I09B/I06 retain full integration/reproducibility/report closure.

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

## G01 verification — 2026-10-18

**G01 / Checkpoint 0 / whale2186 / shared integration coordination / In Progress**, locally verified and pending review/integration. Task branch **feat/g01-backend-skeleton**; exact common contract/base and dependency **G00 at 1721bfff9640263d2799434455cdb9c4f345ac35**. Starting `git status --short --branch` was clean; `git rev-parse HEAD origin/feat/g00-coordination-base` read back this SHA twice. The user explicitly selected this committed common base; no fresh network fetch, remote CI or main merge is claimed. Allowed paths and dependency handling are in the [G01 card](AGENT_TASKS.md#g01-assignment--2026-10-18).

### Implementation and actual boundaries

- `backend/app.py`: factory, environment/explicit SQLite file configuration, real connection check on lifespan startup and shared validation registration. No public health/docs/OpenAPI/domain routes and no application tables/migrations.
- `backend/database.py`: per-unit-of-work SQLite connections, foreign keys, commit/rollback and unconditional close. Tests read back actual persisted synthetic rows and verify failure/connection isolation; this is not F00 case-access verification.
- `backend/errors.py`: invalid path/query/header/body or malformed JSON produces **400**, exactly `{"code":"INVALID_INPUT","message":"Invalid request input."}`. No submitted input/exception dump is echoed or logged; response-validation errors remain 500. This uses the [documented FastAPI RequestValidationError override](https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions).
- Tests invoke the real FastAPI application through HTTPX async ASGI transport with explicit lifespan contexts and real temporary SQLite files. The `/_test/...` handlers are synthetic test-only validation probes; production apps have zero registered routes. Every invalid response is validated against `ApiError` from the actual shared bundle; no local replacement wire schema or application producer double is claimed. Missing bundle fails tests instead of skipping schema assertions.
- `requirements.txt` pins all **22** runtime/test dependency distributions; `backend/.python-version` pins **CPython 3.14.8**. Local SQLite is **3.54.0**, FastAPI **0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, Uvicorn **0.54.0**, HTTPX **0.28.1**, jsonschema **4.25.1**. Every pin matched observed distribution metadata. The backend README (`backend/README.md`) defines setup/run/configuration and the backend test command.

### Commands and observed results

Environment: Linux, Python **3.14.8**, Node **22.23.3**, npm **12.2.0**. `python -m venv --system-site-packages /tmp/evora-g01-venv` succeeded. Initial `/tmp/evora-g01-venv/bin/python -m pip install --disable-pip-version-check --retries 0 --timeout 8 jsonschema==4.25.1` failed with no matching distribution available from the index. Copied `jsonschema` and `jsonschema-4.25.1.dist-info` from the pre-existing cache `/home/whale2186/.cache/uv/archive-v0/Vs02wiBg28l1Fmlz` into that scratch environment. The full `pip install -r requirements.txt` then exited 0 with every pin already satisfied. This is a tested existing-package/cache environment, **not a clean index installation**.

| Check | Observed result |
|---|---|
| Backend suite below, also with `-W error::ResourceWarning` | **Pass, 14 tests, no skips**; startup/database success and failure, persistence/rollback/close/foreign keys, app isolation, absent routes, valid request, invalid body/path/query/header/JSON, schema shape/redaction and server-error separation |
| Uvicorn factory with `--lifespan on --no-access-log` | Real **startup complete and shutdown complete**; exit 3 when localhost binding was denied. A separate ephemeral socket bind returned `PermissionError`, errno 1 (`Operation not permitted`); no external HTTP listener claimed |
| Redocly 2.57.0 lint/bundle | **Pass**, fresh `/tmp/evora-openapi.json`; one pre-existing `info-license` warning |
| openapi-typescript 7.10.1 / TypeScript 5.9.3 `--noEmit --strict` | **Pass**, fresh `/tmp/evora-api.d.ts`; no repository client/type files written |
| Coordination verifier | **Pass**, 27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 source mappings |
| Coordination unittest suite with jsonschema 4.25.1 | **Pass, 122 tests, no skips**; full output `/tmp/evora-g01-coordination-tests.log` |
| Requested `npx --yes @google/design.md@0.4.0 lint DESIGN.md` | **Failed**, registry DNS `EAI_AGAIN`; writable logs and zero retries used |
| Cached exact DESIGN 0.4.0 CLI | **Pass**, zero errors/warnings |
| `git diff --check`; spec comparison against exact G00 base | **Pass**, unchanged `specs/openapi.yaml`; only allowed paths changed |

Initial synchronous Starlette TestClient startup stalled inside its cross-thread portal; a bounded reproduction timed out. The passing suite uses HTTPX async ASGI transport and explicit real lifespan startup/shutdown, avoiding that portal. An initial test-owned SQLite read-back connection produced a ResourceWarning; it was corrected with explicit closing, and the final warning-strict suite passed. No application failure is hidden by a skipped test.

Exact locally successful verification commands, from the repository root:

```sh
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js lint specs/openapi.yaml
node /home/whale2186/.npm/_npx/e8a7a01167a46cae/node_modules/@redocly/cli/bin/cli.js bundle specs/openapi.yaml --output /tmp/evora-openapi.json
node /home/whale2186/.npm/_npx/2ffac754ed3026da/node_modules/openapi-typescript/bin/cli.js specs/openapi.yaml -o /tmp/evora-api.d.ts
node /home/whale2186/.npm/_npx/a322a253dbd59f36/node_modules/typescript/bin/tsc --noEmit --strict /tmp/evora-api.d.ts
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
/tmp/evora-g01-venv/bin/python scripts/verify_coordination.py /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
node /home/whale2186/.npm/_npx/453056feeae89689/node_modules/@google/design.md/dist/index.js lint DESIGN.md
git diff --check
git diff --exit-code 1721bfff9640263d2799434455cdb9c4f345ac35 -- specs/openapi.yaml
```

The cached CLI paths above are machine-local tool locations; the canonical shared-workflow equivalents use `npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml`, `npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json`, `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts`, `npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-api.d.ts`, and `npx --yes @google/design.md@0.4.0 lint DESIGN.md`. Use an activated environment with the pinned requirements for both Python suites. No previously completed checkpoint exists to regress beyond these G00 artifact checks.

### How you can test it

The backend checklist in `backend/README.md` contains exact setup, run, success and malformed-JSON/database failure commands, expected results and cleanup. The backend command is `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s backend/tests -v` (**14 tests, OK**); coordination uses `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py' -v` (**122 tests, OK**). Run the verifier and shared workflow commands above, then `git diff --check` and the exact-base spec comparison. All local test/CLI equivalents were exercised; new package downloads, external HTTP listening, Windows, Python 3.12 application compatibility and remote CI remain unverified.

No unresolved policy blocks this G01 implementation. C-03–C-06 remain open only for their dependent domain rows. G01C must reconcile this tested Python baseline with the current Python 3.12 artifact-only workflow and prove clean Windows/CI skeleton setup; no changes outside G01 paths were made to preempt it. **G01 stays In Progress awaiting review/integration; Checkpoint 0 stays In Progress.** Next dependency-ready task is **G01B**, with an explicit assignee/path handoff; G01C depends on both skeletons. No stage, commit, push, merge, main smoke or another task is authorized or claimed.

## G01B verification — 2026-10-18

Task **G01B / Checkpoint 0**, explicitly assigned to **whale2186** for shared integration coordination on `feat/g01b-frontend-skeleton`. Exact reviewed common base: **e0257a6ad231105b93ae98a97f176ed233a25412** (`feat/g01-backend-skeleton`, which includes G00 at `1721bff`). Starting `git status` was clean; `git rev-parse HEAD` read back this SHA. Allowed paths: `frontend/`, `docs/ROADMAP.md`, `docs/AGENT_TASKS.md`, `docs/PREIMPLEMENTATION_REVIEW.md`.

### Implemented architecture and design adherence

- Created React + TypeScript frontend skeleton under `frontend/` using esbuild bundling/serving and React 19.3.0, TypeScript 5.9.3.
- Generated TypeScript interfaces from unchanged `specs/openapi.yaml` (draft 0.3.0) via `openapi-typescript 7.10.1` into `frontend/src/api/schema.d.ts`. A dedicated typecheck suite (`frontend/src/api/schema.type-test.ts`) verifies compile-time contract adherence (e.g. bodyless `startAnalysis` and required `ApiError` properties).
- Adheres to `DESIGN.md` tokens: colors (`#17212B`, `#52606D`, `#175CD3`, `#F5F7FA`, `#FFFFFF`, `#D5DCE5`), fonts (IBM Plex Sans, IBM Plex Mono), semantic landmarks (`<main id="workspace">`, `<aside aria-labelledby="inspector-heading">`, accessible skip link).
- The skeleton renders honest unavailable states when no case is selected or when case access is not yet implemented; it makes zero API requests and presents no mock domain action buttons.

### Commands and observed results

Runtime: **Node 26.7.0, npm 11.19.0, Python 3.14.8**.

| Check | Observed result |
|---|---|
| `npm --prefix frontend run generate:api` | **Pass, exit 0**; types generated fresh from `specs/openapi.yaml` |
| `npm --prefix frontend run check:api` | **Pass, exit 0**; declarations match schema |
| `npm --prefix frontend run typecheck` (`tsc --noEmit`) | **Pass, exit 0**; clean declaration checking |
| `npm --prefix frontend run test` | **Pass, exit 0; 2 tests passed** in 82ms |
| `npm --prefix frontend run build` | **Pass, exit 0**; produces `dist/assets/main.js` and `dist/assets/main.css` |
| Coordination verifier (`verify_coordination.py`) | **Pass, exit 0**; 27 operations, 126 tasks, 18 checkpoints, 17 markdown files |
| Coordination unittest suite (`scripts/test_*.py`) | **Pass, exit 0; 122 tests OK** |
| Backend unittest suite (`backend/tests`) | **Pass, exit 0; 14 tests OK** with `-W error::ResourceWarning` |
| DESIGN 0.4.0 lint | **Pass, exit 0**; 0 errors, 0 warnings |
| Whitespace & spec check | **Pass, exit 0**; unchanged `specs/openapi.yaml` |

### How you can test it

1. `npm --prefix frontend run typecheck` — exit 0, no type diagnostics.
2. `npm --prefix frontend run test` — exit 0, 2 passing tests.
3. `npm --prefix frontend run build` — exit 0, bundle created in `dist/`.
4. Run all backend tests: `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v` — 14 tests, `OK`.
5. Run all coordination tests: `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s scripts -p 'test_*.py'` — 122 tests, `OK`.
6. Negative check: in `frontend/src/api/schema.type-test.ts`, uncomment an invalid property or omit `code` from `ApiError`; `npm --prefix frontend run typecheck` will fail with diagnostic error.
7. `git diff --check` and `git diff --exit-code e0257a6ad231105b93ae98a97f176ed233a25412 -- specs/openapi.yaml` — exit 0.

Checkpoint 0 remains **In Progress**; G01C remains **Backlog**. Next task is **G01C** (Verify skeleton Windows and CI setup).

## G01C verification — 2026-10-18

**G01C / Checkpoint 0 / whale2186 / shared integration coordination / In Progress.** Branch `feat/g01c-skeleton-ci`; exact user-selected common contract/base **328c103d0f0383c7b4979bd8199b4201408e2a68** (`feat/g01b-frontend-skeleton`). Starting `git status --short` was empty, and branch/HEAD matched the assignment. `git log` and local branch refs read back real **G01 e0257a6ad231105b93ae98a97f176ed233a25412**, **G01B 328c103d0f0383c7b4979bd8199b4201408e2a68** and **G00 1721bfff9640263d2799434455cdb9c4f345ac35** in the accepted ancestry. No fresh remote fetch or hosted CI/main result is inferred. See [assignment](AGENT_TASKS.md#g01c-assignment--2026-10-18) and [live exit-gate record](ROADMAP.md#g01c-live-record--2026-10-18).

### Changes and supported baseline

- `.github/workflows/contract.yml`: one matrix runs **ubuntu-latest/Bash** and **windows-latest/PowerShell**, with fail-fast disabled so one OS cannot cancel the other's evidence. Read-only repository permission and existing PR/push triggers remain. Each command has a separate step; native command failures cannot be hidden by a later successful PowerShell command.
- CPython **3.14.8** comes from `backend/.python-version`; Node **22.23.3** and npm **12.2.0** match the frontend manifest, replacing the old Python 3.12 artifact-only workflow and reconciling the frontend README's historical Node 26/npm 11 claim. CI asserts runtime versions, prints SQLite, installs `requirements.txt`, runs `pip check`, and clean-installs the committed frontend lockfile with `npm ci`.
- Both OS legs run OpenAPI lint/bundle, independent generated declaration compilation, coordination verifier/negative/schema tests, warning-strict backend tests, frontend `check:api`/`typecheck`/`test`/`build`, DESIGN lint and commit whitespace checks. Bundle paths are quoted and use `runner.temp` in step contexts. Actionlint initially rejected `runner.temp` at job-env scope; moving the bundle env to each Python suite's step resolved it.
- `PYTHONUTF8=1` is explicit in both legs and PowerShell instructions because existing tests use default-encoding reads of UTF-8 planning files. Backend/frontend READMEs contain exact native PowerShell setup/run/negative commands and version/platform limits. No cross-directory Markdown link from `docs/` to a backend/frontend file was added; these paths are code mentions.
- Only the six authorized files changed. `specs/openapi.yaml` 0.3.0, requirements, frontend package/lockfile, generated API types and application/tests remain unchanged. No new domain producers or doubles were introduced. Backend probes exercise real FastAPI/HTTPX/SQLite with synthetic test-only routes; frontend tests render the real React shell without domain/API data.

### Commands and observed results

Local host: **Linux, CPython 3.14.8 / SQLite 3.54.0, Node 22.23.3 / npm 12.2.0**. Unlike earlier sessions, package-registry access worked. A new `/tmp/evora-g01c-clean-venv` was created with **no system site packages**; installation from `requirements.txt` passed, using ordinary registry downloads/cache, without manual package copying. All **22 pins** matched distribution metadata, including FastAPI **0.143.1**, Starlette **1.8.0**, Pydantic **2.14.1**, Uvicorn **0.54.0**, HTTPX **0.28.1**, jsonschema **4.25.1**. `pip check` found no broken requirements. Frontend `npm ci` installed the lockfile with React/React DOM **19.3.0**, TypeScript **5.9.3**, esbuild **0.28.1**, openapi-typescript **7.10.1**; it reported zero vulnerabilities at this run.

| Check | Actual result |
|---|---|
| Clean backend install / pip check / metadata read-back | **Pass**, 22 pins match in isolated venv |
| `npm --prefix frontend ci` | **Pass**, lockfile unchanged; npm warned that esbuild's postinstall was blocked by its script policy, but the installed platform binary supported all subsequent tests/builds without a policy override |
| Redocly **2.57.0** lint and fresh JSON bundle | **Pass**, one pre-existing missing `info.license` warning |
| openapi-typescript **7.10.1** generation / TypeScript **5.9.3** `--noEmit --strict` | **Pass**, scratch declarations compile; committed types unchanged |
| Coordination verifier | **Pass**, 27 operations / 126 tasks / 18 checkpoints / 39 capabilities / 40 proposal mappings; 18 Markdown files |
| Full `scripts/test_*.py` suite, jsonschema **4.25.1** | **Pass, 122 tests, no skips**; includes mutation negatives and synthetic wire examples; log `/tmp/evora-g01c-coordination-tests.log` |
| Backend warning-strict suite, clean venv | **Pass, 14 tests, no skips**, real SQLite read-back/rollback/close/isolation/startup failure and HTTP 400 schema validation |
| Requested backend regression using `/tmp/evora-g01-venv/bin/python` | **Pass, 14 tests**, `-W error::ResourceWarning` |
| Frontend API freshness / typecheck / test / build | **Pass**, 2 tests, no skips; `dist/index.html`, `dist/assets/main.js` and `main.css` produced |
| DESIGN **0.4.0** via requested npx command | **Pass**, zero errors/warnings |
| Actionlint **1.7.7** on final workflow | **Pass**, no diagnostics; installed only under `/tmp/evora-g01c-bin` |
| Missing-bundle negative | **Pass**, deliberately missing scratch bundle makes the focused backend schema test exit **1** with `FileNotFoundError`; it cannot silently skip validation |
| Stale declaration negative | **Pass**, scratch stale declaration makes openapi-typescript `--check` exit **1**, `Generated types are not up-to-date!`; scratch contents and source declarations stay unchanged |
| Localhost server smoke | **Pass**: Uvicorn on `127.0.0.1:18000` completed startup, created temporary SQLite, returned **404** for `/`, then completed shutdown (exit 0); frontend dev server on `127.0.0.1:5173` returned **200** with the root mount element, then was stopped with SIGINT |
| Whitespace, exact-base spec/package/type comparison and index check | **Pass**, only authorized paths changed; nothing staged |

Exact successful Linux commands, from the repository root (the environment below already exists from this run):

```sh
python -m venv /tmp/evora-g01c-clean-venv
/tmp/evora-g01c-clean-venv/bin/python -m pip install --disable-pip-version-check --retries 0 --timeout 10 -r requirements.txt
/tmp/evora-g01c-clean-venv/bin/python -m pip check
node --version
npm --version
npm --prefix frontend ci
npx --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json
npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-api.d.ts
npx --yes --package typescript@5.9.3 tsc --noEmit --strict /tmp/evora-api.d.ts
python scripts/verify_coordination.py /tmp/evora-openapi.json
PYTHONUTF8=1 EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm --prefix frontend run check:api
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npx --yes @google/design.md@0.4.0 lint DESIGN.md
/tmp/evora-g01c-bin/actionlint .github/workflows/contract.yml
git diff --check
git diff --exit-code 328c103d0f0383c7b4979bd8199b4201408e2a68 -- specs/openapi.yaml requirements.txt frontend/package.json frontend/package-lock.json frontend/src/api/schema.d.ts
git diff --cached --exit-code
```

The local npx/npm network attempts set `npm_config_fetch_retries=0` and `npm_config_fetch_timeout=10000` to bound registry waits; the same pinned commands passed with normal cache/download resolution. Actionlint setup was `GOBIN=/tmp/evora-g01c-bin go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.7`. This optional local workflow lint is not a substitute for hosted runner execution.

### Windows PowerShell reproduction — pending execution

Supported target: **Windows x64, PowerShell 7, CPython 3.14.8 with `py` launcher, Node 22.23.3, npm 12.2.0**, writable checkout/temp/package prefix and package-registry access. No clean Windows execution is claimed here. Use a fresh checkout without an existing `.venv`; run from the repository root. Commands use `.cmd` wrappers and the venv executable directly, avoiding activation-script policy changes.

```powershell
py -3.14 -c "import platform; print(platform.python_version()); assert platform.python_version() == '3.14.8'"
node --version
npm.cmd install --global npm@12.2.0
npm.cmd --version
py -3.14 -m venv .venv
$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -c "import sqlite3; from importlib.metadata import version; print('SQLite', sqlite3.sqlite_version, 'jsonschema', version('jsonschema'))"
npm.cmd --prefix frontend ci
$env:EVORA_CONTRACT_BUNDLE = Join-Path $env:TEMP 'evora-openapi.json'
$apiTypes = Join-Path $env:TEMP 'evora-api.d.ts'
npx.cmd --yes @redocly/cli@2.57.0 lint specs/openapi.yaml
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output "$env:EVORA_CONTRACT_BUNDLE"
npx.cmd --yes openapi-typescript@7.10.1 specs/openapi.yaml -o "$apiTypes"
npx.cmd --yes --package typescript@5.9.3 tsc --noEmit --strict "$apiTypes"
& .\.venv\Scripts\python.exe scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
& .\.venv\Scripts\python.exe -m unittest discover -s scripts -p 'test_*.py' -v
& .\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
npm.cmd --prefix frontend run check:api
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build
npx.cmd --yes @google/design.md@0.4.0 lint DESIGN.md
git diff --check
```

Each command must exit **0**; stop if `$LASTEXITCODE` is nonzero before continuing manually. Expected: versions above (record actual bundled SQLite), no broken requirements, jsonschema **4.25.1**, verifier counts above, **122 coordination / 14 backend / 2 frontend tests**, generated types compile, build assets exist, DESIGN zero errors/warnings. The existing missing-license warning is nonblocking. CI runs commands in separate steps and fails the leg on any nonzero exit.

Run backend in one window with `& .\.venv\Scripts\python.exe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log`, then `curl.exe -i http://127.0.0.1:8000/` in another: expect startup completion and **404**. Run `npm.cmd --prefix frontend run dev` and open `http://127.0.0.1:5173`: expect the shell's no-case/unavailable-access state. Stop each with Ctrl+C. These native Windows/server/browser steps remain untested in this session.

Known setup boundaries: wrong/missing runtime, unwritable package prefix/private storage, registry failure or unavailable native wheels/binaries must fail setup rather than justify changing pins or bypassing checks. Keep esbuild optional platform dependencies enabled and do not reuse Linux `node_modules` on Windows. SQLite is bundled with Python and can differ by build. POSIX mode 0700 does not establish Windows ACLs; use private synthetic storage and do not infer production privacy from this skeleton. No native Windows/browser/accessibility, Neo4j, model/provider or full-scope reproducibility result is established here. The npm esbuild script-policy warning above did not block Linux build/test and no policy was relaxed.

### How you can test it

- [ ] Run the complete Linux sequence above in the pinned environment: expect every positive command to exit **0**, with **122 / 14 / 2 tests** and unchanged contract/package/type artifacts. Linux commands and combined regression were exercised here; use a new scratch venv path to independently repeat a clean install.
- [ ] Run the PowerShell sequence and server steps above on native Windows: expect the same checks/counts, startup/404 and the honest frontend shell. **Pending**, not demonstrated by the Linux tests or actionlint.
- [ ] Failure case, after building the bundle, run `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v`: expect one test **OK**, proving malformed synthetic JSON returns schema-valid **400** without echoing input. PowerShell equivalent: `& .\.venv\Scripts\python.exe -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v` with the bundle env already set. The Linux negative was exercised in both full backend suites.
- [ ] Check the freshness failure without editing repository files: `printf '%s\n' '// Synthetic stale declaration' > /tmp/evora-g01c-stale-api.d.ts`, then `npx --yes openapi-typescript@7.10.1 specs/openapi.yaml -o /tmp/evora-g01c-stale-api.d.ts --check`: expect exit **1** and `Generated types are not up-to-date!`. Remove only that scratch probe with `rm /tmp/evora-g01c-stale-api.d.ts`. The same negative passed using an automatically cleaned temporary directory; exact PowerShell equivalent is in `frontend/README.md`.
- [ ] When publication is separately authorized, inspect both matrix jobs on the exact reviewed commit/PR. Record CI run/commit, OS, versions and each suite result in this record; a workflow definition or push alone is not success. Current triggers run on PRs and pushes to `main`/`docs/coordination-foundation`; a feature-branch push alone does not trigger it. This session made no stage/commit/push/merge or hosted run.

Tests use synthetic content and clean their temporary SQLite/probe files. Manual server use leaves an ignored `storage/evora.sqlite3`; remove only your own synthetic database after shutdown. Bundle/types/env artifacts stay in ignored or scratch locations. Backend and frontend runtime smoke cover HTTP startup and shell delivery, not an end-to-end domain application or browser audit.

**Checkpoint 0 exit evidence is complete.** Both `ubuntu-latest` and `windows-latest` CI jobs passed on GitHub Actions PR #1 (Run ID **39102433077**). Checkpoint 0 is **Complete**. Next active checkpoint is **1A**: **F00 / sharmelas-925** requires C-03 identity policy before protected APIs; **U01 / JebasJ** consumes F00. No new shared task is automatically assigned to whale2186. G01D/G02 in 1C need a separate handoff.
