# Live ChatGPT connection validation — 2026-11-06

The user completed real ChatGPT authorization in the running EVORA workstation. The saved connection reports sign-in and plan usage authorized, and the live account model catalog loads. After fixing a stream-reading defect, live text, image/OCR, sampled-video, case analysis, executive brief and correctly cited Q&A requests passed with `gpt-6.1-sol`.

This supersedes the earlier reports' unverified-live-ChatGPT limitation for this account, model and run. It does not establish access for every account/model or general forensic accuracy.

## Root cause and repair

The live Responses stream sends final message content in `response.output_item.done`, followed by `response.completed` with `response.output: []`. EVORA previously read only the terminal response's output array, returning an empty answer even though inference completed. This affected text synthesis and image/video interpretation through the same connection.

`backend/chatgpt_connection.py` now retains completed output items by their output index and uses them when the terminal output array is empty. It accepts reasoning items whose schema omits a status field, extracts answer text from message content, preserves the full-terminal-output path without duplicate text, and rejects empty answers. Successful terminal completion is still mandatory; failed/incomplete/interrupted streams and refusals are rejected. Deltas alone are never published.

Four regression tests were added in `backend/tests/test_chatgpt_connection.py`: completed streamed items plus an empty terminal output; no duplication when terminal output is populated; failed/incomplete/interrupted streams after a completed item; and empty/partial/refused output rejection. The fixture includes a reasoning item without a status, matching the live vision stream.

Official references: [ChatGPT-plan models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [Responses streaming events](https://developers.openai.com/api/docs/guides/streaming-responses). The live stream above is the direct evidence for the empty terminal output behavior.

## Live checks

Tests used production API handlers in an isolated local validation database, the workstation's existing protected ChatGPT grant through the production connection and refresh lock, and real OpenAI requests. No provider doubles, copied credential files, private case evidence or authorization bypasses were used. The validation workstation had its own local administrator session. Only public samples and synthetic records were submitted.

| Check | Observed result |
| --- | --- |
| Sign-in, plan permission and account catalog | Connected; plan sharing authorized; catalog returned eight visible models |
| Text inference | Completed JSON answer to `17 + 25`: `{"status":"ok","result":42}` |
| Public scanned-page image | Completed in 13.37 s; correct heading and paragraph; OCR character similarity 0.9967 after whitespace normalization. One spelling difference: `grey` became `gray`. |
| Public astronaut portrait | Completed in 16.56 s; scene described as a person in an orange pressure suit holding a helmet, with flag and shuttle model; OCR included visible patch/name text and `[illegible]` for uncertain text. Not a full character-level accuracy benchmark. |
| Uniform white negative control | Completed in 5.14 s; empty OCR; described as uniformly white with no discernible objects or text, without the invented borders from the earlier local-model run |
| Controlled video | Completed in 25.70 s; two sampled frames processed through the real ChatGPT image pipeline, with frame descriptions/OCR and video provenance. The clip combines the public portrait and recorded audio; it is not real investigation footage. Speech transcription was explicitly disabled in this check. |
| Original integrity and lineage | All media originals retained identical bytes/SHA-256. Observation case/source/run IDs and source locators matched. Model-derived vision fields retained zero extraction confidence. Replaying each idempotency key returned the original run. |
| Synthetic network source | CSV processing completed; the control record associates D-7 with 203.0.113.7 |
| Case analysis and executive brief | Analysis completed against real Neo4j; `ai_executive_hypothesis:v1` finding was present alongside the two source-backed connected components |
| Graph | 35 nodes and two legitimate `assigned_ip` edges; the independent graph oracle validated the complete graph against evidence, entities, events and observations, rather than accepting counts alone |
| Scanned-page Q&A | Supported answer: the model-derived OCR heading is “Region-based segmentation”; cited the correct page and its image locator |
| Network Q&A | Supported answer: D-7 is associated with 203.0.113.7; cited the correct network source and row-2 device/IP observations |
| Unsupported guilt question | Correctly returned `supported: false` with no citations |

The app was restarted with the repaired reader at `http://127.0.0.1:8000`, online ChatGPT mode, `gpt-6.1-sol` and the shared image model enabled. Existing local accounts, session records, source data and ChatGPT authorization were retained. The local graph service remains running with persistent storage. Model/provider preferences remain runtime settings as described in the connection documentation.

## Verification and artifacts

```sh
export EVORA_CONTRACT_BUNDLE=/tmp/evora-feature-qa/openapi.json
export EVORA_QA_MODEL=''
TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python

"$TEST_PYTHON" -m unittest backend.tests.test_chatgpt_connection backend.tests.test_image_understanding backend.tests.test_video_understanding backend.tests.test_qa_synthesis
```

Result: **36 tests passed**. An initial invocation omitted `EVORA_CONTRACT_BUNDLE` and failed fixture setup; the corrected invocation above passed.

The complete backend suite used a separate disposable Neo4j container, rather than the user's persistent graph:

```sh
EVORA_NEO4J_INTEGRATION=1 NEO4J_URI=bolt://127.0.0.1:17687 NEO4J_PASSWORD=disposable-live-validation "$TEST_PYTHON" - <<'PY'
import time, unittest
from backend.graph_db import Neo4jGraphDatabase
for attempt in range(40):
    try:
        db = Neo4jGraphDatabase()
        db.get_driver().verify_connectivity()
        db.close()
        break
    except Exception:
        if attempt == 39: raise
        time.sleep(.5)
result = unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('backend/tests'))
raise SystemExit(not result.wasSuccessful())
PY
```

Result: **900 tests passed in 91.842 s, no skips**, including the seven opt-in Neo4j checks. The container `evora-chatgpt-validation-neo4j` is removed after validation; `evora-workstation-neo4j` remains running for the app.

All three browser integration checks also passed against the current backend and production frontend build. These browser checks use explicit protocol doubles, separately from the live account probes above:

```sh
export EVORA_TEST_PYTHON="$TEST_PYTHON"
export EVORA_PLAYWRIGHT_MODULE=/tmp/evora-feature-qa/tools/node_modules/playwright/index.mjs
export EVORA_CHROME_PATH=/opt/google/chrome/chrome
node frontend/test/chatgpt-connection.integration.mjs
node frontend/test/image-understanding.integration.mjs
node frontend/test/video-understanding.integration.mjs
git diff --check
git status --short
readlink frontend/node_modules
```

Final whitespace validation passed. The tracked dependency symlink is unchanged. Post-restart checks confirmed that the interface is reachable, local setup remains complete, online mode is enabled, and the saved ChatGPT connection remains authorized with credential-file permissions `0600`.

The opt-in live harness ran as:

```sh
"$TEST_PYTHON" -u /tmp/evora-chatgpt-live/validate.py
```

Results: `/tmp/evora-chatgpt-live/verified/results.json`; source data and independent-oracle input: `verified/lineage.json`; brief/findings: `verified/findings.json`; logs: `verified-validation.log`, `focused.log`, `backend.log`. These temporary artifacts may not persist across sessions. They contain public/synthetic validation data, not OAuth tokens. The existing private credential store was never printed or copied into reports.

Remaining limits: other account models were not tested; video covers sampled frames; this run did not test native audio/video submission or speech transcription; OCR is imperfect and generated statements still require verification against originals. The earlier orphan planning test and local-model accuracy findings in [the full feature validation](feature-validation-2026-11-06.md) are outside this repair.

Only the connection reader, its regression tests, and validation documentation changed during this live test. Existing user changes and the tracked frontend dependency symlink were preserved; no commit, push, merge or release was made.
