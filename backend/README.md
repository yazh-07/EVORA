# P04B source-backed Observation listing — 2026-11-01

P04B / Checkpoint 1B / M2 yazh-07, feat/p04b-observation-list from verified
shared base bb3928440ebf39d016e14fb328f045d98fd68bb9. User approved the bounded
scope/read policy and authorized implementation/test/commit/push/merge.
Complete after merge c29e517f218c0851a9959cfa389b093242a255ab; 16 focused tests,
verifier and real Observation/I00 post-merge HTTP smoke PASS.
Current state in docs/ROADMAP.md. Older notes
below are historical. Entire agreed initial scope/additions remain unchanged.

GET /api/v1/cases/{caseId}/observations now reads actual immutable P04 output.
No schema, producer, DB migration, dependency or frontend change.

- Default selects latest completed run per evidence by exact finished_at UTC,
  then UUID descending. Compare every fractional digit without floating-point
  SQLite date rounding; equivalent offset spellings use the UUID tie-break.
  Queued/running/failed runs and partial outputs never replace completed history.
- Optional evidence_id filters same-case source; processing_run_id pins one
  completed historical output. Missing/foreign/pending/failed/mismatched selectors
  share the same safe 404. An accessible case or evidence with no completed output
  is an empty page. A selected empty completed run stays empty, never older data.
- Existing limit=20/default, 1–100 bound; offset=0/default, nonnegative with no
  invented upper cap. Huge beyond-end offsets return empty items with true total.
  Page order is evidence UUID then Observation UUID ascending. Total counts the
  full filtered selection, not one page. Unknown/duplicate query parameters or
  invalid UUID/limit/offset yield safe 400. Existing F00 guards enforce 401/404.
- One read transaction keeps selection/total/page coherent during publication.
  Separate default requests may choose newer completed outputs; pin an existing
  processing_run_id for stable pages across requests. No new snapshot selector.
- Return original Observation wire values, IDs, locators, raw/normalized text,
  candidate keys and timestamp fractions unchanged. Runtime shape/context checks
  reject selected missing/corrupt output as a whole with 404, without private
  fields, partial results or silent older-run fallback. Every response is no-store.
  No read mutates SQL/originals/audit or schedules processing work.
- Existing transcript optional fields/conditional wire rules remain compatible;
  their schema fixture does not implement an ASR/correction producer. P05/P05B
  Entity/Event listing and later provenance/dispatch/recovery/UI rows remain
  separate required tasks. No confidence boost, identity or new public field.

## How you can test P04B

PowerShell at repository root, Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p04b-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p04b-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_observations -v

Expect 16 passing tests. Real network.csv produces six observations; gps.csv
produces three. Default returns total 9 with exactly the stored source values;
evidence_id restricts to 6 or 3, and processing_run_id preserves the chosen
historical run after a newer completion. Pagination over 27 synthetic network
observations yields no duplicate/skipped IDs and full total on every page.
The GPS precision variant retains raw +12.9716000 and UTC nanosecond fraction,
with normalized latitude 12.9716. Storage and servers clean up automatically.

Run actual localhost HTTP smoke independently:

    python -W error::ResourceWarning -m unittest backend.tests.test_observations.ObservationLoopbackTests -v

Expect PASS: actual Uvicorn/FastAPI/SQLite upload -> process -> default/filtered/
pinned Observation pages, limit=2/offset=2 gives two items and total=6 for the
network evidence, and a failed malformed CSV run selector gives 404. Synthetic
auth is explicit; actual P04 run/output IDs are produced, not fabricated fixtures.

Relevant failure/history controls:

    python -m unittest backend.tests.test_observations.ObservationTests.test_pending_running_failed_outputs_hidden_and_prior_completed_remains -v
    python -m unittest backend.tests.test_observations.ObservationTests.test_missing_latest_output_no_silent_fallback_but_old_pin_stays_valid -v

Expect PASS: queued/running/failed selectors return 404 and expose no partial
observations. A corrupt/missing selected latest output fails closed (404), while
an intact older explicitly pinned output remains readable; no fallback hides it.
These failure states are labeled SQL/scheduler/corruption fixtures in temporary
storage, not claims of a real production corruption incident.

Core tests use actual F00/F01/F03/F05/P04 and existing parsers/normalizer/Entity/
Event producers, SQLite/private files with HTTPX in-process ASGI. The separate
smoke uses real localhost HTTP with no producer double. Selection-only SQL
fixtures cover future-dated/equal/sub-microsecond finished_at, UUID ties and empty
latest outputs; a schema-derived transcript fixture proves wire compatibility
only. Scheduling gates/failure injection expose pending/failed states, corruption
fixtures bypass triggers only in temp DBs, and a real writer thread attempts
publication during one held read snapshot. No OS power-loss, distributed worker,
production auth, full Observation UI or real-evidence benchmark claim. Earlier
unrelated suites retain documented doubles. Full prior-checkpoint results are
in docs/PREIMPLEMENTATION_REVIEW.md. Optional cleanup: remove TEMP schema bundle.
Next M2 P05 exposes source-backed candidate Entity listing; no next task started.

# P04 processing-run lifecycle — 2026-11-01

P04 / Checkpoint 1B / M2 yazh-07, feat/p04-processing-lifecycle from verified
shared base 9bec1653525694c01ef82c6a3cd12f2beea8493c. User approved the bounded
scope/lifecycle policy and explicitly authorized implementation/test/push/merge.
Complete after merge f851dd11fd8f7e11140317cf44d022a9999044dd; 21 focused tests,
verifier and actual processing/I00 post-merge HTTP smoke PASS.
Current state in docs/ROADMAP.md.
Older task notes below are historical. Full agreed initial scope is preserved.

The actual startProcessing/getProcessingRun/listProcessingRuns APIs now use
processing-owned SQLite tables and the real network/GPS -> normalization ->
candidate Entities -> source Events pipeline. M1 tables/producers are unchanged.

- POST /api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs is bodyless,
  requires exactly one 1–128 character Idempotency-Key and returns 202 queued.
  Existing F00 auth/case grants apply to all three routes. Unsupported kind returns
  415 without a run/key; supported malformed CSV is accepted then failed safely.
- Scope a key digest to actor/case/startProcessing; fingerprint the request, never
  mutable server data. Replay returns the same original run before resnapshot,
  including failure; a different evidence target conflicts 409. New keys can retry.
  Only digests are stored; raw keys/credentials/private source data are not logged.
- Freeze kind/hash/size, processor/parser/normalizer/projector versions and existing
  50 MiB/100000-row parameters privately at acceptance. A changed configuration
  cannot execute under an older frozen version. Worker rechecks actual membership,
  authorized F05 path, bounded original bytes/hash and membership before publication.
- A local background job claims queued -> running atomically. One asynchronous
  worker lock serializes parsing; waiting jobs do not occupy worker threads or
  block polling. This supports one local application process, not a distributed
  queue or multi-process worker deployment. GET never schedules/progresses jobs.
- On success, immutable observations/entities/events/uncertainty JSON and completed
  status commit together. A failure rolls back partial publication and exposes a
  safe fixed error plus finished_at. SQL triggers protect frozen config, terminal
  runs and completed outputs. Reprocessing retains every earlier output/run.
- Startup marks interrupted queued/running jobs failed with PROCESSING_INTERRUPTED;
  same-key replay stays failed, new key may retry. No pretend completion/reexecution.
  If SQLite itself is unavailable, a job can remain nonterminal until recovery;
  it is never reported as completed without output. No external queue/package.
- Poll GET .../processing-runs/{runId}; list GET .../processing-runs returns oldest
  first by created_at then UUID. Every read is no-store and case/evidence/run scoped;
  missing/foreign targets share 404. Public run wire has no private configuration,
  raw content, provenance JSON or idempotency digest. Terminal fields follow schema.
- These are real immutable outputs but no public listObservations/Entity/Event
  endpoints yet. P04B/P05/P05B add them. P14 richer private provenance, P14B dispatch
  registry and P14C full retry/crash publication gate remain required tasks; basic
  P04 atomicity/first network/GPS path does not mark those rows Complete. F08 owns
  safe public processing audit. No scoring/graph/UI implementation is claimed.

## How you can test P04

PowerShell at repository root with Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p04-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p04-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_processing -v

