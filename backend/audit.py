"""F06 append-only intake accounting; private source details are not public audit."""

import sqlite3
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from backend.auth import CaseAccessGrant, require_case_access
from backend.database import SQLiteDatabase


INTAKE_RECORD_VERSION = "intake-source.v1"

# Public diagnostics are application codes, never exception messages or source
# values. Unknown future adapter codes fail closed to the generic diagnostic.
_PROCESSING_ERRORS = frozenset({
    "PROCESSING_FAILED", "PROCESSING_INTERRUPTED", "SOURCE_UNAVAILABLE", "IMAGE_UNDERSTANDING_FAILED",
    *("CSV_" + code for code in (
        "INVALID_SOURCE", "INVALID_CONTEXT", "BYTE_LIMIT", "INVALID_UTF8",
        "MALFORMED_CSV", "INVALID_HEADER", "ROW_LIMIT", "INVALID_ROW",
        "INVALID_IP", "INVALID_TIMESTAMP", "INVALID_TIMEZONE", "INVALID_COORDINATE",
        "MENTION_LIMIT", "INVALID_AMOUNT", "AMOUNT_LIMIT", "INVALID_CURRENCY",
    )),
    *("TEXT_" + code for code in (
        "INVALID_SOURCE", "INVALID_CONTEXT", "BYTE_LIMIT", "INVALID_UTF8",
        "NUL_BYTE", "LINE_LIMIT",
    )),
})

_ANALYSIS_ERRORS = frozenset({"ANALYSIS_FAILED", "GRAPH_PROJECTION_FAILED"})

# Intake producers store UTC with a Z suffix. Canonical fractional comparison
# keeps whole-second and fractional timestamps in chronological order, retaining
# microseconds (SQLite date functions would round them to milliseconds).
_AUDIT_ORDER = (
    "substr(created_at, 1, 19) ASC, "
    "CASE WHEN substr(created_at, 20, 1) = '.' "
    "THEN substr(substr(created_at, 21, length(created_at) - 21) || '000000', 1, 6) "
    "ELSE '000000' END ASC, id ASC"
)


def initialize_audit(database: SQLiteDatabase) -> None:
    """Add empty accounting tables without fabricating historical intake actors."""
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS audit_events ("
            "id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), "
            "actor_id TEXT NOT NULL, action TEXT NOT NULL, target_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, reason TEXT) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS audit_events_case_order "
            f"ON audit_events (case_id, {_AUDIT_ORDER})"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS intake_provenance ("
            "id TEXT PRIMARY KEY, record_version TEXT NOT NULL, "
            "audit_event_id TEXT NOT NULL UNIQUE REFERENCES audit_events(id), "
            "evidence_id TEXT NOT NULL UNIQUE REFERENCES evidence(id), "
            "source_filename TEXT NOT NULL, source_label TEXT NOT NULL, "
            "media_type TEXT NOT NULL, acquired_at TEXT, "
            "original_sha256 TEXT NOT NULL, original_size_bytes INTEGER NOT NULL, "
            "created_at TEXT NOT NULL) WITHOUT ROWID"
        )
        # Static, application-owned table/column names only. No request values
        # enter DDL. WITHOUT ROWID removes the hidden-rowid replacement path.
        for table, unique_columns in (
            ("audit_events", ("id",)),
            ("intake_provenance", ("id", "audit_event_id", "evidence_id")),
        ):
            for operation in ("UPDATE", "DELETE"):
                connection.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} "
                    f"BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Intake records are append-only.'); END"
                )
            # REPLACE can bypass SQLite delete triggers when recursive triggers
            # are off. Reject collisions before INSERT, including UPSERT/REPLACE.
            collision = " OR ".join(f"{column} = NEW.{column}" for column in unique_columns)
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
                f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {collision}) "
                "BEGIN SELECT RAISE(ABORT, 'Intake records are append-only.'); END"
            )


def record_audit_event(
    connection: sqlite3.Connection, *, case_id: str, actor_id: str, action: str,
    target_id: str, created_at: str, reason: str | None = None,
) -> None:
    """Append within the caller's transaction; never commit separately."""
    connection.execute(
        "INSERT INTO audit_events (id, case_id, actor_id, action, target_id, created_at, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), case_id, actor_id, action, target_id, created_at, reason),
    )


