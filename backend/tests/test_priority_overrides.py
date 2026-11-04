"""U09 HTTP/SQLite overrides against real triage and the contract bundle."""

import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import overrides
from backend.tests import test_analysis as lifecycle
from backend.tests.test_graph_nodes import validator


class PriorityOverrideTests(unittest.IsolatedAsyncioTestCase):
    # Share the real processing/analysis harness and its explicit Neo4j double.
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll

    @classmethod
    def setUpClass(cls):
        cls.override_schema = validator("PriorityOverride")
        cls.error_schema = validator("ApiError")

    def override_url(self, evidence_id, case_id=None):
        return (f"/api/v1/cases/{case_id or self.case}/evidence/{evidence_id}"
                "/priority-overrides")

    async def create(self, evidence_id, priority="P1", reason="Follow up this source.", **kwargs):
        response = await self.client.post(self.override_url(evidence_id),
            json={"priority": priority, "reason": reason}, **kwargs)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        result = response.json()
        self.override_schema.validate(result)
        self.assertEqual(result["case_id"], self.case)
        self.assertEqual(result["evidence_id"], evidence_id)
        self.assertEqual((result["priority"], result["reason"]), (priority, reason))
        return result

    async def triage(self, params=None):
        response = await self.client.get(self.base + "/triage", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        validator("TriagePage").validate(response.json())
        return response.json()

    async def history(self, evidence_id):
        response = await self.client.get(self.base + f"/evidence/{evidence_id}/triage-history")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def stored_records(self):
        with self.app.state.database.connect() as connection:
            return tuple([dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                         for table in ("priority_overrides", "audit_events"))

    def automated_records(self):
        with self.app.state.database.connect() as connection:
            return tuple([dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {key}")]
                         for table, key in (("analysis_runs", "id"), ("analysis_outputs", "run_id")))

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.error_schema.validate(response.json())
        code, message = {
            400: ("INVALID_INPUT", "Invalid request input."),
            401: ("UNAUTHORIZED", "Authentication required."),
            404: ("NOT_FOUND", "Resource not found."),
        }[status]
        self.assertEqual(response.json(), {"code": code, "message": message})

    async def test_each_priority_band_and_exact_reason_round_trip_without_analysis(self):
        evidence, _ = await self.upload(process=False)
        created = []
        for priority in ("P1", "P2", "P3", "P4"):
            with self.subTest(priority=priority):
                result = await self.create(evidence["id"], priority, "  Human rationale: café\nfollow up.  ")
                self.assertEqual(result["actor_id"], "investigator-1")
                created.append(result)
                page = await self.triage()
                self.assertEqual(page["items"], [dict(evidence_id=evidence["id"],
                    override=result, effective_priority=priority)])
        stored, _ = self.stored_records()
        self.assertEqual({row["id"] for row in stored}, {row["id"] for row in created})
        self.assertEqual(await self.history(evidence["id"]), [])

    async def test_latest_override_preserves_all_history_scores_results_and_pinned_order(self):
        evidence, _ = await self.upload()
        await self.upload("gps.csv", "gps")
        run = await self.poll(await self.start())
        self.assertEqual(run["status"], "completed")
        original = await self.triage({"analysis_run_id": run["id"]})
        history = await self.history(evidence["id"])
        automated = self.automated_records()
        target = next(item for item in original["items"] if item["evidence_id"] == evidence["id"])
        different = "P4" if target["latest_result"]["priority"] != "P4" else "P1"
        first = await self.create(evidence["id"], different)
        second = await self.create(evidence["id"], "P2", "New information.")
        third = await self.create(evidence["id"], "P2", "New information.")
        for params in (None, {"analysis_run_id": run["id"]}):
            page = await self.triage(params)
            expected = [dict(item, override=third, effective_priority="P2")
                        if item["evidence_id"] == evidence["id"] else item
                        for item in original["items"]]
            self.assertEqual(page["items"], expected)
            updated = next(item for item in page["items"] if item["evidence_id"] == evidence["id"])
            self.assertEqual(updated["latest_result"], target["latest_result"])
            self.assertEqual(updated["latest_result"]["score"], target["latest_result"]["score"])
        self.assertEqual(await self.history(evidence["id"]), history)
        self.assertEqual(self.automated_records(), automated)
        stored, events = self.stored_records()
        self.assertEqual({row["id"] for row in stored}, {first["id"], second["id"], third["id"]})
        self.assertEqual(len([event for event in events if event["action"] == "setPriorityOverride"]), 3)

    async def test_audit_records_authenticated_actor_case_target_reason_and_time(self):
        evidence, _ = await self.upload(process=False)
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO case_members VALUES (?, ?)", (self.case, "investigator-2"))
        result = await self.create(evidence["id"], "P3", "Verify against the original source.",
                                  headers={"Authorization": "Bearer other"})
        self.assertEqual(result["actor_id"], "investigator-2")
        response = await self.client.get(self.base + "/audit-events", params={"limit": 100})
        self.assertEqual(response.status_code, 200, response.text)
        validator("AuditPage").validate(response.json())
        [event] = [event for event in response.json()["items"] if event["action"] == "setPriorityOverride"]
        self.assertEqual(event, dict(id=event["id"], case_id=self.case, actor_id="investigator-2",
            action="setPriorityOverride", target_id=evidence["id"], reason=result["reason"],
            created_at=result["created_at"]))

    async def test_invalid_bodies_queries_and_paths_are_safe_400_without_writes(self):
        evidence, _ = await self.upload(process=False)
        url = self.override_url(evidence["id"])
        before = self.stored_records()
        valid = {"priority": "P1", "reason": "SYNTHETIC_PRIVATE_REASON"}
        bodies = [{}, {"priority": "P1"}, {"reason": "Reason"}, None, [], "private"]
        bodies += [dict(valid, priority=value) for value in
                   ("P0", "P5", "p1", " P1 ", "", None, 1, True, [], {})]
        bodies += [dict(valid, reason=value) for value in
                   ("", " ", "\n\t", "\u2003", None, 1, True, [], {})]
        bodies += [dict(valid, **{field: "SYNTHETIC_PRIVATE_VALUE"}) for field in
                   ("actor_id", "case_id", "evidence_id", "id", "created_at", "unknown")]
        for body in bodies:
            with self.subTest(body=body):
                self.assert_error(await self.client.post(url, json=body), 400)
        for query in ("extra=private", "priority=P1", "reason=private", "extra=1&extra=2"):
            self.assert_error(await self.client.post(url + "?" + query, json=valid), 400)
        self.assert_error(await self.client.post(url, content='{"priority":',
                         headers={"Content-Type": "application/json"}), 400)
        for bad_url in (self.override_url("bad"), self.override_url(evidence["id"], "bad")):
            self.assert_error(await self.client.post(bad_url, json=valid), 400)
        self.assertEqual(self.stored_records(), before)

    async def test_missing_and_foreign_resources_are_404_without_writes(self):
        evidence, _ = await self.upload(process=False)
        other = (await self.client.post("/api/v1/cases", json={"title": "Other owned case"})).json()["id"]
        before = self.stored_records()
        body = {"priority": "P1", "reason": "Reason"}
        for url in (self.override_url(str(uuid4())), self.override_url(evidence["id"], other),
                    self.override_url(evidence["id"], str(uuid4()))):
            self.assert_error(await self.client.post(url, json=body), 404)
        self.assert_error(await self.client.post(self.override_url(evidence["id"]), json=body,
                         headers={"Authorization": "Bearer other"}), 404)
        self.assertEqual(self.stored_records(), before)

    async def test_missing_or_invalid_authentication_is_401_without_writes(self):
        evidence, _ = await self.upload(process=False)
        before = self.stored_records()
        for authorization in (None, "bad", "Bearer unknown", "Bearer local extra"):
            request = self.client.build_request("POST", self.override_url(evidence["id"]),
                json={"priority": "P1", "reason": "Reason"})
            request.headers.pop("Authorization", None)
            if authorization is not None:
                request.headers["Authorization"] = authorization
            response = await self.client.send(request)
            self.assert_error(response, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertEqual(self.stored_records(), before)

    async def test_audit_failure_rolls_back_override_and_audit_preserving_prior_records(self):
        evidence, _ = await self.upload(process=False)
        first = await self.create(evidence["id"])
        before = self.stored_records()
        record = overrides.record_audit_event

        def fail_after_audit(*args, **kwargs):
            record(*args, **kwargs)
            raise sqlite3.IntegrityError("Synthetic audit failure")

        with patch.object(overrides, "record_audit_event", side_effect=fail_after_audit):
            with self.assertRaises(sqlite3.IntegrityError):
                await self.client.post(self.override_url(evidence["id"]),
                    json={"priority": "P4", "reason": "Later decision"})
        self.assertEqual(self.stored_records(), before)
        self.assertEqual((await self.triage())["items"][0]["override"], first)

    async def test_initialization_is_idempotent_and_preserves_records(self):
        evidence, _ = await self.upload(process=False)
        await self.create(evidence["id"])
        before = self.stored_records()
        overrides.initialize_overrides(self.app.state.database)
        overrides.initialize_overrides(self.app.state.database)
        self.assertEqual(self.stored_records(), before)
        with self.app.state.database.connect() as connection:
            self.assertEqual([row["name"] for row in connection.execute(
                "PRAGMA index_info(idx_priority_overrides)")],
                ["case_id", "evidence_id", "created_at", "id"])

    def test_operation_has_contract_operation_id(self):
        operation = self.app.openapi()["paths"][
            "/api/v1/cases/{caseId}/evidence/{evidenceId}/priority-overrides"]["post"]
        self.assertEqual(operation["operationId"], "setPriorityOverride")
        self.assertIn("201", operation["responses"])
