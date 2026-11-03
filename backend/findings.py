"""A05B completed, immutable SQL graph and finding snapshot reads.

A01B verifies projection and source coherence before publishing SQL completion.
These routes read that authoritative output, never a live Neo4j partition.
"""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from backend.auth import CaseAccessGrant, require_case_access
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.observations import _utc_order

router = APIRouter()


def _completed_output(request, case_id, analysis_run_id, allowed_query):
    if any(key not in allowed_query or len(request.query_params.getlist(key)) != 1
           for key in request.query_params):
        raise invalid_input()
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN')
        if analysis_run_id is not None:
            run = connection.execute("SELECT * FROM analysis_runs WHERE id=? AND case_id=? "
                "AND status='completed'", (str(analysis_run_id), case_id)).fetchone()
            if run is None:
                raise AccessError(404, 'NOT_FOUND', 'Resource not found.')
        else:
            connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
            run = connection.execute("SELECT * FROM analysis_runs WHERE case_id=? AND status='completed' "
                "ORDER BY evora_utc_order(created_at) DESC,id DESC LIMIT 1", (case_id,)).fetchone()
            if run is None:
                return None
        output = connection.execute('SELECT * FROM analysis_outputs WHERE run_id=? AND case_id=?',
                                    (run['id'], case_id)).fetchone()
        if output is None:
            # Never substitute another run or turn missing published data into empty success.
            raise AccessError(404, 'NOT_FOUND', 'Resource not found.')
        return output


@router.get('/api/v1/cases/{caseId}/graph', operation_id='getGraph')
def get_graph(caseId: UUID, request: Request,
              grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
              analysis_run_id: UUID | None = Query(default=None)):
    output = _completed_output(request, str(grant.case_id), analysis_run_id, {'analysis_run_id'})
    graph = (dict(case_id=str(caseId), nodes=[], edges=[]) if output is None
             else json.loads(output['graph_json']))
    return JSONResponse(graph, headers={'Cache-Control': 'no-store'})


@router.get('/api/v1/cases/{caseId}/findings', operation_id='listFindings')
def list_findings(caseId: UUID, request: Request,
                  grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                  analysis_run_id: UUID | None = Query(default=None),
                  limit: int = Query(default=20, ge=1, le=100),
                  offset: int = Query(default=0, ge=0)):
    output = _completed_output(request, str(grant.case_id), analysis_run_id,
                               {'analysis_run_id', 'limit', 'offset'})
    findings = [] if output is None else json.loads(output['findings_json'])
    page = dict(items=findings[offset:offset + limit], total=len(findings), limit=limit, offset=offset)
    if output is not None:
        page['analysis_run_id'] = output['run_id']
    return JSONResponse(page, headers={'Cache-Control': 'no-store'})
