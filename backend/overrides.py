"""U09 manual priority decisions, separate from immutable automated triage."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit import record_audit_event
from backend.auth import CaseAccessGrant, require_case_access
from backend.database import SQLiteDatabase
from backend.errors import AccessError
from backend.evidence import invalid_input


Priority = Literal["P1", "P2", "P3", "P4"]


def initialize_overrides(database: SQLiteDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS priority_overrides ("
            "id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), "
            "evidence_id TEXT NOT NULL REFERENCES evidence(id), actor_id TEXT NOT NULL, "
            "priority TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_priority_overrides "
            "ON priority_overrides (case_id, evidence_id, created_at, id)"
        )


class CreateOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    priority: Priority
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reason must contain non-whitespace characters.")
        return value


class PriorityOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    case_id: UUID
    evidence_id: UUID
    actor_id: str
    priority: Priority
    reason: str
    created_at: datetime


router = APIRouter()


@router.post("/api/v1/cases/{caseId}/evidence/{evidenceId}/priority-overrides",
             operation_id="setPriorityOverride", status_code=201,
             response_model=PriorityOverride)
def set_priority_override(
    evidenceId: UUID, body: CreateOverride, request: Request, response: Response,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
):
    if request.query_params:
        raise invalid_input()
    case_id, evidence_id = str(grant.case_id), str(evidenceId)
    with request.app.state.database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM evidence AS e JOIN cases AS c ON c.id = e.case_id "
            "WHERE e.id = ? AND c.id = ?", (evidence_id, case_id),
        ).fetchone() is None:
            raise AccessError(404, "NOT_FOUND", "Resource not found.")
        override = PriorityOverride(
            id=uuid4(), case_id=grant.case_id, evidence_id=evidenceId,
            actor_id=grant.actor.id, priority=body.priority, reason=body.reason,
            created_at=datetime.now(timezone.utc),
        )
        created_at = override.created_at.isoformat().replace("+00:00", "Z")
        connection.execute(
            "INSERT INTO priority_overrides "
            "(id, case_id, evidence_id, actor_id, priority, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(override.id), case_id, evidence_id, override.actor_id,
             override.priority, override.reason, created_at),
        )
        record_audit_event(
            connection, case_id=case_id, actor_id=override.actor_id,
            action="setPriorityOverride", target_id=evidence_id,
            reason=override.reason, created_at=created_at,
        )
    response.headers["Cache-Control"] = "no-store"
    return override
