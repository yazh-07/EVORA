"""P04B read-only completed output selection; OpenAPI 0.3.0 wire values preserved."""
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.auth import CaseAccessGrant, require_case_access
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.parsers.normalization import normalize_timestamp

router = APIRouter()


class ObservationRecord(BaseModel):
    """Validate the sole wire contract; return original JSON rather than reserialize."""
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    id: UUID
    case_id: UUID
    evidence_id: UUID
    processing_run_id: UUID
    kind: str
    source_locator: str = Field(min_length=1)
    raw_value: str
    normalized_value: str
    extraction_confidence: float = Field(ge=0, le=1)
    observed_at_raw: str | None = None
    observed_at_utc: AwareDatetime | None = Field(default=None, strict=False)
    entity_key: str | None = None
    detector_weight: float | None = None
    detector: str | None = None
    source_observation_id: UUID | None = None
    transcript_revision_id: UUID | None = None

    @model_validator(mode='before')
    @classmethod
    def wire_types(cls, value):
        if not isinstance(value, dict):
            raise ValueError('Invalid stored observation')
        if any(value.get(key) is None for key in value.keys() & {
                'observed_at_raw', 'observed_at_utc', 'entity_key', 'source_observation_id', 'transcript_revision_id'}):
            raise ValueError('Invalid optional wire value')
        for key in ('id', 'case_id', 'evidence_id', 'processing_run_id', 'source_observation_id', 'transcript_revision_id'):
            if key in value and (not isinstance(value[key], str) or str(UUID(value[key])) != value[key].lower()):
                raise ValueError('Invalid wire UUID')
        if 'observed_at_utc' in value and (not isinstance(value['observed_at_utc'], str) or not re.fullmatch(
                r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})',
                value['observed_at_utc'])):
            raise ValueError('Invalid wire timestamp')
        return value

    @model_validator(mode='after')
    def transcript_conditions(self):
        if self.kind == 'transcript.segment' and (not self.raw_value or not self.normalized_value or not re.fullmatch(
                r'media:start_ms=(0|[1-9][0-9]*);end_ms=(0|[1-9][0-9]*)', self.source_locator)):
            raise ValueError('Invalid transcript wire values')
        if self.kind == 'transcript.status' and self.normalized_value not in ('silence', 'no_audio'):
            raise ValueError('Invalid transcript status')
        if (self.source_observation_id is not None and self.kind != 'transcript.segment') or (
                self.transcript_revision_id is not None and self.source_observation_id is None):
            raise ValueError('Invalid transcript wire lineage')
        return self


def _not_found():
    return AccessError(404, 'NOT_FOUND', 'Resource not found.')


def _utc_order(value):
    if not isinstance(value, str):
        return None
    normalized = normalize_timestamp(value).utc_value
    if normalized is None:
        return None
    # Fixed calendar prefix plus exact fractional digits; .1 and .100 compare equal.
    base, _, fraction = normalized[:-1].partition('.')
    return base + '.' + fraction.rstrip('0')


def _valid_record(raw, case_id, evidence_id, run_id):
    try:
        record = ObservationRecord.model_validate_json(raw)
        return int((str(record.case_id), str(record.evidence_id), str(record.processing_run_id)) ==
                   (case_id, evidence_id, run_id))
    except (ValidationError, ValueError, TypeError):
        return 0


_SELECTED = """
 WITH ranked AS (
   SELECT r.*,ROW_NUMBER() OVER(PARTITION BY r.evidence_id ORDER BY evora_utc_order(r.finished_at) DESC,lower(r.id) DESC) AS rank
   FROM processing_runs r WHERE r.case_id=:case_id AND r.status='completed'
     AND (:evidence_id IS NULL OR r.evidence_id=:evidence_id)
     AND (:run_id IS NULL OR r.id=:run_id)
 ), selected AS (
   SELECT r.id,r.case_id,r.evidence_id,o.case_id AS output_case,o.evidence_id AS output_evidence,o.observations_json
   FROM ranked r LEFT JOIN processing_outputs o ON o.run_id=r.id WHERE r.rank=1
 ), records AS (
   SELECT s.id AS run_id,s.case_id,s.evidence_id,j.value,j.type
   FROM selected s,json_each(s.observations_json) j
 )
"""


