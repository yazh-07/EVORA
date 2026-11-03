# P12 exported transaction CSV — 2026-11-02

P12 / Checkpoint3A / M2 yazh-07, explicit independent assignment on
feat/p12-transaction-csv from verifiedbd1e03de15a7f212e77dac391b5efd8d6fc7af07.
User approved the bounded format/amount/currency/time/source-output policy and
commit/push/merge after acceptance. Complete after merge
c1165793cb791fe0e7eccaded43e7c8daa6ee498 with29 P12/verifier/real I00 post-merge
smoke PASS. Entire docs/FEATURE_SCOPE.md including approved additions remains unchanged; earlier
checkpoint gates stay open. Older sections below are historical.

Evidence kind transaction selects actual transactions-csv/1: strict UTF-8 optional
initial BOM, exact timestamp,account_id,amount,currency columns, nonblank cells,
50MiB/100000 rows. Preserve raw values, case/leading zeros/whitespace in account
IDs, duplicate rows, physical row/multiline column locators. Header-only is genuine
empty success. MIME/name is not content verification; no live banking access.

Amount literals match ASCII -?[0-9]+(\.[0-9]+)?, at most128 characters including
sign/decimal point. Accept negative/zero source values without inferring payment
direction. Retain raw amount; exact canonical decimal string removes redundant
integer/trailing-fraction zeros, keeps nonzero sign, negative zero ->0. No float,
Decimal-context rounding, exponent, NaN/infinity, plus sign, grouping/separators,
outer whitespace, conversion or currency-specific rounding. Currency matches
[A-Z]{3} exactly and remains a source label, without claiming ISO validity,
minor-unit rules or FX conversion. P03 time normalization preserves raw invalid/
unknown/ambiguous timestamps without fabricated UTC and retains precise known UTC.

transaction-identifiers/1 emits transaction.account/transaction.amount/
transaction.currency Observations, with exact normalized amount strings and
otherwise unchanged text. Exact account:<raw ID> keys group only within the same
case/run; Entity refs retain all supporting account Observation/Evidence IDs.
transaction-source-events/1 emits one transaction.record source-report Event per
row: summary 'Source transaction record reports: ' plus raw amount and currency.
Event cites all3 row Observations/original Evidence and actual same-case account
Entity sharing that row's account Observation. Confidence0 unavailable throughout.
No owner/person/verified transfer/fraud/criminality claim or matching-source boost.

Real startProcessing validates authorized original bytes/hash/size and actual
layout, then publishes immutable outputs/private provenance/completed pointer
atomically after SQL read-back. Freeze processing-lifecycle/6, actual parser/
account/Event versions, P03 source-normalization/1 time and parser-versioned exact
amount normalization plus byte/row/amount-length caps in processing-provenance/1;
deterministic/no model. Existing processors2/3/4/5 histories/config/output/private
records unchanged. Processing-owned guards upgrade transactionally, no new table/
column/public field/route/M1/old-parser/dependency/frontend changes. Malformed or
over-limit supported input is accepted then fails safely CSV_* with no partial
output/private success record. Same key replays original; new keys retry without
rewriting history; interrupted startup fails safely. Remaining shared UI/graph/
full-modality/analytical gates stay required.

Local results: focused P12/dispatch43 PASS (P12 contributes29); full backend407
run:406 PASS/1 existing Windows symlink SKIP; frontend48/coordination122 PASS.
Contract/types/build/DESIGN/verifier/real I00 smoke PASS. Exact verification and
limits in docs/PREIMPLEMENTATION_REVIEW.md. Hosted CI not yet claimed.

## How you can test P12

PowerShell from repository root with pinned requirements and Node22.23.3 installed.
Use CPython3.14.8; tested local workspace interpreter:

    $py = (Resolve-Path '../evora-tools/python/tools/python.exe').Path

For another checkout with Python3.14.8 on PATH, use $py = (Get-Command python).Source.
Generate the bundle and run focused tests:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p12-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p12-openapi.json"
    & $py -W error::ResourceWarning -m unittest backend.tests.test_transactions -v

Expect29 PASS. Test-generated synthetic input:

    timestamp,account_id,amount,currency
    2026-01-12T15:30:00.123456789+05:30,AC-007,000123456789012345678901234567890.1200,USD
    2026-01-12T10:00:00,AC-8,-001.2300,EUR

Expect6 Observations/2 account candidates/2 source-report Events. Account keys
account:AC-007/account:AC-8 preserve exact text. Amounts normalize to
123456789012345678901234567890.12 and -1.23, raw strings preserved. First UTC is
2026-01-12T10:00:00.123456789Z; second UTC absent. Each Event cites all row sources
and real account participant. Six actual adapter sources together28/11/7; separate
identical account keys from distinct originals retain separate IDs/confidence0.

Independent actual HTTP smoke starts/stops temporary Uvicorn/private SQL:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_transactions.TransactionLoopbackTests -v

Expect1 PASS: upload/start/poll/source/Entity/Event APIs, original bytes, participant
joins/replay/private hash/version read-back. Synthetic header above plus t,AC-7,1,
(blank currency) is accepted then fails CSV_INVALID_ROW with no new output/private
success record; prior good totals remain6/2/2.

Signed/zero/decimal/currency/length failures:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_transactions.TransactionProcessingTests.test_signed_zero_and_128_character_amounts_publish_without_rounding backend.tests.test_transactions.TransactionProcessingTests.test_invalid_amount_currency_length_and_changed_frozen_amount_cap_fail_atomically -v
    & $py -W error::ResourceWarning -m unittest backend.tests.test_transactions.TransactionParserProjectionTests.test_real_byte_limit_and_overflow backend.tests.test_transactions.TransactionParserProjectionTests.test_real_row_limit_and_atomic_overflow -v

Expect PASS: -0.00 ->0 while raw preserved; exact128-character amounts and long
fractional strings publish without rounding, including when test Decimal context
precision is2. NaN/1e3/usd/129-character amounts fail CSV_INVALID_AMOUNT/
CSV_INVALID_CURRENCY/CSV_AMOUNT_LIMIT; earlier valid row never leaks. Actual50MiB/
100000-row parser boundaries succeed, +1 byte/row fails. Caps are not patched lower.
Other tests cover BOM/multiline/unicode/blank/duplicate/precise/unknown-time/case/
forged-context controls, actual100001-row failed run, all-page schemas and sources,
concurrent replay/duplicate worker/new-key/history, membership/missing originals/
body400, private corruption/participant rollback, interrupted retry and old guards.

Regression commands:

    & $py -W error::ResourceWarning -m unittest discover -s backend/tests -v
    & $py scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
    & $py -m unittest discover -s scripts -p 'test_*.py' -q
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = $py
    node frontend/test/cases.integration.mjs

Doubles/limits: synthetic tokens/actors/CSV only. Actual FastAPI/SQLite/private
originals/parser/exact normalization/projectors/provenance/publication/readers.
Core HTTPX ASGI is in process; independent Uvicorn is real HTTP/private SQL.
Explicit scheduler/registry/verifier/missing-participant injections, old-guard
recreation and trigger-bypassing temp SQL corruption are test controls. Decimal
context precision is deliberately changed only in a pure test; producer uses no
Decimal context. No successful producer replacement. Earlier suites retain their
documented controls including P14C actual dedicated-child hard exits. No live bank/
real evidence/production identity/model/full UI/graph workflow/distributed deployment/
hardware power-loss or maximum-size successful pipeline performance claim. Tests
clean temp files/servers; optional cleanup removes only your generated TEMP bundle.

