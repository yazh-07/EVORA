# EVORA improvement plan

## Implementation update — 13 November 2026

The latest “start working” authorizes the UI, map and plate work below. Earlier “planning only” sections record the design discussion, rather than the current authorization boundary.

Latest map update: street tiles now load by default instead of showing a blank country fill at city zoom. The basemap selector offers Street map, Satellite and Offline map; GPS points link to Google Street View. Map choices remain independent of model settings.

Delivered in this pass:

- Direct pending-file processing, selected-file batches, explicit reprocessing, compact progress, and scoped retries. Optional vision operations remain explicit.
- One source inspector with Results / Original / Info, a single media viewer, and source references that resolve the exact historical output and results page.
- Shared controls, action menus, focus restoration, shorter motion, reduced-motion support, readable source columns, mobile inspection, and remembered case-tab scroll positions.
- Locations: local country outlines, clustered evidence points, device/date filters, source links, playback, conservative paths, and approximate place mentions. See GPS_MAP_PLAN.md for coverage and limits.
- Optional isolated local plate detector and OCR, installed on this workstation. See PLATE_RECOGNITION_PLAN.md for validation and remaining work.

Remaining: representative plate accuracy evaluation, dense video tracking/consensus and investigator corrections; persistent regional map management, richer local labels and indexed geographic queries. Earlier proposals are a roadmap, not a claim that every feature has shipped.

### Fluidity, motion and consistency (planning only)

The user requests a more fluid, smooth and consistent interface. Apply this as a shared design standard across account screens, case navigation, Evidence, processing, results, Settings and the proposed Locations workspace. Keep the current planning boundary; no application edits or builds are authorized by this addition.

- **One visual system.** Centralize typography, spacing, radii, surfaces, borders, icon sizes and interactive states. Use the familiar system sans-serif stack, approximately 16px body text, 15–16px controls and readable secondary text. Use a shared spacing scale and consistent panel/header alignment. Preserve custom accents and contrast across Light/Dark/System modes.
- **Predictable actions.** Use one filled primary action for the current task, quiet secondary controls and an overflow menu for infrequent operations. Keep button heights, padding, labels, focus rings, disabled states and progress indicators consistent. Use navigation tabs for switching views, badges for status, and buttons for actions. Avoid several different visual treatments for the same behavior.
- **Fluid responsive layout.** Let the main work area expand naturally. Keep sidebar, table, source inspector and map proportions sensible at intermediate widths. On smaller screens, use a focused inspector view or drawer with a clear return path; avoid squeezing several narrow columns together. Preserve selected evidence, filters, viewport and scroll position when returning within the same case. Long filenames and errors must wrap without pushing controls off screen.
- **Short, useful motion.** Proposed timing tokens: roughly 100–150ms for hover/pressed feedback and 160–220ms for panels/menus. Prefer subtle opacity/position transitions. Inputs, selection, media seeking and chart/map interaction respond immediately; navigation must not wait for an animation. Avoid bounces, decorative entrances, repeated chart redraws and broad animations on every data update.
- **Stable loading and progress.** Reserve dimensions for async content so controls do not jump. Use proportionate skeletons or one compact status indicator, followed by the real content. Show determinate progress only when actual totals are known. Keep successful same-case output visible during an explicitly labeled refresh when safe; never retain another case's or user's evidence after navigation/logout. Errors have a concise recovery action.
- **Smooth task transitions.** Keep the processing action/progress/completion in the same toolbar position. Update only affected records/viewers. Opening Original, returning to Results, selecting a map point and inspecting its source should preserve context. Avoid duplicate viewers, simultaneous refresh buttons, full-screen reloads and success messages that displace the workspace.
- **Accessible interaction.** Respect reduced-motion preferences, including map camera movements and drawer transitions. Keep visible keyboard focus, consistent Escape/close behavior, focus restoration, and adequately sized touch targets. Provide useful table/list access alongside charts/maps. Motion and color must not be the only way a state change is communicated.

Acceptance: review the complete create/upload/process/analyze/inspect/report flow and the planned map flow at 360/768/1280/1440px, normal and reduced motion, mouse/touch/keyboard, and slow/erroring requests. Check layout stability, preserved context, immediate feedback and consistent action hierarchy. Judge smoothness by task completion and responsiveness, not the number of animations.

### GPS maps — concrete workspace proposal (planning only)

The user asks for an actual GPS view with maps. See [GPS map workspace plan](GPS_MAP_PLAN.md) for a source-linked Locations workspace, recorded points/paths, device/time filters, playback, offline regional basemaps, backend coordinate projection and later geospatial analysis. The existing GPS parser supplies the core coordinate/time records; typed geographic queries and the map are still to be implemented. This remains part of the current planning phase.

Also include approximate areas when supported by evidence, with source/method/time references and an explicit precision label. Keep coarse/inferred areas distinct from reported GPS points, preserve conflicting alternatives, and leave unsupported locations unknown.

### Current UI feedback — action hierarchy and evidence inspection (planning only)

The user still sees too many buttons and wants Process all and Details improved. This extends the current planning request; do not implement or build until instructed.

Observed in the current source: the Evidence workspace has Add evidence, a separate Process all panel, a second Start batch action, and a bottom Refresh evidence button. Opening a file adds Download original, Preview original text, Refresh results, Refresh detections, operation cards, and multiple metadata disclosures. Results repeat Details for each item and add a separate Output reference. Processing adds another inspector for image/video sources, status paragraphs, run details and history controls. These overlapping controls make the main task hard to identify.

Proposed layout and behavior:

