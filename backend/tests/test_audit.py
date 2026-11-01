"""F06 real intake/API/SQLite/private-file accounting and failure acceptance."""

import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.audit import INTAKE_RECORD_VERSION, record_intake
from backend.auth import SyntheticTokenVerifier
from backend.cases import initialize_cases
from backend.evidence import initialize_evidence


class IntakeAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.storage = self.root / "private"
        self.app = create_app(self.root / "db.sqlite3", storage_dir=self.storage,
                              token_verifier=SyntheticTokenVerifier({
                                  "synthetic-a": "investigator-1", "synthetic-b": "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
            headers={"Authorization": "Bearer synthetic-a"}))
        self.case_a = (await self.client.post("/api/v1/cases", json={"title": "Synthetic A"})).json()["id"]
        self.case_b = (await self.client.post("/api/v1/cases", json={"title": "Synthetic B"},
                         headers={"Authorization": "Bearer synthetic-b"})).json()["id"]
        self.url = f"/api/v1/cases/{self.case_a}/evidence"
        # Missing bundle fails loudly; no fabricated substitute schema/skips.
        self.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())

    def rows(self, table):
        # Names below are test-owned constants, never request input.
        with self.app.state.database.connect() as connection:
            return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]

    def validate(self, schema, value):
        Draft202012Validator(
            {**self.spec["components"]["schemas"][schema], "components": self.spec["components"]},
            format_checker=FormatChecker(),
        ).validate(value)

    async def upload(self, content=b"SYNTHETIC_PRIVATE_BYTES\x00\xff", **kwargs):
        return await self.client.post(kwargs.pop("url", self.url),
            data=kwargs.pop("data", {"kind": "network_log", "source_label": " Synthetic source "}),
            files={"file": (kwargs.pop("filename", "source.bin"), content, "application/octet-stream")},
            **kwargs)

    def assert_no_intake(self):
        for table in ("evidence", "audit_events", "intake_provenance"):
            self.assertEqual(self.rows(table), [], table)
        self.assertEqual(list(self.storage.rglob("*.bin")), [])

    async def test_success_records_one_linked_safe_event_and_exact_private_source(self):
        content = Path("fixtures/synthetic-case/network.csv").read_bytes()
        timestamp = "2026-11-01T10:11:12.123+05:30"
        response = await self.upload(content, filename="SYNTHETIC_PRIVATE_FILENAME.csv",
            data={"kind": "network_log", "source_label": " SYNTHETIC_PRIVATE_SOURCE ", "acquired_at": timestamp})
        self.assertEqual(response.status_code, 201, response.text)
        evidence = response.json()
        self.validate("Evidence", evidence)
        [event] = self.rows("audit_events")
        public = {key: value for key, value in event.items() if value is not None}
        self.validate("AuditEvent", public)
        UUID(public["id"])
        self.assertEqual(public, dict(id=public["id"], case_id=self.case_a,
            actor_id="investigator-1", action="uploadEvidence", target_id=evidence["id"],
            created_at=evidence["created_at"]))
        self.assertEqual(datetime.fromisoformat(public["created_at"]).utcoffset().total_seconds(), 0)
        [source] = self.rows("intake_provenance")
        UUID(source["id"])
        self.assertEqual(source, dict(id=source["id"], record_version=INTAKE_RECORD_VERSION,
            audit_event_id=event["id"], evidence_id=evidence["id"],
            source_filename=evidence["filename"], source_label=evidence["source_label"],
            media_type=evidence["media_type"], acquired_at=timestamp,
            original_sha256=hashlib.sha256(content).hexdigest(), original_size_bytes=len(content),
            created_at=evidence["created_at"]))
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(public))
        metadata = await self.client.get(self.url + "/" + evidence["id"])
        self.assertEqual(metadata.json(), evidence)
        download = await self.client.get(self.url + "/" + evidence["id"] + "/content")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, content)
        self.assertEqual(len(self.rows("audit_events")), 1, "Reads/download must not claim another intake")

    async def test_server_identity_time_action_and_target_cannot_be_forged_by_form_fields(self):
        response = await self.upload(data={"kind": "document", "source_label": "Synthetic",
            "actor_id": "forged-actor", "action": "forged-action", "target_id": str(uuid4()),
            "created_at": "1900-01-01T00:00:00Z", "reason": "SYNTHETIC_PRIVATE_REASON"})
        self.assertEqual(response.status_code, 201)
        [event] = self.rows("audit_events")
        self.assertEqual(event["actor_id"], "investigator-1")
        self.assertEqual(event["action"], "uploadEvidence")
        self.assertEqual(event["target_id"], response.json()["id"])
        self.assertEqual(event["created_at"], response.json()["created_at"])
        self.assertIsNone(event["reason"])

    async def test_two_real_actors_cases_are_linked_without_cross_case_references(self):
        first = await self.upload()
        second = await self.upload(url=f"/api/v1/cases/{self.case_b}/evidence",
                                   headers={"Authorization": "Bearer synthetic-b"})
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        expected = {first.json()["id"]: (self.case_a, "investigator-1"),
                    second.json()["id"]: (self.case_b, "investigator-2")}
        events = {event["id"]: event for event in self.rows("audit_events")}
        for source in self.rows("intake_provenance"):
            event = events[source["audit_event_id"]]
            self.assertEqual(event["target_id"], source["evidence_id"])
            self.assertEqual((event["case_id"], event["actor_id"]), expected[source["evidence_id"]])

    async def test_rejected_auth_foreign_missing_and_invalid_input_create_no_success_event(self):
        attempts = [
            ({"headers": {"Authorization": "Bearer invalid-synthetic"}}, 401),
            ({"headers": {"Authorization": "Bearer synthetic-b"}}, 404),
            ({"url": f"/api/v1/cases/{uuid4()}/evidence"}, 404),
            ({"url": "/api/v1/cases/not-a-uuid/evidence"}, 400),
            ({"filename": "../bad.bin"}, 400),
            ({"data": {"kind": "unknown", "source_label": "Synthetic"}}, 400),
        ]
        for kwargs, status in attempts:
            with self.subTest(status=status):
                response = await self.upload(**kwargs)
                self.assertEqual(response.status_code, status, response.text)
                self.validate("ApiError", response.json())
                self.assert_no_intake()

    async def test_oversized_upload_removes_partial_file_and_creates_no_records(self):
        with patch("backend.evidence.MAX_UPLOAD_BYTES", 65536):
            response = await self.upload(b"x" * 65537)
        self.assertEqual(response.status_code, 413)
        self.assert_no_intake()

    async def test_metadata_insert_failure_creates_no_accounting_or_file(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_metadata BEFORE INSERT ON evidence "
                               "BEGIN SELECT RAISE(ABORT, 'Synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_no_intake()

    async def test_audit_insert_failure_rolls_back_evidence_and_removes_original(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events "
                               "BEGIN SELECT RAISE(ABORT, 'Synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_no_intake()

    async def test_provenance_insert_failure_rolls_back_event_evidence_and_original(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_provenance BEFORE INSERT ON intake_provenance "
                               "BEGIN SELECT RAISE(ABORT, 'Synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_no_intake()

    async def test_commit_failure_rolls_back_all_three_records_and_original(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TABLE fail_at_commit (case_id TEXT REFERENCES cases(id) "
                               "DEFERRABLE INITIALLY DEFERRED)")
            connection.execute("CREATE TRIGGER fail_commit AFTER INSERT ON intake_provenance "
                               "BEGIN INSERT INTO fail_at_commit VALUES ('synthetic-missing-case'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_no_intake()

    async def test_retry_after_rolled_back_failure_records_only_one_success(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER fail_once BEFORE INSERT ON intake_provenance "
                               "BEGIN SELECT RAISE(ABORT, 'Synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_no_intake()
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TRIGGER fail_once")
        self.assertEqual((await self.upload()).status_code, 201)
        self.assertEqual(len(self.rows("audit_events")), 1)
        self.assertEqual(len(self.rows("intake_provenance")), 1)

    async def test_history_is_append_only_including_replace_and_upsert(self):
        self.assertEqual((await self.upload()).status_code, 201)
        for table in ("audit_events", "intake_provenance"):
            original = self.rows(table)
            row = original[0]
            columns = ", ".join(row)
            placeholders = ", ".join("?" for _ in row)
            mutations = [
                (f"UPDATE {table} SET created_at = '1900-01-01T00:00:00Z'", ()),
                (f"DELETE FROM {table}", ()),
                (f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values())),
                (f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                 "ON CONFLICT(id) DO UPDATE SET created_at = excluded.created_at", tuple(row.values())),
            ]
            if table == "intake_provenance":
                replacement = {**row, "id": str(uuid4())}
                mutations.append((f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
                                  tuple(replacement.values())))
            for statement, values in mutations:
                with self.subTest(table=table, operation=statement.split()[0]):
                    with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                        with self.app.state.database.connect() as connection:
                            connection.execute(statement, values)
                    self.assertEqual(self.rows(table), original)

    async def test_multiple_uploads_append_distinct_events_without_rewriting_earlier_source(self):
        self.assertEqual((await self.upload()).status_code, 201)
        original_event = self.rows("audit_events")[0]
        original_source = self.rows("intake_provenance")[0]
        responses = await asyncio.gather(*(self.upload(bytes([index])) for index in range(4)))
        self.assertTrue(all(response.status_code == 201 for response in responses))
        events, sources = self.rows("audit_events"), self.rows("intake_provenance")
        self.assertEqual(len(events), 5)
        self.assertEqual(len({event["target_id"] for event in events}), 5)
        self.assertEqual(len(sources), 5)
        self.assertIn(original_event, events)
        self.assertIn(original_source, sources)

    async def test_repeat_startup_preserves_existing_history_without_duplicate_events(self):
        self.assertEqual((await self.upload()).status_code, 201)
        before = (self.rows("audit_events"), self.rows("intake_provenance"), self.rows("evidence"))
        async with self.app.router.lifespan_context(self.app):
            self.assertEqual((self.rows("audit_events"), self.rows("intake_provenance"), self.rows("evidence")), before)

    async def test_private_values_are_not_logged_on_success_rejection_or_accounting_failure(self):
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)
        try:
            self.assertEqual((await self.upload(filename="SYNTHETIC_PRIVATE_FILENAME.bin",
                data={"kind": "document", "source_label": "SYNTHETIC_PRIVATE_SOURCE"})).status_code, 201)
            self.assertEqual((await self.upload(headers={"Authorization": "Bearer SYNTHETIC_PRIVATE_TOKEN"})).status_code, 401)
            with self.app.state.database.connect() as connection:
                connection.execute("CREATE TRIGGER fail_private BEFORE INSERT ON intake_provenance "
                                   "BEGIN SELECT RAISE(ABORT, 'Synthetic failure'); END")
            async with AsyncClient(transport=ASGITransport(self.app, raise_app_exceptions=False),
                                   base_url="http://test", headers=self.client.headers) as client:
                response = await client.post(self.url, data={"kind": "document", "source_label": "SYNTHETIC_PRIVATE_SOURCE"},
                    files={"file": ("SYNTHETIC_PRIVATE_FILENAME.bin", b"SYNTHETIC_PRIVATE_BYTES")})
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("SYNTHETIC_PRIVATE", response.text)
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)
            handler.close()
        self.assertNotIn("SYNTHETIC_PRIVATE", captured.getvalue())
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(self.rows("audit_events")))
        self.assertEqual(len(self.rows("evidence")), 1)
        self.assertEqual(len(self.rows("audit_events")), 1)
        self.assertEqual(len(self.rows("intake_provenance")), 1)

    async def test_internal_hook_rejects_cross_case_or_missing_evidence(self):
        evidence = (await self.upload()).json()
        before = (self.rows("audit_events"), self.rows("intake_provenance"))
        for case, target in ((self.case_b, evidence["id"]), (self.case_a, str(uuid4()))):
            with self.assertRaisesRegex(ValueError, "Intake evidence record missing"):
                with self.app.state.database.connect() as connection:
                    record_intake(connection, actor_id="investigator-1", case_id=case, evidence_id=target)
        self.assertEqual((self.rows("audit_events"), self.rows("intake_provenance")), before)

    async def test_private_provenance_is_not_exposed(self):
        self.assertEqual((await self.upload()).status_code, 201)
        for path in ("/intake_provenance", "/audit_events"):
            self.assertEqual((await self.client.get(path)).status_code, 404)


class LegacyIntakeStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_evidence_survives_upgrade_without_fabricated_audit_backfill(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        app = create_app(root / "old.sqlite3", storage_dir=root / "private",
                         token_verifier=SyntheticTokenVerifier({"synthetic-a": "investigator-1"}))
        initialize_cases(app.state.database)
        initialize_evidence(app.state.database)
        case, evidence = str(uuid4()), str(uuid4())
        path = root / "private" / case / (evidence + ".bin")
        path.parent.mkdir(parents=True)
        content = b"Synthetic pre-F06 original"
        path.write_bytes(content)
        stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with app.state.database.connect() as connection:
            connection.execute("INSERT INTO cases VALUES (?, ?, ?, ?)", (case, "Synthetic legacy", None, stamp))
            connection.execute("INSERT INTO case_members VALUES (?, ?)", (case, "investigator-1"))
            connection.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (evidence, case, "document", "old.bin", "application/octet-stream", "Legacy source",
                 hashlib.sha256(content).hexdigest(), len(content), None, stamp, str(path)))
        async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
            base_url="http://test", headers={"Authorization": "Bearer synthetic-a"}) as client:
            response = await client.get(f"/api/v1/cases/{case}/evidence/{evidence}/content")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, content)
            with app.state.database.connect() as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM audit_events").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM intake_provenance").fetchone()[0], 0)
            new = await client.post(f"/api/v1/cases/{case}/evidence",
                data={"kind": "document", "source_label": "New source"}, files={"file": ("new.bin", b"new")})
            self.assertEqual(new.status_code, 201)
            with app.state.database.connect() as connection:
                [event] = connection.execute("SELECT target_id FROM audit_events").fetchall()
                self.assertEqual(event["target_id"], new.json()["id"])
                self.assertEqual(connection.execute("SELECT count(*) FROM evidence").fetchone()[0], 2)
            self.assertEqual(path.read_bytes(), content)