Next M2 catalog P13(3A) text candidate-entity extraction has actual P06/P07
prerequisites but needs its own agreed extraction/evaluation/file handoff. Automatic
selection still waits for earlier checkpoint exits; earlier independent work must
be separately explicitly assigned. P13B and every remaining modality/feature/
approved addition stay required. No next task started.

# P11 exported mobile activity — 2026-11-02

P11 / Checkpoint3A / M2 yazh-07, explicit independent assignment on
feat/p11-mobile-records from verifiedc12deb1fa58863b333bbb6fe2b835e848dfa504d.
User approved format/output/file scope and commit/push/merge after acceptance.
Complete after merge 212a5e204437ca02b40be08b3187d2f17c6c9577 with22 P11/verifier/
real I00 post-merge smoke PASS. Full docs/FEATURE_SCOPE.md including approved
additions remains unchanged; earlier checkpoint gates stay open. Older sections
below are historical.

Evidence kind mobile_log selects actual mobile-csv/1. One agreed exported activity
layout: strict UTF-8 optional initial BOM, exact timestamp,device_id,event,detail
columns, nonblank cells,50MiB/100000 data rows. Preserve raw whitespace, device
case/leading zeros, duplicates and physical row/multiline spans. Strict CSV quoting;
malformed/over-limit input fails atomically. Header-only genuine empty success.
MIME/name alone never verifies content, and this is not physical acquisition.

mobile-identifiers/1 emits three Observations per row: mobile.device/mobile.event/
mobile.detail, exact raw/normalized strings and source row/column locators. P03
source-normalization/1 resolves only supported explicit time offsets, preserving
raw timestamps/precision and uncertainty; invalid nonblank/unknown/ambiguous time
remains raw with no invented UTC. Exact device:<raw ID> keys group only inside
one supplied case/run, with fresh candidate Entity IDs and all supporting device
Observation/Evidence references. Device IDs are not verified people or owners.

mobile-source-events/1 emits one mobile.activity Event per complete row, summary
'Source mobile log reports: ' plus its original event label. Each Event cites all
three same-case row Observations, original Evidence and actual device Entity
sharing that row's device Observation. It is a source report, not a verified
occurrence. Confidence0 is unavailable for Observations/Entities/Events, with no
boost from duplicates or matches to separate originals. Copies/reruns do not alter
old outputs, keys or source records. No person identification/model inference.

Real startProcessing reads authorized immutable originals, verifies hash/size,
executes actual parser/projector and publishes output/provenance/completion
atomically after SQL read-back. Freeze processing-lifecycle/5, parser/normalizer/
Entity/Event versions and byte/row limits in existing processing-provenance/1;
deterministic/no model. Processing-owned guards add version5 transactionally;
existing processor2/3/4 output/config/private records stay unchanged, no backfill.
Same-key replay returns original run; new keys permit retry, interrupted startup
runs fail safely. Supported malformed content becomes accepted failed CSV_* with
no partial output/private success record. Other unsupported kinds still415 before
run/key creation. No public route/field/table/column/M1/old-parser/dependency/
frontend change. Shared full-modality/P05C/P14D/UI/analytical gates remain required.

Local results: P11/dispatch36 PASS (P11 contributes22); full backend378 run:
377 PASS/1 existing Windows symlink SKIP; frontend48/coordination122 PASS.
Contract/types/build/DESIGN/verifier/real I00 smoke PASS. Details and resolved
initial verification issues in docs/PREIMPLEMENTATION_REVIEW.md. Hosted CI pending.

## How you can test P11

PowerShell from repository root with pinned requirements and Node22.23.3 installed.
Use CPython3.14.8. The tested local workspace interpreter is:

    $py = (Resolve-Path '../evora-tools/python/tools/python.exe').Path

For another checkout with Python3.14.8 on PATH, use $py = (Get-Command python).Source.
Build a contract bundle and run focused tests:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p11-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p11-openapi.json"
    & $py -W error::ResourceWarning -m unittest backend.tests.test_mobile -v

Expect22 PASS. Test-generated CSV input is:

    timestamp,device_id,event,detail
    2026-01-12T15:30:00.123456789+05:30,D-007,authentication.success,"Synthetic login, not ownership"
    2026-01-12T10:00:00,D-8,app.open,Synthetic application report

Expect6 Observations/2 candidate Entities/2 source-report Events. Keys device:D-007
and device:D-8 preserve leading zeros/exact text. First row UTC is
2026-01-12T10:00:00.123456789Z; second row lacks UTC. Every Event cites its three
row Observations and real device Entity. No identity/ownership/truth claim.
Actual network/GPS/message/document/mobile test sources yield22/9/5; the three
separate device:D-8 Entities retain distinct UUIDs, sources and confidence0.

Independent real HTTP smoke starts/stops temporary Uvicorn/private SQL:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_mobile.MobileLoopbackTests -v

Expect1 PASS: actual multipart upload/start/poll/source/Entity/Event APIs,
participant joins, original byte roundtrip, replay and private hash/version
read-back. Synthetic timestamp,device_id,event,detail followed by t,D-7,e, (blank
detail) is accepted then fails CSV_INVALID_ROW. It publishes no new output/private
success record; prior good totals stay6/2/2.

Failure/resource controls:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_mobile.MobileProcessingTests.test_malformed_wrong_layout_encoding_late_row_and_actual_overflow_publish_nothing -v
    & $py -W error::ResourceWarning -m unittest backend.tests.test_mobile.MobileParserProjectionTests.test_real_byte_limit_and_overflow backend.tests.test_mobile.MobileParserProjectionTests.test_real_row_limit_and_atomic_overflow -v

Expect PASS: malformed header/encoding/late blank cell/wrong layout and100001 rows
fail with safe CSV_* codes and zero output/provenance. Actual50MiB/100000-row
parser boundaries pass; +1 byte/row fails. Caps are not reduced test substitutes.
Other focused tests exercise BOM/multiline/unicode/whitespace/duplicate/exact-key
controls, raw invalid/uncertain time, mixed-context rejection, same-case source/
participant joins, schema and all-page source APIs, concurrent replay/duplicate
worker, new-key/history, interrupted startup/retry, missing originals/auth/body400,
old-version upgrade, private corruption and verifier/participant rollback.

Regression commands:

    & $py -W error::ResourceWarning -m unittest discover -s backend/tests -v
    & $py scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
    & $py -m unittest discover -s scripts -p 'test_*.py' -q
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = $py
    node frontend/test/cases.integration.mjs

Doubles/limits: synthetic tokens/actors/CSV only. Actual FastAPI/SQLite/private
originals/parser/time/projectors/provenance/publication/read APIs execute. Core
HTTPX ASGI is in process; independent Uvicorn is real HTTP. Explicit scheduler,
changed-registry/verifier/missing-participant injections, old-version guard
recreation and trigger-bypassing temp SQL corruption are test controls. No
successful producer is replaced. Earlier suites retain documented controls,
including actual dedicated-child hard exits around P14C publication. No real
mobile acquisition/evidence, production identity provider, model, full processing
UI/graph workflow, distributed deployment, hardware power-loss or maximum-size
successful full-pipeline performance certification. Tests clean temp files/servers;
optional cleanup removes only your generated TEMP bundle.

