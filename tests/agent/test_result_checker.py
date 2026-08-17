import pytest

from app.agent.result_checker import evaluate_result_check, ResultCheckResult
from app.schemas.agent import ToolResult, RetrievedDocument
from app.schemas.agent import AgentState
from app.agent.router import RouteType


def tr_structured_success(data=None, tool_name="get_fee"):
    return ToolResult(tool_name=tool_name, success=True, data=data, error=None, metadata={"source": "structured_database"})


def tr_structured_failure(tool_name="get_fee"):
    return ToolResult(tool_name=tool_name, success=False, data=None, error="db error", metadata={"source": "structured_database"})


def rd_dict(route, sub_routes=None):
    d = {"route": route}
    if sub_routes is not None:
        d["sub_routes"] = sub_routes
    return d


def test_successful_structured_result():
    state = AgentState(session_id="s", query="q")
    state.tool_results = [tr_structured_success(data={"amount": 1000})]
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.STRUCTURED_TOOL.value)}
    rc = evaluate_result_check(state)
    assert rc.has_successful_results
    assert "STRUCTURED" in rc.authoritative_sources
    assert rc.confidence_score > 0.5


def test_failed_structured_result():
    state = AgentState(session_id="s", query="q")
    state.tool_results = [tr_structured_failure()]
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.STRUCTURED_TOOL.value)}
    rc = evaluate_result_check(state)
    assert rc.has_failed_results
    assert rc.has_successful_results is False


def test_empty_structured_result():
    state = AgentState(session_id="s", query="q")
    state.tool_results = [tr_structured_success(data={})]
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.STRUCTURED_TOOL.value)}
    rc = evaluate_result_check(state)
    assert rc.has_empty_results
    assert rc.is_sufficient is False


def test_successful_rag_result():
    state = AgentState(session_id="s", query="q")
    doc = RetrievedDocument(doc_id="d1", chunk_id="c1", source_file="f.txt", content="content", relevance_score=0.9, metadata={})
    state.tool_results = []
    state.retrieved_documents = [doc]
    state.metadata = {"routing_decision": rd_dict(RouteType.RAG.value)}
    rc = evaluate_result_check(state)
    assert rc.has_successful_results
    assert "RAG" in rc.authoritative_sources


def test_empty_rag_result():
    state = AgentState(session_id="s", query="q")
    state.tool_results = []
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.RAG.value)}
    rc = evaluate_result_check(state)
    assert rc.has_empty_results
    assert rc.is_sufficient is False


def test_low_relevance_rag():
    state = AgentState(session_id="s", query="q")
    doc = RetrievedDocument(doc_id="d1", chunk_id="c1", source_file="f.txt", content="content", relevance_score=0.5, metadata={})
    state.retrieved_documents = [doc]
    state.tool_results = []
    state.metadata = {"routing_decision": rd_dict(RouteType.RAG.value)}
    rc = evaluate_result_check(state, min_rag_relevance=0.7)
    # evidence exists but below threshold counted separately; overall sufficiency should be False
    assert rc.evidence_count == 1
    assert rc.is_sufficient is False


def test_structured_over_rag_conflict_detection():
    state = AgentState(session_id="s", query="q")
    # structured says amount 1000
    state.tool_results = [tr_structured_success(data={"amount": 1000})]
    # rag doc metadata claims different amount
    doc = RetrievedDocument(doc_id="d1", chunk_id="c1", source_file="f.txt", content="content", relevance_score=0.9, metadata={"amount": 2000})
    state.retrieved_documents = [doc]
    state.metadata = {"routing_decision": rd_dict(RouteType.MULTI_INTENT.value)}
    rc = evaluate_result_check(state)
    assert rc.has_conflicts
    assert any("Conflict on amount" in issue for issue in rc.issues)


def test_multi_intent_per_intent_evidence():
    state = AgentState(session_id="s", query="q")
    state.tool_results = [tr_structured_success(data={"amount": 1000})]
    doc = RetrievedDocument(doc_id="d1", chunk_id="c1", source_file="f.txt", content="content", relevance_score=0.9, metadata={})
    state.retrieved_documents = [doc]
    sub1 = {"route": RouteType.STRUCTURED_TOOL.value, "tool_name": "get_fee"}
    sub2 = {"route": RouteType.RAG.value}
    state.metadata = {"routing_decision": {"route": RouteType.MULTI_INTENT.value, "sub_routes": [sub1, sub2]}}
    rc = evaluate_result_check(state)
    assert rc.per_intent_evidence is not None
    assert any(p["route"] == RouteType.STRUCTURED_TOOL.value for p in rc.per_intent_evidence)


def test_clarification_handoff_safe_stop_handling():
    state = AgentState(session_id="s", query="q")
    state.metadata = {"routing_decision": rd_dict(RouteType.CLARIFICATION.value)}
    rc = evaluate_result_check(state)
    assert rc.requires_clarification

    state.metadata = {"routing_decision": rd_dict(RouteType.HUMAN_HANDOFF.value)}
    rc = evaluate_result_check(state)
    assert rc.requires_human_handoff

    state.metadata = {"routing_decision": rd_dict(RouteType.SAFE_STOP.value)}
    rc = evaluate_result_check(state)
    assert rc.is_sufficient is False


def test_partial_tool_failure():
    state = AgentState(session_id="s", query="q")
    state.tool_results = [tr_structured_success(data={"a": 1}), tr_structured_failure(tool_name="get_branch_info")]
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.MULTI_INTENT.value)}
    rc = evaluate_result_check(state)
    assert rc.has_successful_results
    assert rc.has_failed_results


def test_no_evidence():
    state = AgentState(session_id="s", query="q")
    state.tool_results = []
    state.retrieved_documents = []
    state.metadata = {"routing_decision": rd_dict(RouteType.STRUCTURED_TOOL.value)}
    rc = evaluate_result_check(state)
    assert rc.evidence_count == 0
    assert rc.is_sufficient is False