def record_processing_audit(
    connection: sqlite3.Connection, run, status: str, finished_at: str,
    error: str | None = None,
) -> None:
    """Append in the terminal transition transaction; never commit separately.

    The frozen server run/version links to private processing configuration and,
    on success, processing_provenance.run_id. Failures have no published output
    provenance. Callers serialize the transition and only append after updating
    one nonterminal run, so replay/recovery cannot append a second event.
    """
    if status not in {"completed", "failed"}:
        raise ValueError("Processing audit requires a terminal state.")
    reason = f"run:{run['id']};status:{status};version:{run['processor_version']}"
    if status == "failed":
        code = error if error in _PROCESSING_ERRORS else "PROCESSING_FAILED"
        reason += f";error:{code}"
    connection.execute(
        "INSERT INTO audit_events (id, case_id, actor_id, action, target_id, created_at, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), run['case_id'], run['actor_id'], "startProcessing",
         run['evidence_id'], finished_at, reason),
    )


def record_analysis_event(
    connection: sqlite3.Connection, *, run: dict | sqlite3.Row, status: str,
    finished_at: str, error: str | None = None,
) -> None:
    """Append within the terminal status transaction, without committing.

    The run ID joins to the private frozen inputs, algorithm and immutable SQL
    outputs (when produced). No source content or driver diagnostics are public.
    Callers serialize transitions and append only for a changed nonterminal run.
    """
    if status not in {"completed", "failed"}:
        raise ValueError("Analysis audit requires a terminal state.")
    reason = f"run:{run['id']};status:{status};version:{run['algorithm_version']}"
    if status == "failed":
        code = error if error in _ANALYSIS_ERRORS else "ANALYSIS_FAILED"
        reason += f";error:{code}"
    connection.execute(
        "INSERT INTO audit_events (id, case_id, actor_id, action, target_id, created_at, reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), run['case_id'], run['actor_id'], "startAnalysis",
         run['id'], finished_at, reason),
    )


def record_intake(
    connection: sqlite3.Connection, *, actor_id: str, case_id: str, evidence_id: str,
) -> None:
    """Append inside the caller's evidence transaction; never commit separately.

    Read the authoritative inserted metadata, with its same-case check, instead
    of accepting an alternate metadata/actor/time envelope from the upload form.
    The actor comes from the authenticated grant. Source values stay private;
    public audit contains only server identities and operation/resource references.
    """
    row = connection.execute(
        "SELECT filename, source_label, media_type, acquired_at, sha256, size_bytes, created_at "
        "FROM evidence WHERE id = ? AND case_id = ?", (evidence_id, case_id),
    ).fetchone()
    if row is None:
        raise ValueError("Intake evidence record missing.")
    event_id = str(uuid4())
    connection.execute(
        "INSERT INTO audit_events (id, case_id, actor_id, action, target_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, case_id, actor_id, "uploadEvidence", evidence_id, row["created_at"]),
    )
    connection.execute(
        "INSERT INTO intake_provenance (id, record_version, audit_event_id, evidence_id, "
        "source_filename, source_label, media_type, acquired_at, original_sha256, "
        "original_size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), INTAKE_RECORD_VERSION, event_id, evidence_id, row["filename"],
         row["source_label"], row["media_type"], row["acquired_at"], row["sha256"],
         row["size_bytes"], row["created_at"]),
    )


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    case_id: UUID
    actor_id: str
    action: str
    target_id: str
    created_at: datetime
    reason: str | None = None


class AuditPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AuditEvent]
    total: int
    limit: int
    offset: int


router = APIRouter()


@router.get("/api/v1/cases/{caseId}/audit-events", operation_id="listAuditEvents",
            response_model=AuditPage, response_model_exclude_none=True)
def list_audit_events(
    request: Request,
    response: Response,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with request.app.state.database.connect() as connection:
        connection.execute("BEGIN")
        parameters = {"case_id": str(grant.case_id), "limit": limit, "offset": offset}
        total = connection.execute(
            "SELECT count(*) FROM audit_events WHERE case_id = :case_id", parameters,
        ).fetchone()[0]
        # Explicit safe-column projection: private intake provenance is never
        # joined or serialized. Producers store server timestamps as UTC.
        # Offset has no contract upper bound. A beyond-end offset returns an
        # empty page, including integers too large for a SQLite bound integer.
        rows = connection.execute(
            "SELECT id, case_id, actor_id, action, target_id, created_at, reason "
            "FROM audit_events WHERE case_id = :case_id "
            f"ORDER BY {_AUDIT_ORDER} LIMIT :limit OFFSET :offset", parameters,
        ).fetchall() if offset < total else []
    response.headers["Cache-Control"] = "no-store"
    return AuditPage(items=[AuditEvent(**dict(row)) for row in rows],
                     total=total, limit=limit, offset=offset)