1. **One Evidence toolbar.** Put search, Add files, a context-sensitive Process action, and an overflow menu together. Reserve the filled accent style for the next useful task. Add files is primary in an empty case; Process pending files is primary when work is waiting. Keep case analysis visually secondary while examining/processing evidence. Avoid several equally prominent filled buttons across the page.
2. **Replace Process all with a direct, scoped action.** Default label: `Process 8`, where 8 is the actual eligible pending-file count across the case. When files are explicitly selected, show `Process selected (3)` and use exactly that selection. A normal local run starts from that action; remove the redundant Process all → Start batch sequence. A small adjacent options control opens operation choices only when needed. Show supported choices for the selected file types, exclude unsupported files explicitly, and retain direct configuration/error recovery. Completed operations stay available without automatic reruns. New extraction capabilities on previously processed files require operation-aware eligibility, not a blanket “file completed” skip.
3. **Compact progress in the same place.** While running, show one progress indicator and `Processing 3/8`; open the task list on demand. When complete, show a brief result such as `6 ready · 2 failed`, with Retry failed as the useful follow-up action. Keep Activity as the full task history. Use Stop queue for the existing stop behavior: accepted server jobs continue. Do not call it Cancel or offer Pause/Resume until the backend supports those semantics. Batch scope/counts and selection persistence must be explicit across pagination and filters.
4. **One source inspector with Results / Original / Info.** Results opens by default. Original contains the image/video/text viewer and its download action, with one shared viewer instance. Info contains useful file metadata, integrity, extraction method and history. Keep IDs/hashes/raw fields under a single Technical disclosure. Remove repeated generic Details, Method, Output reference and run-ID blocks from the normal results list. Selecting a result shows its relevant source location and metadata in the inspector; preserve citations and historical-output selection.
5. **Make result navigation look like navigation.** Replace large operation-button cards with compact tabs such as Detections, Text and Transcript, with counts and states where useful. Show only relevant operations. Keep the current operation's error or unavailable state clear. Use native media playback controls and small labeled viewer tools. Avoid simultaneous Refresh results, Refresh detections and Refresh evidence controls.
6. **Make secondary actions quieter.** Use one overflow menu per work area for infrequent actions such as Download original, Reprocess, Processing history and manual Refresh. Keep frequently used review/correction actions directly accessible when a result is selected. Use labeled icon controls for refresh/expand/close; provide accessible names, visible focus, touch targets and a usable mobile menu. Show status badges as status, never as decorative buttons. Keep filter controls in a compact toolbar/drawer rather than a second wall of actions.

Behavior required before implementation can be called complete:

- Local processing needs no extra confirmation step. A hosted-provider operation still exposes the actual destination/data scope and obtains the existing required sharing consent at that decision.
- Successful processing/status events refresh the affected list, result and viewer together. Keep a single manual Refresh fallback and explicit retry after failures. Do not imply automatic updates until they are wired.
- Build selection-aware and operation-aware batch handling; the existing whole-case controller is insufficient for Process selected and targeted Retry failed. UI labels must follow real backend/controller behavior, including partial completion and unknown job state.
- Test empty, pending, mixed capabilities, running, failed, complete and reviewer states; multi-page selection; old successful results during a failed rerun; and desktop/mobile keyboard use. Verify that the number of visible primary actions stays small without hiding the next required action.

Suggested implementation order when authorized: consolidate the Evidence toolbar and batch action; unify the source inspector; simplify result tabs and Details; connect shared refresh/progress and selection-aware processing; then review the complete workflow for remaining duplicate controls.

### Current request — plate recognition planning only

The user reports poor license-plate detection and requested a plan without implementation. See [Plate recognition improvement plan](PLATE_RECOGNITION_PLAN.md) for the current-code audit, benchmark, dedicated detector/OCR comparison, video handling, concise review interface, and backend traceability. No application changes or builds are authorized by this planning request.

### Latest implementation — sidebar, readable type, Settings, and text recovery

The user authorized building after the feedback below. The global Home/Colors rail is removed. Case navigation now occupies the sidebar and becomes a horizontal scroller on narrow screens. The case-header UUID/disclosure is removed. Interface typography uses the system sans-serif stack, with 16px body text, 15–16px controls and labels, and readable secondary text. Setup/sign-in explanatory blocks are removed; recovery instructions stay short and functional.

Settings opens to Appearance. Models are available to administrators; Viewer preferences save locally for every role without calling the administrator settings API. Repeated model/provider explanations and promotional model descriptions are removed. Appearance preview/cancel, saved colors, and System/Dark/Light modes remain available.

Text recovery: installed all pinned requirements into a persistent project `.venv`, verified the original spaCy model files, and validated Python 3.14.10 compatibility with the real extraction suite. Package-version and model-hash checks remain enforced. Added `scripts/run-local.sh` and a startup check for actual text-model loading and graph connectivity. The configured local graph credentials are in ignored private `.env`, never committed. A disposable HTTP backend successfully processes real `.txt` bytes and publishes case analysis to the running Neo4j service.

Validation for this revision: frontend schema/type/build checks, 409 frontend tests, 28 backend tests (including real model extraction and invalid-model rejection), complete browser workflow at 360/768/1280/1440px, and a disposable local-account HTTP/browser check using real text processing and live Neo4j publication. Screenshots cover the setup form, populated overview, Settings, source results, mobile, and dark mode. Test graph records were removed after verification.

### Feedback captured before implementation

The user requested these notes before later authorizing implementation. The restrictions below describe that earlier notes-only phase.

Additional feedback:

