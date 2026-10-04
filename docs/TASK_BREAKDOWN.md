# EVORA module-to-task breakdown

**Status:** planned tasks, not implemented. The four modules are *ownership boundaries*, **not** four agent prompts. The full initial feature goal in `docs/FEATURE_SCOPE.md` is unchanged; complete timeline reconstruction and optional Jev integration are future enhancements. Task IDs are stable references; `F1/P1/A1/U1` in older notes mean *milestones*, not single agent runs.

## How to use this catalog

- **One row = one bounded agent assignment, one fresh agent session, one short-lived branch/PR.** If a row still requires several unrelated routes, formats or algorithms, split it further when filing the issue. Never prompt an agent to “implement M2” or “finish A1.”
- One person works through the rows for their assigned module; an agent takes only one bounded row at a time. Give the agent the row ID, shared spec commit, source/target file paths *after the skeleton exists*, fixture and acceptance check. The common prompt and handoff rules are in `docs/AGENT_TASKS.md`.
- A `Depends on` entry is needed for *real integration*. Independent implementation may begin earlier using schema-derived tests, but the task is not **Complete** until tested against the merged producer. No concurrent edits to shared project scaffolding, DB migrations, `specs/openapi.yaml`, or `docs/ROADMAP.md`; one of the four coordinates these shared edits.
- The `Contract` column refers to **existing proposed OpenAPI operationIds or schemas**, not permission to invent endpoints. A task needing a new wire field/operation coordinates a contract change with affected producer/consumer modules before implementation. Later format files beyond the three CSVs need a documented synthetic fixture before code; they remain in full project scope.
- Branch pattern after the common base is published: `feat/<lowercase-task-id>-<short-name>` (e.g. `feat/f03-evidence-upload`). PRs go to the chosen integration base; `main` is not edited directly. Each person handles their module through bounded tasks, not a long-lived branch with many unrelated features.

## Common-base setup — no four-way implementation from divergent drafts

| ID | Module / coordination | Deliverable / dependency | Pass condition |
|---|---|---|---|
| G00 | Four module contributors; one coordinates integration | Record `specs/openapi.yaml` and auth/privacy/case/format choices needed by first tickets; publish one common base | All **four** people branch from the same spec commit; no TBD field required by their first ticket |
| G01 | M1 contributor with shared-file coordination | One shared FastAPI/SQLite backend skeleton, backend module/package layout and backend test command | Backend starts, trivial test runs; no duplicate project skeletons or domain features |
| G01B | M4 contributor with shared-file coordination | React/TypeScript skeleton and one shared-spec client generation/type-check command | UI starts, generated client compiles; no hard-coded fake backend responses |
| G01C | One of the four coordinates setup checks | Windows setup instructions and CI commands for skeletons | Clean install/build/test on a teammate's Windows machine and CI; no paid service |
| G02 | M3 contributor | Versioned triage factor policy: inputs, ranges, default/missing factor behavior, weights, tie-break order and candidate-vs-verified links | Review against synthetic fixture; no numeric claim or forensic-standard claim without tests |
| G03 | M4 and M1 contributors | Decide local vs remote Q&A provider, permitted evidence processing, secrets/cost and fallback behavior | Privacy policy documented; no real evidence leaves system by default |

## M1 — Evidence Foundation (`Fxx`)

