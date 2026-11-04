"""A06 reads of immutable completed triage with live priority overlays."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from backend.auth import CaseAccessGrant, require_case_access
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.observations import _utc_order
from backend.triage.aggregation import sort_triage_results

router = APIRouter()


def _check_query(request, allowed):
    if any(key not in allowed or len(request.query_params.getlist(key)) != 1
           for key in request.query_params):
        raise invalid_input()


def _missing():
    return AccessError(404, 'NOT_FOUND', 'Resource not found.')


def _results(connection, run):
    output = connection.execute(
        'SELECT triage_json FROM analysis_outputs WHERE run_id=? AND case_id=?',
        (run['id'], run['case_id'])).fetchone()
    if output is None:
        raise _missing()
    return json.loads(output['triage_json'])


def _overlay(connection, case_id, entries):
    # Keep reads compatible with databases created before the U09 migration.
    has_overrides = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='priority_overrides'"
    ).fetchone() is not None
    for entry in entries:
        override = None
        if has_overrides:
            row = connection.execute(
                'SELECT id,case_id,evidence_id,actor_id,priority,reason,created_at '
                'FROM priority_overrides WHERE case_id=? AND evidence_id=? '
                'ORDER BY evora_utc_order(created_at) DESC,id DESC LIMIT 1',
                (case_id, entry['evidence_id'])).fetchone()
            override = dict(row) if row is not None else None
        if override is not None:
            entry['override'] = override
            entry['effective_priority'] = override['priority']
        elif 'latest_result' in entry:
            entry['effective_priority'] = entry['latest_result']['priority']


@router.get('/api/v1/cases/{caseId}/triage', operation_id='listTriage')
def list_triage(caseId: UUID, request: Request,
                grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                analysis_run_id: UUID | None = Query(default=None),
                limit: int = Query(default=20, ge=1, le=100),
                offset: int = Query(default=0, ge=0)):
    _check_query(request, {'analysis_run_id', 'limit', 'offset'})
    case_id = str(grant.case_id)
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN')
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        if analysis_run_id is not None:
            run = connection.execute(
                "SELECT * FROM analysis_runs WHERE id=? AND case_id=? AND status='completed'",
                (str(analysis_run_id), case_id)).fetchone()
            if run is None:
                raise _missing()
        else:
            run = connection.execute(
                "SELECT * FROM analysis_runs WHERE case_id=? AND status='completed' "
                'ORDER BY evora_utc_order(created_at) DESC,id DESC LIMIT 1',
                (case_id,)).fetchone()
        if run is None:
            entries = [dict(evidence_id=row['id']) for row in connection.execute(
                'SELECT id FROM evidence WHERE case_id=? ORDER BY id', (case_id,))]
        else:
            snapshot = json.loads(run['input_snapshot_json'])
            entries = sort_triage_results(_results(connection, run), snapshot['evidence_ids'])
        page_items = entries[offset:offset + limit]
        _overlay(connection, case_id, page_items)
        page = dict(items=page_items, total=len(entries), limit=limit, offset=offset)
        if run is not None:
            page['analysis_run_id'] = run['id']
    return JSONResponse(page, headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/evidence/{evidenceId}/triage-history',
            operation_id='getTriageHistory')
def get_triage_history(caseId: UUID, evidenceId: UUID, request: Request,
                       grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    _check_query(request, set())
    case_id, evidence_id = str(grant.case_id), str(evidenceId)
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN')
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        if connection.execute('SELECT 1 FROM evidence WHERE id=? AND case_id=?',
                              (evidence_id, case_id)).fetchone() is None:
            raise _missing()
        runs = connection.execute(
            "SELECT * FROM analysis_runs WHERE case_id=? AND status='completed' "
            'ORDER BY evora_utc_order(created_at),id', (case_id,)).fetchall()
        history = [result for run in runs for result in _results(connection, run)
                   if result['evidence_id'] == evidence_id]
    return JSONResponse(history, headers={'Cache-Control': 'no-store'})
