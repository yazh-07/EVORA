"""F07 real F03/F06 producer -> authorized, safe audit API and pagination."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.database import SQLiteDatabase


class AuditListTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.app = create_app(root / "audit.sqlite3", storage_dir=root / "private",
            token_verifier=SyntheticTokenVerifier({
                "synthetic-a": "investigator-1", "synthetic-b": "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(transport=ASGITransport(self.app),
            base_url="http://test", headers={"Authorization": "Bearer synthetic-a"}))
        self.case_a = (await self.client.post("/api/v1/cases", json={"title": "Synthetic A"})).json()["id"]
        self.case_b = (await self.client.post("/api/v1/cases", json={"title": "Synthetic B"},
            headers={"Authorization": "Bearer synthetic-b"})).json()["id"]
        self.url = f"/api/v1/cases/{self.case_a}/audit-events"
        spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())
        self.validators = {name: Draft202012Validator(
            {**spec["components"]["schemas"][name], "components": spec["components"]},
            format_checker=FormatChecker()) for name in ("AuditPage", "ApiError")}

    async def upload(self, *, case=None, token="synthetic-a", content=None):
        content = content if content is not None else Path("fixtures/synthetic-case/network.csv").read_bytes()
        response = await self.client.post(f"/api/v1/cases/{case or self.case_a}/evidence",
            headers={"Authorization": "Bearer " + token},
            data={"kind": "network_log", "source_label": "SYNTHETIC_PRIVATE_SOURCE"},
            files={"file": ("SYNTHETIC_PRIVATE_FILENAME.csv", content, "text/csv")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def page(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.validators["AuditPage"].validate(response.json())
        return response.json()

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.validators["ApiError"].validate(response.json())

    def insert_fixture_event(self, identifier, stamp, reason=None):
        # Explicit synthetic ordering/optional-field fixture, not a new producer.
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO audit_events "
                "(id, case_id, actor_id, action, target_id, created_at, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (identifier, self.case_a, "investigator-1", "synthetic.fixture", "synthetic-target", stamp, reason))

    async def test_real_upload_action_visible_with_exact_actor_target_time_and_no_null_reason(self):
        evidence = await self.upload()
        page = self.page(await self.client.get(self.url))
        self.assertEqual((page["total"], page["limit"], page["offset"]), (1, 20, 0))
        [event] = page["items"]
        self.assertEqual(event, dict(id=event["id"], case_id=self.case_a, actor_id="investigator-1",
            action="uploadEvidence", target_id=evidence["id"], created_at=evidence["created_at"]))
        with self.app.state.database.connect() as connection:
            stored = dict(connection.execute("SELECT * FROM audit_events WHERE id = ?", (event["id"],)).fetchone())
        self.assertEqual(event, {key: value for key, value in stored.items() if value is not None})

    async def test_empty_case_and_offset_beyond_end_return_authoritative_total(self):
        self.assertEqual(self.page(await self.client.get(self.url)),
                         {"items": [], "total": 0, "limit": 20, "offset": 0})
        await self.upload()
        self.assertEqual(self.page(await self.client.get(self.url, params={"limit": 1, "offset": 10})),
                         {"items": [], "total": 1, "limit": 1, "offset": 10})
        huge_offset = 10 ** 30
        self.assertEqual(self.page(await self.client.get(self.url, params={"offset": huge_offset})),
                         {"items": [], "total": 1, "limit": 20, "offset": huge_offset})

    async def test_default_limit_and_all_pages_have_no_duplicates_for_fixed_history(self):
        targets = {(await self.upload(content=bytes([index])))["id"] for index in range(21)}
        first = self.page(await self.client.get(self.url))
        second = self.page(await self.client.get(self.url, params={"offset": 20}))
        self.assertEqual((first["total"], len(first["items"]), second["total"], len(second["items"])), (21, 20, 21, 1))
        all_items = first["items"] + second["items"]
        self.assertEqual(len({item["id"] for item in all_items}), 21)
        self.assertEqual({item["target_id"] for item in all_items}, targets)
        self.assertEqual(all_items, sorted(all_items, key=lambda item: (item["created_at"], item["id"])))
        self.assertEqual(self.page(await self.client.get(self.url, params={"limit": 100}))["items"], all_items)

    async def test_oldest_first_and_uuid_tie_break_are_deterministic(self):
        identifiers = [f"00000000-0000-4000-8000-{number:012d}" for number in (3, 2, 1)]
        for identifier in identifiers:
            self.insert_fixture_event(identifier, "2026-11-01T12:00:00Z")
        earlier = "00000000-0000-4000-8000-000000000004"
        self.insert_fixture_event(earlier, "2026-11-01T11:00:00Z")
        ids = []
        for offset in range(4):
            page = self.page(await self.client.get(self.url, params={"limit": 1, "offset": offset}))
            self.assertEqual((page["total"], page["limit"], page["offset"]), (4, 1, offset))
            ids.append(page["items"][0]["id"])
        self.assertEqual(ids, [earlier, *sorted(identifiers)])

    async def test_fractional_and_whole_second_timestamps_sort_by_time_then_id(self):
        stamps = {4: "2026-11-01T12:00:00Z", 3: "2026-11-01T12:00:00.000000Z",
                  2: "2026-11-01T12:00:00.000001Z", 1: "2026-11-01T12:00:00.1Z",
                  5: "2026-11-01T12:00:00.100001Z"}
        identifiers = {number: f"00000000-0000-4000-8000-{number:012d}" for number in stamps}
        for number, stamp in stamps.items():
            self.insert_fixture_event(identifiers[number], stamp)
        items = self.page(await self.client.get(self.url))["items"]
        self.assertEqual([item["id"] for item in items], [identifiers[n] for n in (3, 4, 2, 1, 5)])

    async def test_optional_reason_reference_is_preserved_and_null_is_omitted(self):
        self.insert_fixture_event(str(uuid4()), "2026-11-01T12:00:00Z", "synthetic-review-reference")
        [event] = self.page(await self.client.get(self.url))["items"]
        self.assertEqual(event["reason"], "synthetic-review-reference")

    async def test_two_cases_are_filtered_and_foreign_missing_denials_are_indistinguishable(self):
        one = await self.upload()
        two = await self.upload(case=self.case_b, token="synthetic-b")
        first = self.page(await self.client.get(self.url))
        second = self.page(await self.client.get(f"/api/v1/cases/{self.case_b}/audit-events",
                                               headers={"Authorization": "Bearer synthetic-b"}))
        self.assertEqual([event["target_id"] for event in first["items"]], [one["id"]])
        self.assertEqual([event["target_id"] for event in second["items"]], [two["id"]])
        foreign = await self.client.get(f"/api/v1/cases/{self.case_b}/audit-events")
        missing = await self.client.get(f"/api/v1/cases/{uuid4()}/audit-events")
        self.assert_error(foreign, 404)
        self.assert_error(missing, 404)
        self.assertEqual((foreign.content, foreign.headers), (missing.content, missing.headers))

    async def test_missing_invalid_and_duplicate_authentication_return_401(self):
        headers_list = [{"Authorization": ""}, {"Authorization": "Bearer invalid"},
            {"Authorization": "Basic synthetic"}, [("Authorization", "Bearer synthetic-a"),
                                                     ("Authorization", "Bearer synthetic-b")]]
        for headers in headers_list:
            self.assert_error(await self.client.get(self.url, headers=headers), 401)
        self.client.headers.pop("Authorization")
        self.assert_error(await self.client.get(self.url), 401)

    async def test_invalid_pagination_and_case_id_use_shared_safe_400(self):
        for params in ({"limit": 0}, {"limit": 101}, {"limit": "invalid"}, {"limit": "1.5"},
                       {"offset": -1}, {"offset": "invalid"}, {"offset": "0.5"}):
            with self.subTest(params=params):
                response = await self.client.get(self.url, params=params)
                self.assert_error(response, 400)
                self.assertEqual(response.json(), {"code": "INVALID_INPUT", "message": "Invalid request input."})
        response = await self.client.get("/api/v1/cases/SYNTHETIC_PRIVATE_BAD_ID/audit-events")
        self.assert_error(response, 400)
        self.assertNotIn("SYNTHETIC_PRIVATE", response.text)

    async def test_membership_is_current_and_shared_members_can_read_case_history(self):
        await self.upload()
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO case_members VALUES (?, ?)", (self.case_a, "investigator-2"))
        shared = self.page(await self.client.get(self.url, headers={"Authorization": "Bearer synthetic-b"}))
        self.assertEqual(shared["items"][0]["actor_id"], "investigator-1")
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM case_members WHERE case_id = ? AND actor_id = ?",
                               (self.case_a, "investigator-2"))
        self.assert_error(await self.client.get(self.url, headers={"Authorization": "Bearer synthetic-b"}), 404)

    async def test_query_actor_or_case_fields_cannot_override_guard(self):
        await self.upload()
        page = self.page(await self.client.get(self.url, params={"case_id": self.case_b, "actor_id": "investigator-2"}))
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["case_id"], self.case_a)

    async def test_only_safe_fields_returned_and_private_source_storage_is_not_joined(self):
        await self.upload(content=b"SYNTHETIC_PRIVATE_BYTES")
        before = self.page(await self.client.get(self.url))
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TABLE intake_provenance")
        response = await self.client.get(self.url)
        self.assertEqual(self.page(response), before)
        for marker in ("SYNTHETIC_PRIVATE", "source_filename", "source_label", "original_sha256",
                       "storage_path", "record_version", "Bearer", "intake_provenance"):
            self.assertNotIn(marker, response.text)
        self.assertEqual(set(before["items"][0]), {"id", "case_id", "actor_id", "action", "target_id", "created_at"})

    async def test_listing_is_read_only_and_does_not_append_an_intake_event(self):
        await self.upload()
        with self.app.state.database.connect() as connection:
            before = connection.execute("SELECT * FROM audit_events").fetchall()
            sources = connection.execute("SELECT * FROM intake_provenance").fetchall()
        for _ in range(3):
            self.assertEqual(self.page(await self.client.get(self.url))["total"], 1)
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT * FROM audit_events").fetchall(), before)
            self.assertEqual(connection.execute("SELECT * FROM intake_provenance").fetchall(), sources)

    async def test_storage_failure_is_not_reported_as_an_empty_success(self):
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TABLE audit_events")
        async with AsyncClient(transport=ASGITransport(self.app, raise_app_exceptions=False),
                               base_url="http://test") as client:
            response = await client.get(self.url, headers={"Authorization": "Bearer synthetic-a"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.text, "Internal Server Error")

    async def test_total_and_items_share_snapshot_during_committed_append(self):
        await self.upload()
        database = self.app.state.database
        # WAL lets a genuine second connection commit between the SELECTs.
        # Connection tracing schedules the write; neither query/result is mocked.
        with database.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
        original_connect = SQLiteDatabase.connect
        appended = []

        @contextmanager
        def interleaved_connect(instance):
            with original_connect(instance) as reader:
                def trace(statement):
                    if statement.startswith("SELECT id, case_id, actor_id") and not appended:
                        with original_connect(database) as writer:
                            writer.execute("INSERT INTO audit_events "
                                "(id, case_id, actor_id, action, target_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (str(uuid4()), self.case_a, "investigator-1", "synthetic.fixture", "synthetic-target", "2099-01-01T00:00:00Z"))
                        appended.append(True)
                reader.set_trace_callback(trace)
                yield reader

        with patch.object(SQLiteDatabase, "connect", interleaved_connect):
            page = self.page(await self.client.get(self.url))
        self.assertEqual(appended, [True])
        self.assertEqual((page["total"], len(page["items"])), (1, 1))
        next_page = self.page(await self.client.get(self.url))
        self.assertEqual((next_page["total"], len(next_page["items"])), (2, 2))