| ID | One-task scope | Depends on | Contract | Acceptance for this PR |
|---|---|---|---|---|
| F00 | Authenticate a request and enforce a case-access guard (no evidence logic) | G00, G01 | `bearerAuth`, `ApiError` | Missing/invalid identity rejected; foreign-case ID indistinguishable from missing case |
| F01 | Persist and read one case | F00 | `createCase`, `getCase`, `Case` | New case round-trip with stable UUID; invalid title rejected; other actor denied |
| F02 | List authorized cases with pagination | F01 | `listCases`, `CasePage` | Only accessible cases returned, correct `total/limit/offset` |
| F03 | Stream one upload to private immutable storage and hash original bytes | F01 | `uploadEvidence`, `Evidence` | SHA-256 and size match input; original bytes unchanged; invalid/oversize/unsafe filename rejected |
| F04 | Read evidence metadata and list case evidence | F03 | `getEvidence`, `listEvidence` | Case-scoped records, pagination and not-found behavior tested |
| F05 | Download authorized original bytes | F03, F00 | `downloadEvidence` | Round-trip byte/hash match; traversal and foreign-case reads rejected |
| F06 | Record append-only source/provenance and audit events for intake | F03 | `AuditEvent` | Actor, action, target and timestamp recorded; no evidence contents/secrets in logs |
| F07 | Expose case audit-event list | F06 | `listAuditEvents`, `AuditPage` | Case isolation and pagination tested; logged actions visible |
| F08 | Add processing-run audit hook | F06, P04 | `AuditEvent` | Actor, Evidence ID and parser version recorded on success/failure without claiming failed work completed |
| F08B | Add analysis-run audit hook | F06, A05 | `AuditEvent` | Actor, run ID and algorithm version recorded without logging private outputs |
| F08C | Audit regression suite for landed review/override APIs (which must already write audit events) | F06, U08, U09 | `AuditEvent` | Review/override actor, action and reason recorded exactly once; no false success event |
| F09 | Cross-case access and error regression suite for M1 routes | F00, F05, F07 | Existing M1 operations only | Every M1 read/write path has foreign-case, unauthenticated and nonexistent-ID checks; each other module tests its own routes in its task PRs |

## M2 — Multimodal Evidence Processing (`Pxx`)

| ID | One-task scope | Depends on | Contract | Acceptance for this PR |
|---|---|---|---|---|
| P01 | Parse `fixtures/synthetic-case/network.csv` into source-located candidate observations | G01; F05 for live use | `Observation` | Known device/IP/time and row locator match fixture; invalid header/row rejected |
| P02 | Parse `fixtures/synthetic-case/gps.csv` into source-located candidate observations | G01; F05 for live use | `Observation` | Device/time/coordinates match fixture; bad coordinates/zone handled explicitly |
| P03 | Normalize source timestamps and GPS coordinates without losing raw values | P01, P02 | `Observation` | Parsed UTC/time-zone/coordinates and original values coexist; missing/ambiguous zone recorded |
| P03B | Resolve *candidate* identifier keys and entity records | P01, P02, P03 | `Observation`, `Entity` | `D-7` and `D-8` remain distinct; source IDs retained; no inferred person identity |
| P03C | Project source-backed events from parsed rows | P01, P02, P03 | `Event` | Event/time/participants cite observation/Evidence IDs; invalid timestamp not fabricated |
| P04 | Implement one processing-run lifecycle | F05, P01, P02, F00 | `startProcessing`, `getProcessingRun`, `listProcessingRuns` | Queued→completed/failed runs pollable; duplicate key behavior, case isolation, unsupported format checked |
| P04B | Expose source-backed observation list | P04 | `listObservations` | Case/evidence filters and pagination correct; only completed-run observations visible |
| P05 | Add entity list view derived from source-backed observations | P03B, P04B | `listEntities` | Every candidate cites source Evidence/Observation IDs, no cross-case leakage |
| P05B | Add event list view derived from source-backed observations | P03C, P04B | `listEvents` | Each event cites source Evidence/Observation IDs, no cross-case leakage |
| P06 | Parse `messages.csv` body for *candidate* device mentions | P04; G00 first format selected | `Observation`, `Entity` | `D-7` and `D-8` mentions retain row/body source; co-mention is not identity or proof of ownership |
| P07 | Parse one agreed document/text format (not OCR) | P04; agreed fixture | `Observation` | Page/offset or line locator, raw text, bad encoding/empty file behavior |
| P08 | Extract text by OCR from one agreed scanned document/image format | P07; agreed fixture/model/privacy | `Observation` | Text plus page/region, processor version and confidence; failure/false-positive sample |
| P09 | Detect one agreed image object/entity category | P04; agreed fixture/model/privacy | `Observation`, `Entity` | Bounding source region and uncertainty; no automatic named-person identification |
| P10 | Extract video frames/observations from one agreed CCTV format | P09; agreed fixture/limits | `Observation`, `Event` | Frame/time locator, version, resource limit and failed-video behavior |
| P11 | Parse one agreed mobile-record format | P04; agreed fixture | `Observation`, `Event` | Device/event/time traceability; invalid layout fails honestly; no physical acquisition |
| P12 | Parse one agreed transaction CSV format | P04; agreed fixture | `Observation`, `Event` | Account/amount/currency/time source retention; malformed/negative boundary tests |
| P13 | Add text candidate-entity extraction for one agreed document/message format | P06 or P07; agreed labeled fixture | `Entity` | Candidate identifiers linked to source spans and Evidence IDs; measure false matches |
| P13B | Add text event extraction for one agreed document/message format | P13; agreed labeled fixture | `Event` | Event/time linked to source spans and Evidence IDs; ambiguous time not invented |
| P14 | Record parser/model provenance per output | P04, relevant adapter | `ProcessingRun`, `Observation` | Each output's `processing_run_id` resolves to a run with version and Evidence ID; no unidentified model result |
| P14B | Dispatch one uploaded file to its supported adapter or reject it | P04, P01, P02 | `ProcessingRun` | Declared kind/type matched to supported adapter; unsupported input fails explicitly |
| P14C | Make processing failures/retries atomic | P04, P14B | `ProcessingRun` | Failed run leaves no completed partial results; same idempotency key has stable result |

