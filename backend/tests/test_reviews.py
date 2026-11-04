"""U08 HTTP/SQLite reviews using real findings and an explicit Neo4j double."""

import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import analysis, reviews
from backend.tests import test_analysis as lifecycle
from backend.tests.test_graph_nodes import validator


class ReviewTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the HTTP/SQLite/processing harness without inheriting its test cases.
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll

    @classmethod
    def setUpClass(cls):
        cls.review_schema = validator("ReviewDecision")
        cls.error_schema = validator("ApiError")

    async def populate(self):
        await self.upload()
        await self.upload()
        run = await self.poll(await self.start())
        self.assertEqual(run["status"], "completed", run)
        response = await self.client.get(self.base + "/findings")
        self.assertEqual(response.status_code, 200, response.text)
        self.findings = response.json()["items"]
        self.assertGreater(len(self.findings), 1)
        self.finding_id = self.findings[0]["id"]
        self.url = self.review_url(self.finding_id)

    def review_url(self, finding_id, case_id=None):
        return f"/api/v1/cases/{case_id or self.case}/findings/{finding_id}/reviews"

    async def create(self, decision="accepted", reason="Source supports the finding.", **kwargs):
        response = await self.client.post(self.url, json={"decision": decision, "reason": reason}, **kwargs)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        result = response.json()
        self.review_schema.validate(result)
        self.assertEqual(result["case_id"], self.case)
        self.assertEqual(result["finding_id"], self.finding_id)
        self.assertEqual((result["decision"], result["reason"]), (decision, reason))
        return result

    async def history(self, url=None):
        response = await self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        items = response.json()
        self.assertIsInstance(items, list)
        for item in items:
            self.review_schema.validate(item)
        return items

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.error_schema.validate(response.json())
        code, message = {
            400: ("INVALID_INPUT", "Invalid request input."),
            401: ("UNAUTHORIZED", "Authentication required."),
            404: ("NOT_FOUND", "Resource not found."),
        }[status]
        self.assertEqual(response.json(), {"code": code, "message": message})

    def stored_records(self):
        with self.app.state.database.connect() as connection:
            return tuple([dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
                         for table in ("finding_reviews", "audit_events"))

    async def test_each_decision_and_exact_reason_round_trip(self):
        await self.populate()
        created = []
        for decision in ("accepted", "rejected", "needs_investigation"):
            with self.subTest(decision=decision):
                result = await self.create(decision, "  Human rationale: café\nfollow up.  ")
                self.assertEqual(result["actor_id"], "investigator-1")
                created.append(result)
        self.assertEqual(await self.history(), created)

    async def test_existing_finding_without_reviews_returns_empty_array_without_audit(self):
        await self.populate()
        before = self.stored_records()
        self.assertEqual(await self.history(), [])
        self.assertEqual(self.stored_records(), before)

    async def test_multiple_reviews_append_and_duplicate_requests_preserve_history(self):
        await self.populate()
        first = await self.create()
        second = await self.create("rejected", "Later source contradicts the finding.")
        third = await self.create("rejected", "Later source contradicts the finding.")
        self.assertEqual(len({item["id"] for item in (first, second, third)}), 3)
        self.assertEqual(await self.history(), [first, second, third])
        stored, events = self.stored_records()
        self.assertEqual({row["id"] for row in stored}, {first["id"], second["id"], third["id"]})
        self.assertEqual(len([event for event in events if event["action"] == "reviewFinding"]), 3)

    async def test_chronological_order_handles_fractional_times_offsets_and_id_ties(self):
        await self.populate()
        stamps = {
            5: "2026-11-04T12:00:00.100001Z",
            4: "2026-11-04T12:00:00Z",
            3: "2026-11-04T13:00:00.000000+01:00",
            2: "2026-11-04T12:00:00.000001Z",
            1: "2026-11-04T12:00:00.1Z",
        }
        ids = {number: f"00000000-0000-4000-8000-{number:012d}" for number in stamps}
        with self.app.state.database.connect() as connection:
            for number, stamp in stamps.items():
                # Explicit storage fixture for ordering; no history mutation.
                connection.execute("INSERT INTO finding_reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ids[number], self.case, self.finding_id, "investigator-1", "accepted", "Synthetic", stamp))
        self.assertEqual([item["id"] for item in await self.history()],
                         [ids[number] for number in (3, 4, 2, 1, 5)])

    async def test_audit_has_authenticated_actor_case_target_reason_and_matching_time(self):
        await self.populate()
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO case_members VALUES (?, ?)", (self.case, "investigator-2"))
        result = await self.create("needs_investigation", "Verify against the original source.",
                                   headers={"Authorization": "Bearer other"})
        self.assertEqual(result["actor_id"], "investigator-2")
        response = await self.client.get(self.base + "/audit-events", params={"limit": 100})
        self.assertEqual(response.status_code, 200, response.text)
        validator("AuditPage").validate(response.json())
        [event] = [event for event in response.json()["items"] if event["action"] == "reviewFinding"]
        self.assertEqual(event, dict(id=event["id"], case_id=self.case, actor_id="investigator-2",
            action="reviewFinding", target_id=self.finding_id, reason=result["reason"], created_at=result["created_at"]))
        self.assertEqual(await self.history(), [result])

    async def test_invalid_bodies_are_safe_400_and_do_not_append(self):
        await self.populate()
        before = self.stored_records()
        valid = {"decision": "accepted", "reason": "SYNTHETIC_PRIVATE_REASON"}
        bodies = [{}, {"decision": "accepted"}, {"reason": "Reason"}, None, [], "private"]
        bodies += [dict(valid, decision=value) for value in
                   ("invalid-private-decision", "Accepted", " accepted ", "", None, 1, True, [])]
        bodies += [dict(valid, reason=value) for value in ("", " ", "\n\t", "\u2003", None, 1, True, [])]
        bodies += [dict(valid, **{field: "SYNTHETIC_PRIVATE_VALUE"})
                   for field in ("actor_id", "case_id", "finding_id", "id", "created_at", "unknown")]
        for body in bodies:
            with self.subTest(body=body):
                self.assert_error(await self.client.post(self.url, json=body), 400)
        for content in (b'{"decision":', b''):
            self.assert_error(await self.client.post(self.url, content=content,
                              headers={"Content-Type": "application/json"}), 400)
        self.assertEqual(self.stored_records(), before)

    async def test_unknown_query_parameters_are_safe_400_for_both_operations(self):
        await self.populate()
        before = self.stored_records()
        for query in ("unknown=private", "limit=1", "offset=0", f"analysis_run_id={uuid4()}",
                      "reason=private&reason=other", "private="):
            for method in ("GET", "POST"):
                with self.subTest(method=method, query=query):
                    kwargs = {"json": {"decision": "accepted", "reason": "Reason"}} if method == "POST" else {}
                    self.assert_error(await self.client.request(method, self.url + "?" + query, **kwargs), 400)
        self.assertEqual(self.stored_records(), before)

    async def test_malformed_path_ids_are_safe_400(self):
        for url in (self.review_url("private-invalid-finding"), self.review_url(uuid4(), "private-invalid-case")):
            for method in ("GET", "POST"):
                kwargs = {"json": {"decision": "accepted", "reason": "Reason"}} if method == "POST" else {}
                self.assert_error(await self.client.request(method, url, **kwargs), 400)

    async def test_missing_foreign_case_and_foreign_finding_are_indistinguishable_404(self):
        await self.populate()
        await self.create()
        other_case = (await self.client.post("/api/v1/cases", json={"title": "Other owned case"})).json()["id"]
        before = self.stored_records()
        for url, headers in (
            (self.review_url(uuid4()), {}),
            (self.review_url(self.finding_id, other_case), {}),
            (self.review_url(self.finding_id, uuid4()), {}),
            (self.url, {"Authorization": "Bearer other"}),
        ):
            for method in ("GET", "POST"):
                kwargs = {"json": {"decision": "accepted", "reason": "Reason"}} if method == "POST" else {}
                self.assert_error(await self.client.request(method, url, headers=headers, **kwargs), 404)
        self.assertEqual(self.stored_records(), before)

    async def test_reviews_are_scoped_to_the_finding(self):
        await self.populate()
        first = await self.create()
        other_url = self.review_url(self.findings[1]["id"])
        self.assertEqual(await self.history(other_url), [])
        response = await self.client.post(other_url, json={"decision": "rejected", "reason": "Other finding"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(await self.history(), [first])
        self.assertEqual(await self.history(other_url), [response.json()])

    async def test_historical_finding_remains_reviewable_after_new_analysis(self):
        await self.populate()
        first = await self.create()
        new_run = await self.poll(await self.start())
        self.assertEqual(new_run["status"], "completed")
        latest = (await self.client.get(self.base + "/findings")).json()
        self.assertNotIn(self.finding_id, {finding["id"] for finding in latest["items"]})
        second = await self.create("needs_investigation", "Review of the earlier snapshot.")
        self.assertEqual(await self.history(), [first, second])

    async def test_unpublished_and_failed_analysis_findings_are_not_reviewable(self):
        await self.upload()
        await self.upload()
        with patch.object(analysis, "run_analysis_job"):
            run = await self.start()

        def crash():
            raise SystemExit("Synthetic crash after graph commit")

        self.neo.after_commit = crash
        self.app.state.graph_database = self.neo
        with self.assertRaises(SystemExit):
            analysis.process_analysis_run(self.app, run["id"])
        self.neo.after_commit = None
        with self.app.state.database.connect() as connection:
            output = connection.execute("SELECT findings_json FROM analysis_outputs WHERE run_id=?", (run["id"],)).fetchone()
        findings = json.loads(output["findings_json"])
        self.assertTrue(findings)
        url = self.review_url(findings[0]["id"])
        for status in ("running", "failed"):
            if status == "failed":
                with self.app.state.database.connect() as connection:
                    connection.execute("UPDATE analysis_runs SET status='failed', finished_at=?, error='ANALYSIS_FAILED' WHERE id=?",
                                       ("2026-11-04T12:00:00Z", run["id"]))
            self.assert_error(await self.client.get(url), 404)
            self.assert_error(await self.client.post(url, json={"decision": "accepted", "reason": "Reason"}), 404)
        self.assertEqual(self.stored_records()[0], [])

    async def test_authentication_failures_are_401_without_echoing_tokens(self):
        await self.populate()
        before = self.stored_records()
        for authorization in (None, "Bearer SYNTHETIC_PRIVATE_TOKEN", "Basic SYNTHETIC_PRIVATE_TOKEN", "Bearer"):
            for method in ("GET", "POST"):
                kwargs = {"json": {"decision": "accepted", "reason": "Reason"}} if method == "POST" else {}
                request = self.client.build_request(method, self.url, **kwargs)
                request.headers.pop("Authorization", None)
                if authorization is not None:
                    request.headers["Authorization"] = authorization
                response = await self.client.send(request)
                self.assert_error(response, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", response.text)
        self.assertEqual(self.stored_records(), before)

    async def test_audit_failure_rolls_back_the_review_and_prior_history_survives(self):
        await self.populate()
        first = await self.create()
        before = self.stored_records()
        with patch.object(reviews, "record_audit_event", side_effect=sqlite3.IntegrityError("Synthetic audit failure")):
            with self.assertRaises(sqlite3.IntegrityError):
                await self.client.post(self.url, json={"decision": "rejected", "reason": "Reason"})
        self.assertEqual(self.stored_records(), before)
        self.assertEqual(await self.history(), [first])

    async def test_storage_rejects_update_delete_replace_and_upsert(self):
        await self.populate()
        await self.create()
        before = self.stored_records()
        for statement in (
            "UPDATE finding_reviews SET reason='Changed'",
            "DELETE FROM finding_reviews",
            "INSERT OR REPLACE INTO finding_reviews SELECT * FROM finding_reviews",
            "INSERT OR REPLACE INTO finding_reviews (id, case_id, finding_id, actor_id, decision, reason, created_at, rowid) "
            "SELECT 'replacement', case_id, finding_id, actor_id, decision, reason, created_at, rowid FROM finding_reviews",
            "INSERT INTO finding_reviews SELECT * FROM finding_reviews WHERE 1 ON CONFLICT(id) DO UPDATE SET reason='Changed'",
        ):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                with self.app.state.database.connect() as connection:
                    connection.execute(statement)
        self.assertEqual(self.stored_records(), before)

    async def test_initialization_is_idempotent_and_preserves_existing_reviews(self):
        await self.populate()
        first = await self.create()
        before = self.stored_records()
        reviews.initialize_reviews(self.app.state.database)
        reviews.initialize_reviews(self.app.state.database)
        self.assertEqual(self.stored_records(), before)
        self.assertEqual(await self.history(), [first])

    def test_review_operations_have_contract_operation_ids(self):
        operations = self.app.openapi()["paths"]["/api/v1/cases/{caseId}/findings/{findingId}/reviews"]
        self.assertEqual(operations["post"]["operationId"], "reviewFinding")
        self.assertEqual(operations["get"]["operationId"], "listFindingReviews")
