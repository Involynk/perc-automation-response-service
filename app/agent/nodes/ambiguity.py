from app.schemas.agent import AgentState


def ambiguity_node(state: AgentState) -> AgentState:
    """Phase 5 ambiguity checking node.

    Evaluates state ambiguity and populates clarification requirements and
    targeted clarification questions when missing information is detected.
    """
    state.metadata = dict(state.metadata or {})
    if state.ambiguity and state.ambiguity.is_ambiguous:
        state.ambiguity.clarification_required = True
        if not state.ambiguity.clarification_question:
            missing = state.ambiguity.missing_information or []
            if "program" in missing or "course" in missing:
                state.ambiguity.clarification_question = (
                    "Could you please specify which course or program you are inquiring about?"
                )
            elif "target_class" in missing or "grade" in missing:
                state.ambiguity.clarification_question = (
                    "Which grade or class is the student currently in?"
                )
            else:
                state.ambiguity.clarification_question = (
                    "Could you please provide a few more details so we can best assist you?"
                )
    state.metadata["ambiguity_status"] = "not_implemented"
    return state
