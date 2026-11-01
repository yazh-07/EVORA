"""F09 operation-level M1 access/error matrix with real producers and storage."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend import audit, cases, evidence
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier


# This is the complete current M1 operation inventory, not a parallel wire schema.
# Paths/methods/statuses are checked against the actual routers and shared bundle.
OPERATIONS = {
    "createCase": ("POST", "/api/v1/cases", 201, "Case"),
    "listCases": ("GET", "/api/v1/cases", 200, "CasePage"),
    "getCase": ("GET", "/api/v1/cases/{caseId}", 200, "Case"),
    "uploadEvidence": ("POST", "/api/v1/cases/{caseId}/evidence", 201, "Evidence"),
    "listEvidence": ("GET", "/api/v1/cases/{caseId}/evidence", 200, "EvidencePage"),
    "getEvidence": ("GET", "/api/v1/cases/{caseId}/evidence/{evidenceId}", 200, "Evidence"),
    "downloadEvidence": ("GET", "/api/v1/cases/{caseId}/evidence/{evidenceId}/content", 200, None),
    "listAuditEvents": ("GET", "/api/v1/cases/{caseId}/audit-events", 200, "AuditPage"),
}
SCOPED = tuple(name for name, (_, path, _, _) in OPERATIONS.items() if "{caseId}" in path)
RESOURCE_SCOPED = ("getEvidence", "downloadEvidence")
LISTS = ("listCases", "listEvidence", "listAuditEvents")
TOKEN_A, TOKEN_B = "f09-synthetic-a", "f09-synthetic-b"
TABLES = ("cases", "case_members", "evidence", "audit_events", "intake_provenance")


class M1AccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.storage = root / "private"
        self.app = create_app(root / "m1.sqlite3", storage_dir=self.storage,
            token_verifier=SyntheticTokenVerifier({TOKEN_A: "investigator-1", TOKEN_B: "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(transport=ASGITransport(self.app), base_url="http://test"))
        self.spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())
        self.validators = {}
        self.content = Path("fixtures/synthetic-case/network.csv").read_bytes()
        self.case_a, self.case_a2, self.case_b = await self.new_case(TOKEN_A), await self.new_case(TOKEN_A), await self.new_case(TOKEN_B)
        self.contents = {self.case_a: self.content, self.case_a2: b"Synthetic other authorized original\x00",
                         self.case_b: b"SYNTHETIC_PRIVATE_OTHER_ACTOR_ORIGINAL\x00\xff"}
        self.evidence_a = await self.new_evidence(self.case_a, TOKEN_A)
        self.evidence_a2 = await self.new_evidence(self.case_a2, TOKEN_A)
        self.evidence_b = await self.new_evidence(self.case_b, TOKEN_B)
        self.missing_case, self.missing_evidence = str(uuid4()), str(uuid4())
        self.initial_state = self.snapshot()

    async def new_case(self, token):
        response = await self.client.post("/api/v1/cases", headers={"Authorization": "Bearer " + token},
                                          json={"title": "Synthetic F09 case"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    async def new_evidence(self, case_id, token):
        response = await self.call("uploadEvidence", case_id=case_id, token=token,
            files={"file": ("SYNTHETIC_PRIVATE_FILENAME.bin", self.contents[case_id], "application/octet-stream")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    async def call(self, operation, *, case_id=None, evidence_id=None, token=TOKEN_A, headers=None, **overrides):
        method, path, _, _ = OPERATIONS[operation]
        url = path.replace("{caseId}", case_id or self.case_a)
        url = url.replace("{evidenceId}", evidence_id or getattr(self, "evidence_a", "unused-synthetic-id"))
        kwargs = {}
        if operation == "createCase":
            kwargs["json"] = {"title": "Synthetic F09 new case"}
        elif operation == "uploadEvidence":
            kwargs.update(data={"kind": "network_log", "source_label": "SYNTHETIC_PRIVATE_SOURCE"},
                          files={"file": ("SYNTHETIC_PRIVATE_FILENAME.csv", self.content, "text/csv")})
        kwargs.update(overrides)
        if headers is None:
            headers = {"Authorization": "Bearer " + token} if token is not None else {}
        return await self.client.request(method, url, headers=headers, **kwargs)

    def snapshot(self):
        with self.app.state.database.connect() as connection:
            state = {name: sorted(tuple(row) for row in connection.execute(f"SELECT * FROM {name}")) for name in TABLES}
        state["private_files"] = {str(path.relative_to(self.storage)): path.read_bytes() for path in self.storage.rglob("*.bin")}
        return state

    def validate(self, schema, body):
        if schema not in self.validators:
            self.validators[schema] = Draft202012Validator(
                {**self.spec["components"]["schemas"][schema], "components": self.spec["components"]},
                format_checker=FormatChecker())
        self.validators[schema].validate(body)

    def assert_denied(self, operation, response, status):
        method, path, _, _ = OPERATIONS[operation]
        self.assertIn(str(status), self.spec["paths"][path][method.lower()]["responses"])
        self.assertEqual(response.status_code, status, response.text)
        self.validate("ApiError", response.json())
        code, message = {
            400: ("INVALID_INPUT", "Invalid request input."),
            401: ("UNAUTHORIZED", "Authentication required."),
            404: ("NOT_FOUND", "Resource not found."),
        }[status]
        self.assertEqual(response.json(), {"code": code, "message": message})
        self.assertEqual(response.headers["content-type"], "application/json")
        for private in (TOKEN_A, TOKEN_B, self.case_b, self.evidence_b, "SYNTHETIC_PRIVATE", str(self.storage)):
            self.assertNotIn(private, response.text)
        self.assertEqual(self.snapshot(), self.initial_state, "Denied request changed data/history/originals")

    def test_matrix_matches_every_current_m1_router_operation_and_contract(self):
        actual = {(route.operation_id, method, route.path)
                  for router in (cases.router, evidence.router, audit.router)
                  for route in router.routes for method in route.methods}
        expected = {(name, details[0], details[1]) for name, details in OPERATIONS.items()}
        self.assertEqual(actual, expected, "A M1 route needs an explicit access/error matrix entry")
        for name, (method, path, status, _) in OPERATIONS.items():
            operation = self.spec["paths"][path][method.lower()]
            self.assertEqual(operation["operationId"], name)
            self.assertIn(str(status), operation["responses"])

    async def test_authorized_baselines_use_real_api_schema_hash_and_audit(self):
        for token, case_id, evidence_id, own_cases in (
            (TOKEN_A, self.case_a, self.evidence_a, {self.case_a, self.case_a2}),
            (TOKEN_B, self.case_b, self.evidence_b, {self.case_b}),
        ):
            for operation, (_, _, status, schema) in OPERATIONS.items():
                if operation == "createCase":
                    continue  # Case-creation actor ownership has its own positive below.
                with self.subTest(operation=operation, actor=token):
                    response = await self.call(operation, token=token, case_id=case_id, evidence_id=evidence_id)
                    self.assertEqual(response.status_code, status, response.text if schema else "download failed")
                    if schema:
                        self.validate(schema, response.json())
                    else:
                        self.assertEqual(response.content, self.contents[case_id])
                        self.assertEqual(hashlib.sha256(response.content).hexdigest(), hashlib.sha256(self.contents[case_id]).hexdigest())
                    if operation == "listCases":
                        self.assertEqual({item["id"] for item in response.json()["items"]}, own_cases)
                    elif operation in ("listAuditEvents", "listEvidence"):
                        self.assertTrue(all(item["case_id"] == case_id for item in response.json()["items"]))
                        if operation == "listAuditEvents":
                            self.assertTrue(any(item["target_id"] == evidence_id for item in response.json()["items"]))
                    elif operation == "getCase":
                        self.assertEqual(response.json()["id"], case_id)
                    elif operation == "getEvidence":
                        self.assertEqual((response.json()["case_id"], response.json()["id"]), (case_id, evidence_id))

    async def test_create_case_membership_belongs_to_authenticated_actor(self):
        response = await self.call("createCase")
        self.assertEqual(response.status_code, 201)
        self.validate("Case", response.json())
        new_id = response.json()["id"]
        with self.app.state.database.connect() as connection:
            self.assertEqual([tuple(row) for row in connection.execute(
                "SELECT case_id, actor_id FROM case_members WHERE case_id = ?", (new_id,))],
                [(new_id, "investigator-1")])
        denied = await self.call("getCase", case_id=new_id, token=TOKEN_B)
        self.assertEqual(denied.status_code, 404)
        self.validate("ApiError", denied.json())

    async def test_every_operation_rejects_missing_identity_without_side_effects(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assert_denied(operation, await self.call(operation, token=None), 401)

    async def test_every_operation_rejects_invalid_malformed_and_duplicate_identity(self):
        for operation in OPERATIONS:
            for headers in ({"Authorization": "Bearer synthetic-rejected"}, {"Authorization": "Basic synthetic"},
                            [("Authorization", "Bearer " + TOKEN_A), ("Authorization", "Bearer " + TOKEN_B)]):
                with self.subTest(operation=operation, headers=headers):
                    self.assert_denied(operation, await self.call(operation, headers=headers), 401)

    async def test_all_case_routes_have_identical_foreign_and_missing_denials_for_both_actors(self):
        for token, foreign_case, foreign_evidence in ((TOKEN_A, self.case_b, self.evidence_b),
                                                     (TOKEN_B, self.case_a, self.evidence_a)):
            for operation in SCOPED:
                with self.subTest(operation=operation, actor=token):
                    foreign = await self.call(operation, case_id=foreign_case, evidence_id=foreign_evidence, token=token)
                    missing = await self.call(operation, case_id=self.missing_case, evidence_id=foreign_evidence, token=token)
                    self.assert_denied(operation, foreign, 404)
                    self.assert_denied(operation, missing, 404)
                    self.assertEqual((foreign.content, foreign.headers), (missing.content, missing.headers))

    async def test_resource_reads_reject_cross_case_ids_even_when_actor_is_member_of_both(self):
        for operation in RESOURCE_SCOPED:
            for wrong_id in (self.evidence_a2, self.evidence_b):
                with self.subTest(operation=operation, resource=wrong_id):
                    mismatch = await self.call(operation, evidence_id=wrong_id)
                    missing = await self.call(operation, evidence_id=self.missing_evidence)
                    self.assert_denied(operation, mismatch, 404)
                    self.assert_denied(operation, missing, 404)
                    self.assertEqual((mismatch.content, mismatch.headers), (missing.content, missing.headers))

    async def test_all_case_routes_recheck_membership_after_revocation(self):
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM case_members WHERE case_id = ? AND actor_id = ?", (self.case_a, "investigator-1"))
        self.initial_state = self.snapshot()
        for operation in SCOPED:
            with self.subTest(operation=operation):
                self.assert_denied(operation, await self.call(operation), 404)
        page = (await self.call("listCases")).json()
        self.assertEqual({item["id"] for item in page["items"]}, {self.case_a2})

    async def test_replaced_synthetic_verifier_rejects_old_token_on_every_route(self):
        self.app.state.token_verifier = SyntheticTokenVerifier({TOKEN_B: "investigator-2"})
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                self.assert_denied(operation, await self.call(operation), 401)

    async def test_all_uuid_paths_use_shared_400_without_echoing_submitted_values(self):
        for operation in SCOPED:
            with self.subTest(operation=operation):
                self.assert_denied(operation, await self.call(operation, case_id="SYNTHETIC_PRIVATE_BAD_CASE"), 400)
        for operation in RESOURCE_SCOPED:
            with self.subTest(operation=operation):
                self.assert_denied(operation, await self.call(operation, evidence_id="SYNTHETIC_PRIVATE_BAD_EVIDENCE"), 400)

    async def test_collection_routes_do_not_accept_forged_actor_or_case_ownership(self):
        # These two collection operations have no case-ID path; do not invent a
        # nonexistent-ID response or claim that a new case is someone else's.
        for body in ({"title": "Synthetic", "actor_id": "investigator-2"},
                     {"title": "Synthetic", "id": self.case_b},
                     {"title": "Synthetic", "case_id": self.case_b}):
            self.assert_denied("createCase", await self.call("createCase", json=body), 400)
        response = await self.call("listCases", params={"actor_id": "investigator-2", "case_id": self.case_b})
        self.validate("CasePage", response.json())
        self.assertEqual({item["id"] for item in response.json()["items"]}, {self.case_a, self.case_a2})
        self.assertEqual(self.snapshot(), self.initial_state)

    async def test_declared_body_and_pagination_errors_are_safe_and_have_no_effect(self):
        for body in ({}, {"title": " "}, {"title": "x" * 201}, {"title": 123}):
            self.assert_denied("createCase", await self.call("createCase", json=body), 400)
        self.assert_denied("uploadEvidence", await self.call("uploadEvidence", data={"kind": "invalid", "source_label": "Synthetic"}), 400)
        for operation in LISTS:
            for params in ({"limit": 0}, {"limit": 101}, {"limit": "not-an-integer"}, {"offset": -1}):
                with self.subTest(operation=operation, params=params):
                    self.assert_denied(operation, await self.call(operation, params=params), 400)

    async def test_valid_beyond_end_offsets_do_not_turn_into_server_errors(self):
        for operation in LISTS:
            for offset in (1000, 10 ** 30):
                with self.subTest(operation=operation, offset=offset):
                    response = await self.call(operation, params={"offset": offset, "limit": 1})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.validate(OPERATIONS[operation][3], response.json())
                    self.assertEqual(response.json(), {"items": [], "total": 2 if operation == "listCases" else 1,
                                                       "limit": 1, "offset": offset})
        self.assertEqual(self.snapshot(), self.initial_state)

    async def test_query_parameters_cannot_override_case_or_resource_scope(self):
        for operation in SCOPED:
            if operation == "uploadEvidence":
                continue  # Its denied-write paths are covered by the main matrix.
            response = await self.call(operation, params={"case_id": self.case_b, "evidence_id": self.evidence_b,
                                                         "actor_id": "investigator-2"})
            self.assertEqual(response.status_code, 200)
            if operation == "downloadEvidence":
                self.assertEqual(response.content, self.content)
            else:
                body = response.json()
                self.assertNotIn(self.case_b, json.dumps(body))
                self.assertNotIn(self.evidence_b, json.dumps(body))
        self.assertEqual(self.snapshot(), self.initial_state)
