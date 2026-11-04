"""F08C audit regressions: real HTTP, SQLite, processing and analysis.

Only Neo4j uses the existing transactional double. Audit producers and reads
remain real, including SQLite failures before insertion and before commit.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend import analysis, overrides, reviews
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.database import SQLiteDatabase
from backend.tests.test_analysis import GraphDouble
from backend.tests.test_graph_nodes import validator


TOKEN = "F08C_PRIVATE_TOKEN"
OTHER_TOKEN = "F08C_OTHER_PRIVATE_TOKEN"
PASSWORD = "F08C_RAW_PASSWORD"
DIAGNOSTIC = "F08C_INTERNAL_SQL_DIAGNOSTIC: database /private/audit.sqlite3"
SAFE_FIELDS = {"id", "case_id", "actor_id", "action", "target_id", "reason", "created_at"}


class ReviewOverrideAuditTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Use the bundled OpenAPI schemas, including additionalProperties=false
        # and date-time/UUID format checking; never substitute an app schema.
        cls.schemas = {name: validator(name) for name in
                       ("AuditEvent", "AuditPage", "ReviewDecision", "PriorityOverride", "ApiError")}

    async def asyncSetUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.neo = GraphDouble()
        self.enterContext(patch.object(analysis, "Neo4jGraphDatabase", return_value=self.neo))
        self.app = create_app(self.root / "audit.sqlite3", storage_dir=self.root / "private",
            token_verifier=SyntheticTokenVerifier({TOKEN: "investigator-1", OTHER_TOKEN: "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app, raise_app_exceptions=False),
            base_url="http://test", headers={"Authorization": "Bearer " + TOKEN}))
        response = await self.client.post("/api/v1/cases", json={"title": "Synthetic F08C"})
        self.assertEqual(response.status_code, 201, response.text)
        self.case = response.json()["id"]
        self.base = f"/api/v1/cases/{self.case}"
        self.audit_url = self.base + "/audit-events"
        self.pipeline_events = []
        self.evidence = []
        source = (Path(__file__).resolve().parents[2] / "fixtures/synthetic-case/network.csv").read_bytes()
        # Private source content and metadata are positive controls for leaks.
        source = source.replace(b"connected", PASSWORD.encode())
        for _ in range(2):
            response = await self.client.post(self.base + "/evidence",
                data={"kind": "network_log", "source_label": TOKEN},
                files={"file": (PASSWORD + ".csv", source, "text/csv")})
            self.assertEqual(response.status_code, 201, response.text)
            evidence = response.json()
            self.evidence.append(evidence)
            self.pipeline_events.append(self.expected_event("uploadEvidence", evidence["id"], evidence["created_at"]))
            path = self.base + f"/evidence/{evidence['id']}/processing-runs"
            run = await self.completed_run(path)
            self.pipeline_events.append(self.expected_event("startProcessing", evidence["id"], run["finished_at"],
                f"run:{run['id']};status:completed;version:{run['processor_version']}"))
        run = await self.completed_run(self.base + "/analysis-runs")
        self.pipeline_events.append(self.expected_event("startAnalysis", run["id"], run["finished_at"],
            f"run:{run['id']};status:completed;version:{run['algorithm_version']}"))
        response = await self.client.get(self.base + "/findings")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["items"], "Real completed analysis must supply a reviewable finding")
        self.finding = response.json()["items"][0]["id"]
        self.operations = {
            "reviewFinding": dict(url=self.base + f"/findings/{self.finding}/reviews",
                table="finding_reviews", schema="ReviewDecision", field="decision", value="accepted",
                target=self.finding),
            "setPriorityOverride": dict(url=self.base + f"/evidence/{self.evidence[0]['id']}/priority-overrides",
                table="priority_overrides", schema="PriorityOverride", field="priority", value="P1",
                target=self.evidence[0]["id"]),
        }

    async def completed_run(self, path):
        response = await self.client.post(path, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        # ASGITransport awaits the real background task before returning.
        response = await self.client.get(path + "/" + response.json()["id"])
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        self.assertEqual(run["status"], "completed", run)
        return run

    def expected_event(self, action, target, timestamp, reason=None, actor="investigator-1"):
        event = dict(case_id=self.case, actor_id=actor, action=action, target_id=target, created_at=timestamp)
        if reason is not None:
            event["reason"] = reason
        return event

    def stored_records(self):
        with self.app.state.database.connect() as connection:
            return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                    for table in ("audit_events", "finding_reviews", "priority_overrides")}

    def assert_utc_chronological(self, items):
        timestamps = [datetime.fromisoformat(item["created_at"]) for item in items]
        for timestamp in timestamps:
            self.assertIsNotNone(timestamp.tzinfo)
            self.assertEqual(timestamp.utcoffset(), timedelta(0))
        self.assertEqual(timestamps, sorted(timestamps))

    def assert_safe(self, value):
        wire = json.dumps(value)
        for private in (TOKEN, OTHER_TOKEN, PASSWORD, DIAGNOSTIC, str(self.root),
                        "Bearer ", "Traceback", "sqlite3.", "storage_path", "password", "access_token"):
            self.assertNotIn(private, wire)

    async def audit_page(self, url=None, token=TOKEN, **params):
        response = await self.client.get(url or self.audit_url,
            headers={"Authorization": "Bearer " + token}, params=params or {"limit": 100})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        page = response.json()
        self.schemas["AuditPage"].validate(page)
        for event in page["items"]:
            self.schemas["AuditEvent"].validate(event)
            self.assertLessEqual(set(event), SAFE_FIELDS)
        self.assert_utc_chronological(page["items"])
        self.assert_safe(page)
        return page

    async def create_decision(self, action, reason="Human source verification.", value=None, token=TOKEN):
        operation = self.operations[action]
        before = self.stored_records()["audit_events"]
        response = await self.client.post(operation["url"],
            headers={"Authorization": "Bearer " + token},
            json={operation["field"]: value or operation["value"], "reason": reason})
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.schemas[operation["schema"]].validate(result)
        actor = "investigator-1" if token == TOKEN else "investigator-2"
        self.assertEqual(result["actor_id"], actor)
        after = self.stored_records()["audit_events"]
        self.assertTrue(all(event in after for event in before), "Prior audit history must remain unchanged")
        [stored] = [event for event in after if event not in before]
        expected = self.expected_event(action, operation["target"], result["created_at"], reason, actor)
        self.assertEqual(stored, dict(id=stored["id"], **expected))
        page = await self.audit_page()
        self.assertEqual(page["total"], len(after))
        self.assertIn(stored, page["items"])
        return result, stored

    async def test_review_appends_each_decision_with_exact_grant_target_reason_and_utc_time(self):
        created, events = [], []
        for decision in ("accepted", "rejected", "needs_investigation"):
            result, event = await self.create_decision("reviewFinding", value=decision,
                reason=f"  Review {decision}: café\nverify the original source.  ")
            created.append(result)
            events.append(event)
        self.assert_utc_chronological(created)
        items = (await self.audit_page())["items"]
        self.assertEqual([event for event in items if event["action"] == "reviewFinding"], events)
        response = await self.client.get(self.operations["reviewFinding"]["url"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), created)

    async def test_override_appends_each_priority_with_exact_grant_target_reason_and_utc_time(self):
        created, events = [], []
        for priority in ("P1", "P2", "P3", "P4"):
            result, event = await self.create_decision("setPriorityOverride", value=priority,
                reason=f"  Override {priority}: café\nnew source context.  ")
            created.append(result)
            events.append(event)
        self.assert_utc_chronological(created)
        items = (await self.audit_page())["items"]
        self.assertEqual([event for event in items if event["action"] == "setPriorityOverride"], events)

    async def test_shared_member_actions_record_the_member_rather_than_case_owner(self):
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO case_members VALUES (?, ?)", (self.case, "investigator-2"))
        for action in self.operations:
            with self.subTest(action=action):
                await self.create_decision(action, token=OTHER_TOKEN)
        owner = await self.audit_page()
        member = await self.audit_page(token=OTHER_TOKEN)
        self.assertEqual(member, owner)

    async def test_foreign_cases_and_actors_cannot_observe_review_or_override_events(self):
        for action in self.operations:
            await self.create_decision(action, reason="Case A human decision.")
        before = self.stored_records()
        for token in (TOKEN, OTHER_TOKEN):
            with self.subTest(token=token):
                response = await self.client.post("/api/v1/cases", json={"title": "Foreign synthetic case"},
                    headers={"Authorization": "Bearer " + token})
                self.assertEqual(response.status_code, 201, response.text)
                foreign_url = f"/api/v1/cases/{response.json()['id']}/audit-events"
                page = await self.audit_page(foreign_url, token=token)
                self.assertEqual((page["items"], page["total"]), ([], 0))
        denied = await self.client.get(self.audit_url, headers={"Authorization": "Bearer " + OTHER_TOKEN})
        missing = await self.client.get(f"/api/v1/cases/{uuid4()}/audit-events",
            headers={"Authorization": "Bearer " + OTHER_TOKEN})
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.schemas["ApiError"].validate(denied.json())
        self.assertEqual(denied.json(), missing.json())
        self.assert_safe(denied.json())
        self.assertEqual(self.stored_records(), before)

    async def test_combined_history_contains_every_producer_in_chronological_order_across_pages(self):
        expected = list(self.pipeline_events)
        for action in ("reviewFinding", "setPriorityOverride", "reviewFinding", "setPriorityOverride"):
            _, event = await self.create_decision(action)
            expected.append({key: value for key, value in event.items() if key != "id"})
        page = await self.audit_page()
        self.assertEqual(page["total"], len(expected))
        self.assertEqual([{key: value for key, value in event.items() if key != "id"}
                          for event in page["items"]], expected)
        self.assertEqual({event["action"] for event in page["items"]},
            {"uploadEvidence", "startProcessing", "startAnalysis", "reviewFinding", "setPriorityOverride"})
        paginated = []
        for offset in range(0, len(expected), 2):
            part = await self.audit_page(limit=2, offset=offset)
            self.assertEqual((part["total"], part["limit"], part["offset"]), (len(expected), 2, offset))
            paginated.extend(part["items"])
        self.assertEqual(paginated, page["items"])
        self.assertEqual(len({event["id"] for event in paginated}), len(expected))
        self.assert_utc_chronological(paginated)
        stored = self.stored_records()["audit_events"]
        self.assertEqual(sorted(page["items"], key=lambda event: event["id"]),
            [{key: value for key, value in event.items() if value is not None} for event in stored])

    async def test_mixed_whole_and_fractional_review_override_times_sort_chronologically(self):
        events = []
        # Insert out of order, including a tie, to catch string/time ordering
        # regressions independently of normal wall-clock request ordering.
        stamps = ("2099-01-01T12:00:00.1Z", "2099-01-01T12:00:00Z",
                  "2099-01-01T12:00:00.000001Z", "2099-01-01T12:00:00Z")
        for index, stamp in enumerate(stamps):
            action, module = ("reviewFinding", reviews) if index % 2 == 0 else ("setPriorityOverride", overrides)
            with patch.object(module, "datetime", wraps=datetime) as controlled_clock:
                controlled_clock.now.return_value = datetime.fromisoformat(stamp)
                _, event = await self.create_decision(action, reason=f"Ordering control {index}.")
                events.append(event)
        items = (await self.audit_page())["items"]
        human = [event for event in items if event["action"] in self.operations]
        self.assertEqual(human, sorted(events, key=lambda event:
            (datetime.fromisoformat(event["created_at"]), event["id"])))

    async def assert_rollback(self, action):
        operation = self.operations[action]
        first, _ = await self.create_decision(action, reason="Committed decision before failure.")
        for stage in ("decision_insert", "audit_insert", "commit"):
            with self.subTest(stage=stage):
                before = self.stored_records()
                page_before = await self.audit_page()
                reason = f"Uncommitted {action} {stage}."
                observed_pending = []
                if stage == "commit":
                    original_connect = SQLiteDatabase.connect

                    @contextmanager
                    def fail_commit(database):
                        with original_connect(database) as connection:
                            yield connection
                            decision_count = connection.execute(
                                f"SELECT count(*) FROM {operation['table']} WHERE reason=?", (reason,)).fetchone()[0]
                            if decision_count:
                                audit_count = connection.execute(
                                    "SELECT count(*) FROM audit_events WHERE action=? AND reason=?",
                                    (action, reason)).fetchone()[0]
                                observed_pending.append((decision_count, audit_count))
                                # Raising at the unit-of-work boundary exercises
                                # rollback after BOTH real inserts have happened.
                                raise sqlite3.OperationalError(DIAGNOSTIC)

                    failure = patch.object(SQLiteDatabase, "connect", fail_commit)
                else:
                    table = operation["table"] if stage == "decision_insert" else "audit_events"
                    with self.app.state.database.connect() as connection:
                        connection.execute(f"CREATE TRIGGER f08c_reject BEFORE INSERT ON {table} "
                            f"BEGIN SELECT RAISE(ABORT, '{DIAGNOSTIC}'); END")

                    @contextmanager
                    def reject_insert():
                        try:
                            yield
                        finally:
                            with self.app.state.database.connect() as connection:
                                connection.execute("DROP TRIGGER f08c_reject")

                    failure = reject_insert()
                with failure:
                    response = await self.client.post(operation["url"],
                        json={operation["field"]: operation["value"], "reason": reason})
                self.assertEqual(response.status_code, 500, response.text)
                self.assertEqual(response.text, "Internal Server Error")
                self.assert_safe(response.text)
                if stage == "commit":
                    self.assertEqual(observed_pending, [(1, 1)])
                self.assertEqual(self.stored_records(), before,
                    "Failed transaction must preserve decisions and audits without orphan events")
                self.assertEqual(await self.audit_page(), page_before)
                if action == "reviewFinding":
                    response = await self.client.get(operation["url"])
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json(), [first])
                else:
                    response = await self.client.get(self.base + "/triage")
                    self.assertEqual(response.status_code, 200, response.text)
                    target = next(item for item in response.json()["items"]
                                  if item["evidence_id"] == operation["target"])
                    self.assertEqual(target["override"], first)
        # Recovery succeeds after faults are removed and appends one event.
        await self.create_decision(action, reason="Committed decision after recovery.")

    async def test_review_database_failures_roll_back_decision_and_audit_without_orphans(self):
        await self.assert_rollback("reviewFinding")

    async def test_override_database_failures_roll_back_decision_and_audit_without_orphans(self):
        await self.assert_rollback("setPriorityOverride")


if __name__ == "__main__":
    unittest.main()
