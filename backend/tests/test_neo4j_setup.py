"""G01D unit/socket controls and opt-in disposable real Neo4j acceptance."""

from dataclasses import FrozenInstanceError, replace
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from neo4j.exceptions import AuthError, ConstraintError, ServiceUnavailable

from backend.graph_db import (
    GraphDatabaseError, Neo4jConfig, Neo4jGraphDatabase,
    Neo4jUnavailableError, SCHEMA_STATEMENTS,
)


def config(**kwargs):
    # Deliberately synthetic, never a service credential.
    return Neo4jConfig(password="synthetic-unit-test-password", **kwargs)


class ConfigTests(unittest.TestCase):
    def test_environment_defaults_and_explicit_loading(self):
        with patch.dict(os.environ, {"NEO4J_PASSWORD": "synthetic-unit-test-password"}, clear=True):
            value = Neo4jConfig.from_env()
            self.assertEqual(value.uri, "bolt://127.0.0.1:7687")
            self.assertEqual(value.user, "neo4j")
            self.assertEqual(value.database, "neo4j")
            self.assertEqual(value.connection_timeout, 1.0)
            self.assertEqual(Neo4jGraphDatabase().config, value)
        value = Neo4jConfig.from_env(dict(
            NEO4J_URI="bolt+s://localhost:7688", NEO4J_USER="graph-user",
            NEO4J_PASSWORD="  synthetic-value  ", NEO4J_DATABASE="private-graph",
            NEO4J_CONNECTION_TIMEOUT="0.25",
        ))
        self.assertEqual(value.uri, "bolt+s://localhost:7688")
        self.assertEqual(value.user, "graph-user")
        self.assertEqual(value.database, "private-graph")
        self.assertEqual(value.password, "  synthetic-value  ")
        self.assertEqual(value.connection_timeout, 0.25)
        with self.assertRaises(FrozenInstanceError):
            value.database = "changed"
        self.assertNotIn(value.password, repr(value))
        self.assertNotIn(value.uri, repr(value))

    def test_required_credentials_database_and_timeout_validation(self):
        for env in ({}, {"NEO4J_PASSWORD": " "}, {"NEO4J_PASSWORD": "\x00"}):
            with self.subTest(env_keys=list(env)), self.assertRaises(GraphDatabaseError):
                Neo4jConfig.from_env(env)
        for name in ("user", "database", "password"):
            for value in ("", " \t", None, 1, "bad\x00value"):
                with self.subTest(name=name, value=value), self.assertRaises(GraphDatabaseError):
                    replace(config(), **{name: value})
        for value in (0, -1, 2.01, 10**400, float("nan"), float("inf"), True, None, "1"):
            with self.subTest(timeout=value), self.assertRaises(GraphDatabaseError):
                config(connection_timeout=value)
        for value in ("bad", "", "nan", "inf", "0", "-1", "3"):
            with self.subTest(env_timeout=value), self.assertRaises(GraphDatabaseError):
                Neo4jConfig.from_env({"NEO4J_PASSWORD": "synthetic", "NEO4J_CONNECTION_TIMEOUT": value})

    def test_uri_validation_never_exposes_supplied_values(self):
        for value in ("http://localhost:7474", "bolt://", "bolt://host:0", "bolt://host:65536",
                      "bolt://host:invalid", "bolt://[", "bolt://host/path", "bolt://host?x=1",
                      "bolt://host#fragment", "bolt://user:synthetic-secret@host", " bolt://host",
                      "bolt://host\n", None, 123):
            with self.subTest(uri=value), self.assertRaises(GraphDatabaseError) as caught:
                config(uri=value)
            self.assertNotIn("synthetic-secret", str(caught.exception))
        for scheme in ("bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc"):
            self.assertEqual(config(uri=scheme + "://[::1]:7687").uri, scheme + "://[::1]:7687")


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.factory = patch("backend.graph_db.GraphDatabase.driver").start()
        self.addCleanup(patch.stopall)
        self.driver = self.factory.return_value
        self.session = self.driver.session.return_value.__enter__.return_value
        self.db = Neo4jGraphDatabase(config(database="private-graph"))
        self.addCleanup(self.db.close)

    def test_lazy_driver_reuse_configured_database_and_bounded_no_retry_settings(self):
        self.factory.assert_not_called()
        self.assertIs(self.db.get_driver(), self.driver)
        self.assertIs(self.db.get_driver(), self.driver)
        self.factory.assert_called_once_with(
            self.db.config.uri, auth=(self.db.config.user, self.db.config.password),
            database="private-graph", connection_timeout=1.0,
            connection_acquisition_timeout=1.0, connection_write_timeout=1.0,
            max_transaction_retry_time=0.0, disable_auto_commit_retries=True,
            telemetry_disabled=True,
        )
        self.assertTrue(self.db.verify_connectivity())
        self.driver.session.assert_called_once_with(database="private-graph")
        query = self.session.run.call_args.args[0]
        self.assertEqual(query.text, "RETURN 1 AS connected")
        self.assertEqual(query.timeout, 1.0)
        self.session.run.return_value.consume.assert_called_once()
        self.driver.session.return_value.__exit__.assert_called_once()

    def test_close_is_idempotent_and_reopens_lazily(self):
        self.db.close()
        self.factory.assert_not_called()
        self.db.get_driver()
        self.db.close()
        self.db.close()
        self.driver.close.assert_called_once()
        self.db.get_driver()
        self.assertEqual(self.factory.call_count, 2)

    def test_creation_and_connectivity_failures_are_typed_and_sanitized(self):
        for error in (ServiceUnavailable, AuthError, OSError, TimeoutError):
            with self.subTest(error=error):
                self.factory.side_effect = error("synthetic-secret at private-host")
                with self.assertRaises(Neo4jUnavailableError) as caught:
                    self.db.get_driver()
                self.assertIsNone(self.db._driver)
                self.assertEqual(str(caught.exception), "Graph database is unavailable.")
        self.factory.side_effect = None
        for stage in (self.session.run, self.session.run.return_value.consume):
            for error in (ServiceUnavailable, AuthError, TimeoutError):
                with self.subTest(stage=stage, error=error):
                    stage.side_effect = error("synthetic-secret at private-host")
                    with self.assertRaises(Neo4jUnavailableError) as caught:
                        self.db.verify_connectivity()
                    rendered = "".join(traceback.format_exception(caught.exception))
                    self.assertNotIn("synthetic-secret", rendered)
                    self.assertNotIn("private-host", rendered)
                    stage.side_effect = None

    def test_session_acquisition_failure_is_safe(self):
        self.driver.session.side_effect = ServiceUnavailable("synthetic-private-details")
        with self.assertRaisesRegex(Neo4jUnavailableError, "^Graph database is unavailable.$"):
            self.db.verify_connectivity()

    def test_close_failure_is_safe_and_detaches_driver(self):
        self.db.get_driver()
        self.driver.close.side_effect = OSError("synthetic-secret")
        with self.assertRaisesRegex(GraphDatabaseError, "^Graph database cleanup failed.$"):
            self.db.close()
        self.assertIsNone(self.db._driver)
        self.db.close()


