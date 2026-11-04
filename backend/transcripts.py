"""U14B immutable corrections and atomic, complete transcript materializations."""

from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit import record_audit_event
from backend.auth import CaseAccessGrant, require_case_access
from backend.entities import _valid_entity
from backend.errors import AccessError
from backend.events import _valid_event
from backend.evidence import invalid_input
from backend.observations import _not_found, _utc_order, _valid_record
from backend.parsers.text_entities import canonical, identifier_spans
from backend.processing import _json

router = APIRouter()
VERSION = 'transcript-materializer/1'
_FIELDS = ('id', 'case_id', 'evidence_id', 'source_observation_id', 'processing_run_id',
           'base_processing_run_id', 'previous_revision_id', 'corrected_text', 'reason',
           'actor_id', 'created_at', 'derived_processing_run_id', 'derived_observation_id')
_OUTPUTS = ('observations_json', 'entities_json', 'events_json', 'uncertainty_json')


def initialize_transcripts(database):
    with database.connect() as connection:
        connection.executescript("""
          CREATE TABLE IF NOT EXISTS transcript_revisions (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES cases(id),
            evidence_id TEXT NOT NULL REFERENCES evidence(id),
            source_observation_id TEXT NOT NULL,
            processing_run_id TEXT NOT NULL,
            base_processing_run_id TEXT NOT NULL,
            previous_revision_id TEXT,
            corrected_text TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            derived_processing_run_id TEXT NOT NULL,
            derived_observation_id TEXT NOT NULL,
            key_digest TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_transcript_revisions ON transcript_revisions
            (case_id, source_observation_id, created_at, id);
          CREATE UNIQUE INDEX IF NOT EXISTS transcript_revision_keys ON transcript_revisions
            (actor_id, case_id, key_digest);
          CREATE TRIGGER IF NOT EXISTS transcript_revisions_no_update BEFORE UPDATE ON transcript_revisions
            BEGIN SELECT RAISE(ABORT,'Transcript revisions are append-only.'); END;
          CREATE TRIGGER IF NOT EXISTS transcript_revisions_no_delete BEFORE DELETE ON transcript_revisions
            BEGIN SELECT RAISE(ABORT,'Transcript revisions are append-only.'); END;
          CREATE TRIGGER IF NOT EXISTS transcript_revisions_no_replace BEFORE INSERT ON transcript_revisions
            WHEN EXISTS(SELECT 1 FROM transcript_revisions WHERE id=NEW.id OR rowid=NEW.rowid
              OR (actor_id=NEW.actor_id AND case_id=NEW.case_id AND key_digest=NEW.key_digest))
            BEGIN SELECT RAISE(ABORT,'Transcript revisions are append-only.'); END;
        """)


class CreateTranscriptRevision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    processing_run_id: UUID = Field(strict=False)
    base_processing_run_id: UUID = Field(strict=False)
    expected_latest_revision_id: UUID | None = Field(strict=False)
    corrected_text: str = Field(min_length=1, max_length=20000)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator('corrected_text', 'reason')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('A nonblank value is required.')
        return value


def _conflict():
    return AccessError(409, 'CONFLICT', 'Conflicting submission.')


def _wire(row):
    return {key: row[key] for key in _FIELDS}


def _output(connection, run):
    row = connection.execute('SELECT * FROM processing_outputs WHERE run_id=?', (run['id'],)).fetchone()
    if row is None or row['case_id'] != run['case_id'] or row['evidence_id'] != run['evidence_id']:
        raise _not_found()
    try:
        values = [json.loads(row[key]) for key in _OUTPUTS]
        observations, entities, events, uncertainty = values
        if any(not isinstance(items, list) for items in values):
            raise ValueError()
        for records, validate in ((observations, lambda raw: _valid_record(raw, run['case_id'], run['evidence_id'], run['id'])),
                                  (entities, lambda raw: _valid_entity(raw, run['case_id'], run['evidence_id'])),
                                  (events, lambda raw: _valid_event(raw, run['case_id'], run['evidence_id']))):
            if any(not validate(_json(item)) for item in records) or len({x['id'] for x in records}) != len(records):
                raise ValueError()
        by_id = {item['id']: item for item in observations}
        entity_ids = {item['id'] for item in entities}
        if any(set(item['evidence_ids']) != {run['evidence_id']} or not set(item['observation_ids']) <= by_id.keys()
               for item in entities + events):
            raise ValueError()
        if any('entity_key' in by_id[oid] and by_id[oid]['entity_key'] != item['candidate_key']
               for item in entities for oid in item['observation_ids']):
            raise ValueError()
        entity_sources = {item['id']: set(item['observation_ids']) for item in entities}
        if any(not set(item['entity_ids']) <= entity_ids for item in events):
            raise ValueError()
        if any(not entity_sources[eid].intersection(item['observation_ids']) for item in events for eid in item['entity_ids']):
            raise ValueError()
        if any(not isinstance(item, dict) or item.get('observation_id') not in by_id for item in uncertainty):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise _not_found() from None
    return values


