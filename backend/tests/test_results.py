"""Real HTTP/SQL processing plus labeled immutable output fixtures for operation selection."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier


class ResultsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.app = create_app(Path(self.temp.name) / 'db', storage_dir=Path(self.temp.name) / 'files',
                              token_verifier=SyntheticTokenVerifier({'one': 'investigator-1', 'two': 'investigator-2'}))
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url='http://test', headers={'Authorization': 'Bearer one'})
        self.case = (await self.client.post('/api/v1/cases', json={'title': 'Results case'})).json()['id']
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence', data={'kind': 'network_log', 'source_label': 'Gateway'},
            files={'file': ('network.csv', b'timestamp,device_id,ip_address,event\n2026-01-01T12:00:00Z,D-1,192.0.2.1,login\n', 'text/csv')})
        self.evidence = response.json()['id']
        self.base = f'/api/v1/cases/{self.case}/evidence/{self.evidence}'

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None, None, None)
        self.temp.cleanup()

    def fixture(self, config, kinds, index, status='completed'):
        """SQL fixture, not a claim that OCR/diarization inference ran."""
        run_id = str(uuid4())
        items = [dict(id=str(uuid4()), case_id=self.case, evidence_id=self.evidence, processing_run_id=run_id,
                      kind=kind, raw_value=f'Result {n}', normalized_value=f'Result {n}', source_locator=(f'media:start_ms={n*1000};end_ms={(n+1)*1000}' if kind == 'transcript.segment' else f'row={n+1}'), extraction_confidence=0.0)
                 for n, kind in enumerate(kinds)]
        stamp = f'2026-01-01T12:00:{index:02d}Z'
        with self.app.state.database.connect() as c:
            c.execute('INSERT INTO processing_runs (id,case_id,evidence_id,actor_id,key_digest,fingerprint,config_json,processor_version,created_at,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (run_id, self.case, self.evidence, 'investigator-1', str(uuid4()), 'fixture', json.dumps(config), 'results-fixture/1', stamp, 'queued'))
            c.execute("UPDATE processing_runs SET status='running' WHERE id=?", (run_id,))
            if status == 'completed':
                c.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?,?)', (run_id, self.case, self.evidence, json.dumps(items), '[]', '[]', '[]'))
                c.execute("UPDATE processing_runs SET status='completed',finished_at=? WHERE id=?", (stamp, run_id))
            elif status == 'failed':
                c.execute("UPDATE processing_runs SET status='failed',finished_at=?,error='PROCESSING_FAILED' WHERE id=?", (stamp, run_id))
        return run_id

    async def test_real_processing_returns_source_fields_and_contract(self):
        response = await self.client.post(self.base + '/processing-runs', headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 202, response.text)
        response = await self.client.get(self.base + '/results')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['operations'][0]['status'], 'completed')
        self.assertEqual(data['total'], 3)
        self.assertEqual({i['kind'] for i in data['items']}, {'network.device', 'network.ip', 'network.event'})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        import os
        from jsonschema import Draft202012Validator, FormatChecker
        bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text())
        Draft202012Validator({'$ref': '#/components/schemas/EvidenceResults', 'components': bundle['components']}, format_checker=FormatChecker()).validate(data)

    async def image_source(self):
        from io import BytesIO
        from PIL import Image
        buffer = BytesIO(); Image.new('RGB', (16, 16), 'white').save(buffer, format='PNG')
        response = await self.client.post(f'/api/v1/cases/{self.case}/evidence', data={'kind': 'image', 'source_label': 'Image'}, files={'file': ('image.png', buffer.getvalue(), 'image/png')})
        self.evidence = response.json()['id']
        self.base = f'/api/v1/cases/{self.case}/evidence/{self.evidence}'

    async def test_selects_each_operation_independently_and_keeps_success_after_failure(self):
        await self.image_source()
        enriched = self.fixture({'kind': 'image', 'image_understanding': {'model': 'private/path'}}, ['image.description', 'image.ocr'], 1)
        detection = self.fixture({'kind': 'image'}, ['image.detection'], 2)
        failed = self.fixture({'kind': 'image', 'image_understanding': {'model': 'private/path'}}, [], 3, 'failed')
        data = (await self.client.get(self.base + '/results', params={'operation': 'ocr'})).json()
        operations = {op['operation']: op for op in data['operations']}
        self.assertEqual(operations['ocr']['output_run_id'], enriched)
        self.assertEqual(operations['ocr']['latest_run_id'], failed)
        self.assertEqual(operations['ocr']['status'], 'failed')
        self.assertEqual(data['items'][0]['processing_run_id'], enriched)
        self.assertNotIn('private/path', json.dumps(data))
        pinned = (await self.client.get(self.base + '/results', params={'processing_run_id': detection, 'operation': 'ocr'})).json()
        self.assertEqual(pinned['total'], 0)
        self.assertEqual(pinned['items'], [])

    async def test_empty_vs_not_run_pagination_and_access(self):
        self.fixture({'kind': 'image'}, [], 1)
        data = (await self.client.get(self.base + '/results')).json()
        self.assertEqual(next(op for op in data['operations'] if op['operation'] == 'detection')['count'], 0)
        self.assertEqual(data['total'], 0)
        self.fixture({'kind': 'network_log'}, ['network.device'] * 3, 2)
        page = (await self.client.get(self.base + '/results', params={'operation': 'records', 'limit': 1, 'offset': 1})).json()
        self.assertEqual((page['total'], page['offset'], len(page['items'])), (3, 1, 1))
        for query in ['operation=bad', 'limit=0', 'limit=101', 'offset=-1', 'operation=ocr&operation=records', 'secret=1']:
            self.assertIn((await self.client.get(self.base + '/results?' + query)).status_code, (400, 422))
        self.assertEqual((await self.client.get(self.base + '/results', headers={'Authorization': 'Bearer two'})).status_code, 404)
        self.assertEqual((await self.client.get(self.base + '/results', params={'processing_run_id': str(uuid4())})).status_code, 404)

    async def test_transcript_survives_unrelated_output_and_historical_pin(self):
        run = self.fixture({}, ['transcript.segment'], 1)
        self.fixture({'kind': 'network_log'}, ['network.device'], 2)
        data = (await self.client.get(self.base + '/results', params={'operation': 'transcript'})).json()
        self.assertEqual(data['items'][0]['processing_run_id'], run)
        pinned = (await self.client.get(self.base + '/results', params={'operation': 'transcript', 'processing_run_id': run})).json()
        self.assertEqual(data['items'], pinned['items'])

    async def test_corrupt_output_rejected_without_disclosing_values(self):
        self.fixture({}, ['transcript.status'], 1)  # Invalid status text: neither silence nor no_audio.
        response = await self.client.get(self.base + '/results')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('Result 0', response.text)

    async def test_latest_attempt_status_and_empty_output_are_not_fabricated(self):
        await self.image_source()
        initial = (await self.client.get(self.base + '/results')).json()
        self.assertTrue(all(entry['status'] == 'not_run' and entry['count'] is None for entry in initial['operations']))
        completed = self.fixture({'kind': 'image', 'image_understanding': {'model': 'fixture'}}, [], 1)
        running = self.fixture({'kind': 'image'}, [], 2, 'running')
        data = (await self.client.get(self.base + '/results')).json()
        by_op = {entry['operation']: entry for entry in data['operations']}
        self.assertEqual(by_op['detection']['status'], 'running')
        self.assertEqual(by_op['detection']['latest_run_id'], running)
        self.assertEqual(by_op['detection']['output_run_id'], completed)
        self.assertEqual(by_op['ocr']['status'], 'completed')
        self.assertEqual(by_op['ocr']['count'], 0)
