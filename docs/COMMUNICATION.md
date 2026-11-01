# EVORA cross-module decision and handoff queue

Four people each work on one module; one also coordinates integration. This file is a queue for exact questions/mismatches, **not another API authority** or permission to rewrite another module. The 0.3.0 spec/docs are a coordination-branch draft; Git history and the remote ref establish publication state, not this document. The application does not exist yet.

## Use

1. Record task, operation/schema, observed versus required behavior, affected producer/consumer, proposed bounded correction and fixture/test. Avoid private evidence, credentials, raw model prompts/responses and personally identifying case data.
2. Affected module contributors choose one compatible behavior; one person synchronizes shared edits alongside their module. There is no personnel title, fifth member or signoff ceremony.
3. Wire changes go into `specs/openapi.yaml`; internal policy goes into versioned policy/task acceptance. Update producer/consumer/types/fixtures/tests together. A queue comment does not change the API.
4. On implemented code, file a bounded corrective task rather than a module rewrite. Remove verified resolutions from the open queue; preserve their policy/test/PR/Git record. Serialize queue edits or submit in PRs.
5. A dependent task cannot guess an unresolved policy. Unaffected scoped work/review/setup and schema-derived test doubles can proceed; integrated completion requires real producers.

Entry shape: `ID | affected tickets/modules | exact question | versioned resolution + actual proof needed`.

Phase/checkpoint membership and promotion rules live only in [ROADMAP.md](ROADMAP.md). Include the affected checkpoint on new queue entries; an open decision blocks its dependent row, not an entire unrelated phase.

## Open gates

| ID | Affected tickets/modules | Exact question | Resolution and proof needed |
|---|---|---|---|
| C-03 | G00/F00/F01/U01; all case APIs | Bearer auth exists in the wire contract, but issue/expiry/revocation, case membership, local test identities and UI token handling are not chosen | Record a safe provider/local synthetic-only policy; test missing/invalid/expired identity, two actors/cases, foreign IDs and no leaked existence; no shared production token |
| C-04 | F03/P04/P14B/P14D; M1/M2 | CSV byte/row limits, BOM, missing/extra columns, malformed rows and kind/content validation; 415 before run versus accepted failed run | Record first-format policy and actual valid/malformed/unsupported/oversized/retry tests; later adapters choose documented layouts/models/limits before their rows |
| C-05 | G02/A03–A19/I02/I05/I07/I07B; M3 with M2/M4 | Exact factor functions/quality/count/confidence/missing inputs, independence/weights/bands/ties, anomaly mapping and goldens remain open | Version actual scoring policy and positive/counterexamples; prove new-upload, detector feedback and existing-evidence reprocessing change earlier ranks with faithful explanations/history; no silent new factor enum |
| C-06 | G03/A16B/U10B/U10C/U11B/I05C/F08E; M3/M4/M1 privacy | Approved LLM provider/model, retrieval/privacy boundary, prompt versions, verification thresholds and fallback | Record policy and exercise approved generation + verification; no-paid CI adapter labeled test-only; same-case claim locators, unsupported zero citations and private provenance audited without raw public logs |