Expect 21 passing tests. The real synthetic network.csv fixture publishes six
observations, four Entity records and two source Events; gps.csv publishes three
observations, one device Entity and one source Event. Source IDs/locators/raw/time/
confidence remain intact; raw originals and SHA-256 stay unchanged. Start returns
202 queued; polling reaches completed with finished_at; list returns that run.
Same-key replay returns the same UUID and no new work, different target 409;
new key produces a new run without changing earlier outputs. Storage is temporary
and cleaned automatically; no real evidence/token/provider needed.

Run the real localhost smoke independently (server starts/stops automatically):

    python -W error::ResourceWarning -m unittest backend.tests.test_processing.ProcessingLoopbackTests -v

Expect PASS for actual HTTP start/poll/list using both real CSV producers and a
malformed supported CSV that becomes failed. No scheduler/parser/storage double
in this smoke. Synthetic HTTP auth is opt-in only; normal app still rejects tokens
until configured. No real processing-run UUID double: run IDs are produced by P04.

Relevant failure/replay check:

    python -m unittest backend.tests.test_processing.ProcessingTests.test_malformed_supported_file_failed_replay_and_new_key_retry -v

Synthetic input has exact header timestamp,device_id,ip_address,event and row
2026-01-12T10:01:00Z,D-7,SECRET,connected (SECRET is deliberately invalid IP text).
Expect PASS: 202 then failed/CSV_INVALID_IP with finished_at, zero output rows,
no cell text in public error; same key replays the failed UUID, new key creates
another run. Unsupported document Evidence separately returns 415 before a run.
The tests also cover missing/duplicate/oversize keys, nonempty body/query 400,
foreign/missing resources 404, auth 401, revoked access, concurrency, queued/running
polling, atomic rollback/retry and interrupted-run startup failure.

Scheduler gates/failure injections are labeled in tests: a held job makes queued/
running observable; a post-insert exception proves rollback; persisted interrupted
states exercise actual startup recovery. These do not claim an OS power-loss or
multi-process crash test. Focused API tests use actual FastAPI/SQLite/private files
with HTTPX in-process ASGI; the separate smoke uses a real Uvicorn subprocess and
loopback HTTP. Earlier unrelated suites retain their documented doubles. Full
regressions/results are in docs/PREIMPLEMENTATION_REVIEW.md. No real-evidence
benchmark, new browser workflow, clean local reinstall or production auth claim.
Next M2 P04B exposes source-backed historical/latest observations; no next task
starts here. Optional cleanup: remove the TEMP schema bundle after all checks.

# P03C source-backed row events — 2026-11-01

P03C / Checkpoint 1B / M2 yazh-07, feat/p03c-source-events from verified shared
base e68969df9f19f8f78320a708bc3cb80a3c05b85d. User approved the scope/event
policy and authorized implementation/test/commit/push/merge. Complete after
merge bb2d18f1222c8e7fd4ab45dbdf7e1e17b252baca; 15 focused tests, verifier and
real I00 post-merge HTTP smoke PASS. Current state is in docs/ROADMAP.md;
older notes are historical.

backend.parsers.source_events.project_source_events consumes the actual P03B
CandidateProjection (over P01/P02/P03) and an explicit case_id UUID. It returns a
tuple of frozen SourceEventResult values, version source-events/1. Each contains
an existing-schema Event and the preserved internal P03 TimeNormalization.
This component has no I/O, persistence, route, authorization grant or run replay.

- One candidate per complete logical network/GPS row; match exact source locator
  columns and physical line spans under one case/evidence/run/adapter. Cite all
  three row Observation IDs and the original Evidence ID. Identical text/time in
  distinct source rows remains distinct; row fragments/duplicates/overlaps reject.
- network.activity summary says Network log reports: followed by the raw event
  cell. gps.location says GPS record reports device ... with source identifier
  and exact P03 normalized coordinates. Reports remain unverified source content,
  never a verified occurrence/ownership claim or inferred event classification.
  Text is untrusted data; consumers must render safely, never execute markup.
- Network participant IDs are the actual supplied P03B device and IP Entity UUIDs;
  GPS participant is the actual device Entity UUID. Verify exact same-case key/
  Evidence/Observation membership. No participant regenerated or identity inferred.
  Distinct D-7/D-8 keys remain distinct. Confidence 0 means unavailable, no boost.
- Preserve original time/UTC/fractional precision and uncertainty exactly. Missing,
  ambiguous, invalid and -00:00 times retain raw/no UTC; never use processing time.
  Reject conflicting/forged time or coordinate values, mixed cases/run context,
  unsupported projection versions and missing/duplicate/foreign participants.
  Rejection is atomic with safe fixed SourceEventError codes and no raw echo.
- Fresh Event UUIDs identify unpublished records. Existing source/Entity values,
  IDs, locators, original bytes/hash and completed history remain unchanged.
  P04/P05B/P14 retain publication/listing/private provenance; no full app claim.

## How you can test P03C

PowerShell at repository root with Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p03c-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p03c-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_source_events -v

Expect 15 passing tests: complete/multiline/repeated source rows, real source and
participant joins, schema/immutability/time precision and uncertainty, incomplete/
duplicate/mixed-case/run/time/coordinate/participant failures. Actual F03/F05 ->
P01/P02/P03/P03B -> P03C integration uses synthetic identities/unpersisted run
UUIDs, real FastAPI/SQLite/private files/parsers and HTTPX in-process ASGI.
No parser/storage/normalizer/Entity double; separate I00 smoke uses loopback HTTP.
Earlier unrelated suites retain documented doubles. No new UI producer claimed.

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.network_csv import parse_network_csv; from backend.parsers.normalization import normalize_observations; from backend.parsers.candidate_entities import project_candidate_entities; from backend.parsers.source_events import project_source_events; c=uuid4(); n=normalize_observations(parse_network_csv(Path('fixtures/synthetic-case/network.csv').read_bytes(),case_id=c,evidence_id=uuid4(),processing_run_id=uuid4())); p=project_candidate_entities(n,case_id=c); print([(x.event.kind,x.event.summary,len(x.event.observation_ids),len(x.event.entity_ids),x.event.observed_at_utc) for x in project_source_events(p,case_id=c)])"

Expect two network.activity reports, each summary Network log reports: connected,
three source Observation IDs/two actual participant IDs, UTC 2026-01-12T10:01:00Z
and 2026-01-12T10:02:00Z. GPS fixture adds one gps.location report for D-8 with
12.9716/77.5946, three Observation IDs and one actual device Entity ID. Record
UUIDs vary; existing source/participant IDs do not change. No output persisted.

Failure/uncertainty controls with synthetic inputs:

    python -m unittest backend.tests.test_source_events.SourceEventTests.test_incomplete_and_duplicate_row_fields_reject_atomically -v
    python -m unittest backend.tests.test_source_events.SourceEventTests.test_raw_precision_utc_and_timezone_uncertainty_preserved -v

Expect PASS: missing network event column raises INCOMPLETE_ROW; duplicate device
field raises DUPLICATE_ROW_FIELD, without partial output. Invalid source time
2026-02-30T10:02:00Z keeps raw/no UTC and invalid_timestamp; -00:00 remains unknown.
These exact commands/examples were exercised. Optional cleanup: remove the TEMP
bundle after checks. Full regression results in docs/PREIMPLEMENTATION_REVIEW.md.
No new dependency/model/provider, clean local reinstall or real-evidence benchmark.
Entire agreed initial scope/additions preserved. Next M2 P04 processing lifecycle;
no next task started in this assignment.

# P03B candidate identifiers/entities — 2026-11-01

P03B / Checkpoint 1B / M2 yazh-07, feat/p03b-candidate-entities, verified shared
base 59de4686f4a59bff25528d386ce458d259d96e6c. User approved the bounded scope
and key policy and authorized implementation/test/commit/push/merge. Complete
after merge c58e7f24e4f7c21fc5120dc7288d02f960b58006; 15 focused tests,
coordination verifier and real I00 post-merge HTTP smoke PASS.
Current task state is in docs/ROADMAP.md; older notes
below are historical.

backend.parsers.candidate_entities.project_candidate_entities consumes actual P03
NormalizationResult values plus an explicit case_id UUID. It returns a frozen
CandidateProjection containing new frozen observations and source-backed Entity
records, version candidate-identifiers/1. It has no I/O or authorization grant.

- network.device/gps.device -> exact case-sensitive device:<normalized_value>;
  network.ip -> ip:<P01 normalized_value>. No trim/case fold/Unicode rewrite.
  P01 retains validated IP source spelling, so alternate IPv6 spellings remain
  separate. Namespaces prevent device/address collisions. D-7/D-8 stay distinct.
