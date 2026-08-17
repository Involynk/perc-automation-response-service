from app.agent.nodes.initialize import initialize_node
from app.agent.nodes.understand import understand_node
from app.agent.nodes.ambiguity import ambiguity_node
from app.agent.nodes.routing import routing_node
from app.schemas.request import ResponseRequest


def test_initialize_creates_state():
    req = ResponseRequest(session_id="student-001", message="What courses are available?")
    state = initialize_node(req)
    assert state.session_id == "student-001"
    assert state.query == "What courses are available?"
    assert state.metadata.get("initialized_by") == "initialize_node"


def test_understand_sets_intent_and_status():
    req = ResponseRequest(session_id="s2", message="Hello")
    state = initialize_node(req)
    state2 = understand_node(state)
    assert state2.intent is not None
    assert state2.metadata.get("understanding_status") == "ok"


def test_ambiguity_placeholder_preserves_structure():
    req = ResponseRequest(session_id="s3", message="Hi")
    state = initialize_node(req)
    state2 = ambiguity_node(state)
    assert hasattr(state2, "ambiguity")
    assert state2.metadata.get("ambiguity_status") == "not_implemented"


def test_routing_placeholder_does_not_execute_tools():
    req = ResponseRequest(session_id="s4", message="Ping")
    state = initialize_node(req)
    state2 = routing_node(state)
    assert state2.selected_tools == []
    assert state2.metadata.get("routing_status") == "ok"
    assert "routing_decision" in state2.metadata
