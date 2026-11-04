"""SQLite connections owned by one unit of work, never shared across requests."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class SQLiteDatabase:
    """File-backed SQLite connection manager; startup initializes domain schemas."""

    path: Path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Commit on success, roll back on failure, and always close."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=60.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 60000")
            connection.execute("PRAGMA journal_mode = WAL")
            with connection:
                yield connection
        finally:
            connection.close()
