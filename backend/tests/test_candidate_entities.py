"""Synthetic candidate controls and real original -> P01/P02/P03 integration."""
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
from backend.parsers.candidate_entities import (
    PROJECTOR_VERSION, CandidateEntityError, CandidateObservation, project_candidate_entities,
)

ROOT = Path(__file__).resolve().parents[2]


class CandidateEntityTests(unittest.TestCase):
    def setUp(self):
        self.case = uuid4()
        self.network = normalize_observations(parse_network_csv(
            (ROOT / 'fixtures/synthetic-case/network.csv').read_bytes(),
            case_id=self.case, evidence_id=uuid4(), processing_run_id=uuid4()))
        self.gps = normalize_observations(parse_gps_csv(
            (ROOT / 'fixtures/synthetic-case/gps.csv').read_bytes(),
            case_id=self.case, evidence_id=uuid4(), processing_run_id=uuid4()))

    def project(self, values):
        return project_candidate_entities(values, case_id=self.case)

    def identifier(self, value, source=None):
        source = source or self.network[0]
        return replace(source, observation=replace(source.observation, id=uuid4(), raw_value=value, normalized_value=value))

    def test_real_fixture_candidates_remain_distinct_and_source_backed(self):
        result = self.project(self.network + self.gps)
        keys = {item.candidate_key for item in result.entities}
        self.assertTrue({'device:D-7', 'device:D-8', 'device:D-9'} <= keys)
        self.assertEqual(len(result.entities), 5)
        self.assertEqual(result.version, PROJECTOR_VERSION)
        by_id = {item.observation.id: item.observation for item in result.observations}
        for entity in result.entities:
            self.assertEqual(entity.case_id, self.case)
            self.assertEqual(entity.confidence, 0)
            self.assertTrue(entity.observation_ids)
            self.assertEqual(set(entity.evidence_ids), {by_id[oid].evidence_id for oid in entity.observation_ids})
            for oid in entity.observation_ids:
                self.assertEqual(by_id[oid].entity_key, entity.candidate_key)
                self.assertTrue(by_id[oid].source_locator)
        self.assertNotEqual(next(x.id for x in result.entities if x.candidate_key == 'device:D-7'),
                            next(x.id for x in result.entities if x.candidate_key == 'device:D-8'))

    def test_exact_identical_key_groups_across_evidence_with_unique_sorted_sources(self):
        gps_device = self.identifier('D-7', self.gps[0])
        repeat = self.identifier('D-7')
        sources = (self.network[0], repeat, gps_device)
        result = self.project(sources)
        self.assertEqual(len(result.entities), 1)
        entity = result.entities[0]
        self.assertEqual(entity.candidate_key, 'device:D-7')
        self.assertEqual(entity.canonical_label, 'D-7')
        self.assertEqual(entity.kind, 'device')
        self.assertEqual(entity.evidence_ids, tuple(sorted({x.observation.evidence_id for x in sources}, key=str)))
        self.assertEqual(entity.observation_ids, tuple(sorted({x.observation.id for x in sources}, key=str)))
        self.assertEqual(entity.confidence, 0)

    def test_case_whitespace_unicode_and_punctuation_not_silently_rewritten(self):
        labels = ['D-7', 'd-7', ' D-7 ', 'D–7', 'Ｄ-7', 'device:D-7', 'D-7\nextra']
        result = self.project(tuple(self.identifier(value) for value in labels))
        self.assertEqual({x.candidate_key for x in result.entities}, {'device:' + value for value in labels})
        self.assertEqual({x.canonical_label for x in result.entities}, set(labels))

    def test_ip_namespace_and_source_spelling_no_inferred_address_equivalence(self):
        values = (self.identifier('203.0.113.7'), self.identifier('203.0.113.7', self.network[1]),
                  self.identifier('2001:0db8::1', self.network[1]), self.identifier('2001:db8::1', self.network[1]))
        result = self.project(values)
        self.assertEqual({x.candidate_key for x in result.entities},
                         {'device:203.0.113.7', 'ip:203.0.113.7', 'ip:2001:0db8::1', 'ip:2001:db8::1'})
        self.assertEqual({x.kind for x in result.entities}, {'device', 'ip'})

    def test_nonidentifiers_do_not_infer_location_or_event_entities(self):
        sources = (self.network[2], self.gps[1], self.gps[2])
        result = self.project(sources)
        self.assertEqual(result.entities, ())
        for before, after in zip(sources, result.observations):
            self.assertEqual(before, after)
            self.assertNotIn('entity_key', after.observation.to_wire())

    def test_all_source_fields_and_time_uncertainty_preserved(self):
        sources = self.network + self.gps
        before = [x.observation.to_wire() for x in sources]
        result = self.project(sources)
        for original, projected, wire in zip(sources, result.observations, before):
            output = projected.observation.to_wire()
            output.pop('entity_key', None)
            self.assertEqual(output, wire)
            self.assertEqual(projected.time, original.time)
            self.assertEqual(projected.coordinate_status, original.coordinate_status)
            self.assertEqual(projected.version, original.version)
        self.assertEqual([x.observation.to_wire() for x in sources], before)

    def test_missing_unknown_and_ambiguous_times_do_not_create_identity_certainty(self):
        for suffix in ['', '-00:00', ' IST']:
            raw = '2026-01-12T10:02:00' + suffix
            source = replace(self.network[0].observation, observed_at_raw=raw)
            normalized = normalize_observations((source,))
            output = self.project(normalized)
            self.assertEqual(output.observations[0].time, normalized[0].time)
            self.assertNotIn('observed_at_utc', output.observations[0].observation.to_wire())
            self.assertEqual(output.entities[0].confidence, 0)

    def test_extraction_score_preserved_without_candidate_confidence_boost(self):
        source = replace(self.network[0], observation=replace(self.network[0].observation, extraction_confidence=0.7))
        output = self.project((source, self.identifier('D-7')))
        self.assertEqual(output.observations[0].observation.extraction_confidence, 0.7)
        self.assertEqual(output.entities[0].confidence, 0)

    def test_schema_for_entities_and_keyed_observations(self):
        bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
        schemas = bundle['components']['schemas']
        result = self.project(self.network + self.gps)
        for name, values in [('Entity', result.entities), ('Observation', [x.observation for x in result.observations])]:
            validator = Draft202012Validator(schemas[name], format_checker=FormatChecker())
            for item in values:
                validator.validate(item.to_wire())

    def test_immutable_records_and_fresh_wire_containers(self):
        result = self.project(self.network)
        with self.assertRaises(FrozenInstanceError): result.version = 'changed'
        with self.assertRaises(FrozenInstanceError): result.entities[0].confidence = 1
        with self.assertRaises(FrozenInstanceError): result.observations[0].observation.entity_key = 'changed'
        wire = result.entities[0].to_wire()
        wire['evidence_ids'].clear()
        self.assertTrue(result.entities[0].evidence_ids)
        observation = result.observations[0].observation
        copy = observation.to_wire(); copy['raw_value'] = 'changed'
        self.assertNotEqual(observation.raw_value, 'changed')

    def test_reordered_inputs_stable_content_with_new_unpublished_record_ids(self):
        sources = self.network + self.gps
        first = self.project(sources)
        second = self.project(reversed(sources))
        def content(result):
            return [{key: value for key, value in entity.to_wire().items() if key != 'id'} for entity in result.entities]
        self.assertEqual(content(first), content(second))
        self.assertTrue(set(x.id for x in first.entities).isdisjoint(x.id for x in second.entities))
        self.assertEqual(content(first), content(self.project(first.observations)))
        self.assertEqual(self.project(()).entities, ())
        self.assertEqual(self.project(()).observations, ())

    def test_mixed_case_rejected_and_equal_keys_never_share_entity_record_ids(self):
        other = uuid4()
        foreign = replace(self.network[0], observation=replace(self.network[0].observation, case_id=other))
        with self.assertRaises(CandidateEntityError) as caught: self.project((self.network[0], foreign))
        self.assertEqual(caught.exception.code, 'CASE_MISMATCH')
        separate = project_candidate_entities((foreign,), case_id=other)
        local = self.project((self.network[0],))
        self.assertNotEqual(local.entities[0].id, separate.entities[0].id)
        self.assertNotEqual(local.entities[0].case_id, separate.entities[0].case_id)

    def test_duplicate_or_conflicting_input_rejects_atomically_without_raw_diagnostics(self):
        first = self.network[0]
        def changed(**fields): return replace(first, observation=replace(first.observation, id=uuid4(), **fields))
        invalid = [
            (first, 'DUPLICATE_OBSERVATION'),
            (changed(processing_run_id=uuid4()), 'CONFLICTING_RUN_CONTEXT'),
            (changed(evidence_id=uuid4()), 'CONFLICTING_RUN_CONTEXT'),
            (changed(case_id='SECRET'), 'INVALID_CONTEXT'),
            (changed(kind='SECRET'), 'UNSUPPORTED_KIND'),
            (changed(kind=['SECRET']), 'UNSUPPORTED_KIND'),
            (changed(source_locator=''), 'INVALID_SOURCE'),
            (changed(extraction_confidence=float('nan')), 'INVALID_SOURCE'),
            (changed(extraction_confidence=True), 'INVALID_SOURCE'),
            (changed(raw_value='SECRET', normalized_value=' '), 'INVALID_IDENTIFIER'),
            (changed(raw_value='SECRET', normalized_value='different'), 'INVALID_IDENTIFIER'),
            (None, 'INVALID_OBSERVATION'),
        ]
        for source, code in invalid:
            with self.subTest(code=code):
                with self.assertRaises(CandidateEntityError) as caught: self.project((first, source))
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn('SECRET', str(caught.exception))
        with self.assertRaises(CandidateEntityError): project_candidate_entities((), case_id='SECRET')

    def test_invalid_ip_and_preassigned_key_conflicts_reject(self):
        for value in ['999.1.1.1', 'fe80::1%SECRET', ' 203.0.113.7', 'SECRET']:
            with self.assertRaises(CandidateEntityError) as caught:
                self.project((self.identifier(value, self.network[1]),))
            self.assertEqual(caught.exception.code, 'INVALID_IDENTIFIER')
            self.assertNotIn('SECRET', str(caught.exception))
        keyed = self.project((self.network[0],)).observations[0]
        wrong = replace(keyed, observation=replace(keyed.observation, entity_key='device:SECRET'))
        with self.assertRaises(CandidateEntityError) as caught: self.project((wrong,))
        self.assertEqual(caught.exception.code, 'CONFLICTING_KEY')


class CandidateOriginalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_real_authorized_originals_to_candidates_no_storage_or_history_mutation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'p03b-synthetic-one': 'investigator-1', 'p03b-synthetic-two': 'investigator-2'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app), base_url='http://test',
                    headers={'Authorization': 'Bearer p03b-synthetic-one'}) as client:
                case = (await client.post('/api/v1/cases', json={'title': 'Synthetic P03B case'})).json()
                url = f"/api/v1/cases/{case['id']}/evidence"
                sources, originals = [], []
                for name, kind, parser in [('network.csv', 'network_log', parse_network_csv), ('gps.csv', 'gps', parse_gps_csv)]:
                    data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
                    response = await client.post(url, data={'kind': kind, 'source_label': 'Synthetic P03B'}, files={'file': (name, data, 'text/csv')})
                    self.assertEqual(response.status_code, 201)
                    evidence = response.json()
                    content_url = url + '/' + evidence['id'] + '/content'
                    downloaded = await client.get(content_url)
                    self.assertEqual(downloaded.status_code, 200)
                    self.assertEqual(downloaded.content, data)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), evidence['sha256'])
                    # Caller run UUID is synthetic/unpersisted; P04 lifecycle is separate.
                    sources.extend(normalize_observations(parser(downloaded.content, case_id=UUID(case['id']),
                                   evidence_id=UUID(evidence['id']), processing_run_id=uuid4())))
                    originals.append((content_url, data))
                with app.state.database.connect() as connection:
                    before_sql = [tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')]
                before = [x.observation.to_wire() for x in sources]
                result = project_candidate_entities(sources, case_id=UUID(case['id']))
                self.assertEqual(len(result.entities), 5)
                self.assertEqual(len(result.observations), 9)
                self.assertEqual([x.observation.to_wire() for x in sources], before)
                by_id = {x.observation.id: x.observation for x in sources}
                for entity in result.entities:
                    self.assertEqual(set(entity.evidence_ids), {by_id[oid].evidence_id for oid in entity.observation_ids})
                    self.assertTrue(all(by_id[oid].case_id == UUID(case['id']) for oid in entity.observation_ids))
                for content_url, data in originals:
                    self.assertEqual((await client.get(content_url)).content, data)
                    self.assertEqual((await client.get(content_url, headers={'Authorization': 'Bearer p03b-synthetic-two'})).status_code, 404)
                    self.assertEqual((await client.get(content_url, headers={'Authorization': 'invalid'})).status_code, 401)
                with app.state.database.connect() as connection:
                    self.assertEqual([tuple(row) for row in connection.execute('SELECT * FROM evidence ORDER BY id')], before_sql)
                    for row in connection.execute('SELECT storage_path,sha256 FROM evidence'):
                        self.assertEqual(hashlib.sha256(Path(row[0]).read_bytes()).hexdigest(), row[1])
