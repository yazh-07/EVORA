# Feature validation — 2026-11-06

The application workflows pass the automated checks listed below. This is **not an all-features accuracy approval**: the live small-model checks still reveal incorrect image details and an unanswered OCR question. Actual hosted-provider access and a real ChatGPT account authorization were not exercised.

Subsequent [live ChatGPT validation](chatgpt-live-validation-2026-11-06.md) verified real authorization and inference after a stream-reading fix. That later record supersedes this report's unverified-ChatGPT limitation for the tested account/model; the local-model findings below remain unchanged.

[Reliability repairs on 7 November](reliability-fixes-2026-11-07.md) restore the missing planning tests, reject invalid Q&A citations/verifier flags, enforce media qualification and prevent uniform-image hallucinations. They also verify small text/image requests for every listed account model. The historical failures below remain the record of this earlier run.

## Coverage and results

| Feature | Checks and result |
| --- | --- |
| Local accounts and offline access | Backend tests cover setup, authentication, sessions, authorization, account management and recovery. Browser acceptance covers local setup/sign-in, cookies and sign-out. Passed. |
| Cases and source intake | Creation, case isolation, pagination, multipart uploads, batch intake, original downloads and SHA-256 integrity. API and browser checks passed. |
| Processing and source records | Document, message, mobile, network, GPS, transcript and media adapters; observations, entities, events, normalization, failures, idempotency, publication and processing audit. Backend and modality tracers passed. |
| Invalid images | Original storage remains available; analysis rejects invalid/unsupported bytes with 415 before creating a run or partial outputs. Valid images with generic MIME remain supported. Focused regression and full-modality tests passed. |
| Graph and lineage | Entire graphs reconstructed from source observations, including derived GPS nodes, `located_at`, valid `assigned_ip`, candidate links and provenance rays. Exact endpoint/citation checks and mutation regressions passed. All seven opt-in backend Neo4j checks ran against a disposable real database. The cases tracer also checked actual Neo4j publication. Other tracers retain their explicit graph doubles. |
| Analysis, findings and triage | Exact current factor values/weights/contributions, candidate links, connected entity components, matching reported claims, controls, re-analysis, immutable snapshots and history. Passed. Matching claims retain the warning that source independence is unverified. |
| Review and overrides | Review status, reasons, priority overrides, audit and original automated evaluations. Backend and review-override integration checks passed. |
| Timeline and source inspection | Filtering, source navigation, source locators, original preview/download and hash verification. Passed in API/component tests and browser acceptance. |
| Reports | Scope/notes, accepted findings, draft retention and downloaded report content. Browser assertions verify case/run IDs, review text and every included source's ID, label, SHA-256 and byte count. Passed. |
| Settings and model connections | Provider configuration, capability handling, error paths, optional model behavior and connection UI pass controlled backend/component/browser tests. Actual paid OpenRouter inference was not tested. |
| Image description and OCR | Controlled provider tests and browser workflow passed. A real Ollama vision model completed three image probes with source/model provenance and unchanged originals. Accuracy limitations below remain. |
| Video analysis and speech | Controlled tests and browser workflow passed. A live 11-second composite MP4 completed frame descriptions/OCR, detections, candidate tracking and local speech transcription. This was a controlled sample, not a real investigation video or an identity-tracking benchmark. |
| Evidence questions | Retrieval, citations, synthesis validation, audit and unsupported-answer paths passed deterministic tests. The live model did not answer the scanned-heading question despite the heading appearing in OCR. Live answer usefulness therefore did not pass. |
| ChatGPT connection | OAuth protocol, callback/token validation, image/text handling and browser settings passed local test doubles. A real account login, subscription entitlement and actual remote inference remain unverified. |
| Workspace presentation | Desktop navigation, source previews, mobile overflow, light/dark themes, tab drafts and logout clearing passed Chrome acceptance. Animation-related component checks are included in the frontend suite; subjective smoothness on other devices was not benchmarked. |

## Defects found and changes made during this sweep