Next M2 catalog task P12(3A) transaction CSV needs its own format/resource/file
handoff. Automatic selection still awaits earlier checkpoint exits; independent
work requires a separately explicit assignment. P13/P13B/P08 and every initial
feature/approved addition remain required. No next task started.

# P07 plain-text documents — 2026-11-02

P07 / Checkpoint3A / M2 yazh-07, explicit independent assignment on
feat/p07-document-text from verified97564aea28775c96679439dd5ffc22077ea75a64.
User approved the plain-text policy, bounded files and fixture-only unsupported-
kind updates, and commit/push/merge after acceptance. Complete after merge
c8b5331465a25175e6ee0e470795061fa786ce70 and passing18 focused/verifier/real I00
post-merge smoke; earlier checkpoints stay open. Entire docs/FEATURE_SCOPE.md including
approved additions remains unchanged. Older sections below are historical.

Kind document now selects document-text/1 through actual startProcessing. Strict
UTF-8 with one optional leading BOM; reject invalid UTF-8 and NUL bytes. Support
LF/CRLF/CR; preserve blank lines, whitespace and duplicates. Each physical line
emits one immutable text.line Observation with identical raw_value/normalized_value
and confidence0 (unavailable). Locators use line N; chars=start:end: 1-based line,
zero-based half-open Unicode code points into decoded source after its initial
BOM. Separators are excluded from line values but count in offsets; final
separator adds no extra line. Only CR/LF are separators, not Unicode paragraph
separators or form feeds. Empty/BOM-only input completes with zero observations.
Limits50MiB and100000 source lines; overflow rejects atomically. No trim/Unicode
normalization, timestamp inference, Entity or Event extraction. P13/P13B retain
those required tasks. Ordinary prose dates/D-7 remain text only.

This is one plain-text format, not PDF/DOCX/OCR decoding. MIME/name are not proof
of content; any bounded NUL-free valid UTF-8 text meets this format's byte-level
rules without certifying authenticity or semantic format. Original source bytes,
BOM, newlines and hash remain downloadable unchanged. Blank lines have an empty
raw/normalized value and zero-width content span, retaining their physical line.

Document runs freeze processing-lifecycle/4, document-text/1, normalizer/entity/
event_version=not-used (no P03 normalization or candidate execution), max_source_bytes
and max_source_lines in existing private processing-provenance/1. Deterministic,
no model. Existing network/GPS processor2 and message processor3 records/config/
provenance remain unchanged. Two processing-owned guards upgrade transactionally,
no new table/column/public route/field or M1/dependency/frontend changes. Original
access, hash verification, acceptance/replay, new-key retry, frozen history,
private manifests/digest and verified atomic completion publication are retained.
Bad text is accepted then fails safely with TEXT_INVALID_UTF8/TEXT_NUL_BYTE/
TEXT_LINE_LIMIT (parser byte overflow TEXT_BYTE_LIMIT); no partial output/private
success record. Upload's existing50MiB rejection happens before processing.

Local results: focused18 PASS; full backend356 run (355 PASS/1 existing Windows
symlink SKIP); frontend48/coordination122 PASS. Contract/types/build/DESIGN/
verifier/real I00 smoke PASS. Details in docs/PREIMPLEMENTATION_REVIEW.md. Hosted
CI not yet claimed.

## How you can test P07

PowerShell from repository root, installed pinned requirements and Node22.23.3.
Select Python3.14.8. In this local workspace the tested interpreter is:

    $py = (Resolve-Path '../evora-tools/python/tools/python.exe').Path

For another checkout with Python3.14.8 on PATH, use $py = (Get-Command python).Source.
Build the contract bundle and run the focused tests:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p07-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p07-openapi.json"
    & $py -W error::ResourceWarning -m unittest backend.tests.test_documents -v

Expect18 PASS. Synthetic UTF-8 BOM plus text (Python escape notation)
'😀 D-7  \r\n\rsecond\nsecond\n' produces4 Observations,0 Entities,0 Events.
Raw lines are '😀 D-7  ', '', 'second', 'second'; spans0:7,9:9,10:16,17:23.
Offsets are code points, not UTF-8 bytes or UTF-16 units. Both time fields are
absent, including date-like prose. Combined actual network/GPS/message/document
sources yield18 Observations/7 Entities/3 Events; old private records stay intact.

Independent real HTTP test starts/stops a temporary Uvicorn child:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_documents.DocumentLoopbackTests -v

Expect1 PASS: real multipart upload/start/poll/list/source citations, replay and
private SQL hash/parameter read-back. SOURCE above completes4/0/0. Synthetic
b'ok\nSECRET\xff' is accepted then failed TEXT_INVALID_UTF8 with no new outputs/
provenance and safe public error; prior good observations remain4. The source
content/API hash roundtrip is also tested directly in the focused suite.

Failure/limit checks:

    & $py -W error::ResourceWarning -m unittest backend.tests.test_documents.DocumentProcessingTests.test_encoding_nul_and_actual_line_overflow_fail_without_partial_publication -v
    & $py -W error::ResourceWarning -m unittest backend.tests.test_documents.DocumentParserTests.test_real_byte_limit_and_overflow backend.tests.test_documents.DocumentParserTests.test_real_line_limit_including_blanks_and_overflow -v

Expect PASS: invalid UTF-8, NUL and100001 lines fail without partial output;
actual50MiB and100000-line parser boundaries succeed, +1 byte/line fails. Caps are
not patched lower. Empty bytes/BOM-only yield0, one newline yields1 blank line.
Tests also exercise auth/foreign denial, membership revocation, missing original,
body400, changed frozen parameters, publication rollback, private corruption,
version guards, real old-guard upgrade, startup interrupted-run failure and retry.

Regression commands:

    & $py -W error::ResourceWarning -m unittest discover -s backend/tests -v
    & $py scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
    & $py -m unittest discover -s scripts -p 'test_*.py' -q
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = $py
    node frontend/test/cases.integration.mjs

Doubles/limits: synthetic identities/tokens/text only. Actual FastAPI/SQLite/
private originals/parser/provenance/publication/read APIs execute. HTTPX ASGI is
in process; separate Uvicorn is real HTTP. Scheduler holds, changed-registry and
verifier-failure injections, temporary SQL corruption and recreating old version
guards are explicit test controls; no successful text parser is substituted.
Earlier suites retain their documented controls including P14C dedicated-child
hard exits. No production identity provider, real evidence, processing UI,
PDF/DOCX/OCR/model, distributed deployment, hardware power-loss or maximum-size
successful full-pipeline performance claim. Tests clean temporary files/servers;
optional cleanup removes only the TEMP bundle you created.

Next M2 catalog work is P11(3A), one agreed mobile-record format, then P12/P13
according to dependency readiness/catalog order. P13's real P06/P07 prerequisites
become available after this integration; no extraction is claimed here. Automatic
selection still waits for all preceding checkpoint exits; earlier independent
work needs its own explicit handoff and format/resource decisions. No later task
started; whole module/checkpoint completion is not claimed.