- Remove the case-header “Details” control containing the raw UUID. It adds no useful information to the normal investigation flow. Keep internal identifiers available only where a specific diagnostic or reference task requires them.
- Fonts still feel too small and unusual. Use familiar, readable interface typography with larger body text and labels; review the actual screens at normal zoom, including Settings and the sidebar.
- Settings still contains excessive explanatory copy. Audit every section, remove introductions/reassurance/repetition, and show concise controls with help only where needed for a decision.
- Remove the global Home/Cases-and-Colors rail. Move color and Appearance controls into Settings. Reuse sidebar space for useful investigation navigation or contextual tools, and revise the dashboard accordingly. Exact sidebar contents still need to be worked out; do not simply relocate decorative controls.
- Text-file processing/analysis reportedly worked before and now fails. Diagnose this before further visual implementation.

Read-only startup diagnosis (no application changes): the currently running server was started with `/tmp/evora-backend-env/bin/python`, a temporary test environment without `spacy` or `en_core_web_sm`. A synthetic sentence sent directly to the existing local text worker reproduces `NLP_MODEL_UNAVAILABLE`. Document processing requires that worker, so this startup environment cannot process text successfully. This identifies a concrete environment failure without reading or modifying the user's evidence. The running process also has no `NEO4J_PASSWORD`; case-analysis publication separately requires configured graph access. The user's particular failed-run record has not been inspected, so do not assume these are the only possible causes. Correct startup to use the complete pinned runtime and configured services when implementation resumes, then verify text processing and case analysis independently. Do not weaken model validation or substitute fabricated extraction results.

- Remove the introductory paragraph: “Create the first administrator account. Accounts and passwords stay on this workstation.”
- Remove the “About your local data” disclosure from the front page, including the database-encryption explanation and separate-original-files explanation. Put relevant storage/security information in Settings or help when implementation resumes.
- Target first-run screen: a short heading, necessary account fields, and one primary action. No explanatory introduction, reassurance, technical paragraphs, or extra information panels.
- Apply this standard across entry screens too: setup, sign-in, and account recovery. The previous workspace cleanup did not address these sufficiently.
- Keep field labels, actionable validation/errors, and the recovery-code step clear and functional. Simplify presentation without changing account or encryption behavior.
- Wait for a new instruction to build. This feedback authorizes documentation only.

Status: implementation started following user authorization. This document remains the full roadmap; the first results/navigation/chart slice below is implemented. Features not listed as implemented are still pending.

### First implementation slice

- A read-only, authenticated per-evidence results API selects completed output independently for detection, description, OCR, transcript, and structured records. Latest-attempt status and older successful output are separate; pinned historical output never silently falls back to current results.
- Per-file Results shows readable extracted values, operation states/counts, output references, source limitations, and pagination. Source records can open hash-verified original text lines; image/video detections open source regions/frame offsets; available transcript results support media seeking.
- Detections preserve face/person/plate category distinctions and do not claim identity. Standalone audio transcription is not implemented by the existing backend; the UI now makes this limitation explicit rather than offering a processing action that cannot work. Video speech and existing transcripts remain available through their existing paths.
- Primary case navigation is horizontal. Evidence/Timeline filters are contextual and collapsible. The dashboard-reference revision below replaces the initial bitmap treatment with conventional typography and outline icons.
- The analysis action has no heading, permanent completed badge, date paragraph, or analysis-details block. History is available separately; active progress and errors remain visible.
- Timeline includes a UTC activity histogram. Selecting a bucket filters exact date boundaries; undated events remain separate and chart values have an accessible table. This first chart reuses existing bounded/all-page timeline loading; server aggregation for large cases remains pending.

Validation for this slice: frontend schema/type/build checks; 408 frontend unit tests; six results API tests over HTTP/SQLite with real structured-file processing and labeled output fixtures; 30 existing observation/processing-dispatch tests; synthetic-API application browser flow; populated-result media browser checks using real hash-verified image/audio/video bytes and synthetic inference outputs; existing graph browser acceptance; and 20 additional image/video backend tests with real decoding/publication and explicit model-protocol doubles. A disposable local-account backend browser test also verifies real upload/processing, results, hash-verified source lines, timeline chart filtering, and a narrow layout without API mocks. Backend tests used an isolated temporary Python environment with the pinned OpenCV 4.14 package. This does not establish real-model accuracy or validate a complete new acquisition/transcription capability.

Still pending: durable report autosave, case-wide search, indexed/server-side chart queries, GPS/transaction/heatmap workspaces, notes/bookmarks/saved views, comparison, and broader job lifecycle extensions. The Results inspector currently integrates existing original/processing/history sections; a fully unified Results/Original/Details tab layout and stronger result-history selection remain follow-up work.

### Dashboard-reference revision

The latest user direction supersedes the bitmap visual treatment. Reference: `/home/whale2186/Downloads/SaaS Dashboard Template by Carolina Poll.pdf` (one-page dashboard image inspected locally).

Implemented presentation: slim colored global rail, compact white header, pale cream canvas, white cards with small corner radii and minimal borders, proportional sans-serif controls, purple default accent, pastel chart categories, and understated table separators. Existing saved custom colors remain respected. Dark/System modes remain available. Bitmap icon paths and monospace interface labels are removed; monospace remains appropriate for literal technical values.

The overview follows the reference's hierarchy using actual case data: four readiness metrics, activity and evidence-type charts side by side, then recent evidence. Event bars open the matching timeline date range; recent evidence opens its source inspector. No invented trends, sales metrics, or sample records are inserted into the application. Empty/error/loading states reflect available data.

Validation: the frontend build, all 408 unit tests, and the complete application browser flow pass. A disposable real backend with six processed sources also verifies populated cards/charts/tables, chart-to-timeline navigation, source inspection, mobile layout, and dark mode.