- Group only identical keys within this case/source set. Entity kind device/ip;
  label is unchanged identifier text, references are unique lexically sorted
  source UUIDs, entities sorted by key. Each entity gets a new unpublished UUID;
  pure repeated projection is not run replay or a persistent identity registry.
- Confidence 0 means unavailable, never corroboration/identity probability.
  Existing extraction scores, IDs, raw/normalized values, time/uncertainty and
  locators are preserved. Nonidentifier kinds emit no key/entity. Inputs and
  completed history remain immutable. Fresh wire copies use existing schema only.
- Mixed cases, duplicate observation UUIDs, conflicting evidence/run contexts,
  malformed identifiers and conflicting preassigned keys reject the entire batch
  with safe CandidateEntityError codes. No partial result or raw error echo.
- No inferred person identity/ownership, event producer, public route, DB write,
  lifecycle or list API. P03C/P04/P05/P14 retain those separate tasks. Source
  authorization belongs to F00/F05; unpersisted test run UUIDs are synthetic.

## How you can test P03B

PowerShell at repository root with Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p03b-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p03b-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_candidate_entities -v

Expect 15 passing tests. Synthetic identifier controls cover exact matching,
case/whitespace/Unicode distinctions, namespace/IP spelling, identical-key source
grouping, schema/immutability/uncertainty, safe invalid/mixed-case/conflicting
inputs and actual F03/F05 -> P01/P02/P03 -> P03B source/hash/SQL read-back.
Focused HTTP transport is in-process HTTPX ASGI; actual FastAPI/SQLite/private
files/parsers are used. No parser/storage double. I00 separately checks loopback
HTTP; unrelated suites retain their documented doubles. No UI producer claimed.

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.network_csv import parse_network_csv; from backend.parsers.normalization import normalize_observations; from backend.parsers.candidate_entities import project_candidate_entities; c=uuid4(); n=normalize_observations(parse_network_csv(Path('fixtures/synthetic-case/network.csv').read_bytes(),case_id=c,evidence_id=uuid4(),processing_run_id=uuid4())); p=project_candidate_entities(n,case_id=c); print([(e.candidate_key,e.confidence,len(e.observation_ids)) for e in p.entities])"

Expect device:D-7, device:D-9, ip:203.0.113.7 and ip:203.0.113.9, each confidence
0 and one source Observation ID. The GPS fixture adds device:D-8, not a D-7 link.
Fresh entity UUIDs vary; source observation/evidence/run UUIDs remain unchanged.

Failure case (synthetic duplicate observation, no outputs published):

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.network_csv import parse_network_csv; from backend.parsers.normalization import normalize_observations; from backend.parsers.candidate_entities import project_candidate_entities; c=uuid4(); n=normalize_observations(parse_network_csv(Path('fixtures/synthetic-case/network.csv').read_bytes(),case_id=c,evidence_id=uuid4(),processing_run_id=uuid4())); project_candidate_entities((n[0],n[0]),case_id=c)"

Expect nonzero exit with CandidateEntityError code DUPLICATE_OBSERVATION and no
source cells in the diagnostic. Passing another case UUID yields CASE_MISMATCH.
Full completed-checkpoint commands/results are in docs/PREIMPLEMENTATION_REVIEW.md.
No new dependencies/models/provider, clean reinstall or real-evidence benchmark
claimed. Full agreed initial scope including approved additions stays unchanged.
Next M2 P03C projects source-backed events; no next task starts here.

# P03 source normalization — 2026-11-01

P03 / Checkpoint 1B / M2 yazh-07, feat/p03-normalization, verified shared base
ac432e10a6a1c4ff19ae36b49cded514d0e78846. User approved the normalization
policy and explicitly authorized implementation, tests, commit, push and merge.
Complete after authorized merge e9f01f586916f38c480a40ffc8aa3eb72fd146ff;
18 focused tests, coordination verifier and real I00 HTTP smoke pass on that merge.
Current state is in docs/ROADMAP.md.
Earlier task notes below are historical.

backend.parsers.normalization.normalize_observations consumes actual P01/P02
frozen observations and returns a tuple of new frozen NormalizationResult values.
Each contains an existing-schema NormalizedObservation plus an internal time/
coordinate uncertainty envelope and version source-normalization/1. Raw cells,
source timestamps, IDs, locators, kind and extraction confidence stay unchanged.
Completed stored outputs are never modified. This is a pre-publication component;
P04/P14 own real processing lifecycle, persistence and private provenance.
Caller run UUIDs in tests are synthetic context, not published ProcessingRuns.

## Approved source-normalization/1 behavior

- Valid explicit Z/z or numeric +/-HH:MM timestamps convert to UTC, including
  date/year rollover, with every source fractional digit preserved unchanged.
  Supported calendar/clock spelling matches P02; no rounding or host timezone.
- Missing, named/ambiguous, invalid and -00:00 zones yield no observed_at_utc.
  Raw time remains intact; internal time.status records the reason. Out-of-range
  UTC also remains unresolved. No guessed zone/DST or extra public API fields.
- GPS latitude/longitude use exact Decimal values, never float rounding. Trim
  non-significant zeros, canonicalize signed zero to 0; use plain decimals up to
  64 output characters and exact scientific notation otherwise. This expansion
  threshold is not a precision/rejection cap. Range/finite/syntax failures raise
  safe NormalizationError('INVALID_COORDINATE') and reject the whole batch.
- Non-coordinate normalized values remain unchanged. No candidate identity keys,
  source-backed events, joins, scoring boost, HTTP route or DB update is added.
  Pure repeated transformation is not processing-run replay/idempotency.

## How you can test P03

PowerShell at repository root with Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p03-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p03-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_normalization -v

Expect 18 passing focused tests, including actual F03/F05/SQLite/private-original
round trips with synthetic identities, both real parser producers, exact values,
source immutability/schema, context checks and unknown/invalid time failures.
No parser/storage doubles; HTTPX ASGI transport is in process. I00 separately
checks real loopback HTTP. Existing unrelated suites retain their labeled doubles.

    python -c "from backend.parsers.normalization import normalize_timestamp, normalize_coordinate; print(normalize_timestamp('2026-01-12T15:32:00.123456789+05:30')); print(normalize_coordinate('+12.9716000',90)); print(normalize_coordinate('7.75946e1',180))"

Expect UTC 2026-01-12T10:02:00.123456789Z, resolved status, source_offset +05:30;
coordinates 12.9716 and 77.5946. The raw timestamp is retained in the result.

    python -c "from backend.parsers.normalization import normalize_timestamp; print(normalize_timestamp('2026-01-12T10:02:00-00:00')); print(normalize_timestamp('2026-01-12T10:02:00'))"

Expect utc_value=None and unknown_offset / missing_timezone respectively.
Failure case: normalize_coordinate('90.0000000000000000001',90) raises safe
INVALID_COORDINATE; normalize_timestamp('2026-02-30T10:02:00Z') records
invalid_timestamp and no fabricated UTC. No evidence or timestamp is rewritten.
Full previous-checkpoint regressions/results are in docs/PREIMPLEMENTATION_REVIEW.md.
No new model, package, provider, browser check or clean reinstall is claimed.
Next M2 row P03B owns candidate identifier keys/entities, keeping D-7/D-8 distinct;
no next task starts in this assignment. Entire agreed initial scope is preserved.

# P02 GPS CSV parser — 2026-11-01

P02 / 1B / M2 yazh-07, feat/p02-gps-csv, verified shared base
4bc8f307a039d7c91bcc687bb64267fbe80fb6b8. User approved GPS scope/policy and
explicitly authorized implement/test/commit/push/merge for this one task.
P02 integrated at 389652c358fab4b3b20565d592db520549028b8f;
post-merge focused/verifier/real I00 smoke PASS. Current state is in docs/ROADMAP.md. Older notes below are historical.

backend.parsers.gps_csv.parse_gps_csv consumes immutable original bytes and
caller-supplied case/evidence/processing-run UUID context. It returns a tuple
of frozen candidate observations or a safe GPSCSVError, never partial output.
No HTTP endpoint, DB write, processing-run producer, UTC normalization, entity
projection or scoring. Source authorization belongs to actual F00/F03/F05;
P04/P14 own real run publication/idempotency/private provenance. Test run UUIDs
are explicitly synthetic context, not an implemented processing lifecycle.

## Approved gps-csv/1 policy

