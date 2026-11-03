"""App factory, SQLite startup and F01 case operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from backend.analysis import initialize_analysis, recover_analysis_runs, router as analysis_router
from backend.auth import CaseAccess, RejectTokens, TokenVerifier
from backend.audit import initialize_audit, router as audit_router
from backend.database import SQLiteDatabase
from backend.cases import SQLiteCaseAccess, initialize_cases, router
from backend.evidence import initialize_evidence, router as evidence_router
from backend.processing import initialize_processing, router as processing_router
from backend.observations import router as observations_router
from backend.entities import router as entities_router
from backend.events import router as events_router
from backend.findings import router as findings_router
from backend.errors import AccessError, access_error, invalid_request


def create_app(
    database_path: str | Path | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    case_access: CaseAccess | None = None,
    storage_dir: str | Path | None = None,
) -> FastAPI:
    """Configure an isolated app; opening SQLite is deferred until startup."""
    configured_path = (
        database_path
        if database_path is not None
        else os.environ.get("EVORA_DATABASE_PATH", "storage/evora.sqlite3")
    )
    if not str(configured_path).strip() or str(configured_path) == ":memory:":
        raise ValueError("EVORA_DATABASE_PATH must name a SQLite file.")
    database = SQLiteDatabase(Path(configured_path))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        initialize_cases(database)
        initialize_evidence(database)
        initialize_audit(database)
        initialize_processing(database)
        initialize_analysis(database)
        try:
            await recover_analysis_runs(_app)
            yield
        finally:
            if _app.state.graph_database is not None:
                _app.state.graph_database.close()

    app = FastAPI(
        title="EVORA backend skeleton",
        version="0.3.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.database = database
    app.state.processing_lock = asyncio.Lock()
    app.state.analysis_lock = asyncio.Lock()
    app.state.graph_database = None
    app.state.storage_dir = Path(storage_dir if storage_dir is not None else
                                 os.environ.get("EVORA_STORAGE_DIR", "storage/evidence")).resolve()
    app.state.token_verifier = token_verifier if token_verifier is not None else RejectTokens()
    app.state.case_access = case_access if case_access is not None else SQLiteCaseAccess(database)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(AccessError, access_error)
    app.include_router(router)
    app.include_router(evidence_router)
    app.include_router(audit_router)
    app.include_router(processing_router)
    app.include_router(observations_router)
    app.include_router(entities_router)
    app.include_router(events_router)
    app.include_router(analysis_router)
    app.include_router(findings_router)
    return app


async def get_database(request: Request) -> SQLiteDatabase:
    """Dependency for future routes; each caller owns its connection context."""
    return request.app.state.database
