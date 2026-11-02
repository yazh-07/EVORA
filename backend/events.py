"""P05B immutable source Event reads; no inference or producer writes."""
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.auth import CaseAccessGrant, require_case_access
from backend.entities import _valid_entity
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.observations import _utc_order, _valid_record

router = APIRouter()


class EventRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    id: UUID
    case_id: UUID
    kind: str
    summary: str
    evidence_ids: list[UUID] = Field(min_length=1)
    observation_ids: list[UUID] = Field(min_length=1)
    entity_ids: list[UUID]
    observed_at_raw: str | None = None
    observed_at_utc: AwareDatetime | None = Field(default=None, strict=False)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode='before')
    @classmethod
    def wire_values(cls, value):
        if not isinstance(value, dict):
            raise ValueError('Invalid Event wire object')
        ids = [value.get('id'), value.get('case_id')]
        for key in ('evidence_ids', 'observation_ids', 'entity_ids'):
            if not isinstance(value.get(key), list):
                raise ValueError('Invalid Event references')
            ids.extend(value[key])
        if any(not isinstance(x, str) or str(UUID(x)) != x.lower() for x in ids):
            raise ValueError('Invalid Event wire UUID')
        if any(value[key] is None for key in value.keys() & {'observed_at_raw', 'observed_at_utc'}):
            raise ValueError('Invalid optional Event time')
        if 'observed_at_utc' in value and (not isinstance(value['observed_at_utc'], str) or not re.fullmatch(
                r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})',
                value['observed_at_utc'])):
            raise ValueError('Invalid Event wire timestamp')
        return value

    @model_validator(mode='after')
    def unique_references(self):
        if any(len(set(refs)) != len(refs) for refs in (self.evidence_ids, self.observation_ids, self.entity_ids)):
            raise ValueError('Duplicate Event references')
        return self


def _valid_event(raw, case_id, evidence_id):
    try:
        event = EventRecord.model_validate_json(raw)
        return int(str(event.case_id) == case_id and evidence_id in {str(x) for x in event.evidence_ids})
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
          o.observations_json,o.entities_json,o.events_json
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
 ), events AS MATERIALIZED (
   SELECT s.case_id,s.evidence_id,j.value,j.type,
          CASE WHEN j.type='object' THEN lower(json_extract(j.value,'$.id')) END AS event_id
   FROM selected s,json_each(s.events_json) j
 ), event_sources AS MATERIALIZED (
   SELECT e.event_id,o.observation_id,o.evidence_id
   FROM events e,json_each(e.value,'$.observation_ids') ref
   LEFT JOIN observations o ON o.observation_id=lower(ref.value)
 ), event_evidence AS MATERIALIZED (
   SELECT e.event_id,lower(ref.value) AS evidence_id FROM events e,json_each(e.value,'$.evidence_ids') ref
 ), event_participants AS MATERIALIZED (
   SELECT e.event_id,p.entity_id
   FROM events e,json_each(e.value,'$.entity_ids') ref
   LEFT JOIN entities p ON p.entity_id=lower(ref.value)
 )
"""


def _page(connection, case_id, limit, offset):
    return [json.loads(row['value']) for row in connection.execute(_SELECTED +
        'SELECT value FROM events ORDER BY lower(evidence_id),event_id LIMIT :limit OFFSET :offset',
        dict(case_id=case_id, limit=limit, offset=offset))]


@router.get('/api/v1/cases/{caseId}/events', operation_id='listEvents')
def list_events(caseId: UUID, request: Request,
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
        connection.create_function('evora_event_valid', 3, _valid_event, deterministic=True)
        connection.execute('BEGIN')
        if connection.execute("SELECT 1 FROM processing_runs WHERE case_id=? AND status='completed' "
                'AND evora_utc_order(finished_at) IS NULL LIMIT 1', (case_id,)).fetchone() is not None:
            raise _not_found()
        bad_output = connection.execute(_SELECTED + 'SELECT 1 FROM selected WHERE output_case IS NULL '
            'OR output_case!=case_id OR output_evidence!=evidence_id '
            "OR CASE WHEN json_valid(observations_json) THEN json_type(observations_json)!='array' ELSE 1 END "
            "OR CASE WHEN json_valid(entities_json) THEN json_type(entities_json)!='array' ELSE 1 END "
            "OR CASE WHEN json_valid(events_json) THEN json_type(events_json)!='array' ELSE 1 END LIMIT 1",
            parameters).fetchone()
        if bad_output is not None:
            raise _not_found()
        for table, identifier, validator, context in (
                ('observations', 'observation_id', 'evora_observation_valid', 'case_id,evidence_id,run_id'),
                ('entities', 'entity_id', 'evora_entity_valid', 'case_id,evidence_id'),
                ('events', 'event_id', 'evora_event_valid', 'case_id,evidence_id')):
            # All SQL identifiers here are fixed internal constants, never request input.
            counts = connection.execute(_SELECTED + f'SELECT COUNT(*) AS total,'
                f'COALESCE(MIN({validator}(value,{context})),1) AS valid,COUNT(DISTINCT {identifier}) AS unique_ids '
                f'FROM {table}', parameters).fetchone()
            if not counts['valid'] or counts['total'] != counts['unique_ids']:
                raise _not_found()
        total = counts['total']
        failures = (
            'SELECT 1 FROM entity_sources s WHERE observation_id IS NULL OR case_id!=:case_id '
            'OR NOT EXISTS(SELECT 1 FROM entity_evidence e WHERE e.entity_id=s.entity_id AND e.evidence_id=s.evidence_id) '
            'OR (entity_key IS NOT NULL AND entity_key!=candidate_key) LIMIT 1',
            'SELECT 1 FROM entity_evidence e WHERE NOT EXISTS(SELECT 1 FROM entity_sources s '
            'WHERE s.entity_id=e.entity_id AND s.evidence_id=e.evidence_id) LIMIT 1',
            'SELECT 1 FROM event_sources s WHERE observation_id IS NULL '
            'OR NOT EXISTS(SELECT 1 FROM event_evidence e WHERE e.event_id=s.event_id AND e.evidence_id=s.evidence_id) LIMIT 1',
            'SELECT 1 FROM event_evidence e WHERE NOT EXISTS(SELECT 1 FROM event_sources s '
            'WHERE s.event_id=e.event_id AND s.evidence_id=e.evidence_id) LIMIT 1',
            'SELECT 1 FROM event_participants p WHERE entity_id IS NULL OR NOT EXISTS('
            'SELECT 1 FROM entity_sources es JOIN event_sources s ON s.observation_id=es.observation_id '
            'WHERE es.entity_id=p.entity_id AND s.event_id=p.event_id) LIMIT 1',
        )
        if any(connection.execute(_SELECTED + query, parameters).fetchone() is not None for query in failures):
            raise _not_found()
        # The contract permits arbitrarily large beyond-end offsets; do not bind them to SQLite.
        items = _page(connection, case_id, limit, offset) if offset < total else []
    return JSONResponse(dict(items=items, total=total, limit=limit, offset=offset), headers={'Cache-Control': 'no-store'})