- Same strict CSV reader and 50 MiB original-byte / 100000 logical data-row caps
  as P01, reused unchanged. UTF-8 with optional BOM, exact ordered header
  timestamp,device_id,latitude,longitude. Quoted commas/quotes/multiline text and
  LF/CRLF/CR endings supported. Reject bad quotes/encoding/NUL, missing/extra/
  duplicate/reordered headers/cells and blank required values. Header-only is
  empty. Any invalid later row rejects the entire result.
- Latitude [-90,90], longitude [-180,180], inclusive. Finite ASCII decimal
  literals with optional sign/fraction/exponent; exact Decimal range comparison
  prevents float-rounding acceptance beyond a bound. No silent whitespace trim,
  axis swap, DMS, NaN/Infinity or numeric source normalization. Precision,
  exponents and signed zero are preserved verbatim after CSV unescaping.
- Timestamp is a valid calendar date/time YYYY-MM-DD[T/t/space]HH:MM:SS with
  optional fraction and optional Z/z or +/-HH:MM. Clock hour <=23, minute/second
  <=59, explicit offset hour <=23/minute <=59. Invalid dates/offsets/zone suffixes
  reject explicitly; leap-second/unrepresentable clock values are unsupported.
  Missing zone stays unknown; no location-to-zone inference. Raw offset spelling,
  long fractional precision and -00:00 are preserved, never converted to UTC.
  P03 owns normalization and interpretation of source time uncertainty.
- Three existing-schema observations per row: gps.device/gps.latitude/gps.longitude.
  raw_value is the decoded logical source cell; normalized_value initially equals
  it. observed_at_raw is the unchanged timestamp; no observed_at_utc/entity_key
  emitted. Locator names original 1-based physical record line span and column.
  extraction_confidence=0 is an unavailable-score sentinel, not a measured model
  score, source reliability, coordinate accuracy or verified real-world location.
- Parser version gps-csv/1 and these meanings feed future P14 provenance. A pure
  parser cannot verify DB case/run joins; callers must pass authorized source
  context. Diagnostics expose fixed codes/record-start lines, no source cells.
  P04/P14B later own contract-specific accepted-run error handling.

## How you can test P02

PowerShell at repository root, pinned Python 3.14.8 and existing requirements.
No new dependency added. Prepare the unchanged schema bundle, then run:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p02-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p02-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_gps_csv -v

Expect 17 passing tests: fixture/schema/source/immutability, BOM/endings/quotes,
exact coordinate bounds/precision/signed zero, valid/missing/raw timezones,
invalid dates/offsets, header/row/encoding errors, atomic late rejection, actual
50 MiB/100000-row boundaries/overflow, safe context and real original integration.
Boundary tests allocate hundreds of thousands of observations; no performance
benchmark claim. Codex used existing exact-version CLI caches; fresh registry
resolution/clean reinstall was not tested during this task.

Inspect the supplied synthetic fixture (context is synthetic/unpersisted):

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.gps_csv import parse_gps_csv; out=parse_gps_csv(Path('fixtures/synthetic-case/gps.csv').read_bytes(),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4()); print([(x.kind,x.raw_value,x.observed_at_raw,x.source_locator) for x in out])"

Expect three observations for D-8, latitude 12.9716 and longitude 77.5946,
timestamp 2026-01-12T10:02:00Z and row 2 column locators. No normalized UTC or
verified location claim. Header-only yields an empty tuple.

Direct failure command (expected nonzero exit, INVALID_COORDINATE at line 2):

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.gps_csv import parse_gps_csv; parse_gps_csv(Path('fixtures/synthetic-case/gps.csv').read_bytes().replace(b'12.9716',b'91'),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())"

No partial observations or source-cell echo. Invalid explicit timezone examples
+01:99 and +24:00 reject with INVALID_TIMEZONE; a missing timezone is accepted
raw with no observed_at_utc. Full previous-checkpoint regressions:

    python -W error::ResourceWarning -m unittest discover -s backend/tests -v
    python -m unittest discover -s scripts -p 'test_*.py' -v
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = (Get-Command python).Source
    Push-Location frontend
    node test/cases.integration.mjs
    Pop-Location

Actual results: 147 backend run (146 pass/1 existing Windows symlink skip),
48 frontend pass, real I00 audit/intake/original/actor smoke PASS. Source test
uses actual FastAPI/F00/F01/F03/F05/SQLite/private files through HTTPX ASGI,
synthetic identities and synthetic run context, without parser/storage/case
doubles. The separate I00 smoke uses actual loopback HTTP. Prior suites retain
their disclosed doubles. Contract/types/build/DESIGN PASS; existing license
warning remains. No new UI/browser test, clean install, other OS/runtime,
hosted CI or P04 processing-publication claim. Temp DB/files are automatically
cleaned; no real evidence or external data transfer. FEATURE_SCOPE is unchanged.

Next M2 task is P03: normalize timestamps and GPS coordinates from integrated
P01/P02, preserve raw values and missing/ambiguous timezone uncertainty. No P03
work is included in this one-task assignment.

---

# P01 network CSV parser — 2026-11-01

P01 / 1B / M2 yazh-07, feat/p01-network-csv, verified shared base
22673d909b0860663b001269cefa2ac6f302a881. User approved the parser scope/policy
and explicitly authorized finish/test/commit/push/merge for P01 only.
P01 is integrated at cab08f1c38745255ca1c0a210636476b84bad43c;
post-merge focused parser and real intake smoke pass. Integration state is in docs/ROADMAP.md. Older producer notes below are historical.

backend.parsers.network_csv.parse_network_csv consumes immutable original bytes
and caller-supplied case/evidence/processing-run UUID context. It returns frozen
candidate observations as a tuple, or raises NetworkCSVError without returning
partial results. No HTTP route, storage, authorization grant, processing-run
creation/publication, identity inference, entity/event projection or scoring.
F03/F05 authorize originals; P04/P14 own runs, idempotency and private provenance.
Synthetic parser-test run UUIDs are not a working processing producer.

## Approved network-csv/1 policy

UTF-8 with optional leading BOM; exact ordered logical header
(timestamp,device_id,ip_address,event). Strict quote placement, escaped quotes,
quoted commas/multiline values and LF/CRLF/CR endings. Reject changed/duplicate/
reordered headers, missing/extra columns, blank required values/records, NUL,
bad encoding/quotes, nonliteral/invalid IP (including scopes/hostnames/CIDR).
At most 50 MiB original bytes and 100000 logical data records, inclusive.
Header-only input honestly returns no observations. No hidden small field cap:
the local scanner does not alter global csv.field_size_limit. Excess columns
reject early. A late invalid row never returns a valid partial prefix.

Each record emits network.device/network.ip/network.event via existing
Observation fields. raw_value is the exact decoded logical CSV cell after
unescaping; normalized_value initially equals it, without trimming or IP/time/
Unicode normalization. Each retains observed_at_raw; no UTC/entity_key is
invented. Locators name original 1-based physical row/column, including multiline
spans. Source bytes/hash are never rewritten. extraction_confidence=0 is an
unavailable-score sentinel, not measured probability or source reliability.
Parser version network-csv/1 and this meaning are inputs to future P14 private
provenance. P03 handles timestamps; P03B/P03C derive candidate keys/events.
Errors expose fixed codes/line numbers, never source cells or filenames. Later
P04/P14B must map processing failures under their own contract/policy.

## How you can test P01

PowerShell at repository root, pinned Python 3.14.8 and existing requirements.
No packages were added. Prepare the unchanged schema bundle, then run:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p01-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p01-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_network_csv -v

Expect 14 passing tests: fixture/schema/source IDs, immutable results/copies,
BOM/endings, quoting/multiline/Unicode/IPv6 raw preservation, malformed/invalid
controls and atomic late rejection; actual 50 MiB and 100000-row boundaries and
overflow; safe context/errors; CSV-writer round trips and real F03/F05 integration.
Boundary tests allocate hundreds of thousands of observations. No resource
benchmark/performance claim is made. Fresh registry resolution is not claimed;
Codex used installed exact-version CLI caches without a TLS workaround.

Quick fixture inspection (context is explicitly synthetic/unpersisted):

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.network_csv import parse_network_csv; out=parse_network_csv(Path('fixtures/synthetic-case/network.csv').read_bytes(),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4()); print([(x.kind,x.raw_value,x.observed_at_raw,x.source_locator) for x in out])"

