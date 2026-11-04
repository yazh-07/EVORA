"""A05 frozen acceptance and recoverable, coherent analysis publication.

SQLite owns acceptance/history. A01B alone publishes completed after verifying
its immutable SQL output and the matching Neo4j partition. No source bytes or
private driver diagnostics enter public run errors.
"""
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Annotated, TypedDict
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.auth import CaseAccessGrant, require_case_access
from backend.audit import record_analysis_event
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.graph_db import Neo4jGraphDatabase
from backend.graph_nodes import build_graph_nodes
from backend.graph_links import RULE, CO_MENTION_RULE, derive_candidate_links
from backend.graph_projection import initialize_graph_projection, project_analysis_run
from backend.observations import _utc_order
from backend.triage.aggregation import aggregate_triage_result
from backend.triage.factors import calculate_relevance_factor, calculate_connectivity_factor
from backend.triage.policy import POLICY_VERSION

router = APIRouter()
ALGORITHM_VERSION = f'evora-analysis/1;{RULE};{CO_MENTION_RULE};{POLICY_VERSION}'


class AnalysisInputSnapshot(TypedDict):
    case_id: str
    evidence_ids: list[str]
    processing_run_ids: list[str]
    observation_ids: list[str]
    sha256: str


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _wire(row):
    result = {key: row[key] for key in ('id', 'case_id', 'status', 'trigger',
        'algorithm_version', 'created_at', 'finished_at', 'error') if row[key] is not None}
    result['input_snapshot'] = json.loads(row['input_snapshot_json'])
    return result


def initialize_analysis(db):
    initialize_graph_projection(db)
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(analysis_runs)')}
        # Existing A01B acceptance fixtures/records remain readable; no history rewrite.
        if 'trigger' not in columns:
            connection.execute("ALTER TABLE analysis_runs ADD COLUMN trigger TEXT NOT NULL DEFAULT 'initial' "
                               "CHECK(trigger IN ('initial','new_observations','manual'))")
        if 'algorithm_version' not in columns:
            connection.execute("ALTER TABLE analysis_runs ADD COLUMN algorithm_version TEXT NOT NULL DEFAULT 'legacy-a01b'")
        connection.execute('CREATE TRIGGER IF NOT EXISTS analysis_algorithm_frozen BEFORE UPDATE OF '
            "trigger,algorithm_version ON analysis_runs BEGIN SELECT RAISE(ABORT,'Frozen analysis algorithm'); END")


def _freeze(connection, case_id):
    connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
    evidence = [row['id'] for row in connection.execute(
        'SELECT id FROM evidence WHERE case_id=? ORDER BY id', (case_id,))]
    processing, observations = [], []
    for eid in evidence:
        if connection.execute("SELECT 1 FROM processing_runs WHERE case_id=? AND evidence_id=? "
                "AND status='completed' AND evora_utc_order(finished_at) IS NULL", (case_id, eid)).fetchone():
            raise ValueError('Invalid completed processing timestamp')
        run = connection.execute("SELECT id FROM processing_runs WHERE case_id=? AND evidence_id=? "
            "AND status='completed' ORDER BY evora_utc_order(finished_at) DESC,id DESC LIMIT 1",
            (case_id, eid)).fetchone()
        if run is None:
            continue
        output = connection.execute('SELECT observations_json FROM processing_outputs '
            'WHERE run_id=? AND case_id=? AND evidence_id=?', (run['id'], case_id, eid)).fetchone()
        if output is None:
            raise ValueError('Missing completed processing output')
        processing.append(run['id'])
        observations.extend(item['id'] for item in json.loads(output['observations_json']))
    manifest = dict(case_id=case_id, evidence_ids=sorted(set(evidence)),
        processing_run_ids=sorted(set(processing)), observation_ids=sorted(set(observations)))
    return manifest | dict(sha256=hashlib.sha256(_json(manifest).encode('utf-8')).hexdigest())