def _source(connection, case_id, observation_id, run_id=None):
    # Search historical completed outputs, never just the latest selection.
    rows = connection.execute(
        "SELECT r.* FROM processing_runs r JOIN evidence e ON e.id=r.evidence_id AND e.case_id=r.case_id "
        "JOIN processing_outputs o ON o.run_id=r.id AND o.case_id=r.case_id AND o.evidence_id=r.evidence_id "
        "WHERE r.case_id=? AND r.status='completed' AND (? IS NULL OR r.id=?) "
        "AND EXISTS (SELECT 1 FROM json_each(CASE WHEN json_valid(o.observations_json) "
        "THEN o.observations_json ELSE '[]' END) j "
        "WHERE CASE WHEN j.type='object' THEN json_extract(j.value,'$.id') END=?)", (case_id, run_id, run_id, observation_id)).fetchall()
    if len(rows) != 1:
        raise _not_found()
    run = rows[0]
    source = next(item for item in _output(connection, run)[0] if item['id'] == observation_id)
    if source['kind'] != 'transcript.segment':
        raise invalid_input()
    if 'source_observation_id' in source or 'transcript_revision_id' in source:
        raise _not_found()
    return run, source


def _preconditions(connection, case_id, evidence_id, source_id, body):
    base = connection.execute("SELECT * FROM processing_runs WHERE id=? AND case_id=? AND evidence_id=? "
        "AND status='completed'", (str(body.base_processing_run_id), case_id, evidence_id)).fetchone()
    if base is None:
        raise _not_found()
    if connection.execute("SELECT 1 FROM processing_runs WHERE case_id=? AND evidence_id=? AND status='completed' "
            "AND evora_utc_order(finished_at) IS NULL", (case_id, evidence_id)).fetchone():
        raise _not_found()
    latest = connection.execute("SELECT id FROM processing_runs WHERE case_id=? AND evidence_id=? AND status='completed' "
        "ORDER BY evora_utc_order(finished_at) DESC,lower(id) DESC LIMIT 1", (case_id, evidence_id)).fetchone()
    expected = str(body.expected_latest_revision_id) if body.expected_latest_revision_id else None
    if expected:
        referenced = connection.execute('SELECT * FROM transcript_revisions WHERE id=?', (expected,)).fetchone()
        if referenced is not None and (referenced['case_id'], referenced['evidence_id'], referenced['source_observation_id']) != (
                case_id, evidence_id, source_id):
            raise _not_found()
    previous = connection.execute('SELECT * FROM transcript_revisions WHERE case_id=? AND source_observation_id=? '
        'ORDER BY evora_utc_order(created_at) DESC,id DESC LIMIT 1', (case_id, source_id)).fetchone()
    if latest['id'] != base['id'] or expected != (previous['id'] if previous else None):
        raise _conflict()
    return base, previous


def _after(*timestamps):
    """Advance exactly beyond base/revision, including sub-microsecond fixtures."""
    latest = max(_utc_order(value) for value in timestamps if value is not None)
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    if _utc_order(now) > latest:
        return now
    calendar, fraction = latest.split('.')
    digits = max(len(fraction), 6)
    with localcontext() as context:
        context.prec = digits + 2
        advanced = Decimal('0.' + (fraction or '0')) + Decimal(1).scaleb(-digits)
    # Add a finer digit rather than rolling the calendar when the fraction is all 9s.
    if advanced >= 1:
        return calendar + '.' + fraction + '1Z'
    return calendar + format(advanced, f'.{digits}f')[1:] + 'Z'


