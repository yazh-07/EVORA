"""U08 append-only human decisions on published case findings."""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit import record_audit_event
from backend.auth import CaseAccessGrant, require_case_access
from backend.database import SQLiteDatabase
from backend.errors import AccessError
from backend.evidence import invalid_input
from backend.observations import _utc_order


Decision = Literal["accepted", "rejected", "needs_investigation"]


def initialize_reviews(database: SQLiteDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS finding_reviews ("
            "id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), "
            "finding_id TEXT NOT NULL, actor_id TEXT NOT NULL, "
            "decision TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS finding_reviews_case_finding "
            "ON finding_reviews (case_id, finding_id)"
        )
        for operation in ("UPDATE", "DELETE"):
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS finding_reviews_no_{operation.lower()} "
                f"BEFORE {operation} ON finding_reviews "
                "BEGIN SELECT RAISE(ABORT, 'Finding reviews are append-only.'); END"
            )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS finding_reviews_no_replace "
            "BEFORE INSERT ON finding_reviews WHEN EXISTS ("
            "SELECT 1 FROM finding_reviews WHERE id = NEW.id OR rowid = NEW.rowid) "
            "BEGIN SELECT RAISE(ABORT, 'Finding reviews are append-only.'); END"
        )


class CreateReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Decision
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reason must contain non-whitespace characters.")
        return value


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    case_id: UUID
    finding_id: UUID
    actor_id: str
    decision: Decision
    reason: str
    created_at: datetime


def _require_finding(
    connection: sqlite3.Connection, request: Request, case_id: str, finding_id: str,
) -> None:
    if request.query_params:
        raise invalid_input()
    # A finding can belong to an older snapshot. Unpublished output left by an
    # interrupted/failed analysis must never make a finding reviewable.
    outputs = connection.execute(
        "SELECT o.findings_json FROM analysis_outputs AS o "
        "JOIN analysis_runs AS r ON r.id = o.run_id AND r.case_id = o.case_id "
        "WHERE o.case_id = ? AND r.status = 'completed'", (case_id,),
    )
    for output in outputs:
        if any(finding["id"] == finding_id and finding["case_id"] == case_id
               for finding in json.loads(output["findings_json"])):
            return
    raise AccessError(404, "NOT_FOUND", "Resource not found.")


router = APIRouter()


@router.post("/api/v1/cases/{caseId}/findings/{findingId}/reviews",
             operation_id="reviewFinding", status_code=201, response_model=ReviewDecision)
def review_finding(
    findingId: UUID, body: CreateReview, request: Request, response: Response,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
):
    case_id, finding_id = str(grant.case_id), str(findingId)
    with request.app.state.database.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_finding(connection, request, case_id, finding_id)
        review = ReviewDecision(
            id=uuid4(), case_id=grant.case_id, finding_id=findingId,
            actor_id=grant.actor.id, decision=body.decision, reason=body.reason,
            created_at=datetime.now(timezone.utc),
        )
        created_at = review.created_at.isoformat().replace("+00:00", "Z")
        connection.execute(
            "INSERT INTO finding_reviews "
            "(id, case_id, finding_id, actor_id, decision, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(review.id), case_id, finding_id, review.actor_id, review.decision,
             review.reason, created_at),
        )
        record_audit_event(
            connection, case_id=case_id, actor_id=review.actor_id,
            action="reviewFinding", target_id=finding_id, reason=review.reason,
            created_at=created_at,
        )
    response.headers["Cache-Control"] = "no-store"
    return review


@router.get("/api/v1/cases/{caseId}/findings/{findingId}/reviews",
            operation_id="listFindingReviews", response_model=list[ReviewDecision])
def list_finding_reviews(
    findingId: UUID, request: Request, response: Response,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
):
    case_id, finding_id = str(grant.case_id), str(findingId)
    with request.app.state.database.connect() as connection:
        connection.execute("BEGIN")
        _require_finding(connection, request, case_id, finding_id)
        connection.create_function("evora_utc_order", 1, _utc_order, deterministic=True)
        rows = connection.execute(
            "SELECT id, case_id, finding_id, actor_id, decision, reason, created_at "
            "FROM finding_reviews WHERE case_id = ? AND finding_id = ? "
            "ORDER BY evora_utc_order(created_at) ASC, id ASC", (case_id, finding_id),
        ).fetchall()
    response.headers["Cache-Control"] = "no-store"
    return [dict(row) for row in rows]