Expect six observations: D-7/203.0.113.7/connected at row 2 and
D-9/203.0.113.9/connected at row 3, each preserving its original timestamp.
Direct failure command (expected nonzero exit, safe INVALID_IP at line 2):

    python -c "from pathlib import Path; from uuid import uuid4; from backend.parsers.network_csv import parse_network_csv; parse_network_csv(Path('fixtures/synthetic-case/network.csv').read_bytes().replace(b'203.0.113.7',b'999.1.1.1'),case_id=uuid4(),evidence_id=uuid4(),processing_run_id=uuid4())"

Failure case in test_bad_ip_literals likewise replaces the first IP;
expect NetworkCSVError with code INVALID_IP and line 2, no partial output or
source text in diagnostics. No UI processing result or stored run is claimed.
Use only synthetic/permitted fixtures; originals remain byte-identical.

Completed-checkpoint regressions, with EVORA_CONTRACT_BUNDLE still set:

    python -W error::ResourceWarning -m unittest discover -s backend/tests -v
    python -m unittest discover -s scripts -p 'test_*.py' -v
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = (Get-Command python).Source
    Push-Location frontend
    node test/cases.integration.mjs
    Pop-Location

Actual results: 130 backend run, 129 pass/1 Windows symlink skip; 48 frontend
pass; real full I00 intake/audit/original/actor smoke passes. Focused integration
uses actual FastAPI/F00/F01/F03/F05/SQLite/private files with HTTPX ASGI transport,
synthetic identities and synthetic run context only. No case/storage/parser
double. I00 separately uses actual loopback HTTP. Existing suites retain their
declared doubles. Contract lint/bundle/types/build/DESIGN pass, with existing
missing-license warning. Existing pinned dependencies reused through an ignored
node_modules junction. Clean install, new hosted CI, other OS/runtime coverage,
model/provider and P04 processing publication are untested. Temporary test DBs/
files are automatically cleaned. No real evidence or external data transfer.
Full initial scope and approved additions remain unchanged in FEATURE_SCOPE.
Next M2 task is P02 GPS parsing; P03 requires both P01/P02. No P02 work here.

---

# EVORA backend

## F09 M1 access and error regression matrix

**F09 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f09-m1-access-regressions`, common base
`53bac04ed4b94f10334dc92a5ecead2c11dfecad`.

`backend/tests/test_m1_access.py` checks all eight current M1 operations against
the real routers and shared contract: create/list/get cases; upload/list/get
evidence; original download; case audit listing. A route-inventory assertion
requires an explicit matrix entry when a M1 router gains another operation.
Every operation rejects missing/invalid/malformed/duplicate or replaced tokens.
Every case-scoped operation denies foreign/nonexistent/revoked cases; evidence
reads also reject mismatched resources when the actor belongs to both cases.

Create/list cases have no case-ID path parameter. Their applicable regressions
verify server-authored membership, actor-filtered listing and rejected forged
ownership body fields; they do not invent a foreign-ID response. Positive
baselines exercise both synthetic actors and distinct originals. Denied
requests leave cases/memberships/evidence/audit/private provenance and original
file bytes unchanged. Error bodies validate as the declared flat `ApiError` and
do not echo submitted credentials, private source markers or resource IDs.

The new matrix exposed SQLite integer overflow in case/evidence list offsets
larger than the signed SQLite range. The existing contract allows nonnegative
offsets without an upper bound; those routes now return a correct empty page
when the offset is beyond the total, consistent with F07. No status, wire field,
route, identity provider or dependency was added. Automatic production token
expiry remains unimplemented; replacing the synthetic verifier is tested as
credential invalidation, not a claim of expiry behavior.

### How you can test F09

Use the prepared isolated environment by opening
`.\.cache\setup\evora-shell.cmd` from the repository root. In its CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_m1_access -v
python -W error::ResourceWarning -m unittest backend.tests.test_m1_access.M1AccessTests.test_all_case_routes_have_identical_foreign_and_missing_denials_for_both_actors -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expect **14 focused matrix tests passed**, **one selected failure-case test
passed**, and **116 combined backend tests run: 115 passed, one known Windows
symlink-permission skip**. Inputs are three synthetic cases (two owned by one
actor), two synthetic identities, the synthetic network CSV and distinct binary
originals. Every producer/guard/SQLite/filesystem operation is real; no endpoint
or database result is mocked. The selected failure case proves identical
foreign/missing 404 application bodies/headers across all six scoped operations
for both actors, with no denied-write changes. Temporary data cleans up.

Shared checks run via `& .\.cache\setup\verify.ps1` from PowerShell. Local
results: 122 coordination and 48 frontend tests pass; contract lint/bundle,
generated strict types, freshness/typecheck/build, DESIGN and whitespace pass.
Real localhost eight-operation missing-auth and six-operation foreign/missing
matrix, offset boundaries and unchanged SQL/file read-back passed, as did the
existing case/create/upload/download real-client regression. The ignored local
smoke is `.cache/f09/http_smoke.py`; its own server/data clean up automatically.

F09 integrated through PR #14 at **868d697f297748614befdcc6af8a66370b48240b**,
containing task commit **4a69cafae6fb02c770f552c13b14430ac57e5e99**. Ubuntu and
Windows PR CI passed (Run **41301012667**); exact merged-tree real API matrix
and existing client regressions passed. F09's bounded acceptance is **Complete**.
Next is **I00**, a shared real API/UI intake gate requiring an explicit assignee.
M1's later F08 needs real P04/P14 processing dependencies. No new browser,
production expiry or Checkpoint 1A completion is claimed here. Full initial
scope, approved additions, spec, frontend and dependency manifests are unchanged.

## F07 authorized case audit-event list

**F07 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f07-case-audit-list`, common base
`441d37de6db68f1f459aa11eb1bf6bd5864f5b77`.

`GET /api/v1/cases/{caseId}/audit-events` (`listAuditEvents`) returns the existing
`AuditPage` contract after current bearer authentication and case-membership
checks. `limit` defaults to 20 (1–100); `offset` defaults to 0 (nonnegative).
Results are oldest first by server UTC creation time, with ID ascending as the
tie-break. Count and page share one SQLite read snapshot; a beyond-end offset
returns an empty items array while retaining the authorized total, including
offsets larger than SQLite's integer range. Separate requests read current
history; offset pagination does not freeze a case across concurrent changes.

The explicit column projection returns `AuditEvent` fields only, omits a null
optional reason and never joins private intake provenance. Responses carry
`Cache-Control: no-store`. Invalid UUIDs/pagination use the shared 400 ApiError;
missing/invalid authentication returns 401. Foreign and nonexistent cases have
identical 404 bodies/headers. Revoked membership takes effect on the next
request. Storage failures remain server errors rather than successful empty
history. Listing adds no event or mutation. Only this existing GET operation is
added; there are no new selectors, frontend views or audit-write APIs.

### How you can test F07

From the repository root, open `.\.cache\setup\evora-shell.cmd` on this prepared
machine to select the pinned local Python/Node/npm environment. In its CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_audit_list -v
python -W error::ResourceWarning -m unittest backend.tests.test_audit_list.AuditListTests.test_two_cases_are_filtered_and_foreign_missing_denials_are_indistinguishable -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expect 15 focused F07 tests to pass, and one passing selected failure-case test.
Fixtures use the synthetic network CSV, two actors/cases and real upload/audit
producers with SQLite/private files. The selected failure proves an actor
cannot list another case's audit, and gets the same 404 as a nonexistent case.
Other checks cover 21-item pagination, equal-time ID ties, safe fields, optional
reason, empty/huge offsets, invalid input, current memberships, read-only listing
and failed storage. A WAL test schedules a real second-connection append between
the count and page queries and verifies one consistent response. Temporary
databases/files clean up automatically. Full shared checks can be rerun from
PowerShell with `& .\.cache\setup\verify.ps1`.

Local combined regression results: **102 backend run (101 pass, one known
Windows symlink-permission skip), 122 coordination and 48 frontend pass**.
All 15 F07 tests execute without skips. Contract lint/bundle/generated strict
types, frontend freshness/typecheck/build, DESIGN and whitespace pass. Real
localhost audit API/SQL/original read-back and existing case/upload/download
client integration passed. These checks use synthetic identities/data with real
FastAPI, SQLite, files and HTTP. Ordering/optional reason/concurrent-append tests
use explicit synthetic SQL events; connection tracing schedules the real WAL
append without mocking either SELECT or result. Tests remove temporary data.
No new browser/accessibility or production identity claim is made.

