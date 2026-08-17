from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.schemas.agent import QueryIntent, AmbiguityCheck


class RouteType(str, Enum):
    STRUCTURED_TOOL = "STRUCTURED_TOOL"
    RAG = "RAG"
    CLARIFICATION = "CLARIFICATION"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    SAFE_STOP = "SAFE_STOP"
    MULTI_INTENT = "MULTI_INTENT"


class RoutingDecision(BaseModel):
    route: RouteType
    tool_name: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sub_routes: Optional[List["RoutingDecision"]] = None


RoutingDecision.model_rebuild()


_STRUCTURED_TOOL_MAP = {
    QueryIntent.COURSE_DISCOVERY: "get_course_info",
    QueryIntent.COURSE_DETAILS: "get_course_info",
    QueryIntent.FEES_PRICING: "get_fee",
    QueryIntent.ELIGIBILITY: "get_eligibility",
    QueryIntent.BRANCH_LOCATION: "get_branch_info",
    QueryIntent.ADMISSION_PROCESS: "get_admission_steps",
    QueryIntent.AVAILABILITY_STATUS: "get_availability",  # may be refined to get_admission_status
}


def _structured_route_for_intent(intent: QueryIntent, query: str) -> RoutingDecision:
    # Special case: AVAILABILITY_STATUS may map to get_admission_status for live-seat queries
    if intent == QueryIntent.AVAILABILITY_STATUS:
        q = query.lower() if query else ""
        if any(w in q for w in ("open", "available", "right now", "currently", "now")):
            return RoutingDecision(route=RouteType.STRUCTURED_TOOL, tool_name="get_admission_status", reason="live_availability_question", confidence=0.95)
        return RoutingDecision(route=RouteType.STRUCTURED_TOOL, tool_name="get_availability", reason="general_availability", confidence=0.9)

    tool = _STRUCTURED_TOOL_MAP.get(intent)
    if not tool:
        raise ValueError(f"No structured tool mapping for intent {intent}")
    return RoutingDecision(route=RouteType.STRUCTURED_TOOL, tool_name=tool, reason=f"structured_route_for_{intent.name}", confidence=0.95)


def decide_routing(intent: Optional[QueryIntent], secondary_intents: List[QueryIntent], ambiguity: AmbiguityCheck, entities: dict, query: str) -> RoutingDecision:
    """Deterministic routing decision based on intent, ambiguity, and entities.

    Priority order enforced:
      1. Human handoff
      2. Clarification (ambiguity)
      3. Multi-intent decomposition
      4. Structured tool
      5. RAG
      6. Safe stop
    """
    # Human handoff priority
    if intent == QueryIntent.GRIEVANCE_HUMAN_HANDOFF:
        return RoutingDecision(route=RouteType.HUMAN_HANDOFF, reason="grievance_handoff", confidence=1.0)

    # Ambiguity/clarification
    if ambiguity and ambiguity.is_ambiguous:
        return RoutingDecision(route=RouteType.CLARIFICATION, reason="ambiguous_incomplete", confidence=0.1)

    # Unknown or missing intent
    if intent is None:
        return RoutingDecision(route=RouteType.SAFE_STOP, reason="missing_intent", confidence=0.0)

    # Explicit out-of-scope
    if intent == QueryIntent.OUT_OF_SCOPE_ESCALATION:
        return RoutingDecision(route=RouteType.SAFE_STOP, reason="out_of_scope", confidence=0.0)

    # Multi-intent decomposition
    if intent == QueryIntent.MULTI_INTENT:
        sub = []
        for s in secondary_intents:
            # route each secondary intent deterministically
            if s in _STRUCTURED_TOOL_MAP or s == QueryIntent.AVAILABILITY_STATUS:
                sub.append(_structured_route_for_intent(s, query))
            else:
                # default to RAG for these secondary intents
                sub.append(RoutingDecision(route=RouteType.RAG, reason=f"rag_for_{s.name}", confidence=0.8))
        return RoutingDecision(route=RouteType.MULTI_INTENT, sub_routes=sub, reason="multi_intent_decomposition", confidence=0.9)

    # Follow-up contextual
    if intent == QueryIntent.FOLLOW_UP_CONTEXTUAL:
        # If ambiguity indicates missing info, ask for clarification
        if ambiguity and ambiguity.is_ambiguous:
            return RoutingDecision(route=RouteType.CLARIFICATION, reason="followup_missing_context", confidence=0.1)
        # If entities or secondary intents resolve to a known intent, route accordingly
        if secondary_intents:
            # prefer first resolved secondary
            s = secondary_intents[0]
            if s == QueryIntent.MULTI_INTENT:
                return RoutingDecision(route=RouteType.MULTI_INTENT, reason="followup_resolved_to_multi", confidence=0.9)
            if s in _STRUCTURED_TOOL_MAP or s == QueryIntent.AVAILABILITY_STATUS:
                return _structured_route_for_intent(s, query)
            return RoutingDecision(route=RouteType.RAG, reason="followup_resolved_to_rag", confidence=0.8)
        # fallback safe stop
        return RoutingDecision(route=RouteType.CLARIFICATION, reason="followup_unresolved", confidence=0.1)

    # Ambiguity handled earlier; route based on intent mapping
    structured_intents = {
        QueryIntent.COURSE_DISCOVERY,
        QueryIntent.COURSE_DETAILS,
        QueryIntent.FEES_PRICING,
        QueryIntent.ELIGIBILITY,
        QueryIntent.BRANCH_LOCATION,
        QueryIntent.ADMISSION_PROCESS,
        QueryIntent.AVAILABILITY_STATUS,
    }

    rag_intents = {
        QueryIntent.REQUIRED_DOCUMENTS,
        QueryIntent.POLICIES,
        QueryIntent.COMPARISON,
        QueryIntent.HOSTEL_ACCOMMODATION,
        QueryIntent.PLACEMENT_CAREER_OUTCOMES,
        QueryIntent.LANGUAGE_MEDIUM,
    }

    if intent in structured_intents:
        return _structured_route_for_intent(intent, query)

    if intent in rag_intents:
        return RoutingDecision(route=RouteType.RAG, reason=f"rag_for_{intent.name}", confidence=0.85)

    # C14 handled earlier; C15 handled earlier; any remaining intents default to safe stop
    return RoutingDecision(route=RouteType.SAFE_STOP, reason="default_safe_stop", confidence=0.0)


__all__ = ["RouteType", "RoutingDecision", "decide_routing"]
