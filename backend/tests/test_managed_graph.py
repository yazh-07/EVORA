import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import traceback

from filelock import Timeout
from neo4j import GraphDatabase
from backend.managed_graph import ManagedGraph


class GraphPackagingTests(unittest.TestCase):
    def test_trim_removes_only_unused_neo4j_payload(self):
        from scripts.prepare_windows_graph import trim_neo4j
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('web','labs','bin','products','import','plugins','lib','licenses','conf'):
                (root/name).mkdir()
            (root/'LICENSE.txt').write_text('license')
            trim_neo4j(root)
            self.assertFalse((root/'web').exists())
            self.assertFalse((root/'labs').exists())
            self.assertTrue((root/'lib').is_dir())
            self.assertTrue((root/'licenses').is_dir())
            self.assertTrue((root/'conf').is_dir())
            self.assertTrue((root/'LICENSE.txt').is_file())

    def test_query_deadline_is_independent_and_diagnostics_exclude_exception_text(self):
        from backend.graph_db import Neo4jConfig, GraphDatabaseError, report_graph_error
        config = Neo4jConfig.from_env({'NEO4J_PASSWORD': 'private', 'NEO4J_QUERY_TIMEOUT': '60'})
        self.assertEqual(config.connection_timeout, 1)
        self.assertEqual(config.query_timeout, 60)
        for value in ('0', '121', 'nan', 'inf'):
            with self.assertRaises(GraphDatabaseError):
                Neo4jConfig.from_env({'NEO4J_PASSWORD': 'private', 'NEO4J_QUERY_TIMEOUT': value})
        with self.assertLogs('backend.graph_db', level='WARNING') as captured:
            report_graph_error('projection', RuntimeError('private evidence and credentials'))
        self.assertNotIn('private', '\n'.join(captured.output))

    def test_initialization_failure_does_not_log_the_password_and_releases_lock(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / 'runtime'
            (runtime / 'java/bin').mkdir(parents=True)
            (runtime / 'classes').mkdir()
            (runtime / 'java/bin' / ('java.exe' if os.name == 'nt' else 'java')).touch()
            (runtime / 'classes/GraphHost.class').touch()
            home = root / 'home'
            graph = ManagedGraph(runtime, home)
            def fail(command, **kwargs):
                raise subprocess.CalledProcessError(1, command)
            with patch('backend.managed_graph.subprocess.run', side_effect=fail):
                try:
                    graph.start()
                except RuntimeError:
                    rendered = traceback.format_exc()
                else:
                    self.fail('Initialization must fail')
            password = json.loads((home / 'credentials.json').read_text())['password']
            self.assertNotIn(password, rendered)
            from filelock import FileLock
            with FileLock(str(home / 'runtime.lock'), timeout=0):
                pass

    def test_missing_runtime_fails_without_creating_data(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            graph = ManagedGraph(root / 'missing', root / 'data')
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                graph.start()
            self.assertFalse((root / 'data').exists())

    def test_download_lock_has_explicit_artifacts_and_sha256(self):
        from scripts.prepare_windows_graph import ROOT
        lock = json.loads((ROOT / 'desktop/graph/runtime-lock.json').read_text())
        self.assertEqual(set(lock), {'version', 'neo4j', 'java', 'neo4j-source', 'java-source'})
        for name, artifact in lock.items():
            if name != 'version':
                self.assertTrue(artifact['url'].startswith('https://'))
                self.assertRegex(artifact['sha256'], r'^[0-9a-f]{64}$')

    def test_runtime_archive_rejects_traversal(self):
        from scripts.prepare_windows_graph import unpack
        import zipfile
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'bad.zip', 'w') as archive:
                archive.writestr('../escape', 'bad')
            with self.assertRaises(ValueError):
                unpack(root / 'bad.zip', root / 'unpacked')
            self.assertFalse((root / 'escape').exists())


@unittest.skipUnless(os.environ.get('EVORA_GRAPH_TEST_RUNTIME'), 'Requires an explicitly staged JVM/Neo4j runtime')
class ManagedGraphIntegrationTests(unittest.TestCase):
    def test_authenticated_restart_preserves_data_credentials_and_rejects_second_owner(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            graph = ManagedGraph(os.environ['EVORA_GRAPH_TEST_RUNTIME'], root)
            try:
                env = graph.start()
                self.assertNotEqual(env['NEO4J_PASSWORD'], 'neo4j')
                with GraphDatabase.driver(env['NEO4J_URI'], auth=('neo4j', env['NEO4J_PASSWORD'])) as driver:
                    driver.execute_query('CREATE (:EvoraSmoke {value: $value})', value='persistent', database_='neo4j')
                credential_bytes = (root / 'credentials.json').read_bytes()
                second = ManagedGraph(os.environ['EVORA_GRAPH_TEST_RUNTIME'], root)
                with self.assertRaises(Timeout):
                    second.start()
                self.assertIsNone(graph.process.poll())
                process = graph.process
                graph.close()
                self.assertEqual(process.returncode, 0)
                env = graph.start()
                self.assertTrue((root / 'credentials.json').read_bytes() == credential_bytes)
                with GraphDatabase.driver(env['NEO4J_URI'], auth=('neo4j', env['NEO4J_PASSWORD'])) as driver:
                    result = driver.execute_query('MATCH (n:EvoraSmoke) RETURN n.value AS value', database_='neo4j')
                    self.assertEqual(result.records[0]['value'], 'persistent')
                config = (root / 'conf/neo4j.conf').read_text()
                self.assertIn('server.http.enabled=false', config)
                self.assertIn('server.bolt.listen_address=127.0.0.1:', config)
                self.assertIn('dbms.usage_report.enabled=false', config)
                self.assertNotIn(env['NEO4J_PASSWORD'], config)
                self.assertNotIn(env['NEO4J_PASSWORD'], (root / 'runtime.log').read_text())
            finally:
                graph.close()

    def test_desktop_owner_death_stops_graph_cleanly(self):
        with TemporaryDirectory() as directory:
            owner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
            graph = ManagedGraph(os.environ['EVORA_GRAPH_TEST_RUNTIME'], directory, owner_pid=owner.pid)
            try:
                graph.start()
                process = graph.process
                owner.terminate()
                owner.wait(timeout=10)
                self.assertEqual(process.wait(timeout=45), 0)
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait()
                graph.close()
