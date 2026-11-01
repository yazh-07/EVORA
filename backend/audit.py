"""F06 append-only intake accounting; private source details are not public audit."""

import sqlite3
from uuid import uuid4

from backend.database import SQLiteDatabase


INTAKE_RECORD_VERSION = "intake-source.v1"


def initialize_audit(database: SQLiteDatabase) -> None:
    """Add empty accounting tables without fabricating historical intake actors."""
    with database.connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS audit_events ("
            "id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), "
            "actor_id TEXT NOT NULL, action TEXT NOT NULL, target_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, reason TEXT) WITHOUT ROWID"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS intake_provenance ("
            "id TEXT PRIMARY KEY, record_version TEXT NOT NULL, "
            "audit_event_id TEXT NOT NULL UNIQUE REFERENCES audit_events(id), "
            "evidence_id TEXT NOT NULL UNIQUE REFERENCES evidence(id), "
            "source_filename TEXT NOT NULL, source_label TEXT NOT NULL, "
            "media_type TEXT NOT NULL, acquired_at TEXT, "
            "original_sha256 TEXT NOT NULL, original_size_bytes INTEGER NOT NULL, "
            "created_at TEXT NOT NULL) WITHOUT ROWID"
        )
        # Static, application-owned table/column names only. No request values
        # enter DDL. WITHOUT ROWID removes the hidden-rowid replacement path.
        for table, unique_columns in (
            ("audit_events", ("id",)),
            ("intake_provenance", ("id", "audit_event_id", "evidence_id")),
        ):
            for operation in ("UPDATE", "DELETE"):
                connection.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} "
                    f"BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Intake records are append-only.'); END"
                )
            # REPLACE can bypass SQLite delete triggers when recursive triggers
            # are off. Reject collisions before INSERT, including UPSERT/REPLACE.
            collision = " OR ".join(f"{column} = NEW.{column}" for column in unique_columns)
            connection.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
                f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {collision}) "
                "BEGIN SELECT RAISE(ABORT, 'Intake records are append-only.'); END"
            )


def record_intake(
    connection: sqlite3.Connection, *, actor_id: str, case_id: str, evidence_id: str,
) -> None:
    """Append inside the caller's evidence transaction; never commit separately.

    Read the authoritative inserted metadata, with its same-case check, instead
    of accepting an alternate metadata/actor/time envelope from the upload form.
    The actor comes from the authenticated grant. Source values stay private;
    public audit contains only server identities and operation/resource references.
    """
    row = connection.execute(
        "SELECT filename, source_label, media_type, acquired_at, sha256, size_bytes, created_at "
        "FROM evidence WHERE id = ? AND case_id = ?", (evidence_id, case_id),
    ).fetchone()
    if row is None:
        raise ValueError("Intake evidence record missing.")
    event_id = str(uuid4())
    connection.execute(
        "INSERT INTO audit_events (id, case_id, actor_id, action, target_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, case_id, actor_id, "uploadEvidence", evidence_id, row["created_at"]),
    )
    connection.execute(
        "INSERT INTO intake_provenance (id, record_version, audit_event_id, evidence_id, "
        "source_filename, source_label, media_type, acquired_at, original_sha256, "
        "original_size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), INTAKE_RECORD_VERSION, event_id, evidence_id, row["filename"],
         row["source_label"], row["media_type"], row["acquired_at"], row["sha256"],
         row["size_bytes"], row["created_at"]),
    )