1. `cases.integration.mjs` and `adaptive.integration.mjs` expected an older analysis version, only two triage factors and an earlier graph shape. Current producers evaluate zero gap/conflict factors and, when available, temporal proximity. Valid source-backed relationships also create connected-component findings. Updated assertions now independently calculate the documented policy and verify complete graph/finding lineage; they do not merely accept new counts. Four new oracle tests include mutations for missing factors, changed values/weights/scores, fabricated or misattributed findings, and false independence claims.
2. `workspace-browser.integration.mjs` used the removed bearer-token login. It now provisions a local administrator on a fresh disposable workstation and uses the resulting session cookie. Report export assertions now verify content rather than download completion alone.
3. `GraphView.tsx` supplied multiple text children to an SVG `title`, producing React server-render warnings. The title now uses one string; graph component tests verify its visible source label, ID and stable counter.

Files changed for this sweep: `frontend/src/cases/GraphView.tsx`; `frontend/test/{cases.integration,adaptive.integration,workspace-browser.integration,graph-view.test,feature-oracles.test,triage-policy-oracle,finding-lineage-oracle}.mjs`; this report. Existing modified and untracked work was preserved.

## Live accuracy findings and remaining failures

The actual model was `qwen3-vl:2b-instruct` on an isolated Ollama server at `http://127.0.0.1:11435`.

- A public scanned-page sample produced OCR matching the reference after whitespace normalization (character similarity 1.0). This is one sample, not a general OCR accuracy estimate.
- The astronaut photograph's small patch text was misread, including invented strings such as `COLEMAN HAMLEY TOGETHER` and `BUSH V. C.`.
- A generated plain white negative control produced empty OCR, but its description invented thin black top and bottom lines. Empty OCR alone does not establish an accurate description.
- Asking for the scanned page heading returned `supported: false` and an unavailable-answer response, with no citations. This was a safe abstention but failed the expected useful, correctly sourced answer. The unsupported guilt question also correctly abstained.
- Live image processing, original hash preservation, provenance, idempotency, failed-rerun retention, graph publication, analysis snapshot inclusion, re-login persistence and unauthenticated denial passed.
- Live video processing produced two speech segments, two sampled-frame descriptions, two OCR observations, eleven frame detections and one geometric candidate track. These counts confirm pipeline execution, not complete scene coverage or transcript/identity accuracy. Optional speech dependencies and the model were installed only in the scratch environment; a normal deployment still requires speech setup.
- Existing backend evaluation fixtures also contain measured extraction false positives and misses despite meeting their test thresholds. Passing tests do not establish perfect entity/text extraction.
- Broad script discovery still fails to import `scripts/test_transcription_scope.py`: missing `verify_coordination`. That orphan planning test also references absent `docs/TASK_BREAKDOWN.md`; its docstring explicitly says it is not a model or application test. No assertion was disabled and no placeholder planning assets were fabricated. Result: 31 passing contract checks plus one import error.

No live hosted-provider credential check, real ChatGPT account authorization, exhaustive format/codec benchmark, forensic accuracy certification or performance/load benchmark was performed.

## Environment and reproducible commands

The tracked `frontend/node_modules` symlink was never replaced or deleted. Its target remains `/home/whale2186/nemesis-shared/EVORA/git/frontend/node_modules`. Dependencies were installed with `npm ci` in `/tmp/evora-feature-qa/project/frontend`. Backend/frontend source bytes in that scratch copy were compared with the worktree: 258 files matched. Scratch fixtures/specs/scripts/docs refer to the working tree. Builds and test data are disposable, not the user's application data.

```sh
export EVORA_TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python
export EVORA_CONTRACT_BUNDLE=/tmp/evora-feature-qa/openapi.json
export EVORA_QA_MODEL=''
export EVORA_NEO4J_INTEGRATION=1
export NEO4J_URI=bolt://127.0.0.1:17687
export NEO4J_PASSWORD=disposable-feature-validation
export EVORA_PLAYWRIGHT_MODULE=/tmp/evora-feature-qa/tools/node_modules/playwright/index.mjs
export EVORA_CHROME_PATH=/opt/google/chrome/chrome
QA_FRONTEND=/tmp/evora-feature-qa/project/frontend
```

Neo4j used a temporary `neo4j:5.26.0-community` container named `evora-feature-qa-neo4j`, with a disposable password, loopback port 17687 and temporary data. Existing services and application databases were not modified.

Before contract tests, regenerate the bundle from the authoritative spec (all references are internal):

