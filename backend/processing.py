"""P04 single-process background lifecycle; immutable SQL publication, no list outputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.auth import Actor, CaseAccessGrant, require_case_access
from backend.errors import AccessError
from backend.evidence import download_evidence, invalid_input
from backend.parsers.network_csv import NetworkCSVError
from backend.parsers.gps_csv import GPSCSVError
from backend.processing_dispatch import adapter_for
from backend.parsers.normalization import NORMALIZER_VERSION, normalize_observations
from backend.parsers.candidate_entities import PROJECTOR_VERSION as ENTITY_VERSION, project_candidate_entities
from backend.parsers.source_events import PROJECTOR_VERSION as EVENT_VERSION, project_source_events
from backend.processing_provenance import (
    PROCESSOR_VERSION, RECORD_VERSION, initialize_provenance, record_processing_provenance,
)

_WIRE = ('id', 'case_id', 'evidence_id', 'status', 'processor_version', 'created_at', 'finished_at', 'error')
router = APIRouter()


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _wire(row):
    return {key: row[key] for key in _WIRE if row[key] is not None}


def _not_found():
    return AccessError(404, 'NOT_FOUND', 'Resource not found.')


def _versions(adapter):
    return dict(parser_version=adapter.parser_version, normalizer_version=NORMALIZER_VERSION,
                entity_version=ENTITY_VERSION, event_version=EVENT_VERSION, processor_version=PROCESSOR_VERSION,
                max_source_bytes=adapter.max_source_bytes, max_data_rows=adapter.max_data_rows, provenance_version=RECORD_VERSION)


def initialize_processing(database):
    with database.connect() as connection:
        connection.executescript("""
          CREATE TABLE IF NOT EXISTS processing_runs (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
            evidence_id TEXT NOT NULL REFERENCES evidence(id), actor_id TEXT NOT NULL,
            key_digest TEXT NOT NULL, fingerprint TEXT NOT NULL, config_json TEXT NOT NULL,
            processor_version TEXT NOT NULL, created_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
            finished_at TEXT, error TEXT,
            UNIQUE(actor_id,case_id,key_digest),
            CHECK((status IN ('queued','running') AND finished_at IS NULL AND error IS NULL)
              OR (status='completed' AND finished_at IS NOT NULL AND error IS NULL)
              OR (status='failed' AND finished_at IS NOT NULL AND error IS NOT NULL AND length(error)>0)));
          CREATE TABLE IF NOT EXISTS processing_outputs (
            run_id TEXT PRIMARY KEY REFERENCES processing_runs(id), case_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL, observations_json TEXT NOT NULL,
            entities_json TEXT NOT NULL, events_json TEXT NOT NULL, uncertainty_json TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS processing_run_frozen BEFORE UPDATE OF
            id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,processor_version,created_at
            ON processing_runs BEGIN SELECT RAISE(ABORT,'Frozen processing configuration'); END;
          CREATE TRIGGER IF NOT EXISTS processing_run_terminal BEFORE UPDATE ON processing_runs
            WHEN OLD.status IN ('completed','failed')
            BEGIN SELECT RAISE(ABORT,'Immutable terminal processing run'); END;
          CREATE TRIGGER IF NOT EXISTS processing_run_transition BEFORE UPDATE OF status ON processing_runs
            WHEN NOT ((OLD.status='queued' AND NEW.status IN ('running','failed'))
              OR (OLD.status='running' AND NEW.status IN ('completed','failed')))
            BEGIN SELECT RAISE(ABORT,'Invalid processing transition'); END;
          CREATE TRIGGER IF NOT EXISTS processing_run_no_delete BEFORE DELETE ON processing_runs
            BEGIN SELECT RAISE(ABORT,'Immutable processing history'); END;
          CREATE TRIGGER IF NOT EXISTS processing_output_insert BEFORE INSERT ON processing_outputs
            WHEN NOT EXISTS(SELECT 1 FROM processing_runs WHERE id=NEW.run_id AND status='running'
              AND case_id=NEW.case_id AND evidence_id=NEW.evidence_id)
            BEGIN SELECT RAISE(ABORT,'Invalid processing output context'); END;
          CREATE TRIGGER IF NOT EXISTS processing_output_update BEFORE UPDATE ON processing_outputs
            BEGIN SELECT RAISE(ABORT,'Immutable processing output'); END;
          CREATE TRIGGER IF NOT EXISTS processing_output_delete BEFORE DELETE ON processing_outputs
            BEGIN SELECT RAISE(ABORT,'Immutable processing output'); END;
          CREATE TRIGGER IF NOT EXISTS processing_completion_output BEFORE UPDATE OF status ON processing_runs
            WHEN NEW.status='completed' AND NOT EXISTS(SELECT 1 FROM processing_outputs WHERE run_id=NEW.id)
            BEGIN SELECT RAISE(ABORT,'Missing processing output'); END;
        """)
        initialize_provenance(connection)
        connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='PROCESSING_INTERRUPTED' "
                           "WHERE status IN ('queued','running')", (_now(),))


def publish_outputs(connection, run, output):
    """One transaction owned by caller; insert and terminal pointer commit together."""
    connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)',
                       (run['id'], run['case_id'], run['evidence_id'], *output))
    finished_at = _now()
    record_processing_provenance(connection, run, output, finished_at)
    connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=? AND status='running'",
                       (finished_at, run['id']))


def process_run(app, run_id):
    database = app.state.database
    try:
        with database.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            run = connection.execute('SELECT * FROM processing_runs WHERE id=?', (run_id,)).fetchone()
            if run is None or run['status'] != 'queued':
                return
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
        case_id, evidence_id = UUID(run['case_id']), UUID(run['evidence_id'])
        if not app.state.case_access.allows(run['actor_id'], case_id):
            raise AccessError(404, 'SOURCE_UNAVAILABLE', 'Source unavailable.')
        config = json.loads(run['config_json'])
        adapter = adapter_for(config['kind'])
        if adapter is None or any(config.get(key) != value for key, value in _versions(adapter).items()):
            # Never execute changed configuration under an older frozen version.
            raise ValueError('processing configuration changed')
        grant = CaseAccessGrant(Actor(run['actor_id']), case_id)
        original = download_evidence(case_id, evidence_id, Request({'type': 'http', 'app': app}), grant)
        with Path(original.path).open('rb') as source:
            data = source.read(adapter.max_source_bytes + 1)
        if len(data) != config['size_bytes'] or hashlib.sha256(data).hexdigest() != config['sha256']:
            raise ValueError('source integrity')
        observations = adapter.parse(data, case_id=case_id, evidence_id=evidence_id, processing_run_id=UUID(run_id))
        candidates = project_candidate_entities(normalize_observations(observations), case_id=case_id)
        events = project_source_events(candidates, case_id=case_id)
        output = (_json([x.observation.to_wire() for x in candidates.observations]),
                  _json([x.to_wire() for x in candidates.entities]),
                  _json([x.event.to_wire() for x in events]),
                  _json([{'observation_id': str(x.observation.id), 'time': {
                      'raw_value': x.time.raw_value, 'utc_value': x.time.utc_value,
                      'status': x.time.status, 'source_offset': x.time.source_offset},
                      'coordinate_status': x.coordinate_status} for x in candidates.observations]))
        with database.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT status FROM processing_runs WHERE id=?', (run_id,)).fetchone()
            if current['status'] != 'running':
                return
            # Membership can change during processing; never publish after revocation.
            if not app.state.case_access.allows(run['actor_id'], case_id):
                raise AccessError(404, 'SOURCE_UNAVAILABLE', 'Source unavailable.')
            publish_outputs(connection, run, output)
    except Exception as error:
        code = ('CSV_' + error.code if isinstance(error, (NetworkCSVError, GPSCSVError)) else
                'SOURCE_UNAVAILABLE' if isinstance(error, (AccessError, OSError)) else 'PROCESSING_FAILED')
        try:
            with database.connect() as connection:
                connection.execute("UPDATE processing_runs SET status='failed',finished_at=?,error=? "
                                   "WHERE id=? AND status IN ('queued','running')", (_now(), code, run_id))
        except Exception:
            # Database outage: leave nonterminal state for explicit startup recovery.
            return


async def run_job(app, run_id):
    # Pending jobs wait asynchronously; one parser uses memory/thread capacity at a time.
    async with app.state.processing_lock:
        await run_in_threadpool(process_run, app, run_id)


@router.post('/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', operation_id='startProcessing')
async def start_processing(caseId: UUID, evidenceId: UUID, request: Request, background: BackgroundTasks,
                           grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    keys = request.headers.getlist('idempotency-key')
    if len(keys) != 1 or not 1 <= len(keys[0]) <= 128 or request.query_params:
        raise invalid_input()
    async for chunk in request.stream():
        if chunk:
            raise invalid_input()
    digest = hashlib.sha256(keys[0].encode('utf-8')).hexdigest()
    fingerprint = hashlib.sha256(_json({'method': 'POST', 'path': request.url.path, 'query': [], 'body': None}).encode('utf-8')).hexdigest()
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        existing = connection.execute('SELECT * FROM processing_runs WHERE actor_id=? AND case_id=? AND key_digest=?',
                                      (grant.actor.id, str(caseId), digest)).fetchone()
        if existing is not None:
            if existing['fingerprint'] != fingerprint:
                raise AccessError(409, 'IDEMPOTENCY_CONFLICT', 'Conflicting submission.')
            return JSONResponse(_wire(existing), status_code=202, headers={'Cache-Control': 'no-store'})
        evidence = connection.execute('SELECT * FROM evidence WHERE id=? AND case_id=?',
                                      (str(evidenceId), str(caseId))).fetchone()
        if evidence is None:
            raise _not_found()
        adapter = adapter_for(evidence['kind'])
        if adapter is None:
            raise AccessError(415, 'UNSUPPORTED_MEDIA', 'File cannot be processed as declared.')
        config = {key: evidence[key] for key in ('kind', 'sha256', 'size_bytes')}
        config.update(_versions(adapter))
        run_id = str(uuid4())
        connection.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,'
                           'processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (run_id, str(caseId), str(evidenceId), grant.actor.id, digest, fingerprint, _json(config),
                            PROCESSOR_VERSION, _now(), 'queued'))
        result = _wire(connection.execute('SELECT * FROM processing_runs WHERE id=?', (run_id,)).fetchone())
    background.add_task(run_job, request.app, run_id)
    return JSONResponse(result, status_code=202, headers={'Cache-Control': 'no-store'})


def _require_evidence(connection, case_id, evidence_id):
    if connection.execute('SELECT 1 FROM evidence WHERE id=? AND case_id=?', (str(evidence_id), str(case_id))).fetchone() is None:
        raise _not_found()


@router.get('/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs', operation_id='listProcessingRuns')
def list_processing(caseId: UUID, evidenceId: UUID, request: Request,
                    grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    with request.app.state.database.connect() as connection:
        _require_evidence(connection, grant.case_id, evidenceId)
        result = [_wire(row) for row in connection.execute('SELECT * FROM processing_runs WHERE case_id=? AND evidence_id=? '
                  'ORDER BY created_at,id', (str(grant.case_id), str(evidenceId)))]
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/evidence/{evidenceId}/processing-runs/{runId}', operation_id='getProcessingRun')
def get_processing(caseId: UUID, evidenceId: UUID, runId: UUID, request: Request,
                   grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    with request.app.state.database.connect() as connection:
        row = connection.execute('SELECT * FROM processing_runs WHERE id=? AND case_id=? AND evidence_id=?',
                                 (str(runId), str(grant.case_id), str(evidenceId))).fetchone()
    if row is None:
        raise _not_found()
    return JSONResponse(_wire(row), headers={'Cache-Control': 'no-store'})
