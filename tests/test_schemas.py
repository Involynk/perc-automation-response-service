import pytest
from pydantic import ValidationError

from app.schemas import (
    AgentState,
    AmbiguityCheck,
    ExtractedEntities,
    QueryIntent,
    ResponseRequest,
    ResponseResponse,
    RetrievedDocument,
    ToolResult,
    ToolSelection,
    ValidationResult,
)


def test_valid_response_request():
    """Test 1: Valid ResponseRequest."""
    req = ResponseRequest(session_id="session-123", message="What is the fee for JEE?")
    assert req.session_id == "session-123"
    assert req.message == "What is the fee for JEE?"


def test_empty_message_rejected():
    """Test 2: Empty message rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ResponseRequest(session_id="session-123", message="")
    assert "message" in str(exc_info.value)


def test_whitespace_only_message_rejected():
    """Test 3: Whitespace-only message rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ResponseRequest(session_id="session-123", message="   \n\t   ")
    assert "message" in str(exc_info.value)


def test_empty_session_id_rejected():
    """Test 3b: Empty or whitespace-only session_id rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ResponseRequest(session_id="   ", message="What courses do you offer?")
    assert "session_id" in str(exc_info.value)


def test_valid_agent_state():
    """Test 4: Valid AgentState representation."""
    state = AgentState(
        session_id="session-123",
        query="Tell me about NEET Foundation for Class 9",
        intent=QueryIntent.COURSE_DETAILS,
        entities=ExtractedEntities(
            course="NEET Foundation",
            target_class="Class 9",
            exam="NEET",
        ),
    )
    assert state.session_id == "session-123"
    assert state.intent == QueryIntent.COURSE_DETAILS
    assert state.entities.course == "NEET Foundation"
    assert state.entities.target_class == "Class 9"
    assert state.human_escalation_required is False


def test_valid_intent():
    """Test 5: Valid QueryIntent Enum usage."""
    intent = QueryIntent.FEES_PRICING
    assert intent == "C3_FEES_PRICING"
    assert QueryIntent("C3_FEES_PRICING") == QueryIntent.FEES_PRICING
    assert QueryIntent.GRIEVANCE_HUMAN_HANDOFF == "C15_GRIEVANCE_HUMAN_HANDOFF"


def test_invalid_intent_rejected():
    """Test 6: Invalid intent string rejected by QueryIntent Enum."""
    with pytest.raises(ValueError):
        QueryIntent("INVALID_INTENT_CATEGORY")


def test_ambiguous_query_representation():
    """Test 7: Ambiguous query representation."""
    ambiguity = AmbiguityCheck(
        is_ambiguous=True,
        missing_information=["target_class", "exam_target"],
        clarification_required=True,
        clarification_question="Which class is your child in, and which exam are they preparing for?",
    )
    assert ambiguity.is_ambiguous is True
    assert ambiguity.clarification_required is True
    assert len(ambiguity.missing_information) == 2
    assert ambiguity.clarification_question.startswith("Which class")


def test_tool_result_success():
    """Test 8: Successful ToolResult object."""
    result = ToolResult(
        tool_name="get_course_info",
        success=True,
        data={"name": "IIT-JEE Advanced", "duration": "2 Years", "batch_size": "15-20 students"},
        metadata={"execution_time_ms": 12},
    )
    assert result.tool_name == "get_course_info"
    assert result.success is True
    assert result.data["name"] == "IIT-JEE Advanced"
    assert result.error is None


def test_tool_result_failure():
    """Test 9: Failed ToolResult object."""
    result = ToolResult(
        tool_name="get_fee",
        success=False,
        error="Fee query restricted; fees are provided during demo counseling session.",
        metadata={"error_code": "FEES_NOT_PUBLIC"},
    )
    assert result.tool_name == "get_fee"
    assert result.success is False
    assert "FEES_NOT_PUBLIC" in result.metadata["error_code"]
    assert result.data is None


def test_final_response_validation():
    """Test 10: Final ResponseResponse validation."""
    response = ResponseResponse(
        session_id="session-123",
        answer="PERC offers IIT-JEE Advanced coaching for Classes 11-12. Please contact PERC for fee details.",
        status="success",
        intent=QueryIntent.COURSE_DETAILS,
        sources=["courses.json", "course-details.md"],
    )
    assert response.session_id == "session-123"
    assert response.status == "success"
    assert response.intent == QueryIntent.COURSE_DETAILS
    assert len(response.sources) == 2
    assert response.clarification_required is False


def test_extracted_entities_alias_and_extensibility():
    """Test ExtractedEntities supporting 'class' alias and additional entities."""
    entities = ExtractedEntities.model_validate({
        "course": "PERC Ignite",
        "class": "Class 6",
        "additional_entities": {"preferred_slot": "B1"},
    })
    assert entities.course == "PERC Ignite"
    assert entities.target_class == "Class 6"
    assert entities.additional_entities["preferred_slot"] == "B1"


def test_retrieved_document_and_validation_result():
    """Test RetrievedDocument and ValidationResult contracts."""
    doc = RetrievedDocument(
        doc_id="doc-1",
        chunk_id="chunk-3",
        source_file="policies.md",
        content="PERC maintains a strict batch size limit of 15 to 20 students.",
        relevance_score=0.92,
    )
    assert doc.relevance_score == 0.92
    assert doc.source_file == "policies.md"

    val = ValidationResult(
        is_valid=True,
        is_grounded=True,
        is_safe=True,
        confidence_score=0.98,
    )
    assert val.is_valid is True
    assert val.hallucination_detected is False