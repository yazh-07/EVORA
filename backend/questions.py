"""Case-wide forensic synthesis from authorized snapshots and exact observation citations."""

from datetime import datetime, timezone
from collections import Counter, defaultdict
import httpx
import json
import re
from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit import record_audit_event
from backend.qa_synthesis import synthesize, SynthesisError
from backend.errors import AccessError
from backend.entities import _valid_entity
from backend.events import _valid_event
from backend.graph_nodes import build_graph_nodes, source_group
from backend.graph_links import derive_candidate_links, derive_semantic_links
from backend.auth import CaseAccessGrant, require_case_access
from backend.evidence import invalid_input
from backend.observations import _page, _utc_order, _valid_record, _validated_count
from backend.qa_provenance import (MODEL_VERSION, PROMPT_TEMPLATE_VERSION,
                                   initialize_qa_provenance, record_qa_provenance)


RETRIEVAL_VERSION = "case-context-retrieval/2"
_INSUFFICIENT = (
    "Insufficient evidence in this case to support the inquiry; "
    "candidate observations do not establish identity or guilt."
)
_TOKENS = re.compile(r"[^\W_]+(?:[.-][^\W_]+)*", re.UNICODE)
_IDENTITY_OR_GUILT = re.compile(
    r"\b(?:guilt\w*|innocen\w*|identity|identities|identify|identified|identification|"
    r"perpetrator\w*|culprit\w*|who|whose|whom|killer\w*|murderer\w*|"
    r"responsible|committed|criminal\w*|attacker\w*|offender\w*|"
    r"owner\w*|owns?|belongs?|real\s+name|used\s+by)\b", re.IGNORECASE,
)
_STOPWORDS = frozenset(
    "a an and are as at be been by can case could did do does evidence for from "
    "had has have how i in into is it me of on or please recorded records "
    "show shows tell that the their there these this to was were what when where "
    "whether which with would you about confirm confirms".split()
)


class CaseQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must contain non-whitespace characters.")
        return value


def _tokens(value: str) -> set[str]:
    return set(_TOKENS.findall(value.casefold()))


def _matching_observations(question: str, observations: list[dict]) -> list[dict]:
    if _IDENTITY_OR_GUILT.search(question):
        return []
    keywords = _tokens(question) - _STOPWORDS
    identifiers = {token for token in keywords if any(char.isdigit() for char in token)}
    terms = identifiers or keywords
    matches = []
    for observation in observations:
        values = _tokens(" ".join(observation[key] for key in
                                 ("kind", "raw_value", "normalized_value")))
        values.update(observation["kind"].casefold().split("."))
        if any(term in values or (re.fullmatch(r"\d+(?:\.\d+)+", term) and
               any(value.startswith(term + ".") for value in values)) for term in terms):
            matches.append(observation)
    return matches


