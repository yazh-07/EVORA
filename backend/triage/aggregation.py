"""A04 result construction and complete-snapshot ordering over the G02 policy.

Callers authorize the case and supply coherent frozen producer inputs. This
module neither verifies observation counts against storage nor publishes runs.
"""
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from backend.graph_nodes import _uuid
from backend.triage.policy import FactorValue, POLICY_VERSION, score_evidence, triage_sort_key


def _created_at(value: str | None) -> str:
    if value is None:
        instant = datetime.now(timezone.utc)
    else:
        if not isinstance(value, str) or "T" not in value:
            raise ValueError("created_at must be an ISO 8601 timestamp with timezone")
        try:
            instant = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("created_at must be an ISO 8601 timestamp with timezone") from None
        if instant.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _factor_values(factors) -> dict[str, FactorValue | None]:
    # FactorValue intentionally has no name: a named mapping is necessary for
    # that handoff. Never infer a factor name from its weight or list position.
    if isinstance(factors, Mapping):
        values = dict(factors)
        if any(factor is not None and not isinstance(factor, FactorValue)
               for factor in values.values()):
            raise ValueError("Named factors must be FactorValue or None")
        return values
    values = {}
    for factor in factors:
        if not isinstance(factor, Mapping):
            raise ValueError("Use named producer dictionaries or a name-to-FactorValue mapping")
        required = {"name", "value", "explanation", "evidence_ids"}
        if not required <= factor.keys() or factor.keys() - required - {"weight", "contribution"}:
            raise ValueError("Expected a named producer factor with value, explanation and sources")
        name = factor["name"]
        if not isinstance(name, str) or name in values:
            raise ValueError("Factor names must be unique strings")
        # Standalone producer weights/contributions are intentionally recomputed.
        values[name] = FactorValue(factor["value"], factor["explanation"],
                                   tuple(factor["evidence_ids"]))
    return values


def aggregate_triage_result(
    *, case_id: str, analysis_run_id: str, evidence_id: str,
    observation_count: int,
    factors: Iterable[dict | FactorValue] | Mapping[str, FactorValue | None],
    case_evidence_ids: Iterable[str], created_at: str | None = None,
) -> dict | None:
    """Build a strict TriageResult, or None for an unscored item.

    Accept A03/A03B dictionaries or explicit name-to-FactorValue mappings.
    Missing factors are omitted (or None in a mapping); evaluated zero remains
    available. G02 validates values/sources even on unscored paths. IDs are
    canonical lowercase UUIDs. The deterministic result UUID identifies one
    case/run/evidence/policy slot; A05 must enforce immutable run inputs/time.
    Policy version belongs in AnalysisRun.algorithm_version, never a new field.
    """
    case_id = _uuid(case_id, "case_id")
    analysis_run_id = _uuid(analysis_run_id, "analysis_run_id")
    evidence_id = _uuid(evidence_id, "evidence_id")
    allowed = tuple(_uuid(eid, "case_evidence_ids") for eid in case_evidence_ids)
    values = _factor_values(factors)
    for factor in values.values():
        if factor is not None:
            for eid in factor.evidence_ids:
                _uuid(eid, "factor.evidence_ids")
    timestamp = _created_at(created_at)
    scored = score_evidence(evidence_id=evidence_id, observation_count=observation_count,
                            factors=values, case_evidence_ids=allowed)
    if scored is None:
        return None
    names = ", ".join(factor["name"] for factor in scored.factors)
    return {
        "id": str(uuid5(NAMESPACE_URL, f"evora:{POLICY_VERSION}:{case_id}:{analysis_run_id}:{evidence_id}")),
        "case_id": case_id, "evidence_id": evidence_id, "analysis_run_id": analysis_run_id,
        "score": float(scored.score), "priority": scored.priority,
        "factors": list(scored.factors),
        "explanation": f"{scored.explanation} Available factors: {names}.",
        "created_at": timestamp,
    }


def sort_triage_results(results: list[dict], all_case_evidence_ids: Iterable[str]) -> list[dict]:
    """Return TriageEntry dictionaries for the complete frozen membership.

    Inputs are computed TriageResults from one case/run. Entries without a
    result contain only evidence_id. Sort before A06 pagination; priority and
    live overrides never affect this order. Duplicate/foreign/mixed-run results
    fail closed. Returned entries do not alias input result dictionaries.
    """
    membership = {_uuid(eid, "all_case_evidence_ids") for eid in all_case_evidence_ids}
    by_evidence, contexts = {}, set()
    for result in results:
        eid = _uuid(result["evidence_id"], "evidence_id")
        if eid not in membership or eid in by_evidence:
            raise ValueError("Results must uniquely belong to the frozen evidence membership")
        contexts.add((_uuid(result["case_id"], "case_id"),
                      _uuid(result["analysis_run_id"], "analysis_run_id")))
        if len(contexts) > 1:
            raise ValueError("Results must belong to one case and analysis run")
        if result["score"] is None:
            raise ValueError("Unscored evidence must omit its TriageResult")
        triage_sort_key(eid, result["score"])
        by_evidence[eid] = result
    ordered = sorted(membership, key=lambda eid: triage_sort_key(
        eid, by_evidence[eid]["score"] if eid in by_evidence else None))
    return [dict(evidence_id=eid, latest_result=deepcopy(by_evidence[eid]))
            if eid in by_evidence else dict(evidence_id=eid) for eid in ordered]