Copy cleanup: removed metric subtitles, repeated overview heading, dashboard scope footer, task explanations, repeated counts, case-list descriptions, and redundant filenames. Case description/reference and media method/provenance are available in collapsed details. Chart metadata and draft status use short labels. Errors, original source content, review state, and model-output identification remain accessible.

The earlier bitmap sections below are historical planning context and no longer describe the target appearance. The forensic functionality and backend roadmap remain applicable.

## 1. Product direction

Build a practical forensic investigation workspace using the supplied dashboard reference for its visual language. Prioritize evidence examination, useful visualizations, and a straightforward flow:

**Create case → add files → process → analyze → inspect sources → record assessments → export report.**

Every visible element must help someone navigate, understand data, or perform a task. Charts must lead to records and sources. Avoid slogans, decorative dashboards, invented metrics, unnecessary instructions, and repeated headings.

Use conventional readable typography, a slim purple global navigation rail, white cards, a warm light canvas, and useful charts/tables. Preserve customizable colors and readable evidence. Purple is the new default; do not overwrite saved user choices.

## 2. Current-state audit

This is a source-code audit of the current worktree, including previous local edits. Existing tests and screenshots document the earlier cleanup; they do not validate the proposed features below. No new runtime or usability claims are made by this planning update.

| Area | Observed implementation | Required improvement |
| --- | --- | --- |
| Analysis controls | `StartAnalysis.tsx` still shows a heading, status, Analysis details, dates, and sometimes a history selector around the action. | Leave the action alone in the header; move history and technical information into a menu. Show progress/errors only when relevant. |
| Navigation | `CaseWorkspace.tsx` places the five primary views in a left sidebar; Findings has a second tool switch. | Put primary navigation below the case header. Use the left side for contextual filters. |
| Overview | `InvestigationOverview.tsx` shows a next action and three file-readiness counts. | Add a useful activity chart and a review queue; avoid filling the screen with more totals. |
| Existing metrics | `CaseMetrics.tsx` and `metricsData.ts` implement additional counts, but the component is not mounted by another current screen. Metrics combine live evidence/entities with selected-analysis links/findings. | Reuse validated data logic selectively. Do not simply mount the old verbose metrics panel or combine incompatible scopes. |
| Timeline | `TimelineWorkspace.tsx` loads live events across pages and offers date/source/text filters and source links. It is independent of the selected analysis. | Add an event histogram, shared selection, entity/type filtering, and clear live/snapshot scope. |
| Search | Cases/evidence and finding-kind filtering operate on the current loaded page. | Provide real case-wide search/filter/sort with accurate totals. |
| Connections | Existing graph supports grouped/raw records, selection, zoom, inspection, and source references. | Improve investigation around a selected subject and reduce graph clutter; preserve raw records and grouping meaning. |
| Structured records | Parsers exist for GPS, network logs, messages, and transactions. Public events carry summaries and references, rather than all chart-ready fields. | Add typed projections/aggregations where required; never recover amounts, coordinates, or relationships by parsing summary prose. |
| Source inspection | Original text/media previews, hashes, observation references, transcripts, and citation locators already exist. Results are scattered across processing controls, modality panels, and generic observation tables. | Make a per-file Results view the default destination after processing; unify source opening/return and add comparison, bookmarks, and annotations. |
| Review | Findings support decisions/reasons; priorities support overrides/history. | Provide a clear review queue with direct source access and consistent filters. |
| Reports | Editable draft state is component-local. Tab switching retains it; case/analysis navigation and reload can discard it. Manual leave guards and export exist. | Persist drafts with authenticated access and recover them after reopening; keep versions separate. |
| Appearance | Light/Dark/System, presets, custom colors, validation, contrast adjustment, and local persistence exist. | Retain these while replacing rounded/decorative styling with coherent bitmap-inspired controls. |
| Navigation state | Active view/tool/selection primarily live in component state. | Support deep links, browser history, and restoration of working context. |

Key code references: `frontend/src/App.tsx`, `frontend/src/cases/CaseWorkspace.tsx`, `StartAnalysis.tsx`, `InvestigationOverview.tsx`, `TimelineWorkspace.tsx`, `EvidenceWorkspace.tsx`, `GraphView.tsx`, `ReportWorkspace.tsx`, `metricsData.ts`, `frontend/src/appearance/`, and `specs/openapi.yaml`.

## 3. Layout and left-panel placement

Recommended desktop layout:

```text
EVORA                                      Activity  Appearance  Account
← Cases    Case name                         [Run case analysis]  [⋯]
Overview    Evidence    Timeline    Findings    Report
──────────────────────────────────────────────────────────────────────
[Filters]         Chart / records                    Source inspector
context-specific  current investigation task         on selection
collapsible       uses the available width           resizable
```

- Move primary case navigation from the left sidebar to a horizontal row below the case header.
- Keep five primary views; do not add a permanent tab for every chart.
- Repurpose the left area as a collapsible filter panel, approximately 220–260px when space allows.
- Open a source inspector on the right. Collapse filters or use a full-width source view when three columns would make the content cramped.
- Allow resizing of the record/source split within sensible minimum widths.
- At medium widths use a Filters drawer and two working columns where practical. On narrow screens use one working view with a return action.
- Keep primary tabs keyboard accessible and horizontally scrollable where necessary; avoid an icon-only navigation rail that requires guessing.
- Preserve selected source, filters, chart range, sorting, pagination, and scroll position when visiting a source and returning.
- Put rare actions in a labeled menu. Keep frequent actions directly reachable.

Contextual left-panel contents:

| View | Useful filters |
| --- | --- |
| Overview | Date range and source scope only when its chart supports them; otherwise no panel. |
| Evidence | File type, processing state, source, upload/acquisition date, tags/bookmarks once implemented. |
| Timeline | Date/time range, timezone display, event type, source, device/account/subject, dated/undated records. |
| Findings — Review | Review state, finding type, priority where defined, source, subject. |
| Findings — Connections | Subject search, relationship type, source, grouped/raw mode. |
| Findings — Locations | Device, time range, source, accuracy/quality fields only when actually available. |
| Findings — Transactions | Account, date range, currency, amount range, recipient when present. |
| Report | Avoid forcing a filter panel; use findings selection within the editor. |

Use a visible Filters button, active-filter chips/count, Clear filters, and empty-result recovery. Persist panel open/closed preference separately from case content.

## 4. Bitmap-inspired visual system

- Crisp 1px borders, square or minimally rounded controls, flat surfaces, consistent alignment, restrained separators.
- A coherent pixel-grid icon set for navigation, source types, controls, and status. Icons should be code-native assets aligned to a grid, not generated bitmap illustrations.
- Optional bitmap-style type for short navigation/status labels only after checking readability at normal scaling. Use readable regular type for records, evidence, transcripts, forms, charts, and reports.
- Keep charts vector/canvas based and crisp at different display densities. Do not rasterize labels or evidence content for the theme.
- Use tabular numbers and monospace where useful for timestamps, hashes, addresses, and IDs.
- Teal default accent; preserve existing presets/custom color, preview/cancel/reset, Light/Dark/System, and persistence.
- Keep error/warning/success meanings independent of the chosen accent. Every state has a text or shape cue.
- Use accessible focus states and generally 44px touch targets. Compact table rows must not make buttons too small to operate.
- No fake terminal output, scan lines, glitch effects, ornamental diagrams, oversized hero areas, or decorative gradients.
- Consolidate shared styles and component ownership rather than adding another layer of CSS overrides. Inspect hardcoded media/graph colors as part of the theme pass.

Deliverable before implementation: annotated wireframes for Overview, Evidence with source selected, Timeline with chart, and Findings, shown at desktop and narrow widths. This is an implementation deliverable, not a request to build them during this planning turn.

## 5. Remove text around Run case analysis

Default header: **Run case analysis** and a compact Analysis history/menu control. No surrounding title, generic explanation, persistent completed badge, results date paragraph, or Analysis details disclosure.

- Button states: Run case analysis → Analyzing… → Run case analysis. A failed attempt gets an actionable error and Retry.
- Keep previous completed results usable while a new analysis runs. Prevent duplicate submissions.
- Put prior runs, selected-run date, algorithm/version, input references, and diagnostics inside Analysis history/details.
- Show a short stale-results notice in the results workspace when newer/reprocessed evidence is excluded. Do not hide important scope changes to make the header look cleaner.
- Read-only users should not receive an apparently actionable run button. Convey read-only status through account/access context or an accessible explanation on the disabled control.
- Before first analysis, direct users to the actual missing prerequisite. Avoid letting them enter an empty report or graph with an unrelated navigation suggestion.
- Keep the overview next action state-aware. When it duplicates the header analysis action, use a single clear primary action in that task context rather than two competing primary buttons.

## 6. Charts and forensic tools

### A. Event activity chart — first chart to build

Question: **What happened during this period?**

- Histogram of recorded events over time; sensible hour/day/week buckets based on the range.
- Select or brush a range to filter the event list. Provide equivalent date controls for keyboard users.
- Break down by event type or source when useful; show exact counts and bucket boundaries.
- Click an event to open its underlying source/observation location.
- Keep undated records available separately. A missing timestamp must never become midnight or a guessed date.
- Expose timezone and live/analysis scope concisely. Do not mix upload time with event time.

### B. Activity heatmap

Question: **When does recorded activity concentrate?**

- Day/hour heatmap filtered by device, account, source, or event type.
- Selecting a cell opens the matching records and their source references.
- Show counts with a legend and an accessible table alternative.
- Distinguish recorded counts from coverage: sparse records do not prove inactivity.

### C. Connections investigation

Question: **Which recorded subjects connect across sources?**

- Start from a selected device/account/identifier, with one-hop expansion and source filters.
- Keep disconnected or unsupported candidates out of the initial crowded view while allowing raw inspection.
- Label relationship types; click a relationship to see the exact supporting records.
- Distinguish exact identifier grouping from verified identity. A shared name/address alone must not imply one real person or device.
- Provide searchable table/list alternatives, focus/reset controls, and a persistent selected-subject context.
- Avoid unhelpful graph metrics such as an unexplained “suspicion” score.

### D. Location workspace

Question: **Where was activity recorded, and in what sequence?**

- Show timestamped GPS observations by device, with a linked chronological list.
- Click a point to inspect its original row and normalized coordinates/time.
- Separate devices and missing-time observations; do not connect unrelated samples into a route.
- Any connecting line means sample order, not a known traveled path. No invented accuracy radius, speed, or interpolation.
- Keep maps local/offline-capable by design where required. Make basemap availability explicit; external tile requests must not silently expose case locations. Choose the map package/provider during implementation after capability review.
- GPS parser support exists; typed coordinate/time projections and map integration still need implementation/verification.

### E. Transaction workspace

Question: **What recorded amounts appear by account, time, and currency?**

