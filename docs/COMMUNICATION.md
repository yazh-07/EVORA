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


## P03B approved candidate policy — 2026-11-01

User explicitly approved the P03B bounded file scope and exact-key policy.
Version candidate-identifiers/1 consumes P03 normalized observations for one
explicitly supplied case. Device values remain exact/case-sensitive with no
trim, case fold, Unicode rewrite or inferred ownership: device:D-7 and device:D-8
are distinct. Network IP keys use the existing P01 normalized_value verbatim
with ip: namespace; P01 currently retains validated source spelling. This does
not merge alternate IPv6 spellings, mapped address forms or device/IP namespaces.
Future key-policy changes need versioning, never rewriting completed outputs.

Group identical keys only within the supplied source set/case. Entity kind is
device or ip, canonical_label is the unchanged key value, and source Evidence/
Observation UUID references are unique lexically ordered tuples. Output entities
are ordered by candidate key. Each gets a fresh record UUID before publication;
repeating this pure projection is not P04 replay or a global identity registry.
confidence=0 is unavailable, not probability/reliability/corroboration. Existing
source extraction scores remain unchanged; repeated mentions do not boost them.

New frozen observation copies add only existing optional entity_key on identifier
kinds; other observations and P03 time/coordinate uncertainty envelopes survive.
No key/entity is inferred from network.event or GPS coordinates. No source/raw/
normalized/time/locator/UUID changes, person identity, event projection, HTTP,
DB write, run lifecycle or list API. P04/P05/P14 retain their required tasks.

Reject mixed-case input, duplicate observation UUIDs, inconsistent evidence/run
context or preassigned conflicting keys atomically with fixed safe codes. One
run belongs to one evidence item, and one supplied evidence item uses one run;
caller chooses authorized outputs, rather than mixing historical runs. Source
validation retains the existing six network/GPS kinds and schema value bounds.
No access grant is implied by an internal UUID; real source access remains F00/F05.
Entire agreed initial scope including approved transcription remains unchanged.


## P03C approved source-event policy — 2026-11-01

User approved the bounded P03C scope and row-to-event policy. Version
source-events/1 creates one candidate event per complete P01/P02 logical CSV row,
including rows spanning physical lines. Group by explicit case/evidence/run,
physical row span and adapter family, never by coincident time/device/text.
Network rows require device/ip/event columns; GPS rows device/latitude/longitude.
Every Event cites all three source observation IDs and that original Evidence ID.
Exact canonical parser locators identify columns; reject duplicate/incomplete,
wrong-column, overlapping row spans or mixed adapter rows within one evidence.
Equal-content rows with distinct locators remain separate source reports.

Use network.activity and gps.location kinds, summaries explicitly framed as
source reports. Preserve the network event cell verbatim in its report summary;
GPS report summarizes source device and P03 normalized coordinates. These are
untrusted source text for safe rendering, not confirmed activity/location or
identity/ownership. No event classification inferred from a string such as
connected; no person participant, link between distinct device keys or score boost.

Consume actual P03B CandidateProjection participant records already integrated
in this base. Verify exact same-case key/source memberships and use their actual
record UUIDs: network device plus IP; GPS device. No invented or regenerated
participant IDs. P01/P02/P03 remain catalog prerequisites; this implementation
uses the existing P03B handoff rather than inventing an independent identity map.
Reject missing/duplicate/foreign/altered Entity references or unsupported versions.

Preserve row raw timestamp and P03 TimeNormalization envelope exactly. Row cells
must agree on raw/UTC/time uncertainty and match P03 interpretation; malformed,
missing, ambiguous and -00:00 timestamps keep raw/no UTC, never processing time.
GPS coordinates must match actual P03 exact canonical values. Fresh event UUIDs
are unpublished record IDs; pure projection is not run replay/idempotency.
confidence=0 is unavailable, not measured event truth/extraction/corroboration.
No DB writes, new wire fields, API route, processing publication or list producer.
P04/P05B/P14 retain lifecycle/listing/private persistence tasks. Full initial
scope including approved transcription remains unchanged.


