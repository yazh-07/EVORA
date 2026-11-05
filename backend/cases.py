"""F01 case persistence and authoritative membership access."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.auth import Actor, CaseAccessGrant, authenticated_actor, require_case_access
from backend.database import SQLiteDatabase
from backend.errors import AccessError


class SQLiteCaseAccess:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def allows(self, actor_id: str, case_id: UUID) -> bool:
        # The same indexed query handles foreign and missing IDs. Never look up
        # case existence separately or expose a different denial response.
        with self.database.connect() as connection:
            # Local administrators manage all existing cases; other accounts need membership.
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_users'").fetchone():
                if connection.execute("SELECT 1 FROM local_users WHERE id=? AND role='administrator' AND disabled=0", (actor_id,)).fetchone():
                    return connection.execute('SELECT 1 FROM cases WHERE id=?', (str(case_id),)).fetchone() is not None
            return connection.execute(
                "SELECT 1 FROM case_members WHERE case_id = ? AND actor_id = ?",
                (str(case_id), actor_id),
            ).fetchone() is not None


def initialize_cases(database: SQLiteDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, "
            "title TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS case_members ("
            "case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE, "
            "actor_id TEXT NOT NULL, PRIMARY KEY (case_id, actor_id))"
        )


class CreateCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must contain non-whitespace characters.")
        return value


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    description: str | None = None
    created_at: datetime


class CasePage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Case]
    total: int
    limit: int
    offset: int


router = APIRouter()


@router.get("/api/v1/cases", operation_id="listCases", status_code=200,
            response_model=CasePage, response_model_exclude_none=True)
def list_cases(request: Request,
               actor: Annotated[Actor, Depends(authenticated_actor)],
               limit: Annotated[int, Query(ge=1, le=100)] = 20,
               offset: Annotated[int, Query(ge=0)] = 0):
    with request.app.state.database.connect() as connection:
        # Count and page share one SQLite read snapshot.
        connection.execute("BEGIN")
        if actor.role == 'administrator':
            total = connection.execute('SELECT count(*) FROM cases').fetchone()[0]
            rows = connection.execute('SELECT * FROM cases ORDER BY created_at DESC,id ASC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
            return CasePage(items=[Case(**dict(row)) for row in rows], total=total, limit=limit, offset=offset)
        total = connection.execute(
            "SELECT count(*) FROM case_members WHERE actor_id = ?", (actor.id,),
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT c.id, c.title, c.description, c.created_at FROM cases AS c "
            "JOIN case_members AS m ON m.case_id = c.id WHERE m.actor_id = ? "
            "ORDER BY c.created_at DESC, c.id ASC LIMIT ? OFFSET ?",
            (actor.id, limit, offset),
        ).fetchall() if offset < total else []
    return CasePage(items=[Case(**dict(row)) for row in rows],
                    total=total, limit=limit, offset=offset)


@router.post("/api/v1/cases", operation_id="createCase", status_code=201,
             response_model=Case, response_model_exclude_none=True)
def create_case(body: CreateCase, request: Request,
                actor: Annotated[Actor, Depends(authenticated_actor)]):
    case = Case(id=uuid4(), title=body.title, description=body.description,
                created_at=datetime.now(timezone.utc))
    with request.app.state.database.connect() as connection:
        connection.execute(
            "INSERT INTO cases (id, title, description, created_at) VALUES (?, ?, ?, ?)",
            (str(case.id), case.title, case.description, case.created_at.isoformat().replace("+00:00", "Z")),
        )
        connection.execute("INSERT INTO case_members (case_id, actor_id) VALUES (?, ?)",
                           (str(case.id), actor.id))
    return case


@router.get("/api/v1/cases/{caseId}", operation_id="getCase",
            response_model=Case, response_model_exclude_none=True)
def get_case(request: Request,
             grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
    with request.app.state.database.connect() as connection:
        row = connection.execute("SELECT id, title, description, created_at FROM cases WHERE id = ?",
                                 (str(grant.case_id),)).fetchone()
    if row is None:
        raise AccessError(404, "NOT_FOUND", "Resource not found.")
    return dict(row)