- Chart amounts over time, account totals, and exact supporting rows.
- Filter by account, date, currency, signed amount, and recipient where present.
- Preserve decimal precision. Never add mixed currencies or assume a conversion rate.
- Explain signed amounts according to the source format; do not infer debit/credit semantics from sign alone without a declared convention.
- Only draw account-to-account flows when a recipient relationship is present. The parser accepts optional recipient data; it must not be invented for older inputs.
- Show duplicate-source records transparently; do not silently deduplicate or double-count them as distinct transactions without a defined rule.

### F. Communication and network views

Question: **Which recorded participants/devices have activity together?**

- Message counts over time and sender/recipient records where recipients actually exist; preserve message bodies and source positions.
- Device/IP assignment history and activity by event type from supported network logs.
- Do not imply packet inspection, session reconstruction, message delivery, geolocation from IP, or recipient knowledge that the source does not provide.
- Start with linked lists/charts; add relationship views only for explicit source-supported associations.

### G. Review queue — first functional companion to charts

Question: **What needs my attention next?**

- Unreviewed findings, conflict findings, failed processing, and high-priority sources, with distinct labels and counts.
- Selecting an item opens the finding/source directly, retaining the originating queue/filter.
- Keep review decisions and reason/history accessible; provide next/previous item navigation.
- Accepting a conflict finding confirms the assessment of that finding; it does not mark conflicting evidence resolved.
- Priority remains a work-order aid. Do not relabel it certainty, truth, or guilt.

Do not build all charts into Overview. Offer specialist views inside Findings/Timeline and display a clear unavailable-data state when the source types do not support a tool.

### H. Per-file Results workspace — priority before adding more charts

Question: **What did EVORA actually do with this file, and what information did it extract?**

A completed job is not an adequate result screen. Opening processed evidence must show readable extracted information next to the source, without requiring users to understand observation schemas or processing-run IDs.

Recommended layout:

```text
File name                           [Process / Reprocess] [History]
Results       Original       Details
────────────────────────────────────────────────────────────────
Source image / player / document      Extracted results
highlighted region / time / row        click result → source location
```

- Results is the default for a processed file; Original remains directly reachable. Before processing, show the original and the applicable processing action.
- A compact status strip identifies what ran: detection, OCR, transcription, structured parsing, scene description, or entity extraction. Each operation can be completed, running, failed, not run, unsupported, or unavailable.
- Render result sections only for applicable operations. Do not show empty OCR/transcript/detection blocks on every source.
- Separate extracted source content, model-generated descriptions, and investigator annotations. Show concise AI/automatic labels where needed; place technical provenance under Details.
- Distinguish processing success from available output: “Completed, no transcript returned” differs from “Transcription not run” and “Transcription failed.” Do not invent zero detections when an operation never ran.
- Result counts refer to the selected output and defined units. Repeated video detections are not automatically distinct people; extracted fields are not distinct source rows.
- Every result has a stable source locator and evidence/processing reference. Selecting it highlights or seeks to the exact supporting region, interval, page, or row.
- Unsupported previews fall back to the original download and readable extracted results. Never pretend a plain-text preview can render every document format.

| Evidence | Results to show | Source interaction and limits |
| --- | --- | --- |
| Image | Detection list with thumbnail crops and original category labels; visible-text OCR; generated scene description when run; extracted attributes only if provided. | Select a detection to highlight its original bounding box. Select OCR to highlight its region only if region coordinates exist; otherwise show full-image attribution. Keep the original unchanged. |
| Audio | Timestamped transcript, text search, language when returned, uncertain/inaudible segments, completed duration or coverage when available. | Select text to play its source interval. An optional waveform can assist seeking but is not evidence of speaker identity. Distinguish original machine transcript and human corrections. |
| Video | Sampled-frame strip with timestamps, scene descriptions, per-frame detections/OCR, transcript when run, and candidate tracks if supported. | Select a result to seek to its actual frame/time. Show sampling interval, analyzed coverage, and missed/failed samples concisely. Do not imply continuous observation, continuous tracking, or events between sampled frames. |
| Text/document | Extracted text, entities such as names/addresses/accounts/dates where supported, and extraction gaps or unsupported content. | Select an entity to highlight its exact text span/page when available. Keep an extracted name separate from a verified person. Image-only documents need an explicit supported OCR path. |
| Messages | Readable messages, sender, recipient only if present, recorded timestamps, mentioned identifiers, and related records. | Open the exact source row/message; preserve original body and timestamp. Do not infer a recipient or message delivery. |
| Network/mobile logs | Parsed row table with device, IP, activity, timestamps, and supported relationships. | Select a row to inspect the original record. Do not imply packet capture, full browsing history, or unsupported fields. |
| GPS | Coordinates, device, recorded/normalized time, mapped points, and chronological list. | Select a point/row to open its source record. Unavailable coordinates, timestamps, and accuracy stay unknown. |
| Transactions | Exact recorded amount/currency, account, timestamp, recipient if present, and flagged records with reasons. | Select a transaction to inspect its original row. Preserve decimal precision and currency separation; avoid invented counterparty links. |

**People and identity:** label observations such as “Person detection 1” or “Face region 2,” with “Identity unknown.” These identifiers are local to their source/output and must not imply the same individual across files. A face detection and a person detection can overlap; retain the actual detector class and avoid misleading combined labels such as “Person / Face.”

- The current code supports detections and candidate associations, not verified person identification. Do not promise names or biometric matching from a person/face box.
- A name extracted from image text or a document is a text mention, not the identity of the person shown.
- If an investigator supplies an identity label, record it as an investigator annotation with author, reason, and source links; keep the original automatic result separate.
- Speaker separation, if introduced, uses anonymous speaker labels only when supported by real diarization output. Do not manufacture speaker labels or identify a speaker from transcript text.
- Cross-frame tracks are geometric candidate associations. Counts of tracks, boxes, faces, and unique individuals are different quantities and must be labeled accordingly.