## P04 approved lifecycle policy — 2026-11-01

User approved the bounded scope and C-04 lifecycle choices. Version
processing-lifecycle/1 supports existing network_log and gps CSV layouts/limits
using actual P01/P02/P03/P03B/P03C; no MIME/filename-only success. Unsupported
Evidence kind returns 415 before creating a run/key. Supported-kind malformed
CSV is accepted as queued then failed with a fixed safe code, never partial output.
Bodyless start rejects submitted body/undeclared query; Idempotency-Key is exactly
one header of 1–128 characters per spec (no secret/raw key persisted or logged).
Scope key digest to actor/case/startProcessing, fingerprint request target before
selecting current input/config; repeat returns original run including failure,
changed target 409, new key permits retry. Reauthorize case on every read/replay.

Freeze original hash/size/kind and processor/parser/normalizer/projector versions
at acceptance in private SQL. Authorized F05 original lookup is reused; worker
rechecks membership, bounded bytes and frozen size/hash before actual parsing.
No original rewrite. Store immutable source observations/entities/events and time
uncertainty only in an atomic output transaction with completed status. New runs
retain old outputs. Public run error contains only fixed diagnostic codes, no
raw cells, paths, credentials or private configuration. F08 public processing
audit/P14 richer private provenance/P14B dispatch registration/P14C full retry/
crash publication gate remain separate required tasks; this is real P04 lifecycle
and basic atomicity, not completion of those later rows.

Single local application process, one background job scheduled per newly accepted
run; queued->running claim is atomic and replay never reexecutes it. Jobs do not
run on GET/poll. On startup, mark interrupted queued/running jobs failed with
PROCESSING_INTERRUPTED and finished_at; never fabricate completion or silently
rerun them. Same key returns that failed run, new key may retry. No external queue,
new package, automatic production auth, multi-process worker deployment or model.
Safe SQL failure leaves no completed publication; an inaccessible database can
leave a nonterminal run until restart recovery, never fictional success.

Processing-owned tables/triggers retain frozen configuration, terminal run records
and published output JSON immutably without changing M1 tables. listProcessingRuns
returns oldest by created_at then UUID; reads are no-store, case/evidence/run joins
are exact and foreign/missing use the same 404. P04B/P05/P05B retain output listing.
Full initial scope including approved additions remains unchanged.

P04 implementation detail: one asynchronous per-application worker lock serializes
parsing so pending jobs wait without taking thread-pool slots or blocking polls.
Frozen configuration includes the existing parser byte/row parameters; a mismatch
with executing versions/limits fails rather than silently using new configuration.
The necessary skeleton table-inventory assertion includes processing-owned tables;
all original table assertions remain. No M1 table/schema or source producer changed.


## P04B approved observation-read policy — 2026-11-01

User approved bounded P04B files/read policy. Existing listObservations defaults
to latest completed run per evidence by exact finished_at UTC then UUID, or pins
one completed same-case processing_run_id. evidence_id filters the same case;
foreign/missing/pending/failed or mismatched filters use the same 404. No completed
output is a real empty page, including valid unprocessed evidence. Existing
limit default 20/max 100/min 1 and offset default 0/min 0 remain unchanged.

Page order is evidence UUID then Observation UUID, ascending canonical UUID text.
One explicit read transaction freezes selection, total and page per response;
a default unpinned read may select newer outputs on the next request. Historical
stable pagination requires the existing run selector; no case-wide snapshot
field/selector is invented. Compare completion instants without SQLite floating
point date rounding, including fractions/offset equivalents and UUID tie-breaks.

Use real immutable P04 SQL JSON output, read-only. Return original Observation
wire values unchanged with no private configuration/uncertainty envelope fields.
Validate selected output structure/schema and same-case/evidence/run context,
including unique observation IDs; a selected missing/corrupt output returns
safe 404 for the whole read, never partial data or silent older-run fallback.
Unknown/duplicate query parameters are invalid 400, avoiding ambiguous selectors.
Each request uses existing F00 access checks; all responses are no-store.