def freeze_analysis_input_snapshot(db, case_id) -> AnalysisInputSnapshot:
    """Use the caller's acceptance transaction, or a standalone consistent read."""
    case_id = str(UUID(str(case_id)))
    if isinstance(db, sqlite3.Connection):
        return _freeze(db, case_id)
    with db.connect() as connection:
        connection.execute('BEGIN')
        return _freeze(connection, case_id)


def _outputs(connection, run):
    snapshot = json.loads(run['input_snapshot_json'])
    case, run_id = run['case_id'], run['id']
    evidence = [dict(connection.execute('SELECT * FROM evidence WHERE case_id=? AND id=?',
        (case, eid)).fetchone()) for eid in snapshot['evidence_ids']]
    observations, entities, events = [], [], []
    for pid in snapshot['processing_run_ids']:
        row = connection.execute('SELECT o.* FROM processing_outputs o JOIN processing_runs r '
            "ON r.id=o.run_id AND r.case_id=o.case_id AND r.evidence_id=o.evidence_id "
            "WHERE r.id=? AND r.case_id=? AND r.status='completed'", (pid, case)).fetchone()
        if row is None:
            raise ValueError('Frozen source unavailable')
        observations.extend(json.loads(row['observations_json']))
        entities.extend(json.loads(row['entities_json']))
        events.extend(json.loads(row['events_json']))
    nodes = build_graph_nodes(case, evidence, entities, events)
    edges, findings = derive_candidate_links(case, run_id, entities, observations)
    triage = []
    for eid in snapshot['evidence_ids']:
        count = sum(item['evidence_id'] == eid for item in observations)
        relevance = calculate_relevance_factor(case_id=case, evidence_id=eid,
            target_entities=[item for item in entities if eid in item['evidence_ids']],
            known_case_entities=entities, evidence_records=evidence, observations=observations)
        connectivity = calculate_connectivity_factor(case_id=case, evidence_id=eid,
            target_nodes=nodes, edges=edges, observation_count=count)
        result = aggregate_triage_result(case_id=case, analysis_run_id=run_id, evidence_id=eid,
            observation_count=count, factors=[factor for factor in (relevance, connectivity) if factor is not None],
            case_evidence_ids=snapshot['evidence_ids'], created_at=run['created_at'])
        if result is not None:
            triage.append(result)
    return (dict(case_id=case, analysis_run_id=run_id, nodes=[node.to_wire() for node in nodes],
                 edges=[edge.to_wire() for edge in edges]), [finding.to_wire() for finding in findings], triage)


def process_analysis_run(app, run_id):
    db = app.state.database
    try:
        with db.connect() as connection:
            connection.execute('BEGIN')
            run = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (run_id,)).fetchone()
            if run is None or run['status'] in ('completed', 'failed'):
                return
            if not app.state.case_access.allows(run['actor_id'], UUID(run['case_id'])):
                raise ValueError('Source unavailable')
            if run['algorithm_version'] != ALGORITHM_VERSION:
                raise ValueError('Algorithm unavailable')
            stored = connection.execute('SELECT * FROM analysis_outputs WHERE run_id=?', (run_id,)).fetchone()
            if stored is not None:
                graph, findings, triage = (json.loads(stored[key]) for key in ('graph_json', 'findings_json', 'triage_json'))
            else:
                graph, findings, triage = _outputs(connection, run)
        # Membership is checked again immediately before authoritative publication.
        if not app.state.case_access.allows(run['actor_id'], UUID(run['case_id'])):
            raise ValueError('Source unavailable')
        if app.state.graph_database is None:
            app.state.graph_database = Neo4jGraphDatabase()
        project_analysis_run(db, app.state.graph_database, case_id=run['case_id'],
            analysis_run_id=run_id, graph=graph, findings=findings, triage=triage)
    except Exception:
        # A01B may already have recorded a sanitized terminal projection failure.
        try:
            with db.connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                run = connection.execute('SELECT * FROM analysis_runs WHERE id=?', (run_id,)).fetchone()
                finished_at = _now()
                changed = connection.execute("UPDATE analysis_runs SET status='failed',finished_at=?,error='ANALYSIS_FAILED' "
                    "WHERE id=? AND status IN ('queued','running')", (finished_at, run_id)).rowcount
                if changed:
                    record_analysis_event(connection, run=run, status='failed',
                        finished_at=finished_at, error='ANALYSIS_FAILED')
        except Exception:
            # Outage leaves pending history hidden for startup recovery.
            return


