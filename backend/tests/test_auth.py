"""F00 guards on real FastAPI; memberships/routes below are test-only F01 doubles."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
import unittest
from uuid import UUID

from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator

from backend.app import create_app
from backend.auth import (
    Actor, CaseAccessGrant, SyntheticTokenVerifier, authenticated_actor, require_case_access,
)


CASE_A = UUID("00000000-0000-4000-8000-000000000001")
CASE_B = UUID("00000000-0000-4000-8000-000000000002")
MISSING_CASE = UUID("00000000-0000-4000-8000-000000000003")
# Only synthetic fixture credentials; none are default application credentials.
TOKEN_A = "synthetic-f00-actor-a"
TOKEN_B = "synthetic-f00-actor-b"


class SQLiteMembershipFixture:
    """Temporary membership producer double, not F01's persistence schema/API."""

    def __init__(self, database):
        self.database = database
        self.lookups = []

    def allows(self, actor_id, case_id):
        self.lookups.append((actor_id, case_id))
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM synthetic_cases AS c "
                "JOIN synthetic_memberships AS m ON m.case_id = c.id "
                "WHERE c.id = ? AND m.actor_id = ?",
                (str(case_id), actor_id),
            ).fetchone() is not None


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        spec = json.loads(Path(os.environ["EVORA_CONTRACT_BUNDLE"]).read_text())
        cls.validator = Draft202012Validator(spec["components"]["schemas"]["ApiError"])

    async def asyncSetUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.app = create_app(
            Path(directory) / "auth.sqlite3",
            token_verifier=SyntheticTokenVerifier({TOKEN_A: "investigator-1", TOKEN_B: "investigator-2"}),
        )
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.membership = SQLiteMembershipFixture(self.app.state.database)
        self.app.state.case_access = self.membership
        with self.app.state.database.connect() as connection:
            connection.executescript(
                "CREATE TABLE synthetic_cases (id TEXT PRIMARY KEY);"
                "CREATE TABLE synthetic_memberships ("
                "case_id TEXT REFERENCES synthetic_cases(id), actor_id TEXT NOT NULL, "
                "PRIMARY KEY(case_id, actor_id));"
                "CREATE TABLE synthetic_writes (actor_id TEXT, case_id TEXT);"
            )
            connection.executemany("INSERT INTO synthetic_cases VALUES (?)", [(str(CASE_A),), (str(CASE_B),)])
            connection.executemany("INSERT INTO synthetic_memberships VALUES (?, ?)", [
                (str(CASE_A), "investigator-1"), (str(CASE_B), "investigator-2"),
            ])
        self.handler_calls = 0

        @self.app.get("/_test/auth")
        def identity(actor: Annotated[Actor, Depends(authenticated_actor)]):
            self.handler_calls += 1
            return {"actor_id": actor.id}

        @self.app.get("/_test/cases/{caseId}")
        def read_case(grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
            self.handler_calls += 1
            return {"actor_id": grant.actor.id, "case_id": str(grant.case_id)}

        @self.app.post("/_test/cases/{caseId}")
        def write_case(grant: Annotated[CaseAccessGrant, Depends(require_case_access)]):
            self.handler_calls += 1
            with self.app.state.database.connect() as connection:
                connection.execute("INSERT INTO synthetic_writes VALUES (?, ?)",
                                   (grant.actor.id, str(grant.case_id)))
            return {"written": True}

        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
        ))

    def assert_access_error(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.validator.validate(response.json())
        self.assertEqual(response.json(), {
            "code": "UNAUTHORIZED" if status == 401 else "NOT_FOUND",
            "message": "Authentication required." if status == 401 else "Resource not found.",
        })
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.headers["cache-control"], "no-store")
        if status == 401:
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
        else:
            self.assertNotIn("www-authenticate", response.headers)

    async def test_two_actors_authenticate_and_access_only_their_own_case(self):
        for token, actor, case in ((TOKEN_A, "investigator-1", CASE_A), (TOKEN_B, "investigator-2", CASE_B)):
            with self.subTest(actor=actor):
                identity = await self.client.get("/_test/auth", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(identity.json(), {"actor_id": actor})
                response = await self.client.get(f"/_test/cases/{case}", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"actor_id": actor, "case_id": str(case)})

    async def test_missing_invalid_malformed_or_duplicate_identity_rejected_before_lookup(self):
        invalid_headers = [
            {}, {"Authorization": ""}, {"Authorization": "Bearer"},
            {"Authorization": "Bearer "}, {"Authorization": "Basic synthetic"},
            {"Authorization": "Bearer unknown-synthetic-token"},
            {"Authorization": f"Bearer {TOKEN_A} extra"},
            {"Authorization": f"Bearer\t{TOKEN_A}"},
            {"Authorization": f" Bearer {TOKEN_A}"},
            {"Authorization": f"Bearer {TOKEN_A} "},
            {"Authorization": f"Bearer {TOKEN_A}, Bearer {TOKEN_B}"},
            [("Authorization", f"Bearer {TOKEN_A}"), ("Authorization", f"Bearer {TOKEN_B}")],
            [("Authorization", f"Bearer {TOKEN_A}"), ("Authorization", f"Bearer {TOKEN_A}")],
        ]
        for headers in invalid_headers:
            with self.subTest(headers=headers):
                self.assert_access_error(await self.client.get(f"/_test/cases/{CASE_A}", headers=headers), 401)
        self.assertEqual(self.membership.lookups, [])
        self.assertEqual(self.handler_calls, 0)

    async def test_bearer_scheme_is_case_insensitive_and_accepts_http_spaces(self):
        response = await self.client.get("/_test/auth", headers={"Authorization": f"bEaReR  {TOKEN_A}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"actor_id": "investigator-1"})

    async def test_query_cookie_and_actor_header_cannot_supply_identity(self):
        response = await self.client.get(
            f"/_test/cases/{CASE_A}", params={"token": TOKEN_A, "actor_id": "investigator-1"},
            headers={"Cookie": f"token={TOKEN_A}", "X-Actor-Id": "investigator-1"},
        )
        self.assert_access_error(response, 401)
        self.assertEqual(self.membership.lookups, [])

    async def test_foreign_and_missing_cases_have_identical_status_body_and_headers(self):
        for token, foreign in ((TOKEN_A, CASE_B), (TOKEN_B, CASE_A)):
            foreign_response = await self.client.get(f"/_test/cases/{foreign}", headers={"Authorization": f"Bearer {token}"})
            missing_response = await self.client.get(f"/_test/cases/{MISSING_CASE}", headers={"Authorization": f"Bearer {token}"})
            self.assert_access_error(foreign_response, 404)
            self.assert_access_error(missing_response, 404)
            self.assertEqual(foreign_response.content, missing_response.content)
            self.assertEqual(foreign_response.headers, missing_response.headers)
        self.assertEqual(self.handler_calls, 0)

    async def test_foreign_missing_and_unauthenticated_writes_have_no_side_effects(self):
        for case, token, status in ((CASE_B, TOKEN_A, 404), (MISSING_CASE, TOKEN_A, 404), (CASE_A, None, 401)):
            response = await self.client.post(f"/_test/cases/{case}", headers={"Authorization": f"Bearer {token}"} if token else {})
            self.assert_access_error(response, status)
        self.assertEqual(self.handler_calls, 0)
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM synthetic_writes").fetchone()[0], 0)

    async def test_authorized_write_records_authenticated_actor_and_guarded_case(self):
        response = await self.client.post(f"/_test/cases/{CASE_A}", headers={"Authorization": f"Bearer {TOKEN_A}", "X-Actor-Id": "investigator-2"})
        self.assertEqual(response.status_code, 200)
        with self.app.state.database.connect() as connection:
            self.assertEqual([tuple(row) for row in connection.execute("SELECT * FROM synthetic_writes")],
                             [("investigator-1", str(CASE_A))])

    async def test_membership_rechecked_after_revocation(self):
        headers = {"Authorization": f"Bearer {TOKEN_A}"}
        self.assertEqual((await self.client.get(f"/_test/cases/{CASE_A}", headers=headers)).status_code, 200)
        with self.app.state.database.connect() as connection:
            connection.execute("DELETE FROM synthetic_memberships WHERE case_id = ?", (str(CASE_A),))
        self.assert_access_error(await self.client.get(f"/_test/cases/{CASE_A}", headers=headers), 404)
        self.assertEqual(self.handler_calls, 1)

    async def test_membership_is_not_inferred_from_case_id_or_actor_number(self):
        with self.app.state.database.connect() as connection:
            connection.execute("INSERT INTO synthetic_memberships VALUES (?, ?)", (str(CASE_B), "investigator-1"))
        response = await self.client.get(f"/_test/cases/{CASE_B}", headers={"Authorization": f"Bearer {TOKEN_A}"})
        self.assertEqual(response.status_code, 200)

    async def test_membership_storage_failure_never_grants_access(self):
        with self.app.state.database.connect() as connection:
            connection.execute("DROP TABLE synthetic_memberships")
        async with AsyncClient(transport=ASGITransport(self.app, raise_app_exceptions=False), base_url="http://test") as client:
            response = await client.get(f"/_test/cases/{CASE_A}", headers={"Authorization": f"Bearer {TOKEN_A}"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.text, "Internal Server Error")
        self.assertEqual(self.handler_calls, 0)

    async def test_invalid_case_id_uses_shared_400_without_input_echo(self):
        response = await self.client.get("/_test/cases/SYNTHETIC_PRIVATE_VALUE", headers={"Authorization": f"Bearer {TOKEN_A}"})
        self.assertEqual(response.status_code, 400)
        self.validator.validate(response.json())
        self.assertEqual(response.json(), {"code": "INVALID_INPUT", "message": "Invalid request input."})
        self.assertEqual(self.membership.lookups, [])
        self.assertEqual(self.handler_calls, 0)

    async def test_missing_identity_precedes_invalid_case_validation(self):
        self.assert_access_error(await self.client.get("/_test/cases/not-a-uuid"), 401)

    async def test_default_verifier_and_membership_deny_access(self):
        default_app = create_app(self.app.state.database.path)
        self.app.state.token_verifier = default_app.state.token_verifier
        self.assert_access_error(await self.client.get("/_test/auth", headers={"Authorization": f"Bearer {TOKEN_A}"}), 401)
        self.app.state.token_verifier = SyntheticTokenVerifier({TOKEN_A: "investigator-1"})
        self.app.state.case_access = default_app.state.case_access
        self.assert_access_error(await self.client.get(f"/_test/cases/{CASE_A}", headers={"Authorization": f"Bearer {TOKEN_A}"}), 404)

    async def test_replacing_verifier_revokes_token_without_stale_identity_cache(self):
        headers = {"Authorization": f"Bearer {TOKEN_A}"}
        self.assertEqual((await self.client.get("/_test/auth", headers=headers)).status_code, 200)
        self.app.state.token_verifier = SyntheticTokenVerifier({TOKEN_B: "investigator-2"})
        self.assert_access_error(await self.client.get("/_test/auth", headers=headers), 401)

    async def test_separate_apps_do_not_share_authentication_configuration(self):
        other = create_app(self.app.state.database.path, token_verifier=SyntheticTokenVerifier({}))

        @other.get("/_test/auth")
        def identity(actor: Annotated[Actor, Depends(authenticated_actor)]):
            return {"actor_id": actor.id}

        async with AsyncClient(transport=ASGITransport(other), base_url="http://test") as client:
            self.assert_access_error(await client.get("/_test/auth", headers={"Authorization": f"Bearer {TOKEN_A}"}), 401)
        self.assertEqual((await self.client.get("/_test/auth", headers={"Authorization": f"Bearer {TOKEN_A}"})).status_code, 200)

    async def test_auth_failures_do_not_log_or_echo_credentials_or_case_ids(self):
        with self.assertNoLogs("backend", level="DEBUG"):
            invalid = await self.client.get(f"/_test/cases/{CASE_A}", headers={"Authorization": "Bearer SYNTHETIC_PRIVATE_SECRET"})
            foreign = await self.client.get(f"/_test/cases/{CASE_B}", headers={"Authorization": f"Bearer {TOKEN_A}"})
        for response in (invalid, foreign):
            for private in ("SYNTHETIC_PRIVATE_SECRET", TOKEN_A, str(CASE_A), str(CASE_B), "investigator-1"):
                self.assertNotIn(private, response.text)
                self.assertNotIn(private, str(response.headers))


class SyntheticVerifierTests(unittest.TestCase):
    def test_only_configured_tokens_map_to_declared_synthetic_actors(self):
        verifier = SyntheticTokenVerifier({TOKEN_A: "investigator-1"})
        self.assertEqual(verifier.verify(TOKEN_A), Actor("investigator-1"))
        self.assertIsNone(verifier.verify(TOKEN_B))
        self.assertIsNone(verifier.verify("investigator-1"))
        self.assertIsNone(verifier.verify("non-ascii-\u00e9"))
        self.assertIsNone(SyntheticTokenVerifier({}).verify(TOKEN_A))

    def test_invalid_configuration_errors_do_not_echo_input(self):
        for config in ({"": "investigator-1"}, {"bad token": "investigator-1"},
                       {"private-token": "unapproved-actor"}, {"\u00e9": "investigator-1"}):
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, "^Invalid synthetic authentication configuration\\.$"):
                SyntheticTokenVerifier(config)

    def test_verifier_copies_configuration_and_does_not_retain_plaintext_tokens(self):
        config = {TOKEN_A: "investigator-1"}
        verifier = SyntheticTokenVerifier(config)
        config.clear()
        self.assertEqual(verifier.verify(TOKEN_A), Actor("investigator-1"))
        self.assertNotIn(TOKEN_A, repr(verifier))
        self.assertNotIn(TOKEN_A, repr(vars(verifier)))