F07 integrated through PR #13 at **6687d7cbd820fc4db820d85e4dcd518dd941c99d**,
containing final task commit **e7cd61402e87d2afbed1eafa8ab930e2597dea2b**.
Ubuntu and Windows PR CI passed (Run **41299455397**); exact merged-tree real
audit API/SQL and existing case/upload/download client checks passed. F07's
bounded acceptance is **Complete**. F09 is the next M1 task; the I00 shared
intake gate still needs an explicit assignee. Full agreed scope is unchanged.

## F06 append-only intake audit and private provenance

**F06 / Checkpoint 1A / M1 / sharmelas-925 / Complete**, task branch
`feat/f06-intake-audit`, verified common base
`3eab939ada44363de5420d542ead711198ccea0f`.

Each successful `uploadEvidence` now appends a server-authored `AuditEvent`
using the authenticated actor, authorized case, Evidence ID and UTC intake time.
Its action is the existing operation identifier `uploadEvidence`. Public audit
contains safe references only; uploaded filenames, source labels, acquisition
text, bytes, bearer credentials and private storage paths are not added to it.
The upload's existing 201 `Evidence` response is unchanged.

The linked private `intake_provenance` snapshot (`intake-source.v1`) preserves
the original filename/source label/media type/acquisition text, byte hash/size
and intake time from the actual inserted evidence metadata. It stores no raw
file bytes, bearer token or model output. Evidence metadata, audit and private
provenance commit in the same SQLite transaction. A metadata/accounting/commit
failure rolls all records back and uses the existing upload cleanup to remove
that upload's file. Invalid, unauthorized and oversized uploads create no
successful-intake event. A repeated successful upload creates a new Evidence
ID/event; the upload contract has no idempotency key or implicit deduplication.

Startup adds empty accounting tables to existing databases and preserves prior
originals/metadata. It does not invent actors or backfill history for evidence
uploaded before F06. SQL triggers reject ordinary UPDATE, DELETE, replacement
and UPSERT mutations of both accounting tables. This is application/database
write protection, with no claim of tamper resistance against a database owner
who changes the schema. Crash/power-loss recovery across filesystem and SQLite
has not been verified by this task.

### How you can test F06

Use the pinned Python/Node environment and `requirements.txt`. On this prepared
machine, launch `.\.cache\setup\evora-shell.cmd` from the repository root; the
new CMD shell selects the existing isolated toolchain. Run:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_audit -v
python -W error::ResourceWarning -m unittest backend.tests.test_audit.IntakeAuditTests.test_provenance_insert_failure_rolls_back_event_evidence_and_original -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

- Expect **17 focused tests passed** and **one selected failure-case test
  passed**. Synthetic inputs include `fixtures/synthetic-case/network.csv`,
  binary originals, two test identities/cases and private-data markers.
  Read-back validates the shared `AuditEvent` schema and exact source/hash/size,
  preserved timestamp text, original download and no cross-case association.
- The failure case uses a real SQLite trigger to reject provenance insertion
  after the audit insert. Expected result: evidence/audit/provenance counts are
  zero and the temporary original file is removed. Other tests exercise audit
  insert and deferred commit failure, retry, SQL replacement rejection, denied
  uploads, private logging and legacy database startup.
- Expect **87 combined backend tests run: 86 passed, one Windows symlink test
  skipped** on this account. All 17 F06 tests execute without skips. The tests
  create and automatically clean temporary synthetic databases/files.
- Shared regressions can be run from PowerShell with
  `& .\.cache\setup\verify.ps1`. The existing real API/client regression is
  `node frontend/test/cases.integration.mjs` after frontend tests/build, with
  `EVORA_TEST_PYTHON` set to the absolute `.venv\Scripts\python.exe` path.

Integrated through PR #12 at **1b5166d91e0f3b86b85585d714a917a3efc82d44**.
Ubuntu and Windows PR CI passed (Run **41297980571**); post-merge real HTTP/SQL
and existing case/upload/download client integration passed on that exact tree.
All of the focused/backend/shared checks and real localhost integration above
were exercised. F06's local HTTP/SQL smoke is in the ignored
`.cache/f06/http_smoke.py`; it stops its own server and removes its temporary
files. No new browser acceptance is claimed. The audit-list API is delivered by
the separate **F07** task above; private provenance has no public route.
Processing/model/RAG provenance remains with its existing later tasks. Full
initial scope, approved additions, API schemas and dependencies are unchanged.
F06's bounded intake acceptance is Complete. F07 is the next M1 task; the
Checkpoint 1A end-to-end gate remains open.

## F05 authorized original download

`GET /api/v1/cases/{caseId}/evidence/{evidenceId}/content`
(`downloadEvidence`) requires bearer authentication and current case membership.
It returns 200 with unmodified original bytes, `Content-Type:
application/octet-stream`, attachment filename and `Cache-Control: no-store`,
regardless of the uploaded MIME type. It uses a case-scoped SQLite lookup and
checks that the resolved storage path is a regular file strictly inside the
configured storage root's authorized case directory, including symlink checks.

Missing/invalid credentials return 401 ApiError. Invalid path UUIDs return
400 `{"code":"INVALID_INPUT","message":"Invalid request input."}`.
Foreign/missing cases, mismatched/missing evidence IDs, missing files and unsafe
stored paths return 404 `{"code":"NOT_FOUND","message":"Resource not found."}`
without a server path. This is the full-byte download contract; clients must
avoid persistent evidence caching. UI download/playback remains U04/U14 work.

Run the bundled-schema evidence suite using an interpreter with
`requirements.txt` installed:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v
```

The 23 evidence tests include F03/F04 regressions and seven F05 tests using real
FastAPI/SQLite/private storage with automatically cleaned temporary directories.
They verify the synthetic network.csv byte/hash round trip, empty/binary files,
headers, authentication, case/resource isolation, UUID validation, revoked
membership and tampered paths. Symlink creation is tested where the OS/account
permits it; otherwise that test explicitly skips. F05 platform limits and full
verification are recorded in `docs/PREIMPLEMENTATION_REVIEW.md`.

## F04 evidence metadata and listing

`GET /api/v1/cases/{caseId}/evidence` (`listEvidence`) returns 200
`EvidencePage` with `items`, `total`, `limit`, `offset`. It reads only the
authorized case's SQLite evidence, ordered by `created_at DESC, id ASC`.
Count and page share one read snapshot. `limit` defaults to 20 (1–100) and
`offset` to 0 (minimum 0). An empty case or offset at/beyond the total returns
empty `items` with the accurate total and requested pagination values.

`GET /api/v1/cases/{caseId}/evidence/{evidenceId}` (`getEvidence`) returns
200 `Evidence` from the same authorized case. Both routes omit absent
`acquired_at`, preserve stored timestamp text, and exclude private storage paths.
Both require bearer authentication and current case membership. Missing/invalid
credentials return 401; inaccessible/missing cases and missing/mismatched
evidence return 404 `{"code":"NOT_FOUND","message":"Resource not found."}`.
Invalid UUIDs or pagination return 400
`{"code":"INVALID_INPUT","message":"Invalid request input."}`.

Using the pinned requirements environment, run the real upload/read integration
and bundled-schema checks from the repository root:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v
```

The 16 evidence tests cover upload regressions and metadata reads, 23-item
pagination with timestamp ties, limits/empty pages, two actors and multiple
cases, revoked membership, UUID/input/authentication errors and omission of
private paths. They use real FastAPI/SQLite/private temporary storage with
synthetic identities and evidence. F04 verification and platform limits are
recorded in `docs/PREIMPLEMENTATION_REVIEW.md`.

## F02 authorized case listing

`GET /api/v1/cases` (`listCases`) requires `authenticated_actor` and returns
200 `CasePage` with `items`, `total`, `limit`, `offset`. Only current SQLite
`case_members` memberships for the authenticated actor are returned. Cases sort
by `created_at DESC, id ASC`; absent descriptions are omitted. Count and page
share one database read snapshot. `total` counts all accessible cases before
pagination. No cases or an offset at/beyond total returns empty `items` while
preserving the total and requested pagination values.

`limit` defaults to 20 (1–100), `offset` to 0 (minimum 0). Invalid pagination
returns 400 `{"code":"INVALID_INPUT","message":"Invalid request input."}`;
missing/invalid bearer credentials return the existing 401 ApiError.
No production identity provider is configured by default.