def _materialize(output, source, body, revision_id, run_id):
    """Copy complete base output; rebuild changed literal candidates from effective text.

    This version shares the existing deterministic text identifier rules. It emits
    no inferred speech events. Dependent stale mentions/entities/events are removed;
    unaffected candidates/events are copied with all source/participant IDs remapped.
    """
    observations, entities, events, uncertainty = output
    matches = [item for item in observations if item['kind'] == 'transcript.segment'
               and item.get('source_observation_id', item['id']) == source['id']]
    if len(matches) != 1:
        raise _conflict()
    target = matches[0]
    # Candidate mentions at this media locator are dependent derived observations.
    removed = {item['id'] for item in observations if item['id'] != target['id']
               and item['source_locator'] == target['source_locator']
               and (item['kind'].startswith('text.mention.') or item['kind'].startswith('transcript.mention.'))}
    observation_ids = {item['id']: str(uuid4()) for item in observations if item['id'] not in removed}
    affected = removed | {target['id']}
    kept_entities = [dict(item, observation_ids=[oid for oid in item['observation_ids'] if oid not in affected])
                     for item in entities if set(item['observation_ids']) - affected]
    entity_ids = {item['id']: str(uuid4()) for item in kept_entities}
    result, predecessors = [], {}
    for item in observations:
        if item['id'] in removed:
            continue
        copy = dict(item, id=observation_ids[item['id']], processing_run_id=run_id)
        predecessors[copy['id']] = item['id']
        if item['kind'] == 'transcript.segment':
            copy['source_observation_id'] = item.get('source_observation_id', item['id'])
        if item['id'] == target['id']:
            copy.update(raw_value=source['raw_value'], source_locator=source['source_locator'],
                        extraction_confidence=source['extraction_confidence'], normalized_value=body.corrected_text,
                        transcript_revision_id=revision_id)
            copy.pop('entity_key', None)
        result.append(copy)
    copied_entities = [dict(item, id=entity_ids[item['id']],
        observation_ids=[observation_ids[oid] for oid in item['observation_ids']]) for item in kept_entities]
    kept_events = [item for item in events if not affected.intersection(item['observation_ids'])
                   and set(item['entity_ids']) <= entity_ids.keys()]
    copied_events = [dict(item, id=str(uuid4()),
        observation_ids=[observation_ids[oid] for oid in item['observation_ids']],
        entity_ids=[entity_ids[eid] for eid in item['entity_ids']]) for item in kept_events]
    groups = {}
    for span in identifier_spans(body.corrected_text):
        raw = body.corrected_text[span['start']:span['end']]
        label = canonical(span['kind'], raw)
        key = span['kind'] + ':' + label
        mention = dict(id=str(uuid4()), case_id=source['case_id'], evidence_id=source['evidence_id'],
            processing_run_id=run_id, kind='text.mention.' + span['kind'], source_locator=source['source_locator'],
            raw_value=raw, normalized_value=label, entity_key=key, extraction_confidence=0)
        result.append(mention)
        groups.setdefault((span['kind'], label, key), []).append(mention['id'])
    derived_id = observation_ids[target['id']]
    for (kind, label, key), refs in sorted(groups.items()):
        copied_entities.append(dict(id=str(uuid4()), case_id=source['case_id'], kind=kind, canonical_label=label,
            candidate_key=key, evidence_ids=[source['evidence_id']], observation_ids=refs, confidence=0))
    copied_uncertainty = [dict(item, observation_id=observation_ids[item['observation_id']]) for item in uncertainty
                          if item['observation_id'] in observation_ids]
    segment_ids = {item['source_locator']: item['id'] for item in result if item['kind'] == 'transcript.segment'}
    lineage = dict(observations=predecessors, entities={entity_ids[item['id']]: item['id'] for item in kept_entities},
                   events={copy['id']: item['id'] for copy, item in zip(copied_events, kept_events)},
                   mention_segments={item['id']: segment_ids[item['source_locator']] for item in result
                       if item['kind'].startswith(('text.mention.', 'transcript.mention.'))
                       and item['source_locator'] in segment_ids})
    return (result, copied_entities, copied_events, copied_uncertainty), derived_id, lineage


@router.post('/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions',
             operation_id='appendTranscriptRevision', status_code=201)
