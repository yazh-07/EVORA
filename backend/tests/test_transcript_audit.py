"""F08D transcript audit regressions over real HTTP and SQLite transactions.

Machine transcript publication is an explicit fixture: this checkout has no ASR
adapter. Correction, audit, provenance storage and analysis publication stay real;
only Neo4j uses the existing transactional double. The fixture deliberately
does not fabricate provenance for either machine or derived processing runs.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis, transcripts
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.database import SQLiteDatabase
from backend.tests.test_analysis import GraphDouble
from backend.tests.test_graph_nodes import validator


TOKEN = "F08D_PRIVATE_TOKEN"
OTHER_TOKEN = "F08D_OTHER_PRIVATE_TOKEN"
RAW_TEXT = "F08D_RAW_TRANSCRIPT: private machine speech."
CORRECTED_TEXT = "F08D_CORRECTED_TRANSCRIPT: private corrected speech from D-42."
REASON = "F08D_SENSITIVE_REASON: confidential source identity verified."
DIAGNOSTIC = "F08D_INTERNAL_SQL_DIAGNOSTIC: /private/transcripts.sqlite3"
AUDIT_FIELDS = {"id", "case_id", "actor_id", "action", "target_id", "created_at"}


class TranscriptAuditTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # The shared helper loads the supplied contract bundle, forbids extra
        # properties and checks UUID/date-time formats, rather than app models.
        cls.schemas = {name: validator(name) for name in (
            "AuditEvent", "AuditPage", "TranscriptRevision", "TranscriptRevisionPage",
            "ProcessingRun", "AnalysisRun", "ApiError")}

    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.enterContext(patch.object(analysis, "Neo4jGraphDatabase", return_value=GraphDouble()))
        self.app = create_app(self.root / "audit.sqlite3", storage_dir=self.root / "private",
            token_verifier=SyntheticTokenVerifier({TOKEN: "investigator-1", OTHER_TOKEN: "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app, raise_app_exceptions=False), base_url="http://test",
            headers={"Authorization": "Bearer " + TOKEN}))
        response = await self.client.post("/api/v1/cases", json={"title": "Synthetic F08D"})
        self.assertEqual(response.status_code, 201, response.text)
        self.case = response.json()["id"]
        self.base = f"/api/v1/cases/{self.case}"
        self.audit_url = self.base + "/audit-events"
        response = await self.client.post(self.base + "/evidence",
            data={"kind": "audio", "source_label": REASON},
            files={"file": (TOKEN + ".wav", RAW_TEXT.encode(), "audio/wav")})
        self.assertEqual(response.status_code, 201, response.text)
        self.evidence = response.json()
        self.run_id = str(uuid4())
        self.source = dict(id=str(uuid4()), case_id=self.case, evidence_id=self.evidence["id"],
            processing_run_id=self.run_id, kind="transcript.segment",
            source_locator="media:start_ms=0;end_ms=1000", raw_value=RAW_TEXT,
            normalized_value=RAW_TEXT, extraction_confidence=0.4)
        with self.app.state.database.connect() as connection:
            connection.execute(
                "INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,"
                "config_json,processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.run_id, self.case, self.evidence["id"], "investigator-1", str(uuid4()),
                 "synthetic-machine-fixture", "{}", "synthetic-asr-fixture/1",
                 "2026-01-01T00:00:00Z", "queued"))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (self.run_id,))
            connection.execute("INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)",
                (self.run_id, self.case, self.evidence["id"], json.dumps([self.source]), "[]", "[]", "[]"))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?",
                ("2026-01-01T00:00:00Z", self.run_id))
        self.url = self.base + f"/observations/{self.source['id']}/transcript-revisions"
        self.body = dict(processing_run_id=self.run_id, base_processing_run_id=self.run_id,
            expected_latest_revision_id=None, corrected_text=CORRECTED_TEXT, reason=REASON)

    def snapshot(self):
        with self.app.state.database.connect() as connection:
            return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                    for table in ("audit_events", "transcript_revisions", "processing_runs",
                                  "processing_outputs", "processing_provenance", "evidence")}

    def assert_private_safe(self, value):
        wire = json.dumps(value)
        for private in (RAW_TEXT, CORRECTED_TEXT, REASON, TOKEN, OTHER_TOKEN, DIAGNOSTIC,
                        str(self.root), "Bearer ", "Traceback", "storage_path", "corrected_text",
                        "raw_value", "normalized_value", "payload_json", "config_json"):
            self.assertNotIn(private, wire)

    def assert_utc_chronological(self, events):
        stamps = [datetime.fromisoformat(event["created_at"]) for event in events]
        for stamp in stamps:
            self.assertIsNotNone(stamp.tzinfo)
            self.assertEqual(stamp.utcoffset(), timedelta(0))
        self.assertEqual(stamps, sorted(stamps))

    async def audit_page(self, url=None, token=TOKEN, **params):
        response = await self.client.get(url or self.audit_url, params=params or {"limit": 100},
            headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        page = response.json()
        self.schemas["AuditPage"].validate(page)
        for event in page["items"]:
            self.schemas["AuditEvent"].validate(event)
            if event["action"] == "appendTranscriptRevision":
                self.assertEqual(set(event), AUDIT_FIELDS)
        self.assert_utc_chronological(page["items"])
        self.assert_private_safe(page)
        return page

    async def append(self, body=None, key=None, token=TOKEN):
        return await self.client.post(self.url, json=self.body if body is None else body,
            headers={"Idempotency-Key": key or str(uuid4()), "Authorization": "Bearer " + token})

    async def create_revision(self, body=None, token=TOKEN, **kwargs):
        before = self.snapshot()["audit_events"]
        response = await self.append(body, token=token, **kwargs)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        revision = response.json()
        self.schemas["TranscriptRevision"].validate(revision)
        actor = "investigator-1" if token == TOKEN else "investigator-2"
        self.assertEqual(revision["actor_id"], actor)
        after = self.snapshot()["audit_events"]
        self.assertTrue(all(event in after for event in before), "Existing history must remain unchanged")
        [stored] = [event for event in after if event not in before]
        expected = dict(id=stored["id"], case_id=self.case, actor_id=actor,
            action="appendTranscriptRevision", target_id=revision["id"], created_at=revision["created_at"])
        self.assertEqual(stored, dict(expected, reason=None))
        self.schemas["AuditEvent"].validate(expected)
        page = await self.audit_page()
        self.assertEqual(page["total"], len(after))
        [public] = [event for event in page["items"] if event["id"] == stored["id"]]
        self.assertEqual({key: value for key, value in public.items() if key != "created_at"},
                         {key: value for key, value in expected.items() if key != "created_at"})
        # HTTP datetime serialization can omit an all-zero fractional part.
        self.assertEqual(datetime.fromisoformat(public["created_at"]),
                         datetime.fromisoformat(revision["created_at"]))
        return revision, public

    def next_body(self, revision, **changes):
        return dict(self.body, base_processing_run_id=revision["derived_processing_run_id"],
                    expected_latest_revision_id=revision["id"], **changes)

    async def revision_page(self):
        response = await self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.schemas["TranscriptRevisionPage"].validate(response.json())
        return response.json()

    async def test_each_append_has_exact_actor_case_revision_and_monotonic_utc_timestamp(self):
        revisions, events = [], []
        body = self.body
        for _ in range(3):
            revision, event = await self.create_revision(body)
            revisions.append(revision)
            events.append(event)
            body = self.next_body(revision)
        self.assert_utc_chronological(events)
        page = await self.audit_page()
        self.assertEqual([item for item in page["items"] if item["action"] == "appendTranscriptRevision"], events)
        self.assertEqual((await self.revision_page())["items"], revisions)
        paginated = []
        for offset in range(page["total"]):
            part = await self.audit_page(limit=1, offset=offset)
            self.assertEqual((part["total"], part["limit"], part["offset"]), (page["total"], 1, offset))
            paginated.extend(part["items"])
        self.assertEqual(paginated, page["items"])
        self.assert_utc_chronological(paginated)

    async def test_member_grant_records_member_and_actor_scoped_replay_is_exactly_once(self):
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO case_members VALUES (?,?)", (self.case, "investigator-2"))
        key = str(uuid4())
        first, _ = await self.create_revision(key=key)
        second_body = self.next_body(first)
        second, _ = await self.create_revision(second_body, key=key, token=OTHER_TOKEN)
        before = self.snapshot()
        for token, body, expected in ((TOKEN, self.body, first), (OTHER_TOKEN, second_body, second)):
            with self.subTest(token=token):
                response = await self.append(body, key=key, token=token)
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(response.json(), expected)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(await self.audit_page(token=OTHER_TOKEN), await self.audit_page())

    async def test_private_transcript_and_correction_reason_are_absent_from_public_history(self):
        revision, _ = await self.create_revision()
        # Positive controls prove the sensitive values actually reached storage.
        self.assertEqual((revision["corrected_text"], revision["reason"]), (CORRECTED_TEXT, REASON))
        stored = next(row for row in self.snapshot()["processing_outputs"]
                      if row["run_id"] == revision["derived_processing_run_id"])
        derived = next(item for item in json.loads(stored["observations_json"])
                       if item["id"] == revision["derived_observation_id"])
        self.assertEqual((derived["raw_value"], derived["normalized_value"]), (RAW_TEXT, CORRECTED_TEXT))
        await self.audit_page()

    async def test_foreign_cases_and_unrelated_actor_cannot_observe_revision_events(self):
        revision, event = await self.create_revision()
        before = self.snapshot()
        for token in (TOKEN, OTHER_TOKEN):
            with self.subTest(token=token):
                response = await self.client.post("/api/v1/cases", json={"title": "Foreign F08D"},
                    headers={"Authorization": "Bearer " + token})
                self.assertEqual(response.status_code, 201, response.text)
                url = f"/api/v1/cases/{response.json()['id']}/audit-events"
                page = await self.audit_page(url, token=token)
                self.assertEqual((page["items"], page["total"]), ([], 0))
                self.assertNotIn(revision["id"], json.dumps(page))
                self.assertNotIn(event["id"], json.dumps(page))
        denied = await self.client.get(self.audit_url, headers={"Authorization": "Bearer " + OTHER_TOKEN})
        missing = await self.client.get(f"/api/v1/cases/{uuid4()}/audit-events",
            headers={"Authorization": "Bearer " + OTHER_TOKEN})
        self.assertEqual((denied.status_code, missing.status_code), (404, 404))
        self.schemas["ApiError"].validate(denied.json())
        self.assertEqual(denied.json(), missing.json())
        self.assert_private_safe(denied.json())
        self.assertEqual(self.snapshot(), before)

    async def test_stale_base_and_conflicting_replay_append_no_audit_or_revision(self):
        key = str(uuid4())
        await self.create_revision(key=key)
        before = self.snapshot()
        for body, request_key in ((self.body, str(uuid4())),
                                  (dict(self.body, reason=REASON + " changed"), key)):
            response = await self.append(body, key=request_key)
            self.assertEqual(response.status_code, 409, response.text)
            self.schemas["ApiError"].validate(response.json())
            self.assert_private_safe(response.json())
        self.assertEqual(self.snapshot(), before)
        await self.audit_page()

    async def test_clock_rollback_still_produces_nondecreasing_utc_audit_times(self):
        body, events = self.body, []
        # The second request's wall clock goes backwards; the base completion
        # time must keep the correction history monotonic and selectable.
        for stamp in ("2099-01-01T12:00:00Z", "2099-01-01T11:59:59Z", "2099-01-01T12:00:00.1Z"):
            with patch.object(transcripts, "datetime", wraps=datetime) as controlled_clock:
                controlled_clock.now.return_value = datetime.fromisoformat(stamp)
                revision, event = await self.create_revision(body)
            events.append(event)
            body = self.next_body(revision)
        self.assert_utc_chronological(events)
        self.assertEqual(len({event["created_at"] for event in events}), 3)
        self.assertEqual([event for event in (await self.audit_page())["items"]
                          if event["action"] == "appendTranscriptRevision"], events)

    async def test_derived_processing_run_links_to_persisted_processing_provenance(self):
        revision, _ = await self.create_revision()
        with self.app.state.database.connect() as connection:
            run = dict(connection.execute("SELECT * FROM processing_runs WHERE id=?",
                (revision["derived_processing_run_id"],)).fetchone())
            config = json.loads(run["config_json"])
            records = [dict(row) for row in connection.execute(
                "SELECT p.* FROM transcript_revisions t JOIN processing_runs r "
                "ON r.id=t.derived_processing_run_id AND r.case_id=t.case_id AND r.evidence_id=t.evidence_id "
                "JOIN processing_provenance p ON p.run_id=r.id AND p.case_id=r.case_id AND p.evidence_id=r.evidence_id "
                "WHERE t.id=?", (revision["id"],))]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["finished_at"], revision["created_at"])
        self.assertEqual(config["transcript_revision_id"], revision["id"])
        self.assertEqual(config["original_processing_run_id"], self.run_id)
        self.assertEqual(config["base_processing_run_id"], self.run_id)
        self.assertEqual(len(records), 1,
            "appendTranscriptRevision must persist processing_provenance for its derived run")
        self.assertEqual(records[0]["finished_at"], run["finished_at"])
        self.assertEqual(run["processor_version"], "transcript-correction/1")
        self.assertEqual(records[0]["record_version"], "processing-provenance/1")
        payload = json.loads(records[0]["payload_json"])
        self.assertEqual((payload["case_id"], payload["evidence_id"], payload["processing_run_id"]),
                         (self.case, self.evidence["id"], run["id"]))
        self.assertEqual(payload["record_version"], records[0]["record_version"])
        self.assertEqual(payload["input"], {key: self.evidence[key] for key in ("kind", "sha256", "size_bytes")})
        self.assertEqual(payload["execution"]["versions"]["processor_version"], run["processor_version"])
        self.assertEqual(payload["execution"]["versions"]["materializer_version"], config["materializer_version"])
        self.assertEqual((payload["accepted_at"], payload["finished_at"]), (run["created_at"], run["finished_at"]))
        output = next(row for row in self.snapshot()["processing_outputs"] if row["run_id"] == run["id"])
        for name, field in zip(("observation_ids", "entity_ids", "event_ids"), transcripts._OUTPUTS):
            self.assertEqual(payload["outputs"][name], sorted(item["id"] for item in json.loads(output[field])))
        digest_input = json.dumps({field: output[field] for field in transcripts._OUTPUTS},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(payload["output_sha256"], hashlib.sha256(digest_input).hexdigest())
        self.assert_private_safe(payload)
        before = self.snapshot()
        for statement in (
                "UPDATE processing_provenance SET payload_json='{}' WHERE run_id=?",
                "DELETE FROM processing_provenance WHERE run_id=?",
                "INSERT OR REPLACE INTO processing_provenance SELECT * FROM processing_provenance WHERE run_id=?"):
            with self.subTest(statement=statement), self.app.state.database.connect() as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement, (run["id"],))
        self.assertEqual(self.snapshot(), before)

    async def start_analysis(self, key=None):
        response = await self.client.post(self.base + "/analysis-runs",
            headers={"Idempotency-Key": key or str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        response = await self.client.get(self.base + "/analysis-runs/" + response.json()["id"])
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        self.schemas["AnalysisRun"].validate(run)
        self.assertEqual(run["status"], "completed", run)
        await self.audit_page()
        return run

    async def test_subsequent_analysis_selects_derived_run_and_preserves_prior_snapshot(self):
        key = str(uuid4())
        original = await self.start_analysis(key)
        before = self.snapshot()
        revision, _ = await self.create_revision()
        response = await self.client.get(
            self.base + f"/evidence/{self.evidence['id']}/processing-runs/{revision['derived_processing_run_id']}")
        self.assertEqual(response.status_code, 200, response.text)
        self.schemas["ProcessingRun"].validate(response.json())
        self.assertEqual(response.json()["status"], "completed")
        corrected = await self.start_analysis()
        self.assertEqual(corrected["trigger"], "new_observations")
        self.assertEqual(corrected["input_snapshot"]["processing_run_ids"], [revision["derived_processing_run_id"]])
        self.assertIn(revision["derived_observation_id"], corrected["input_snapshot"]["observation_ids"])
        self.assertNotIn(self.source["id"], corrected["input_snapshot"]["observation_ids"])
        self.assertEqual(original["input_snapshot"]["processing_run_ids"], [self.run_id])
        self.assertIn(self.source["id"], original["input_snapshot"]["observation_ids"])
        self.assertNotEqual(original["input_snapshot"]["sha256"], corrected["input_snapshot"]["sha256"])
        self.assertEqual(await self.start_analysis(key), original)
        for table in ("processing_runs", "processing_outputs", "processing_provenance", "evidence"):
            for row in before[table]:
                self.assertIn(row, self.snapshot()[table])

    async def test_database_failures_roll_back_revision_output_run_provenance_and_audit(self):
        first, _ = await self.create_revision()
        for stage in ("run_insert", "output_insert", "provenance_insert", "provenance_missing",
                      "revision_insert", "completion_update", "audit_insert", "commit"):
            with self.subTest(stage=stage):
                before = self.snapshot()
                page_before = await self.audit_page()
                body = self.next_body(first, reason=REASON + " " + stage)
                pending = []
                if stage == "commit":
                    original_connect = SQLiteDatabase.connect

                    @contextmanager
                    def fail_commit(database):
                        with original_connect(database) as connection:
                            yield connection
                            revision = connection.execute("SELECT * FROM transcript_revisions WHERE reason=?",
                                (body["reason"],)).fetchone()
                            if revision is not None:
                                run_id = revision["derived_processing_run_id"]
                                pending.append((
                                    connection.execute("SELECT status FROM processing_runs WHERE id=?", (run_id,)).fetchone()[0],
                                    connection.execute("SELECT count(*) FROM processing_outputs WHERE run_id=?", (run_id,)).fetchone()[0],
                                    connection.execute("SELECT count(*) FROM processing_provenance WHERE run_id=?", (run_id,)).fetchone()[0],
                                    connection.execute("SELECT count(*) FROM audit_events WHERE action=? AND target_id=?",
                                        ("appendTranscriptRevision", revision["id"])).fetchone()[0]))
                                # All publications exist before the unit of work
                                # fails, proving rollback after audit insertion.
                                raise sqlite3.OperationalError(DIAGNOSTIC)

                    failure = patch.object(SQLiteDatabase, "connect", fail_commit)
                else:
                    table = {"run_insert": "processing_runs", "output_insert": "processing_outputs",
                             "provenance_insert": "processing_provenance", "provenance_missing": "processing_provenance",
                             "revision_insert": "transcript_revisions", "completion_update": "processing_runs",
                             "audit_insert": "audit_events"}[stage]
                    operation = "UPDATE OF status" if stage == "completion_update" else "INSERT"
                    condition = "WHEN NEW.status='completed' " if stage == "completion_update" else ""
                    rejection = "RAISE(IGNORE)" if stage == "provenance_missing" else f"RAISE(ABORT, '{DIAGNOSTIC}')"
                    with self.app.state.database.connect() as connection:
                        connection.execute(f"CREATE TRIGGER f08d_reject BEFORE {operation} ON {table} "
                            f"{condition}BEGIN SELECT {rejection}; END")

                    @contextmanager
                    def reject_insert():
                        try:
                            yield
                        finally:
                            with self.app.state.database.connect() as connection:
                                connection.execute("DROP TRIGGER f08d_reject")

                    failure = reject_insert()
                with failure:
                    response = await self.append(body)
                self.assertEqual(response.status_code, 500, response.text)
                self.assertEqual(response.text, "Internal Server Error")
                self.assert_private_safe(response.text)
                if stage == "commit":
                    self.assertEqual(pending, [("completed", 1, 1, 1)])
                self.assertEqual(self.snapshot(), before,
                    "Failed correction must leave no orphan audit, revision, run, output or provenance")
                self.assertEqual(await self.audit_page(), page_before)
                self.assertEqual((await self.revision_page())["items"], [first])
        await self.create_revision(self.next_body(first))


if __name__ == "__main__":
    unittest.main()
