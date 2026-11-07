"""SQLite units of work, with SQLCipher at rest for local workstation accounts."""
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import os
import logging
import secrets
import sqlite3
import threading
import weakref

from filelock import FileLock
from backend.database_keys import KeyStore, private, sync_directory, atomic_json
from backend.errors import AccessError

# Third-party debug messages include private workstation paths.
logging.getLogger('filelock').setLevel(logging.WARNING)

HEADER = b'SQLite format 3\0'


class _DatabaseGate:
    """Concurrent SQLite units; exclusive migration/key changes; one backend process."""
    def __init__(self, path):
        self.condition = threading.Condition(threading.RLock())
        self.active = {}
        self.owner = None
        self.depth = 0
        self.lease_count = 0
        self.lease = FileLock(str(path) + '.lock', thread_local=False)

    @contextmanager
    def connection(self):
        thread = threading.get_ident()
        with self.condition:
            while self.owner is not None and self.owner != thread:
                self.condition.wait()
            self.active[thread] = self.active.get(thread, 0) + 1
        try:
            yield
        finally:
            with self.condition:
                self.active[thread] -= 1
                if not self.active[thread]:
                    del self.active[thread]
                self.condition.notify_all()

    @contextmanager
    def exclusive(self):
        thread = threading.get_ident()
        with self.condition:
            while (self.owner is not None and self.owner != thread) or any(t != thread for t in self.active):
                self.condition.wait()
            self.owner = thread
            self.depth += 1
        try:
            yield
        finally:
            with self.condition:
                self.depth -= 1
                if not self.depth:
                    self.owner = None
                self.condition.notify_all()


_GATES = weakref.WeakValueDictionary()
_GATES_LOCK = threading.Lock()


def _gate(path):
    with _GATES_LOCK:
        identity = str(path.resolve())
        result = _GATES.get(identity)
        if result is None:
            result = _DatabaseGate(path)
            _GATES[identity] = result
        return result