To test with synthetic identities and automatically cleaned temporary SQLite:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_cases -v
```

Use the pinned requirements environment. Expect 14 tests to pass, including
23-case pagination with timestamp ties, actor isolation/revocation, empty pages,
limit boundaries and rejected `limit=0/101/abc`, `offset=-1`, missing/invalid auth.
See [F02 verification](../docs/PREIMPLEMENTATION_REVIEW.md#f02-verification--2026-10-25).

## F01 case persistence (current behavior)

**F01 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f01-case-persistence`, exact common base
`86f14eedc575032d636a77233b19f13bf665c077` (includes merged F00).
The earlier F00/G01 sections below retain their historical verification results;
F01 supersedes their statements that domain routes/tables are absent.

Startup initializes `cases(id TEXT PRIMARY KEY, title TEXT NOT NULL,
description TEXT, created_at TEXT NOT NULL)` and
`case_members(case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
actor_id TEXT NOT NULL, PRIMARY KEY(case_id, actor_id))`. Both writes commit in
one SQLiteDatabase unit of work; failed membership insertion rolls back the case.
Connections remain request-owned and always close. Startup is repeatable and
preserves existing cases. SQLite is authoritative; there is no in-memory store.

- `POST /api/v1/cases` (`createCase`) requires `authenticated_actor` and returns
  201 with a UUID4, unchanged title/description and UTC `created_at`. The creating
  actor receives membership. Title is a strict string of 1–200 characters and
  must contain non-whitespace text; optional description is a strict string of
  at most 5000 characters. Explicit null and additional properties are rejected.
  Absent description is omitted from the response.
- `GET /api/v1/cases/{caseId}` (`getCase`) uses `require_case_access` and returns
  the persisted Case. `SQLiteCaseAccess` is the default adapter, queries current
  membership on every request and uses the same indexed query for foreign and
  nonexistent UUIDs. Both denials use the existing fixed 404 body and no-store
  headers. Storage failures propagate as server errors. Identical code/query
  paths avoid existence-specific branches; no constant-time guarantee is claimed.

Authentication still defaults to rejecting all tokens. Configure the existing
`SyntheticTokenVerifier` privately for the two local synthetic actors; no token
issuance or production provider is introduced. Explicit case-access injection
remains available. F02 adds listing above; upload remains outside these tasks.

The unchanged contract currently requires flat `ApiError` bodies, for example
`{"code":"NOT_FOUND","message":"Resource not found."}`. Validation uses the
existing flat `INVALID_INPUT` mapping. The task request's nested `error` envelope
and `BAD_REQUEST` conflict with that contract and F00/U01 consumers; the F01
assignment records the pending decision. Current checks verify the existing
contract, not the requested alternate envelope.

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_cases
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest discover -s backend/tests
```

Use the pinned requirements environment described below. Focused tests use real
FastAPI, file-backed SQLite, synthetic identities and temporary directories that
clean up after tests. They cover persistence across app restart, absent optional
fields, validation/authentication/path negatives, same-response case isolation,
revocation, rollback, foreign keys/cascade and real membership-storage failure.
Case and error responses validate against the bundle when configured. See the
[F01 verification record](../docs/PREIMPLEMENTATION_REVIEW.md#f01-verification--2026-10-25)
for actual results and limits. Next M1 task is F02 after F01 acceptance;
Checkpoint 1A and browser integration are not complete.


## F00 authentication and case-access dependencies

**F00 / Checkpoint 1A / M1 / sharmelas-925 / In Progress**, branch
`feat/f00-auth-case-guard`, common contract/base
`f8c5fe7b7abf62a02d8dd96fd89ad7bd6e57b029`.

`backend.auth.authenticated_actor` accepts one well-formed HTTP bearer header.
Missing, malformed, duplicate or rejected credentials return HTTP 401 with
`{"code":"UNAUTHORIZED","message":"Authentication required."}` and
`WWW-Authenticate: Bearer`. Query parameters, cookies and actor headers cannot
supply identity. `require_case_access` validates the contract's UUID `caseId`
path parameter and checks current membership before the route handler runs.
Foreign and missing cases return identical HTTP 404 bodies and headers:
`{"code":"NOT_FOUND","message":"Resource not found."}`. Both access errors
use `ApiError` and `Cache-Control: no-store`; malformed authenticated case IDs
use the existing safe 400 mapping. No submitted credential or case ID is echoed
by these errors or logged by the guards.

The app factory accepts keyword-only `token_verifier` and `case_access` adapters.
It defaults to rejecting every token and denying all case access. Explicit local
development callers can supply `SyntheticTokenVerifier({token: actor_id})` for
C-03's two synthetic identities, `investigator-1` and `investigator-2`. Supply
opaque tokens privately; actor IDs themselves are not built-in credentials.
The verifier copies configuration and retains token digests, not plaintext
tokens. No shared token, token issuance/login route, automatic expiration or
production identity provider is implemented. Replacing the verifier applies on
the next request without a cached identity. Future adapters must enforce their
selected expiry/revocation policy and return `None` for rejected credentials.

Future case routes use `Depends(authenticated_actor)`; case-scoped routes use
`Depends(require_case_access)`, whose immutable internal result carries the
authenticated actor and authorized case UUID. F01 must supply a `CaseAccess`
adapter whose `allows(actor_id, case_id)` returns true only for an existing case
with that actor's authoritative membership. Membership is checked on every
request; storage errors propagate as server failures without reaching the route
handler. This dependency adds no persistence schema or public operation. Child
resource producers must still check their own same-case joins. Protect every
future route explicitly; F00 does not automatically authenticate arbitrary routes.

### How you can test F00

Use the pinned Python 3.14.8 environment and `requirements.txt` installation
described below. On the locally prepared machine, open
`.\.cache\setup\evora-shell.cmd` from the repository root to select the isolated
Python/Node/npm toolchain. In that CMD shell:

```bat
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output .cache\setup\evora-openapi.json
set "EVORA_CONTRACT_BUNDLE=%CD%\.cache\setup\evora-openapi.json"
python -W error::ResourceWarning -m unittest backend.tests.test_auth -v
python -W error::ResourceWarning -m unittest backend.tests.test_auth.AuthenticationTests.test_foreign_and_missing_cases_have_identical_status_body_and_headers -v
python -W error::ResourceWarning -m unittest discover -s backend/tests -v
```

Expected: **19 focused F00 tests**, **1 selected foreign/missing failure-case
test**, and **33 combined backend tests** pass without skips. The tests exercise
real FastAPI dependency resolution, HTTPX ASGI transport, the shared contract's
`ApiError` schema and real temporary file-backed SQLite. Inputs are two synthetic
tokens/actors and two UUID cases plus one missing UUID. Test-only `/_test/...`
routes and SQLite membership tables stand in for the absent F01 producer; they
are never registered/created by the application factory. Denied synthetic writes
leave the test table empty; a failed membership lookup returns a server error
and never reaches a protected handler. Temporary databases clean up automatically.

The default server still exposes no public operations: `GET /` returns 404,
and no sign-in/case/evidence UI can be tested end to end yet. F01 persistence,
real U01/browser/CORS integration, production authentication and remote CI on this
uncommitted branch are unverified. Full initial scope and approved additions are
unchanged. F00 stays In Progress pending review and real producer integration.

## G01 backend skeleton

Task **G01 / Checkpoint 0**, `whale2186`, branch `feat/g01-backend-skeleton`,
common contract/base `1721bfff9640263d2799434455cdb9c4f345ac35`.

The factory in `backend.app` creates a FastAPI application and checks a real
file-backed SQLite connection at startup. It registers no HTTP routes, including
health, documentation or generated OpenAPI endpoints. Domain APIs and schemas
start in later tasks. `specs/openapi.yaml` draft 0.3.0 remains the HTTP authority.

## Tested environment and setup

The local tested baseline is **CPython 3.14.8**, recorded in
`backend/.python-version`, with **SQLite 3.54.0** from this Python build.
`requirements.txt` pins runtime/test packages and their transitive dependencies:
FastAPI 0.143.1, Starlette 1.8.0, Pydantic 2.14.1, Uvicorn 0.54.0,
HTTPX 0.28.1 and jsonschema **4.25.1**. SQLite comes from Python's standard
library; check its actual version for each Python build.

Run everything from the repository root. With CPython 3.14.8 installed:

```sh
python --version
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

G01C clean-installed all 22 pins in a new isolated Linux environment
(`/tmp/evora-g01c-clean-venv`, without system site packages); `pip check`, package
metadata read-back and all 14 warning-strict backend tests passed. Earlier G01
cache-only results remain historical in the verification record.

