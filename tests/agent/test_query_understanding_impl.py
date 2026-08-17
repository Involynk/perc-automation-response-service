import json
from pathlib import Path

from app.agent.nodes.understand import understand_node
from app.schemas.request import ResponseRequest
from app.schemas.agent import AgentState


CASE_FILE = Path("tests/agent/query_understanding_cases.json")


def _run_case(case):
    req = ResponseRequest(session_id="t1", message=case["query"])
    st = AgentState(session_id=req.session_id, query=req.message)
    if case.get("context"):
        st.metadata = dict(st.metadata or {})
        st.metadata["conversation_context"] = case.get("context")
    out = understand_node(st)
    return out


def test_all_cases_classification_and_entities():
    cases = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    assert len(cases) >= 18

    for case in cases:
        out = _run_case(case)
        expected = case["expected_primary_intent"]
        assert out.intent.value == expected

        # validate multi-intent where expected
        if case.get("expected_secondary_intents"):
            exp_sec = case["expected_secondary_intents"]
            assert all(s in [i.value for i in out.secondary_intents] for s in exp_sec)

        # ambiguity expectations
        if case.get("expected_ambiguity"):
            exp_amb = case["expected_ambiguity"]
            assert out.ambiguity.is_ambiguous == exp_amb.get("is_ambiguous", False)


def test_empty_query_results_ambiguous():
    st = AgentState(session_id="t2", query="")
    out = understand_node(st)
    assert out.ambiguity.is_ambiguous


def test_provider_malformed_output_handling(monkeypatch):
    # simulate provider returning bad shape
    from app.agent.providers.query_understanding import MockDataProvider

    def bad_analyze(self, q, context=None):
        return "not-a-dict"

    monkeypatch.setattr(MockDataProvider, "analyze", bad_analyze)
    st = AgentState(session_id="t3", query="What courses?")
    try:
        understand_node(st)
        assert False, "Expected ValueError for malformed provider output"
    except ValueError:
        pass


def test_provider_invalid_confidence(monkeypatch):
    from app.agent.providers.query_understanding import MockDataProvider

    def bad_conf(self, q, context=None):
        return {"primary_intent": "C1_COURSE_DISCOVERY", "confidence": 2.0}

    monkeypatch.setattr(MockDataProvider, "analyze", bad_conf)
    st = AgentState(session_id="t4", query="What courses?")
    try:
        understand_node(st)
        assert False, "Expected ValueError for invalid confidence"
    except ValueError:
        pass
