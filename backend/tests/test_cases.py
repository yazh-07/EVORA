"""Real F01 API/SQLite integration with synthetic identities only."""

import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier


class CaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / "cases.sqlite3"
        self.app = create_app(self.path, token_verifier=SyntheticTokenVerifier({
            "synthetic-f01-a": "investigator-1", "synthetic-f01-b": "investigator-2",
        }))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
            headers={"Authorization": "Bearer synthetic-f01-a"},
        ))
        bundle = os.environ.get("EVORA_CONTRACT_BUNDLE")
        self.spec = json.loads(Path(bundle).read_text()) if bundle else None

    def check_response(self, response, status, schema):
        self.assertEqual(response.status_code, status, response.text)
        if self.spec:
            Draft202012Validator({**self.spec["components"]["schemas"][schema], "components": self.spec["components"]},
                                 format_checker=FormatChecker()).validate(response.json())
        return response.json()

    async def create(self, **body):
        return self.check_response(await self.client.post("/api/v1/cases", json=body), 201, "Case")

    async def list_page(self, **params):
        return self.check_response(await self.client.get("/api/v1/cases", params=params),
                                   200, "CasePage")

    async def test_list_isolation_defaults_and_empty_actor(self):
        own = await self.create(title="Own synthetic case")
        headers = {"Authorization": "Bearer synthetic-f01-b"}
        response = await self.client.get("/api/v1/cases", headers=headers)
        self.assertEqual(self.check_response(response, 200, "CasePage"),
                         {"items": [], "total": 0, "limit": 20, "offset": 0})
        foreign = self.check_response(await self.client.post(
            "/api/v1/cases", json={"title": "Foreign synthetic case"}, headers=headers), 201, "Case")
        self.assertEqual(await self.list_page(),
                         {"items": [own], "total": 1, "limit": 20, "offset": 0})
        response = await self.client.get("/api/v1/cases", headers=headers)
        self.assertEqual(self.check_response(response, 200, "CasePage")["items"], [foreign])
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM case_members WHERE case_id = ?", (own["id"],))
        self.assertEqual((await self.list_page())["total"], 0)

    async def test_list_pagination_and_stable_order(self):
        cases = [await self.create(title=f"Synthetic {i}", **(
            {"description": "Preserved description"} if i == 0 else {})) for i in range(23)]
        with self.app.state.database.connect() as connection:
            for i, case in enumerate(cases):
                case["created_at"] = f"2026-10-{25 if i < 12 else 26}T00:00:00Z"
                connection.execute("UPDATE cases SET created_at = ? WHERE id = ?",
                                   (case["created_at"], case["id"]))
        expected = sorted(cases, key=lambda case: case["id"])
        expected.sort(key=lambda case: case["created_at"], reverse=True)
        self.assertEqual(await self.list_page(),
                         {"items": expected[:20], "total": 23, "limit": 20, "offset": 0})
        collected = []
        for offset in range(0, 25, 5):
            page = await self.list_page(limit=5, offset=offset)
            self.assertEqual(page, {"items": expected[offset:offset + 5],
                                   "total": 23, "limit": 5, "offset": offset})
            collected.extend(page["items"])
        self.assertEqual(collected, expected)
        for offset in (23, 100):
            self.assertEqual(await self.list_page(limit=100, offset=offset),
                             {"items": [], "total": 23, "limit": 100, "offset": offset})
        self.assertEqual((await self.list_page(limit=1))["items"], expected[:1])

    async def test_list_invalid_pagination(self):
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "abc"}):
            with self.subTest(params=params):
                response = await self.client.get("/api/v1/cases", params=params)
                self.check_response(response, 400, "ApiError")
                self.assertEqual(response.json(), {"code": "INVALID_INPUT",
                                                   "message": "Invalid request input."})

    async def test_roundtrip_and_restart_preserve_original_values(self):
        case = await self.create(title=" Synthetic case ", description="Synthetic description")
        self.assertEqual(UUID(case["id"]).version, 4)
        self.assertTrue(case["created_at"].endswith("Z"))
        self.assertEqual(case["title"], " Synthetic case ")
        read = await self.client.get('/api/v1/cases/' + case["id"])
        self.assertEqual(self.check_response(read, 200, "Case"), case)
        restarted = create_app(self.path, token_verifier=self.app.state.token_verifier)
        async with restarted.router.lifespan_context(restarted), AsyncClient(
            transport=ASGITransport(restarted), base_url="http://test",
            headers=dict(self.client.headers),
        ) as client:
            self.assertEqual((await client.get('/api/v1/cases/' + case["id"])).json(), case)
        with self.app.state.database.connect() as connection:
            self.assertEqual(dict(connection.execute("SELECT * FROM cases").fetchone()), case)
            self.assertEqual(tuple(connection.execute("SELECT * FROM case_members").fetchone()),
                             (case["id"], "investigator-1"))

    async def test_creation_without_description(self):
        case = await self.create(title="Synthetic")
        self.assertNotIn("description", case)
        self.assertEqual((await self.client.get('/api/v1/cases/' + case["id"])).json(), case)

    async def test_validation_negatives_leave_database_empty(self):
        for body in ({}, {"title": ""}, {"title": " \t\n"}, {"title": "x" * 201},
                     {"title": "ok", "description": "x" * 5001},
                     {"title": "ok", "extra": True}, {"title": 1},
                     {"title": "ok", "description": None}):
            with self.subTest(body=body):
                response = await self.client.post("/api/v1/cases", json=body)
                self.check_response(response, 400, "ApiError")
                self.assertEqual(response.json(), {"code": "INVALID_INPUT", "message": "Invalid request input."})
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM cases").fetchone()[0], 0)

    async def test_valid_length_boundaries(self):
        await self.create(title="x" * 200, description="x" * 5000)
        await self.create(title="x", description="")

    async def test_missing_and_malformed_authentication(self):
        case = await self.create(title="Synthetic")
        for token in (None, "Basic invalid", "Bearer", "Bearer rejected"):
            headers = {} if token is None else {"Authorization": token}
            async with AsyncClient(transport=ASGITransport(self.app), base_url="http://test") as client:
                for method, path, kwargs in (
                    (client.post, "/api/v1/cases", {"json": {"title": "Synthetic"}}),
                    (client.get, '/api/v1/cases/' + case["id"], {}),
                    (client.get, "/api/v1/cases", {}),
                ):
                    self.check_response(await method(path, headers=headers, **kwargs), 401, "ApiError")

    async def test_foreign_and_missing_are_identical(self):
        case = await self.create(title="Synthetic")
        headers = {"Authorization": "Bearer synthetic-f01-b"}
        foreign = await self.client.get('/api/v1/cases/' + case["id"], headers=headers)
        missing = await self.client.get('/api/v1/cases/' + str(uuid4()), headers=headers)
        self.check_response(foreign, 404, "ApiError")
        self.assertEqual(foreign.json(), {"code": "NOT_FOUND", "message": "Resource not found."})
        self.assertEqual((foreign.status_code, foreign.content, foreign.headers),
                         (missing.status_code, missing.content, missing.headers))

    async def test_invalid_uuid(self):
        self.check_response(await self.client.get('/api/v1/cases/not-a-uuid'), 400, "ApiError")

    async def test_membership_revocation_takes_effect_immediately(self):
        case = await self.create(title="Synthetic")
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM case_members WHERE case_id = ?", (case["id"],))
        self.check_response(await self.client.get('/api/v1/cases/' + case["id"]), 404, "ApiError")

    async def test_membership_failure_rolls_back_case(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_membership BEFORE INSERT ON case_members "
                               "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.client.post('/api/v1/cases', json={"title": "Synthetic"})
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM cases").fetchone()[0], 0)

    async def test_membership_foreign_key_and_delete_cascade(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.app.state.database.connect() as connection:
                connection.execute("INSERT INTO case_members VALUES (?, ?)", (str(uuid4()), "investigator-1"))
        case = await self.create(title="Synthetic")
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM cases WHERE id = ?", (case["id"],))
        self.assertFalse(self.app.state.case_access.allows("investigator-1", UUID(case["id"])))

    async def test_real_membership_storage_failure_is_server_error(self):
        case = await self.create(title="Synthetic")
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TABLE case_members")
        async with AsyncClient(transport=ASGITransport(self.app, raise_app_exceptions=False),
                               base_url="http://test", headers=dict(self.client.headers)) as client:
            response = await client.get('/api/v1/cases/' + case["id"])
        self.assertEqual(response.status_code, 500)
