from app.schemas.agent import AgentState, ToolResult, QueryIntent
from app.agent.generator import DraftAnswerModel
from app.agent.result_validator import validate_draft
from app.agent.result_checker import ResultCheckResult


def test_validation_passes_with_structured_fee_evidence():
    state = AgentState(session_id="s1", query="What is the fee?")
    state.intent = QueryIntent.FEES_PRICING
    # structured tool result with fee
    tr = ToolResult(tool_name="get_fee", success=True, data={"amount": 1000}, metadata={"source": "structured_database"})
    state.tool_results = [tr]
    # result_check indicates sufficiency and structured authority
    state.result_check = ResultCheckResult(is_sufficient=True, evidence_count=1, authoritative_sources=["STRUCTURED"]) 

    draft = DraftAnswerModel(draft_answer="The fee is 1000", used_structured=True, used_rag=False, evidence=[{"tool_name":"get_fee","amount":1000}], confidence=0.9)

    res = validate_draft(state, draft)
    assert res.is_valid is True
    assert res.is_grounded is True
    assert res.hallucination_detected is False


def test_validation_detects_fee_hallucination():
    state = AgentState(session_id="s2", query="What is the fee?")
    state.intent = QueryIntent.FEES_PRICING
    # no structured fee results
    state.tool_results = []
    state.result_check = ResultCheckResult(is_sufficient=False, evidence_count=0, authoritative_sources=["RAG"])

    # draft claims a numeric fee but used_structured=False and no evidence
    draft = DraftAnswerModel(draft_answer="The fee is 1200", used_structured=False, used_rag=True, evidence=[], confidence=0.8)

    res = validate_draft(state, draft)
    assert res.is_valid is False
    assert res.hallucination_detected is True
    assert "fee_claim_without_structured_evidence" in res.issues


def test_validation_respects_human_handoff_flag():
    state = AgentState(session_id="s3", query="I want to escalate")
    state.result_check = ResultCheckResult(requires_human_handoff=True)
    draft = DraftAnswerModel(draft_answer="Please talk to support", used_structured=False, used_rag=False, evidence=[], confidence=0.5)

    res = validate_draft(state, draft)
    assert res.is_valid is False
    assert res.requires_human_handoff is True