# P06 message source and candidate device extraction — 2026-11-02

P06 / Checkpoint 2A / M2 yazh-07 is explicitly assigned independent work from
verified shared base 9454430a56502dfa8dad791e3d3f420c05424509 on
feat/p06-message-mentions. Earlier 1B/I00B and 1C/I01 gates remain open.
Complete after authorized merge 1b938d93c09ad82f2ef5af8eac214026d7a820f7 and passing24 focused
P06/verifier/real I00 post-merge smoke. The full agreed initial scope and approved
additions in docs/FEATURE_SCOPE.md remain unchanged.

The real message adapter accepts UTF-8 (optional BOM), exact ordered
message_id,timestamp,sender,body columns and nonblank required cells. Header-only
input completes with empty output; duplicate rows remain separate. Limits are
50 MiB, 100000 data rows and 100000 device mention occurrences across the file.
Malformed or over-limit input fails atomically, with safe CSV_* errors.

messages-csv/1 preserves message ID, sender, complete logical body and timestamp.
message-candidates/1 emits three metadata Observations per row plus one per
standalone case-sensitive ASCII D-[0-9]+ body occurrence. Unicode word characters
and ASCII hyphens block adjacent matches; exact IDs/leading zeros stay distinct.
Locators preserve physical row spans and zero-based half-open Unicode code-point
body spans, e.g. row 2, body; chars=8:11. Spans address the decoded logical body,
not byte offsets into CSV quoting. Identical keys group only within the same run;
Entities cite all supporting full-body and mention Observations and Evidence.
Confidence 0 means unavailable. Sender is source text, not an identified person;
co-mention establishes neither ownership nor identity. P03 timestamp normalization
retains raw invalid/uncertain time without invented UTC. P06 emits no Events;
P13B retains required message/text event extraction.

startProcessing uses actual immutable originals, parser, projection and SQL
publication verification. Message runs freeze processing-lifecycle/3, parser,
normalizer, message projector, event_version=not-used and all three limits in
private processing-provenance/1. Network/GPS keep processor2 and existing private
record bytes. Version guards upgrade transactionally without backfills or schema
columns/tables. Replay, new-key retry, older completed source reads and atomic
output/provenance/completion remain intact. No new public route/field, dependency,
frontend or M1-table changes.

Local results: full backend337 run (336 PASS/1 existing Windows symlink SKIP),
added old-trigger upgrade1 PASS; initial P06/dispatch37 PASS; frontend48 and
coordination122 PASS. Contract/types/build/DESIGN/verifier/real I00 smoke PASS.
Details and limitations in docs/PREIMPLEMENTATION_REVIEW.md. Hosted CI pending.

## How you can test P06

PowerShell from repository root with Python 3.14.8, Node 22.23.3 and installed
requirements/locked frontend dependencies:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p06-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p06-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_messages -v

Expect 24 tests PASS. The actual fixtures/synthetic-case/messages.csv row contains
MSG-1, synthetic-sender and body Devices D-7 and D-8 appear together in this message.
It publishes five Observations, two Entities (device:D-7/device:D-8), zero Events;
body spans 8:11 and 16:19. Each Entity cites full body and its literal occurrence.
Combined actual network/GPS/message fixtures produce 14/7/3 Observation/Entity/
Event totals; separate Evidence retain separate Entity UUIDs for identical keys.

Independent HTTP smoke starts/stops a real Uvicorn child with temporary storage:

    python -W error::ResourceWarning -m unittest backend.tests.test_messages.MessageLoopbackTests -v

Expect one PASS: actual upload/start/poll/source APIs, replay and private SQL
read-back. Synthetic malformed input message_id,timestamp,sender,body followed by
M,t,s, (empty body) is accepted then fails CSV_INVALID_ROW, with no new outputs or
success provenance; previous good output remains 5/2/0.

Relevant failure commands (synthetic inputs are generated by the tests):

    python -W error::ResourceWarning -m unittest backend.tests.test_messages.MessageProcessingTests.test_actual_mention_and_row_overflow_fail_atomically_through_processing -v
    python -W error::ResourceWarning -m unittest backend.tests.test_messages.MessageParserTests.test_literal_case_sensitive_unicode_word_and_hyphen_boundaries -v

Expect PASS: 100001 D-7 occurrences fail CSV_MENTION_LIMIT; 100001 data rows fail
CSV_ROW_LIMIT; no partial outputs/provenance. D-7/D-007 remain exact and distinct;
d-7, XD-7, D-7x and hyphen-attached tokens do not match. Repeated matches retain
separate Observation IDs. Parser tests exercise real byte/row/mention boundaries;
there is no maximum-size successful full-pipeline performance certification.

Regression commands:

    python -W error::ResourceWarning -m unittest discover -s backend/tests -v
    python scripts/verify_coordination.py "$env:EVORA_CONTRACT_BUNDLE"
    python -m unittest discover -s scripts -p 'test_*.py' -q
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run build
    $env:EVORA_TEST_PYTHON = (Get-Command python).Source
    node frontend/test/cases.integration.mjs

Real FastAPI/SQLite/private originals/producers are used; core HTTPX ASGI is in
process and the Uvicorn test is real loopback HTTP. Identities/tokens are synthetic.
Explicit scheduler holds, changed-registry and verification failure injections,
forbidden-Event output injection and temporary SQL corruption are test controls;
no successful message parser/projector is replaced. Earlier suites retain their
documented controls, including P14C crash hooks in dedicated test children.
No real evidence, production identity provider, model, full processing UI,
distributed deployment or hardware power-loss test. Tests clean their temporary
files/servers; the TEMP bundle can be removed separately.

P06 does not complete A07/U06B/I02 or earlier checkpoint gates. Next M2 catalog
work is P07 (3A, document/text); automatic selection still waits for preceding
checkpoint exits, or requires a separately explicit independent handoff. P07's
format/limits/allowed-file decisions must be recorded before implementation.

# P14C verified atomic processing publication — 2026-11-02

P14C / Checkpoint1B / M2 yazh-07, feat/p14c-atomic-processing from verified
shared base fb52aba41310ae644bb9a12bd4884862367932cc. User approved bounded
files/recorded lifecycle policy and implementation/test/commit/push/merge into
shared docs/coordination-foundation. Complete after merge
920331d95fdd359f1e20cfbcfba48fc6e2afb292 and passing post-merge smoke;
current state in docs/ROADMAP.md. Older notes are historical.
Full FEATURE_SCOPE including approved additions remains unchanged.

Before marking a run completed, backend/processing_publication.py reads actual
SQL run/frozen context, output and P14 private record inside the publication
transaction. It compares every prepared output JSON string (including private
uncertainty) against persisted bytes, validates source/participant joins and
reconstructs P14 manifests/digest/time from SQL. Missing, corrupt or mismatched
run/case/Evidence/output/private metadata fails publication. Updating completion
must affect exactly one running row; no inference from an INSERT call or producer
return value. Output/private record/completed state commit together or roll back.