Module owners and integration coordination are confirmed by GitHub handle in [ROADMAP.md](ROADMAP.md#module-assignment-and-live-task-state). G00 now records the user's exact common-base/shared-task handoff below; later task handoffs, shared G/I assignees and tested package/Windows/Neo4j/model setup remain open readiness items. Ownership does not imply G00 completion or installation success.

## G00 common-base handoff — 2026-10-18

The user explicitly assigned **G00 / Checkpoint 0 / whale2186** on `feat/g00-coordination-base`, dependencies none, from **114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb** (`origin/docs/coordination-foundation`). Allowed edits are only ROADMAP, PREIMPLEMENTATION_REVIEW, COMMUNICATION and AGENT_TASKS under `docs/`. Starting HEAD and the local remote-tracking ref matched; no fresh fetch or remote CI is claimed. The unchanged draft 0.3.0 contract remains the sole wire authority.

[Actual results and exact commands](PREIMPLEMENTATION_REVIEW.md#g00-verification--2026-10-18): requested npx commands failed registry DNS; cached exact-version CLI equivalents passed lint/bundle/types/DESIGN, and the coordination verifier plus **122 tests with jsonschema 4.25.1** passed. Package-download reproducibility needs a network-enabled rerun; local artifact success does not prove clean Windows/CI or any application behavior. One existing license warning remains.

C-03–C-06 stay **Open** in the queue above: M1 auth → M4 token handling; M1 intake/M2 format/failure policy → M4 upload/status errors; M2 source lineage/M3 scoring policy → M4 faithful explanations; M3 retrieval/M4 provider verification → M1 private provenance. Each choice blocks only its affected producer/consumer rows, at the deadlines recorded in ROADMAP; no future policy or all-policy settlement is implied by G00.

Local G00 record is **In Progress**, awaiting review/publication without a commit/push/merge in this session. Checkpoint 0 is **In Progress**; G01/G01B/G01C remain **Backlog**. Next handoffs after G00 acceptance are G01 or independent G01B with explicit shared-task assignee/paths; G01C requires both real skeletons. No four-person signoff ceremony is introduced.

Gates are targeted: P08/P09/P10 need approved OCR/image/video adapter/model/version and private data-boundary decisions under C-04/task acceptance, not G03's final generative provider choice. Deterministic U10 needs approved authorized local retrieval/grounding/privacy behavior, not that choice; full U10B/U10C generation/verification retains G03/C-06. C-05/G02 retains score functions/bands/score-level tie policy; `listTriage` pagination order is already fixed by pinned computed score descending, then evidence UUID ascending, with unscored UUID-ordered items last, never live effective priority.

## Transcription handoff decisions

The user has approved initial local audio/video speech transcription; this is not waiting for another feature vote. C-04 for P16/P16B still needs tested model/runtime/version/license, supported languages/codecs/audio-track selection and stream offsets, duration/byte/compute/time limits, private temporary derivative cleanup, no-audio/silence versus failure policy and labeled quality controls. C-03 applies to U14 playback and U14B/U14C corrections; C-05 must not count visual/audio/transcript derivatives as independent corroboration. CONTRACTS.md defines immutable correction revisions and later processing consumption. U14 transcript search uses all pages of selected completed observations, not an invented HTTP search parameter. G03 is not a prerequisite for local transcription. Do not send evidence to a cloud speech API.

## Declared resolutions, not running-code claims

C-01 is resolved in draft policy/schema: required frozen AnalysisInputSnapshot, latest completed processing selection, canonical digest, request-based idempotency before resnapshot, derived trigger and immutable historic output. A05/A18/I01/I07B still must execute these tests.

C-02 is resolved in draft wire mapping: **all** operations declare 400 ApiError. G01/F00 still must implement and test FastAPI validation mapping rather than default 422. G01 implemented and verified this shared mapping.

C-03 is resolved in coordination policy for F00/U01:
- Bearer authentication format uses standard HTTP `Authorization: Bearer <token>`.
- For local development and testing, authentication uses a synthetic token verifier with two test identities: `investigator-1` and `investigator-2`.
- Missing or invalid tokens return HTTP 401 with `ApiError` (`code: "UNAUTHORIZED"`, `message: "Authentication required."`).
- Case access checks require the authenticated actor to be an authorized member of the case. Accessing an unauthorized case or a nonexistent case returns HTTP 404 with `ApiError` (`code: "NOT_FOUND"`, `message: "Resource not found."`) to prevent case existence leakage.
- Frontend (U01) stores tokens in memory only (no localStorage or persistent browser storage).
- Zero production secrets committed to Git. F00 implements the backend guard; U01 consumes it.

Draft 0.3.0 preserves the original 25 operationIds and adds listTranscriptRevisions/appendTranscriptRevision for the user-approved transcription workflow. Publication requires explicit authorization and verification of the exact remote commit and CI. Full proposal scope is not awaiting renewed feature approval; unresolved settings block their dependent rows only. Artifact verification status belongs in `PREIMPLEMENTATION_REVIEW.md`, not invented application metrics here.

## P01 approved first network CSV policy — 2026-11-01

User approved P01 scope and policy: UTF-8 with one optional leading BOM, exact
ordered timestamp,device_id,ip_address,event header, strict comma/quote CSV,
50 MiB original bytes and 100000 data records maximum. LF, CRLF and CR record
endings and quoted commas/escaped quotes/multiline logical fields are supported.
Reject malformed quotes, NUL, blank/missing/extra fields, changed/duplicate
headers, bad UTF-8, nonliteral/invalid IP, byte/row overflow; no partial result.
Header-only CSV yields no observations. No extra column or resource cap.

P01 emits frozen candidate network.device/network.ip/network.event values per
record using existing Observation fields. raw_value is the decoded logical
cell (CSV escaping removed), normalized_value initially equals it without
case/IP/time normalization; all three retain observed_at_raw. Locators name
physical record start/end lines and column. Machine extraction score is
unavailable, represented by documented 0 sentinel, not measured confidence,
truth or source quality. No entity key/person identity/event truth inferred.
P03 normalizes time, P03B/P03C project candidate keys/events, P04/P14 own run
publication and private provenance (consume parser version network-csv/1).
Run UUID is caller context only; P01 creates no processing run or public API.

P01 validation has no public error-status route. The parser raises safe
code/line errors without cell text. Later P04/P14B must map accepted-run failures
using their own contract/gates. This resolves this adapter's CSV parsing choice,
not later adapters or processing dispatch/retry policy. No scope reduction.

## P02 approved GPS CSV policy — 2026-11-01

User approved strict P01-equivalent CSV rules/caps for GPS: UTF-8 optional BOM,
exact ordered timestamp,device_id,latitude,longitude columns; reject malformed
quotes/encoding/NUL, nonblank required fields and exact row widths; no partial
result; 50 MiB original bytes/100000 logical data records inclusive. Quoted
commas/escaped quotes/multiline logical values and LF/CRLF/CR supported.
Header-only is empty. P01's bounded four-column scanner is reused unchanged.

Coordinates are finite ASCII decimal literals (optional sign/fraction/exponent),
latitude [-90,90], longitude [-180,180], exact Decimal comparison without float
rounding. Do not silently trim coordinate strings, accept DMS/NaN/Infinity or
swap axes. Raw signed zeros, precision, exponents and device text are retained.

GPS timestamps require a valid calendar date and time YYYY-MM-DD[T/t/space]
HH:MM:SS, optional decimal fraction, optional Z/z or numeric +/-HH:MM offset.
Hours 00–23, minutes/seconds 00–59, explicit offset hour <=23/minute <=59;
invalid calendar values/offsets/named-zone suffixes reject. A missing offset is
accepted as unknown, not inferred UTC. All accepted timestamp strings, including
-00:00 or long fractions, remain raw and unconverted. P03 owns normalization
and uncertainty, including any source-clock/offset interpretation; no source
clock is verified by parsing. Unrepresentable/leap-second timestamps reject
explicitly as unsupported/invalid input, never fabricated UTC.

Existing Observation wire only: gps.device/gps.latitude/gps.longitude cells
retain observed_at_raw, normalized_value initially identical to raw and physical
row/column spans. No UTC/entity_key or new endpoint/status field. Confidence 0
means unavailable score, not a measurement/source quality, consistent with P01.
Parser version gps-csv/1 and this policy feed future P14 private provenance.
Caller must authorize same-case original/run context; P04 owns actual runs and
publication. This resolves P02 only, not P03/P04 or later modality choices.

## P03 approved normalization policy — 2026-11-01

User approved raw-preserving exact UTC/GPS normalization and internal unresolved
reasons, immutable output copies and no historical DB changes. Version
source-normalization/1 supports P01/P02 calendar timestamps YYYY-MM-DD[T/t/space]
HH:MM:SS with optional decimal fraction and Z/z or +/-HH:MM. Validate clock
00–23/00–59/00–59/calendar and offset <=23:59 explicitly. Other/invalid formats
remain raw/unresolved. Named-zone suffixes are ambiguous, never resolved from
machine timezone, evidence GPS/location, DST guesses or timezone abbreviations.
Missing zone and -00:00 are unresolved; +00:00/Z are explicit known offsets.
UTC conversion shifts integer minutes across calendar boundaries and reattaches
all fractional digits unchanged, without datetime microsecond truncation.
Out-of-range UTC retains source and has internal utc_out_of_range status.

GPS finite decimal ranges stay latitude [-90,90], longitude [-180,180]. Exact
Decimal tuples (no float/context rounding) canonicalize sign/leading/trailing
zeros; negative zero becomes 0. Plain form is used when at most 64 characters;
otherwise lossless scientific form avoids expansion of tiny exponents. This is
a formatting threshold, not a precision cap, rejection rule or rounding limit.
All significant digits remain. Invalid defensive GPS inputs reject the whole
batch rather than fabricate coordinates. Other cell normalized values unchanged.

Frozen copies retain all case/evidence/run/observation UUIDs, kinds, raw values,
raw times, locators and extraction scores. This operates on pre-publication
parser values; completed stored outputs are never mutated. Internal versioned
TimeNormalization/coordinate statuses carry reasons and original offset text;
only existing Observation fields (optional observed_at_utc) serialize to HTTP
shape. P14 will persist appropriate private provenance. No public status field,
endpoint, entity key or source-confidence increase. P04 owns actual runs and
publication. P03B/P03C consume normalized values afterward. Full scope retained.
