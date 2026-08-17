from app.agent.graph import build_response_graph
from app.schemas.request import ResponseRequest
from app.schemas.agent import AgentState


def test_compiled_graph_returns_agentstate_model():
    graph = build_response_graph()
    assert graph is not None
    assert hasattr(graph, "invoke")

    req = ResponseRequest(session_id="integration-1", message="Show fees")
    inputs = {"session_id": req.session_id, "query": req.message}

    out = graph.invoke(inputs)

    # Normalize to a mapping
    state_mapping = out if isinstance(out, dict) else (out.model_dump() if hasattr(out, "model_dump") else out)

    # Attempt to validate/construct AgentState from the returned mapping
    # This ensures the compiled graph produced a final state that matches the
    # `AgentState` contract (default lists, nested models, etc.).
    validated = AgentState.model_validate(state_mapping) if hasattr(AgentState, "model_validate") else AgentState(**state_mapping)

    assert validated.session_id == "integration-1"
    assert validated.query == "Show fees"

    # Defaults preserved
    assert isinstance(validated.selected_tools, list)
    assert isinstance(validated.tool_results, list)
    assert isinstance(validated.retrieved_documents, list)
    assert isinstance(validated.metadata, dict)
