"""F03 private original intake and F04 authorized metadata reads."""

from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict

from backend.auth import CaseAccessGrant, require_case_access
from backend.database import SQLiteDatabase
from backend.errors import AccessError

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
KINDS = frozenset(("document", "image", "video", "audio", "message", "network_log",
                   "mobile_log", "transaction", "gps"))
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)", re.ASCII)


def initialize_evidence(database: SQLiteDatabase) -> None:
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, "
            "case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE, "
            "kind TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL, "
            "source_label TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, "
            "acquired_at TEXT, created_at TEXT NOT NULL, storage_path TEXT NOT NULL)"
        )


def invalid_input() -> AccessError:
    return AccessError(400, "INVALID_INPUT", "Invalid request input.")


router = APIRouter()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    case_id: UUID
    kind: str
    filename: str
    media_type: str
    source_label: str
    sha256: str
    size_bytes: int
    # Keep source timestamp text exactly as stored by intake.
    acquired_at: str | None = None
    created_at: str


class EvidencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Evidence]
    total: int
    limit: int
    offset: int


_METADATA_COLUMNS = (
    "id, case_id, kind, filename, media_type, source_label, sha256, "
    "size_bytes, acquired_at, created_at"
)


@router.get("/api/v1/cases/{caseId}/evidence", operation_id="listEvidence",
            response_model=EvidencePage, response_model_exclude_none=True)
def list_evidence(
    caseId: UUID,
    request: Request,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    parameters = {"case_id": str(grant.case_id), "limit": limit, "offset": offset}
    with request.app.state.database.connect() as connection:
        # Count and page use the same SQLite read snapshot.
        connection.execute("BEGIN")
        total = connection.execute(
            "SELECT count(*) FROM evidence WHERE case_id = :case_id", parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT {_METADATA_COLUMNS} FROM evidence WHERE case_id = :case_id "
            "ORDER BY created_at DESC, id ASC LIMIT :limit OFFSET :offset", parameters,
        ).fetchall()
    return EvidencePage(items=[Evidence(**dict(row)) for row in rows],
                        total=total, limit=limit, offset=offset)


@router.get("/api/v1/cases/{caseId}/evidence/{evidenceId}", operation_id="getEvidence",
            response_model=Evidence, response_model_exclude_none=True)
def get_evidence(
    caseId: UUID,
    evidenceId: UUID,
    request: Request,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
):
    with request.app.state.database.connect() as connection:
        row = connection.execute(
            f"SELECT {_METADATA_COLUMNS} FROM evidence "
            "WHERE case_id = :case_id AND id = :evidence_id",
            {"case_id": str(grant.case_id), "evidence_id": str(evidenceId)},
        ).fetchone()
    if row is None:
        raise AccessError(404, "NOT_FOUND", "Resource not found.")
    return Evidence(**dict(row))


@router.post("/api/v1/cases/{caseId}/evidence", operation_id="uploadEvidence",
             status_code=201)
async def upload_evidence(
    request: Request,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
    file: UploadFile = File(...),
    kind: str = Form(...),
    source_label: str = Form(...),
    acquired_at: str | None = Form(None),
):
    filename = file.filename or ""
    if (kind not in KINDS or not source_label.strip() or not filename.strip()
            or filename in (".", "..") or ".." in filename
            or any(c in filename for c in '/\\:<>"|?*')
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)):
        raise invalid_input()
    if "acquired_at" in await request.form() and acquired_at is None:
        raise invalid_input()
    if acquired_at is not None:
        try:
            if not _TIMESTAMP.fullmatch(acquired_at):
                raise ValueError
            datetime.fromisoformat(acquired_at.upper())
        except ValueError:
            raise invalid_input() from None

    evidence_id = str(uuid4())
    case_id = str(grant.case_id)
    request.app.state.storage_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = request.app.state.storage_dir / case_id
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / (evidence_id + ".bin")
    digest = hashlib.sha256()
    size = 0
    created = False
    try:
        # Exclusive creation never overwrites an original, even on UUID collision.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as output:
            while chunk := await file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise AccessError(413, "PAYLOAD_TOO_LARGE", "Upload exceeds configured limit.")
                output.write(chunk)
                digest.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        result = dict(id=evidence_id, case_id=case_id, kind=kind, filename=filename,
                      media_type=file.content_type or "application/octet-stream",
                      source_label=source_label, sha256=digest.hexdigest(), size_bytes=size,
                      created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        if acquired_at is not None:
            result["acquired_at"] = acquired_at
        with request.app.state.database.connect() as connection:
            connection.execute(
                "INSERT INTO evidence (id, case_id, kind, filename, media_type, source_label, "
                "sha256, size_bytes, acquired_at, created_at, storage_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (evidence_id, case_id, kind, filename, result["media_type"], source_label,
                 result["sha256"], size, acquired_at, result["created_at"], str(path)),
            )
        return result
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
