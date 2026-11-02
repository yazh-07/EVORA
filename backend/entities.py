"""P05 persisted candidate records and verified same-case source joins; read-only."""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.auth import CaseAccessGrant, require_case_access
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.observations import _utc_order, _valid_record

router = APIRouter()


class EntityRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    id: UUID
    case_id: UUID
    kind: str
    canonical_label: str
    candidate_key: str
    evidence_ids: list[UUID] = Field(min_length=1)
    observation_ids: list[UUID] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode='before')
    @classmethod
    def wire_uuids(cls, value):
        if not isinstance(value, dict):
            raise ValueError('Invalid Entity wire object')
        ids = [value.get('id'), value.get('case_id')]
        for key in ('evidence_ids', 'observation_ids'):
            if not isinstance(value.get(key), list):
                raise ValueError('Invalid Entity references')
            ids.extend(value[key])
        if any(not isinstance(identifier, str) or str(UUID(identifier)) != identifier.lower() for identifier in ids):
            raise ValueError('Invalid Entity wire UUID')
        return value

    @model_validator(mode='after')
    def unique_references(self):
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError('Duplicate Entity references')
        return self


def _valid_entity(raw, case_id, source_evidence):
    try:
        entity = EntityRecord.model_validate_json(raw)
        return int(str(entity.case_id) == case_id and source_evidence in {str(x) for x in entity.evidence_ids})
    except (ValidationError, ValueError, TypeError):
        return 0


def _not_found():
    return AccessError(404, 'NOT_FOUND', 'Resource not found.')


_SELECTED = """
 WITH ranked AS (
   SELECT r.*,ROW_NUMBER() OVER(PARTITION BY r.evidence_id ORDER BY evora_utc_order(r.finished_at) DESC,lower(r.id) DESC) AS rank
   FROM processing_runs r WHERE r.case_id=:case_id AND r.status='completed'
 ), selected AS (
   SELECT r.id,r.case_id,r.evidence_id,o.case_id AS output_case,o.evidence_id AS output_evidence,
          o.observations_json,o.entities_json
   FROM ranked r LEFT JOIN processing_outputs o ON o.run_id=r.id WHERE r.rank=1
 ), observations AS MATERIALIZED (
   SELECT s.id AS run_id,s.case_id,s.evidence_id,j.value,j.type,
          CASE WHEN j.type='object' THEN lower(json_extract(j.value,'$.id')) END AS observation_id,
          CASE WHEN j.type='object' THEN json_extract(j.value,'$.entity_key') END AS entity_key
   FROM selected s,json_each(s.observations_json) j
 ), entities AS MATERIALIZED (
   SELECT s.id AS run_id,s.case_id,s.evidence_id,j.value,j.type,
          CASE WHEN j.type='object' THEN lower(json_extract(j.value,'$.id')) END AS entity_id,
          CASE WHEN j.type='object' THEN json_extract(j.value,'$.candidate_key') END AS candidate_key
   FROM selected s,json_each(s.entities_json) j
 ), entity_sources AS MATERIALIZED (
   SELECT e.entity_id,e.candidate_key,o.observation_id,o.case_id,o.evidence_id,o.entity_key
   FROM entities e,json_each(e.value,'$.observation_ids') ref
   LEFT JOIN observations o ON o.observation_id=lower(ref.value)
 ), entity_evidence AS MATERIALIZED (
   SELECT e.entity_id,lower(ref.value) AS evidence_id FROM entities e,json_each(e.value,'$.evidence_ids') ref
 )
"""


def _page(connection, case_id, limit, offset):
    return [json.loads(row['value']) for row in connection.execute(_SELECTED +
        "SELECT value FROM entities ORDER BY candidate_key,entity_id "
        "LIMIT :limit OFFSET :offset", dict(case_id=case_id, limit=limit, offset=offset))]


@router.get('/api/v1/cases/{caseId}/entities', operation_id='listEntities')
def list_entities(caseId: UUID, request: Request,
                  grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                  limit: Annotated[int, Query(ge=1, le=100)] = 20,
                  offset: Annotated[int, Query(ge=0)] = 0):
    if any(key not in {'limit', 'offset'} or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise invalid_input()
    case_id = str(grant.case_id)
    parameters = dict(case_id=case_id)
    with request.app.state.database.connect() as connection:
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        connection.create_function('evora_observation_valid', 4, _valid_record, deterministic=True)
        connection.create_function('evora_entity_valid', 3, _valid_entity, deterministic=True)
        connection.execute('BEGIN')
        if connection.execute("SELECT 1 FROM processing_runs WHERE case_id=? AND status='completed' "
                "AND evora_utc_order(finished_at) IS NULL LIMIT 1", (case_id,)).fetchone() is not None:
            raise _not_found()
        bad_output = connection.execute(_SELECTED + "SELECT 1 FROM selected WHERE output_case IS NULL "
            "OR output_case!=case_id OR output_evidence!=evidence_id "
            "OR CASE WHEN json_valid(observations_json) THEN json_type(observations_json)!='array' ELSE 1 END "
            "OR CASE WHEN json_valid(entities_json) THEN json_type(entities_json)!='array' ELSE 1 END LIMIT 1",
            parameters).fetchone()
        if bad_output is not None:
            raise _not_found()
        observations = connection.execute(_SELECTED + "SELECT COUNT(*) AS total,"
            "COALESCE(MIN(evora_observation_valid(value,case_id,evidence_id,run_id)),1) AS valid,"
            "COUNT(DISTINCT observation_id) AS unique_ids "
            "FROM observations", parameters).fetchone()
        entities = connection.execute(_SELECTED + "SELECT COUNT(*) AS total,"
            "COALESCE(MIN(evora_entity_valid(value,case_id,evidence_id)),1) AS valid,"
            "COUNT(DISTINCT entity_id) AS unique_ids "
            "FROM entities", parameters).fetchone()
        if any(not group['valid'] or group['total'] != group['unique_ids'] for group in (observations, entities)):
            raise _not_found()
        bad_observation_ref = connection.execute(_SELECTED + "SELECT 1 FROM entity_sources s WHERE observation_id IS NULL "
            "OR case_id!=:case_id OR NOT EXISTS(SELECT 1 FROM entity_evidence e "
            "WHERE e.entity_id=s.entity_id AND e.evidence_id=s.evidence_id) "
            "OR (entity_key IS NOT NULL AND entity_key!=candidate_key) LIMIT 1", parameters).fetchone()
        bad_evidence_ref = connection.execute(_SELECTED + "SELECT 1 FROM entity_evidence e WHERE NOT EXISTS("
            "SELECT 1 FROM entity_sources s WHERE s.entity_id=e.entity_id AND s.evidence_id=e.evidence_id) LIMIT 1",
            parameters).fetchone()
        if bad_observation_ref is not None or bad_evidence_ref is not None:
            raise _not_found()
        total = entities['total']
        items = _page(connection, case_id, limit, offset) if offset < total else []
    return JSONResponse(dict(items=items, total=total, limit=limit, offset=offset), headers={'Cache-Control': 'no-store'})