async def run_analysis_job(app, run_id):
    async with app.state.analysis_lock:
        await run_in_threadpool(process_analysis_run, app, run_id)


async def recover_analysis_runs(app):
    """Resume frozen queued inputs or persisted running outputs after restart."""
    with app.state.database.connect() as connection:
        pending = [row['id'] for row in connection.execute("SELECT id FROM analysis_runs "
            "WHERE status IN ('queued','running') ORDER BY created_at,id")]
    for run_id in pending:
        await run_analysis_job(app, run_id)


@router.post('/api/v1/cases/{caseId}/analysis-runs', operation_id='startAnalysis')
async def start_analysis(caseId: UUID, request: Request, background: BackgroundTasks,
                         grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    keys = request.headers.getlist('idempotency-key')
    if len(keys) != 1 or not 1 <= len(keys[0]) <= 128 or request.query_params:
        raise invalid_input()
    try:
        key = str(UUID(keys[0]))
    except ValueError:
        raise invalid_input() from None
    async for chunk in request.stream():
        if chunk:
            raise invalid_input()
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        existing = connection.execute('SELECT * FROM analysis_runs WHERE actor_id=? AND case_id=? AND key_digest=?',
            (grant.actor.id, str(caseId), digest)).fetchone()
        if existing is not None:
            return JSONResponse(_wire(existing), status_code=202, headers={'Cache-Control': 'no-store'})
        snapshot = freeze_analysis_input_snapshot(connection, str(caseId))
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        previous = connection.execute("SELECT input_snapshot_json FROM analysis_runs WHERE case_id=? "
            "AND status='completed' ORDER BY evora_utc_order(created_at) DESC,id DESC LIMIT 1", (str(caseId),)).fetchone()
        trigger = ('initial' if previous is None else 'manual' if
            json.loads(previous['input_snapshot_json'])['sha256'] == snapshot['sha256'] else 'new_observations')
        run_id = str(uuid4())
        connection.execute('INSERT INTO analysis_runs (id,case_id,actor_id,key_digest,status,input_snapshot_json,'
            'created_at,trigger,algorithm_version) VALUES (?,?,?,?,?,?,?,?,?)',
            (run_id, str(caseId), grant.actor.id, digest, 'queued', _json(snapshot), _now(), trigger, ALGORITHM_VERSION))
        result = _wire(connection.execute('SELECT * FROM analysis_runs WHERE id=?', (run_id,)).fetchone())
    background.add_task(run_analysis_job, request.app, run_id)
    return JSONResponse(result, status_code=202, headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/analysis-runs/{runId}', operation_id='getAnalysisRun')
def get_analysis_run(caseId: UUID, runId: UUID, request: Request,
                     grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    if request.query_params:
        raise invalid_input()
    with request.app.state.database.connect() as connection:
        row = connection.execute('SELECT * FROM analysis_runs WHERE id=? AND case_id=?',
                                 (str(runId), str(caseId))).fetchone()
        if row is None:
            raise AccessError(404, 'NOT_FOUND', 'Resource not found.')
        return JSONResponse(_wire(row), headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/analysis-runs', operation_id='listAnalysisRuns')
def list_analysis_runs(caseId: UUID, request: Request,
                       grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    if request.query_params:
        raise invalid_input()
    with request.app.state.database.connect() as connection:
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        rows = connection.execute(
            'SELECT * FROM analysis_runs WHERE case_id=? '
            'ORDER BY evora_utc_order(created_at) ASC, id ASC',
            (str(caseId),)
        ).fetchall()
        return JSONResponse([_wire(row) for row in rows], headers={'Cache-Control': 'no-store'})