Processing-owned INSERT collision guards supplement existing UPDATE/DELETE
protections, rejecting REPLACE/UPSERT/key/hidden-rowid collisions that could
rewrite completed or failed history. They add no table/field or M1-table change.
Existing private provenance schema, public operations/status/error fields,
parser versions/limits and processor version remain unchanged. A verification
failure maps through existing safe PROCESSING_FAILED, never raw SQL/source data.

Same-key lookup returns the original actor/case/request resource before new
processing, including failure/interrupted history; another target conflicts409.
A new key permits retry with prior completed outputs/private records intact.
Concurrent same-key acceptance and duplicate worker claims publish once; separate
keys preserve every completed run. Readers see only previously completed outputs
while new SQL writes are staged; after verified commit, the new completed output
becomes visible with matching provenance. Historical Observation pins stay intact.

Existing startup policy is preserved: interrupted queued/running jobs become
failed PROCESSING_INTERRUPTED, not resumed or falsely completed. Seven actual
child-process hard-exit boundaries test queued, claimed running, output insert,
private-provenance insert, verified output, completed pointer before commit, and
after committed publication. Uncommitted writes roll back; a committed completed
run survives restart. Fresh application startup rechecks the same SQLite file,
then same-key replay retains the original resource and new-key retry succeeds.
Tests assert boundary marker/exit code, old history and SQLite/FK integrity.
This is real process-interruption testing, not hardware/OS power-loss certification.

No new public route/field/table/provenance format/parser/dependency/frontend or
M1-table changes. Core producers remain real, local and deterministic. F08 public
processing audit and remaining UI/integration gates remain required. This is the
last M2 row in1B, not whole-module/checkpoint completion. P06(2A) is next M2 catalog
work; automatic selection awaits remaining1B/I00B and1C/I01 exits. Earlier allowed
independent work needs its own explicit handoff. No next task started.

## How you can test P14C

PowerShell from repository root, Python3.14.8/Node22.23.3 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p14c-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p14c-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_processing_publication -v

Expect13 passing tests. Real synthetic network/GPS input publishes6/4/2 and3/1/1
Observation/Entity/Event IDs with P14 hash/manifest/version/time joins. A verifier
probe observes persisted outputs/private record while status is still running;
completed is published only after verification. Eight concurrent same-key starts
produce one run/execution/output/private record. Distinct-target reuse returns409;
new keys/duplicate claims preserve unique immutable histories.

Independent real localhost smoke (starts/stops Uvicorn/temp storage):

    python -W error::ResourceWarning -m unittest backend.tests.test_processing_publication.PublicationLoopbackTests -v

Expect PASS: actual network/GPS start/poll/list/private SQL, malformed CSV failed
without provenance; public totals9 Observations/5 Entities/3 Events and no private
HTTP endpoint. This smoke does not substitute successful producers.

Relevant actual interruption/retry control:

    python -W error::ResourceWarning -m unittest backend.tests.test_processing_publication.PublicationTests.test_real_child_crashes_rollback_or_preserve_commit_then_restart_replay_and_retry -v

Expect PASS across seven hard-exit stages using temporary synthetic originals.
Before commit: original resource becomes failed PROCESSING_INTERRUPTED on fresh
startup, no new output/private row leaks, old completed data remains readable.
After commit: completed run/private data survives. Same key replays exact recovered
resource; new key succeeds with new IDs. Existing original hashes/history and
pinned historical Observations stay unchanged; SQLite integrity/FK checks pass.
Only test-created child processes exit; the user application is not terminated.

SQL corruption failure control:

    python -m unittest backend.tests.test_processing_publication.PublicationTests.test_sql_output_or_private_corruption_is_rejected_before_completion -v

Expect PASS: explicit missing/corrupt SQL output/private/frozen-context fixtures
roll back and produce safe PROCESSING_FAILED, zero partial records; normal retry
still succeeds. Temp-only faults bypass immutable triggers inside the transaction;
they are not a production mutation feature. Other tests cover staged-read isolation,
exact completion row count, auth/foreign reads and REPLACE/UPSERT/hidden-rowid guards.

Core tests use actual FastAPI/SQLite/private files and P01/P02/P03/P03B/P03C/P04/
P14/P14B, HTTPX ASGI in process; independent Uvicorn is real HTTP/private SQL.
Synthetic identities, held scheduler/verification gates, parser-count wrappers,
transactional corruption and crash-hook replacements are explicit test controls.
Successful producers execute actual parsers/normalizer/projectors. Hard exits use
os._exit in dedicated test children at marker-verified boundaries, followed by
real SQLite recovery/fresh application startup; not a simulated success response.
Earlier suites retain their documented doubles. No real evidence/model/production
auth, hardware power-loss, distributed deployment, full processing UI or maximum-
size successful pipeline benchmark claim. Exact results in
docs/PREIMPLEMENTATION_REVIEW.md. Temporary servers/files/children are cleaned;
optional cleanup removes TEMP bundle. Checkpoint1B/M2 remain open; no next task started.

# P14B registered network/GPS dispatch — 2026-11-02

P14B / Checkpoint1B / M2 yazh-07, feat/p14b-processing-dispatch from verified
shared base acf07fec95442c8ae8b9c099dda827a9f68c9a5d. User approved bounded
paths/recorded C-04 policy and authorized implementation/test/commit/push/merge
into shared docs/coordination-foundation. Complete after merge
d7a4315377cc1fdae63200780bd7728c583a14dd and passing post-merge smoke;
current state in docs/ROADMAP.md. Older notes are historical.
Full FEATURE_SCOPE including approved additions remains unchanged.

backend/processing_dispatch.py explicitly registers actual network-csv/1 and
gps-csv/1 producers with parser-owned versions and limits. A read-only mapping
and frozen descriptors prevent runtime mutation of entries. Declared kind alone
selects a registered adapter; the worker invokes that actual parser to validate
original content. No filename/extension/MIME/source-label sniffing or silent
cross-kind fallback. Upload is opaque intake, not successful processing.

| Declared Evidence kind | Required exact ordered CSV header | Registered parser |
|---|---|---|
| network_log | timestamp,device_id,ip_address,event | network-csv/1 |
| gps | timestamp,device_id,latitude,longitude | gps-csv/1 |

Both retain existing UTF-8/optional leading BOM, comma/quote/multiline logical
records, LF/CRLF/CR, exact header/row/value rules and inclusive50MiB/100000-row
limits. P01/P02 own format/time/value details; no extra cap or new accepted format.
The full regression suite retains actual parser byte/row boundary tests. This
P14B suite also sends actual100001-row originals through upload/start/worker on
both adapters and observes failed CSV_ROW_LIMIT with no output/provenance prefix.
No maximum-size successful full-pipeline performance benchmark is claimed.

Unsupported declared kinds return415 before run/key creation, even if bytes look
like supported CSV. Wrong-layout or malformed supported-kind data is accepted
queued then failed with fixed safe CSV errors, never successful empty output or
rerouted to another adapter. Header-only matching CSV is genuine empty success.
A misleading filename/MIME can accompany valid bytes without overriding kind or
establishing success. Actual content validation remains mandatory.

P04 acceptance freezes selected kind/parser_version/byte-row limits and existing
normalizer/projector/processor versions. Worker compares current registered
metadata before execution; mismatch fails without invoking a changed parser.
P14's unchanged private record links actual input/hash/output IDs/digest/parameters/
versions/completion time. No config/provenance/schema/wire format or processor/
parser version change: dispatch policy is unchanged by this extraction. Same-key
lookup happens before current selection, preserving original history; new key
retries independently. Source bytes/history remain immutable, no model/provider.

