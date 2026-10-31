"""Real multipart/FastAPI/SQLite/private-file F03 and metadata F04 acceptance."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier


class EvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.storage = (root / "private").resolve()
        self.app = create_app((root / "db.sqlite3").resolve(), storage_dir=self.storage,
                              token_verifier=SyntheticTokenVerifier({
                                  "synthetic-a": "investigator-1", "synthetic-b": "investigator-2"}))
        await self.enterAsyncContext(self.app.router.lifespan_context(self.app))
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(self.app), base_url="http://test",
            headers={"Authorization": "Bearer synthetic-a"}))
        self.case = (await self.client.post('/api/v1/cases', json={"title": "Synthetic"})).json()
        self.url = '/api/v1/cases/' + self.case['id'] + '/evidence'
        bundle = os.environ.get('EVORA_CONTRACT_BUNDLE')
        self.spec = json.loads(Path(bundle).resolve().read_text()) if bundle else None

    async def upload(self, content=b'synthetic\x00\xff\r\n', filename='source.bin', **kwargs):
        data = kwargs.pop('data', {"kind": "network_log", "source_label": " Synthetic source "})
        return await self.client.post(kwargs.pop('url', self.url), data=data,
                                      files={"file": (filename, content, "application/octet-stream")}, **kwargs)

    def check(self, response, status, schema='ApiError'):
        self.assertEqual(response.status_code, status, response.text)
        if self.spec:
            Draft202012Validator({**self.spec['components']['schemas'][schema],
                                  'components': self.spec['components']},
                                 format_checker=FormatChecker()).validate(response.json())
        return response.json()

    def assert_empty(self):
        self.assertEqual(list(self.storage.rglob('*.bin')), [])
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM evidence').fetchone()[0], 0)

    async def test_roundtrip_and_unique_immutable_originals(self):
        content = Path('fixtures/synthetic-case/network.csv').resolve().read_bytes()
        first = self.check(await self.upload(content), 201, 'Evidence')
        second = self.check(await self.upload(b'different'), 201, 'Evidence')
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotIn('acquired_at', first)
        self.assertNotIn('storage_path', first)
        self.assertEqual(first['sha256'], hashlib.sha256(content).hexdigest())
        self.assertEqual(first['size_bytes'], len(content))
        self.assertEqual(first['source_label'], ' Synthetic source ')
        with self.app.state.database.connect() as connection:
            row = dict(connection.execute('SELECT * FROM evidence WHERE id = ?', (first['id'],)).fetchone())
        path = Path(row.pop('storage_path')).resolve()
        self.assertEqual(path.resolve(), (self.storage / self.case['id'] / (first['id'] + '.bin')).resolve())
        self.assertEqual(path.read_bytes(), content)
        self.assertIsNone(row.pop('acquired_at'))
        self.assertEqual(row, first)
        self.assertEqual((await self.client.get('/' + str(path))).status_code, 404)
        # Startup is repeatable and does not replace original bytes or metadata.
        async with self.app.router.lifespan_context(self.app):
            self.assertEqual(path.read_bytes(), content)

    async def test_timestamp_preserved_and_empty_file(self):
        stamp = '2026-10-31T10:11:12.123+05:30'
        body = self.check(await self.upload(b'', data={"kind": "document", "source_label": "s",
                                                      "acquired_at": stamp}), 201, 'Evidence')
        self.assertEqual(body['acquired_at'], stamp)
        self.assertEqual(body['sha256'], hashlib.sha256(b'').hexdigest())
        self.assertEqual(body['size_bytes'], 0)

    async def test_validation(self):
        for fields in ({"kind": "unknown", "source_label": "s"},
                       {"kind": "document", "source_label": " \t"}, {},
                       *({"kind": "document", "source_label": "s", "acquired_at": stamp}
                         for stamp in ('garbage', '2026-02-30T00:00:00Z', '2026-10-31',
                                       '2026-10-31T00:00:00', '2026-10-31T00:00:00+00:99', '', '123'))):
            body = self.check(await self.upload(data=fields), 400)
            self.assertEqual(body, {"code": "INVALID_INPUT", "message": "Invalid request input."})
        self.check(await self.client.post(self.url, data={"kind": "document", "source_label": "s"}), 400)
        self.assert_empty()

    async def test_unsafe_filenames(self):
        for name in ('../../bad.txt', '..\\bad.txt', '/bad.txt', 'a..b', 'C:bad.txt', '.'):
            self.check(await self.upload(filename=name), 400)
        self.assert_empty()

    async def test_authentication(self):
        for value in ('', 'Basic rejected', 'Bearer rejected'):
            self.check(await self.upload(headers={"Authorization": value}), 401)
        self.client.headers.pop('Authorization')
        self.check(await self.upload(), 401)
        self.assert_empty()

    async def test_case_isolation_and_uuid(self):
        foreign = await self.upload(headers={"Authorization": "Bearer synthetic-b"})
        missing = await self.upload(url='/api/v1/cases/' + str(uuid4()) + '/evidence')
        self.check(foreign, 404)
        self.assertEqual((foreign.content, foreign.headers), (missing.content, missing.headers))
        self.assertEqual(foreign.json(), {"code": "NOT_FOUND", "message": "Resource not found."})
        self.check(await self.upload(url='/api/v1/cases/invalid/evidence'), 400)
        self.assert_empty()

    async def test_size_limit_and_cleanup(self):
        with patch('backend.evidence.MAX_UPLOAD_BYTES', 65536):
            self.check(await self.upload(b'x' * 65536), 201, 'Evidence')
            response = await self.upload(b'x' * 65537)
            self.assertEqual(self.check(response, 413)['code'], 'PAYLOAD_TOO_LARGE')
        self.assertEqual(len(list(self.storage.rglob('*.bin'))), 1)
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM evidence').fetchone()[0], 1)

    async def test_database_failure_cleans_file(self):
        with self.app.state.database.connect() as connection:
            connection.execute("CREATE TRIGGER reject_evidence BEFORE INSERT ON evidence "
                               "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            await self.upload()
        self.assert_empty()

    async def test_read_failure_cleans_partial_file(self):
        from starlette.datastructures import UploadFile
        with patch.object(UploadFile, 'read', side_effect=[b'partial', OSError('synthetic failure')]):
            with self.assertRaises(OSError):
                await self.upload()
        self.assert_empty()

    async def test_get_evidence_roundtrip(self):
        for data in ({"kind": "network_log", "source_label": " Synthetic source "},
                     {"kind": "document", "source_label": "Synthetic timestamp",
                      "acquired_at": "2026-10-31T10:11:12.123+05:30"}):
            with self.subTest(data=data):
                uploaded = self.check(await self.upload(data=data), 201, 'Evidence')
                result = self.check(await self.client.get(self.url + '/' + uploaded['id']),
                                    200, 'Evidence')
                self.assertEqual(result, uploaded)
                self.assertNotIn('storage_path', result)
                if 'acquired_at' not in data:
                    self.assertNotIn('acquired_at', result)
                page = self.check(await self.client.get(self.url), 200, 'EvidencePage')
                self.assertIn(uploaded, page['items'])

    async def test_list_evidence_pagination_and_order(self):
        uploaded = [self.check(await self.upload(content=f'synthetic-{i}'.encode()),
                               201, 'Evidence') for i in range(23)]
        # Controlled timestamps on real uploaded rows exercise ordering and UUID ties
        # independently of clock resolution on Linux and Windows.
        with self.app.state.database.connect() as connection:
            for i, item in enumerate(uploaded):
                item['created_at'] = f'2026-10-{30 if i % 2 else 31}T00:00:00Z'
                connection.execute('UPDATE evidence SET created_at = ? WHERE id = ?',
                                   (item['created_at'], item['id']))
        older = sorted((item for i, item in enumerate(uploaded) if i % 2),
                       key=lambda item: item['id'])
        newer = sorted((item for i, item in enumerate(uploaded) if not i % 2),
                       key=lambda item: item['id'])
        expected = newer + older
        page = self.check(await self.client.get(self.url), 200, 'EvidencePage')
        self.assertEqual(page, dict(items=expected[:20], total=23, limit=20, offset=0))
        collected = []
        for offset in range(0, 24, 5):
            page = self.check(await self.client.get(self.url, params={'limit': 5, 'offset': offset}),
                              200, 'EvidencePage')
            self.assertEqual(page, dict(items=expected[offset:offset + 5], total=23,
                                        limit=5, offset=offset))
            collected.extend(page['items'])
        self.assertEqual(collected, expected)
        for limit, offset in ((1, 0), (100, 0), (20, 23), (20, 30)):
            page = self.check(await self.client.get(self.url, params={'limit': limit, 'offset': offset}),
                              200, 'EvidencePage')
            self.assertEqual(page, dict(items=expected[offset:offset + limit], total=23,
                                        limit=limit, offset=offset))

    async def test_list_empty_case_and_same_actor_case_isolation(self):
        other = self.check(await self.client.post('/api/v1/cases', json={'title': 'Other synthetic'}),
                           201, 'Case')
        other_url = '/api/v1/cases/' + other['id'] + '/evidence'
        self.check(await self.upload(url=other_url), 201, 'Evidence')
        page = self.check(await self.client.get(self.url), 200, 'EvidencePage')
        self.assertEqual(page, dict(items=[], total=0, limit=20, offset=0))
        own = self.check(await self.upload(), 201, 'Evidence')
        page = self.check(await self.client.get(self.url), 200, 'EvidencePage')
        self.assertEqual(page, dict(items=[own], total=1, limit=20, offset=0))

    async def test_metadata_case_and_resource_isolation(self):
        uploaded = self.check(await self.upload(), 201, 'Evidence')
        headers = {'Authorization': 'Bearer synthetic-b'}
        other = self.check(await self.client.post('/api/v1/cases', json={'title': 'Actor B'},
                                                  headers=headers), 201, 'Case')
        other_url = '/api/v1/cases/' + other['id'] + '/evidence'
        other_item = self.check(await self.upload(url=other_url, headers=headers), 201, 'Evidence')
        own_page = self.check(await self.client.get(self.url), 200, 'EvidencePage')
        self.assertEqual(own_page['items'], [uploaded])
        other_page = self.check(await self.client.get(other_url, headers=headers), 200, 'EvidencePage')
        self.assertEqual(other_page, dict(items=[other_item], total=1, limit=20, offset=0))
        missing_case = '/api/v1/cases/' + str(uuid4()) + '/evidence'
        missing_evidence = self.url + '/' + str(uuid4())
        baseline = await self.client.get(missing_evidence)
        self.assertEqual(self.check(baseline, 404),
                         {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
        for url, auth in ((self.url, headers),
                          (self.url + '/' + uploaded['id'], headers),
                          (missing_case, {}),
                          (missing_case + '/' + uploaded['id'], {}),
                          (other_url, {}),
                          (other_url + '/' + other_item['id'], {}),
                          (other_url + '/' + uploaded['id'], headers),
                          (other_url + '/' + str(uuid4()), headers),
                          (self.url + '/' + other_item['id'], {})):
            with self.subTest(url=url, auth=bool(auth)):
                response = await self.client.get(url, headers=auth)
                self.check(response, 404)
                self.assertEqual((response.content, response.headers),
                                 (baseline.content, baseline.headers))

    async def test_metadata_validation(self):
        for url in ('/api/v1/cases/invalid/evidence',
                    '/api/v1/cases/invalid/evidence/' + str(uuid4()),
                    self.url + '/invalid'):
            with self.subTest(url=url):
                self.assertEqual(self.check(await self.client.get(url), 400),
                                 {'code': 'INVALID_INPUT', 'message': 'Invalid request input.'})
        for params in ({'limit': 0}, {'limit': 101}, {'offset': -1}, {'limit': 'abc'}):
            with self.subTest(params=params):
                self.assertEqual(self.check(await self.client.get(self.url, params=params), 400),
                                 {'code': 'INVALID_INPUT', 'message': 'Invalid request input.'})

    async def test_metadata_authentication(self):
        uploaded = self.check(await self.upload(), 201, 'Evidence')
        for url in (self.url, self.url + '/' + uploaded['id']):
            for value in ('', 'Basic rejected', 'Bearer rejected'):
                with self.subTest(url=url, value=value):
                    response = await self.client.get(url, headers={'Authorization': value})
                    self.assertEqual(self.check(response, 401),
                                     {'code': 'UNAUTHORIZED', 'message': 'Authentication required.'})
                    self.assertEqual(response.headers['WWW-Authenticate'], 'Bearer')
        self.client.headers.pop('Authorization')
        for url in (self.url, self.url + '/' + uploaded['id']):
            self.check(await self.client.get(url), 401)

    async def test_metadata_membership_revocation(self):
        uploaded = self.check(await self.upload(), 201, 'Evidence')
        self.check(await self.client.get(self.url), 200, 'EvidencePage')
        self.check(await self.client.get(self.url + '/' + uploaded['id']), 200, 'Evidence')
        with self.app.state.database.connect() as connection:
            connection.execute('DELETE FROM case_members WHERE case_id = ?', (self.case['id'],))
        for url in (self.url, self.url + '/' + uploaded['id']):
            self.assertEqual(self.check(await self.client.get(url), 404),
                             {'code': 'NOT_FOUND', 'message': 'Resource not found.'})