class SQLiteDatabase:
    def __init__(self, path: Path, *, protect=False):
        self.path = path
        self.protect = protect
        self.keys = KeyStore(Path(str(path) + '.keys.json'))
        self._key = None
        self._gate = _gate(path)

    @property
    def encrypted(self):
        if not self.path.is_file() or self.path.stat().st_size == 0:
            return False
        with self.path.open('rb') as source:
            header = source.read(16)
        return header != HEADER and self.keys.path.exists()

    @property
    def locked(self):
        return self.encrypted and self._key is None

    @contextmanager
    def guard(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._gate.exclusive():
            yield

    def _open(self, key=None):
        if key is None:
            driver = sqlite3
        else:
            from sqlcipher3 import dbapi2 as driver
        connection = driver.connect(self.path, timeout=60.0)
        try:
            if key is not None:
                connection.execute(f'''PRAGMA key = "x'{key.hex()}'"''')
                connection.execute('PRAGMA cipher_memory_security = ON')
                connection.execute('PRAGMA temp_store = MEMORY')
            connection.row_factory = driver.Row
            connection.execute('PRAGMA foreign_keys = ON')
            connection.execute('PRAGMA busy_timeout = 60000')
            return connection
        except Exception:
            connection.close()
            raise

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._gate.connection():
            if self.locked:
                raise AccessError(401, 'DATABASE_LOCKED', 'Sign in with your password to unlock the database.')
            connection = self._open(self._key if self.encrypted else None)
            try:
                connection.execute('PRAGMA journal_mode = WAL')
                with connection:
                    yield connection
            except Exception as error:
                # SQLCipher's DB-API exceptions are distinct from stdlib sqlite3.
                if type(error).__module__.startswith('sqlcipher3'):
                    raise getattr(sqlite3, type(error).__name__, sqlite3.DatabaseError)(str(error)) from None
                raise
            finally:
                connection.close()

    def unlock(self, username, secret, *, recovery=False):
        """Do not retain a key until the encrypted account authorizes this credential."""
        from backend.local_auth import digest, verify
        with self.guard():
            if not self.locked:
                return False
            purpose = 'recovery' if recovery else 'password'
            for key in self.keys.candidates(username, secret, purpose):
                connection = self._open(key)
                try:
                    user = connection.execute('SELECT * FROM local_users WHERE username=? COLLATE NOCASE', (username,)).fetchone()
                    valid = user is not None and not user['disabled'] and (
                        secrets.compare_digest(user['recovery_hash'] or '', digest(secret)) if recovery
                        else verify(user['password_hash'], secret))
                    if valid:
                        # Persisted browser cookies cannot bypass password entry after restart.
                        connection.execute('DELETE FROM local_sessions')
                        connection.commit()
                        self._key = key
                        return True
                finally:
                    connection.close()
            raise AccessError(400 if recovery else 401, 'INVALID_RECOVERY' if recovery else 'INVALID_LOGIN',
                'Username or recovery code is incorrect.' if recovery else 'Username or password is incorrect. If this is an older account, ask an administrator to unlock EVORA first.')

    def enable(self, username, password, recovery):
        """Export and verify an encrypted copy, then atomically replace the original.

        Wrapped keys reach stable storage before the encrypted database does. At a
        crash boundary the database is either the original or the verified export.
        No plaintext backup is made by migration.
        """
        if not self.protect:
            return
        with self.guard():
            if self.encrypted:
                return
            from sqlcipher3 import dbapi2 as cipher
            key = secrets.token_bytes(32)
            temporary = self.path.with_name(self.path.name + '.' + secrets.token_hex(8) + '.encrypted.tmp')
            try:
                source = cipher.connect(self.path)
                try:
                    source.execute('PRAGMA temp_store = MEMORY')
                    source.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                    if source.execute('PRAGMA journal_mode = DELETE').fetchone()[0] != 'delete':
                        raise RuntimeError('Close other EVORA processes before encrypting this database.')
                    source.execute('ATTACH DATABASE ? AS protected KEY "x\'' + key.hex() + '\'"', (str(temporary),))
                    source.execute("SELECT sqlcipher_export('protected')")
                    for setting in ('user_version', 'application_id'):
                        value = source.execute('PRAGMA ' + setting).fetchone()[0]
                        source.execute('PRAGMA protected.' + setting + ' = ' + str(int(value)))
                    source.execute('DETACH DATABASE protected')
                    private(temporary)
                    check = cipher.connect(temporary)
                    try:
                        check.execute(f'''PRAGMA key = "x'{key.hex()}'"''')
                        if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or check.execute('PRAGMA cipher_integrity_check').fetchall():
                            raise RuntimeError('Encrypted database verification failed.')
                        # Verify every table's rows and schema, not just SQLite page structure.
                        tables = source.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
                        if tables != check.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
                            raise RuntimeError('Encrypted schema verification failed.')
                        schema = 'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'
                        if source.execute(schema).fetchall() != check.execute(schema).fetchall():
                            raise RuntimeError('Encrypted database objects verification failed.')
                        for name, _ in tables:
                            quoted = '"' + name.replace('"', '""') + '"'
                            if sorted(source.execute('SELECT * FROM '+quoted).fetchall(), key=repr) != sorted(check.execute('SELECT * FROM '+quoted).fetchall(), key=repr):
                                raise RuntimeError('Encrypted row verification failed.')
                    finally:
                        check.close()
                    # Windows requires a writable handle when flushing the file.
                    with temporary.open('r+b') as file:
                        os.fsync(file.fileno())
                    self.keys.create(key, username, password, recovery)
                finally:
                    source.close()
                os.replace(temporary, self.path)
                self._key = key
                sync_directory(self.path.parent)
            finally:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def credentials(self, username, password=None, recovery=None):
        """Coordinate password/reset key changes with the caller's SQL transaction."""
        with self.guard():
            if not self.encrypted or (password is None and recovery is None):
                yield
                return
            if self._key is None:
                raise AccessError(401, 'DATABASE_LOCKED', 'Sign in to unlock the database.')
            previous = self.keys.read()
            final = self.keys.stage(self._key, username, password, recovery)
            try:
                yield
            except BaseException:
                atomic_json(self.keys.path, previous)
                raise
            else:
                self.keys.finish(username, final)

    def acquire_process(self):
        if not self.protect:
            return
        from filelock import Timeout
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._gate.condition:
            if self._gate.lease_count == 0:
                try:
                    self._gate.lease.acquire(timeout=0)
                except Timeout:
                    raise RuntimeError('This database is already open in another EVORA backend. Close that backend before starting EVORA again.') from None
            self._gate.lease_count += 1

    def release_process(self):
        if not self.protect:
            return
        with self._gate.condition:
            self._gate.lease_count -= 1
            if self._gate.lease_count == 0:
                self._gate.lease.release()

    def forget_key(self):
        self._key = None