class SchemaTests(unittest.TestCase):
    def test_static_partitioned_ddl_is_idempotent_and_consumed(self):
        db = Neo4jGraphDatabase(config())
        session = MagicMock()
        db.setup_schema(session)
        first = [call.args[0].text for call in session.run.call_args_list]
        self.assertEqual(first, list(SCHEMA_STATEMENTS))
        self.assertIn("FOR (n:Node) REQUIRE (n.case_id, n.analysis_run_id, n.id) IS UNIQUE", first[0])
        self.assertIn("FOR ()-[e:Edge]-() REQUIRE (e.case_id, e.analysis_run_id, e.id) IS UNIQUE", first[1])
        self.assertEqual(sum("CREATE CONSTRAINT" in query for query in first), 2)
        self.assertEqual(sum("CREATE INDEX" in query for query in first), 4)
        for variable in ("n", "e"):
            self.assertTrue(any(f"ON ({variable}.case_id, {variable}.analysis_run_id)" in q for q in first))
            self.assertTrue(any(f"ON ({variable}.case_id, {variable}.id)" in q for q in first))
        for call in session.run.call_args_list:
            self.assertIn("IF NOT EXISTS", call.args[0].text)
            self.assertEqual(call.args[0].timeout, 1.0)
            self.assertNotIn(db.config.password, call.args[0].text)
        db.setup_schema(session)
        self.assertEqual([call.args[0].text for call in session.run.call_args_list], first * 2)
        self.assertEqual(session.run.return_value.consume.call_count, 12)
        session.close.assert_not_called()  # caller owns the session

    def test_partial_schema_failure_stops_without_reporting_success(self):
        for error, expected in ((ServiceUnavailable("synthetic-secret"), Neo4jUnavailableError),
                                (ConstraintError("synthetic-secret"), GraphDatabaseError)):
            with self.subTest(error=type(error)):
                db = Neo4jGraphDatabase(config())
                session = MagicMock()
                session.run.side_effect = [MagicMock(), error]
                with self.assertRaises(expected) as caught:
                    db.setup_schema(session)
                self.assertNotIn("synthetic-secret", str(caught.exception))
                self.assertEqual(session.run.call_count, 2)
                session.run.side_effect = None
                db.setup_schema(session)  # recover by rerunning the entire DDL
                self.assertEqual(session.run.call_count, 8)

    def test_deferred_schema_failure_on_consume_is_not_success(self):
        session = MagicMock()
        session.run.return_value.consume.side_effect = ConstraintError("synthetic-secret")
        with self.assertRaisesRegex(GraphDatabaseError, "^Graph schema setup failed.$"):
            Neo4jGraphDatabase(config()).setup_schema(session)
        self.assertEqual(session.run.call_count, 1)