No DB/schema/producer/spec/dependency/frontend change, new public fields or
Entity/Event APIs. Full agreed initial scope including approved transcription
remains required; existing optional transcript wire fields/conditionals are
preserved, not converted into an implemented transcript producer. P05/P05B and
later UI/provenance/dispatch/recovery rows remain separate tasks.


## P05 approved Entity-read policy — 2026-11-01

User approved the bounded files/read policy. listEntities is a live processing
view over persisted candidate Entity records in latest completed output per
Evidence, using the same exact UTC finished_at/UUID choice as P04B. No new run/
analysis/evidence selectors are added to this limit/offset-only operation.
Historical analytical sources remain frozen internal snapshot references, not
live Entity lists. One read transaction keeps selection, sources, total and page
coherent per response; separate requests may see newer completed outputs.

Preserve persisted Entity UUIDs, keys, labels, confidence and source arrays exactly.
Never regenerate/merge IDs on GET: actual Event participants must remain valid.
Identical candidate_key values from distinct persisted records stay distinct;
shared identifier text alone is not verified identity/ownership or independent
corroboration. D-7/D-8 stay distinct. No confidence boost or key normalization.

Validate wire shape, unique record/reference UUIDs, case context and every cited
Observation in same-case selected completed outputs. Evidence IDs must exactly
match the cited observations' Evidence set, including the stored output's source
Evidence. If a cited observation carries entity_key, it must match this candidate
key; do not invent a mandatory entity_key on future generic source observations.
Missing/corrupt selected records, broken/foreign/stale citations or ambiguous
repeated Entity UUIDs fail the whole read with the same safe 404; no partial
records or silent older-run fallback. Pending/failed output remains invisible.
An accessible case with no completed candidates returns an empty page.

Use existing limit default 20/min 1/max 100 and offset default 0/min 0, with no
invented maximum offset. Order candidate_key then canonical Entity UUID ascending.
Unknown/duplicate query parameters are invalid 400. Existing F00 guards apply
on every request; responses are no-store. No SQL writes, source mutation, new
public fields, DB/schema/producer/dependency/frontend changes or Event API.
All future modalities/scope additions stay required; current candidate listing
is not implementation of future extraction/identity/graph features. P05B is next.


## P05B approved Event-read policy — 2026-11-02

User approved the bounded file handoff and read policy. listEvents is a live
processing-source view over immutable latest completed output per Evidence,
using P04B exact UTC finished_at then UUID selection. Preserve stored Event IDs,
kinds, summaries, raw/UTC time strings, confidence and source/participant arrays
unchanged. Do not reproject/regenerate IDs, merge coincident/duplicate reports,
infer time/identity or boost confidence. No new selector/public field or timeline
reconstruction claim. Unknown/duplicate query parameters use safe400; existing
F00 auth401/case404 and no-store behavior apply.

Validate selected output/Observation/Entity/Event wire shape and same-case run
context. Event Evidence sets exactly match cited selected Observations and include
its output Evidence. Participant UUIDs resolve actual selected Entities whose
citations also validate; each participant shares at least one Event source
Observation. Empty participant arrays and omitted optional timestamps remain
valid. Missing/corrupt/stale/foreign source or participant references fail the
whole read safe404, no partial output or silent fallback. Validation establishes
shape/context/source joins, not factual source truth or tamper authenticity.

Contract limit default20/min1/max100 and offset default0/min0; canonical Evidence
UUID then Event UUID ascending before slicing. One explicit read snapshot keeps
selection/sources/participants/total/page coherent per response; another request
may see newer completed output. Pending/failed partial outputs invisible; empty
latest stays empty. No writes/processing on reads. No DB/schema/producer/spec/
dependency/frontend edits. P14/P14B/P14C and later modalities/UI remain required;
full FEATURE_SCOPE including approved additions is unchanged.


## P14 approved private processing-provenance policy — 2026-11-02

