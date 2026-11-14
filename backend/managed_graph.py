"""Own a bundled JVM graph process; never attach to or stop another server."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

from filelock import FileLock
from neo4j import GraphDatabase
from backend.database_keys import atomic_json
from backend.process_owner import alive


class ManagedGraph:
    def __init__(self, runtime, home, *, timeout=150, owner_pid=None):
        self.runtime, self.home = Path(runtime).resolve(), Path(home).resolve()
        self.timeout = timeout
        self.process = None
        self.log = None
        self.lock = None
        self.stop_path = self.home / ('stop-' + secrets.token_hex(16))
        self.environment = None
        self.owner_pid = owner_pid or os.getpid()

    def java(self):
        return self.runtime / 'java/bin' / ('java.exe' if os.name == 'nt' else 'java')

    def command(self, main, *args):
        classpath = str(self.runtime / 'classes') + os.pathsep + str(self.runtime / 'neo4j/lib/*')
        return [str(self.java()), '-Xms128m', '-Xmx512m', '-XX:+UseG1GC',
                '--add-opens=java.base/java.nio=ALL-UNNAMED',
                '--add-opens=java.base/java.io=ALL-UNNAMED',
                '--add-opens=java.base/sun.nio.ch=ALL-UNNAMED',
                '--enable-native-access=ALL-UNNAMED', '-cp', classpath, main, *map(str, args)]

    def start(self):
        if self.process is not None:
            raise RuntimeError('Graph runtime already started')
        if not self.java().is_file() or not (self.runtime / 'classes/GraphHost.class').is_file():
            raise RuntimeError('Bundled graph runtime is missing. Reinstall EVORA.')
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == 'nt':
            from backend.windows_credentials import secure_path
            secure_path(self.home, directory=True)
        else:
            self.home.chmod(0o700)
        self.lock = FileLock(str(self.home / 'runtime.lock'))
        self.lock.acquire(timeout=0)
        try:
            return self._start()
        except BaseException:
            self.close()
            raise

    def _start(self):
        credentials = self.home / 'credentials.json'
        if credentials.exists():
            password = json.loads(credentials.read_text())['password']
            if not isinstance(password, str) or len(password) < 32:
                raise RuntimeError('Invalid private graph credentials')
        else:
            if (self.home / 'data/databases/system').exists():
                raise RuntimeError('Graph credentials are missing; existing data was preserved')
            password = secrets.token_urlsafe(48)
            atomic_json(credentials, {'password': password})
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', 0))
            port = candidate.getsockname()[1]
        conf = self.home / 'conf'
        conf.mkdir(exist_ok=True)
        config = conf / 'neo4j.conf'
        config.write_text('\n'.join([
            'server.default_listen_address=127.0.0.1',
            'server.bolt.enabled=true',
            f'server.bolt.listen_address=127.0.0.1:{port}',
            f'server.bolt.advertised_address=127.0.0.1:{port}',
            'server.http.enabled=false', 'server.https.enabled=false',
            'dbms.security.auth_enabled=true', 'dbms.usage_report.enabled=false',
            'server.memory.pagecache.size=128m',
            'server.directories.data=' + (self.home / 'data').as_posix(),
            'server.directories.logs=' + (self.home / 'logs').as_posix(),
            'server.directories.run=' + (self.home / 'run').as_posix(),
        ]) + '\n', encoding='utf-8')
        env = {k: v for k, v in os.environ.items() if k not in
               {'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH', 'NEO4J_AUTH'}}
        env.update(JAVA_HOME=str(self.runtime / 'java'), NEO4J_HOME=str(self.runtime / 'neo4j'), NEO4J_CONF=str(conf))
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        # Only initialize a new store. Never reset a password on an existing graph.
        if not (self.home / 'data/databases/system').exists():
            try:
                # Generated secrets may begin with '-'; terminate option parsing.
                subprocess.run(self.command('org.neo4j.cli.AdminTool', 'dbms', 'set-initial-password', '--', password),
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=True, timeout=90, **options)
            except (OSError, subprocess.SubprocessError):
                # CalledProcessError/TimeoutExpired include argv, including the secret.
                raise RuntimeError('Could not initialize private graph credentials') from None
        self.log = (self.home / 'runtime.log').open('ab')
        self.process = subprocess.Popen(self.command('GraphHost', self.home, config, self.stop_path, os.getpid(), self.owner_pid),
                                        env=env, stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log, **options)
        uri = f'bolt://127.0.0.1:{port}'
        deadline = time.monotonic() + self.timeout
        with GraphDatabase.driver(uri, auth=('neo4j', password), connection_timeout=1,
                                  connection_acquisition_timeout=2, max_transaction_retry_time=0) as driver:
            while time.monotonic() < deadline:
                if not alive(self.owner_pid):
                    raise RuntimeError('Desktop closed during graph startup')
                if self.process.poll() is not None:
                    raise RuntimeError('Bundled graph stopped during startup; see graph/runtime.log')
                try:
                    driver.verify_connectivity()
                    self.environment = {'NEO4J_URI': uri, 'NEO4J_USER': 'neo4j',
                                        'NEO4J_PASSWORD': password, 'NEO4J_DATABASE': 'neo4j'}
                    return self.environment
                except Exception:
                    time.sleep(.25)
        raise RuntimeError('Bundled graph startup timed out; see graph/runtime.log')

    def close(self):
        try:
            if self.process is not None:
                self.stop_path.touch()
                try:
                    self.process.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
                self.process = None
        finally:
            if self.log is not None:
                self.log.close()
                self.log = None
            self.stop_path.unlink(missing_ok=True)
            if self.lock is not None:
                self.lock.release()
                self.lock = None