def _page(connection, parameters, limit, offset):
    return [json.loads(row['value']) for row in connection.execute(_SELECTED +
        "SELECT value FROM records ORDER BY lower(evidence_id),lower(json_extract(value,'$.id')) LIMIT :limit OFFSET :offset",
        dict(parameters, limit=limit, offset=offset))]


def _validated_count(connection, parameters):
    """Validate selected outputs before any caller discloses their observations.

    The caller owns the transaction and registers the UTC/record SQL functions.
    Selection and validation are shared by listing and grounded retrieval.
    """
    invalid_time = connection.execute("SELECT 1 FROM processing_runs WHERE case_id=:case_id AND status='completed' "
        "AND (:evidence_id IS NULL OR evidence_id=:evidence_id) AND (:run_id IS NULL OR id=:run_id) "
        "AND evora_utc_order(finished_at) IS NULL LIMIT 1", parameters).fetchone()
    invalid_output = connection.execute(_SELECTED + "SELECT 1 FROM selected WHERE output_case IS NULL "
        "OR output_case!=case_id OR output_evidence!=evidence_id OR CASE WHEN json_valid(observations_json) "
        "THEN json_type(observations_json)!='array' ELSE 1 END LIMIT 1", parameters).fetchone()
    if invalid_time is not None or invalid_output is not None:
        raise _not_found()
    counts = connection.execute(_SELECTED + "SELECT COUNT(*) AS total,COALESCE(MIN(evora_observation_valid(value,"
        "case_id,evidence_id,run_id)),1) AS valid,COUNT(DISTINCT lower(CASE WHEN type='object' "
        "THEN json_extract(value,'$.id') END)) AS unique_ids FROM records", parameters).fetchone()
    if not counts['valid'] or counts['total'] != counts['unique_ids']:
        raise _not_found()
    return counts['total']


@router.get('/api/v1/cases/{caseId}/observations', operation_id='listObservations')
def list_observations(caseId: UUID, request: Request,
                      grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
                      evidence_id: UUID | None = None, processing_run_id: UUID | None = None,
                      limit: Annotated[int, Query(ge=1, le=100)] = 20,
                      offset: Annotated[int, Query(ge=0)] = 0):
    if any(key not in {'evidence_id', 'processing_run_id', 'limit', 'offset'} or
           len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise invalid_input()
    parameters = dict(case_id=str(grant.case_id), evidence_id=str(evidence_id) if evidence_id else None,
                      run_id=str(processing_run_id) if processing_run_id else None)
    with request.app.state.database.connect() as connection:
        connection.create_function('evora_utc_order', 1, _utc_order, deterministic=True)
        connection.create_function('evora_observation_valid', 4, _valid_record, deterministic=True)
        connection.execute('BEGIN')
        if evidence_id is not None and connection.execute('SELECT 1 FROM evidence WHERE id=? AND case_id=?',
                (str(evidence_id), str(grant.case_id))).fetchone() is None:
            raise _not_found()
        if processing_run_id is not None:
            run = connection.execute('SELECT evidence_id,status FROM processing_runs WHERE id=? AND case_id=?',
                                     (str(processing_run_id), str(grant.case_id))).fetchone()
            if run is None or run['status'] != 'completed' or (evidence_id is not None and run['evidence_id'] != str(evidence_id)):
                raise _not_found()
        total = _validated_count(connection, parameters)
        # offset has no upper bound in the contract; do not bind huge Python integers to SQLite.
        items = _page(connection, parameters, limit, offset) if offset < total else []
    return JSONResponse(dict(items=items, total=total, limit=limit, offset=offset), headers={'Cache-Control': 'no-store'})
