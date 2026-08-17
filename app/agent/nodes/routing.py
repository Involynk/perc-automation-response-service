from app.schemas.agent import AgentState
from app.agent.router import decide_routing, RoutingDecision


def routing_node(state: AgentState) -> AgentState:
    """Phase 5C routing node: deterministically decide the execution route.

    This node MUST NOT execute any tools, RAG, or LLMs. It only records a
    `routing_decision` into the `AgentState` for downstream phases.
    """
    state.metadata = dict(state.metadata or {})

    # Use router to decide
    rd: RoutingDecision = decide_routing(
        intent=state.intent,
        secondary_intents=state.secondary_intents,
        ambiguity=state.ambiguity,
        entities=state.entities.model_dump() if hasattr(state.entities, "model_dump") else dict(state.entities),
        query=state.query,
    )

    # Attach routing decision as serializable dict
    state.metadata["routing_status"] = "ok"
    state.metadata["routing_decision"] = rd.model_dump() if hasattr(rd, "model_dump") else (dict(rd) if isinstance(rd, dict) else rd)
    return state
