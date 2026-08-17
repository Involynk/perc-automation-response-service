import pytest

from app.schemas.agent import AgentState, ToolResult
from app.agent.executor import ExecutionEngine, set_global_execution_engine
from app.agent.nodes.execution import execution_node
from app.agent.router import RouteType


class FakeStructuredService:
    def __init__(self):
        self.courses = {"bca": type("C", (), {"id": "bca", "name": "BCA", "fee": 1000})}

    def get_course_by_name(self, name):
        if not name:
            return None
        if name.lower().startswith("bca"):
            return type("C", (), {"id": "bca", "name": "BCA"})
        return None

    def get_program_fee(self, course_id):
        if course_id == "bca":
            return type("F", (), {"model_dump": lambda self=None: {"amount": 1000}})()
        return None


class FakeRetriever:
    def search(self, query, top_k=3, **kwargs):
        # return simple RetrievedDocument-like objects
        from app.schemas.agent import RetrievedDocument

        return [RetrievedDocument(doc_id="d1", chunk_id="c1", source_file="doc.md", content="content", relevance_score=0.9, metadata={})]


def test_structured_get_fee_execution(monkeypatch):
    # Setup fake engine with fake service + retriever
    svc = FakeStructuredService()
    retr = FakeRetriever()
    engine = ExecutionEngine(structured_service=svc, retriever=retr)
    set_global_execution_engine(engine)

    state = AgentState(session_id="s1", query="What is the BCA fee?", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    # Simulate routing decision
    state.metadata = {"routing_decision": {"route": RouteType.STRUCTURED_TOOL.value, "tool_name": "get_fee", "confidence": 0.9}}

    updated = execution_node(state)
    assert isinstance(updated.tool_results, list)
    # Expect at least one ToolResult
    assert any(tr.tool_name == "get_fee" or tr.tool_name == "get_fee" for tr in updated.tool_results)


def test_rag_execution(monkeypatch):
    svc = FakeStructuredService()
    retr = FakeRetriever()
    engine = ExecutionEngine(structured_service=svc, retriever=retr)
    set_global_execution_engine(engine)

    state = AgentState(session_id="s2", query="What are required documents?", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    state.metadata = {"routing_decision": {"route": RouteType.RAG.value, "confidence": 0.8}}

    updated = execution_node(state)
    assert len(updated.retrieved_documents) == 1
    assert any(tr.tool_name == "rag_search" for tr in updated.tool_results)


def test_multi_intent_execution(monkeypatch):
    svc = FakeStructuredService()
    retr = FakeRetriever()
    engine = ExecutionEngine(structured_service=svc, retriever=retr)
    set_global_execution_engine(engine)

    # Multi intent with one structured (get_fee) and one rag
    sub1 = {"route": RouteType.STRUCTURED_TOOL.value, "tool_name": "get_fee", "confidence": 0.9}
    sub2 = {"route": RouteType.RAG.value, "confidence": 0.8}
    state = AgentState(session_id="s3", query="Multi question", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    state.metadata = {"routing_decision": {"route": RouteType.MULTI_INTENT.value, "sub_routes": [sub1, sub2], "confidence": 0.9}}

    updated = execution_node(state)
    # Expect both fee and rag_search results
    assert any(tr.tool_name == "get_fee" for tr in updated.tool_results)
    assert any(tr.tool_name == "rag_search" for tr in updated.tool_results)


def test_clarification_and_handoff_and_safe_stop(monkeypatch):
    svc = FakeStructuredService()
    retr = FakeRetriever()
    engine = ExecutionEngine(structured_service=svc, retriever=retr)
    set_global_execution_engine(engine)

    # Clarification
    state_c = AgentState(session_id="c1", query="?", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    state_c.metadata = {"routing_decision": {"route": RouteType.CLARIFICATION.value}}
    updated_c = execution_node(state_c)
    assert updated_c.metadata.get("execution_status") == "awaiting_clarification"

    # Human handoff
    state_h = AgentState(session_id="h1", query="?", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    state_h.metadata = {"routing_decision": {"route": RouteType.HUMAN_HANDOFF.value}}
    updated_h = execution_node(state_h)
    assert updated_h.metadata.get("execution_status") == "human_handoff"
    assert updated_h.human_escalation_required is True

    # Safe stop
    state_s = AgentState(session_id="s1", query="?", entities={}, ambiguity={}, selected_tools=[], tool_results=[], retrieved_documents=[])
    state_s.metadata = {"routing_decision": {"route": RouteType.SAFE_STOP.value}}
    updated_s = execution_node(state_s)
    assert updated_s.metadata.get("execution_status") == "safe_stop"
