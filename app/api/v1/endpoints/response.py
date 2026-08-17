import json
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_response_graph
from app.schemas.agent import QueryIntent
from app.schemas.request import ResponseRequest
from app.schemas.response import ResponseResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_answer_text(draft: Any) -> str:
    """Extract readable text from draft answer payload."""
    if not draft:
        return ""
    if isinstance(draft, str):
        try:
            parsed = json.loads(draft)
            if isinstance(parsed, dict) and "draft_answer" in parsed:
                return str(parsed["draft_answer"])
        except Exception:
            pass
        return draft
    if isinstance(draft, dict):
        return str(draft.get("draft_answer") or draft)
    if hasattr(draft, "draft_answer"):
        return str(draft.draft_answer)
    return str(draft)


@router.post("/response", response_model=ResponseResponse)
def generate_response(
    request: ResponseRequest,
    graph: Any = Depends(get_response_graph),
) -> ResponseResponse:
    """Execute LangGraph response pipeline and map final state to ResponseResponse."""
    graph_input = {
        "session_id": request.session_id,
        "query": request.message,
        "metadata": request.metadata or {},
    }

    try:
        raw_result = graph.invoke(graph_input)
    except Exception as exc:
        logger.error(f"Graph execution failed for session {request.session_id}: {exc}", exc_info=True)
        return ResponseResponse(
            session_id=request.session_id,
            answer="An error occurred while processing your request. Please try again later.",
            status="error",
            sources=[],
            clarification_required=False,
        )

    # Extract session_id
    session_id = (
        raw_result.get("session_id")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "session_id", request.session_id)
    ) or request.session_id

    # Extract intent
    intent_raw = (
        raw_result.get("intent")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "intent", None)
    )
    intent: Optional[QueryIntent] = None
    if intent_raw:
        if isinstance(intent_raw, QueryIntent):
            intent = intent_raw
        elif isinstance(intent_raw, str):
            try:
                intent = QueryIntent(intent_raw)
            except (ValueError, KeyError):
                try:
                    intent = QueryIntent[intent_raw]
                except (ValueError, KeyError):
                    intent = None

    # Extract and deduplicate sources
    sources: List[str] = []
    retrieved_docs = (
        raw_result.get("retrieved_documents")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "retrieved_documents", [])
    ) or []
    for doc in retrieved_docs:
        src = (
            doc.get("source_file")
            if isinstance(doc, dict)
            else getattr(doc, "source_file", None)
        )
        if src and src not in sources:
            sources.append(src)

    tool_results = (
        raw_result.get("tool_results")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "tool_results", [])
    ) or []
    for tr in tool_results:
        meta = tr.get("metadata") if isinstance(tr, dict) else getattr(tr, "metadata", {})
        src = meta.get("source") if meta else None
        if src and src not in sources:
            sources.append(src)

    # Extract ambiguity / clarification
    ambiguity = (
        raw_result.get("ambiguity")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "ambiguity", None)
    )
    clarification_required = False
    clarification_question: Optional[str] = None

    if ambiguity:
        if isinstance(ambiguity, dict):
            clarification_required = bool(ambiguity.get("clarification_required"))
            clarification_question = ambiguity.get("clarification_question")
        else:
            clarification_required = bool(getattr(ambiguity, "clarification_required", False))
            clarification_question = getattr(ambiguity, "clarification_question", None)

    # Extract result check
    result_check = (
        raw_result.get("result_check")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "result_check", None)
    )
    rc_human_handoff = False
    if result_check:
        if isinstance(result_check, dict):
            if result_check.get("requires_clarification"):
                clarification_required = True
                if not clarification_question:
                    clarification_question = result_check.get("clarification_question")
            if result_check.get("requires_human_handoff"):
                rc_human_handoff = True
        else:
            if getattr(result_check, "requires_clarification", False):
                clarification_required = True
                if not clarification_question:
                    clarification_question = getattr(result_check, "clarification_question", None)
            if getattr(result_check, "requires_human_handoff", False):
                rc_human_handoff = True

    # Extract metadata and routing info
    meta = (
        raw_result.get("metadata")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "metadata", {})
    ) or {}
    routing_dec = meta.get("routing_decision") or {}
    route = routing_dec.get("route") if isinstance(routing_dec, dict) else getattr(routing_dec, "route", None)

    human_escalation = (
        raw_result.get("human_escalation_required")
        if isinstance(raw_result, dict)
        else getattr(raw_result, "human_escalation_required", False)
    )

    is_escalated = bool(
        human_escalation
        or rc_human_handoff
        or route in ("HUMAN_HANDOFF", "SAFE_STOP")
        or intent in (QueryIntent.GRIEVANCE_HUMAN_HANDOFF, QueryIntent.OUT_OF_SCOPE_ESCALATION)
    )

    # Determine status and final answer
    error_flag = meta.get("error")
    gen_status = meta.get("generation_status")

    if clarification_required:
        status = "clarification_required"
        answer = (
            clarification_question
            or "Could you please provide more details so we can best assist you?"
        )
    elif is_escalated:
        status = "escalated"
        draft_raw = (
            raw_result.get("draft_answer")
            if isinstance(raw_result, dict)
            else getattr(raw_result, "draft_answer", None)
        )
        if draft_raw:
            answer = _parse_answer_text(draft_raw)
        else:
            answer = "Your query has been escalated to our counseling team. A representative will get in touch with you shortly."
    elif error_flag or gen_status == "generation_failed":
        status = "error"
        answer = "An error occurred while processing your request. Please try again later."
    else:
        draft_raw = (
            raw_result.get("draft_answer")
            if isinstance(raw_result, dict)
            else getattr(raw_result, "draft_answer", None)
        )
        if draft_raw:
            status = "success"
            answer = _parse_answer_text(draft_raw)
        else:
            status = "escalated"
            answer = "I was unable to find sufficient information to answer your query. Please contact the PERC admissions team for assistance."

    return ResponseResponse(
        session_id=session_id,
        answer=answer,
        status=status,
        intent=intent,
        sources=sources,
        clarification_required=clarification_required,
        clarification_question=clarification_question if clarification_required else None,
    )