def append_transcript_revision(observationId: UUID, body: CreateTranscriptRevision, request: Request,
                               grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    keys = request.headers.getlist('idempotency-key')
    try:
        if len(keys) != 1 or len(keys[0]) != 36:
            raise ValueError()
        key = str(UUID(keys[0]))
    except ValueError:
        raise invalid_input() from None
    if request.query_params:
        raise invalid_input()
    digest = hashlib.sha256(key.encode()).hexdigest()
    case_id, source_id = str(grant.case_id), str(observationId)
    with request.app.state.database.connect() as connection:
        # All processing publishers also use BEGIN IMMEDIATE. Holding the writer
        # lock through preparation makes both preconditions stable until commit.
        connection.execute('BEGIN IMMEDIATE')
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        original, source = _source(connection, case_id, source_id, str(body.processing_run_id))
        existing = connection.execute('SELECT * FROM transcript_revisions WHERE actor_id=? AND case_id=? AND key_digest=?',
                                      (grant.actor.id, case_id, digest)).fetchone()
        if existing is not None:
            expected = str(body.expected_latest_revision_id) if body.expected_latest_revision_id else None
            if any(existing[field] != value for field, value in dict(source_observation_id=source_id,
                    processing_run_id=str(body.processing_run_id), base_processing_run_id=str(body.base_processing_run_id),
                    previous_revision_id=expected, corrected_text=body.corrected_text, reason=body.reason).items()):
                raise AccessError(409, 'IDEMPOTENCY_CONFLICT', 'Conflicting submission.')
            return JSONResponse(_wire(existing), status_code=201, headers={'Cache-Control': 'no-store'})
        base, previous = _preconditions(connection, case_id, source['evidence_id'], source_id, body)
        revision_id, run_id = str(uuid4()), str(uuid4())
        output, derived_id, predecessors = _materialize(_output(connection, base), source, body, revision_id, run_id)
        timestamp = _after(base['finished_at'], previous['created_at'] if previous else None)
        revision = dict(id=revision_id, case_id=case_id, evidence_id=source['evidence_id'], source_observation_id=source_id,
            processing_run_id=original['id'], base_processing_run_id=base['id'], previous_revision_id=previous['id'] if previous else None,
            corrected_text=body.corrected_text, reason=body.reason, actor_id=grant.actor.id, created_at=timestamp,
            derived_processing_run_id=run_id, derived_observation_id=derived_id)
        config = dict(materializer_version=VERSION, original_processing_run_id=original['id'],
            base_processing_run_id=base['id'], transcript_revision_id=revision_id,
            original_config=json.loads(original['config_json']), predecessors=predecessors,
            output_sha256=hashlib.sha256(_json(output).encode()).hexdigest())
        connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
            'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (run_id, case_id, source['evidence_id'], grant.actor.id, hashlib.sha256(('revision:' + revision_id).encode()).hexdigest(),
             hashlib.sha256(_json(revision).encode()).hexdigest(), _json(config), VERSION, timestamp, 'queued'))
        connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
        connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                           (run_id, case_id, source['evidence_id'], *[_json(items) for items in output]))
        # Validate actual persisted joins before making the output selectable.
        persisted = _output(connection, dict(id=run_id, case_id=case_id, evidence_id=source['evidence_id']))
        if _json(persisted) != _json(output):
            raise ValueError('Unverified transcript materialization.')
        if not request.app.state.case_access.allows(grant.actor.id, grant.case_id):
            raise _not_found()
        _preconditions(connection, case_id, source['evidence_id'], source_id, body)
        connection.execute('INSERT INTO transcript_revisions (' + ','.join(_FIELDS) + ',key_digest) VALUES (' +
                           ','.join('?' for _ in range(len(_FIELDS) + 1)) + ')',
                           (*[revision[field] for field in _FIELDS], digest))
        connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (timestamp, run_id))
        record_audit_event(connection, case_id=case_id, actor_id=grant.actor.id, action='appendTranscriptRevision',
                           target_id=revision_id, created_at=timestamp)
    return JSONResponse(revision, status_code=201, headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/observations/{observationId}/transcript-revisions',
            operation_id='listTranscriptRevisions')
def list_transcript_revisions(observationId: UUID, request: Request,
                              grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                              limit: Annotated[int, Query(ge=1, le=100)] = 20,
                              offset: Annotated[int, Query(ge=0)] = 0):
    if any(key not in {'limit', 'offset'} or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise invalid_input()
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN')
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        _source(connection, str(grant.case_id), str(observationId))
        params = (str(grant.case_id), str(observationId))
        total = connection.execute('SELECT COUNT(*) FROM transcript_revisions WHERE case_id=? AND source_observation_id=?',
                                   params).fetchone()[0]
        rows = connection.execute('SELECT * FROM transcript_revisions WHERE case_id=? AND source_observation_id=? '
            'ORDER BY evora_utc_order(created_at) ASC,id ASC LIMIT ? OFFSET ?', (*params, limit, offset)).fetchall() if offset < total else []
    return JSONResponse(dict(items=[_wire(row) for row in rows], total=total, limit=limit, offset=offset),
                        headers={'Cache-Control': 'no-store'})
