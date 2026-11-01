from contextlib import closing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend.app import create_app


class SkeletonTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / "private" / "evora.sqlite3"

    async def test_factory_defers_io_and_lifespan_opens_real_sqlite(self):
        app = create_app(self.path)
        self.assertFalse(self.path.exists())
        async with app.router.lifespan_context(app):
            self.assertTrue(self.path.is_file())
            with app.state.database.connect() as connection:
                self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual([row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )], ["audit_events", "case_members", "cases", "evidence", "intake_provenance"])
        # Lifespan has left no open connection; reconnect after shutdown.
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_connections_commit_read_back_rollback_and_close(self):
        database = create_app(self.path).state.database
        # Table and rows are test-only, never part of the application schema.
        with database.connect() as connection:
            connection.execute("CREATE TABLE probe (value TEXT NOT NULL)")
            connection.execute("INSERT INTO probe VALUES (?)", ("synthetic",))
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with database.connect() as failed_connection:
                failed_connection.execute("INSERT INTO probe VALUES (?)", ("rolled back",))
                raise RuntimeError("synthetic failure")
        with self.assertRaises(sqlite3.ProgrammingError):
            failed_connection.execute("SELECT 1")
        with database.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual([row["value"] for row in connection.execute("SELECT value FROM probe")],
                             ["synthetic"])

    def test_foreign_key_violation_is_rejected_and_rolled_back(self):
        database = create_app(self.path).state.database
        with database.connect() as connection:
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
        with self.assertRaises(sqlite3.IntegrityError):
            with database.connect() as connection:
                connection.execute("INSERT INTO child VALUES (123)")
        with database.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM child").fetchone()[0], 0)

    async def test_only_f01_routes_are_exposed(self):
        app = create_app(self.path)
        async with app.router.lifespan_context(app), AsyncClient(
            transport=ASGITransport(app), base_url="http://test"
        ) as client:
            for path in ("/", "/health", "/status", "/docs", "/redoc", "/openapi.json",
                         "/_test/input"):
                with self.subTest(path=path):
                    self.assertEqual((await client.get(path)).status_code, 404)
            self.assertEqual((await client.post("/api/v1/cases", json={"title": "Synthetic"})).status_code,
                             401)

    def test_environment_configuration_and_explicit_override(self):
        with patch.dict(os.environ, {"EVORA_DATABASE_PATH": str(self.path)}):
            self.assertEqual(create_app().state.database.path, self.path)
            explicit = self.path.with_name("explicit.sqlite3")
            self.assertEqual(create_app(explicit).state.database.path, explicit)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(create_app().state.database.path, Path("storage/evora.sqlite3"))
        for value in ("", " ", ":memory:"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                create_app(value)

    async def test_separate_apps_use_separate_database_files(self):
        first = create_app(self.path)
        second = create_app(self.path.with_name("other.sqlite3"))
        async with first.router.lifespan_context(first), second.router.lifespan_context(second):
            with first.state.database.connect() as connection:
                connection.execute("CREATE TABLE first_only (value TEXT)")
            with second.state.database.connect() as connection:
                self.assertIsNone(connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'first_only'"
                ).fetchone())

    async def test_database_open_failure_prevents_startup(self):
        # An existing directory cannot be opened as a SQLite database file.
        self.path.mkdir(parents=True)
        with self.assertRaises(sqlite3.OperationalError):
            app = create_app(self.path)
            async with app.router.lifespan_context(app):
                self.fail("Startup must fail before serving requests")