Two existing processing-test injection points now replace the selected descriptor
with a test wrapper instead of mutating the removed private parser dictionary;
all existing assertions/source execution remain. No parser, P14 format, M1 table,
frontend, dependency, schema or spec edits. P14C full retry/recovery/publication
and F08 audit remain separate required work, as do all later modality adapters.

## How you can test P14B

PowerShell at repository root with Python3.14.8/Node22.23.3 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p14b-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p14b-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_processing_dispatch -v

Expect14 passing tests using synthetic actors/CSV only. Actual network.csv/GPS.csv
publish6/4/2 and3/1/1 Observation/Entity/Event IDs with matching P14 private inputs,
versions/limits/manifests/completion timestamps. Valid network bytes named gps.csv
with image/png MIME still use network-csv/1; valid GPS bytes named network.bin
with application/pdf MIME still use gps-csv/1. Original hash/bytes are preserved.
BOM/multiline quoted source locators/raw values and uncertain GPS time survive.

Independent real localhost HTTP-to-private-SQL smoke:

    python -W error::ResourceWarning -m unittest backend.tests.test_processing_dispatch.DispatchLoopbackTests -v

Expect PASS: real network/GPS start/poll yields two matching private records,
while malformed and cross-layout runs fail without provenance. Unsupported
document-kind valid network CSV returns415 with no run. Actual API totals are
9 Observations/5 Entities/3 Events, not uploaded-file counts. Server/temp storage
are created and cleaned by the test; no private HTTP endpoint is added.

Relevant wrong-layout failure control:

    python -m unittest backend.tests.test_processing_dispatch.DispatchTests.test_wrong_layout_never_silently_dispatches_to_other_kind -v

Expect PASS: GPS content declared network_log and network content declared gps
are accepted then fail CSV_INVALID_HEADER, with zero output/provenance records
and no fallback. Other controls cover bad encoding/NUL/quotes/IP/GPS values,
all other declared kinds415, auth/case isolation, row overflow, frozen version/
limit changes before parsing, replay-before-selection and failed-prefix history.

Core tests use actual FastAPI/SQLite/private files/parsers/normalizer/projectors/
P14 via HTTPX ASGI; independent Uvicorn subprocess is real HTTP/private SQL.
Synthetic actors/tokens, held scheduler, replaced selection/version/limit/parser
wrapper and failure controls are explicit test doubles. Core successful sources
and HTTP smoke do not replace producers. Prior suites retain disclosed doubles.
No production auth/model/OS power-loss/distributed worker/full processing UI/
maximum-size successful pipeline benchmark/real-evidence claim. Exact matrix in
docs/PREIMPLEMENTATION_REVIEW.md. Tests clean temp originals/database/server;
optional cleanup removes TEMP bundle. Next M2 P14C, no next task started.
Checkpoint1B/M2 remain open; full initial scope/additions preserved.

# P14 private versioned processing provenance — 2026-11-02

P14 / Checkpoint 1B / M2 yazh-07, feat/p14-processing-provenance from verified
shared base 98a28260f2fb2d91dd803c2f1835de264c5d0973. User approved bounded
paths/private-record policy and authorized implementation/test/commit/push/merge
into shared docs/coordination-foundation. Complete after merge
c03361b8171e6506d2c160a85cc1e89e76315fb3 and passing post-merge smoke;
current state in docs/ROADMAP.md. Older notes are historical.
Entire initial FEATURE_SCOPE including approved additions remains unchanged.

New processing-lifecycle/2 runs freeze processing-provenance/1 plus existing
original hash/size/kind, parser/normalizer/Entity/Event versions and row/byte limits.
Successful publication writes one private processing_provenance row in the same
SQLite transaction as immutable outputs/completed pointer, using identical
finished_at. Failure at any publication stage rolls everything back; the existing
safe failed run/config remains. Same key replays original history, new key creates
a new immutable run/record. Empty successful output has genuine empty manifests.

The private payload records case/Evidence/processing_run_id, original input
snapshot, execution versions/parameters, accepted_at/finished_at and exact output
UUID manifests. Current network/GPS adapters are deterministic and model=null
means no model used; no model installation/version/execution is invented. Existing
output observations retain locators/source values/uncertainty and processing_run_id
for source joins; no raw text, locators, filenames, storage paths, credentials or
idempotency keys are copied into this provenance manifest or logged publicly.

output_sha256 hashes UTF-8 compact sorted-key JSON mapping observations_json,
entities_json, events_json and uncertainty_json to their exact persisted JSON
strings (ensure_ascii=False, allow_nan=False). Output UUID manifests are unique
and sorted by canonical UUID. This links the record to exact private output
serialization, not a signature, independent corroboration or certified source
truth. Publication validates record shape/context and source/participant joins;
P14C's full dispatch/recovery/publication gate remains a separate required row.

One processing-owned WITHOUT ROWID table rejects UPDATE/DELETE/REPLACE/UPSERT
collisions. A completion trigger requires matching new-version provenance and
completion timestamp; old-version historical rows stay unchanged. Startup adds
an empty table without fabricating provenance for older completed runs; old
Observation/Entity/Event APIs still read those immutable outputs. P04 interrupted
queued/running startup behavior remains failed, not false success/backfill.

read_processing_provenance(app, grant, evidence_id, run_id) is an internal Python
helper, not a new HTTP endpoint. It rechecks real current case membership and
exact case/Evidence/run/output joins in a read snapshot, reconstructs the expected
private manifest/digest from frozen source records, and returns safe404 for
unavailable/legacy/pending/failed/foreign/missing/corrupt records without fallback.
Public ProcessingRun/AuditEvent fields remain unchanged; new runs expose only
the existing processor_version value bump. F08 safe processing audit linkage
through run references remains required M1 work. No M1 table, parser, frontend,
spec or dependency edits; no full modality/model/provenance-UI claim.

## How you can test P14

PowerShell at repository root, Python3.14.8/Node22.23.3 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p14-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p14-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_processing_provenance -v

Expect18 passing tests using synthetic actors and fixtures/synthetic-case CSVs.
Network.csv produces6 Observations/4 Entities/2 Events; GPS produces3/1/1.
Private manifests match these exact stored UUIDs, original SHA-256/size, frozen
versions/limits and actual run completion timestamp/digest. Empty header-only CSV
completes with three empty UUID manifests. Replay creates no additional record;
a new key preserves older records while publishing new output UUIDs.

Run independent real HTTP-to-private-SQL smoke (starts/stops Uvicorn/temp storage):

    python -W error::ResourceWarning -m unittest backend.tests.test_processing_provenance.ProvenanceLoopbackTests -v

Expect PASS: actual network/GPS start/poll completes with matching private SQL
records; malformed CSV fails with no success provenance. No private provenance
HTTP route is exposed. The internal-reader authorization checks run separately
against actual SQLite case membership, including immediate revocation.

Relevant atomic-failure control:

    python -m unittest backend.tests.test_processing_provenance.ProcessingProvenanceTests.test_provenance_failure_before_insert_publishes_no_outputs_or_completion -v

