"""A16/U10 real HTTP, SQLite and processing outputs against the shared contract."""

import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.audit import record_audit_event
from backend.questions import RETRIEVAL_VERSION


ROOT = Path(__file__).resolve().parents[2]


class QuestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_follow_up_uses_prior_question_but_rejects_unbounded_dialogue(self):
        first=(await self.client.post(self.url,json={'question':'D-7'})).json()
        self.assertTrue(first['supported'])
        response=await self.client.post(self.url,json={'question':'Which records mention it?',
            'conversation':[dict(question=first['question'],answer=first['answer'])]})
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['supported'])
        for conversation in [[dict(question='x',answer='y')]*9,[dict(question='x',answer='y'*8001)]]:
            rejected=await self.client.post(self.url,json={'question':'Follow up','conversation':conversation})
            self.assertEqual(rejected.status_code,400,rejected.text)

    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.app = create_app(root / "questions.sqlite3", storage_dir=root / "private",
            token_verifier=SyntheticTokenVerifier({
                "questions-one": "investigator-1", "questions-two": "investigator-2",
            }))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.app.state.qa_model = ""  # Explicit offline extraction mode for retrieval contract tests.
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
            headers={"Authorization": "Bearer questions-one"},
        ))
        self.bundle = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())
        self.case = await self.new_case()
        self.url = f"/api/v1/cases/{self.case}/questions"
        self.network = await self.upload()
        self.run = await self.process(self.network)

    async def new_case(self):
        response = await self.client.post("/api/v1/cases", json={"title": "Synthetic grounded inquiry"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    async def upload(self, kind="network_log", data=None, case=None):
        if data is None:
            name = {"network_log": "network.csv", "gps": "gps.csv", "message": "messages.csv"}[kind]
            data = (ROOT / "fixtures/synthetic-case" / name).read_bytes()
        response = await self.client.post(f"/api/v1/cases/{case or self.case}/evidence",
            data={"kind": kind, "source_label": "Synthetic questions source"},
            files={"file": ("source.csv", data, "text/csv")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def process(self, evidence):
        response = await self.client.post(
            f"/api/v1/cases/{evidence['case_id']}/evidence/{evidence['id']}/processing-runs",
            headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def stored_observations(self, run=None):
        with self.app.state.database.connect() as connection:
            row = connection.execute("SELECT observations_json FROM processing_outputs WHERE run_id=?",
                                     ((run or self.run)["id"],)).fetchone()
        return json.loads(row["observations_json"])

    def inquiries(self):
        with self.app.state.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM audit_events WHERE action='askCaseQuestion' ORDER BY created_at,id")]

    def validate(self, name, value):
        Draft202012Validator({"$ref": "#/components/schemas/" + name,
                              "components": self.bundle["components"]},
                             format_checker=FormatChecker()).validate(value)

    async def ask(self, question, case=None):
        response = await self.client.post(
            f"/api/v1/cases/{case or self.case}/questions", json={"question": question})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        body = response.json()
        self.validate("CaseAnswer", body)
        self.assertEqual(body["question"], question)
        self.assertEqual(body["case_id"], case or self.case)
        self.assertEqual(body["retrieval_version"], "case-context-retrieval/2")
        return body

    def assert_supported(self, body, expected):
        self.assertIs(body["supported"], True)
        self.assertTrue(body["answer"].startswith("Here’s what the matching records say:"))
        expected = sorted(expected, key=lambda item: (item["evidence_id"], item["id"]))
        self.assertEqual([citation["observation_id"] for citation in body["citations"]],
                         [item["id"] for item in expected])
        self.assertGreaterEqual(len(body["citations"]), 1)
        for citation, item in zip(body["citations"], expected):
            self.validate("AnswerCitation", citation)
            self.assertEqual(citation["evidence_id"], item["evidence_id"])
            self.assertEqual(citation["source_locator"], item["source_locator"])
            self.assertIn(citation["claim"], body["answer"])
            self.assertEqual(citation["claim"],
                f"{item['kind']} records {json.dumps(item['normalized_value'], ensure_ascii=False)}.")

    def assert_unsupported(self, body):
        self.assertIs(body["supported"], False)
        self.assertEqual(body["citations"], [])
        expected = "There aren’t any processed records to search yet. Upload and process evidence, then ask me about it." if body['answer_status']=='no_evidence' else "I couldn’t find enough evidence to answer that. Try a specific file, identifier or time."
        self.assertEqual(body['answer'], expected)

    def test_operation_matches_contract(self):
        path = "/api/v1/cases/{caseId}/questions"
        self.assertEqual(self.bundle["paths"][path]["post"]["operationId"], "askCaseQuestion")
        self.assertEqual(self.app.openapi()["paths"][path]["post"]["operationId"], "askCaseQuestion")
        self.assertEqual(RETRIEVAL_VERSION, "case-context-retrieval/2")

    async def test_supported_identifier_casefold_and_exact_source_citations(self):
        observations = self.stored_observations()
        for device in ("D-7", "D-9"):
            with self.subTest(device=device):
                question = f"  What evidence mentions {device.lower()}?  "
                self.validate("CaseQuestion", {"question": question})
                body = await self.ask(question)
                self.assert_supported(body, [item for item in observations if item["normalized_value"] == device])

    async def test_ip_address_prefix_and_connected_keyword(self):
        observations = self.stored_observations()
        for question, values in (("203.0.113.7", {"203.0.113.7"}),
                                 ("203.0.113", {"203.0.113.7", "203.0.113.9"}),
                                 ("What was connected?", {"connected"})):
            with self.subTest(question=question):
                self.assert_supported(await self.ask(question),
                    [item for item in observations if item["normalized_value"] in values])

    async def test_gps_message_and_d8_use_actual_processing_outputs(self):
        gps = await self.upload("gps")
        gps_run = await self.process(gps)
        message = await self.upload("message")
        message_run = await self.process(message)
        gps_observations = self.stored_observations(gps_run)
        message_observations = self.stored_observations(message_run)
        self.assert_supported(await self.ask("What GPS evidence is recorded?"), gps_observations)
        self.assert_supported(await self.ask("Show message evidence"), message_observations)
        self.assert_supported(await self.ask("What mentions D-8?"),
            [item for item in gps_observations + message_observations if "D-8" in item["normalized_value"]])

    async def test_unknown_identifiers_do_not_fall_back_to_generic_keywords(self):
        for question in ("Was D-70 connected?", "D-99", "203.0.113.70", "203.0.11", "astronomy",
                         "What is the evidence?", "???"):
            with self.subTest(question=question):
                self.assert_unsupported(await self.ask(question))

    async def test_identity_guilt_and_perpetrator_questions_abstain_despite_matching_values(self):
        for question in ("Is D-7 guilty?", "Does D-7 establish guilt?", "Who used D-7?",
                         "Establish the identity behind D-7", "Identify D-7",
                         "Is D-7 the perpetrator?", "Is D-7 innocent?",
                         "Whose device is D-7?", "Was D-7 responsible?", "Who was connected?",
                         "Is D-7 the attacker?", "Does D-7 belong to Alex?", "Show the owner of D-7"):
            with self.subTest(question=question):
                self.assert_unsupported(await self.ask(question))

    async def test_contract_rejects_wrong_citation_cardinality_and_incomplete_citations(self):
        supported = await self.ask("D-7")
        with self.assertRaises(ValidationError):
            self.validate("CaseAnswer", dict(supported, citations=[]))
        unsupported = await self.ask("Who used D-7?")
        with self.assertRaises(ValidationError):
            self.validate("CaseAnswer", dict(unsupported, citations=supported["citations"]))
        citation = supported["citations"][0]
        for required in ("claim", "evidence_id", "source_locator"):
            with self.assertRaises(ValidationError):
                self.validate("AnswerCitation", {key: value for key, value in citation.items() if key != required})
        self.validate("AnswerCitation", {key: value for key, value in citation.items() if key != "observation_id"})

    async def test_same_snapshot_question_is_deterministic(self):
        first = await self.ask("203.0.113")
        second = await self.ask("203.0.113")
        self.assertNotEqual(first.pop("provenance_id"), second.pop("provenance_id"))
        self.assertEqual(first, second)
        self.assertEqual(len(self.inquiries()), 2)

    async def test_supported_and_unsupported_audit_events_are_readable_and_do_not_store_question(self):
        await self.ask("D-7")
        await self.ask("Who used D-7? PRIVATE_QUESTION")
        events = self.inquiries()
        self.assertEqual(len(events), 2)
        self.assertEqual([event["reason"] for event in events],
                         ["Grounded inquiry (supported)", "Grounded inquiry (unsupported)"])
        for event in events:
            self.assertEqual((event["action"], event["target_id"], event["case_id"], event["actor_id"]),
                             ("askCaseQuestion", self.case, self.case, "investigator-1"))
            self.assertNotIn("PRIVATE_QUESTION", json.dumps(event))
        response = await self.client.get(f"/api/v1/cases/{self.case}/audit-events", params={"limit": 100})
        self.assertEqual(response.status_code, 200, response.text)
        self.validate("AuditPage", response.json())
        self.assertEqual({event["id"] for event in events},
                         {event["id"] for event in response.json()["items"] if event["action"] == "askCaseQuestion"})

    async def test_authorized_cases_cannot_retrieve_each_others_observations(self):
        other_case = await self.new_case()
        other_evidence = await self.upload(case=other_case,
            data=b"timestamp,device_id,ip_address,event\n2026-01-12T10:00:00Z,D-55,198.51.100.55,private-marker\n")
        other_run = await self.process(other_evidence)
        self.assert_unsupported(await self.ask("D-55"))
        self.assert_unsupported(await self.ask("private-marker"))
        self.assert_unsupported(await self.ask("D-7", case=other_case))
        self.assert_supported(await self.ask("D-55", case=other_case),
            [item for item in self.stored_observations(other_run) if item["normalized_value"] == "D-55"])
        body = await self.ask("connected")
        self.assertNotIn(other_evidence["id"], json.dumps(body))
        self.assertNotIn(other_case, json.dumps(body))

    async def test_unauthenticated_foreign_missing_and_revoked_access_have_no_audit(self):
        async with AsyncClient(transport=ASGITransport(self.app), base_url="http://test") as client:
            for headers in ({}, {"Authorization": "invalid"}, {"Authorization": "Bearer rejected"},
                            [("Authorization", "Bearer questions-one")] * 2):
                response = await client.post(self.url, headers=headers, json={"question": "D-7"})
                self.assertEqual(response.status_code, 401, response.text)
                self.validate("ApiError", response.json())
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
        foreign = await self.client.post(self.url, headers={"Authorization": "Bearer questions-two"},
                                         json={"question": "D-7"})
        missing = await self.client.post(self.url.replace(self.case, str(uuid4())), json={"question": "D-7"})
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual((foreign.content, foreign.headers), (missing.content, missing.headers))
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM case_members WHERE case_id=?", (self.case,))
        response = await self.client.post(self.url, json={"question": "D-7"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.inquiries(), [])

    async def test_invalid_bodies_paths_and_unknown_queries_return_safe_400_without_audit(self):
        for body in ({}, {"question": ""}, {"question": " \t\n"}, {"question": "x" * 2001},
                     {"question": 123}, {"question": True}, {"question": None}, {"question": []},
                     {"question": "D-7", "actor_id": "PRIVATE_INPUT"}, ["PRIVATE_INPUT"]):
            with self.subTest(body=body):
                response = await self.client.post(self.url, json=body)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json(), {"code": "INVALID_INPUT", "message": "Invalid request input."})
                self.validate("ApiError", response.json())
        for params in ({"case_id": str(uuid4())}, {"question": "D-7"}, {"PRIVATE_INPUT": "secret"},
                       [("limit", "1"), ("limit", "2")]):
            response = await self.client.post(self.url, params=params, json={"question": "D-7"})
            self.assertEqual(response.status_code, 400)
            self.validate("ApiError", response.json())
            self.assertNotIn("PRIVATE_INPUT", response.text)
        for url, kwargs in ((self.url, {"content": '{"question": PRIVATE_INPUT'}),
                            (self.url, {}),
                            (self.url.replace(self.case, "PRIVATE_INPUT"), {"json": {"question": "D-7"}})):
            response = await self.client.post(url, **kwargs)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("PRIVATE_INPUT", response.text)
        self.assertEqual(self.inquiries(), [])

    async def test_valid_length_boundaries(self):
        for question in ("x", "x" * 2000):
            self.assert_unsupported(await self.ask(question))

    async def test_empty_case_unprocessed_and_empty_latest_output_abstain(self):
        empty_case = await self.new_case()
        await self.upload(case=empty_case)
        self.assert_unsupported(await self.ask("D-7", case=empty_case))
        self.completed_fixture("2099-01-12T00:00:00Z", 1, [])
        self.assert_unsupported(await self.ask("D-7"))

    def completed_fixture(self, finished_at, integer_id, observations=None):
        """Controlled selection metadata over real output; no processing claim."""
        run_id = str(UUID(int=integer_id))
        values = [dict(item, id=str(uuid4()), processing_run_id=run_id)
                  for item in (self.stored_observations() if observations is None else observations)]
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,"
                "config_json,processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, self.case, self.network["id"], "investigator-1", str(uuid4()), "selection-fixture",
                 "{}", "question-selection-fixture/1", "2099-01-01T00:00:00Z", "queued"))
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            connection.execute("INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)",
                (run_id, self.case, self.network["id"], json.dumps(values), "[]", "[]", "[]"))
            connection.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?",
                               (finished_at, run_id))
        return values

    async def test_latest_completed_per_evidence_utc_precision_and_uuid_tie(self):
        gps_run = await self.process(await self.upload("gps"))
        self.completed_fixture("2099-01-12T10:00:00.0000000001Z", 100)
        later = self.completed_fixture("2099-01-12T10:00:00.0000000002Z", 1)
        self.assert_supported(await self.ask("D-7"),
            [item for item in later + self.stored_observations(gps_run) if item["normalized_value"] == "D-7"])
        self.completed_fixture("2099-01-12T16:30:00.1+05:30", 2)
        tie_winner = self.completed_fixture("2099-01-12T11:00:00.1000Z", 101)
        self.assert_supported(await self.ask("D-9"),
            [item for item in tie_winner if item["normalized_value"] == "D-9"])

    async def test_pending_partial_and_failed_runs_never_replace_completed_sources(self):
        before = await self.ask("D-7")
        with patch("backend.processing.process_run"):
            await self.process(self.network)  # queued
            running = await self.process(self.network)
        with self.app.state.database.connect() as connection:
            connection.execute("UPDATE processing_runs SET status='running' WHERE id=?", (running["id"],))
            partial = [dict(item, id=str(uuid4()), processing_run_id=running["id"])
                       for item in self.stored_observations()]
            connection.execute("INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)",
                (running["id"], self.case, self.network["id"], json.dumps(partial), "[]", "[]", "[]"))
        with patch("backend.processing.publish_outputs", side_effect=RuntimeError("Synthetic failure")):
            await self.process(self.network)
        after = await self.ask("D-7")
        self.assertEqual({k: v for k, v in after.items() if k != "provenance_id"},
                         {k: v for k, v in before.items() if k != "provenance_id"})

    async def test_retrieval_searches_beyond_first_observation_page(self):
        rows = b"timestamp,device_id,ip_address,event\n" + b"".join(
            f"2026-01-12T10:00:00Z,D-{index},203.0.113.7,connected\n".encode() for index in range(100, 140))
        run = await self.process(await self.upload(data=rows))
        self.assert_supported(await self.ask("What was connected?"),
            [item for item in self.stored_observations() + self.stored_observations(run)
             if item["normalized_value"] == "connected"])

    async def test_corrupt_selected_output_fails_closed_without_audit_or_fallback(self):
        original = self.stored_observations()
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TRIGGER processing_output_update")
        for corrupt in ("PRIVATE_CORRUPTION", "{}", json.dumps(original + [original[0]]),
                        json.dumps([dict(original[0], case_id=str(uuid4()))]),
                        json.dumps([dict(original[0], evidence_id=str(uuid4()))]),
                        json.dumps([dict(original[0], processing_run_id=str(uuid4()))]),
                        json.dumps([dict(original[0], source_locator="")])):
            with self.app.state.database.connect() as connection:
                connection.execute("UPDATE processing_outputs SET observations_json=? WHERE run_id=?",
                                   (corrupt, self.run["id"]))
            response = await self.client.post(self.url, json={"question": "D-7"})
            self.assertEqual(response.status_code, 404, response.text)
            self.assertNotIn("PRIVATE_CORRUPTION", response.text)
        self.assertEqual(self.inquiries(), [])

    async def test_missing_latest_output_fails_closed_without_stale_fallback(self):
        latest = await self.process(self.network)
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TRIGGER processing_output_delete")
            connection.execute("DELETE FROM processing_outputs WHERE run_id=?", (latest["id"],))
        response = await self.client.post(self.url, json={"question": "D-7"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.inquiries(), [])

    async def test_audit_write_failure_cannot_return_unaudited_success(self):
        def fail_after_insert(*args, **kwargs):
            record_audit_event(*args, **kwargs)
            raise sqlite3.OperationalError("Synthetic audit failure")

        with patch("backend.questions.record_audit_event", side_effect=fail_after_insert):
            async with AsyncClient(transport=ASGITransport(self.app, raise_app_exceptions=False),
                                   base_url="http://test", headers=self.client.headers) as client:
                response = await client.post(self.url, json={"question": "D-7"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.inquiries(), [])


if __name__ == "__main__":
    unittest.main()
