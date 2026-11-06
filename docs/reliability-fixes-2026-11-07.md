# Reliability repairs — 7 November 2026

This repair addresses the broken planning test and confirmed validation gaps in the OCR/Q&A paths. It does not make model output infallible or change video from sampled-frame analysis to native video inference.

## Confirmed defects and fixes

### Missing planning-test dependencies

`scripts/test_transcription_scope.py` imported a missing `verify_coordination` helper and opened a removed task catalog. The original helper and catalog were recovered from EVORA commit `114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb` in the sibling checkout, without changing that checkout.

Only the catalog/DAG/contract helper functions needed by these tests were restored. The catalog is preserved unchanged as `fixtures/planning/transcription-task-catalog.txt`, explicitly documented as historical test data. No obsolete active roadmap was recreated. The seven original checkpoint, direct-handoff, dependency-closure, operation-name and version assertions remain intact. The validator recognizes the 23 approved workstation/media extensions alongside the original 27 operations; it still rejects renamed/missing/duplicate operations, broken references, lost provenance requirements and snapshot-selector regressions. Two additional tests cover media operation renaming/duplication and broken references.

The script suite now includes 31 contract-example tests and nine planning/contract regression tests, all passing.

### Invalid citations and verifier flags

The generation validator previously ignored an invented citation if another citation was valid, and expanded evidence/finding IDs into observation lists. That violated the generation prompt's exact-observation requirement. It also accepted verifier JSON `{"supported":1}` because Python compares `1` equal to `True`.

`backend/qa_synthesis.py` now requires every generated citation to be a known exact observation ID, rejects non-string IDs and broader evidence/finding IDs, and requires the verifier's `supported` value to be the actual boolean `true`. Invalid results abstain without publishing or storing partial citations. Short answers are validated too; they are no longer silently skipped by the previous five-character cutoff.

Claims citing image descriptions/OCR, sampled-video descriptions/OCR or speech transcript segments receive the explicit prefix `Model-derived, unverified:` before verification and publication. Qualification is enforced by code even when the model omits it. Existing identifier/number/time checks and independent model entailment checks remain in place. This does not guarantee that a model will select the right source or interpret it correctly in every case.

Regression tests reproduced the acceptance gaps before implementation and now cover mixed valid/invented IDs, evidence/finding shorthand, null/object IDs, numeric verifier flags, media qualification, short answers and HTTP/provenance abstention without partial citations.

### Uniform-image hallucinations

The earlier local-model test invented borders on an entirely white image. `backend/image_understanding.py` now checks every normalized visible pixel **before resizing**. Only exactly uniform images qualify: even one faint changed pixel prevents the override. When the source is uniform, the published description and OCR are replaced by the deterministic uniform-color result, and limitations disclose the local check. For example, a white source produces `Uniform white image with no visible objects or text.` and empty OCR.

Provenance records `uniform_rgb`, `content_validation: uniform-pixel-check/1`, and the provider-output SHA-256 alongside existing model/prompt/source hashes. Nonuniform images keep their generated description/OCR. The original file remains unchanged. The check concerns visible pixels under the recorded white-alpha normalization, not hidden metadata or steganographic content.

The OCR prompt additionally requests original spelling/capitalization/punctuation rather than corrections or modernization. Its hash is frozen into new processing runs. The original prompt hash remains supported: historical records remain readable, and any legacy frozen run executes the exact original prompt and records its original hash. Unknown prompt hashes are still rejected. Tests verify this compatibility and verify uniform colors, transparent-image normalization and a single faint mark before downsampling. The general vision protocol fixture now contains actual printed marks rather than a uniform white image.

### Verification gate

`scripts/verify-full-scope.sh` previously assumed a pre-existing `/tmp` OpenAPI bundle, skipped the broken planning module and printed obsolete fixed test counts. It now regenerates the bundle from `specs/openapi.yaml` using the YAML parser already pinned by the frontend tooling, verifies all internal references, runs every script test, honors `EVORA_TEST_PYTHON`, and reports actual suite results. It resolves the source worktree separately for Git checks when executed through a scratch-project symlink.

The tracked `frontend/node_modules` symlink is preserved. Builds/tests use the existing scratch dependency directory; no packages were installed into the symlink target.

## Live account checks

Public/synthetic samples were sent using the user's already-authorized ChatGPT connection; no private case evidence or tokens were copied into reports. The application's local account and grant remain intact.

All eight models returned by the live account catalog completed both a small text calculation and a real image-heading probe correctly: `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6.1-terra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`. These are 16 small capability checks, not full forensic accuracy evaluations of each model.

The complete live media/case probe used `gpt-6.1-sol`:

- Scanned page, portrait, uniform-white control and a controlled two-frame video analysis all completed.
- The white control published the deterministic uniform description and empty OCR, with the pixel-check provenance.
- Original hashes, observation source/run IDs and locators, zero model-derived extraction confidence and idempotency checks passed.
- Analysis, the executive brief and real Neo4j graph publication completed. The independent source oracle validated all 35 nodes and both legitimate `assigned_ip` edges.
- The page-heading answer cited the scanned page and carried the enforced qualification. The D-7/IP answer cited the correct network row. The unsupported guilt question abstained.
- Historical image/video observations from before this update remained readable with identical IDs.