Expect PASS: explicit injected provenance-write exception produces failed run
with PROCESSING_FAILED, zero output/provenance rows, Event total0, same-key replay
of the original failure and successful new-key retry. Other tests inject faults
after private insert/completed update to prove rollback at those boundaries.

Tests also exercise immutable SQL mutation/REPLACE/UPSERT/rowid controls,
missing/foreign/revoked/context/digest corruption safe404, output reference
validation, same-time publication, historical reads and upgrade without backfill.
Core tests use real FastAPI/SQLite/private original files and actual source
parsers/normalizer/Entity/Event producers via HTTPX ASGI; a separate Uvicorn
subprocess exercises real HTTP. Synthetic auth, scheduler/publication faults,
pre-P14 schema/version fixture built from actual outputs, and temp-only corruption
bypassing immutable triggers are explicit doubles, not production incidents or
an actual historic deployment migration. Privacy tests capture application logs
and public run/audit responses using synthetic content/key/token sentinels.
No production identity provider, real evidence/model, OS power-loss/distributed
worker, full provenance UI or maximum-size performance claim. No sensitive-data
transfer. Existing unrelated test doubles remain disclosed in earlier records.
Results in docs/PREIMPLEMENTATION_REVIEW.md. Tests clean temporary files/server;
optional cleanup removes the TEMP bundle. Next M2 P14B network/GPS dispatch;
no next task started here. Checkpoint1B/M2 remain open.

# P05B source-backed Event listing — 2026-11-02

P05B / Checkpoint 1B / M2 yazh-07. Isolated feat/p05b-event-list from verified
shared base b5cb37b8d3dbe3d8f23b29a6516162c407cf4335. User approved bounded
paths/read policy and authorized implementation/test/commit/push/merge into
shared docs/coordination-foundation. Complete after merge
c0e25d401651b468d05a60ff5f5e3525e87e6f5f and passing post-merge smoke;
current state in docs/ROADMAP.md. Older notes below are historical.
Entire agreed initial FEATURE_SCOPE including approved additions is preserved.

GET /api/v1/cases/{caseId}/events now reads actual immutable P03C/P04 Event
records from latest completed output per Evidence using P04B's exact UTC
finished_at then UUID selection. Return existing EventPage only.

- Preserve Event IDs/kinds/summaries/raw and UTC time strings/confidence/source
  arrays/participant UUIDs exactly. Never reproject/regenerate IDs or merge
  duplicate source reports. Current network/GPS score0 means unavailable; the
  reader does not infer identity, occurrence time, ownership or source truth.
- Validate selected output shape/context and same-case Observation/Evidence
  references. Event Evidence set exactly matches its cited source observations,
  including the output's Evidence. Participant IDs resolve actual selected
  Entity records with valid source citations; each participant must share an
  Event Observation. Missing/corrupt/stale/foreign/duplicate/broken references
  fail the whole read safe404, no partial page or silent older-output fallback.
  This checks wire/context/joins, not authenticity after arbitrary DB tampering.
- Optional timestamps and empty participant arrays remain supported by the
  generic contract. Existing producers preserve malformed/missing-zone/unknown-
  offset source text without fabricated UTC. Blank required CSV cells fail the
  existing parser and publish no Events. No new producer/format is implemented.
- Contract limit default20/min1/max100, offset default0/min0. Order by output
  Evidence UUID then Event UUID, canonical ascending text, before paging. Huge
  beyond-end offsets return empty items with true total. One read transaction
  keeps sources/participants/selection/total/page coherent; a subsequent request
  may see newer output. No historical-analysis/run/evidence selector is added.
  This is a processing-source list, not chronological timeline reconstruction.
- Unprocessed/header-only/empty latest outputs yield empty pages; queued/running/
  failed partial outputs stay invisible. Existing F00 auth401/case404 and shared
  invalid-input400 mapping apply; successful/Event access-error reads are no-store.
  Reads never write history/audit/originals or schedule processing. Materialized
  query records support reference joins; no persistent schema/index change.
- No DB/schema/producer/spec/dependency/frontend changes. Full Entity/Event UI,
  P14 private provenance, P14B dispatch/P14C recovery and all later adapters remain
  separate required scope. Next eligible M2 is P14, not a whole-module completion.

## How you can test P05B

PowerShell from repository root with Python 3.14.8, Node 22.23.3 and installed
requirements (synthetic inputs only; tests create/clean temporary SQLite/storage):

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p05b-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p05b-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_events -v

Expect 20 passing tests. Actual fixtures/synthetic-case/network.csv produces two
Events, gps.csv one; default total3. Each Event's Observation IDs resolve the
selected same-case P04B source locators; each participant is an actual P05 Entity
with shared source references. Stored raw/UTC time strings, summary and score0
are unchanged. Duplicate rows/Evidence stay separate reports with distinct IDs.
27-record all-page test proves total/order/no duplicate/skip; default20/max100 and
arbitrarily large beyond-end offsets are covered.

Independent real localhost smoke (starts/stops Uvicorn and temporary storage):

    python -W error::ResourceWarning -m unittest backend.tests.test_events.EventLoopbackTests -v

Expect PASS: synthetic network -> total2, plus GPS ->3, second network ->5,
malformed supported CSV -> failed run and total stays5. limit=2/offset=2 returns
two items with total5; real Observation and Entity APIs resolve every citation/
participant. No producer doubles in this HTTP smoke.

Relevant stale/foreign/unrelated participant failure control:

    python -m unittest backend.tests.test_events.EventTests.test_missing_stale_foreign_and_unrelated_participants_fail_safe_404 -v

Expect PASS: missing/old-run/another case/unrelated same-case participant UUIDs
cause safe404 for the whole Event read, with no private/partial records. These are
explicit temporary DB corruption fixtures bypassing immutable triggers; the
normal pipeline uses real source/participant UUIDs. Other negative tests cover
invalid query/auth/revoked access, broken wire/UTC/source/output metadata and
missing latest output. New processing selects new immutable IDs; historical
outputs remain unchanged; failed retry retains last completed selection.

Core tests use actual FastAPI/F00/F03/F05/P04/P04B/P05/parser/normalizer/projectors,
SQLite/private files with synthetic actors/tokens; HTTPX ASGI is in process.
The independent Uvicorn subprocess exercises real HTTP. Scheduler/publication
fault gates, controlled timestamp selection SQL, temp corruption and held-read/
real writer-thread race are labeled. A generic text Event fixture only proves
schema compatibility (omitted optional time/empty participants/nonzero stored
score), not a text extraction producer. Prior suites retain existing documented
doubles. No production-auth/full Event UI/OS power-loss/distributed worker/
maximum-size benchmark/real-evidence claim. Exact regression results are in
docs/PREIMPLEMENTATION_REVIEW.md. Optional cleanup: remove the TEMP contract bundle.
Next M2 P14 private versioned parser/model provenance; no next task started here.

# P05 source-backed candidate Entity listing — 2026-11-01

P05 / Checkpoint 1B / M2 yazh-07, feat/p05-entity-list from verified shared base
abeb516ba879636afb18aaa2a800b2143915e0f7. User approved the bounded scope/read
policy and authorized implementation/test/commit/push/merge. Complete after
merge 04af24f1c44abbc8059b0c006d9079d271ced947 and passing post-merge smoke;
current state in docs/ROADMAP.md. Older notes are
historical. Entire agreed initial scope/additions remain unchanged.

