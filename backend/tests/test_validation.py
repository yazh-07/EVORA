"""Synthetic test-only routes exercise the shared handler, not domain APIs."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
import unittest
from uuid import UUID

from fastapi import Depends, Header, Query
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

from backend.app import create_app, get_database
from backend.database import SQLiteDatabase


class ProbeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int = Field(ge=1)


class ValidationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Fail loudly if the shared bundle is missing; never skip schema checks
        # or replace the authoritative schema with a handwritten local copy.
        spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())
        schema = spec["components"]["schemas"]["ApiError"]
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)

    async def asyncSetUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.app = create_app(Path(directory) / "validation.sqlite3")
        self.calls = 0

        @self.app.post("/_test/input/{identifier}")
        async def probe(
            identifier: UUID,
            body: ProbeInput,
            limit: Annotated[int, Query(ge=1, le=100)],
            key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
            database: Annotated[SQLiteDatabase, Depends(get_database)],
        ):
            self.calls += 1
            with database.connect() as connection:
                return {"connected": connection.execute("SELECT 1").fetchone()[0] == 1}

        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test"
        ))

    async def send(self, **overrides):
        kwargs = {
            "url": "/_test/input/00000000-0000-4000-8000-000000000001",
            "params": {"limit": 1},
            "headers": {"Idempotency-Key": "synthetic-test"},
            "json": {"value": 1},
        }
        kwargs.update(overrides)
        if "content" in overrides:
            kwargs.pop("json", None)
        return await self.client.post(**kwargs)

    def assert_invalid(self, response):
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.validator.validate(response.json())
        self.assertEqual(response.json(), {
            "code": "INVALID_INPUT", "message": "Invalid request input."
        })
        self.assertEqual(self.calls, 0)

    async def test_valid_request_reaches_handler_and_real_database(self):
        response = await self.send()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"connected": True})
        self.assertEqual(self.calls, 1)

    async def test_invalid_path_returns_400_api_error(self):
        self.assert_invalid(await self.send(url="/_test/input/not-a-uuid"))

    async def test_invalid_query_returns_400_api_error(self):
        for params in ({}, {"limit": "invalid"}, {"limit": 0}, {"limit": 101}):
            with self.subTest(params=params):
                self.assert_invalid(await self.send(params=params))

    async def test_invalid_header_returns_400_api_error(self):
        for headers in ({}, {"Idempotency-Key": ""}, {"Idempotency-Key": "x" * 129}):
            with self.subTest(headers=headers):
                self.assert_invalid(await self.send(headers=headers))

    async def test_invalid_body_returns_400_api_error_without_echoing_input(self):
        for body in (None, {}, {"value": 0}, {"value": "SYNTHETIC_DO_NOT_ECHO"},
                     {"value": 1, "SYNTHETIC_PRIVATE_FIELD": "SYNTHETIC_PRIVATE_VALUE"}):
            with self.subTest(body=body):
                self.assert_invalid(await self.send(json=body))

    async def test_malformed_json_returns_400_api_error(self):
        self.assert_invalid(await self.send(
            content='{"value": "SYNTHETIC_DO_NOT_ECHO',
            headers={"Idempotency-Key": "synthetic-test", "Content-Type": "application/json"},
        ))

    async def test_server_response_validation_is_not_mapped_to_invalid_input(self):
        @self.app.get("/_test/bad-response", response_model=ProbeInput)
        async def bad_response():
            return {"value": 0}

        async with AsyncClient(
            transport=ASGITransport(self.app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            response = await client.get("/_test/bad-response")
        self.assertEqual(response.status_code, 500)
