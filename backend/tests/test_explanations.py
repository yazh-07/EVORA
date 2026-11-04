"""A15 faithfulness, ablation, strict bundle and real published API read-back."""
from copy import deepcopy
import unittest
from uuid import UUID, uuid4

from backend.graph_links import derive_candidate_links
from backend.parsers.gps_csv import parse_gps_csv
from backend.parsers.network_csv import parse_network_csv
from backend.tests import test_analysis as lifecycle
from backend.tests.test_graph_links import NETWORK, GPS_SHARED, projected
from backend.tests.test_graph_nodes import validator
from backend.tests.test_triage_aggregation import factor, result_validator, CASE, RUN, IDS, TIME
from backend.triage.aggregation import aggregate_triage_result
from backend.triage.explanations import (
    evaluate_counterfactual_sensitivity, generate_finding_explanation,
    generate_triage_explanation,
)
from backend.triage.goldens import ROUNDING_CAP_CONTROL


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.case = str(uuid4())
        target, first = projected(UUID(self.case), NETWORK, parse_network_csv)
        other, second = projected(UUID(self.case), GPS_SHARED, parse_gps_csv)
        self.target, self.entities = target, target + other
        self.observations = first + second
        self.by_id = {o['id']: o for o in self.observations}
        self.eid = first[0]['evidence_id']
        self.edges, findings = derive_candidate_links(self.case, str(uuid4()), self.entities, self.observations)
        self.finding = findings[0].to_wire()

    def result(self, factors=None):
        return aggregate_triage_result(case_id=CASE, analysis_run_id=RUN, evidence_id=IDS[0],
            observation_count=1, factors=factors or [factor(), factor('connectivity', .1)],
            case_evidence_ids=IDS, created_at=TIME)

    def sensitivity(self, **changes):
        args = dict(evidence_id=self.eid, case_id=self.case, entities=self.target,
                    observations=self.observations, removed_entity_key='device:D-7',
                    all_case_entities=self.entities, edges=self.edges)
        return evaluate_counterfactual_sensitivity(**(args | changes))

    def test_exact_arithmetic_basis_and_aggregation_wiring(self):
        result = self.result()
        text = generate_triage_explanation(result)
        self.assertEqual(text, result['explanation'])
        for expected in ('48.88 points, P3', 'base weight 0.25', 'base weight 0.2',
                         'normalized weight 0.5555555555555556', 'value 0.8',
                         '= 44.44 points', '= 4.44 points', 'sum 48.88',
                         'Synthetic supported observation', 'Absent factors omitted',
                         'SHAP/learned feature importance is not applicable', 'not truth'):
            self.assertIn(expected, text)
        self.assertIn(IDS[0], text)
        self.assertNotIn('base weight 0.15', text)

    def test_rounding_cap_and_zero_retains_weight(self):
        result = self.result([factor(n, v) for n, v in ROUNDING_CAP_CONTROL['factor_values'].items()])
        self.assertIn('100.01 capped at 100.00', result['explanation'])
        self.assertIn('score = min(100.00, 100.01) = 100.00', result['explanation'])
        zero = self.result([factor(value=1), factor('connectivity', 0)])
        self.assertEqual(zero['score'], 55.56)
        self.assertIn('= 0.00 points', zero['explanation'])

    def test_finding_exact_locators_and_uncertainty(self):
        text = generate_finding_explanation(self.finding, self.by_id)
        for oid in self.finding['observation_ids']:
            source = self.by_id[oid]
            self.assertIn(source['source_locator'], text)
            self.assertIn(source['evidence_id'], text)
            self.assertIn(oid, text)
            self.assertIn('row ', source['source_locator'])
            self.assertIn(', device_id', source['source_locator'])
        self.assertIn('candidate_link_shared_identifier:v1', text)
        self.assertIn('device:D-7', text)
        self.assertIn('unassessed association', text)
        self.assertIn('source independence are unverified', text)
        self.assertNotIn('device:D-8', text)

    def test_counterfactual_real_producers_and_immutable_inputs(self):
        before = deepcopy((self.entities, self.observations, self.edges))
        baseline, counter = self.sensitivity()
        self.assertEqual(baseline['score'], 48.88)
        self.assertEqual(counter['score'], 33.33)
        self.assertEqual([f['value'] for f in baseline['factors']], [.8, .1])
        self.assertEqual([f['value'] for f in counter['factors']], [.6, 0.])
        self.assertIn('device:D-7', baseline['explanation'])
        self.assertNotIn('device:D-7', counter['explanation'])
        self.assertNotEqual(baseline['explanation'], counter['explanation'])
        remaining = [e for e in self.entities if not
                     (self.eid in e['evidence_ids'] and e['candidate_key'] == 'device:D-7')]
        self.assertEqual(derive_candidate_links(self.case, RUN, remaining, self.observations), ([], []))
        self.assertEqual(before, (self.entities, self.observations, self.edges))
        self.assertEqual((baseline, counter), self.sensitivity())

    def test_triage_locator_context_is_not_fabricated_factor_attribution(self):
        result, _ = self.sensitivity()
        text = generate_triage_explanation(result, self.by_id)
        self.assertIn('Evidence context only (factor-specific observation attribution unavailable)', text)
        for source in self.observations:
            if source['evidence_id'] in {eid for f in result['factors'] for eid in f['evidence_ids']}:
                self.assertIn(source['source_locator'], text)
        self.assertIn('no source locators supplied', generate_triage_explanation(result, {}))

    def test_strict_actual_bundle_and_negative_controls(self):
        triage_schema = result_validator()
        finding_schema = validator('Finding')
        for result in (self.result(), *self.sensitivity()):
            triage_schema.validate(result)
            for field in result:
                missing = dict(result)
                del missing[field]
                self.assertFalse(triage_schema.is_valid(missing), field)
            for changes in ({'invented_metric': .9}, {'score': 101}, {'priority': 'P5'},
                            {'created_at': 'bad'}, {'analysis_run_id': 'bad'}):
                self.assertFalse(triage_schema.is_valid(result | changes))
        finding_schema.validate(self.finding)
        for changes in ({'explanation': 'extra field'}, {'observation_ids': []},
                        {'observation_ids': self.finding['observation_ids'] * 2},
                        {'kind': 'candidate_match'}, {'confidence': True}):
            self.assertFalse(finding_schema.is_valid(self.finding | changes))

    def test_invalid_arithmetic_rejected(self):
        for changes in ({'score': 99}, {'priority': 'P1'}, {'factors': []},
                        {'factors': self.result()['factors'] * 2}):
            with self.assertRaises(ValueError):
                generate_triage_explanation(self.result() | changes)
        for field, value in (('weight', .25), ('contribution', 9), ('value', float('nan')),
                             ('name', 'imaginary'), ('explanation', ''), ('evidence_ids', [])):
            result = self.result()
            result['factors'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                generate_triage_explanation(result)

    def test_missing_foreign_mismatched_and_mixed_run_sources_fail_closed(self):
        oid = self.finding['observation_ids'][0]
        for changes in ({'case_id': str(uuid4())}, {'id': str(uuid4())},
                        {'evidence_id': str(uuid4())}, {'source_locator': ''},
                        {'entity_key': 'device:D-8'}):
            sources = self.by_id | {oid: self.by_id[oid] | changes}
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                generate_finding_explanation(self.finding, sources)
        with self.assertRaises(ValueError):
            generate_finding_explanation(self.finding, {})
        for changes in ({'rule': 'future-rule:v1'}, {'confidence': .9},
                        {'observation_ids': self.finding['observation_ids'] * 2}):
            with self.assertRaises(ValueError):
                generate_finding_explanation(self.finding | changes, self.by_id)
        source = self.observations[0]
        foreign = self.by_id | {source['id']: source | {'case_id': str(uuid4())}}
        with self.assertRaises(ValueError):
            generate_triage_explanation(self.sensitivity()[0], foreign)
        second = next(o for o in self.observations if o['evidence_id'] == source['evidence_id']
                      and o['id'] != source['id'])
        mixed = self.by_id | {second['id']: second | {'processing_run_id': str(uuid4())}}
        with self.assertRaises(ValueError):
            generate_triage_explanation(self.sensitivity()[0], mixed)

    def test_counterfactual_invalid_key_edges_case_and_target(self):
        for changes in ({'removed_entity_key': 'device:missing'}, {'edges': []},
                        {'case_id': str(uuid4())}, {'evidence_id': str(uuid4())},
                        {'observations': self.observations * 2}):
            with self.subTest(changes=changes.keys()), self.assertRaises(ValueError):
                self.sensitivity(**changes)


class PublishedExplanationTests(unittest.IsolatedAsyncioTestCase):
    # Reuse real HTTP/SQLite processing setup; only Neo4j projection is a double.
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll

    async def test_completed_run_triage_and_finding_source_readback(self):
        await self.upload()
        response = await self.client.post(self.base + '/evidence',
            data={'kind': 'gps', 'source_label': 'Synthetic A15'},
            files={'file': ('gps-shared-synthetic.csv', GPS_SHARED, 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        await self.process(response.json()['id'])
        run = await self.poll(await self.start())
        self.assertEqual(run['status'], 'completed')
        params = {'analysis_run_id': run['id'], 'limit': 100}
        triage = (await self.client.get(self.base + '/triage', params=params)).json()
        observations = (await self.client.get(self.base + '/observations', params={'limit': 100})).json()['items']
        by_id = {o['id']: o for o in observations}
        findings = (await self.client.get(self.base + '/findings', params=params)).json()['items']
        self.assertEqual({finding['kind'] for finding in findings}, {'relationship', 'corroboration', 'cluster'})
        for finding in findings:
            validator('Finding').validate(finding)
            if finding['kind'] == 'relationship':
                self.assertIn('device:D-7', generate_finding_explanation(finding, by_id))
        for entry in triage['items']:
            result = entry['latest_result']
            result_validator().validate(result)
            self.assertEqual(result['explanation'], generate_triage_explanation(result))
            self.assertIn('base weight', result['explanation'])
            self.assertEqual(result['analysis_run_id'], run['id'])
            history = (await self.client.get(self.base + f"/evidence/{entry['evidence_id']}/triage-history")).json()
            self.assertEqual(history, [result])
        foreign = await self.client.get(self.base + '/triage', headers={'Authorization': 'Bearer other'})
        self.assertEqual(foreign.status_code, 404)