**OCR limitation:** the latest full scanned-page transcription preserved `grey`, but appended an extra `[illegible]` marker. Whitespace-normalized character similarity was 0.9803 versus 0.9967 in the previous live run. The exact heading was correct. The prompt change is not a demonstrated general accuracy improvement; OCR still needs comparison with the original. Nonuniform-image interpretation and source selection can still be wrong. Sampled-frame video does not establish continuous coverage or identity, and these live account checks did not exercise speech transcription.

## Commands and results

Worktree: `/home/whale2186/nemesis-shared/EVORA/evora-clean`. Scratch sources/dependencies: `/tmp/evora-feature-qa/project`. Logs and public test artifacts: `/tmp/evora-reliability-fix` (temporary).

```sh
export EVORA_TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python
export EVORA_QA_MODEL=''
export EVORA_NEO4J_INTEGRATION=1
export NEO4J_URI=bolt://127.0.0.1:17687
export NEO4J_PASSWORD=disposable-reliability-validation
export EVORA_CONTRACT_BUNDLE=/tmp/evora-reliability-fix/openapi.json

"$EVORA_TEST_PYTHON" -m unittest discover -s scripts -p 'test_*.py'
"$EVORA_TEST_PYTHON" -m unittest backend.tests.test_qa_synthesis backend.tests.test_image_understanding backend.tests.test_video_understanding backend.tests.test_image_preflight backend.tests.test_qa_provenance_and_audit
"$EVORA_TEST_PYTHON" -m unittest discover -s backend/tests
bash /tmp/evora-feature-qa/project/scripts/verify-full-scope.sh
python3 /tmp/evora-reliability-fix/run_integrations.py
"$EVORA_TEST_PYTHON" -u /tmp/evora-reliability-fix/validate_live.py
git diff --check
git status --short
readlink frontend/node_modules
```

The verification gate regenerates its own bundle before contract/backend tests. The separate sequential runner executes cases, adaptive, review-override, qa-tracer, full-modality, detector-feedback, deeper-processing, local-auth-browser, image-understanding, video-understanding and chatgpt-connection integration scripts, with the project test interpreter and current Playwright/Chrome paths. All eleven completed with exit 0. The model probes and live image/video/Q&A checks use real provider responses; browser protocol tests retain their explicit doubles.

An initial full backend run had one `GRAPH_PROJECTION_FAILED` result in an opt-in real-Neo4j test. The identical test passed on a warm rerun and the next complete suite passed; no graph assertions or production graph code were changed. A database warm-up/resource transient is suspected, not conclusively established. An initial gate run from the scratch project also failed its final Git check because the scratch copy is not a Git worktree; resolving the real source worktree fixes that gate.

## Final results

| Check | Result |
| --- | --- |
| Complete backend after the final short-answer change | 908 tests, 95.199 s, OK, no skips |
| Focused image/video/Q&A/provenance regressions | 40 tests, OK |
| All script tests | 40 tests, OK: 31 contract examples plus nine planning/contract regressions |
| Direct planning module invocation | Nine tests, OK |
| Complete frontend | 381 passed, no skips |
| API type freshness, TypeScript, production build | Passed |
| Updated verification gate | Exit 0; its complete backend pass had 907 tests before the final short-answer regression was added; the final 908-test run above verifies that last change |
| Eleven sequential integration scripts | All exit 0 |
| Separate workspace browser workflow | Exit 0; includes report contents, original hash verification, mobile layout and logout |
| Live ChatGPT catalog probes | 16/16 text/image probes correct across all eight listed models |
| Live media/analysis/Q&A | All processing and source/citation checks passed; OCR accuracy limitation documented above |
| Original/historical results | Old observations readable with original IDs; new media originals unchanged |
| Independent live graph lineage | Complete 35-node, two-edge graph passed |
| Contract bundler negative checks | External and broken references rejected before output was written |
| `git diff --check`, final status and symlink | Passed; existing changes retained and dependency symlink unchanged |

Sanitized public [model probe results](validation/chatgpt-model-probes-2026-11-07.json) are retained in the repository. Full live results and execution logs remain in the temporary directory noted above. The tracked source files in the scratch backend/frontend were compared with the worktree: 258 files matched.

The repaired app remains at `http://127.0.0.1:8000` with the tested `gpt-6.1-sol` ChatGPT provider and shared image model. Post-restart checks confirmed `setup_required: false`, online mode, and an authorized ChatGPT connection. No active processing or analysis was interrupted. Local accounts, sessions, cases, originals and the private OAuth store were retained. Test-only servers and the disposable `evora-reliability-neo4j` container are stopped; the persistent workstation graph and app remain running.

Files changed for this repair: image-understanding and Q&A producers, their two regression-test files, the restored planning helper/catalog fixture, script regression imports/tests, the contract bundler and verification gate, plus this report, the public model-probe artifact and links from previous validation documentation. No commit, push, merge, remote change or release was made.
