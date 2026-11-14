"""Private authorized Q&A provenance storage (U10C / F08E).

Links prompt templates, retrieved source IDs/locators, model versions,
generated response, timestamp and verification details in private store.
"""
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4, uuid5


PROMPT_TEMPLATE_VERSION = "forensic-case-synthesis/3"
MODEL_VERSION = "deterministic-extractor/1"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def initialize_qa_provenance(connection):
    connection.execute("""
      CREATE TABLE IF NOT EXISTS qa_provenance (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        actor_id TEXT NOT NULL,
        retrieval_version TEXT NOT NULL,
        model_version TEXT,
        prompt_template_version TEXT,
        question_sha256 TEXT NOT NULL,
        supported INTEGER NOT NULL,
        citations_json TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    """)


def record_qa_provenance(connection, *, case_id: str, actor_id: str,
                         retrieval_version: str, question: str, answer: str,
                         citations: list[dict], supported: bool, created_at: str,
                         model_version: str | None = MODEL_VERSION,
                         prompt_template_version: str | None = PROMPT_TEMPLATE_VERSION,
                         context: dict | None = None, verification: dict | None = None) -> str:
    question_hash = hashlib.sha256(question.encode('utf-8')).hexdigest()
    provenance_id = str(uuid4())
    payload = {
        "provenance_id": provenance_id,
        "case_id": case_id,
        "actor_id": actor_id,
        "retrieval_version": retrieval_version,
        "model_version": model_version,
        "prompt_template_version": prompt_template_version,
        "question_hash": question_hash,
        "supported": supported,
        "citations": citations,
        "created_at": created_at,
        "answer": answer,
    }
    if context is not None:
        payload['context'] = context
        payload['context_sha256'] = hashlib.sha256(_json(context).encode()).hexdigest()
    if verification is not None:
        payload['verification'] = verification
    connection.execute("""
      INSERT INTO qa_provenance (
        id, case_id, actor_id, retrieval_version, model_version,
        prompt_template_version, question_sha256, supported,
        citations_json, payload_json, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        provenance_id, case_id, actor_id, retrieval_version, model_version,
        prompt_template_version, question_hash, 1 if supported else 0,
        _json(citations), _json(payload), created_at
    ))
    return provenance_id