**Data and implementation requirements:** introduce a typed result manifest describing operations attempted, capability availability, status, output counts, locators, coverage, and limitations for each evidence/run. Do not infer this manifest merely from absent observations or the currently configured model. Audit whether the present storage records enough operation status and coverage; extend it where necessary.

A file may have different completed outputs for detection, OCR, transcription, or interpretation. Define explicit selection of compatible operation outputs; do not accidentally replace an existing transcript with a newer detection-only output. Show which output produced each visible section. Historical citations must reopen their referenced output, and newer results must not silently replace them.

Source actions remain concise: Process/Reprocess, applicable operation selection, History, and original download. Results should load automatically on confirmed completion. Processing settings and provider configuration belong in an expandable action area; specific hosted-processing consent stays visible before a request.

Acceptance: processing a supported image/audio/video/structured file produces a readable Results view; users can state what ran and what was extracted, select a result to inspect the exact source, distinguish absent data from unperformed/failed operations, and recognize that a detection does not identify a person. Test this with actual populated results, not only empty panels or completed-job badges.

## 7. Practical workflow improvements

| Priority | Improvement | Required behavior |
| --- | --- | --- |
| P0 | Durable report drafts | Save scoped to authenticated user/case/analysis; show Saving/Saved/Failed; recover after reload/reopen; prevent cross-user leakage. Use existing protected backend storage conventions. |
| P1 | Case-wide search/filter/sort | Query all accessible records with matching totals, not only the loaded page. Include appropriate evidence text/metadata and scope labels. |
| P1 | Shared investigation state | Chart, records, source viewer, and filters share the same context. Back returns to the prior selection and position. |
| P1 | Addressable navigation | Deep-link case, tool, selected source, and relevant filter state. Support browser Back/Forward; keep sensitive content out of URLs. |
| P1 | Source comparison | Two source viewers with readable labels; optional linked time navigation only when comparable timestamps exist. No changes to originals. |
| P1 | Bookmarks | Save a finding, row, passage, transcript interval, or frame with its exact source/run locator. |
| P1 | Notes and annotations | Investigator-authored notes tied to evidence and analysis context; preserve author and edit history; keep separate from extracted facts. |
| P2 | Saved views | Restore filters, column choices, chart range, and scope, with permission checks and unavailable-record recovery. |
| P2 | Table usability | Sorting, column visibility, exact-value copy, multi-selection where an actual bulk action exists, keyboard navigation, and useful empty states. |
| P2 | Chart/record export | Export selected records/charts with case, filter, timezone, analysis scope, and source references; respect access controls. |

Evidence intake should auto-detect supported types, prefill editable labels, preserve originals, show per-file results, and retry only relevant failures. Batch processing should remain available while users work elsewhere. Keep specific consent for hosted processing and do not turn chart interactions into implicit model requests.

Media/transcript work should preserve source fidelity: visible OCR/AI authorship, exact frame/interval navigation, original versus corrected transcript distinction, and unsupported-format recovery. Avoid duplicate preview/download/process buttons serving the same action.

## 8. Data and API requirements

Before building a visualization, define its record set, scope, aggregation unit, and drill-down contract.

- Typed projection fields for event timestamps, subject references, coordinates, amounts/currencies, and participants as applicable. Include evidence, observation, and processing-run references.
- Aggregation/query endpoints for large cases: histogram buckets, heatmap cells, filter facets, matching totals, and paginated drill-down rows. Existing client-side all-page loading may be reused for bounded cases but must not become the large-case strategy by default.
- Validate case membership, permissions, pagination, selected analysis identity, and total consistency before displaying complete aggregates.
- Distinguish a live evidence/processing view from a selected immutable analysis snapshot. If a view cannot be pinned through current APIs, label it live rather than implying snapshot consistency.
- Use event IDs for event counts and a defined transaction/observation identity for other charts. Multiple extracted fields from one row are not multiple events.
- Distinguish unknown/unavailable values from zero. Keep malformed/unsupported records inspectable where appropriate, without injecting them into valid chart totals.
- Preserve source time and normalized time. A display-timezone change must not mutate recorded timestamps.
- Cancel obsolete queries on scope changes; prevent late responses from restoring a previous case/session.
- Cache by case, analysis/live revision, filters, and access context. Refresh on relevant completed processing/review changes without hiding active errors.
- Define authenticated persistence for drafts/bookmarks/notes/saved views, including session-expiry behavior and account isolation.
- Inspect existing settings/account permissions before exposing new configuration; personal appearance stays available independently of administrator controls.

### Backend delivery priorities

The current backend already has FastAPI endpoints, local SQLite/SQLCipher storage, access checks, immutable processing outputs, hashes, audit records, model provenance, supported file parsers, and analysis snapshots. Extend these mechanisms rather than replacing the backend or adding a service per chart.

