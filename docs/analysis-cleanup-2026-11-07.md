# Local analysis and graph cleanup

Source corrections and case remediation were validated locally before publication. Runtime evidence, accounts, credentials and backups are excluded from the source changes.

## Confirmed problems

The synthetic Harborlight case produced 176 graph nodes, 48 edges and 52 findings. The legacy Haar classifiers produced 53 license-plate region matches on rendered graphics and animation, each promoted to a vehicle candidate and a detection-event node. These were false detections for this known synthetic source. Source-scoped copies of D-101/D-202 produced pairwise identifier matches and overlapping detector summaries. Text NER classified some person names as organizations, technical abbreviations as organizations and a filename as a location. Mobile CSV auto-detection was missing. The executive brief received 24 of 208 observations; its context omitted the actual cancellation timestamp and status-board OCR.

All source-record graph nodes and edges reproduced from frozen processing outputs. The problem was extraction quality, presentation and context selection, rather than duplicate uploads or orphaned graph records.

## Changes

- New image/video detections produce `visual_candidate` entities, retaining detector labels, source boxes, frame/time locators, weights and raw observations. A classifier match no longer becomes an asserted person/vehicle type. New processor versions distinguish this policy from historical outputs.
- The graph defaults to a grouped view of exact identifiers and reported coordinates. It excludes file nodes, raw events, date mentions and unverified visual candidates. Grouping is a view, not real-world identity resolution. All underlying source IDs remain inspectable.
- Semantic edge IDs and citations are retained within each analysis. In the grouped view, only displayed endpoints change to their representative source IDs. All valid `assigned_ip` and `located_at` relationships remain. No provenance-only relationships are manufactured.
- **Show all source records** exposes the complete stored graph. Raw visual candidates carry an explicit warning; media files are displayed as image/video files, not verified camera hardware. Empty grouped views still expose the source-view action. Evidence/Events filters switch to source view.
- Graph motion is reinitialized in the layout phase when its graph changes. This prevents stale particle state from crashing the grouped/source transition. Normal and reduced-motion transitions are tested.
- Multi-pair exact-identifier findings are consolidated with complete supporting subject/source/observation unions. Redundant same-identifier, unassessed cluster/corroboration summaries are folded when they add no new claim. Cross-identifier relationships and independently meaningful detector results remain.
- The findings interface folds alternate detector views only when subject IDs, evidence IDs, observation IDs and contradiction references match exactly. Every underlying finding remains individually inspectable/reviewable; explicit kind filters expose the individual records.
- Brief context prioritizes source lines, structured fields, OCR and scene descriptions. Duplicate NER mentions, raw detector boxes, tracks and provenance blobs cannot consume the brief's source budget. Source balancing, natural row/line order, bounded text and explicit coverage remain. The prompt asks for attributed reported times and distinguishes missing excerpts from missing facts.
- Text extraction uses full literal ISO dates ahead of overlapping partial predictions, filters filename-only and technical-abbreviation predictions, and uses explicit local role cues to disambiguate name categories. Corporate suffixes guard against turning company allocation statements into person claims. Extraction remains fallible and unverified.
- Mobile CSV auto-detection recognizes the supported header, including quoted header fields. Existing document uploads can be reinterpreted through `POST .../processing-runs/interpret-as`, without changing uploaded metadata or bytes. The frozen configuration/private provenance retain the original kind and selected parser. The public run exposes optional `source_kind`/`processing_kind`; the UI restores the latest successful interpretation after reload.
- OpenAPI, generated declarations, contract-operation checks and focused regressions cover the new endpoint. The original bodyless processing endpoint retains its existing behavior.

## Applied demo-case correction

The affected document, mobile, image and video sources were reprocessed through the normal acceptance/publication functions using the existing administrator's verified case access. The existing authorized ChatGPT connection/model was reused for the synthetic media and brief. No new accounts, synthetic grants or rewritten evidence records were introduced. A private SQLite backup was made outside the repository before maintenance.

