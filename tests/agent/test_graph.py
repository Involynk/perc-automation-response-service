from app.agent import build_response_graph
from app.schemas.request import ResponseRequest


def test_graph_compiles_and_executes():
    graph = build_response_graph()
    assert graph is not None
    # The returned object should be a compiled LangGraph graph exposing `invoke`.
    assert hasattr(graph, "invoke")

    req = ResponseRequest(session_id="session-xyz", message="What is the fee?")
    # compiled.invoke expects a mapping matching the graph's state schema.
    # Provide the required `session_id` and `query` fields.
    inputs = {"session_id": req.session_id, "query": req.message}
    out = graph.invoke(inputs)

    # compiled graphs typically return a dict-like state; support both dict and pydantic model
    state = out if isinstance(out, dict) else (out.model_dump() if hasattr(out, "model_dump") else out)

    # session and query preserved
    assert state.get("session_id") == "session-xyz"
    assert state.get("query") == "What is the fee?"

    # placeholders recorded; understanding and routing implemented in Phase 5B/5C
    metadata = state.get("metadata") or {}
    assert metadata.get("understanding_status") == "ok"
    assert metadata.get("ambiguity_status") == "not_implemented"
    assert metadata.get("routing_status") == "ok"
    # routing decision attached
    assert "routing_decision" in metadata

    # graph should not pick tools or retrieved documents in Phase 5A
    assert state.get("selected_tools") == []
    assert state.get("retrieved_documents") == []