class SocketFailureTests(unittest.TestCase):
    def check_unavailable(self, port):
        # A subprocess deadline makes a hanging regression fail the test rather
        # than hang the suite. The real driver, not a mock, opens the socket.
        code = """
import sys, time
from backend.graph_db import Neo4jConfig, Neo4jGraphDatabase, Neo4jUnavailableError
db = Neo4jGraphDatabase(Neo4jConfig(uri=sys.argv[1], password='synthetic-socket-test', connection_timeout=0.35))
start = time.monotonic()
try:
    db.verify_connectivity()
except Neo4jUnavailableError as error:
    assert str(error) == 'Graph database is unavailable.'
    print('UNAVAILABLE', time.monotonic() - start)
else:
    raise AssertionError('Unavailable database reported success')
finally:
    db.close()
"""
        started = time.monotonic()
        result = subprocess.run([sys.executable, "-W", "error::ResourceWarning", "-c", code,
                                 f"bolt://127.0.0.1:{port}"], capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("UNAVAILABLE "), result.stdout)
        self.assertLess(float(result.stdout.split()[1]), 2.0)
        self.assertLess(time.monotonic() - started, 2.0)

    def test_refused_loopback_port_fails_within_two_seconds(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))  # reserved, deliberately not listening
            self.check_unavailable(sock.getsockname()[1])

    def test_accepted_connection_with_stalled_bolt_handshake_is_bounded(self):
        stop = threading.Event()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(2)

            def stall():
                try:
                    connection, _ = listener.accept()
                    with connection:
                        stop.wait(2)
                except (TimeoutError, OSError):
                    pass

            worker = threading.Thread(target=stall)
            worker.start()
            try:
                self.check_unavailable(listener.getsockname()[1])
            finally:
                stop.set()
                worker.join(timeout=3)
            self.assertFalse(worker.is_alive())


@unittest.skipUnless(os.environ.get("EVORA_NEO4J_INTEGRATION") == "1",
                     "Opt-in real Neo4j: use a disposable database and backend NEO4J_* configuration")
