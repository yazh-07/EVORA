"""I05/P15/A18 synthetic ranking goldens and real existing-evidence feedback.

HTTP, SQLite, parsers, policy, factors and publication are real; only Neo4j uses
the established explicit transactional double. Metrics describe these controls,
not population accuracy. Gold relevance comes from authored source scenarios.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend import analysis, processing
from backend.deeper_processing import POLICY_VERSION, select_deeper_processing
from backend.evaluation import (evaluate_triage_ranking, evaluate_weight_sensitivity,
                                rank_consistency_correlation)
from backend.parsers.messages_csv import parse_messages_csv
from backend.parsers.message_entities import project_message_entities
from backend.deeper_processing import project_deeper_message_entities
from backend.processing_dispatch import adapter_for
from backend.tests import test_analysis as lifecycle
from backend.tests import test_triage_endpoints as endpoints
from backend.triage.policy import BASE_WEIGHTS


class TriageEvaluationTests(unittest.TestCase):
    def test_independent_golden_rankings_and_mean_reciprocal_rank(self):
        # Missing gold items remain in the recall denominator; first-hit RR is
        # calculated beyond k too. Precision uses fixed k, not returned length.
        scenarios = [(['noise', 'lead', 'other', 'support'], {'lead', 'support', 'missing'}, 2,
                      (1 / 3, .5, .5)),
                     (['lead', 'support', 'noise'], ['lead', 'support', 'support'], 2, (1., 1., 1.)),
                     (['noise', 'other', 'lead'], {'lead'}, 1, (0., 0., 1 / 3)),
                     (['lead'], {'lead'}, 5, (1., .2, 1.)),
                     (['noise'], {'lead'}, 5, (0., 0., 0.)),
                     ([], {'lead'}, 5, (0., 0., 0.)),
                     (['noise'], set(), 5, (0., 0., 0.)),
                     ([], set(), 5, (0., 0., 0.))]
        reciprocal_ranks = []
        for ranking, gold, k, expected in scenarios:
            with self.subTest(ranking=ranking, gold=gold, k=k):
                before = deepcopy((ranking, gold))
                result = evaluate_triage_ranking(ranking, gold, k)
                self.assertEqual(result, dict(zip(
                    ('top_k_recall', 'precision_at_k', 'reciprocal_rank'), expected)))
                self.assertEqual((ranking, gold), before)
                reciprocal_ranks.append(result['reciprocal_rank'])
        self.assertAlmostEqual(sum(reciprocal_ranks) / len(scenarios), 17 / 48)

    def test_invalid_rankings_and_cutoffs_fail(self):
        for k in (0, -1, True, 1.5, '5'):
            with self.subTest(k=k), self.assertRaises(ValueError):
                evaluate_triage_ranking(['a'], {'a'}, k)
        for ranked, gold in ((['a', 'a'], {'a'}), ([''], {'a'}), ([None], {'a'}), (['a'], [' '])):
            with self.subTest(ranked=ranked, gold=gold), self.assertRaises(ValueError):
                evaluate_triage_ranking(ranked, gold)

    def test_spearman_goldens_and_undefined_controls(self):
        self.assertEqual(rank_consistency_correlation(['a', 'b', 'c'], ['a', 'b', 'c']), 1.)
        self.assertEqual(rank_consistency_correlation(['a', 'b', 'c'], ['c', 'b', 'a']), -1.)
        self.assertEqual(rank_consistency_correlation(['a', 'b', 'c'], ['b', 'a', 'c']), .5)
        self.assertEqual(rank_consistency_correlation([], []), 0.)
        self.assertEqual(rank_consistency_correlation(['a'], ['a']), 0.)
        for first, second in ((['a'], ['b']), (['a', 'b'], ['a']), (['a', 'a'], ['a', 'b'])):
            with self.assertRaises(ValueError):
                rank_consistency_correlation(first, second)

    def test_weight_sensitivity_exact_drift_scores_ties_and_no_mutation(self):
        baseline = {'c': 10., 'b': 20., 'a': 30.}
        perturbed = {'b': 40., 'a': 30., 'c': 10.}
        original = deepcopy((baseline, perturbed))
        measured = evaluate_weight_sensitivity(baseline, perturbed)
        self.assertEqual(measured, dict(rank_correlation=.5, rank_changes={'a': 1, 'b': -1, 'c': 0},
            mean_absolute_rank_drift=2 / 3, max_rank_drift=1,
            score_changes={'a': 0., 'b': 20., 'c': 0.}, mean_absolute_score_change=20 / 3,
            max_absolute_score_change=20.))
        self.assertEqual((baseline, perturbed), original)
        tied = evaluate_weight_sensitivity({'b': 1., 'a': 1.}, {'a': 1., 'b': 1.})
        self.assertEqual(tied['rank_changes'], {'a': 0, 'b': 0})
        self.assertEqual(tied['rank_correlation'], 1.)
        shifted = evaluate_weight_sensitivity(baseline, {eid: value + 2 for eid, value in baseline.items()})
        self.assertEqual(shifted['mean_absolute_rank_drift'], 0.)
        self.assertEqual(shifted['mean_absolute_score_change'], 2.)
        empty = evaluate_weight_sensitivity({}, {})
        self.assertEqual(empty['rank_correlation'], 0.)
        self.assertEqual(empty['rank_changes'], {})
        self.assertEqual(empty['mean_absolute_rank_drift'], 0.)
        singleton = evaluate_weight_sensitivity({'a': 3.}, {'a': 2.})
        self.assertEqual(singleton['rank_changes'], {'a': 0})
        self.assertEqual(singleton['rank_correlation'], 0.)
        for first, second in (({'a': 1.}, {}), ({'a': 1.}, {'b': 1.}),
                              ({'a': True}, {'a': 1.}), ({'a': '1'}, {'a': 1.}),
                              ({'a': float('nan')}, {'a': 1.}), ({'a': 1.}, {'a': float('inf')})):
            with self.subTest(first=first, second=second), self.assertRaises(ValueError):
                evaluate_weight_sensitivity(first, second)

    def test_deeper_literal_projection_source_spans_duplicates_and_limits(self):
        body = 'D-7 AC-42 +12025550123 2001:db8::7 AC-42'
        rows = parse_messages_csv(('message_id,timestamp,sender,body\n'
            f'm1,2026-01-12T10:01:00Z,synthetic,{body}\n').encode(),
            case_id=uuid4(), evidence_id=uuid4(), processing_run_id=uuid4())
        base = project_message_entities(rows, case_id=rows[0].case_id)
        deeper = project_deeper_message_entities(base, max_mentions=5)
        self.assertEqual(len(base.entities), 1)
        self.assertEqual({entity.candidate_key for entity in deeper.entities},
                         {'device:D-7', 'account:AC-42', 'phone:+12025550123', 'ip:2001:db8::7'})
        self.assertEqual(deeper.observations[:len(base.observations)], base.observations)
        for item in deeper.observations[len(base.observations):]:
            source = item.observation
            start, end = map(int, source.source_locator.split('chars=')[1].split(':'))
            self.assertEqual(source.raw_value, body[start:end])
            self.assertEqual(source.processing_run_id, rows[0].processing_run_id)
            self.assertEqual(source.extraction_confidence, 0.)
        account = next(entity for entity in deeper.entities if entity.kind == 'account')
        self.assertEqual(len(account.observation_ids), 2)
        with self.assertRaises(ValueError):
            project_deeper_message_entities(base, max_mentions=4)


MESSAGE_BODY = 'D-7 203.0.113.7 203.0.113.9 AC-42 +12025550123'


class ReprocessingRankingTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = lifecycle.AnalysisTests.asyncSetUp
    upload = lifecycle.AnalysisTests.upload
    process = lifecycle.AnalysisTests.process
    start = lifecycle.AnalysisTests.start
    poll = lifecycle.AnalysisTests.poll
    triage = endpoints.TriageEndpointTests.triage
    history = endpoints.TriageEndpointTests.history
    stored = endpoints.TriageEndpointTests.stored

    def row(self, table, run_id):
        column = 'id' if table.endswith('_runs') else 'run_id'
        with self.app.state.database.connect() as connection:
            return dict(connection.execute(f'SELECT * FROM {table} WHERE {column}=?', (run_id,)).fetchone())

    async def upload_message(self, body=MESSAGE_BODY):
        data = ('message_id,timestamp,sender,body\n'
                f'm1,2026-01-12T10:01:00Z,synthetic,{body}\n').encode()
        response = await self.client.post(self.base + '/evidence',
            data={'kind': 'message', 'source_label': 'Synthetic deeper processing'},
            files={'file': ('messages.csv', data, 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        evidence = response.json()
        return evidence, await self.process(evidence['id']), data

    async def upload_csv(self, kind, source):
        response = await self.client.post(self.base + '/evidence',
            data={'kind': kind, 'source_label': 'Synthetic ranking control'},
            files={'file': ('control.csv', source.encode(), 'text/csv')})
        self.assertEqual(response.status_code, 201, response.text)
        evidence = response.json()
        await self.process(evidence['id'])
        return evidence

    async def assert_feedback_gate(self, initial, target_id):
        """Compare ranks of the original candidates after a new source arrives.

        Hold this evaluation universe fixed: new evidence can independently take
        first place in the full list. Gold identifies the authored earlier lead.
        """
        changed = await self.poll(await self.start())
        self.assertEqual((changed['status'], changed['trigger']), ('completed', 'new_observations'))
        self.assertNotEqual(changed['input_snapshot']['sha256'], initial['input_snapshot']['sha256'])
        membership = set(initial['input_snapshot']['evidence_ids'])
        metrics = []
        for run in (initial, changed):
            page = await self.triage({'analysis_run_id': run['id']})
            ranking = [item['evidence_id'] for item in page['items'] if item['evidence_id'] in membership]
            metrics.append(evaluate_triage_ranking(ranking, {target_id}, k=1))
        self.assertEqual(metrics, [dict(top_k_recall=0., precision_at_k=0., reciprocal_rank=.5),
                                   dict(top_k_recall=1., precision_at_k=1., reciprocal_rank=1.)])
        self.assertEqual((await self.history(target_id))[0]['analysis_run_id'], initial['id'])
        return changed

    async def test_new_upload_connectivity_reranks_earlier_evidence(self):
        target, _, _ = await self.upload_message('D-7 D-8')
        await self.upload_message('D-9 D-10 D-11')
        initial = await self.poll(await self.start())
        await self.upload_csv('network_log', 'timestamp,device_id,ip_address,event\n'
            '2026-01-12T10:01:00Z,D-7,203.0.113.7,connected\n'
            '2026-01-12T10:01:00Z,D-8,203.0.113.8,connected\n')
        changed = await self.assert_feedback_gate(initial, target['id'])
        result = next(r for r in self.stored(changed) if r['evidence_id'] == target['id'])
        connectivity = next(f for f in result['factors'] if f['name'] == 'connectivity')
        self.assertEqual(connectivity['value'], .2)

    async def test_detector_conflict_factor_reranks_earlier_evidence(self):
        target = await self.upload_csv('gps', 'timestamp,device_id,latitude,longitude\n'
            '2026-01-12T10:01:00Z,D-7,12,77\n')
        # Missing timezone remains unknown and supplies no temporal factor.
        await self.upload_csv('gps', 'timestamp,device_id,latitude,longitude\n'
            '2026-01-12T10:01:00,D-8,12,77\n2026-01-12T10:01:00,D-9,12,77\n')
        initial = await self.poll(await self.start())
        await self.upload_csv('gps', 'timestamp,device_id,latitude,longitude\n'
            '2026-01-12T10:01:00Z,D-7,13,77\n')
        changed = await self.assert_feedback_gate(initial, target['id'])
        before = next(r for r in self.stored(initial) if r['evidence_id'] == target['id'])
        after = next(r for r in self.stored(changed) if r['evidence_id'] == target['id'])
        self.assertEqual(next(f['value'] for f in before['factors'] if f['name'] == 'conflict_relevance'), 0.)
        conflict = next(f for f in after['factors'] if f['name'] == 'conflict_relevance')
        self.assertEqual(conflict['value'], .8)
        self.assertGreater(conflict['contribution'], 0.)
        # Zero the conflict signal while retaining its weight and all other
        # factors. Production aggregation then puts the lead below its competitor.
        from backend.triage.aggregation import aggregate_triage_result
        ablated = aggregate_triage_result(case_id=self.case, analysis_run_id=changed['id'],
            evidence_id=target['id'], observation_count=3,
            factors=[dict(f, value=0.) if f['name'] == 'conflict_relevance' else f for f in after['factors']],
            case_evidence_ids=changed['input_snapshot']['evidence_ids'], created_at=changed['created_at'])
        competitor = next(r for r in self.stored(changed)
                          if r['evidence_id'] in initial['input_snapshot']['evidence_ids']
                          and r['evidence_id'] != target['id'])
        self.assertLess(ablated['score'], competitor['score'])
        self.assertGreater(after['score'], competitor['score'])

    async def prepared_case(self):
        network, _ = await self.upload()
        target, initial_processing, original = await self.upload_message()
        self.initial_analysis_key = str(uuid4())
        initial = await self.poll(await self.start(self.initial_analysis_key))
        self.assertEqual(initial['status'], 'completed', initial)
        return network, target, initial_processing, original, initial

    async def test_deeper_reprocessing_reranks_same_evidence_and_preserves_history(self):
        network, target, first, original, initial = await self.prepared_case()
        eid = target['id']
        old_rows = {table: self.row(table, first['id'] if table.startswith('processing') else initial['id'])
                    for table in ('processing_runs', 'processing_outputs', 'processing_provenance',
                                  'analysis_runs', 'analysis_outputs')}
        old_history = await self.history(eid)
        before = await self.triage({'analysis_run_id': initial['id']})
        self.assertEqual([item['evidence_id'] for item in before['items']], [network['id'], eid])
        self.assertNotIn('deeper', json.loads(old_rows['processing_runs']['config_json']))
        url = self.base + f'/evidence/{eid}/processing-runs'
        response = await self.client.post(url, headers={'Idempotency-Key': 'deeper-success-key'})
        self.assertEqual(response.status_code, 202, response.text)
        second = (await self.client.get(url + '/' + response.json()['id'])).json()
        self.assertEqual(second['status'], 'completed', second)
        config = json.loads(self.row('processing_runs', second['id'])['config_json'])
        self.assertIs(config['deeper'], True)
        self.assertEqual(config['deeper_policy'], POLICY_VERSION)
        self.assertEqual(config['deeper_analysis_run_id'], initial['id'])
        findings = json.loads(old_rows['analysis_outputs']['findings_json'])
        self.assertTrue(set(config['deeper_finding_ids']) <= {f['id'] for f in findings
                        if f['kind'] == 'corroboration' and eid in f['evidence_ids']})
        provenance = json.loads(self.row('processing_provenance', second['id'])['payload_json'])
        self.assertEqual(provenance['execution']['deeper_processing']['deeper_policy'], POLICY_VERSION)
        self.assertNotIn('deeper', second)  # Private configuration has no new wire fields.
        output = self.row('processing_outputs', second['id'])
        observations = json.loads(output['observations_json'])
        extra = [o for o in observations if o['kind'] in ('message.ip', 'message.account', 'message.phone')]
        self.assertEqual(len(extra), 4)
        for source in extra:
            start, end = map(int, source['source_locator'].split('chars=')[1].split(':'))
            self.assertEqual(source['raw_value'], MESSAGE_BODY[start:end])
            self.assertEqual(source['processing_run_id'], second['id'])
            self.assertEqual(source['evidence_id'], eid)
        changed = await self.poll(await self.start())
        self.assertEqual((changed['status'], changed['trigger']), ('completed', 'new_observations'))
        snapshot = changed['input_snapshot']
        self.assertNotEqual(snapshot['sha256'], initial['input_snapshot']['sha256'])
        self.assertIn(second['id'], snapshot['processing_run_ids'])
        self.assertNotIn(first['id'], snapshot['processing_run_ids'])
        self.assertTrue({o['id'] for o in observations} <= set(snapshot['observation_ids']))
        old_observations = json.loads(old_rows['processing_outputs']['observations_json'])
        self.assertFalse({o['id'] for o in old_observations} & set(snapshot['observation_ids']))
        after = await self.triage({'analysis_run_id': changed['id']})
        self.assertEqual([item['evidence_id'] for item in after['items']], [eid, network['id']])
        old_result = next(r for r in self.stored(initial) if r['evidence_id'] == eid)
        new_result = next(r for r in self.stored(changed) if r['evidence_id'] == eid)
        self.assertGreater(new_result['score'], old_result['score'])
        old_factors = {f['name']: f for f in old_result['factors']}
        factors = {f['name']: f for f in new_result['factors']}
        for name in ('relevance', 'connectivity'):
            self.assertGreater(factors[name]['value'], old_factors[name]['value'])
            self.assertIn(eid, factors[name]['evidence_ids'])
        self.assertIn('ip:203.0.113.7', factors['relevance']['explanation'])
        # Graph source trace for the new connection resolves to the exact span.
        graph = json.loads(self.row('analysis_outputs', changed['id'])['graph_json'])
        self.assertTrue(any(set(edge['observation_ids']) & {o['id'] for o in extra}
                            and eid in edge['evidence_ids'] for edge in graph['edges']))
        for page, expected in ((before, (0., 0., .5)), (after, (1., 1., 1.))):
            measured = evaluate_triage_ranking([x['evidence_id'] for x in page['items']], {eid}, k=1)
            self.assertEqual(tuple(measured.values()), expected)
        content = await self.client.get(self.base + f'/evidence/{eid}/content')
        self.assertEqual(content.content, original)
        self.assertEqual(hashlib.sha256(content.content).hexdigest(), target['sha256'])
        self.assertEqual(await self.triage({'analysis_run_id': initial['id']}), before)
        self.assertEqual((await self.history(eid))[:len(old_history)], old_history)
        self.assertEqual(len(await self.history(eid)), 2)
        for table, row in old_rows.items():
            self.assertEqual(self.row(table, first['id'] if table.startswith('processing') else initial['id']), row)
        third = await self.process(eid)
        third_config = json.loads(self.row('processing_runs', third['id'])['config_json'])
        self.assertEqual(third_config['deeper_analysis_run_id'], initial['id'])
        self.assertEqual(third_config['deeper_finding_ids'], config['deeper_finding_ids'])
        with patch.object(processing, 'select_deeper_processing', side_effect=AssertionError('reselected')):
            replay = await self.client.post(url, headers={'Idempotency-Key': 'deeper-success-key'})
        self.assertEqual(replay.json(), second)
        self.assertIn(third['id'], analysis.freeze_analysis_input_snapshot(
            self.app.state.database, self.case)['processing_run_ids'])
        # Direct mutations also fail under the actual immutable-history guards.
        for table, column, value in (('processing_runs', 'id', first['id']),
                                     ('processing_outputs', 'run_id', first['id']),
                                     ('analysis_runs', 'id', initial['id']),
                                     ('analysis_outputs', 'run_id', initial['id'])):
            for operation in (f'UPDATE {table} SET {column}={column} WHERE {column}=?',
                              f'DELETE FROM {table} WHERE {column}=?'):
                with self.app.state.database.connect() as connection, self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(operation, (value,))

    async def test_replay_skips_policy_failed_and_queued_deeper_keep_prior_selection(self):
        _, target, first, _, initial = await self.prepared_case()
        eid = target['id']
        url = self.base + f'/evidence/{eid}/processing-runs'
        key = 'deeper-failure-key'
        bounded_adapter = replace(adapter_for('message'), max_device_mentions=3)
        with patch.object(processing, 'adapter_for', return_value=bounded_adapter):
            accepted = await self.client.post(url, headers={'Idempotency-Key': key})
        self.assertEqual(accepted.status_code, 202, accepted.text)
        failed = (await self.client.get(url + '/' + accepted.json()['id'])).json()
        self.assertEqual((failed['status'], failed['error']), ('failed', 'PROCESSING_FAILED'))
        self.assertTrue(json.loads(self.row('processing_runs', failed['id'])['config_json'])['deeper'])
        with patch.object(processing, 'select_deeper_processing', side_effect=AssertionError('reselected')):
            replay = await self.client.post(url, headers={'Idempotency-Key': key})
        self.assertEqual(replay.json(), failed)
        with patch.object(processing, 'run_job'):
            queued = await self.client.post(url, headers={'Idempotency-Key': 'deeper-queued-key'})
        self.assertEqual(queued.status_code, 202, queued.text)
        self.assertEqual(analysis.freeze_analysis_input_snapshot(self.app.state.database, self.case), initial['input_snapshot'])
        manual = await self.poll(await self.start())
        self.assertEqual(manual['trigger'], 'manual')
        self.assertEqual(self.stored(manual)[0]['score'], self.stored(initial)[0]['score'])
        second = await self.process(eid)
        self.assertIn(second['id'], analysis.freeze_analysis_input_snapshot(
            self.app.state.database, self.case)['processing_run_ids'])
        with patch.object(analysis, 'freeze_analysis_input_snapshot', side_effect=AssertionError('resnapshot')):
            self.assertEqual(await self.start(self.initial_analysis_key), initial)
        with self.app.state.database.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM processing_outputs WHERE run_id=?',
                                                (failed['id'],)).fetchone()[0], 0)
        self.assertEqual(self.row('processing_runs', first['id'])['status'], 'completed')

    async def test_latest_completed_selection_uses_utc_then_id_and_never_creation_time(self):
        evidence, _ = await self.upload(process=False)
        eid = evidence['id']
        # Equal instants have different lexical representations. Assign a later
        # creation time to the earlier finish to prove acceptance time is unused.
        with patch.object(processing, '_now', side_effect=['2026-11-04T00:00:00Z', '2026-11-03T13:00:00+01:00']):
            first = await self.process(eid)
        with patch.object(processing, '_now', side_effect=['2026-11-03T00:00:00Z', '2026-11-03T12:00:00Z']):
            second = await self.process(eid)
        snapshot = analysis.freeze_analysis_input_snapshot(self.app.state.database, self.case)
        self.assertEqual(snapshot['processing_run_ids'], [max(first['id'], second['id'])])
        with patch.object(processing, '_now', side_effect=['2026-11-02T00:00:00Z', '2026-11-03T08:00:00-05:00']):
            latest = await self.process(eid)
        snapshot = analysis.freeze_analysis_input_snapshot(self.app.state.database, self.case)
        self.assertEqual(snapshot['processing_run_ids'], [latest['id']])
        self.assertEqual(snapshot['observation_ids'], sorted(o['id'] for o in
            json.loads(self.row('processing_outputs', latest['id'])['observations_json'])))

    async def test_no_detector_signal_no_deeper_and_no_public_selector(self):
        target, first, _ = await self.upload_message('AC-42 203.0.113.7')
        await self.poll(await self.start())
        second = await self.process(target['id'])
        for run in (first, second):
            self.assertNotIn('deeper', json.loads(self.row('processing_runs', run['id'])['config_json']))
        url = self.base + f'/evidence/{target["id"]}/processing-runs'
        for kwargs in ({'json': {'deeper': True}}, {'params': {'deeper': 'true'}}):
            response = await self.client.post(url, headers={'Idempotency-Key': 'invalid-selector'}, **kwargs)
            self.assertEqual(response.status_code, 400)
        with self.app.state.database.connect() as connection:
            self.assertEqual(select_deeper_processing(connection, str(uuid4()), target['id'], 'message'), {})

    async def test_experimental_weight_perturbations_use_actual_frozen_factor_values(self):
        _, target, _, _, initial = await self.prepared_case()
        await self.process(target['id'])
        changed = await self.poll(await self.start())
        results = self.stored(changed)
        baseline = {r['evidence_id']: r['score'] for r in results}
        for multiplier in (.8, 1., 1.2):
            weights = dict(BASE_WEIGHTS)
            weights['relevance'] *= multiplier
            perturbed = {}
            for result in results:
                total = sum(weights[f['name']] for f in result['factors'])
                perturbed[result['evidence_id']] = min(100., round(sum(round(
                    100 * f['value'] * weights[f['name']] / total, 2) for f in result['factors']), 2))
            measured = evaluate_weight_sensitivity(baseline, perturbed)
            self.assertEqual(measured['rank_correlation'], 1.)
            self.assertEqual(measured['max_rank_drift'], 0)
            if multiplier == 1.:
                self.assertEqual(perturbed, baseline)
            else:
                self.assertGreater(measured['max_absolute_score_change'], 0.)
            print('I05_WEIGHT_SENSITIVITY ' + json.dumps({'relevance_multiplier': multiplier, **measured}, sort_keys=True))
        self.assertNotEqual(initial['input_snapshot']['sha256'], changed['input_snapshot']['sha256'])