## M3 — Fusion and Adaptive Triage (`Axx`)

| ID | One-task scope | Depends on | Contract | Acceptance for this PR |
|---|---|---|---|---|
| A01 | Construct case-scoped evidence/entity/event graph nodes from normalized observations | P03B, P03C; fixture test doubles allowed | `Graph`, `GraphNode` | Stable node references and source Evidence IDs, no cross-case nodes |
| A02 | Add an evidence-backed *candidate* link rule for shared identifiers | A01 | `GraphEdge`, `Finding` | Link cites observations/Evidence IDs; weak match stays candidate; unrelated `D-9` unlinked |
| A03 | Define and test relevance factor calculation | G02, A02 | `TriageFactor` `relevance` | Deterministic `[0,1]` value, reason/source IDs and missing-data behavior |
| A03B | Define and test graph-connectivity factor calculation | G02, A02 | `TriageFactor` `connectivity` | Deterministic `[0,1]` value and source-backed explanation; no circular score dependency |
| A04 | Aggregate available factors into versioned score and priority band | A03, A03B, G02 | `TriageResult`, `Priority` | 0–100 sum, correct bands/ties, documented missing-factor policy and provenance; later factors added by their own PRs |
| A05 | Persist/poll one analysis-run lifecycle | A01, A02, F00 | `startAnalysis`, `getAnalysisRun`, `listAnalysisRuns` | Completed/failed states, idempotency, case isolation; partial outputs hidden |
| A05B | Expose latest completed graph/findings | A05 | `getGraph`, `listFindings` | Latest completed snapshot and evidence-backed links; pending run does not leak partial results |
| A06 | Expose latest triage and append-only per-evidence history | A04, A05 | `listTriage`, `getTriageHistory` | Not-scored state before run; history remains after new run; automated score separate from override |
| A07 | Add `messages.csv` co-mention candidate link and rerun | A02, A05B, A06, P06 | `GraphEdge`, `TriageResult` | `D-7`/`D-8` link changes an earlier item's factors/priority; prior run retained; no guilt/identity claim |
| A08 | Add independent-source corroboration factor/finding | A02, G02 | `Finding`, `TriageFactor` | Same source counted once; independent support cites sources; counterexample tested |
| A09 | Add source-quality/uncertainty policy to findings and triage | G02, A04 | `Finding`, `TriageFactor` | Extraction confidence not conflated with source reliability; missing quality disclosed |
| A10 | Detect one supported potential conflict rule | A02; labeled positive/negative fixture | `Finding` kind `conflict` | Time-zone/clock uncertainty considered; conflicting evidence cited, no source declared false |
| A11 | Detect one evidence-gap rule | A05; labeled fixture | `Finding` kind `gap` | Gap bounded by observed sources; absence not reported as proof of non-occurrence |
| A12 | Compute connected evidence clusters | A02 | `Finding` kind `cluster` | Deterministic membership, each cluster cites relevant Evidence IDs |
| A12B | Derive cluster review order from scored evidence | A12, A04 | `Finding` kind `cluster` | Sort deterministic and explainable; no new unexplained scoring system |
| A13 | Add one deterministic anomaly detector for an agreed structured format | P01 or P12; labeled fixture | `Finding` kind `anomaly` | Positive and false-positive controls; abnormal is not criminal |
| A14 | Represent one pair of alternative hypotheses with support and contradiction | A02, A10; coordinate a field change across affected modules if structured missing-data representation is needed | `Finding` kind `hypothesis` | Both alternatives shown with supporting, contradicting and missing data; no invented wire fields |
| A15 | Explain one finding/priority from actual contributing inputs | A04 and one finding rule | `Finding`, `TriageResult` | Every displayed reason maps to real rule/factor/source; removing input changes explanation |
| A16 | Retrieve case-filtered source passages/observations for Q&A (not prose generation) | P04B, A05B, F00 | `CaseQuestion`/`CaseAnswer` support | Relevant source IDs, source locations and case isolation; unsupported query returns no invented citation |