class RealNeo4jTests(unittest.TestCase):
    def setUp(self):
        self.db = Neo4jGraphDatabase()
        self.addCleanup(self.db.close)
        self.case_id = str(uuid4())
        self.other_case = str(uuid4())
        self.run_id = str(uuid4())
        self.other_run = str(uuid4())
        self.source_id = str(uuid4())

    def test_real_connectivity_schema_twice_and_schema_readback(self):
        self.assertTrue(self.db.verify_connectivity())
        with self.db.get_driver().session(database=self.db.config.database) as session:
            version = session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS version").single()["version"]
            self.assertEqual(version, "5.26.0")
            self.db.setup_schema(session)
            self.db.setup_schema(session)
            constraints = {row["name"]: row for row in session.run("SHOW CONSTRAINTS").data()}
            for name, entity in (("evora_node_identity_v1", "NODE"), ("evora_edge_identity_v1", "RELATIONSHIP")):
                self.assertEqual(constraints[name]["properties"], ["case_id", "analysis_run_id", "id"])
                self.assertEqual(constraints[name]["entityType"], entity)
            session.run("CALL db.awaitIndexes($seconds)", seconds=10).consume()
            indexes = {row["name"]: row for row in session.run("SHOW INDEXES").data()}
            for kind in ("node", "edge"):
                for suffix, properties in (("partition", ["case_id", "analysis_run_id"]), ("source", ["case_id", "id"])):
                    row = indexes[f"evora_{kind}_{suffix}_v1"]
                    self.assertEqual(row["properties"], properties)
                    self.assertEqual(row["state"], "ONLINE")

    def test_real_invalid_auth_is_safe_and_bounded(self):
        db = Neo4jGraphDatabase(replace(self.db.config, password="synthetic-invalid-password"))
        self.addCleanup(db.close)
        start = time.monotonic()
        with self.assertRaises(Neo4jUnavailableError) as caught:
            db.verify_connectivity()
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(str(caught.exception), "Graph database is unavailable.")

    def test_real_missing_database_fails_closed(self):
        db = Neo4jGraphDatabase(replace(self.db.config, database="g01d-nonexistent"))
        self.addCleanup(db.close)
        with self.assertRaises(Neo4jUnavailableError):
            db.verify_connectivity()

    def test_real_node_and_relationship_uniqueness_with_case_run_isolation(self):
        parameters = dict(case_id=self.case_id, run_id=self.run_id, source_id=self.source_id)
        with self.db.get_driver().session(database=self.db.config.database) as session:
            self.db.setup_schema(session)
            try:
                for case, run in ((self.case_id, self.run_id), (self.case_id, self.other_run),
                                  (self.other_case, self.run_id)):
                    session.run(
                        "CREATE (n:Node {case_id:$case_id, analysis_run_id:$run_id, id:$source_id}) "
                        "CREATE (n)-[:Edge {case_id:$case_id, analysis_run_id:$run_id, id:$source_id}]->(n)",
                        case_id=case, run_id=run, source_id=self.source_id,
                    ).consume()
                with self.assertRaises(ConstraintError):
                    session.run("CREATE (:Node {case_id:$case_id, analysis_run_id:$run_id, id:$source_id})",
                                **parameters).consume()
                with self.assertRaises(ConstraintError):
                    session.run(
                        "MATCH (n:Node {case_id:$case_id, analysis_run_id:$run_id, id:$source_id}) "
                        "CREATE (n)-[:Edge {case_id:$case_id, analysis_run_id:$run_id, id:$source_id}]->(n)",
                        **parameters,
                    ).consume()
                rows = session.run(
                    "MATCH (n:Node {id:$source_id}) WHERE n.case_id IN $cases "
                    "RETURN n.case_id AS case_id, n.analysis_run_id AS run_id",
                    source_id=self.source_id, cases=[self.case_id, self.other_case],
                ).data()
                self.assertEqual({(row["case_id"], row["run_id"]) for row in rows}, {
                    (self.case_id, self.run_id), (self.case_id, self.other_run), (self.other_case, self.run_id),
                })
            finally:
                session.run("MATCH (n:Node {id:$source_id}) WHERE n.case_id IN $cases DETACH DELETE n",
                            source_id=self.source_id, cases=[self.case_id, self.other_case]).consume()


if __name__ == "__main__":
    unittest.main()
