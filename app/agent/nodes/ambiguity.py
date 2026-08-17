from app.schemas.agent import AgentState


def ambiguity_node(state: AgentState) -> AgentState:
    """Deterministic placeholder for ambiguity checking.

    Phase 5A must NOT generate clarification text or modify the shape of
    the `AmbiguityCheck` contract in a non-deterministic way. Mark the
    metadata to show work is pending.
    """
    state.metadata = dict(state.metadata or {})
    state.metadata["ambiguity_status"] = "not_implemented"
    # Preserve existing ambiguity structure; do not fabricate missing fields.
    return state
