# Investigation workspace revamp

The workspace now opens on an actionable overview and groups work into Overview, Evidence, Timeline, Investigation, and Report. Investigation contains findings, connections, entities, priorities, and questions. Panels mount on first use and retain their state while switching sections; session replacement clears the case workspace.

## Implemented

- Light and dark workspace themes, responsive navigation, readable case cards, and progressive disclosure of internal references.
- Case-wide evidence readiness counts and next-step actions, using real processing histories.
- Explicit completed-analysis history selection; passive discovery cannot override an investigator's choice.
- Multiple-file drag-and-drop intake with editable labels/kinds, acquisition timestamp, per-file status, and sequential upload. A failed item stops the queue; successful items are not resubmitted on retry.
- Format support descriptions distinguishing original storage from available extraction. Existing single-file intake remains available for individual metadata.
- Full-width source inspection, original download, SHA-256 verified UTF-8 previews, media inspection, extraction controls, and observation provenance.
- Case-wide extracted-event timeline with source/text/date filters, normalized UTC ordering, a separate undated view, and links to evidence. This is explicitly a live view, not an analysis snapshot. All pages load before counts/filter results are shown; rendering is incremental.
- Findings with review controls and progressively disclosed provenance. Relationship exploration can focus on the selected node and its immediate neighbors.
- Report drafting from a pinned completed analysis. Source manifest, source hashes, observation references, method/snapshot identifiers, review decisions, AI labels, and limitations are retained. Accepted findings are initially selected; investigators can include other states explicitly. Export plain text or print/save PDF through the browser.

## Boundaries

Report scope and notes are held in memory for the open case; export before leaving, reloading, signing out, or changing the selected analysis. Shared persistent notebooks, assignments, tags, identity reconciliation, and versioned report storage are not implemented in this change. Evidence library search remains page-scoped and labeled as such. The timeline covers extracted Event records, not every Observation or media-relative offset. PDF/DOCX, packet capture, and automatic speech extraction remain outside the revamp. A subsequent update adds explicit vision-model image descriptions and model-assisted OCR; see [Image descriptions and OCR](image-description-and-ocr.md). The existing provider credential and synchronous AI brief concerns from the repository review are separate backend work.

## Verification

Run from the repository root:

```sh
npm --prefix frontend test
npm --prefix frontend run build
```

The browser acceptance uses real FastAPI/SQLite producers and the repository's explicit Neo4j test double. It creates a new synthetic case, processes network/GPS fixtures, records a review, and exercises source inspection, timeline filtering, relationship navigation, report export, draft retention, batch upload, responsive layout, themes, and session clearing.

Start an isolated synthetic server (never point this harness at a production case):

```sh
EVORA_QA_MODEL='' python frontend/test/serve-cases.py --database /tmp/evora-workspace-browser/cases.sqlite3 --port 8913
```

With Playwright available, run in another terminal:

```sh
EVORA_BROWSER_BASE_URL=http://127.0.0.1:8913 node frontend/test/workspace-browser.integration.mjs
```

`EVORA_PLAYWRIGHT_MODULE` may identify an existing Playwright module; `EVORA_CHROME_PATH` may identify an installed browser. `EVORA_BROWSER_ARTIFACTS` controls the screenshot/report artifact directory (defaults to a unique directory under `/tmp`). The browser harness leaves its clearly named synthetic case in the isolated test database for inspection. Live Neo4j and live AI-provider behavior are outside this test.
