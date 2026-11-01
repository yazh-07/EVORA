"""Synthetic event controls and real original/parser/normalizer/entity chain."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from jsonschema import Draft202012Validator, FormatChecker
from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.parsers.network_csv import parse_network_csv
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.normalization import normalize_observations
from backend.parsers.candidate_entities import project_candidate_entities
from backend.parsers.source_events import PROJECTOR_VERSION, SourceEventError, project_source_events

ROOT = Path(__file__).resolve().parents[2]


class SourceEventTests(unittest.TestCase):
    def setUp(self):
        self.case = uuid4()
        self.network = self.parse('network.csv', parse_network_csv)
        self.gps = self.parse('gps.csv', parse_gps_csv)
        self.sources = self.network + self.gps

    def parse(self, name, parser, data=None):
        return normalize_observations(parser(data if data is not None else (ROOT / 'fixtures/synthetic-case' / name).read_bytes(),
            case_id=self.case, evidence_id=uuid4(), processing_run_id=uuid4()))

    def candidates(self, sources=None):
        return project_candidate_entities(self.sources if sources is None else sources, case_id=self.case)

    def events(self, projection):
        return project_source_events(projection, case_id=self.case)

    def test_real_rows_source_membership_and_actual_participants(self):
        projection = self.candidates()
        results = self.events(projection)
        self.assertEqual(len(results), 3)
        self.assertEqual({x.event.kind for x in results}, {'network.activity', 'gps.location'})
        by_id = {x.observation.id: x.observation for x in projection.observations}
        entities = {x.id: x for x in projection.entities}
        for result in results:
            event = result.event
            self.assertEqual(result.version, PROJECTOR_VERSION)
            self.assertEqual(event.case_id, self.case)
            self.assertEqual(len(event.observation_ids), 3)
            self.assertEqual(len(event.evidence_ids), 1)
            self.assertEqual(event.confidence, 0)
            self.assertEqual(event.observation_ids, tuple(sorted(event.observation_ids, key=str)))
            self.assertEqual(event.entity_ids, tuple(sorted(event.entity_ids, key=str)))
            for oid in event.observation_ids:
                self.assertEqual(by_id[oid].evidence_id, event.evidence_ids[0])
                self.assertEqual(by_id[oid].case_id, event.case_id)
            for eid in event.entity_ids:
                self.assertEqual(entities[eid].case_id, event.case_id)
                self.assertTrue(set(entities[eid].observation_ids) & set(event.observation_ids))
            keys = {entities[eid].candidate_key for eid in event.entity_ids}
            self.assertEqual(len(keys), 1 if event.kind == 'gps.location' else 2)
            self.assertFalse({'device:D-7', 'device:D-8'} <= keys)

    def test_summaries_are_source_reports_and_not_event_classification(self):
        results = self.events(self.candidates())
        network = [x.event for x in results if x.event.kind == 'network.activity']
        self.assertTrue(all(x.summary == 'Network log reports: connected' for x in network))
        gps = next(x.event for x in results if x.event.kind == 'gps.location')
        self.assertEqual(gps.summary, 'GPS record reports device D-8 at latitude 12.9716, longitude 77.5946')

    def test_raw_summary_text_preserved_unexecuted_and_multiline_locators(self):
        data = b'timestamp,device_id,ip_address,event\n2026-01-12T10:01:00Z,D-7,203.0.113.7,"<script>untrusted</script>\nreported"\n'
        sources = self.parse('network.csv', parse_network_csv, data)
        self.assertTrue(all(x.observation.source_locator.startswith('rows 2-3, ') for x in sources))
        event = self.events(self.candidates(sources))[0].event
        self.assertEqual(event.summary, 'Network log reports: <script>untrusted</script>\nreported')
        self.assertEqual(set(event.observation_ids), {x.observation.id for x in sources})

    def test_identical_rows_are_separate_source_events_not_deduplicated_by_text_or_time(self):
        row = b'2026-01-12T10:01:00Z,D-7,203.0.113.7,connected\n'
        sources = self.parse('network.csv', parse_network_csv, b'timestamp,device_id,ip_address,event\n' + row + row)
        results = self.events(self.candidates(sources))
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0].event.id, results[1].event.id)
        self.assertTrue(set(results[0].event.observation_ids).isdisjoint(results[1].event.observation_ids))
        self.assertEqual(results[0].event.entity_ids, results[1].event.entity_ids)

    def test_raw_precision_utc_and_timezone_uncertainty_preserved(self):
        cases = [
            ('2026-01-12T15:32:00.123456789+05:30', 'resolved', '2026-01-12T10:02:00.123456789Z'),
            ('2026-01-12T10:02:00', 'missing_timezone', None),
            ('2026-01-12T10:02:00-00:00', 'unknown_offset', None),
            ('2026-11-01T01:30:00 IST', 'ambiguous_timezone', None),
            ('2026-02-30T10:02:00Z', 'invalid_timestamp', None),
            ('SECRET invalid source time', 'invalid_timestamp', None),
        ]
        for raw, status, utc in cases:
            sources = normalize_observations(tuple(replace(x.observation, observed_at_raw=raw) for x in self.network[:3]))
            result = self.events(self.candidates(sources))[0]
            self.assertEqual(result.event.observed_at_raw, raw)
            self.assertEqual(result.event.observed_at_utc, utc)
            self.assertEqual(result.time, sources[0].time)
            self.assertEqual(result.time.status, status)
            self.assertEqual('observed_at_utc' in result.event.to_wire(), utc is not None)

    def test_immutability_schema_and_no_internal_wire_fields(self):
        projection = self.candidates()
        before = [x.observation.to_wire() for x in projection.observations]
        entities_before = [x.to_wire() for x in projection.entities]
        results = self.events(projection)
        bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
        validator = Draft202012Validator(bundle['components']['schemas']['Event'], format_checker=FormatChecker())
        for result in results:
            wire = result.event.to_wire()
            validator.validate(wire)
            for key in ['time', 'version', 'status', 'source_offset', 'processing_run_id']:
                self.assertNotIn(key, wire)
            with self.assertRaises(FrozenInstanceError): result.event.summary = 'changed'
            with self.assertRaises(FrozenInstanceError): result.version = 'changed'
            wire['observation_ids'].clear()
            self.assertEqual(len(result.event.observation_ids), 3)
        self.assertEqual([x.observation.to_wire() for x in projection.observations], before)
        self.assertEqual([x.to_wire() for x in projection.entities], entities_before)

    def test_empty_input_and_reordering_not_lifecycle_replay(self):
        self.assertEqual(self.events(self.candidates(())), ())
        first_projection = self.candidates()
        first = self.events(first_projection)
        second = self.events(replace(first_projection, observations=tuple(reversed(first_projection.observations))))
        def content(results):
            return [{key: value for key, value in x.event.to_wire().items() if key != 'id'} for x in results]
        self.assertEqual(content(first), content(second))
        self.assertTrue(set(x.event.id for x in first).isdisjoint(x.event.id for x in second))

    def test_incomplete_and_duplicate_row_fields_reject_atomically(self):
        sources = self.network[:3]
        with self.assertRaises(SourceEventError) as caught:
            self.events(self.candidates(sources[:-1]))
        self.assertEqual(caught.exception.code, 'INCOMPLETE_ROW')
        duplicate = replace(sources[0], observation=replace(sources[0].observation, id=uuid4()))
        with self.assertRaises(SourceEventError) as caught:
            self.events(self.candidates(sources + (duplicate,)))
        self.assertEqual(caught.exception.code, 'DUPLICATE_ROW_FIELD')

    def test_invalid_wrong_column_and_overlapping_spans_reject(self):
        for locator in ['SECRET', 'row 1, device_id', 'rows 2-2, device_id', 'rows 3-2, device_id',
                        'row 2, event', 'row 02, device_id', 'row ' + '9' * 5000 + ', device_id']:
            sources = list(self.network)
            sources[0] = replace(sources[0], observation=replace(sources[0].observation, source_locator=locator))
            with self.assertRaises(SourceEventError) as caught: self.events(self.candidates(sources))
            self.assertEqual(caught.exception.code, 'INVALID_LOCATOR')
            self.assertNotIn('SECRET', str(caught.exception))
        sources = tuple(replace(x, observation=replace(x.observation, source_locator=x.observation.source_locator.replace('row 2,', 'rows 2-3,'))) for x in self.network)
        with self.assertRaises(SourceEventError) as caught: self.events(self.candidates(sources))
        self.assertEqual(caught.exception.code, 'OVERLAPPING_ROWS')

    def test_conflicting_raw_time_or_fabricated_utc_rejects(self):
        source = self.network[0]
        variants = [
            replace(source, observation=replace(source.observation, observed_at_utc='2026-01-01T00:00:00Z')),
            replace(source, time=replace(source.time, status='resolved SECRET')),
            replace(source, version='SECRET'),
        ]
        # Individually valid P03 times can still disagree within one logical row.
        variants.append(normalize_observations((replace(source.observation, observed_at_raw='2026-01-12T10:02:00Z'),))[0])
        for changed in variants:
            with self.assertRaises(SourceEventError) as caught:
                self.events(self.candidates((changed,) + self.network[1:3]))
            self.assertEqual(caught.exception.code, 'CONFLICTING_TIME')
            self.assertNotIn('SECRET', str(caught.exception))

    def test_invalid_coordinate_or_status_rejects(self):
        source = self.gps[1]
        for changed in [replace(source, observation=replace(source.observation, normalized_value='13')),
                        replace(source, observation=replace(source.observation, raw_value='SECRET')),
                        replace(source, coordinate_status='SECRET')]:
            with self.assertRaises(SourceEventError) as caught:
                self.events(self.candidates((self.gps[0], changed, self.gps[2])))
            self.assertEqual(caught.exception.code, 'INVALID_COORDINATE')
        changed = replace(self.network[0], coordinate_status='SECRET')
        with self.assertRaises(SourceEventError) as caught:
            self.events(self.candidates((changed,) + self.network[1:3]))
        self.assertEqual(caught.exception.code, 'INVALID_SOURCE')

    def test_missing_foreign_duplicate_or_altered_participants_reject(self):
        projection = self.candidates()
        entity = projection.entities[0]
        variants = [projection.entities[1:], projection.entities + (entity,),
                    (replace(entity, case_id=uuid4()),) + projection.entities[1:],
                    (replace(entity, observation_ids=(uuid4(),)),) + projection.entities[1:],
                    (replace(entity, evidence_ids=(uuid4(),)),) + projection.entities[1:],
                    (replace(entity, confidence=1),) + projection.entities[1:],
                    (replace(entity, canonical_label='SECRET'),) + projection.entities[1:],
                    (replace(entity, id=projection.entities[1].id),) + projection.entities[1:]]
        for entities in variants:
            with self.assertRaises(SourceEventError) as caught: self.events(replace(projection, entities=entities))
            self.assertEqual(caught.exception.code, 'INVALID_PARTICIPANT')
            self.assertNotIn('SECRET', str(caught.exception))

    def test_case_run_duplicates_bad_projection_and_no_implicit_keys_reject(self):
        projection = self.candidates()
        first = projection.observations[0]
        foreign = replace(first, observation=replace(first.observation, case_id=uuid4()))
        bad_run = replace(first, observation=replace(first.observation, processing_run_id=uuid4()))
        for source, code in [(foreign, 'CASE_MISMATCH'), (bad_run, 'CONFLICTING_RUN_CONTEXT'), (projection.observations[1], 'DUPLICATE_OBSERVATION')]:
            with self.assertRaises(SourceEventError) as caught:
                self.events(replace(projection, observations=(source,) + projection.observations[1:]))
            self.assertEqual(caught.exception.code, code)
        for invalid in [None, replace(projection, version='SECRET'), replace(projection, observations=list(projection.observations))]:
            with self.assertRaises(SourceEventError): self.events(invalid)
        with self.assertRaises(SourceEventError): project_source_events(projection, case_id='SECRET')
        with self.assertRaises(SourceEventError) as caught:
            self.events(replace(projection, observations=self.sources))
        self.assertEqual(caught.exception.code, 'INVALID_PROJECTION')

    def test_mixed_adapter_evidence_rejects_and_different_runs_evidence_stay_separate(self):
        network = self.network[0].observation
        gps = tuple(replace(x, observation=replace(x.observation, evidence_id=network.evidence_id,
                    processing_run_id=network.processing_run_id)) for x in self.gps)
        with self.assertRaises(SourceEventError) as caught: self.events(self.candidates(self.network + gps))
        self.assertEqual(caught.exception.code, 'MIXED_ADAPTER')
        results = self.events(self.candidates())
        self.assertEqual(len({x.event.evidence_ids for x in results}), 2)


class SourceEventOriginalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_originals_to_source_events_and_original_history_unchanged(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                token_verifier=SyntheticTokenVerifier({'p03c-synthetic-one': 'investigator-1', 'p03c-synthetic-two': 'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app), base_url='http://test',
                    headers={'Authorization': 'Bearer p03c-synthetic-one'}) as client:
                case = (await client.post('/api/v1/cases', json={'title': 'Synthetic P03C case'})).json()
                url = f"/api/v1/cases/{case['id']}/evidence"
                sources, originals = [], []
                for name, kind, parser in [('network.csv', 'network_log', parse_network_csv), ('gps.csv', 'gps', parse_gps_csv)]:
                    data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
                    response = await client.post(url, data={'kind': kind, 'source_label': 'Synthetic P03C'}, files={'file': (name, data, 'text/csv')})
                    self.assertEqual(response.status_code, 201)
                    evidence = response.json()
                    content_url = url + '/' + evidence['id'] + '/content'
                    downloaded = await client.get(content_url)
                    self.assertEqual(downloaded.status_code, 200)
                    self.assertEqual(downloaded.content, data)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), evidence['sha256'])
                    # Unpersisted caller run UUID; real P04 lifecycle remains a separate task.
                    sources.extend(normalize_observations(parser(downloaded.content, case_id=UUID(case['id']),
                        evidence_id=UUID(evidence['id']), processing_run_id=uuid4())))
                    originals.append((content_url, data))
                projection = project_candidate_entities(sources, case_id=UUID(case['id']))
                before = [x.observation.to_wire() for x in projection.observations]
                with app.state.database.connect() as connection:
                    before_sql = [tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')]
                results = project_source_events(projection, case_id=UUID(case['id']))
                self.assertEqual(len(results), 3)
                self.assertEqual([x.observation.to_wire() for x in projection.observations], before)
                by_id = {x.observation.id: x.observation for x in projection.observations}
                entity_ids = {x.id for x in projection.entities}
                for result in results:
                    event = result.event
                    self.assertTrue(set(event.entity_ids) <= entity_ids)
                    self.assertEqual({by_id[oid].evidence_id for oid in event.observation_ids}, set(event.evidence_ids))
                    self.assertTrue(all(by_id[oid].case_id == event.case_id for oid in event.observation_ids))
                for content_url, data in originals:
                    self.assertEqual((await client.get(content_url)).content, data)
                    self.assertEqual((await client.get(content_url, headers={'Authorization': 'Bearer p03c-synthetic-two'})).status_code, 404)
                    self.assertEqual((await client.get(content_url, headers={'Authorization': 'invalid'})).status_code, 401)
                with app.state.database.connect() as connection:
                    self.assertEqual([tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')], before_sql)
                    for row in connection.execute('SELECT storage_path,sha256 FROM evidence'):
                        self.assertEqual(hashlib.sha256(Path(row[0]).read_bytes()).hexdigest(), row[1])
