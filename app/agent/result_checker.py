from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.agent import ToolResult, RetrievedDocument, QueryIntent


class ResultCheckResult(BaseModel):
    is_sufficient: bool = Field(default=False)
    has_successful_results: bool = Field(default=False)
    has_failed_results: bool = Field(default=False)
    has_empty_results: bool = Field(default=False)
    has_conflicts: bool = Field(default=False)
    requires_clarification: bool = Field(default=False)
    requires_human_handoff: bool = Field(default=False)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0)
    authoritative_sources: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    per_intent_evidence: Optional[List[Dict[str, Any]]] = None


_STRUCTURED_TOOL_NAMES = {
    "get_course_info",
    "get_fee",
    "get_branch_info",
    "get_eligibility",
    "get_admission_steps",
    "get_admission_status",
    "get_availability",
}


def evaluate_result_check(state: Any, min_rag_relevance: float = 0.70) -> ResultCheckResult:
    """Deterministic evaluation of AgentState evidence and conflicts.

    Returns a `ResultCheckResult` summarizing evidence sufficiency and issues.
    """
    rc = ResultCheckResult()

    rd_raw = state.metadata.get("routing_decision")
    route = None
    if rd_raw:
        route = rd_raw.get("route") if isinstance(rd_raw, dict) else getattr(rd_raw, "route", None)

    # Special handling for clarification/handoff/safe stop
    if route == "CLARIFICATION":
        rc.requires_clarification = True
        rc.is_sufficient = False
        rc.metadata["reason"] = "routing_clarification"
        return rc

    if route == "HUMAN_HANDOFF":
        rc.requires_human_handoff = True
        rc.is_sufficient = False
        rc.metadata["reason"] = "routing_human_handoff"
        return rc

    if route == "SAFE_STOP":
        rc.is_sufficient = False
        rc.metadata["reason"] = "routing_safe_stop"
        return rc

    # Tally structured tool results
    structured_success = 0
    structured_failed = 0
    structured_empty = 0

    for tr in getattr(state, "tool_results", []) or []:
        name = tr.tool_name
        source = tr.metadata.get("source") if tr.metadata else None
        is_structured = (name in _STRUCTURED_TOOL_NAMES) or (source == "structured_database")
        if is_structured:
            if tr.success:
                structured_success += 1
                # check data emptiness
                if tr.data is None or (isinstance(tr.data, (list, dict)) and len(tr.data) == 0):
                    structured_empty += 1
            else:
                structured_failed += 1

    # RAG evidence
    rag_count = 0
    rag_below_threshold = 0
    for doc in getattr(state, "retrieved_documents", []) or []:
        rag_count += 1
        if getattr(doc, "relevance_score", None) is not None:
            if doc.relevance_score < min_rag_relevance:
                rag_below_threshold += 1

    rc.has_successful_results = (structured_success + rag_count) > 0
    rc.has_failed_results = structured_failed > 0
    # Empty results: no structured successes and no RAG, or all structured successes were empty
    if structured_success == 0 and rag_count == 0:
        rc.has_empty_results = True
    elif structured_empty > 0 and structured_empty == structured_success:
        rc.has_empty_results = True
    else:
        rc.has_empty_results = False
    rc.evidence_count = structured_success + rag_count

    # Authoritative sources
    sources = set()
    if structured_success > 0:
        sources.add("STRUCTURED")
    if rag_count > 0:
        sources.add("RAG")
    if not sources:
        sources.add("NONE")
    rc.authoritative_sources = list(sources)

    # Conflict detection: conservative checks
    conflicts = []
    if structured_success > 0 and rag_count > 0:
        # For each structured ToolResult, compare top-level scalar fields against retrieved_documents' metadata
        for tr in getattr(state, "tool_results", []) or []:
            if not tr.success:
                continue
            if tr.tool_name not in _STRUCTURED_TOOL_NAMES:
                continue
            data = tr.data
            if isinstance(data, dict):
                for k, v in data.items():
                    # only compare simple scalar values
                    if isinstance(v, (str, int, float, bool)):
                        for doc in getattr(state, "retrieved_documents", []) or []:
                            if doc.metadata and k in doc.metadata:
                                if doc.metadata.get(k) != v:
                                    conflicts.append(f"Conflict on {k}: structured='{v}' vs rag='{doc.metadata.get(k)}'")
    rc.has_conflicts = len(conflicts) > 0
    rc.issues.extend(conflicts)

    # Confidence scoring: deterministic and explainable
    score = 0.0
    # structured success is high authority
    if structured_success > 0:
        score += 0.7
    # rag contributes moderately
    if rag_count > 0:
        score += 0.4
    # subtract for failures
    score -= min(0.5, 0.2 * structured_failed)
    # subtract for conflicts
    if rc.has_conflicts:
        score -= 0.3
    # penalize if evidence empty or below threshold
    if rc.has_empty_results:
        score -= 0.4

    # clamp
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0

    rc.confidence_score = round(score, 3)

    # Determine sufficiency: simple thresholds
    rc.is_sufficient = rc.confidence_score >= 0.6 and not rc.has_conflicts

    # Per-intent evidence: if MULTI_INTENT, look for sub_routes
    per_intent = []
    rd = state.metadata.get("routing_decision")
    if rd and isinstance(rd, dict) and rd.get("route") == "MULTI_INTENT":
        subs = rd.get("sub_routes") or []
        for sub in subs:
            # For each sub-route, determine if it had evidence
            r = {"route": sub.get("route"), "tool_name": sub.get("tool_name"), "has_evidence": False}
            if sub.get("route") == "RAG":
                r["has_evidence"] = rag_count > 0
            elif sub.get("route") == "STRUCTURED_TOOL":
                r["has_evidence"] = structured_success > 0
            per_intent.append(r)
    if per_intent:
        rc.per_intent_evidence = per_intent

    # Additional metadata
    rc.metadata["structured_success_count"] = structured_success
    rc.metadata["structured_failed_count"] = structured_failed
    rc.metadata["rag_count"] = rag_count

    return rc


__all__ = ["ResultCheckResult", "evaluate_result_check"]