def build_case_context(connection, case_id, observations):
    """One case-scoped read snapshot; stale analysis is explicitly excluded."""
    evidence = [dict(row) for row in connection.execute(
        "SELECT id,case_id,kind,filename,sha256,size_bytes,source_label FROM evidence WHERE case_id=? ORDER BY id",
        (case_id,))]
    observation_map = {item['id']: item for item in observations}
    entities, events, run_ids = [], [], []
    rows = connection.execute("""
        WITH ranked AS (
          SELECT r.*,ROW_NUMBER() OVER(PARTITION BY evidence_id ORDER BY
            evora_utc_order(finished_at) DESC,id DESC) AS rank
          FROM processing_runs r WHERE case_id=? AND status='completed')
        SELECT o.* FROM ranked r JOIN processing_outputs o ON o.run_id=r.id
        AND o.case_id=r.case_id AND o.evidence_id=r.evidence_id WHERE r.rank=1 ORDER BY r.id
        """, (case_id,)).fetchall()
    for row in rows:
        run_ids.append(row['run_id'])
        for field, target, validator in (('entities_json', entities, _valid_entity),
                                         ('events_json', events, _valid_event)):
            for item in json.loads(row[field]):
                if (not validator(json.dumps(item), case_id, row['evidence_id']) or
                        not set(item['observation_ids']) <= observation_map.keys() or
                        set(item['evidence_ids']) != {observation_map[oid]['evidence_id'] for oid in item['observation_ids']}):
                    raise AccessError(404, 'NOT_FOUND', 'Resource not found.')
                target.append(item)
    # Derived current graph remains useful before the first persisted analysis.
    context_id = str(uuid5(UUID(case_id), 'qa:' + ':'.join(sorted(run_ids))))
    nodes = build_graph_nodes(case_id, evidence, entities, events, observations)
    links, _ = derive_candidate_links(case_id, context_id, entities, observations)
    links.extend(derive_semantic_links(case_id, context_id, evidence, entities, observations))
    findings, triage, analysis_id = [], [], None
    run = connection.execute("SELECT r.id,r.input_snapshot_json,o.findings_json,o.triage_json "
        "FROM analysis_runs r JOIN analysis_outputs o ON o.run_id=r.id AND o.case_id=r.case_id "
        "WHERE r.case_id=? AND r.status='completed' ORDER BY evora_utc_order(r.created_at) DESC,r.id DESC LIMIT 1",
        (case_id,)).fetchone()
    if run:
        snapshot = json.loads(run['input_snapshot_json'])
        if (set(snapshot['observation_ids']) == observation_map.keys() and
                set(snapshot['evidence_ids']) == {item['id'] for item in evidence} and
                set(snapshot['processing_run_ids']) == set(run_ids)):
            analysis_id = run['id']
            findings = [item for item in json.loads(run['findings_json'])
                        if set(item['observation_ids']) <= observation_map.keys()]
            triage = json.loads(run['triage_json'])
    # Message/transcript observations may not have persisted Event records yet.
    # Include their source timestamps without fabricating an occurrence time.
    represented = {oid for event in events for oid in event['observation_ids']}
    for item in observations:
        if item['id'] not in represented:
            events.append(dict(id=str(uuid5(UUID(case_id), 'qa-timeline:' + item['id'])),
                kind=item['kind'], summary=item['normalized_value'],
                evidence_ids=[item['evidence_id']], observation_ids=[item['id']],
                **({'observed_at_utc': item['observed_at_utc']} if item.get('observed_at_utc') else {})))
    dated = sorted((item for item in events if item.get('observed_at_utc')),
                   key=lambda item: (_utc_order(item['observed_at_utc']), item['id']))
    undated = sorted((item for item in events if not item.get('observed_at_utc')), key=lambda item: item['id'])
    records = defaultdict(list)
    for item in observations:
        records[source_group(item)].append(dict(observation_id=item['id'], kind=item['kind'],
            value=item['normalized_value'], timestamp=item.get('observed_at_utc'),
            source_locator=item['source_locator']))
    return dict(case_id=case_id, source_records=[dict(evidence_id=key[0], source_record=key[2], fields=value)
        for key, value in sorted(records.items())], evidence=evidence, entities=entities,
        entity_counts=dict(Counter(item['kind'] for item in entities)),
        evidence_counts=dict(Counter(item['kind'] for item in evidence)),
        location_count=sum(node.kind == 'location' for node in nodes),
        locations=[node.to_wire() for node in nodes if node.kind == 'location'],
        observations=observations, timeline=dated, undated_events=undated,
        relationships=[link.to_wire() for link in links], findings=findings, triage=triage,
        analysis_run_id=analysis_id, processing_run_ids=sorted(run_ids),
        limitations=['Visual candidates do not identify individuals or vehicle owners.',
                    'Entity counts are candidate records, not unique real-world identities.',
                    'Relative media offsets are not absolute timestamps.',
                    'Missing recipients cannot establish communication or transfer destinations.'] +
                    ([] if analysis_id else ['No completed analysis matches this current evidence snapshot.']))


router = APIRouter()


