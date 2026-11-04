"""A16/U10 deterministic retrieval of case observations with exact citations."""

from datetime import datetime, timezone
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.audit import record_audit_event
from backend.auth import CaseAccessGrant, require_case_access
from backend.evidence import invalid_input
from backend.observations import _page, _utc_order, _valid_record, _validated_count


RETRIEVAL_VERSION = "deterministic-grounded-retrieval/1"
_INSUFFICIENT = (
    "Insufficient evidence in this case to support the inquiry; "
    "candidate observations do not establish identity or guilt."
)
_TOKENS = re.compile(r"[^\W_]+(?:[.-][^\W_]+)*", re.UNICODE)
_IDENTITY_OR_GUILT = re.compile(
    r"\b(?:guilt\w*|innocen\w*|identity|identities|identify|identified|identification|"
    r"perpetrator\w*|culprit\w*|who|whose|whom|killer\w*|murderer\w*|"
    r"responsible|committed|criminal\w*|attacker\w*|offender\w*|suspect\w*|"
    r"owner\w*|owns?|belongs?|person|real\s+name|used\s+by)\b", re.IGNORECASE,
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
    # Explicit identifiers take precedence: an unknown device must not match
    # just because a generic word like "connected" appears elsewhere.
    identifiers = {token for token in keywords if any(char.isdigit() for char in token)}
    terms = identifiers or keywords
    matches = []
    for observation in observations:
        values = _tokens(" ".join(observation[key] for key in
                                 ("kind", "raw_value", "normalized_value")))
        # Kind components allow "GPS" / "message" queries. Dotted numeric
        # prefixes allow the documented network query "203.0.113".
        values.update(observation["kind"].casefold().split("."))
        if any(term in values or (re.fullmatch(r"\d+(?:\.\d+)+", term) and
               any(value.startswith(term + ".") for value in values)) for term in terms):
            matches.append(observation)
    return matches


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
        # Retrieval and its audit entry share a snapshot and commit together.
        connection.execute("BEGIN IMMEDIATE")
        connection.create_function("evora_utc_order", 1, _utc_order, deterministic=True)
        connection.create_function("evora_observation_valid", 4, _valid_record, deterministic=True)
        total = _validated_count(connection, parameters)
        observations = _page(connection, parameters, total, 0)
        matches = _matching_observations(body.question, observations)
        citations = [dict(
            claim=f"{item['kind']} records {json.dumps(item['normalized_value'], ensure_ascii=False)}.",
            evidence_id=item["evidence_id"], observation_id=item["id"],
            source_locator=item["source_locator"],
        ) for item in matches]
        supported = bool(citations)
        answer = ("Evidence in this case confirms these recorded observations: " +
                  " ".join(citation["claim"] for citation in citations)) if supported else _INSUFFICIENT
        record_audit_event(
            connection, action="askCaseQuestion", target_id=str(caseId),
            actor_id=grant.actor.id, case_id=case_id,
            reason=f"Grounded inquiry ({'supported' if supported else 'unsupported'})",
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    response.headers["Cache-Control"] = "no-store"
    return dict(case_id=case_id, question=body.question, supported=supported,
                answer=answer, citations=citations, retrieval_version=RETRIEVAL_VERSION)