```sh
python3 - <<'PY'
import json
from pathlib import Path
import yaml
spec = yaml.safe_load(Path('specs/openapi.yaml').read_text())
def verify(value):
    if isinstance(value, dict):
        if '$ref' in value:
            assert value['$ref'].startswith('#/'), 'External reference needs bundling'
        for child in value.values(): verify(child)
    elif isinstance(value, list):
        for child in value: verify(child)
verify(spec)
Path('/tmp/evora-feature-qa/openapi.json').write_text(json.dumps(spec))
PY

"$EVORA_TEST_PYTHON" -m unittest discover -s backend/tests
npm --prefix "$QA_FRONTEND" test
"$EVORA_TEST_PYTHON" -m unittest discover -s scripts -p test_contract_examples.py
npm --prefix "$QA_FRONTEND" run build
"$EVORA_TEST_PYTHON" -m unittest discover -s scripts -p 'test_*.py'
"$EVORA_TEST_PYTHON" -m unittest backend.tests.test_image_preflight backend.tests.test_image_understanding backend.tests.test_media_detection backend.tests.test_graph_nodes backend.tests.test_graph_links backend.tests.test_semantic_graph backend.tests.test_graph_projection backend.tests.test_co_mention
```

The final sequential integration run used `python3 /tmp/evora-feature-qa/run_integrations.py`, which runs the following commands with the environment above and scratch frontend as its working directory:

```sh
node test/cases.integration.mjs
node test/adaptive.integration.mjs
node test/review-override.integration.mjs
node test/qa-tracer.integration.mjs
node test/full-modality.integration.mjs
node test/detector-feedback.integration.mjs
node test/deeper-processing.integration.mjs
node test/local-auth-browser.integration.mjs
node test/image-understanding.integration.mjs
node test/video-understanding.integration.mjs
node test/chatgpt-connection.integration.mjs
```

The separate workspace browser check used a fresh local-account server and the final production build:

```sh
# Run from /tmp/evora-feature-qa/project; server stays running for browser check.
"$EVORA_TEST_PYTHON" -m backend.run --database /tmp/evora-feature-qa/workspace-final2.sqlite --storage /tmp/evora-feature-qa/workspace-final2-evidence --port 18916

EVORA_BROWSER_BASE_URL=http://127.0.0.1:18916 EVORA_BROWSER_ARTIFACTS=/tmp/evora-feature-qa/workspace-final2-artifacts node "$QA_FRONTEND/test/workspace-browser.integration.mjs"
```

Live probes (run from the actual worktree, using separate temporary data and Ollama):

```sh
"$EVORA_TEST_PYTHON" scripts/validate_live_images.py --model qwen3-vl:2b-instruct --endpoint http://127.0.0.1:11435 --scan /tmp/evora-feature-qa/page.png --output /tmp/evora-feature-qa/live-images
PYTHONPATH=/tmp/evora-feature-qa/speech-deps EVORA_SPEECH_MODEL_PATH=/tmp/evora-feature-qa/whisper-tiny.en "$EVORA_TEST_PYTHON" scripts/validate_live_video.py --video /tmp/evora-feature-qa/speech.mp4 --model qwen3-vl:2b-instruct --endpoint http://127.0.0.1:11435 --output /tmp/evora-feature-qa/live-video
git diff --check
git status --short
readlink frontend/node_modules
```

Samples: repository `fixtures/media/astronaut.png`; [scikit-image's public page fixture](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/page.png); [Whisper's public JFK audio fixture](https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac). The video combines the portrait and audio for controlled pipeline testing.

## Final verification totals

| Command group | Result |
| --- | --- |
| Complete backend, real Neo4j enabled | 896 passed, no skips |
| Complete frontend | 381 passed, no skips |
| OpenAPI contract examples | 31 passed |
| Focused image/media/graph backend regressions | 83 passed, no skips |
| Eleven sequential API/browser integration scripts | All exit 0 |
| Separate complete-workspace Chrome acceptance | Exit 0, including report contents |
| Production build | Passed schema freshness, TypeScript and asset build |
| Broad scripts discovery | 31 passed; one legacy planning-module import error |
| Live image/video probes | Pipelines completed; image/Q&A accuracy issues remain as documented above |
| `git diff --check` | Passed |
| Final worktree and dependency symlink inspection | Existing changes retained; tracked symlink unchanged |

Logs, live outputs and browser screenshots are under `/tmp/evora-feature-qa/`; temporary artifacts may not persist across sessions. The detailed failures above are retained here. Only test-owned servers and the disposable database container are stopped after validation. No commit, push, merge, remote change or release was made.