| Check | Before | Corrected |
| --- | --- | --- |
| Default graph | 176 source-record nodes | 17 grouped nodes |
| Full source graph | 176 nodes | 175 nodes, available explicitly |
| Vehicle-typed raw classifier candidates | 53 | 0; retained as unverified visual candidates |
| Valid IP assignment relationships | 5 | 5 |
| Valid GPS location relationships | 5 | 5 |
| Visible grouped relationships | All 48 raw edges | 11 subject relationships |
| Stored findings | 52 | 18 |
| Finding cards | Repeated detector results | 11 cards; all 18 records accessible |
| Brief source observations | 24 of 208 | 65 of 204 |
| Cancellation/refund | Cancellation timing called unresolved | Reports 09:12 cancellation and 10:30 refund |

Every original evidence row and file hash matched its pre-repair value. Every previous processing run/output/provenance record and analysis run/output was unchanged. New runs have new identifiers; the previous snapshot remains available. Recomputing the corrected raw graph from its frozen sources matched exactly. A separate check confirmed that the final lexical rules reproduce the saved entity keys of the three corrected text documents.

## Verification

Dependencies were installed in `/tmp/evora-bulk/frontend`, with current source/test/spec files mirrored there. The tracked symlink in the other checkout and the main repository's existing `frontend/node_modules` directory were preserved.

```sh
TEST_PYTHON=/home/whale2186/.hermes/cache/scratch/test_neo4j_venv/bin/python
node scripts/bundle-openapi.mjs specs/openapi.yaml /tmp/evora-clutter/openapi.json /tmp/evora-bulk/frontend
EVORA_CONTRACT_BUNDLE=/tmp/evora-clutter/openapi.json EVORA_QA_MODEL='' "$TEST_PYTHON" -m unittest discover -s backend/tests
EVORA_CONTRACT_BUNDLE=/tmp/evora-clutter/openapi.json "$TEST_PYTHON" -m unittest discover -s scripts -p 'test_*.py'
npm --prefix /tmp/evora-bulk/frontend test
npm --prefix /tmp/evora-bulk/frontend run build
```

Results: **918 backend tests, OK (9 environment-specific skips); 125 script tests, OK; 402 frontend tests, all passed; generated API freshness, TypeScript and production build passed.** The skips are seven opt-in Neo4j checks and two native Windows ACL checks; the corrected demo analysis itself used the running real local Neo4j service.

With `EVORA_TEST_PYTHON="$TEST_PYTHON"` and the regenerated `EVORA_CONTRACT_BUNDLE`, these integration scripts passed: `full-modality.integration.mjs`, `detector-feedback.integration.mjs`, `deeper-processing.integration.mjs`, `adaptive.integration.mjs`, and `bulk-processing.integration.mjs` (105 files).

With `EVORA_PLAYWRIGHT_MODULE=/tmp/evora-bulk-browser/node_modules/playwright/index.mjs` and `EVORA_CHROME_PATH=/opt/google/chrome/chrome`, browser checks passed for image understanding, video understanding, the new structured-interpretation flow, and repeated grouped/source graph transitions under normal/reduced motion. An additional browser check rendered the actual corrected graph: 17 grouped nodes/11 edges, all 175 raw records accessible, candidate warnings and desktop/mobile rendering, with no JavaScript errors.

Final `git diff --check` passed. Local logs and diagnostic artifacts are under `/tmp/evora-clutter`; they may not persist across sessions. The source change contains implementation, contract, tests and documentation only; no runtime data or credentials.

## Limits

Grouping does not resolve physical identity or establish guilt. Haar scores remain uncalibrated candidates, and NER/OCR/model outputs require source review. The brief still uses a bounded selection, not every observation or every original file byte. The synthetic demo's corrected result is not a general accuracy benchmark or forensic certification. No new Windows build or release was attempted.
