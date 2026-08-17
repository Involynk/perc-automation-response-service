import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_response_graph
from app.schemas.agent import AgentState, QueryIntent, AmbiguityCheck, ExtractedEntities
from app.schemas.response import ResponseResponse


class FakeGraph:
    def __init__(self, result: dict | AgentState | Exception):
        self.result = result
        self.last_input = None

    def invoke(self, input_data: dict):
        self.last_input = input_data
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Test 1: Health check endpoint returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_successful_response_dict_output(client):
    """Test 2: Successful response mapping when graph returns a dictionary."""
    fake_result = {
        "session_id": "test-session-1",
        "query": "What are the JEE Advanced batches?",
        "intent": "C2_COURSE_DETAILS",
        "draft_answer": '{"draft_answer": "PERC offers 2-Year classroom coaching for JEE Advanced."}',
        "retrieved_documents": [
            {"source_file": "course-details.md"},
            {"source_file": "course-details.md"},  # duplicate
        ],
        "tool_results": [
            {"tool_name": "get_course_info", "metadata": {"source": "structured_database"}},
        ],
        "metadata": {
            "routing_decision": {"route": "STRUCTURED_TOOL"},
            "generation_status": "ok",
        },
    }

    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(fake_result)
    try:
        response = client.post(
            "/api/v1/response",
            json={"session_id": "test-session-1", "message": "What are the JEE Advanced batches?"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-1"
        assert validated.status == "success"
        assert validated.intent == QueryIntent.COURSE_DETAILS
        assert validated.answer == "PERC offers 2-Year classroom coaching for JEE Advanced."
        # Sources should be deduplicated: course-details.md and structured_database
        assert validated.sources == ["course-details.md", "structured_database"]
        assert validated.clarification_required is False
        assert validated.clarification_question is None
    finally:
        app.dependency_overrides.clear()


def test_successful_response_agent_state_output(client):
    """Test 3: Successful response mapping when graph returns an AgentState object."""
    state = AgentState(
        session_id="test-session-2",
        query="What is the fee for Class 11?",
        intent=QueryIntent.FEES_PRICING,
        draft_answer="The fee for Class 11 coaching is provided during the demo counseling session.",
        metadata={"generation_status": "ok"},
    )

    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(state)
    try:
        response = client.post(
            "/response",
            json={"session_id": "test-session-2", "message": "What is the fee for Class 11?"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-2"
        assert validated.status == "success"
        assert validated.intent == QueryIntent.FEES_PRICING
        assert validated.answer == "The fee for Class 11 coaching is provided during the demo counseling session."
    finally:
        app.dependency_overrides.clear()


def test_clarification_response(client):
    """Test 4: Clarification state correctly populates clarification_required and question."""
    fake_result = {
        "session_id": "test-session-3",
        "query": "Tell me about coaching",
        "intent": "C13_AMBIGUOUS_INCOMPLETE",
        "ambiguity": {
            "is_ambiguous": True,
            "clarification_required": True,
            "clarification_question": "Which grade are you in and which exam are you preparing for?",
        },
        "metadata": {
            "routing_decision": {"route": "CLARIFICATION"},
        },
    }

    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(fake_result)
    try:
        response = client.post(
            "/api/v1/response",
            json={"session_id": "test-session-3", "message": "Tell me about coaching"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-3"
        assert validated.status == "clarification_required"
        assert validated.clarification_required is True
        assert validated.clarification_question == "Which grade are you in and which exam are you preparing for?"
        assert validated.answer == "Which grade are you in and which exam are you preparing for?"
    finally:
        app.dependency_overrides.clear()


def test_human_handoff_response(client):
    """Test 5: Human handoff / escalation query yields escalated status."""
    fake_result = {
        "session_id": "test-session-4",
        "query": "I want to speak with a manager to file a complaint",
        "intent": "C15_GRIEVANCE_HUMAN_HANDOFF",
        "human_escalation_required": True,
        "metadata": {
            "routing_decision": {"route": "HUMAN_HANDOFF"},
        },
    }

    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(fake_result)
    try:
        response = client.post(
            "/api/v1/response",
            json={"session_id": "test-session-4", "message": "I want to speak with a manager to file a complaint"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-4"
        assert validated.status == "escalated"
        assert validated.intent == QueryIntent.GRIEVANCE_HUMAN_HANDOFF
        assert "counseling" in validated.answer.lower() or "representative" in validated.answer.lower() or "escalated" in validated.answer.lower()
    finally:
        app.dependency_overrides.clear()


def test_invalid_empty_message(client):
    """Test 6: Empty message rejected with 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/response",
        json={"session_id": "test-session-5", "message": ""},
    )
    assert response.status_code == 422


def test_invalid_empty_session_id(client):
    """Test 7: Empty or whitespace-only session_id rejected with 422."""
    response = client.post(
        "/api/v1/response",
        json={"session_id": "   ", "message": "Valid query message"},
    )
    assert response.status_code == 422


def test_graph_runtime_failure_handling(client):
    """Test 8: Graph runtime exception is caught gracefully and returns error status."""
    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(
        RuntimeError("Internal graph execution engine crash")
    )
    try:
        response = client.post(
            "/api/v1/response",
            json={"session_id": "test-session-6", "message": "Trigger unexpected crash"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-6"
        assert validated.status == "error"
        assert "error occurred" in validated.answer.lower()
        assert "crash" not in validated.answer.lower()  # no internal trace leakage
    finally:
        app.dependency_overrides.clear()


def test_graph_input_contract_and_context(client):
    """Test 9: Verify graph input receives session_id and query matching the request."""
    fake_graph = FakeGraph({
        "session_id": "session-xyz",
        "query": "What is the fee?",
        "draft_answer": "Fees are discussed in counseling.",
    })
    app.dependency_overrides[get_response_graph] = lambda: fake_graph
    try:
        response = client.post(
            "/api/v1/response",
            json={"session_id": "session-xyz", "message": "What is the fee?"},
        )
        assert response.status_code == 200
        assert fake_graph.last_input == {
            "session_id": "session-xyz",
            "query": "What is the fee?",
            "metadata": {},
        }
    finally:
        app.dependency_overrides.clear()


def test_insufficient_evidence_fallback(client):
    """Test 10: Missing draft answer due to insufficient evidence maps to escalated status with user guidance."""
    fake_result = {
        "session_id": "test-session-7",
        "query": "Obscure question",
        "intent": "C2_COURSE_DETAILS",
        "draft_answer": None,
        "metadata": {"generation_status": "skipped_insufficient_evidence"},
    }
    app.dependency_overrides[get_response_graph] = lambda: FakeGraph(fake_result)
    try:
        response = client.post(
            "/response",
            json={"session_id": "test-session-7", "message": "Obscure question"},
        )
        assert response.status_code == 200
        data = response.json()
        validated = ResponseResponse.model_validate(data)
        assert validated.session_id == "test-session-7"
        assert validated.status == "escalated"
        assert "admissions" in validated.answer.lower() or "assistance" in validated.answer.lower()
    finally:
        app.dependency_overrides.clear()

