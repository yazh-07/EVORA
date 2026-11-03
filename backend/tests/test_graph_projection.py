"""A01B real SQLite, synthetic driver failures, opt-in real Neo4j acceptance."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.auth import SyntheticTokenVerifier
from backend.database import SQLiteDatabase
from backend.errors import AccessError
from backend.graph_db import Neo4jGraphDatabase
from backend.graph_links import derive_candidate_links
from backend.graph_nodes import build_graph_nodes
from backend import graph_projection as projection
from backend.tests.test_graph_nodes import validator
from backend.triage.aggregation import aggregate_triage_result
from backend.triage.factors import calculate_connectivity_factor, calculate_relevance_factor
from backend.triage.policy import FactorValue

ROOT = Path(__file__).resolve().parents[2]


def snapshot(case, evidence, processing, observations):
    manifest = dict(case_id=case, evidence_ids=sorted(evidence),
                    processing_run_ids=sorted(processing), observation_ids=sorted(observations))
    return manifest | dict(sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest())


def accept(db, case, run, manifest):
    """Explicit A05 acceptance double. No startAnalysis API is claimed here."""
    with db.connect() as connection:
        connection.execute("INSERT INTO analysis_runs "
            "(id,case_id,actor_id,key_digest,status,input_snapshot_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (run, case, 'synthetic-investigator', hashlib.sha256(run.encode()).hexdigest(), 'queued',
             projection._json(manifest), '2026-11-03T12:00:00Z'))


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def consume(self):
        return None

    def data(self):
        return deepcopy(self.rows)

    def single(self, strict=False):
        if strict and len(self.rows) != 1:
            raise AssertionError('Expected exactly one row')
        return self.data()[0]


class SyntheticTransaction:
    """Stateful transaction double; rollback and committed state stay separate.

    Exact query dispatch is unit-only. Real opt-in tests validate actual Cypher,
    driver semantics, constraints and source-backed publication independently.
    """
    def __init__(self, service):
        self.service = service
        self.partitions = deepcopy(service.partitions)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        if self.service.fail == 'commit':
            raise OSError('synthetic-private-driver-detail')
        self.service.partitions = deepcopy(self.partitions)
        if self.service.after_commit:
            self.service.after_commit()

    def run(self, query, **params):
        self.service.calls.append((query, deepcopy(params)))
        if self.service.before_query:
            self.service.before_query()
        if query == self.service.fail:
            raise OSError('synthetic-private-driver-detail')
        key = (params['case_id'], params['run_id'])
        partition = self.partitions.setdefault(key, dict(nodes={}, edges={}))
        if query == projection._DELETE_EDGES:
            partition['edges'].clear()
        elif query == projection._DELETE_NODES:
            partition['nodes'].clear()
        elif query == projection._WRITE_NODE:
            for node in params['nodes']:
                partition['nodes'][node['id']] = deepcopy(node)
        elif query == projection._WRITE_EDGE:
            for edge in params['edges']:
                if edge['from_id'] in partition['nodes'] and edge['to_id'] in partition['nodes']:
                    partition['edges'][edge['id']] = dict(
                        edge={key: deepcopy(value) for key, value in edge.items() if key not in ('from_id', 'to_id')},
                        from_id=edge['from_id'], to_id=edge['to_id'], from_case=params['case_id'],
                        to_case=params['case_id'], from_run=params['run_id'], to_run=params['run_id'],
                        from_labels=['Node'], to_labels=['Node'])
        elif query in (projection._COUNT_NODES, projection._COUNT_EDGES):
            count = len(partition['nodes' if query == projection._COUNT_NODES else 'edges'])
            return Result([dict(count=count + int(self.service.corrupt == query))])
        elif query == projection._READ_NODES:
            rows = [dict(node=deepcopy(node)) for node in partition['nodes'].values()]
            if self.service.corrupt == 'property' and rows:
                rows[0]['node']['label'] = 'Corrupt synthetic label'
            return Result(rows)
        elif query == projection._READ_EDGES:
            rows = deepcopy(list(partition['edges'].values()))
            if self.service.corrupt == 'endpoint' and rows:
                rows[0]['to_run'] = str(uuid4())
            return Result(rows)
        else:
            raise AssertionError('Unexpected Cypher')
        return Result()


class SyntheticNeo4j:
    def __init__(self):
        self.config = SimpleNamespace(database='synthetic-private-db', connection_timeout=1.)
        self.partitions, self.calls = {}, []
        self.fail = self.corrupt = self.before_query = self.after_commit = None

    def get_driver(self):
        if self.fail == 'connect':
            raise OSError('synthetic-private-driver-detail')
        return self

    @contextmanager
    def session(self, *, database):
        assert database == self.config.database
        yield self

    def setup_schema(self, session):
        if self.fail == 'schema':
            raise OSError('synthetic-private-driver-detail')

    def begin_transaction(self, *, timeout):
        assert timeout == self.config.connection_timeout
        return SyntheticTransaction(self)


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = SQLiteDatabase(Path(temporary.name) / 'test.sqlite3')
        self.neo = SyntheticNeo4j()
        self.case, self.run = str(uuid4()), str(uuid4())
        self.eids = sorted(str(uuid4()) for _ in range(2))
        self.pids = [str(uuid4()), str(uuid4())]
        self.oids = [str(uuid4()), str(uuid4())]
        self.entities = []
        # Minimal synthetic source SQL fixture for failure controls, not real
        # M1/M2 producers. RealProducerTests below uses the merged producers.
        with self.db.connect() as connection:
            connection.executescript('''
              CREATE TABLE cases(id TEXT PRIMARY KEY);
              CREATE TABLE evidence(id TEXT PRIMARY KEY, case_id TEXT, filename TEXT);
              CREATE TABLE processing_runs(id TEXT PRIMARY KEY, case_id TEXT, evidence_id TEXT, status TEXT);
              CREATE TABLE processing_outputs(run_id TEXT PRIMARY KEY, case_id TEXT, evidence_id TEXT,
                observations_json TEXT, entities_json TEXT, events_json TEXT);
            ''')
            connection.execute('INSERT INTO cases VALUES (?)', (self.case,))
            for eid, pid, oid in zip(self.eids, self.pids, self.oids):
                entity = dict(id=str(uuid4()), case_id=self.case, kind='device', canonical_label='D-7',
                    candidate_key='device:D-7', evidence_ids=[eid], observation_ids=[oid], confidence=.7)
                self.entities.append(entity)
                observation = dict(id=oid, case_id=self.case, evidence_id=eid, processing_run_id=pid,
                    entity_key='device:D-7', source_locator='row 2, device_id', raw_value='D-7')
                connection.execute('INSERT INTO evidence VALUES (?,?,?)', (eid, self.case, 'synthetic.csv'))
                connection.execute('INSERT INTO processing_runs VALUES (?,?,?,?)', (pid, self.case, eid, 'completed'))
                connection.execute('INSERT INTO processing_outputs VALUES (?,?,?,?,?,?)', (pid, self.case, eid,
                    projection._json([observation]), projection._json([entity]), '[]'))
        projection.initialize_graph_projection(self.db)
        self.manifest = snapshot(self.case, self.eids, self.pids, self.oids)
        accept(self.db, self.case, self.run, self.manifest)
        self.graph, self.findings, self.triage = self.outputs(self.run)

    def outputs(self, run):
        with self.db.connect() as connection:
            evidence = [dict(row) for row in connection.execute('SELECT * FROM evidence')]
            observations = [item for row in connection.execute('SELECT * FROM processing_outputs')
                            for item in json.loads(row['observations_json'])]
        nodes = build_graph_nodes(self.case, evidence, self.entities, [])
        edges, findings = derive_candidate_links(self.case, run, self.entities, observations)
        triage = [aggregate_triage_result(case_id=self.case, analysis_run_id=run, evidence_id=eid,
            observation_count=1, factors=dict(connectivity=FactorValue(.1, 'Synthetic candidate adjacency', (eid,))),
            case_evidence_ids=self.eids, created_at='2026-11-03T12:00:00Z') for eid in self.eids]
        return (dict(case_id=self.case, analysis_run_id=run, nodes=[n.to_wire() for n in nodes],
                     edges=[e.to_wire() for e in edges]), [f.to_wire() for f in findings], triage)

    def project(self, **changes):
        return projection.project_analysis_run(self.db, self.neo, **(dict(case_id=self.case,
            analysis_run_id=self.run, graph=self.graph, findings=self.findings, triage=self.triage) | changes))

    def get(self, **changes):
        return projection.get_projected_graph(self.db, self.neo,
            **(dict(case_id=self.case, analysis_run_id=self.run) | changes))

    def rebuild(self, **changes):
        return projection.rebuild_graph_partition(self.db, self.neo,
            **(dict(case_id=self.case, analysis_run_id=self.run) | changes))

    def row(self):
        with self.db.connect() as connection:
            return dict(connection.execute('SELECT * FROM analysis_runs WHERE id=?', (self.run,)).fetchone())

    def test_committed_sql_precedes_neo4j_then_exact_readback_and_schema(self):
        def pending():
            self.assertEqual(self.row()['status'], 'running')
            with self.db.connect() as connection:
                stored = connection.execute('SELECT * FROM analysis_outputs').fetchone()
                self.assertEqual(json.loads(stored['graph_json']), self.graph)
                self.assertEqual(json.loads(stored['findings_json']), self.findings)
                self.assertEqual(json.loads(stored['triage_json']), self.triage)
        self.neo.before_query = pending
        before = deepcopy((self.graph, self.findings, self.triage))
        self.project()
        self.neo.before_query = None
        self.assertEqual(self.row()['status'], 'completed')
        self.assertIsNone(self.row()['error'])
        self.assertIsNotNone(datetime.fromisoformat(self.row()['finished_at']).utcoffset())
        graph = self.get()
        self.assertEqual(graph, self.graph)
        validator('Graph').validate(graph)
        for finding in self.findings:
            validator('Finding').validate(finding)
        for result in self.triage:
            validator('TriageResult').validate(result)
        self.assertEqual((self.graph, self.findings, self.triage), before)

    def test_repeated_completed_projection_is_read_only_and_identical(self):
        self.project()
        before = deepcopy(self.neo.partitions), self.row()
        self.neo.calls.clear()
        self.project()
        self.assertEqual((self.neo.partitions, self.row()), before)
        self.assertTrue(all(query not in (projection._DELETE_NODES, projection._WRITE_NODE,
                                          projection._WRITE_EDGE) for query, _ in self.neo.calls))
        self.assertEqual(self.get(), self.graph)
        changed = deepcopy(self.graph)
        changed['edges'].clear()
        with self.assertRaisesRegex(ValueError, 'Immutable'):
            self.project(graph=changed)
        self.assertEqual((self.neo.partitions, self.row()), before)

    def test_failures_never_publish_and_hide_retained_partial_partition(self):
        for failure in ('connect', 'schema', projection._WRITE_NODE, projection._WRITE_EDGE,
                        projection._COUNT_EDGES, 'commit'):
            with self.subTest(failure=failure):
                # Separate accepted run for each terminal failure.
                self.run = str(uuid4())
                accept(self.db, self.case, self.run, self.manifest)
                self.graph, self.findings, self.triage = self.outputs(self.run)
                self.neo.partitions[(self.case, self.run)] = dict(nodes={'partial': {}}, edges={})
                self.neo.fail = failure
                with self.assertRaises(projection.ProjectionError) as caught:
                    self.project()
                self.assertNotIn('synthetic-private-driver-detail', str(caught.exception))
                self.assertEqual(self.row()['status'], 'failed')
                self.assertEqual(self.row()['error'], 'GRAPH_PROJECTION_FAILED')
                with self.assertRaises(AccessError) as denied:
                    self.get()
                self.assertEqual(denied.exception.status_code, 404)
                with self.assertRaises(ValueError):
                    self.project()
                self.neo.fail = None
                self.assertTrue(self.rebuild())
                self.assertEqual(self.row()['status'], 'failed')
                with self.assertRaises(AccessError):
                    self.get()

    def test_verification_rejects_counts_properties_and_cross_partition_endpoints(self):
        for corruption in (projection._COUNT_NODES, projection._COUNT_EDGES, 'property', 'endpoint'):
            with self.subTest(corruption=corruption):
                self.run = str(uuid4())
                accept(self.db, self.case, self.run, self.manifest)
                self.graph, self.findings, self.triage = self.outputs(self.run)
                self.neo.corrupt = corruption
                with self.assertRaises(projection.ProjectionError):
                    self.project()
                self.assertEqual(self.row()['status'], 'failed')
                self.assertNotIn((self.case, self.run), self.neo.partitions)

    def test_crash_boundaries_resume_original_immutable_output(self):
        for stage in ('before-graph', 'after-graph'):
            with self.subTest(stage=stage):
                self.run = str(uuid4())
                accept(self.db, self.case, self.run, self.manifest)
                self.graph, self.findings, self.triage = self.outputs(self.run)
                def crash():
                    raise SystemExit('Synthetic process interruption')
                if stage == 'before-graph':
                    self.neo.before_query = crash
                else:
                    self.neo.after_commit = crash
                with self.assertRaises(SystemExit):
                    self.project()
                self.neo.before_query = self.neo.after_commit = None
                self.assertEqual(self.row()['status'], 'running')
                with self.assertRaises(AccessError):
                    self.get()
                projection.initialize_graph_projection(self.db)  # Restart preserves history.
                self.assertTrue(self.rebuild())
                self.assertEqual(self.row()['status'], 'running')
                self.project()
                self.assertEqual(self.get(), self.graph)

    def test_sql_completion_failure_after_graph_commit_fails_closed(self):
        with self.db.connect() as connection:
            connection.executescript("CREATE TRIGGER inject_failure BEFORE UPDATE OF status ON analysis_runs "
                "WHEN NEW.status='completed' BEGIN SELECT RAISE(ABORT,'Synthetic SQL publish failure'); END;")
        with self.assertRaises(projection.ProjectionError):
            self.project()
        self.assertIn((self.case, self.run), self.neo.partitions)
        self.assertEqual(self.row()['status'], 'failed')
        with self.assertRaises(AccessError):
            self.get()

    def test_sql_commit_failure_after_graph_commit_rolls_back_publication(self):
        original_db = self.db

        class CommitFailure:
            @contextmanager
            def connect(inner):
                with original_db.connect() as connection:
                    yield connection
                    row = connection.execute('SELECT status FROM analysis_runs WHERE id=?', (self.run,)).fetchone()
                    if row and row['status'] == 'completed':
                        raise sqlite3.OperationalError('Synthetic commit failure')

        self.db = CommitFailure()
        with self.assertRaises(projection.ProjectionError):
            self.project()
        self.db = original_db
        self.assertIn((self.case, self.run), self.neo.partitions)
        self.assertEqual(self.row()['status'], 'failed')
        with self.assertRaises(AccessError):
            self.get()

    def test_failed_failure_accounting_leaves_hidden_recoverable_running_output(self):
        with self.db.connect() as connection:
            connection.executescript("CREATE TRIGGER inject_failure BEFORE UPDATE OF status ON analysis_runs "
                "WHEN NEW.status='failed' BEGIN SELECT RAISE(ABORT,'Synthetic SQL failure'); END;")
        self.neo.fail = 'connect'
        with self.assertRaisesRegex(projection.ProjectionError, 'SQL recovery is required'):
            self.project()
        self.assertEqual(self.row()['status'], 'running')
        with self.assertRaises(AccessError):
            self.get()
        self.neo.fail = None
        self.project()
        self.assertEqual(self.get(), self.graph)

    def test_rebuild_repairs_loss_and_stale_data_without_mutating_sql(self):
        self.project()
        with self.db.connect() as connection:
            before = [tuple(row) for row in connection.execute('SELECT * FROM analysis_outputs')], self.row()
        self.neo.partitions.clear()
        with self.assertRaises(projection.ProjectionError):
            self.get()
        for _ in range(2):
            self.neo.partitions[(self.case, self.run)] = dict(nodes={'stale': {}}, edges={})
            self.assertTrue(self.rebuild())
            self.assertEqual(self.get(), self.graph)
        with self.db.connect() as connection:
            self.assertEqual(([tuple(row) for row in connection.execute('SELECT * FROM analysis_outputs')],
                              self.row()), before)
        self.neo.fail = 'connect'
        self.assertFalse(self.rebuild())
        with self.assertRaises(projection.ProjectionError):
            self.get()
        self.assertEqual(self.row()['status'], 'completed')

    def test_foreign_missing_pending_and_failed_selectors_have_same_404(self):
        self.project()
        previous = deepcopy(self.neo.partitions)
        for kwargs in (dict(case_id=str(uuid4())), dict(analysis_run_id=str(uuid4()))):
            for function in (self.get, self.rebuild, self.project):
                with self.assertRaises(AccessError) as caught:
                    function(**kwargs)
                self.assertEqual((caught.exception.status_code, caught.exception.code,
                                  str(caught.exception)), (404, 'NOT_FOUND', 'Resource not found.'))
        self.assertEqual(self.neo.partitions, previous)
        for identifier in ('bad', self.run.upper(), None):
            with self.assertRaises(ValueError):
                self.get(analysis_run_id=identifier)

    def test_source_output_negatives_precede_projection(self):
        mutations = []
        for target, key, value in (('nodes', 'id', str(uuid4())), ('nodes', 'case_id', str(uuid4())),
                ('edges', 'to_id', str(uuid4())), ('edges', 'observation_ids', [str(uuid4())]),
                ('edges', 'observation_ids', []), ('edges', 'confidence', True)):
            changed = deepcopy(self.graph)
            changed[target][0][key] = value
            mutations.append(dict(graph=changed))
        mutations.append(dict(graph=self.graph | dict(nodes=self.graph['nodes'] * 2)))
        mutations.append(dict(findings=[self.findings[0] | dict(analysis_run_id=str(uuid4()))]))
        mutations.append(dict(findings=[self.findings[0] | dict(evidence_ids=[self.eids[0]])]))
        mutations.append(dict(triage=[self.triage[0] | dict(case_id=str(uuid4()))]))
        mutations.append(dict(triage=self.triage * 2))
        for changes in mutations:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.project(**changes)
        self.assertEqual(self.row()['status'], 'queued')
        self.assertFalse(self.neo.calls)

    def test_frozen_source_selection_rejects_hash_locators_and_foreign_processing(self):
        for mutation in ('digest', 'foreign-processing', 'missing-observation', 'missing-locator'):
            with self.subTest(mutation=mutation):
                self.run = str(uuid4())
                self.graph, self.findings, self.triage = self.outputs(self.run)
                manifest = deepcopy(self.manifest)
                if mutation == 'digest':
                    manifest['sha256'] = '0' * 64
                elif mutation == 'foreign-processing':
                    manifest = snapshot(self.case, self.eids, [str(uuid4())], self.oids)
                elif mutation == 'missing-observation':
                    manifest = snapshot(self.case, self.eids, self.pids, [])
                else:
                    with self.db.connect() as connection:
                        row = connection.execute('SELECT * FROM processing_outputs LIMIT 1').fetchone()
                        observations = json.loads(row['observations_json'])
                        observations[0]['source_locator'] = ' '
                        connection.execute('UPDATE processing_outputs SET observations_json=? WHERE run_id=?',
                            (projection._json(observations), row['run_id']))
                accept(self.db, self.case, self.run, manifest)
                with self.assertRaises(ValueError):
                    self.project()
        self.assertFalse(self.neo.calls)

    def test_sql_guards_reject_update_delete_replace_upsert_and_acceptance_mutation(self):
        self.project()
        for statement in (
                "UPDATE analysis_outputs SET graph_json='{}'", "DELETE FROM analysis_outputs",
                "INSERT OR REPLACE INTO analysis_outputs SELECT * FROM analysis_outputs",
                "INSERT INTO analysis_outputs SELECT * FROM analysis_outputs WHERE 1 "
                    "ON CONFLICT(run_id) DO UPDATE SET graph_json='{}'",
                "UPDATE analysis_runs SET input_snapshot_json='{}'", "UPDATE analysis_runs SET status='failed'",
                "DELETE FROM analysis_runs", "INSERT OR REPLACE INTO analysis_runs SELECT * FROM analysis_runs"):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                with self.db.connect() as connection:
                    connection.execute(statement)
        self.assertEqual(self.get(), self.graph)

    def test_empty_completed_graph_retains_run_id(self):
        case, run = str(uuid4()), str(uuid4())
        with self.db.connect() as connection:
            connection.execute('INSERT INTO cases VALUES (?)', (case,))
        accept(self.db, case, run, snapshot(case, [], [], []))
        graph = dict(case_id=case, analysis_run_id=run, nodes=[], edges=[])
        self.project(case_id=case, analysis_run_id=run, graph=graph, findings=[], triage=[])
        validator('Graph').validate(self.get(case_id=case, analysis_run_id=run))
        self.assertTrue(self.rebuild(case_id=case, analysis_run_id=run))

    def test_same_source_ids_in_two_runs_remain_independent(self):
        self.project()
        first = deepcopy(self.neo.partitions[(self.case, self.run)])
        first_run = self.run
        self.run = str(uuid4())
        accept(self.db, self.case, self.run, self.manifest)
        self.graph, self.findings, self.triage = self.outputs(self.run)
        self.project()
        self.assertEqual(self.neo.partitions[(self.case, first_run)], first)
        self.assertEqual(len(self.neo.partitions), 2)
        self.rebuild()
        self.assertEqual(self.neo.partitions[(self.case, first_run)], first)


class RealProducerTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, neo):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(root / 'db.sqlite3', storage_dir=root / 'private',
                token_verifier=SyntheticTokenVerifier({'local': 'investigator-1'}))
            async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app),
                    base_url='http://test', headers={'Authorization': 'Bearer local'}) as client:
                response = await client.post('/api/v1/cases', json={'title': 'Synthetic A01B'})
                self.assertEqual(response.status_code, 201)
                case, run = response.json()['id'], str(uuid4())
                base = f'/api/v1/cases/{case}'
                pids = []
                for name, kind in (('network.csv', 'network_log'), ('gps.csv', 'gps')):
                    data = (ROOT / 'fixtures/synthetic-case' / name).read_bytes()
                    if kind == 'gps':
                        data += b'2026-01-12T10:03:00Z,D-7,12.9716,77.5946\n'
                    response = await client.post(base + '/evidence', data={'kind': kind, 'source_label': 'Synthetic'},
                        files={'file': (name, data, 'text/csv')})
                    self.assertEqual(response.status_code, 201)
                    eid = response.json()['id']
                    response = await client.post(base + f'/evidence/{eid}/processing-runs',
                                                headers={'Idempotency-Key': str(uuid4())})
                    self.assertEqual(response.status_code, 202)
                    pids.append(response.json()['id'])
                    response = await client.get(base + f'/evidence/{eid}/processing-runs/{pids[-1]}')
                    self.assertEqual(response.json()['status'], 'completed')
                pages = {}
                for path in ('evidence', 'entities', 'events', 'observations'):
                    response = await client.get(base + '/' + path, params={'limit': 100})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(len(response.json()['items']), response.json()['total'])
                    pages[path] = response.json()['items']
                nodes = build_graph_nodes(case, pages['evidence'], pages['entities'], pages['events'])
                edges, findings = derive_candidate_links(case, run, pages['entities'], pages['observations'])
                self.assertTrue(edges)
                evidence_ids = [item['id'] for item in pages['evidence']]
                triage = []
                for eid in evidence_ids:
                    count = sum(o['evidence_id'] == eid for o in pages['observations'])
                    relevance = calculate_relevance_factor(case_id=case, evidence_id=eid,
                        target_entities=[e for e in pages['entities'] if eid in e['evidence_ids']],
                        known_case_entities=pages['entities'], evidence_records=pages['evidence'],
                        observations=pages['observations'])
                    connectivity = calculate_connectivity_factor(case_id=case, evidence_id=eid,
                        target_nodes=nodes, edges=edges, observation_count=count)
                    triage.append(aggregate_triage_result(case_id=case, analysis_run_id=run, evidence_id=eid,
                        observation_count=count, factors=[relevance, connectivity], case_evidence_ids=evidence_ids))
                db = app.state.database
                projection.initialize_graph_projection(db)
                accept(db, case, run, snapshot(case, evidence_ids, pids, [o['id'] for o in pages['observations']]))
                graph = dict(case_id=case, analysis_run_id=run, nodes=[n.to_wire() for n in nodes],
                             edges=[e.to_wire() for e in edges])
                try:
                    projection.project_analysis_run(db, neo, case_id=case, analysis_run_id=run,
                        graph=graph, findings=[f.to_wire() for f in findings], triage=triage)
                    if isinstance(neo, Neo4jGraphDatabase):
                        # Prove actual projection loss fails read-back and rebuild
                        # restores it from immutable SQL, not an in-memory graph.
                        with neo.get_driver().session(database=neo.config.database) as session:
                            session.run(projection._DELETE_EDGES, case_id=case, run_id=run).consume()
                            session.run(projection._DELETE_NODES, case_id=case, run_id=run).consume()
                        with self.assertRaises(projection.ProjectionError):
                            projection.get_projected_graph(db, neo, case_id=case, analysis_run_id=run)
                        self.assertTrue(projection.rebuild_graph_partition(db, neo, case_id=case, analysis_run_id=run))
                        self.assertEqual(projection.get_projected_graph(db, neo, case_id=case, analysis_run_id=run), graph)
                    self.assertEqual(projection.get_projected_graph(db, neo, case_id=case, analysis_run_id=run), graph)
                    validator('Graph').validate(graph)
                    self.assertTrue(projection.rebuild_graph_partition(db, neo, case_id=case, analysis_run_id=run))
                    projection.project_analysis_run(db, neo, case_id=case, analysis_run_id=run,
                        graph=graph, findings=[f.to_wire() for f in findings], triage=triage)
                finally:
                    if isinstance(neo, Neo4jGraphDatabase):
                        with neo.get_driver().session(database=neo.config.database) as session:
                            params = dict(case_id=case, run_id=run)
                            session.run(projection._DELETE_EDGES, **params).consume()
                            session.run(projection._DELETE_NODES, **params).consume()

    async def test_merged_sources_nodes_links_factors_sql_and_synthetic_neo4j(self):
        await self.exercise(SyntheticNeo4j())

    @unittest.skipUnless(os.environ.get('EVORA_NEO4J_INTEGRATION') == '1', 'Opt-in disposable real Neo4j')
    async def test_real_neo4j_projection_and_rebuild_from_merged_producers(self):
        neo = Neo4jGraphDatabase()
        try:
            await self.exercise(neo)
        finally:
            neo.close()


if __name__ == '__main__':
    unittest.main()