GET /api/v1/cases/{caseId}/entities now reads actual persisted P03B/P04 candidate
records from latest completed output per Evidence, matching P04B exact UTC
finished_at/UUID selection. No Entity IDs are regenerated or merged on GET.

- Preserve IDs, keys, labels, confidence and source arrays exactly; duplicate keys
  with different persisted IDs remain separate source records. D-7/D-8 stay distinct.
  Existing Event participant UUIDs remain valid. No inferred identity/ownership,
  confidence boost or independent-corroboration claim. Current parser score 0 is
  the documented unavailable sentinel; readers do not reinterpret stored scores.
- Validate every Entity's same-case selected Observation/Evidence citations and
  source locators. Evidence set must match cited source observations; any present
  Observation entity_key must agree. Generic future sources need not invent an
  entity_key field absent from the contract. Missing/corrupt/broken/stale/foreign
  references or ambiguous duplicate record UUIDs fail the whole read with safe 404.
  No partial result or silent older-run fallback. This validates wire/context/joins,
  not arbitrary database-tampering authenticity or factual truth of a source.
- Contract limit default 20/min 1/max 100, offset default 0/min 0; huge beyond-end
  offsets return empty items with true total. Order candidate_key then Entity UUID.
  One read transaction keeps selection/citations/total/page coherent; separate
  requests may select newer outputs. This is a live processing view, not a frozen
  historical analysis view. No new run/analysis/evidence selector or public field.
- Existing F00 guards return auth 401 and foreign/missing case 404; invalid/unknown/
  duplicate query parameters return safe 400. Every response is no-store. Empty or
  unprocessed cases, header-only or selected empty completed outputs return empty
  candidate pages. Pending/running/failed/partial outputs remain invisible.
- Source joins use materialized read-query records and indexed citation lookups;
  no persistent schema/index, source producer, dependency or frontend change.
  Reads never mutate SQL/history/originals/audit or schedule processing. P05B Event
  listing, later modalities/provenance/recovery/UI remain separate required tasks.

## How you can test P05

PowerShell at repository root, Python 3.14.8 and installed requirements:

    npx.cmd --yes @redocly/cli@2.57.0 bundle specs/openapi.yaml -o "$env:TEMP/evora-p05-openapi.json"
    $env:PYTHONUTF8 = '1'
    $env:EVORA_CONTRACT_BUNDLE = "$env:TEMP/evora-p05-openapi.json"
    python -W error::ResourceWarning -m unittest backend.tests.test_entities -v

Expect 17 passing tests. Real network.csv -> four Entity records; gps.csv -> one,
so default total 5, each record's Observation IDs resolve to the same-case selected
P04B source observations and correct Evidence set. Entity records exactly match
stored wire values; actual source Event participant IDs are retained. Reprocessing
selects new immutable records and retains old history; a failed retry does not
replace completed candidates. Uploading a second identical network fixture yields
nine records total, including two separate device:D-7 records with confidence 0.

Run independent real localhost smoke (starts/stops its own server/temp storage):

    python -W error::ResourceWarning -m unittest backend.tests.test_entities.EntityLoopbackTests -v

Expect PASS: actual upload/process/Observation/Entity APIs, source citations,
limit=2/offset=2 returns two items with total 9 after the repeated network source,
and malformed supported CSV fails without adding candidates. No producer double.

Relevant broken-citation failure control:

    python -m unittest backend.tests.test_entities.EntityTests.test_foreign_and_stale_observation_refs_fail_without_exposing_old_or_other_case -v

Expect PASS: replacing a citation with an older-run or another case's Observation
UUID yields safe 404 for the entire Entity read, never leaked/partial records.
Faults are explicit temp-only corruption fixtures bypassing immutable triggers,
not a claim of a production incident. The normal pipeline uses actual source IDs.

Other cases cover 28-record all-page totals/order/no duplicates, exact fractional/
offset completion ties, empty latest versus older output, bad queries/auth/revoked
access, malformed Entity/source JSON/fields/references and concurrent publication.
Core tests use actual FastAPI/F00/F03/F05/P04/P04B/parsers/normalization/projections,
SQLite/private files and in-process HTTPX ASGI, with synthetic identities. Real
HTTP smoke uses a Uvicorn subprocess. Selection-only SQL fixtures exercise precise
completion metadata; one generic account/text wire fixture checks schema-only
compatibility, not an implemented text/account producer. Scheduler/publication/
corruption gates and read/publication race are labeled. Earlier suites retain
existing doubles. No maximum-size benchmark, OS power-loss/distributed worker,
production auth, full Entity inspector or real-evidence claim. Full regression
results in docs/PREIMPLEMENTATION_REVIEW.md. Optional cleanup: remove TEMP bundle.
Next M2 P05B source-backed Event listing; no next task started here.

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

## F08 terminal processing audit

F08 / Checkpoint 1B / M1 / sharmelas-925 adds
`record_processing_audit(connection, run, status, finished_at, error=None)` in
`backend/audit.py`. Processing appends one `startProcessing` AuditEvent on
completion or failure, including startup recovery of queued/running jobs as
`PROCESSING_INTERRUPTED`. The authenticated initiating actor, case, Evidence ID
and exact terminal timestamp come from the persisted run/transition. The safe
reason holds `run:<UUID>;status:<state>;version:<processor version>` and, for
failure, an allowlisted diagnostic code. Unknown diagnostics become
`PROCESSING_FAILED` in public audit; no exception text is copied.

Completion inserts output, private versioned provenance, run state and audit in
one SQLite transaction. Failure/recovery likewise commits state and audit
together. An audit or commit failure rolls back its entire transition; if failure
accounting also fails, the run remains nonterminal for startup recovery. Existing
write serialization, terminal-state guards and key replay prevent duplicates.
The existing audit UPDATE/DELETE/REPLACE/UPSERT guards protect these events.

The public run/version reference joins to private `processing_runs` frozen
configuration and successful `processing_provenance.run_id`; failed runs have
no completed output/provenance fabricated for them. Raw cells, source filenames,
storage paths, credentials, private parameters and output contents remain outside
audit/logs. Existing authorized `listAuditEvents` provides UTC-ordered pagination
with case-membership isolation. Historical terminal runs receive no backfill.

From the repository root with the existing pinned dependencies installed:

```sh
npx @redocly/cli bundle specs/openapi.yaml --output /tmp/evora-openapi.json
EVORA_CONTRACT_BUNDLE=/tmp/evora-openapi.json python -W error::ResourceWarning -m unittest backend.tests.test_processing_audit -v
```

Expected: 13 tests pass, exercising real synthetic upload/processing/API/SQLite
producers, private provenance joins, malformed-input diagnostics, concurrent key
replay/workers, audit listing/foreign-case denial, append-only triggers and
injected publication/audit/commit/recovery failures. Scheduler holds and failure
injections are test-only. Full verification and local runtime limitations are
recorded in `docs/PREIMPLEMENTATION_REVIEW.md` under F08. F08 remains In Progress
pending review/integration; Checkpoint 1B still requires I00B and its other rows.

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