The shared `.github/workflows/contract.yml` now selects CPython **3.14.8** from
`backend/.python-version`, Node **22.23.3** and npm **12.2.0**, and runs coordination,
backend and frontend checks on `ubuntu-latest` (Bash) and `windows-latest`
(PowerShell). Windows is a configured target awaiting a native runner result;
this Linux session cannot certify Windows or hosted CI. Other Python versions
are unverified. SQLite's bundled version can differ by OS/build.
See [G01C verification](../docs/PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18).

## Windows PowerShell setup and run

Prerequisites: Windows x64, PowerShell 7, Git, CPython **3.14.8** with the `py`
launcher, Node **22.23.3** on PATH, package-registry access and a writable checkout.
Run from the repository root in a fresh checkout without an existing `.venv`.
Use the venv executable directly; activation/execution-policy changes are unnecessary.
Use `npm.cmd`/`npx.cmd` to avoid PowerShell choosing their `.ps1` wrappers.

```powershell
py -3.14 -c "import platform; print(platform.python_version()); assert platform.python_version() == '3.14.8'"
node --version
npm.cmd install --global npm@12.2.0
npm.cmd --version
py -3.14 -m venv .venv
$env:PYTHONUTF8 = '1'
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -c "import sqlite3; from importlib.metadata import version; print('SQLite', sqlite3.sqlite_version, 'jsonschema', version('jsonschema'))"
$env:EVORA_CONTRACT_BUNDLE = Join-Path $env:TEMP 'evora-openapi.json'
npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output "$env:EVORA_CONTRACT_BUNDLE"
& .\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
& .\.venv\Scripts\python.exe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log
```

Expected: Node `v22.23.3`, npm `12.2.0`, `pip check` reports no broken requirements,
jsonschema `4.25.1`, **14 tests, OK**, then `Application startup complete`.
In a second PowerShell window, `curl.exe -i http://127.0.0.1:8000/` should return
**404**. Stop the server with Ctrl+C. It creates only the ignored local
`storage/evora.sqlite3`; no domain API is available. Exact full coordination
commands are in the G01C verification record linked above.

Known limits: these PowerShell commands and native Windows execution remain
unverified locally. `PYTHONUTF8=1` matches CI and ensures existing tests read the
UTF-8 planning documents consistently across Windows locales. Python installation
must include SQLite; package downloads
and native dependency wheels must be available for the selected runtime/OS.
The directory mode 0700 applies on POSIX; this skeleton does not configure Windows
ACLs. Use a private writable local directory for synthetic work. No Neo4j, model,
authentication or full-system Windows support is established by skeleton tests.

## Run and configuration

```sh
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --lifespan on --no-access-log
```

Expected: `Application startup complete`, then Uvicorn listens on localhost.
`GET /` returns 404 because G01 has no operations. Stop with Ctrl+C.
The default database is `storage/evora.sqlite3`, relative to the working directory;
the repository already ignores this local directory and SQLite files.

`EVORA_DATABASE_PATH` selects another SQLite file. `create_app(database_path=...)`
overrides the environment for embedded use/tests. Empty values and `:memory:`
are rejected; each connection represents a unit of work over a persistent file.
Startup creates missing parent directories (the final directory uses mode 0700
on POSIX), opens/checks SQLite and closes the connection. An inaccessible or
invalid database path fails startup. The skeleton creates no application tables
or migrations and does not serve storage files.

Future routes can use `Depends(get_database)` from `backend.app` to obtain the
configured `SQLiteDatabase`. Use `with database.connect() as connection:` within
one unit of work; connections enable foreign keys, commit on success, roll back
transactions on failure and always close. Do not pass a connection between
threads or retain it in application state. Domain migrations and access policy
belong to their assigned tasks.

## Validation behavior and tests

The factory overrides FastAPI's `RequestValidationError` handler. Invalid
path/query/header/body data, including malformed JSON, produces HTTP **400**:

```json
{"code":"INVALID_INPUT","message":"Invalid request input."}
```

The handler does not echo/log submitted values, bodies, field names or validation
exception details. Server response-validation errors remain server errors.
Later domain routes still need their declared constraints, authorization and
explicit domain errors; G01 does not implement F00 or generic HTTP error policy.

Build the shared bundle and run the backend command:

```sh
npx --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest discover -s backend/tests -v
```

The suite must report **14 tests, OK** without skips. Missing/invalid bundle input
fails instead of bypassing schema checks. On Windows use a writable bundle path
and set `$env:EVORA_CONTRACT_BUNDLE` to it before running the same unittest command.
HTTPX's async ASGI transport exercises the real application and FastAPI
validation, with explicit lifespan contexts and temporary SQLite files. Synthetic
`/_test/...` routes exist only in tests and do not implement domain operations.
The suite proves database read-back, transaction rollback/close, foreign-key
enforcement, isolated app configuration, startup failure and route absence.
Every invalid request response is validated against the shared bundle's
`ApiError`, including its required properties and `additionalProperties: false`.

## How you can test it

- [ ] Run the setup commands above with CPython 3.14.8; installation should exit 0.
  Clean isolated Linux installation passed in G01C; native Windows is pending.
- [ ] Build the bundle and run the backend command above: **14 tests, OK**.
  Locally exercised with clean-installed packages. To repeat using G01C's environment:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json /tmp/evora-g01c-clean-venv/bin/python -W error::ResourceWarning -m unittest discover -s backend/tests -v`.
- [ ] Run the Uvicorn command: expect startup completion and a localhost listener;
  `curl -i http://127.0.0.1:8000/` should return 404. Startup/shutdown was exercised
  in G01; G01C records its own localhost smoke result in the verification record.
- [ ] Failure case:
  `EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -m unittest backend.tests.test_validation.ValidationTests.test_malformed_json_returns_400_api_error -v`.
  Expect one test `OK`: synthetic malformed JSON returns HTTP 400 with exactly
  `code` and `message`, validates against `ApiError`, and never reaches the probe.
- [ ] Database failure:
  `python -m unittest backend.tests.test_skeleton.SkeletonTests.test_database_open_failure_prevents_startup -v`.
  Expect one test `OK`: using a directory as the SQLite file raises an actual
  `sqlite3.OperationalError` before startup completes. Both negatives were exercised.
- [ ] Run the shared artifact commands in
  [the G01C verification record](../docs/PREIMPLEMENTATION_REVIEW.md#g01c-verification--2026-10-18)
  and `git diff --check`; expect no new errors. Native Windows and remote CI
  are pending; the Linux results are recorded separately.

Tests clean up their temporary files. A manual server run leaves its ignored
SQLite file for inspection; remove only your own synthetic test file when finished.

## F03 original evidence upload

`POST /api/v1/cases/{caseId}/evidence` (`uploadEvidence`) accepts multipart
`file`, `kind`, `source_label` and optional RFC 3339 `acquired_at`. Current
case membership is required. Returns 201 Evidence with the original filename,
client-declared media type (not content verification), exact lowercase SHA-256,
size and source metadata. Acquisition text and source label are preserved;
missing acquisition time is omitted. Invalid fields/unsafe filenames return the
flat 400 INVALID_INPUT; access failures retain 401/indistinguishable 404.

Originals are limited to **50 MiB (52,428,800 bytes)**; excess returns 413
PAYLOAD_TOO_LARGE and removes the partial original. Bytes are copied and hashed
in 64 KiB chunks from UploadFile's multipart spool, without inline content
processing. This is a file-byte limit during private storage, not an ingress
request-body limit: Starlette parses/spools multipart before handler execution.
Opaque files, including empty files, can be preserved; parser content/CSV limits
belong to processing tasks. Unsafe filenames containing `..`, separators,
control characters or Windows path punctuation are rejected.

Configure `create_app(storage_dir=...)` or `EVORA_STORAGE_DIR` (default
`storage/evidence`). Keep it outside publicly served directories. Paths use
`{storage_dir}/{case_id}/{evidence_id}.bin`, never the filename. New directories
use mode 0700 and exclusive new files mode 0600 on POSIX. Originals have no
application mutation route; exclusive creation prevents overwrites. This is
application immutability, not OS/WORM protection from the service account.
SQLite stores the private path but responses omit it. Failed copies or database
transactions unlink the new file. Crash recovery across filesystem/SQLite and
storage-operator tampering are not certified by F03.

Install the pinned `requirements.txt` including python-multipart 0.0.32.
Test with temporary SQLite/storage and synthetic identities:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_evidence -v
```

Expect exact fixture hash/size/private-byte read-back, empty/timestamp uploads,
400 input/traversal, 401 authentication, 404 case isolation, 413 boundary and
partial-copy/database-failure cleanup tests. F04/F05/F06 and I00 remain separate.
