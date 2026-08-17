from app.schemas.agent import AgentState
from app.agent.generator import AnswerGenerator
from app.core.config import settings


def generation_node(state: AgentState) -> AgentState:
    """Phase 5F generation node: calls LLM to produce a draft answer JSON and
    attaches it to `state.draft_answer` (string) and leaves `state.final_answer`
    untouched.

    This node will construct an `AnswerGenerator` using the configured LLM
    provider if no client is injected. For tests, inject a stub client.
    """
    state.metadata = dict(state.metadata or {})

    # If result_check indicates insufficiency or requires clarification/handoff,
    # do not call LLM; set empty draft and record reason.
    rc = getattr(state, "result_check", None)
    if rc is None:
        state.metadata["generation_status"] = "no_result_check"
        state.draft_answer = None
        return state

    # result_check may be a pydantic model or a plain dict depending on graph wiring
    if isinstance(rc, dict):
        requires_clarification = rc.get("requires_clarification", False)
        requires_human_handoff = rc.get("requires_human_handoff", False)
        is_sufficient = rc.get("is_sufficient", False)
    else:
        requires_clarification = getattr(rc, "requires_clarification", False)
        requires_human_handoff = getattr(rc, "requires_human_handoff", False)
        is_sufficient = getattr(rc, "is_sufficient", False)

    if requires_clarification or requires_human_handoff or not is_sufficient:
        state.metadata["generation_status"] = "skipped_insufficient_evidence"
        state.draft_answer = None
        return state

    # Construct generator (may raise if no client configured)
    gen = AnswerGenerator()
    try:
        draft = gen.generate(state)
    except Exception as exc:
        state.metadata["generation_status"] = "generation_failed"
        state.metadata["generation_error"] = str(exc)
        state.draft_answer = None
        return state

    # Attach drafted answer text and metadata
    state.draft_answer = draft.draft_answer
    state.metadata["generation_status"] = "ok"
    state.metadata["generation_used_structured"] = draft.used_structured
    state.metadata["generation_used_rag"] = draft.used_rag
    state.metadata["generation_confidence"] = float(draft.confidence)
    state.metadata["generation_evidence_count"] = len(draft.evidence or [])
    return state


__all__ = ["generation_node"]
