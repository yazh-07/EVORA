"""App factory and startup check; G01 exposes no HTTP operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from backend.database import SQLiteDatabase
from backend.errors import invalid_request


def create_app(database_path: str | Path | None = None) -> FastAPI:
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
        # Fail startup if SQLite cannot open the configured file. No domain
        # migrations/tables or fictional health success are introduced here.
        with database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        yield

    app = FastAPI(
        title="EVORA backend skeleton",
        version="0.3.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.database = database
    app.add_exception_handler(RequestValidationError, invalid_request)
    return app


async def get_database(request: Request) -> SQLiteDatabase:
    """Dependency for future routes; each caller owns its connection context."""
    return request.app.state.database