User approved bounded P14 paths and one processing-owned append-only SQLite table.
New runs use processing-lifecycle/2, freezing processing-provenance/1 with existing
input hash/size/kind and parser/normalizer/Entity/Event/processor versions and
byte/row parameters. Existing adapters are deterministic: model is explicitly
not used, never an invented model/version. Each newly completed run publishes one
private record with case/Evidence/run IDs, input snapshot, frozen execution
versions/parameters, exact output-ID manifests and digest, and completion time.
Provenance/output/completed pointer share one transaction and timestamp; a
provenance failure publishes none. Success provenance is not attached to failed
runs, whose existing frozen config/safe errors remain. Same-key replay preserves
its original record; a new key yields a new immutable record without rewriting
history or original bytes. Empty successful outputs receive genuine empty manifests.

Old completed runs remain readable through existing APIs without fabricated
backfill. Old pending/running jobs retain P04 interrupted-failure startup policy.
An internal private reader rechecks current membership and same-case Evidence/run/
output context; missing/legacy/pending/failed/foreign/corrupt provenance returns
safe404, not another run or leaked details. No new public route/field or private
payload in public AuditEvent/application logs. F08 will link safe audit through
existing run references; it remains separate required M1 work. P14B dispatch and
P14C full failure/recovery gates remain separate required M2 work. No M1 table,
parser, dependency, frontend, spec or entire FEATURE_SCOPE/addition change.


## P14B approved first-adapter dispatch handoff — 2026-11-02

User approved bounded P14B paths and reuse of recorded P01/P02/P04 C-04 policy.
An explicit immutable registry binds network_log to actual network-csv/1 and gps
to actual gps-csv/1, including parser-owned50MiB/100000-row limits. Declared kind
selects the adapter; actual original content must pass that parser's exact UTF-8/
optional BOM/header/quote/row/value validation. Filename, extension, MIME and
source label do not establish format or success. Never silently sniff/reroute a
wrong-layout source to another kind. Unsupported kind415 before run/key creation;
malformed/wrong-layout supported CSV is accepted then fails with safe existing
codes, no output/provenance partial success. Header-only input is genuine empty
success, not upload-as-processing. All existing byte/row/field/time rules remain.

P04 freezes selected kind/parser_version/row-byte limits and existing producer
versions; worker verifies them against the registered adapter before execution.
P14 records exact actual input/output/versions/parameters/time privately. This
refactors selection without changing dispatch policy, wire/config/provenance
format or processor/parser version; no historical records rewritten/backfilled.
Same-key replay precedes current selection, new key may retry. No new public
route/field, schema, parser, dependency, frontend or model. P14C full retry/recovery
and F08 audit remain separate required tasks; full FEATURE_SCOPE/additions stay.


## P14C approved atomic publication/recovery handoff — 2026-11-02

User approved bounded P14C files and recorded lifecycle policy. Before completed
publication, re-read actual SQL run/frozen context, exact output JSON and P14
private record in the same transaction. Verify case/Evidence/run ownership,
source/participant IDs, manifests/digest and identical completion timestamp
against the prepared actual outputs; never infer successful persistence from a
producer returning values or an INSERT call alone. Update exactly one running
row to completed only after verification. Any failure rolls back output/private
record/pointer together and leaves a safe failed run when failure persistence is
available; a DB outage may leave interrupted state for startup recovery, never
fictional completion. Harden processing-owned records against replacement as
well as existing UPDATE/DELETE guards. No M1 table or new table/field change.

Preserve existing behavior: same actor/case/key/fingerprint replays the original
resource before selecting/executing new inputs, including failed/interrupted
history; new key permits retry with old completed outputs preserved. Concurrent
same-key acceptance/worker claim must not duplicate execution/publication. On
restart, queued/running jobs become failed PROCESSING_INTERRUPTED rather than
resume or claim completion. Actual child-process hard exits exercise SQLite
rollback/committed durability; this is not a hardware/OS power-loss certification.
No new endpoint/status/error contract/provenance format/parser/dependency/frontend
or model. Entire FEATURE_SCOPE/additions remain required. P14C does not seal1B:
F08/U05C/U05/U05B/U13/I00B integration remains required before the1B exit; automatic M2 P06 selection in2A also waits for1C/I01 exit. No later task started.
