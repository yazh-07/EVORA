"""F00 request identity/case guards; no case persistence or public routes.

The synthetic verifier is an explicitly configured local-development adapter,
not a production issuer/provider. F01 supplies the real membership producer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Request

from backend.errors import AccessError


@dataclass(frozen=True)
class Actor:
    id: str
    role: str = "investigator"


@dataclass(frozen=True)
class CaseAccessGrant:
    actor: Actor
    case_id: UUID


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Actor | None:
        """Return a current identity, or None for any invalid identity."""
        ...


class CaseAccess(Protocol):
    def allows(self, actor_id: str, case_id: UUID) -> bool:
        """True only for an existing case with this actor's membership.

        Query authoritative membership on each request; do not cache grants or
        disclose whether a denied case exists. Storage failures must propagate,
        never become a grant or a fictional not-found result.
        """
        ...


class RejectTokens:
    def verify(self, token: str) -> Actor | None:
        return None


class DenyCaseAccess:
    def allows(self, actor_id: str, case_id: UUID) -> bool:
        return False


_TOKEN = r"[A-Za-z0-9\-._~+/]+=*"
_BEARER = re.compile(r"(?i:Bearer) +(" + _TOKEN + r")", flags=re.ASCII)
_SYNTHETIC_ACTORS = frozenset({"investigator-1", "investigator-2"})


class SyntheticTokenVerifier:
    """Opt-in C-03 synthetic identities with caller-provided opaque tokens.

    Only SHA-256 token digests are retained; no default token, issuance route,
    automatic expiry or production identity claim. Reconfigure/replace the
    verifier to revoke/change these development credentials. The input mapping
    is copied and must stay private, outside Git/logs/browser persistence.
    """

    def __init__(self, tokens: Mapping[str, str]):
        if any(
            not isinstance(token, str) or not re.fullmatch(_TOKEN, token, re.ASCII)
            or actor_id not in _SYNTHETIC_ACTORS
            for token, actor_id in tokens.items()
        ):
            raise ValueError("Invalid synthetic authentication configuration.")
        self._actors_by_digest = {
            hashlib.sha256(token.encode("ascii")).digest(): Actor(actor_id)
            for token, actor_id in tokens.items()
        }

    def verify(self, token: str) -> Actor | None:
        # Parser supplies ASCII credentials; reject invalid direct callers too.
        if not re.fullmatch(_TOKEN, token, re.ASCII):
            return None
        return self._actors_by_digest.get(hashlib.sha256(token.encode("ascii")).digest())


def authenticated_actor(request: Request) -> Actor:
    """Accept one well-formed Authorization bearer header, never query/cookies."""
    if getattr(request.app.state, 'local_auth', False):
        from backend.local_auth import session_actor
        actor = session_actor(request)
        if actor is None:
            raise AccessError(401, 'UNAUTHORIZED', 'Sign in to your local account.')
        request.state.actor_id = actor.id
        return actor
    values = request.headers.getlist("authorization")
    match = _BEARER.fullmatch(values[0]) if len(values) == 1 else None
    actor = request.app.state.token_verifier.verify(match[1]) if match else None
    if actor is None:
        raise AccessError(401, "UNAUTHORIZED", "Authentication required.")
    return actor


def require_case_access(
    caseId: UUID,
    request: Request,
    actor: Annotated[Actor, Depends(authenticated_actor)],
) -> CaseAccessGrant:
    """Authorize before a route handler runs, using the contract's caseId path."""
    if not request.app.state.case_access.allows(actor.id, caseId):
        raise AccessError(404, "NOT_FOUND", "Resource not found.")
    return CaseAccessGrant(actor=actor, case_id=caseId)