@router.post("/api/v1/cases/{caseId}/questions", operation_id="askCaseQuestion")
def ask_case_question(
    caseId: UUID, body: CaseQuestion, request: Request, response: Response,
    grant: Annotated[CaseAccessGrant, Depends(require_case_access)],
):
    if request.query_params:
        raise invalid_input()
    case_id = str(grant.case_id)
    parameters = dict(case_id=case_id, evidence_id=None, run_id=None)
    with request.app.state.database.connect() as connection:
        connection.execute("BEGIN")
        connection.create_function("evora_utc_order", 1, _utc_order, deterministic=True)
        connection.create_function("evora_observation_valid", 4, _valid_record, deterministic=True)
        total = _validated_count(connection, parameters)
        observations = _page(connection, parameters, total, 0)
        try:
            context = build_case_context(connection, case_id, observations)
        except (ValueError, TypeError, KeyError):
            raise AccessError(404, 'NOT_FOUND', 'Resource not found.') from None
    model = request.app.state.qa_model
    provider = request.app.state.qa_provider
    citations, model_version = [], MODEL_VERSION
    verification = dict(status='unsupported_question')
    asked_ids = re.findall(r"\b(?:D-\d+|(?:\d{1,3}\.){3}\d{1,3})\b", body.question, re.I)
    source_text = ' '.join(item['normalized_value'] for item in observations)
    unknown_id = any(not re.search(r'(?<![\w.])' + re.escape(value) + r'(?![\w.])',
                                  source_text, re.I) for value in asked_ids)
    if observations and not unknown_id and not _IDENTITY_OR_GUILT.search(body.question):
        if model:
            model_version = provider + ':' + model
            try:
                citations, actual, verification = synthesize(body.question, context, model,
                    qa_url=request.app.state.qa_url, qa_provider=provider,
                    openai_api_key=request.app.state.openai_api_key,
                    openai_base_url=request.app.state.openai_base_url,
                    **({'chatgpt_connection':request.app.state.chatgpt_connection} if provider=='chatgpt' else {}))
                model_version = provider + ':' + actual
            except (SynthesisError, httpx.HTTPError, ValueError, KeyError, TypeError):
                citations = []
                verification = dict(status='generation_unavailable_or_unverified')
        else:
            # Explicit extractive mode is useful offline and is labelled in provenance.
            matches = _matching_observations(body.question, observations)
            citations = [dict(
                claim=f"{item['kind']} records {json.dumps(item['normalized_value'], ensure_ascii=False)}.",
                evidence_id=item['evidence_id'], observation_id=item['id'],
                source_locator=item['source_locator']) for item in matches]
            verification = dict(status='extractive_mode')
    supported = bool(citations)
    claims_text = " ".join(dict.fromkeys(citation['claim'] for citation in citations))
    answer = claims_text if model else 'Evidence in this case confirms these recorded observations: ' + claims_text
    if not supported:
        answer = _INSUFFICIENT
        if verification['status'] == 'generation_unavailable_or_unverified':
            answer = 'A verified analytical answer is unavailable. ' + _INSUFFICIENT
    created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    # No SQLite write lock is held across inference. Check access again afterwards.
    if not request.app.state.case_access.allows(grant.actor.id, grant.case_id):
        raise AccessError(404, 'NOT_FOUND', 'Resource not found.')
    with request.app.state.database.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        initialize_qa_provenance(connection)
        provenance_id = record_qa_provenance(connection, case_id=case_id, actor_id=grant.actor.id,
            retrieval_version=RETRIEVAL_VERSION, question=body.question, answer=answer,
            citations=citations, supported=supported, created_at=created_at,
            model_version=model_version, context=context, verification=verification)
        record_audit_event(connection, action='askCaseQuestion', target_id=str(caseId),
            actor_id=grant.actor.id, case_id=case_id,
            reason=f"Grounded inquiry ({'supported' if supported else 'unsupported'})", created_at=created_at)
    response.headers['Cache-Control'] = 'no-store'
    return dict(case_id=case_id, question=body.question, supported=supported,
        answer=answer, citations=citations, retrieval_version=RETRIEVAL_VERSION,
        provenance_id=provenance_id, model_version=model_version,
        prompt_template_version=PROMPT_TEMPLATE_VERSION)
