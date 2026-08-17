from app.schemas.agent import AgentState
from app.agent.result_checker import evaluate_result_check, ResultCheckResult


def result_check_node(state: AgentState) -> AgentState:
    """Phase 5E result-check node: inspects execution outputs and populates
    `state.result_check` with a deterministic `ResultCheckResult`.

    This node must not call any LLMs or external services; it is purely
    deterministic analysis of prior tool and retrieval outputs.
    """
    state.metadata = dict(state.metadata or {})

    rc = evaluate_result_check(state)
    state.result_check = rc

    # Mirror high-level flags into metadata for backward compatibility
    state.metadata["result_check_status"] = "ok"
    state.metadata["result_check_is_sufficient"] = rc.is_sufficient
    state.metadata["result_check_confidence"] = float(rc.confidence_score)

    return state


__all__ = ["result_check_node"]
