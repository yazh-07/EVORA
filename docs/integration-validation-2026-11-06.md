# Integration failure diagnosis and verification

Worktree: `/home/whale2186/nemesis-shared/EVORA/evora-clean`.

## Diagnosis

| Failure | Classification and fix |
| --- | --- |
| Extra graph node in full-modality snapshot | Outdated assertion. OpenAPI explicitly permits deterministic source-row GPS location nodes. Validate each coordinate pair, its evidence/run/row, values, citations and UUID instead of assuming only evidence/entity/event UUIDs. |
| Detector baseline assumes no edges | Outdated assertion. The two network rows each justify an `assigned_ip` edge; the GPS row justifies a `located_at` edge. Preserve and validate these relationships. Network assignment components also legitimately generate cluster findings. |
| Follow-up expects one edge but observes five | Outdated all-edge count. There is one shared-identifier edge, two network assignments, and two GPS location relationships. Validate the complete graph against source roles, then assert the one shared-identifier relationship specifically. |
| Document/media source membership emitted as `referenced_in` / `detected_in_frame` edges | Production semantics bug. Membership is already present in node evidence/observation lineage and rendered by the graph consumer as provenance rays. Remove these duplicate relationship edges, retain all source metadata, and advance the semantic algorithm version to `source_semantic_relations/2`. Historical stored outputs are not rewritten. |
| Invalid image bytes produce an accepted run | Production acceptance bug. Adapter registration alone does not establish decodability. Both ordinary processing and explicit image understanding now validate the integrity, decoding and limits of the stored original before inserting a run. Return `415 UNSUPPORTED_MEDIA` without runs or partial outputs. Upload/download still preserve arbitrary originals; valid images with a generic MIME type and filename still process. |

The final graph oracle reconstructs complete expected node and relationship sets from the actual selected source records. It checks every endpoint, evidence owner, observation citation and source-row/run join, including derived GPS UUIDs. Historical checks use cached records from the frozen processing runs rather than newer intake. Mutation tests reject omitted assignments, invented location nodes, forged coordinates, mismatched runs/endpoints/evidence, foreign observations and provenance-only edges. Baseline cluster findings are compared to the exact source-validated assignment components, not accepted by count alone. The original triage/history/score assertions remain in place.

The complete suite also exposed two existing media assertions documenting the superseded behavior: they expected corrupt images to create failed runs and detection membership to be a graph edge. These tests now verify pre-acceptance image rejection and exact detection-node/observation provenance. Video decode failure remains an asynchronous failed-run test; video acceptance behavior was not changed.

## Files changed for this repair

- Production: `backend/processing.py`, `backend/image_understanding.py`, `backend/graph_links.py`, `backend/analysis.py`.
- Contract: `specs/openapi.yaml`, plus the two generated documentation comments in `frontend/src/api/schema.d.ts`.
- Backend regression tests: `backend/tests/test_image_preflight.py`, `backend/tests/test_semantic_graph.py`, `backend/tests/test_media_detection.py`, `backend/tests/test_co_mention.py`.
- Integration assertions: `frontend/test/full-modality.integration.mjs`, `frontend/test/detector-feedback.integration.mjs`, `frontend/test/graph-lineage.mjs`, `frontend/test/graph-lineage.test.mjs`.
- This validation record. Other pre-existing modified/untracked work was retained.

## Environment and exact final verification commands

The tracked `frontend/node_modules` symlink and its target were never replaced or populated. A frontend copy under `/tmp/evora-integration-fix/project/frontend` uses scratch dependencies at `/tmp/evora-openrouter-qa/frontend-deps/node_modules`. Source bytes were checked against the working tree, excluding generated build directories. Backend, fixtures and specs in the scratch project link to this working tree. This makes ESM resolution and subprocess builds work without altering the tracked symlink.

Common environment for the commands below:

```sh
export EVORA_TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python
export EVORA_CONTRACT_BUNDLE=/tmp/evora-integration-fix/openapi.json
export EVORA_QA_MODEL=''
QA_FRONTEND=/tmp/evora-integration-fix/project/frontend
```

The model setting keeps optional external executive inference out of these deterministic producer/graph tracers. An initial run without this environment waited on a live local model; it was superseded by the correctly configured runs. Neo4j is explicitly doubled by the integration harness. These results are not live Neo4j acceptance or LLM accuracy claims.

Regenerate the self-contained JSON OpenAPI bundle before contract tests:

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
Path('/tmp/evora-integration-fix/openapi.json').write_text(json.dumps(spec))
PY
```

Result: 344 internal references, no external references.

```sh
"$EVORA_TEST_PYTHON" -m unittest backend.tests.test_image_preflight backend.tests.test_image_understanding backend.tests.test_media_detection backend.tests.test_graph_nodes backend.tests.test_graph_links backend.tests.test_semantic_graph backend.tests.test_graph_projection backend.tests.test_co_mention
node --test frontend/test/graph-lineage.test.mjs
node "$QA_FRONTEND/test/full-modality.integration.mjs"
node "$QA_FRONTEND/test/detector-feedback.integration.mjs"
node "$QA_FRONTEND/test/deeper-processing.integration.mjs"
"$EVORA_TEST_PYTHON" -m unittest discover -s backend/tests
npm --prefix "$QA_FRONTEND" test
"$EVORA_TEST_PYTHON" -m unittest discover -s scripts -p test_contract_examples.py
npm --prefix "$QA_FRONTEND" run build
git diff --check
git status --short
readlink frontend/node_modules
```

Final logs are under `/tmp/evora-integration-fix/`: `focused-complete.log`, `oracle.log`, `full-verified.log`, `detector-verified.log`, `deeper-verified.log`, `backend-verified.log`, `frontend-all.log`, `contracts-verified.log`, and `build-final.log`.

## Final results

| Check | Result |
| --- | --- |
| Focused image/media/graph backend command | 83 tests, OK, 1 opt-in live Neo4j test skipped |
| Graph-oracle mutation tests | 2 passed |
| Full-modality tracer | Exit 0, all checks passed |
| Detector-feedback tracer | Exit 0, positive/control lineage, findings, history and scoring passed |
| Deeper-processing tracer (run after the two tracers above) | Exit 0, passed |
| Complete backend suite | 896 tests in 85.847 s, OK, 7 skipped |
| Complete frontend suite | 377 passed, 0 failed |
| Regenerated-contract example tests | 31 passed |
| Frontend production build, schema freshness, TypeScript | Passed |
| `git diff --check` | Passed, no output |
| `git status --short` | Inspected; pre-existing work remains modified/untracked, plus this repair |
| Dependency symlink | Still `/home/whale2186/nemesis-shared/EVORA/git/frontend/node_modules`; no diff for `frontend/node_modules` |

No remaining verification failures or task blockers. Optional live-service tests remain skipped by the ordinary backend suite; the integration tracers explicitly use a Neo4j double. No commit, push, merge, remote change or release operation was performed.
