from app.schemas.agent import AgentState
from app.agent.executor import get_execution_engine


def execution_node(state: AgentState) -> AgentState:
    """Phase 5D execution node: runs structured tools or RAG based on routing decision.

    This node is deterministic given the same `ExecutionEngine` and services.
    It avoids creating DB sessions directly; tests should inject a fake engine
    via `app.agent.executor.set_global_execution_engine()` when needed.
    """
    state.metadata = dict(state.metadata or {})

    engine = get_execution_engine()
    updated = engine.execute(state)
    return updated


__all__ = ["execution_node"]