## M4 — Investigator Application (`Uxx`)

| ID | One-task scope | Depends on | Contract | Acceptance for this PR |
|---|---|---|---|---|
| U01 | Configure authenticated API base URL and typed client in the shared frontend skeleton | G01B, F00 | `specs/openapi.yaml` | Generated client type-check passes; error and auth handling shared, no hard-coded tokens |
| U02 | Case list UI | U01, F02 | `listCases`, `getCase` | Real API data, loading/empty/error states, actor sees only own cases |
| U02B | Case-creation UI | U02, F01 | `createCase` | Valid/invalid title behavior and created case appears in list |
| U03 | Upload and metadata UI for one file | U01, F03, F04 | `uploadEvidence`, `getEvidence` | Real bytes upload; size/type failure visible; ID/hash metadata displayed |
| U04 | Original evidence download/detail UI | U03, F05 | `downloadEvidence` | Evidence click-through retrieves original authorized bytes; no persistent client cache |
| U05 | Processing-run status UI | U03, P04 | `getProcessingRun` | Queued/running/failed/completed states; no fabricated result |
| U05B | Extracted observation UI | U05, P04B | `listObservations` | Row/source references and raw/normalized values with empty/error states |
| U06 | Priority list UI | U01, A06 | `listTriage` | Not-scored/score/override states distinct; source links correct |
| U06B | Per-item priority explanation/history UI | U06, A06 | `getTriageHistory` | Reasons, contributing factors and previous runs shown; no overwrite of history |
| U07 | Graph UI | U01, A05B | `getGraph` | Graph edge click-through reaches supporting original Evidence IDs |
| U07B | Finding detail UI | U07, A05B | `listFindings` | One finding opens with supporting/contradicting IDs and uncertainty |
| U08 | Human finding-review API | A05B, F06, F00 | `reviewFinding`, `listFindingReviews` | Accepted/rejected/needs-investigation action audited with actor/reason; prior reviews retained |
| U08B | Human finding-review UI | U07B, U08 | `reviewFinding`, `listFindingReviews` | Investigator sees previous decisions and can submit reasoned review against real API |
| U09 | Manual priority-override API | A06, F06, F00 | `setPriorityOverride`, `PriorityOverride` | Effective priority changes; automated history immutable; actor/reason audited |
| U09B | Manual priority-override UI | U06B, U09 | `setPriorityOverride`, `PriorityOverride` | Computed and effective priorities shown separately; reason required |
| U10 | Grounded case-question endpoint with unsupported-answer path | G03, A16, F00 | `askCaseQuestion`, `CaseAnswer`, `AnswerCitation` | Each factual claim cites same-case Evidence ID and source locator; unsupported identity question returns no factual claim and no citations |
| U11 | Question/answer UI with citations and uncertainty | U10, U04 | `askCaseQuestion` | Claim/source-locator links and unsupported state visible; no uncited claims rendered as verified facts |
| U12A | Conflict panel | U07B, A10 | `listFindings` kind `conflict` | Conflict uncertainty and source links with empty/error states |
| U12B | Gap panel | U07B, A11 | `listFindings` kind `gap` | Missing evidence is not shown as proof of non-occurrence |
| U12C | Cluster panel | U07B, A12B | `listFindings` kind `cluster` | Cluster membership and source links with empty/error states |
| U12D | Anomaly panel | U07B, A13 | `listFindings` kind `anomaly` | Abnormal is not displayed as guilt; source links visible |
| U12E | Hypothesis panel | U07B, A14 | `listFindings` kind `hypothesis` | Alternatives show support/contradiction/missing data without invented fields |

