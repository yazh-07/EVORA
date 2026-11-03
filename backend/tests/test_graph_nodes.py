"""A01 synthetic negatives and real merged network/GPS producer integration."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
from itertools import permutations
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
from backend.graph_nodes import GraphNode, build_graph_nodes

ROOT = Path(__file__).resolve().parents[2]
CASE = 'aaaaaaaa-0000-4000-8000-000000000001'
OTHER_CASE = 'bbbbbbbb-0000-4000-8000-000000000001'
E1 = 'eeeeeeee-0000-4000-8000-000000000001'
E2 = 'eeeeeeee-0000-4000-8000-000000000002'
ENTITY = 'cccccccc-0000-4000-8000-000000000001'
EVENT = 'dddddddd-0000-4000-8000-000000000001'
BAD_UUIDS = ('bad', E1.upper(), E1.replace('-', ''), '{' + E1 + '}',
             'urn:uuid:' + E1, ' ' + E1, E1 + ' ', '', None, 1, True, UUID(E1))


def validator(name):
    # Fail if the real bundle is unavailable; never replace it with a test schema.
    bundle = json.loads(Path(os.environ['EVORA_CONTRACT_BUNDLE']).read_text(encoding='utf-8'))
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
              '$ref': '#/components/schemas/' + name, 'components': bundle['components']}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


class GraphNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = validator('GraphNode')

    def setUp(self):
        self.evidence = [dict(id=E2, case_id=CASE, filename='gps.csv'),
                         dict(id=E1, case_id=CASE, filename='network.csv')]
        self.entities = [dict(id=ENTITY, case_id=CASE, kind='device',
                              canonical_label='D-7', evidence_ids=[E1])]
        self.events = [dict(id=EVENT, case_id=CASE, kind='network.connection',
                            summary='Source reports a connection', evidence_ids=[E1])]

    def build(self, evidence=None, entities=None, events=None):
        nodes = build_graph_nodes(CASE, self.evidence if evidence is None else evidence,
                                  self.entities if entities is None else entities,
                                  self.events if events is None else events)
        for node in nodes:
            self.schema.validate(node.to_wire())
        return nodes

    def test_exact_source_ids_labels_kinds_and_wire_fields(self):
        nodes = self.build()
        by_id = {node.id: node.to_wire() for node in nodes}
        self.assertEqual(set(by_id), {E1, E2, ENTITY, EVENT})
        self.assertEqual(by_id[E1], dict(id=E1, case_id=CASE, kind='evidence',
                                       label='network.csv', evidence_ids=[E1]))
        self.assertEqual(by_id[ENTITY], dict(id=ENTITY, case_id=CASE, kind='device',
                                           label='D-7', evidence_ids=[E1]))
        self.assertEqual(by_id[EVENT], dict(id=EVENT, case_id=CASE, kind='network.connection',
                                          label='Source reports a connection', evidence_ids=[E1]))
        for node in nodes:
            self.assertEqual(node.id, str(UUID(node.id)))
            self.assertEqual(set(node.to_wire()), {'id', 'case_id', 'kind', 'label', 'evidence_ids'})

    def test_no_observation_ids_required_or_copied_and_full_records_accepted(self):
        self.entities[0].update(observation_ids=[str(uuid4())], candidate_key='device:D-7', confidence=0)
        self.events[0].update(observation_ids=[str(uuid4())], entity_ids=[ENTITY], confidence=0)
        self.evidence[0].update(sha256='1' * 64, size_bytes=0, source_label='Synthetic')
        self.assertEqual(len(self.build()), 4)

    def test_empty_case_and_evidence_only_are_valid_without_scoring(self):
        self.assertEqual(build_graph_nodes(CASE, [], [], []), [])
        self.assertEqual(len(self.build(entities=[], events=[])), 2)
        self.assertEqual(len(self.build(evidence=self.evidence[:1], entities=[], events=[])), 1)

    def test_label_fallback_and_untrusted_unicode_text_preserved(self):
        evidence = dict(id=E1, case_id=CASE, label='  <script>synthetic</script> café\n')
        self.assertEqual(next(x for x in self.build(evidence=[evidence]) if x.id == E1).label, evidence['label'])
        evidence['filename'] = 'filename wins.csv'
        self.assertEqual(next(x for x in self.build(evidence=[evidence]) if x.id == E1).label, evidence['filename'])

    def test_duplicate_records_merge_sorted_unique_sources_for_entity_and_event(self):
        entity = dict(self.entities[0], evidence_ids=[E2, E1, E2])
        event = dict(self.events[0], evidence_ids=[E2, E2])
        nodes = self.build(evidence=self.evidence * 2, entities=self.entities + [entity], events=self.events + [event])
        self.assertEqual(len(nodes), 4)
        for node in nodes:
            self.assertEqual(node.evidence_ids, (E1, E2) if node.id in (ENTITY, EVENT) else (node.id,))
        self.assertEqual(nodes, self.build(evidence=self.evidence, entities=[entity], events=[dict(event, evidence_ids=[E1, E2])]))

    def test_canonical_order_independent_of_inputs_and_iterable_support(self):
        entities = self.entities + [dict(self.entities[0], id=OTHER_CASE, kind='person', canonical_label='Synthetic person')]
        events = self.events + [dict(self.events[0], id=CASE, kind='gps.fix', evidence_ids=[E2])]
        expected = self.build(entities=entities, events=events)
        self.assertEqual([(x.kind, x.id) for x in expected], sorted((x.kind, x.id) for x in expected))
        for evidence_order in permutations(self.evidence):
            for entity_order in permutations(entities):
                for event_order in permutations(events):
                    self.assertEqual(expected, build_graph_nodes(CASE, iter(evidence_order), iter(entity_order), iter(event_order)))

    def test_identical_labels_with_distinct_source_uuids_remain_distinct(self):
        other = dict(self.entities[0], id=OTHER_CASE, evidence_ids=[E2])
        nodes = self.build(entities=self.entities + [other])
        self.assertEqual(len(nodes), 5)
        candidates = [node for node in nodes if node.kind == 'device']
        self.assertEqual({node.id for node in candidates}, {ENTITY, OTHER_CASE})
        self.assertEqual({node.label for node in candidates}, {'D-7'})
        self.assertEqual({node.evidence_ids for node in candidates}, {(E1,), (E2,)})

    def test_inputs_and_previous_results_immutable_and_serialization_detached(self):
        original = deepcopy((self.evidence, self.entities, self.events))
        nodes = self.build()
        before = [node.to_wire() for node in nodes]
        self.build(entities=self.entities + [dict(self.entities[0], evidence_ids=[E2])])
        self.assertEqual((self.evidence, self.entities, self.events), original)
        self.assertEqual([node.to_wire() for node in nodes], before)
        with self.assertRaises(FrozenInstanceError):
            nodes[0].label = 'changed'
        nodes[0].to_wire()['evidence_ids'].clear()
        self.assertEqual([node.to_wire() for node in nodes], before)

    def test_invalid_requested_case_rejected_even_for_empty_input(self):
        for bad in BAD_UUIDS:
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'case_id.*canonical UUID'):
                build_graph_nodes(bad, [], [], [])

    def test_invalid_source_ids_and_case_ids_rejected_in_every_category(self):
        for records in (self.evidence, self.entities, self.events):
            for field in ('id', 'case_id'):
                for bad in BAD_UUIDS:
                    with self.subTest(field=field, bad=bad), self.assertRaisesRegex(ValueError, 'canonical UUID'):
                        original = records[0]
                        records[0] = dict(original, **{field: bad})
                        try:
                            self.build()
                        finally:
                            records[0] = original

    def test_foreign_case_records_rejected_even_if_duplicate_is_valid(self):
        for records in (self.evidence, self.entities, self.events):
            foreign = dict(records[0], case_id=OTHER_CASE)
            records.append(foreign)
            with self.assertRaisesRegex(ValueError, 'case_id does not match'):
                self.build()
            records.pop()

    def test_foreign_or_absent_evidence_references_rejected_without_inventing_nodes(self):
        for category in ('entities', 'events'):
            for references in ([OTHER_CASE], [E1, OTHER_CASE]):
                records = getattr(self, category)
                with self.subTest(category=category, references=references), self.assertRaisesRegex(ValueError, 'outside the supplied case'):
                    self.build(**{category: [dict(records[0], evidence_ids=references)]})
        with self.assertRaisesRegex(ValueError, 'outside the supplied case'):
            self.build(evidence=[])

    def test_invalid_evidence_references_and_empty_nonarray_values(self):
        for category in ('entities', 'events'):
            record = getattr(self, category)[0]
            for bad in BAD_UUIDS:
                with self.subTest(category=category, bad=bad), self.assertRaisesRegex(ValueError, 'canonical UUID'):
                    self.build(**{category: [dict(record, evidence_ids=[bad])]})
            for refs in ([], (), None, E1, {E1}, {E1: True}, 1):
                with self.subTest(category=category, refs=refs), self.assertRaisesRegex(ValueError, 'nonempty list or tuple'):
                    self.build(**{category: [dict(record, evidence_ids=refs)]})

    def test_blank_missing_and_nonstring_labels_and_kinds_rejected(self):
        for category, field in (('evidence', 'filename'), ('entities', 'canonical_label'),
                                ('events', 'summary'), ('entities', 'kind'), ('events', 'kind')):
            record = getattr(self, category)[0]
            for value in ('', ' \t\n', None, 0, False, ['label']):
                with self.subTest(category=category, field=field, value=value), self.assertRaisesRegex(ValueError, 'nonblank string'):
                    self.build(**{category: [dict(record, **{field: value})]})
            missing = dict(record)
            del missing[field]
            with self.assertRaisesRegex(ValueError, 'nonblank string'):
                self.build(**{category: [missing]})

    def test_missing_identifiers_references_and_nonmapping_records_fail_cleanly(self):
        for category in ('evidence', 'entities', 'events'):
            for field in ('id', 'case_id') + (() if category == 'evidence' else ('evidence_ids',)):
                missing = dict(getattr(self, category)[0])
                del missing[field]
                with self.subTest(category=category, field=field), self.assertRaises(ValueError):
                    self.build(**{category: [missing]})
            for bad in (None, [None], ['record'], [1]):
                # Direct call avoids this helper's None-as-default shorthand.
                arguments = dict(evidence_records=self.evidence, entity_records=self.entities, event_records=self.events)
                arguments[{'evidence': 'evidence_records', 'entities': 'entity_records', 'events': 'event_records'}[category]] = bad
                with self.subTest(category=category, bad=bad), self.assertRaisesRegex(ValueError, 'mapping'):
                    build_graph_nodes(CASE, **arguments)

    def test_conflicting_duplicate_label_kind_or_category_rejected_in_both_orders(self):
        for category, field in (('evidence', 'filename'), ('entities', 'canonical_label'),
                                ('events', 'summary'), ('entities', 'kind'), ('events', 'kind')):
            record = getattr(self, category)[0]
            for records in permutations((record, dict(record, **{field: 'different'}))):
                with self.subTest(category=category, field=field), self.assertRaisesRegex(ValueError, 'conflicting'):
                    self.build(**{category: records})
        for id_value, kind, label in ((E1, 'evidence', 'network.csv'), (EVENT, 'network.connection', self.events[0]['summary'])):
            with self.assertRaisesRegex(ValueError, 'conflicting category'):
                self.build(entities=[dict(self.entities[0], id=id_value, kind=kind, canonical_label=label)])

    def test_node_constructor_strictness_and_schema_negative_controls(self):
        node = self.build()[0]
        for extra in ('observation_ids', 'confidence', 'analysis_run_id', 'unexpected'):
            with self.subTest(extra=extra), self.assertRaises(TypeError):
                GraphNode(**dict(id=node.id, case_id=CASE, kind=node.kind, label=node.label,
                                 evidence_ids=node.evidence_ids, **{extra: []}))
            self.assertFalse(self.schema.is_valid(dict(node.to_wire(), **{extra: []})))
        for refs in ((), [], (E1, E1), (E2, E1), ('invalid',)):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                replace(node, evidence_ids=refs)
        for field in ('id', 'case_id', 'kind', 'label', 'evidence_ids'):
            missing = node.to_wire()
            del missing[field]
            self.assertFalse(self.schema.is_valid(missing))
        for field, bad in (('id', 'invalid'), ('case_id', 'invalid'), ('label', 1),
                           ('kind', None), ('evidence_ids', []), ('evidence_ids', [E1, E1]), ('evidence_ids', ['bad'])):
            self.assertFalse(self.schema.is_valid(dict(node.to_wire(), **{field: bad})))
        # Draft label has no minLength/pattern: blank rejection is builder policy.
        self.assertTrue(self.schema.is_valid(dict(node.to_wire(), label='')))
        with self.assertRaisesRegex(ValueError, 'label.*nonblank'):
            replace(node, label='')

    def test_graph_envelopes_validate_without_claiming_analysis_publication(self):
        graph_schema = validator('Graph')
        graph_schema.validate(dict(case_id=CASE, nodes=[], edges=[]))
        graph = dict(case_id=CASE, nodes=[x.to_wire() for x in self.build()], edges=[])
        self.assertFalse(graph_schema.is_valid(graph))
        # Schema-only envelope fixture; no analysis run or Neo4j write is made.
        graph_schema.validate(dict(graph, analysis_run_id=OTHER_CASE))


class RealProducerGraphNodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_upload_processing_source_joins_and_case_isolation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                             token_verifier=SyntheticTokenVerifier({'a01-synthetic-one': 'investigator-1',
                                                                    'a01-synthetic-two': 'investigator-2'}))
            async with app.router.lifespan_context(app):
                async with AsyncClient(transport=ASGITransport(app), base_url='http://test',
                                       headers={'Authorization': 'Bearer a01-synthetic-one'}) as client:
                    response = await client.post('/api/v1/cases', json={'title': 'Synthetic A01 case'})
                    self.assertEqual(response.status_code, 201)
                    case = response.json()['id']
                    base = f'/api/v1/cases/{case}'
                    originals = {}
                    for name, kind in (('network.csv', 'network_log'), ('gps.csv', 'gps')):
                        data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
                        response = await client.post(base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic A01'},
                                                     files={'file': (name, data, 'text/csv')})
                        self.assertEqual(response.status_code, 201, response.text)
                        evidence = response.json()
                        originals[evidence['id']] = data
                        response = await client.post(base + f"/evidence/{evidence['id']}/processing-runs",
                                                     headers={'Idempotency-Key': str(uuid4())})
                        self.assertEqual(response.status_code, 202, response.text)
                        run_id = response.json()['id']
                        response = await client.get(base + f"/evidence/{evidence['id']}/processing-runs/{run_id}")
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['status'], 'completed', response.text)

                    pages = {}
                    for path, schema in (('evidence', 'Evidence'), ('entities', 'Entity'), ('events', 'Event'), ('observations', 'Observation')):
                        response = await client.get(base + '/' + path, params={'limit': 100})
                        self.assertEqual(response.status_code, 200, response.text)
                        page = response.json()
                        self.assertEqual(len(page['items']), page['total'])
                        pages[path] = page['items']
                        for record in page['items']:
                            validator(schema).validate(record)

                    before = deepcopy(pages)
                    nodes = build_graph_nodes(case, pages['evidence'], pages['entities'], pages['events'])
                    self.assertEqual(len(nodes), 10)  # 2 Evidence, 5 candidates, 3 source Events.
                    self.assertEqual({node.id for node in nodes}, {r['id'] for key in ('evidence', 'entities', 'events') for r in pages[key]})
                    observations = {o['id']: o for o in pages['observations']}
                    by_id = {node.id: node for node in nodes}
                    for node in nodes:
                        validator('GraphNode').validate(node.to_wire())
                        self.assertEqual(node.case_id, case)
                        self.assertTrue(set(node.evidence_ids) <= originals.keys())
                    for key, label in (('entities', 'canonical_label'), ('events', 'summary')):
                        for record in pages[key]:
                            node = by_id[record['id']]
                            self.assertEqual((node.kind, node.label), (record['kind'], record[label]))
                            self.assertEqual(set(node.evidence_ids), {observations[oid]['evidence_id'] for oid in record['observation_ids']})
                            for oid in record['observation_ids']:
                                self.assertEqual(observations[oid]['case_id'], case)
                                self.assertTrue(observations[oid]['source_locator'])
                    devices = [r for r in pages['entities'] if r['kind'] == 'device']
                    self.assertEqual({r['canonical_label'] for r in devices}, {'D-7', 'D-8', 'D-9'})
                    self.assertEqual(len({by_id[r['id']].id for r in devices}), 3)

                    foreign_headers = {'Authorization': 'Bearer a01-synthetic-two'}
                    response = await client.post('/api/v1/cases', json={'title': 'Synthetic foreign case'}, headers=foreign_headers)
                    self.assertEqual(response.status_code, 201)
                    foreign_case = response.json()['id']
                    response = await client.post(f'/api/v1/cases/{foreign_case}/evidence', headers=foreign_headers,
                                                 data={'kind': 'network_log', 'source_label': 'Synthetic foreign'},
                                                 files={'file': ('foreign.csv', next(iter(originals.values())), 'text/csv')})
                    self.assertEqual(response.status_code, 201)
                    foreign_evidence = response.json()
                    response = await client.get(f'/api/v1/cases/{foreign_case}/evidence')
                    self.assertEqual(response.status_code, 404)
                    with self.assertRaisesRegex(ValueError, 'case_id does not match'):
                        build_graph_nodes(case, pages['evidence'] + [foreign_evidence], pages['entities'], pages['events'])
                    for key in ('entities', 'events'):
                        for changes in ({'case_id': foreign_case}, {'evidence_ids': [foreign_evidence['id']]}):
                            selected = dict(pages)
                            selected[key] = pages[key] + [dict(pages[key][0], **changes)]
                            with self.assertRaises(ValueError):
                                build_graph_nodes(case, selected['evidence'], selected['entities'], selected['events'])

                    self.assertEqual(pages, before)
                    self.assertEqual(nodes, build_graph_nodes(case, pages['evidence'], pages['entities'], pages['events']))
                    for evidence in pages['evidence']:
                        response = await client.get(base + f"/evidence/{evidence['id']}/content")
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.content, originals[evidence['id']])
                        self.assertEqual(hashlib.sha256(response.content).hexdigest(), evidence['sha256'])


if __name__ == '__main__':
    unittest.main()
