import json

from app.agent.nodes.generation import generation_node
from app.agent.generator import AnswerGenerator, DraftAnswerModel
from app.agent.executor import set_global_execution_engine, ExecutionEngine
from app.schemas.agent import AgentState, ToolResult, RetrievedDocument
from app.agent.result_checker import ResultCheckResult


class StubClient:
    def generate(self, prompt: str) -> str:
        # Return a valid JSON draft matching DraftAnswerModel
        out = {
            "draft_answer": "Stubbed answer based on structured data.",
            "used_structured": True,
            "used_rag": False,
            "evidence": [{"source": "STRUCTURED", "id": "get_fee", "note": "program_fee"}],
            "confidence": 0.9,
        }
        return json.dumps(out)


def test_generation_with_sufficient_evidence(monkeypatch):
    # Prepare state with result_check indicating sufficiency
    state = AgentState(session_id="s", query="q")
    state.tool_results = [ToolResult(tool_name="get_fee", success=True, data={"amount": 1000}, metadata={"source": "structured_database"})]
    state.retrieved_documents = []
    state.result_check = ResultCheckResult(is_sufficient=True, has_successful_results=True, confidence_score=0.9)
    # Inject stub client into generator by monkeypatching AnswerGenerator.__init__
    monkeypatch.setattr('app.agent.generator.AnswerGenerator.__init__', lambda self, client=None: setattr(self, 'client', StubClient()) or None)

    updated = generation_node(state)
    assert updated.draft_answer is not None
    assert updated.metadata.get("generation_status") == "ok"


def test_generation_skipped_on_insufficient():
    state = AgentState(session_id="s", query="q")
    state.tool_results = []
    state.retrieved_documents = []
    state.result_check = ResultCheckResult(is_sufficient=False, requires_clarification=True)
    updated = generation_node(state)
    assert updated.draft_answer is None
    assert updated.metadata.get("generation_status") == "skipped_insufficient_evidence"