## Cross-module integration and evaluation (`Ixx`, coordinated by one of the four)

| ID | One-task scope | Depends on | Contract | Acceptance for this PR |
|---|---|---|---|---|
| I01 | Contract smoke suite for first two synthetic CSVs | F05, P04B, A05B, A06, U02, U05B, U06, U07 | Accepted OpenAPI + fixture | Intake→processing→initial graph and priority through real API/UI, case isolation and failure paths |
| I02 | Adaptive tracer with synthetic message | I01, P06, A07, U06B | `docs/INTEGRATION.md` | Initially disconnected evidence becomes candidate-linked; earlier rank/reasons and history change visibly in UI |
| I02B | Human review and override tracer | I02, U08B, U09B, F08C | `docs/INTEGRATION.md` | Review/override actor and reason audited; computed score/history unchanged |
| I02C | Grounded question/answer tracer | I02B, U10, U11 | `docs/INTEGRATION.md` | Supported question cites claim/source locators for same-case evidence in UI; unsupported identity question returns no claim/citation |
| I03 | Reproducible Windows and CI verification | G01C, I02C | All module test commands | Clean install/build/test on Windows and CI with no paid service or real evidence |
| I04 | Labeled extraction/link evaluation | P13B, A02; synthetic/public labels | Evaluation protocol | Precision/recall/F1 with sample counts, false positives and actual executed metrics |
| I05 | Triage ranking evaluation | A07; labeled fixture | Evaluation protocol | Top-k, precision@k/MRR and rerank changes actually measured |
| I05B | Conflict/gap/anomaly evaluation | A10, A11, A13; labeled fixture | Evaluation protocol | True/false positives and missed cases reported per detector |
| I05C | Grounded-answer evaluation | U10; labeled questions | Evaluation protocol | Citation correctness and unsupported-claim rate actually measured |
| I06 | Threat, provenance and research limitations report | F09, F08, F08B, F08C, I03, I04, I05, I05B, I05C | Full research scope | Real limitations, privacy restrictions, algorithm/version logs; no admissibility or originality overclaim |

**Future-only tasks (not dependencies for the initial project):** full timeline reconstruction/visualization, optional Jev-assisted candidate resolution or citation verification after privacy/evaluation approval, physical acquisition, disk imaging, live banking integration and court-admissible deployment. Keep Jev behind an optional adapter; core graph, scoring and Q&A must work without it.

## Handoff / completion invariant

Every PR identifies one task ID, shared contract commit, assigned module/person, exact changed files, tests and real results, upstream interfaces consumed, downstream interfaces produced, and next unblocked ticket. If an agent cannot finish its one row in a reasonable reviewable diff, stop after a tested vertical slice and file a follow-up ticket; never label the whole module **Complete** on the strength of one row. Coordinate `docs/ROADMAP.md` edits with the person handling integration so task status is not overwritten by parallel agents.