| Order | Backend change | Deliverable |
| --- | --- | --- |
| 1 | Per-operation extraction results | A typed results endpoint/manifest with attempted operation, state, structured output, source locator, output version, and actual coverage. Select outputs per operation so a detection-only run does not hide an earlier transcript/OCR result. |
| 2 | Persistent working records | Authenticated tables/endpoints and migrations for editable report drafts, bookmarks, notes, and saved views; revisions/concurrency handling, account/case/run scope, save failures, and recovery tests. Model-generated report provenance already exists; it is not a substitute for saving user edits. |
| 3 | Search/query layer | Indexed case-wide text/OCR/transcript/record search and metadata filters/sort, pagination, matching totals, facets, and exact source positions. Verify encrypted-storage search support before selecting an indexing implementation. |
| 4 | Structured chart data | Typed event/GPS/transaction/participant projections, server-side histogram/heatmap/summary aggregations, stable scopes, and drill-down queries. Preserve decimal amounts and separate currencies. |
| 5 | Duplicate intake lookup | Same-case hash/size lookup with an explicit duplicate response/warning, preserving separate acquisition records. Do not expose matches in inaccessible cases or silently merge originals. |
| 6 | Job lifecycle extensions | Extend persisted job state with operation/stage/coverage, bounded concurrency and resource limits, and an explicit retry/interruption policy. Processing currently uses single-process background work and marks interrupted work; analysis has restart recovery. Audit both before promising resumable or cancellable jobs. |
| 7 | Comparison and audit coverage | Compare versioned outputs by stable source/operation references; extend the existing append-only audit mechanism to new working-record mutations and relevant exports. Do not recreate existing audit/provenance infrastructure. |

For every addition: update the OpenAPI contract and generated frontend types, add migrations and focused backend tests, verify permission boundaries and immutable originals, and run a disposable real-backend integration test. External queues, search servers, face identification, speaker identification, and new acquisition formats are separate decisions, not implied requirements for this revision.

## 9. Screen composition

| Screen | Default content | On demand |
| --- | --- | --- |
| Cases | Search, recent/accessible cases, New case | Case details and administration |
| Overview | Current next action, compact file readiness, one activity chart, short review queue | Chart filters, failures, detailed scope |
| Evidence | Files, Add files, Process files, per-file Results beside original source | Acquisition/hash metadata, format help, operation selection, processing history |
| Timeline | Activity chart and matching event list | Heatmap, advanced filters, raw time/normalization details |
| Findings | Review queue and findings | Connections, subjects, locations, transactions, communications/network views, Ask |
| Report | Details, selected findings, editable draft, preview/export, save status | Model/version/source coverage, raw export text, history |
| Appearance | Mode, accent presets/custom color, preview/apply/reset | Minimal contrast-adjustment explanation |

Do not display every specialist tool at once. Keep tool names short and indicate unavailable data without an unexplained disabled button. Keep AI assistance optional to core source inspection and reporting.

## 10. Implementation order

1. **Header and layout:** remove text around Run case analysis; compact history menu; horizontal primary navigation; collapsible contextual filters; bitmap design tokens/components.
2. **Per-file results:** typed operation/result manifest; readable image, audio, video, document, and structured-source output; exact-source navigation; operation-specific errors and output history.
3. **Core data navigation:** case-wide queries, shared filters, source-return behavior, URL/history state. Begin persistence design and report autosave early.
4. **Activity and review:** interactive event histogram, linked records, short review queue, overview integration. Validate the full primary journey.
5. **Connections and comparison:** subject expansion, relationship inspection, side-by-side evidence, bookmarks/notes.
6. **Structured specialist views:** GPS, transactions, communication/network activity, then heatmap and saved views. Add typed projections before rendering.
7. **Reports and final validation:** complete durable draft recovery, selected-view exports, accessibility/performance testing, and realistic investigator walkthroughs.

Do not treat the visual refresh as completion of the forensic tools. Do not implement new charts until their data meaning and source navigation are defined. User authorization to start building was given after this plan; continue implementation in the sequence above, without treating this first slice as completion of the whole roadmap.

## 11. Acceptance checklist

- The main journey is achievable without reading a tutorial; every prerequisite/failed step has a direct recovery action.
- Run case analysis has no persistent surrounding explanatory block; running/errors and stale-result context remain understandable.
- Primary navigation is below the case header; the left panel filters the current task and collapses cleanly.
- Bitmap style is coherent at normal display scaling, with readable evidence and chart labels. No evidence pixels or text are degraded for styling.
- Default teal and all custom modes remain usable; normal text meets 4.5:1 contrast, large text/meaningful controls 3:1, with non-color status cues.
- Every processed evidence type shows what operations ran, what was extracted, and source-linked results. Operation not run, unsupported, failed, empty, and partial results are distinct. Person/face detections and speaker labels do not assert identity.
- Every chart selection opens or filters the exact underlying records and supports source inspection/return.
- Counts match full query scope, including records beyond the first page; partial/missing data is never labeled a complete result.
- Timezones, undated records, decimal amounts, separate currencies, absent recipients, and source duplicates behave according to defined semantics.
- Original evidence, integrity checks, citations, uncertainty, AI labels, sharing consent, human-review history, and role restrictions remain intact.
- Drafts/notes/bookmarks recover correctly and remain isolated across users, cases, and analyses. Save failures and expired sessions are handled explicitly.
- Test empty, loading, running, partial success, failed processing, no model, unsupported source type, read-only access, stale analysis, and lost-connection states.
- Validate 360/768/1280/1440px layouts, keyboard-only operations, focus restoration, filter drawers, reduced motion, accessible chart tables, and large-case performance.
- Run relevant type/build/unit/browser checks with representative structured fixtures, then verify against a disposable real backend. Synthetic transport success does not prove backend integrations.
- Conduct representative task walkthroughs before calling the forensic workflow complete. Record observed friction and unresolved limitations.

## 12. Scope boundary

This revision is a plan, not an implementation or a claim that all capabilities exist. EVORA currently processes supported exported files; this plan does not promise disk imaging, deleted-file recovery, physical-device acquisition, packet capture, verified identity matching, or an external forensic-format integration without separate work and validation.

The next implementation should start with the compact analysis controls, horizontal navigation/context filters, per-file extraction results, and one genuinely interactive activity chart—not another decorative dashboard.
